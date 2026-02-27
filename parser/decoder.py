"""
TransactionDecoder: turns raw jsonParsed RPC data into clean, flat records.

The Solana RPC node's jsonParsed encoding already decodes instructions for
well-known programs (System, SPL Token, etc.).  For unknown programs we fall
back to our own program-specific decoders, then raw base-58 data.

Output schema (one dict per transaction)
─────────────────────────────────────────
{
  # ── Identity ────────────────────────────────────────────────
  "signature":           str,
  "slot":                int,
  "block_time":          int | None,       # Unix timestamp
  "block_time_utc":      str | None,       # ISO-8601

  # ── Status ──────────────────────────────────────────────────
  "success":             bool,
  "error":               str | None,       # stringified error if failed
  "fee_lamports":        int,
  "fee_sol":             float,
  "fee_payer":           str,

  # ── Accounts ────────────────────────────────────────────────
  "accounts":            list[str],        # all accounts in the tx message
  "writable_accounts":   list[str],
  "signer_accounts":     list[str],

  # ── SOL balance changes ─────────────────────────────────────
  "sol_changes":         list[{account, pre_lamports, post_lamports, delta_lamports, delta_sol}],

  # ── Token balance changes ───────────────────────────────────
  "token_changes":       list[{account, owner, mint, pre_amount, post_amount, delta, decimals, ui_delta}],

  # ── Instructions (outer) ────────────────────────────────────
  "instructions":        list[InstructionRecord],

  # ── Inner instructions ───────────────────────────────────────
  "inner_instructions":  list[InnerInstructionRecord],

  # ── Log messages ────────────────────────────────────────────
  "log_messages":        list[str],

  # ── Loaded addresses (v0 / ALT) ──────────────────────────────
  "loaded_writable":     list[str],
  "loaded_readonly":     list[str],

  # ── Memo ────────────────────────────────────────────────────
  "memo":                str | None,

  # ── Versioning ──────────────────────────────────────────────
  "version":             str,              # "legacy" | "0"
}

InstructionRecord:
{
  "index":               int,
  "program_id":          str,
  "program_name":        str,
  "program_category":    str,
  "accounts":            list[str],
  "data_raw":            str | None,       # base-58 raw data
  "decoded":             dict | None,      # jsonParsed or our decoder output
  "is_parsed":           bool,             # True if RPC returned parsed info
}
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from programs.known_programs import get_program_name, get_program_category
from programs.system import decode_system_instruction
from programs.spl_token import decode_token_instruction

logger = logging.getLogger(__name__)

_SYSTEM_PROGRAM = "11111111111111111111111111111111"
_SPL_TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
_TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"


class TransactionDecoder:
    """Converts raw RPC getTransaction results into structured records."""

    # ── Public interface ───────────────────────────────────────────────────────

    def decode(
        self,
        sig_info: dict,
        tx_data: Optional[dict],
        wallet_address: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Decode one transaction.

        Args:
            sig_info:       Entry from getSignaturesForAddress (has 'signature',
                            'slot', 'blockTime', 'err', 'memo').
            tx_data:        Result of getTransaction (may be None if not found).
            wallet_address: The wallet being analysed (used for context).

        Returns:
            Flat dict ready for CSV/JSON export.
        """
        signature = sig_info.get("signature", "")
        slot = sig_info.get("slot")
        block_time = sig_info.get("blockTime") or (tx_data.get("blockTime") if tx_data else None)
        err_from_sig = sig_info.get("err")

        record: dict[str, Any] = {
            "signature": signature,
            "slot": slot,
            "block_time": block_time,
            "block_time_utc": _ts_to_iso(block_time),
            "success": err_from_sig is None,
            "error": str(err_from_sig) if err_from_sig else None,
            "fee_lamports": 0,
            "fee_sol": 0.0,
            "fee_payer": "",
            "accounts": [],
            "writable_accounts": [],
            "signer_accounts": [],
            "sol_changes": [],
            "token_changes": [],
            "instructions": [],
            "inner_instructions": [],
            "log_messages": [],
            "loaded_writable": [],
            "loaded_readonly": [],
            "memo": sig_info.get("memo"),
            "version": "legacy",
            "wallet_address": wallet_address or "",
        }

        if tx_data is None:
            record["error"] = record["error"] or "Transaction data not available"
            return record

        meta = tx_data.get("meta") or {}
        transaction = tx_data.get("transaction") or {}
        message = transaction.get("message") or {}

        # ── Version ────────────────────────────────────────────────────────────
        record["version"] = str(tx_data.get("version", "legacy"))

        # ── Fee / error ────────────────────────────────────────────────────────
        record["fee_lamports"] = meta.get("fee", 0)
        record["fee_sol"] = record["fee_lamports"] / 1e9
        if meta.get("err") and not err_from_sig:
            record["error"] = str(meta["err"])
            record["success"] = False

        # ── Accounts ───────────────────────────────────────────────────────────
        account_keys = _extract_account_keys(message)
        record["accounts"] = [a["pubkey"] for a in account_keys]
        record["writable_accounts"] = [
            a["pubkey"] for a in account_keys if a.get("writable")
        ]
        record["signer_accounts"] = [
            a["pubkey"] for a in account_keys if a.get("signer")
        ]
        record["fee_payer"] = record["signer_accounts"][0] if record["signer_accounts"] else ""

        # ── Loaded addresses (v0 transactions / address lookup tables) ─────────
        loaded = meta.get("loadedAddresses") or {}
        record["loaded_writable"] = loaded.get("writable") or []
        record["loaded_readonly"] = loaded.get("readonly") or []

        # Merge ALT addresses into the full accounts list for index resolution
        all_accounts: list[str] = (
            record["accounts"]
            + record["loaded_writable"]
            + record["loaded_readonly"]
        )

        # ── SOL balance changes ────────────────────────────────────────────────
        record["sol_changes"] = _decode_sol_changes(meta, all_accounts)

        # ── Token balance changes ──────────────────────────────────────────────
        record["token_changes"] = _decode_token_changes(meta)

        # ── Instructions ───────────────────────────────────────────────────────
        outer_ixs = message.get("instructions") or []
        record["instructions"] = [
            self._decode_instruction(i, ix, all_accounts)
            for i, ix in enumerate(outer_ixs)
        ]

        # ── Inner instructions ─────────────────────────────────────────────────
        inner_raw = meta.get("innerInstructions") or []
        record["inner_instructions"] = self._decode_inner_instructions(inner_raw, all_accounts)

        # ── Log messages ───────────────────────────────────────────────────────
        record["log_messages"] = meta.get("logMessages") or []

        # ── Memo (from instructions if not in sig_info) ────────────────────────
        if not record["memo"]:
            record["memo"] = _extract_memo(record["instructions"])

        return record

    # ── Instruction decoding ───────────────────────────────────────────────────

    def _decode_instruction(
        self,
        index: int,
        ix: dict,
        all_accounts: list[str],
    ) -> dict[str, Any]:
        """Decode a single instruction dict from the jsonParsed RPC response."""
        # jsonParsed already decoded
        if "parsed" in ix:
            program_id = ix.get("programId", "")
            # Prefer our lookup table name over the short RPC name (e.g. "system" → "System Program")
            from programs.known_programs import KNOWN_PROGRAMS as _KP
            known_name = _KP.get(program_id, {}).get("name")
            return {
                "index": index,
                "program_id": program_id,
                "program_name": known_name or ix.get("program") or program_id,
                "program_category": get_program_category(program_id),
                "accounts": ix.get("accounts", []),
                "data_raw": None,
                "decoded": ix["parsed"],
                "is_parsed": True,
            }

        # Raw instruction (unknown program or base58 data)
        program_id = ix.get("programId", "")
        accounts_indices = ix.get("accounts", [])
        # accounts can be either indices (legacy) or pubkeys (already resolved)
        resolved_accounts = _resolve_accounts(accounts_indices, all_accounts)
        raw_data: Optional[str] = ix.get("data")

        decoded = self._fallback_decode(program_id, raw_data or "", resolved_accounts)

        return {
            "index": index,
            "program_id": program_id,
            "program_name": get_program_name(program_id),
            "program_category": get_program_category(program_id),
            "accounts": resolved_accounts,
            "data_raw": raw_data,
            "decoded": decoded,
            "is_parsed": False,
        }

    def _decode_inner_instructions(
        self,
        inner_raw: list[dict],
        all_accounts: list[str],
    ) -> list[dict[str, Any]]:
        """Decode all inner instructions across all outer instruction indices."""
        result = []
        for group in inner_raw:
            outer_index = group.get("index", -1)
            for i, ix in enumerate(group.get("instructions") or []):
                decoded = self._decode_instruction(i, ix, all_accounts)
                decoded["outer_index"] = outer_index
                result.append(decoded)
        return result

    @staticmethod
    def _fallback_decode(
        program_id: str,
        raw_data: str,
        accounts: list[str],
    ) -> Optional[dict]:
        """Try our own decoders for known programs that the RPC didn't parse."""
        if not raw_data or raw_data == "base58":
            return None
        if program_id == _SYSTEM_PROGRAM:
            return decode_system_instruction(raw_data, accounts)
        if program_id in (_SPL_TOKEN, _TOKEN_2022):
            return decode_token_instruction(raw_data, accounts)
        return {"raw": raw_data}


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _ts_to_iso(ts: Optional[int]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _extract_account_keys(message: dict) -> list[dict]:
    """
    Return a list of {pubkey, signer, writable} dicts.

    The jsonParsed encoding already provides accountKeys as a list of objects
    with pubkey/signer/writable fields.
    """
    raw = message.get("accountKeys") or []
    result = []
    for entry in raw:
        if isinstance(entry, dict):
            result.append({
                "pubkey": entry.get("pubkey", ""),
                "signer": entry.get("signer", False),
                "writable": entry.get("writable", False),
            })
        elif isinstance(entry, str):
            result.append({"pubkey": entry, "signer": False, "writable": False})
    return result


def _resolve_accounts(indices_or_keys: list, all_accounts: list[str]) -> list[str]:
    """
    Convert account indices to public keys (or pass through if already keys).
    """
    resolved = []
    for item in indices_or_keys:
        if isinstance(item, int):
            resolved.append(all_accounts[item] if item < len(all_accounts) else str(item))
        else:
            resolved.append(str(item))
    return resolved


def _decode_sol_changes(meta: dict, all_accounts: list[str]) -> list[dict]:
    """Compute per-account SOL balance changes from pre/post balances."""
    pre = meta.get("preBalances") or []
    post = meta.get("postBalances") or []
    changes = []
    for i, (pre_bal, post_bal) in enumerate(zip(pre, post)):
        delta = post_bal - pre_bal
        changes.append({
            "account": all_accounts[i] if i < len(all_accounts) else str(i),
            "pre_lamports": pre_bal,
            "post_lamports": post_bal,
            "delta_lamports": delta,
            "delta_sol": delta / 1e9,
        })
    return changes


def _decode_token_changes(meta: dict) -> list[dict]:
    """Compute per-token-account balance changes from pre/post token balances."""
    pre_map: dict[str, dict] = {}
    for entry in (meta.get("preTokenBalances") or []):
        key = f"{entry.get('accountIndex')}:{entry.get('mint')}"
        pre_map[key] = entry

    changes = []
    for post in (meta.get("postTokenBalances") or []):
        idx = post.get("accountIndex")
        mint = post.get("mint", "")
        key = f"{idx}:{mint}"
        pre = pre_map.get(key, {})

        pre_ui = pre.get("uiTokenAmount", {})
        post_ui = post.get("uiTokenAmount", {})

        pre_amount = int(pre_ui.get("amount", 0) or 0)
        post_amount = int(post_ui.get("amount", 0) or 0)
        decimals = post_ui.get("decimals", 0)
        delta = post_amount - pre_amount

        changes.append({
            "account_index": idx,
            "owner": post.get("owner", ""),
            "mint": mint,
            "pre_amount": pre_amount,
            "post_amount": post_amount,
            "delta": delta,
            "decimals": decimals,
            "ui_pre": float(pre_ui.get("uiAmountString", 0) or 0),
            "ui_post": float(post_ui.get("uiAmountString", 0) or 0),
            "ui_delta": delta / (10 ** decimals) if decimals else delta,
        })

    # Also capture pre-balances that no longer appear in post (account closed)
    post_keys = {f"{p['accountIndex']}:{p['mint']}" for p in (meta.get("postTokenBalances") or [])}
    for key, pre in pre_map.items():
        if key not in post_keys:
            idx = pre.get("accountIndex")
            mint = pre.get("mint", "")
            pre_ui = pre.get("uiTokenAmount", {})
            pre_amount = int(pre_ui.get("amount", 0) or 0)
            decimals = pre_ui.get("decimals", 0)
            changes.append({
                "account_index": idx,
                "owner": pre.get("owner", ""),
                "mint": mint,
                "pre_amount": pre_amount,
                "post_amount": 0,
                "delta": -pre_amount,
                "decimals": decimals,
                "ui_pre": float(pre_ui.get("uiAmountString", 0) or 0),
                "ui_post": 0.0,
                "ui_delta": -pre_amount / (10 ** decimals) if decimals else -pre_amount,
            })

    return changes


def _extract_memo(instructions: list[dict]) -> Optional[str]:
    """Pull memo text from any Memo program instruction."""
    memo_programs = {
        "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
        "Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo",
    }
    for ix in instructions:
        if ix.get("program_id") in memo_programs:
            decoded = ix.get("decoded")
            if isinstance(decoded, dict):
                return decoded.get("info", {}).get("memo") or str(decoded)
            if isinstance(decoded, str):
                return decoded
            raw = ix.get("data_raw")
            if raw:
                try:
                    import base58
                    return base58.b58decode(raw).decode("utf-8", errors="replace")
                except Exception:
                    pass
    return None
