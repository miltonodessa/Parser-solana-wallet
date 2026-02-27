"""
Fetcher module: retrieves ALL signatures and full transactions from Solana RPC.

Key design decisions
────────────────────
• getSignaturesForAddress paginates via the `before` cursor (oldest-first or
  newest-first depending on scan direction).  The hard limit per call is 1000.
  We iterate until the RPC returns an empty page to collect every signature.
• getTransaction is called with encoding="jsonParsed" so that well-known
  programs (System, SPL Token, etc.) are decoded automatically by the node.
• A thread-pool is used for transaction fetching to speed things up while
  still respecting rate limits via a semaphore.
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore
from typing import Any, Generator, Optional

import requests

import config

logger = logging.getLogger(__name__)


# ─── Low-level RPC helper ──────────────────────────────────────────────────────

class RPCClient:
    """Thin JSON-RPC 2.0 wrapper around requests with retry logic."""

    def __init__(self, endpoint: str = config.RPC_URL) -> None:
        self.endpoint = endpoint
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def call(
        self,
        method: str,
        params: list[Any],
        retries: int = config.MAX_RETRIES,
    ) -> Any:
        """
        Execute a single JSON-RPC call.

        Raises:
            RuntimeError: if all retries are exhausted.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }
        backoff = config.RETRY_BACKOFF
        last_error: Optional[Exception] = None

        for attempt in range(1, retries + 1):
            try:
                resp = self.session.post(
                    self.endpoint,
                    data=json.dumps(payload),
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()

                if "error" in data and data["error"]:
                    err = data["error"]
                    # Rate-limit → back off and retry
                    if err.get("code") in (-32005, 429):
                        logger.warning("Rate limited (attempt %d/%d). Sleeping %.1fs", attempt, retries, backoff)
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                    raise RuntimeError(f"RPC error: {err}")

                return data.get("result")

            except (requests.RequestException, RuntimeError) as exc:
                last_error = exc
                if attempt < retries:
                    sleep_time = backoff * (2 ** (attempt - 1))
                    logger.warning(
                        "RPC call %s failed (attempt %d/%d): %s. Retrying in %.1fs",
                        method, attempt, retries, exc, sleep_time
                    )
                    time.sleep(sleep_time)

        raise RuntimeError(
            f"RPC {method} failed after {retries} retries: {last_error}"
        )


# ─── Signature Fetcher ─────────────────────────────────────────────────────────

class SignatureFetcher:
    """
    Fetches ALL transaction signatures for a Solana wallet address.

    Solana's getSignaturesForAddress returns signatures in reverse
    chronological order (newest first).  Pagination is done by passing
    the oldest signature from the previous page as the `before` cursor.
    """

    def __init__(self, rpc: RPCClient) -> None:
        self.rpc = rpc

    def fetch_all(
        self,
        address: str,
        before: Optional[str] = None,
        until: Optional[str] = None,
        commitment: str = config.COMMITMENT,
        on_page: Optional[callable] = None,
    ) -> list[dict]:
        """
        Retrieve every signature for *address*.

        Args:
            address:    Wallet public key.
            before:     Start pagination from this signature (exclusive).
                        Pass None to start from the most recent transaction.
            until:      Stop when this signature is reached (exclusive).
                        Useful for incremental updates.
            commitment: "finalized" | "confirmed" | "processed"
            on_page:    Optional callback(page_num, sigs_on_page) called after
                        each page is fetched – useful for progress reporting.

        Returns:
            List of signature-info dicts in reverse chronological order
            (newest → oldest).
        """
        all_sigs: list[dict] = []
        page = 0
        cursor = before

        logger.info("Fetching signatures for %s …", address)

        while True:
            opts: dict[str, Any] = {
                "limit": config.SIGNATURES_PER_PAGE,
                "commitment": commitment,
            }
            if cursor:
                opts["before"] = cursor
            if until:
                opts["until"] = until

            page_sigs: Optional[list[dict]] = self.rpc.call(
                "getSignaturesForAddress",
                [address, opts],
            )

            if not page_sigs:
                break  # No more signatures

            all_sigs.extend(page_sigs)
            page += 1
            logger.info(
                "  Page %d: %d signatures (total: %d)",
                page, len(page_sigs), len(all_sigs),
            )

            if on_page:
                on_page(page, page_sigs)

            # Rate-limit delay between pages
            time.sleep(config.REQUEST_DELAY)

            if len(page_sigs) < config.SIGNATURES_PER_PAGE:
                break  # Last page (partial)

            # Move cursor to the oldest signature on this page
            cursor = page_sigs[-1]["signature"]

        logger.info("Total signatures collected: %d", len(all_sigs))
        return all_sigs

    def fetch_page(
        self,
        address: str,
        limit: int = 100,
        before: Optional[str] = None,
        until: Optional[str] = None,
        commitment: str = config.COMMITMENT,
    ) -> list[dict]:
        """Fetch a single page of signatures (for incremental use)."""
        opts: dict[str, Any] = {"limit": min(limit, 1000), "commitment": commitment}
        if before:
            opts["before"] = before
        if until:
            opts["until"] = until
        return self.rpc.call("getSignaturesForAddress", [address, opts]) or []


# ─── Transaction Fetcher ───────────────────────────────────────────────────────

class TransactionFetcher:
    """
    Fetches full transaction details using getTransaction with jsonParsed
    encoding (for automatic instruction decoding by the RPC node).
    """

    def __init__(self, rpc: RPCClient) -> None:
        self.rpc = rpc
        self._semaphore = Semaphore(config.MAX_WORKERS)

    def fetch_one(
        self,
        signature: str,
        commitment: str = config.COMMITMENT,
        max_version: int = 0,
    ) -> Optional[dict]:
        """
        Fetch a single transaction with jsonParsed encoding.

        Returns None if the transaction is not found or was skipped.
        """
        with self._semaphore:
            result = self.rpc.call(
                "getTransaction",
                [
                    signature,
                    {
                        "encoding": "jsonParsed",
                        "commitment": commitment,
                        "maxSupportedTransactionVersion": max_version,
                    },
                ],
            )
            time.sleep(config.REQUEST_DELAY)
        return result

    def fetch_batch(
        self,
        signatures: list[str],
        commitment: str = config.COMMITMENT,
        max_version: int = 0,
        on_progress: Optional[callable] = None,
    ) -> Generator[tuple[str, Optional[dict]], None, None]:
        """
        Fetch multiple transactions in parallel.

        Yields:
            (signature, transaction_data) tuples (transaction_data may be None
            if the transaction was not found).
        """
        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as pool:
            futures = {
                pool.submit(self.fetch_one, sig, commitment, max_version): sig
                for sig in signatures
            }
            done = 0
            for future in as_completed(futures):
                sig = futures[future]
                done += 1
                try:
                    tx = future.result()
                except Exception as exc:
                    logger.error("Failed to fetch tx %s: %s", sig, exc)
                    tx = None

                if on_progress:
                    on_progress(done, len(signatures))

                yield sig, tx

    def fetch_batch_rpc(
        self,
        signatures: list[str],
        commitment: str = config.COMMITMENT,
        max_version: int = 0,
    ) -> list[Optional[dict]]:
        """
        Fetch multiple transactions using a single HTTP request
        with JSON-RPC batch (more efficient for ≤50 sigs).

        Returns list in the same order as *signatures*.
        """
        if not signatures:
            return []

        payload = [
            {
                "jsonrpc": "2.0",
                "id": i,
                "method": "getTransaction",
                "params": [
                    sig,
                    {
                        "encoding": "jsonParsed",
                        "commitment": commitment,
                        "maxSupportedTransactionVersion": max_version,
                    },
                ],
            }
            for i, sig in enumerate(signatures)
        ]

        session = requests.Session()
        session.headers["Content-Type"] = "application/json"

        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                resp = session.post(
                    self.rpc.endpoint,
                    data=json.dumps(payload),
                    timeout=60,
                )
                resp.raise_for_status()
                results_raw: list[dict] = resp.json()
                # Re-order by id
                id_to_result = {r["id"]: r.get("result") for r in results_raw}
                return [id_to_result.get(i) for i in range(len(signatures))]
            except Exception as exc:
                if attempt < config.MAX_RETRIES:
                    sleep_time = config.RETRY_BACKOFF * (2 ** (attempt - 1))
                    logger.warning("Batch fetch failed (attempt %d): %s. Retry in %.1fs", attempt, exc, sleep_time)
                    time.sleep(sleep_time)

        # Fallback: fetch individually
        logger.warning("Batch RPC failed; falling back to individual fetches")
        return [self.fetch_one(sig, commitment, max_version) for sig in signatures]


def create_rpc_client(endpoint: Optional[str] = None) -> RPCClient:
    """Factory that returns an RPCClient, optionally with a custom endpoint."""
    return RPCClient(endpoint or config.RPC_URL)
