"""
System Program instruction decoder.
Program ID: 11111111111111111111111111111111
"""
from __future__ import annotations
import struct
from typing import Any


# Instruction type indices
_SYSTEM_IX = {
    0: "CreateAccount",
    1: "Assign",
    2: "Transfer",
    3: "CreateAccountWithSeed",
    4: "AdvanceNonceAccount",
    5: "WithdrawNonceAccount",
    6: "InitializeNonceAccount",
    7: "AuthorizeNonceAccount",
    8: "Allocate",
    9: "AllocateWithSeed",
    10: "AssignWithSeed",
    11: "TransferWithSeed",
    12: "UpgradeNonceAccount",
}


def decode_system_instruction(data_b58: str, accounts: list[str]) -> dict[str, Any]:
    """
    Decode a raw System Program instruction.

    Args:
        data_b58: Base-58 encoded instruction data.
        accounts:  List of account public keys in instruction order.

    Returns:
        Dict with 'type' and decoded 'params'.
    """
    try:
        import base58
        raw = base58.b58decode(data_b58)
    except Exception:
        return {"type": "Unknown", "raw_data": data_b58}

    if len(raw) < 4:
        return {"type": "Unknown", "raw_data": data_b58}

    ix_type = struct.unpack_from("<I", raw, 0)[0]
    name = _SYSTEM_IX.get(ix_type, f"Unknown({ix_type})")

    params: dict[str, Any] = {"instruction_type_id": ix_type}

    try:
        if ix_type == 0:  # CreateAccount
            lamports = struct.unpack_from("<Q", raw, 4)[0]
            space = struct.unpack_from("<Q", raw, 12)[0]
            params.update({
                "funding_account": accounts[0] if len(accounts) > 0 else None,
                "new_account": accounts[1] if len(accounts) > 1 else None,
                "lamports": lamports,
                "sol": lamports / 1e9,
                "space_bytes": space,
            })
        elif ix_type == 2:  # Transfer
            lamports = struct.unpack_from("<Q", raw, 4)[0]
            params.update({
                "from": accounts[0] if len(accounts) > 0 else None,
                "to": accounts[1] if len(accounts) > 1 else None,
                "lamports": lamports,
                "sol": lamports / 1e9,
            })
        elif ix_type == 1:  # Assign
            params.update({
                "account": accounts[0] if accounts else None,
                "owner": raw[4:36].hex() if len(raw) >= 36 else None,
            })
        elif ix_type == 11:  # TransferWithSeed
            lamports = struct.unpack_from("<Q", raw, 4)[0]
            params.update({
                "from": accounts[0] if len(accounts) > 0 else None,
                "base": accounts[1] if len(accounts) > 1 else None,
                "to": accounts[2] if len(accounts) > 2 else None,
                "lamports": lamports,
                "sol": lamports / 1e9,
            })
    except struct.error:
        pass

    return {"type": name, "params": params}
