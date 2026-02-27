"""
Known Solana program IDs with human-readable names and categories.
"""

KNOWN_PROGRAMS: dict[str, dict] = {
    # ── Core ──────────────────────────────────────────────────────────────────
    "11111111111111111111111111111111": {
        "name": "System Program",
        "category": "core",
        "url": "https://docs.solana.com/developing/runtime-facilities/programs#system-program",
    },
    "ComputeBudget111111111111111111111111111111": {
        "name": "Compute Budget",
        "category": "core",
    },
    "Config1111111111111111111111111111111111111": {
        "name": "Config Program",
        "category": "core",
    },
    "Stake11111111111111111111111111111111111111": {
        "name": "Stake Program",
        "category": "core",
    },
    "Vote111111111111111111111111111111111111111": {
        "name": "Vote Program",
        "category": "core",
    },
    "BPFLoaderUpgradeab1e11111111111111111111111": {
        "name": "BPF Upgradeable Loader",
        "category": "core",
    },
    "BPFLoader2111111111111111111111111111111111": {
        "name": "BPF Loader v2",
        "category": "core",
    },
    "AddressLookupTab1e1111111111111111111111111": {
        "name": "Address Lookup Table",
        "category": "core",
    },

    # ── SPL Token ─────────────────────────────────────────────────────────────
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": {
        "name": "SPL Token",
        "category": "token",
    },
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb": {
        "name": "Token-2022",
        "category": "token",
    },
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJe1bFo": {
        "name": "Associated Token Account",
        "category": "token",
    },
    "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s": {
        "name": "Metaplex Token Metadata",
        "category": "nft",
    },
    "cndy3Z4yapfJBmL3ShUp5exZKqR3z33thTzeNMm2gRZ": {
        "name": "Metaplex Candy Machine v2",
        "category": "nft",
    },
    "CndyV3LdqHUfDLmd1quitcKTdwBpBDVMPRBboOaUAuaU": {
        "name": "Metaplex Candy Machine v3",
        "category": "nft",
    },
    "p1exdMJcjVao65QdewkaZRUnU6VPSXhus9n2GzWfh98": {
        "name": "Metaplex Auction House",
        "category": "nft",
    },
    "M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K": {
        "name": "Magic Eden v2",
        "category": "nft",
    },

    # ── DEX / AMM ─────────────────────────────────────────────────────────────
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": {
        "name": "Jupiter v6",
        "category": "dex",
    },
    "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB": {
        "name": "Jupiter v4",
        "category": "dex",
    },
    "JUP3c2Uh3WA4Ng34tw6kPd2G4LFxStaouCJGpfhrkEo": {
        "name": "Jupiter v3",
        "category": "dex",
    },
    "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP": {
        "name": "Orca Whirlpool",
        "category": "dex",
    },
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": {
        "name": "Orca Whirlpools",
        "category": "dex",
    },
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": {
        "name": "Raydium AMM v4",
        "category": "dex",
    },
    "5quBtoiQqxF9Jv6KYKctB59NT3gtJD2Y65kdnB1Uev3h": {
        "name": "Raydium AMM v3",
        "category": "dex",
    },
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": {
        "name": "Raydium CLMM",
        "category": "dex",
    },
    "RVKd61ztZW9GUwhRbbLoYVRE5Xf1B2tVscKqwZqXgEr": {
        "name": "Raydium v3 (CPMM)",
        "category": "dex",
    },
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": {
        "name": "Raydium CPMM",
        "category": "dex",
    },
    "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX": {
        "name": "Serum DEX v3",
        "category": "dex",
    },
    "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin": {
        "name": "Serum DEX v3 (old)",
        "category": "dex",
    },
    "MERLuDFBMmsHnsBPZw2sDQZHvXFMwp8EdjudcU2HKky": {
        "name": "Mercurial Finance",
        "category": "dex",
    },
    "SSwpkEEcbUqx4vtoEByFjSkhKdCT862DNVb52nZg1UZ": {
        "name": "Saber Swap",
        "category": "dex",
    },
    "DjVE6JNiYqPL2QXyCUUh8rNjHrbz9hXHNYt99MQ59qw1": {
        "name": "Orca v1",
        "category": "dex",
    },

    # ── Lending ───────────────────────────────────────────────────────────────
    "So1endDq2YkqhipRh3WViPa8hdiSpxWy6z3Z6tMCpAo": {
        "name": "Solend",
        "category": "lending",
    },
    "MarBmsSgKXdrN1egZf5sqe1TMai9K1rChYNDJgjq7aD": {
        "name": "Marinade Finance",
        "category": "liquid_staking",
    },
    "SPoo1Ku8WFXoNDMHPsrGSTx1A7v4eiKz8Z5JbMQoXay": {
        "name": "Stake Pool",
        "category": "liquid_staking",
    },

    # ── Other ─────────────────────────────────────────────────────────────────
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr": {
        "name": "Memo Program v2",
        "category": "memo",
    },
    "Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo": {
        "name": "Memo Program v1",
        "category": "memo",
    },
    "namesLPneVptA9Z5rqUDD9tMTWEJwofgaYwp8cawRkX": {
        "name": "Solana Name Service",
        "category": "naming",
    },
    "SW1TCH7qEPTdLsDHRgPuMQjbQxKdH2aBStViMFnt64f": {
        "name": "Switchboard Oracle",
        "category": "oracle",
    },
    "GDDMwNyyx8uB6zrqwBFHjLLG3TkTCibyLSJkgqe5Djn": {
        "name": "Pyth Oracle",
        "category": "oracle",
    },
}


def get_program_name(program_id: str) -> str:
    """Return human-readable program name or the program ID if unknown."""
    info = KNOWN_PROGRAMS.get(program_id)
    return info["name"] if info else program_id


def get_program_category(program_id: str) -> str:
    """Return program category or 'unknown'."""
    info = KNOWN_PROGRAMS.get(program_id)
    return info.get("category", "unknown") if info else "unknown"
