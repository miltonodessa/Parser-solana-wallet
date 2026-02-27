#!/usr/bin/env python3
"""
Solana Wallet Transaction Parser
═════════════════════════════════
Fetches ALL transactions for a Solana wallet address (no 1000-tx limit),
decodes instruction data using jsonParsed RPC encoding + custom decoders,
and exports the results to JSON, CSV and (optionally) XLSX.

Usage examples
──────────────
# Basic – export everything for a wallet
python main.py <WALLET_ADDRESS>

# Custom RPC endpoint + output directory
python main.py <WALLET> --rpc https://my-rpc.com --output ./results

# Only last N transactions
python main.py <WALLET> --limit 500

# Resume from a known signature (skip newer ones)
python main.py <WALLET> --before <SIGNATURE>

# Stop at a known signature (skip older ones)
python main.py <WALLET> --until <SIGNATURE>

# Skip XLSX (faster if openpyxl not installed)
python main.py <WALLET> --no-xlsx

# Verbose logging
python main.py <WALLET> -v
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

# ── Path setup ─────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

import config
from parser.fetcher import RPCClient, SignatureFetcher, TransactionFetcher
from parser.decoder import TransactionDecoder
from parser.analyzer import WalletAnalyzer
from parser.exporter import DataExporter


# ── Logging ────────────────────────────────────────────────────────────────────

def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )


# ── Progress helper ─────────────────────────────────────────────────────────────

class Progress:
    def __init__(self, total: int, label: str = "transactions") -> None:
        self.total = total
        self.done = 0
        self.label = label
        self.start = time.time()

    def update(self, done: int, total: Optional[int] = None) -> None:
        if total is not None:
            self.total = total
        self.done = done
        pct = 100 * done / self.total if self.total else 0
        elapsed = time.time() - self.start
        eta = (elapsed / done * (self.total - done)) if done else 0
        bar = "#" * int(pct / 2) + "-" * (50 - int(pct / 2))
        print(
            f"\r  [{bar}] {pct:5.1f}%  {done}/{self.total} {self.label}"
            f"  elapsed {elapsed:.0f}s  ETA {eta:.0f}s   ",
            end="",
            flush=True,
        )
        if done >= self.total:
            print()


# ── Main pipeline ───────────────────────────────────────────────────────────────

def run(
    wallet: str,
    rpc_url: str = config.RPC_URL,
    output_dir: str = config.OUTPUT_DIR,
    limit: Optional[int] = None,
    before: Optional[str] = None,
    until: Optional[str] = None,
    skip_xlsx: bool = False,
    commitment: str = config.COMMITMENT,
    verbose: bool = False,
) -> None:
    logger = logging.getLogger(__name__)

    print(f"\n{'═'*60}")
    print(f"  Solana Wallet Transaction Parser")
    print(f"{'═'*60}")
    print(f"  Wallet  : {wallet}")
    print(f"  RPC     : {rpc_url}")
    print(f"  Output  : {output_dir}")
    if limit:
        print(f"  Limit   : {limit:,} transactions")
    if before:
        print(f"  Before  : {before[:20]}…")
    if until:
        print(f"  Until   : {until[:20]}…")
    print(f"{'─'*60}\n")

    # ── 1. Fetch signatures ────────────────────────────────────────────────────
    rpc = RPCClient(rpc_url)
    sig_fetcher = SignatureFetcher(rpc)

    print("Step 1/4: Fetching signatures …")
    sig_infos = sig_fetcher.fetch_all(
        wallet,
        before=before,
        until=until,
        commitment=commitment,
    )

    if limit:
        sig_infos = sig_infos[:limit]

    total = len(sig_infos)
    print(f"  → {total:,} signatures collected\n")

    if total == 0:
        print("No transactions found. Exiting.")
        return

    # ── 2. Fetch full transaction data ────────────────────────────────────────
    print("Step 2/4: Fetching full transaction data …")
    tx_fetcher = TransactionFetcher(rpc)
    decoder = TransactionDecoder()

    progress = Progress(total, "transactions")
    records: list[dict] = []

    # Build a lookup from signature → sig_info for O(1) access
    sig_info_map = {s["signature"]: s for s in sig_infos}
    signatures = [s["signature"] for s in sig_infos]

    # Fetch in batches via thread pool
    batch_size = config.TX_BATCH_SIZE
    done_count = 0

    for batch_start in range(0, total, batch_size):
        batch_sigs = signatures[batch_start: batch_start + batch_size]

        for sig, tx_data in tx_fetcher.fetch_batch(
            batch_sigs,
            commitment=commitment,
            on_progress=None,
        ):
            sig_info = sig_info_map.get(sig, {"signature": sig})
            record = decoder.decode(sig_info, tx_data, wallet_address=wallet)
            records.append(record)
            done_count += 1
            progress.update(done_count, total)

    print(f"  → {len(records):,} transactions decoded\n")

    # ── 3. Analyse ─────────────────────────────────────────────────────────────
    print("Step 3/4: Running analysis …")
    analyzer = WalletAnalyzer(wallet)
    analysis = analyzer.analyze(records)

    summary = analysis["summary"]
    print(f"  Success rate  : {summary['successful_transactions']}/{summary['total_transactions']}")
    print(f"  Total fees    : {summary['total_fees_sol']:.6f} SOL")
    print(f"  Net SOL flow  : {summary['net_sol_change']:+.6f} SOL")
    print(f"  Unique mints  : {summary['unique_token_mints']:,}")
    print(f"  SOL transfers : {len(analysis['sol_transfers']):,}")
    print(f"  Token transfers: {len(analysis['token_transfers']):,}")
    print(f"  Swaps detected: {len(analysis['swaps']):,}")
    print(f"  NFT events    : {len(analysis['nft_events']):,}\n")

    # ── 4. Export ──────────────────────────────────────────────────────────────
    print("Step 4/4: Exporting data …")
    exporter = DataExporter(output_dir)

    # JSON exports
    tx_json = exporter.transactions_to_json(records, wallet)
    analysis_json = exporter.analysis_to_json(analysis, wallet)

    # CSV exports
    tx_csv = exporter.transactions_to_csv(records, wallet)
    sol_csv = exporter.sol_transfers_to_csv(analysis["sol_transfers"], wallet)
    tok_csv = exporter.token_transfers_to_csv(analysis["token_transfers"], wallet)
    swap_csv = exporter.swaps_to_csv(analysis["swaps"], wallet)

    # Optional XLSX
    xlsx_path = None
    if not skip_xlsx:
        xlsx_path = exporter.to_xlsx(records, analysis, wallet)

    print(f"\n{'═'*60}")
    print("  Export summary")
    print(f"{'─'*60}")
    print(f"  {tx_json}")
    print(f"  {analysis_json}")
    print(f"  {tx_csv}")
    print(f"  {sol_csv}")
    print(f"  {tok_csv}")
    print(f"  {swap_csv}")
    if xlsx_path:
        print(f"  {xlsx_path}")
    print(f"{'═'*60}\n")
    print("Done! ✓")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch and decode ALL transactions for a Solana wallet address.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("wallet", help="Solana wallet public key (base-58)")
    p.add_argument(
        "--rpc",
        default=os.getenv("SOLANA_RPC_URL", config.RPC_URL),
        metavar="URL",
        help=f"RPC endpoint URL (default: {config.RPC_URL})",
    )
    p.add_argument(
        "--output", "-o",
        default=config.OUTPUT_DIR,
        metavar="DIR",
        help=f"Output directory (default: {config.OUTPUT_DIR})",
    )
    p.add_argument(
        "--limit", "-n",
        type=int,
        default=None,
        metavar="N",
        help="Maximum number of transactions to fetch (default: all)",
    )
    p.add_argument(
        "--before",
        default=None,
        metavar="SIG",
        help="Start pagination before this signature (newest first)",
    )
    p.add_argument(
        "--until",
        default=None,
        metavar="SIG",
        help="Stop pagination at this signature (exclusive)",
    )
    p.add_argument(
        "--commitment",
        default=config.COMMITMENT,
        choices=["finalized", "confirmed", "processed"],
        help=f"Commitment level (default: {config.COMMITMENT})",
    )
    p.add_argument(
        "--no-xlsx",
        action="store_true",
        help="Skip XLSX export (faster; useful if openpyxl is not installed)",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=config.REQUEST_DELAY,
        metavar="SECS",
        help=f"Delay between RPC calls in seconds (default: {config.REQUEST_DELAY})",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=config.MAX_WORKERS,
        metavar="N",
        help=f"Parallel worker threads for tx fetching (default: {config.MAX_WORKERS})",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    _setup_logging(args.verbose)

    # Override config from CLI args
    config.REQUEST_DELAY = args.delay
    config.MAX_WORKERS = args.workers

    run(
        wallet=args.wallet,
        rpc_url=args.rpc,
        output_dir=args.output,
        limit=args.limit,
        before=args.before,
        until=args.until,
        skip_xlsx=args.no_xlsx,
        commitment=args.commitment,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
