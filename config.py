"""
Configuration for Solana wallet transaction parser.
"""
import os

# ─── RPC Endpoints ────────────────────────────────────────────────────────────
# Public endpoints (rate-limited). For heavy usage get a private RPC key.
RPC_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-mainnet.g.alchemy.com/v2/demo",
    "https://rpc.ankr.com/solana",
]

# Primary RPC (override via env var SOLANA_RPC_URL)
RPC_URL: str = os.getenv("SOLANA_RPC_URL", RPC_ENDPOINTS[0])

# ─── Pagination ────────────────────────────────────────────────────────────────
# Max signatures per RPC call (Solana hard limit = 1000)
SIGNATURES_PER_PAGE: int = 1000

# Delay between RPC calls to avoid rate limits (seconds)
REQUEST_DELAY: float = float(os.getenv("REQUEST_DELAY", "0.3"))

# Max retries on RPC failure
MAX_RETRIES: int = 5

# Backoff multiplier (seconds) between retries
RETRY_BACKOFF: float = 2.0

# ─── Transaction fetching ──────────────────────────────────────────────────────
# How many transactions to fetch in parallel (thread pool size)
MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "5"))

# Batch size for getTransaction calls
TX_BATCH_SIZE: int = int(os.getenv("TX_BATCH_SIZE", "10"))

# ─── Output ───────────────────────────────────────────────────────────────────
OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "output")

# ─── Commitment level ─────────────────────────────────────────────────────────
COMMITMENT: str = "finalized"
