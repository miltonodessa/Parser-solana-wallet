"""
WalletAnalyzer: high-level summary statistics over a list of decoded transactions.

Produces:
  • summary dict    – totals and aggregated stats
  • transfers list  – every SOL / token transfer involving the wallet
  • swaps list      – detected DEX swap events
  • nft_events list – detected NFT mint / transfer / sale events
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from programs.known_programs import get_program_category


class WalletAnalyzer:
    """Compute analytics over decoded transaction records."""

    DEX_CATEGORIES = {"dex"}
    NFT_CATEGORIES = {"nft"}
    TOKEN_PROGRAMS = {
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    }

    def __init__(self, wallet_address: str) -> None:
        self.wallet = wallet_address

    # ── Public interface ───────────────────────────────────────────────────────

    def analyze(self, records: list[dict]) -> dict[str, Any]:
        """
        Run all analyses and return a combined result dict.

        Returns:
            {
              "summary":    {...},
              "sol_transfers":   [...],
              "token_transfers": [...],
              "swaps":      [...],
              "nft_events": [...],
              "programs_used": {...},
            }
        """
        return {
            "summary": self._summary(records),
            "sol_transfers": self._sol_transfers(records),
            "token_transfers": self._token_transfers(records),
            "swaps": self._swaps(records),
            "nft_events": self._nft_events(records),
            "programs_used": self._programs_used(records),
        }

    # ── Summary ────────────────────────────────────────────────────────────────

    def _summary(self, records: list[dict]) -> dict[str, Any]:
        total = len(records)
        successful = sum(1 for r in records if r.get("success"))
        failed = total - successful

        total_fees_lamports = sum(r.get("fee_lamports", 0) for r in records)

        # Net SOL flow for the wallet
        net_sol = 0.0
        for r in records:
            if not r.get("success"):
                continue
            for chg in r.get("sol_changes", []):
                if chg["account"] == self.wallet:
                    net_sol += chg["delta_sol"]

        # First / last transaction timestamps
        times = [r["block_time"] for r in records if r.get("block_time")]
        first_ts = min(times) if times else None
        last_ts = max(times) if times else None

        # Unique programs
        program_ids: set[str] = set()
        for r in records:
            for ix in r.get("instructions", []):
                program_ids.add(ix["program_id"])

        # Token mints interacted with
        mints: set[str] = set()
        for r in records:
            for chg in r.get("token_changes", []):
                if chg.get("mint"):
                    mints.add(chg["mint"])

        return {
            "wallet": self.wallet,
            "total_transactions": total,
            "successful_transactions": successful,
            "failed_transactions": failed,
            "total_fees_lamports": total_fees_lamports,
            "total_fees_sol": total_fees_lamports / 1e9,
            "net_sol_change": net_sol,
            "unique_programs": len(program_ids),
            "unique_token_mints": len(mints),
            "first_transaction_time": first_ts,
            "last_transaction_time": last_ts,
        }

    # ── SOL transfers ──────────────────────────────────────────────────────────

    def _sol_transfers(self, records: list[dict]) -> list[dict]:
        transfers = []
        for r in records:
            if not r.get("success"):
                continue
            for ix in r.get("instructions", []) + r.get("inner_instructions", []):
                decoded = ix.get("decoded")
                # decoded can be a string (e.g. Memo program returns plain text)
                if not isinstance(decoded, dict):
                    continue


                # jsonParsed format: {"type": "transfer", "info": {...}}
                if decoded.get("type") == "transfer":
                    info = decoded.get("info", {})
                    if isinstance(info, dict):
                        src = info.get("source", "")
                        dst = info.get("destination", "")
                        lamports = info.get("lamports", 0)
                        if lamports and (src == self.wallet or dst == self.wallet):
                            transfers.append({
                                "signature": r["signature"],
                                "block_time": r["block_time"],
                                "block_time_utc": r["block_time_utc"],
                                "direction": "out" if src == self.wallet else "in",
                                "from": src,
                                "to": dst,
                                "lamports": lamports,
                                "sol": lamports / 1e9,
                                "program": ix.get("program_name", ""),
                            })
                        continue

                # Our decoded format for System Program Transfer
                params = decoded.get("params", {})
                if isinstance(params, dict) and "lamports" in params and decoded.get("type") == "Transfer":
                    src = params.get("from", "")
                    dst = params.get("to", "")
                    lamports = params.get("lamports", 0)
                    if lamports and (src == self.wallet or dst == self.wallet):
                        transfers.append({
                            "signature": r["signature"],
                            "block_time": r["block_time"],
                            "block_time_utc": r["block_time_utc"],
                            "direction": "out" if src == self.wallet else "in",
                            "from": src,
                            "to": dst,
                            "lamports": lamports,
                            "sol": lamports / 1e9,
                            "program": ix.get("program_name", ""),
                        })

        return transfers

    # ── Token transfers ────────────────────────────────────────────────────────

    def _token_transfers(self, records: list[dict]) -> list[dict]:
        transfers = []
        for r in records:
            if not r.get("success"):
                continue
            for chg in r.get("token_changes", []):
                if chg.get("owner") == self.wallet and chg.get("delta") != 0:
                    transfers.append({
                        "signature": r["signature"],
                        "block_time": r["block_time"],
                        "block_time_utc": r["block_time_utc"],
                        "direction": "in" if chg["delta"] > 0 else "out",
                        "mint": chg["mint"],
                        "owner": chg["owner"],
                        "delta": chg["delta"],
                        "ui_delta": chg["ui_delta"],
                        "decimals": chg["decimals"],
                        "pre_amount": chg["pre_amount"],
                        "post_amount": chg["post_amount"],
                    })
        return transfers

    # ── Swap detection ─────────────────────────────────────────────────────────

    def _swaps(self, records: list[dict]) -> list[dict]:
        """
        Detect swap events: transactions that involve a known DEX program
        and have at least two different token balance changes.
        """
        swaps = []
        for r in records:
            if not r.get("success"):
                continue

            uses_dex = any(
                get_program_category(ix.get("program_id", "")) in self.DEX_CATEGORIES
                for ix in r.get("instructions", []) + r.get("inner_instructions", [])
            )
            if not uses_dex:
                continue

            token_changes = r.get("token_changes", [])
            wallet_changes = [c for c in token_changes if c.get("owner") == self.wallet]

            if len(wallet_changes) < 2:
                # Might still be a swap with only one side visible; include anyway
                if len(wallet_changes) == 0 and not uses_dex:
                    continue

            # Identify input (negative) and output (positive) tokens
            tokens_in = [c for c in wallet_changes if c["delta"] < 0]
            tokens_out = [c for c in wallet_changes if c["delta"] > 0]

            sol_change = next(
                (c for c in r.get("sol_changes", []) if c["account"] == self.wallet), None
            )

            dex_programs = [
                ix.get("program_name")
                for ix in r.get("instructions", [])
                if get_program_category(ix.get("program_id", "")) in self.DEX_CATEGORIES
            ]

            swaps.append({
                "signature": r["signature"],
                "block_time": r["block_time"],
                "block_time_utc": r["block_time_utc"],
                "dex_programs": list(set(filter(None, dex_programs))),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "sol_delta": sol_change["delta_sol"] if sol_change else None,
                "fee_sol": r.get("fee_sol", 0),
            })

        return swaps

    # ── NFT events ─────────────────────────────────────────────────────────────

    def _nft_events(self, records: list[dict]) -> list[dict]:
        """Detect NFT-related events (mint, transfer, burn, list/sale)."""
        events = []
        for r in records:
            uses_nft_program = any(
                get_program_category(ix.get("program_id", "")) in self.NFT_CATEGORIES
                for ix in r.get("instructions", []) + r.get("inner_instructions", [])
            )
            if not uses_nft_program:
                continue

            # Look for token changes with amount == 1 (NFTs are amount=1)
            nft_changes = [
                c for c in r.get("token_changes", [])
                if abs(c.get("delta", 0)) == 1 and c.get("decimals", 0) == 0
            ]

            nft_programs = [
                ix.get("program_name")
                for ix in r.get("instructions", [])
                if get_program_category(ix.get("program_id", "")) in self.NFT_CATEGORIES
            ]

            sol_change = next(
                (c for c in r.get("sol_changes", []) if c["account"] == self.wallet), None
            )

            events.append({
                "signature": r["signature"],
                "block_time": r["block_time"],
                "block_time_utc": r["block_time_utc"],
                "success": r.get("success"),
                "nft_programs": list(set(filter(None, nft_programs))),
                "nft_token_changes": nft_changes,
                "sol_delta": sol_change["delta_sol"] if sol_change else None,
            })

        return events

    # ── Programs usage ─────────────────────────────────────────────────────────

    def _programs_used(self, records: list[dict]) -> dict[str, int]:
        """Count how many times each program was invoked."""
        counts: dict[str, int] = defaultdict(int)
        for r in records:
            for ix in r.get("instructions", []):
                name = ix.get("program_name") or ix.get("program_id", "unknown")
                counts[name] += 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))
