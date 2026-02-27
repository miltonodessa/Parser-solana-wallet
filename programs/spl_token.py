"""
SPL Token Program instruction decoder.
Program IDs:
  TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA  (Token v1)
  TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb  (Token-2022)
"""
from __future__ import annotations
import struct
from typing import Any


_TOKEN_IX = {
    0: "InitializeMint",
    1: "InitializeAccount",
    2: "InitializeMultisig",
    3: "Transfer",
    4: "Approve",
    5: "Revoke",
    6: "SetAuthority",
    7: "MintTo",
    8: "Burn",
    9: "CloseAccount",
    10: "FreezeAccount",
    11: "ThawAccount",
    12: "TransferChecked",
    13: "ApproveChecked",
    14: "MintToChecked",
    15: "BurnChecked",
    16: "InitializeAccount2",
    17: "SyncNative",
    18: "InitializeAccount3",
    19: "InitializeMultisig2",
    20: "InitializeMint2",
    21: "GetAccountDataSize",
    22: "InitializeImmutableOwner",
    23: "AmountToUiAmount",
    24: "UiAmountToAmount",
    25: "InitializeMintCloseAuthority",
    26: "TransferFeeExtension",
    27: "ConfidentialTransferExtension",
    28: "DefaultAccountStateExtension",
    29: "Reallocate",
    30: "MemoTransfer",
    31: "CreateNativeMint",
    32: "InitializeNonTransferableMint",
    33: "InterestBearingMintExtension",
    34: "CpiGuardExtension",
    35: "InitializePermanentDelegate",
    36: "TransferHookExtension",
    37: "ConfidentialTransferFeeExtension",
    38: "WithdrawExcessLamports",
    39: "MetadataPointerExtension",
    40: "GroupPointerExtension",
    41: "GroupMemberPointerExtension",
    42: "TokenMetadataExtension",
    43: "TokenGroupExtension",
}


def decode_token_instruction(data_b58: str, accounts: list[str]) -> dict[str, Any]:
    """
    Decode a raw SPL Token / Token-2022 instruction.

    Args:
        data_b58: Base-58 encoded instruction data.
        accounts:  Ordered list of account public keys.

    Returns:
        Dict with 'type' and decoded 'params'.
    """
    try:
        import base58
        raw = base58.b58decode(data_b58)
    except Exception:
        return {"type": "Unknown", "raw_data": data_b58}

    if not raw:
        return {"type": "Unknown", "raw_data": data_b58}

    ix_type = raw[0]
    name = _TOKEN_IX.get(ix_type, f"Unknown({ix_type})")
    params: dict[str, Any] = {"instruction_type_id": ix_type}

    try:
        if ix_type == 3:  # Transfer
            amount = struct.unpack_from("<Q", raw, 1)[0]
            params.update({
                "source": accounts[0] if len(accounts) > 0 else None,
                "destination": accounts[1] if len(accounts) > 1 else None,
                "authority": accounts[2] if len(accounts) > 2 else None,
                "amount": amount,
            })
        elif ix_type == 12:  # TransferChecked
            amount = struct.unpack_from("<Q", raw, 1)[0]
            decimals = raw[9] if len(raw) > 9 else None
            params.update({
                "source": accounts[0] if len(accounts) > 0 else None,
                "mint": accounts[1] if len(accounts) > 1 else None,
                "destination": accounts[2] if len(accounts) > 2 else None,
                "authority": accounts[3] if len(accounts) > 3 else None,
                "amount": amount,
                "decimals": decimals,
                "ui_amount": amount / (10 ** decimals) if decimals is not None else None,
            })
        elif ix_type == 7:  # MintTo
            amount = struct.unpack_from("<Q", raw, 1)[0]
            params.update({
                "mint": accounts[0] if len(accounts) > 0 else None,
                "destination": accounts[1] if len(accounts) > 1 else None,
                "authority": accounts[2] if len(accounts) > 2 else None,
                "amount": amount,
            })
        elif ix_type == 14:  # MintToChecked
            amount = struct.unpack_from("<Q", raw, 1)[0]
            decimals = raw[9] if len(raw) > 9 else None
            params.update({
                "mint": accounts[0] if len(accounts) > 0 else None,
                "destination": accounts[1] if len(accounts) > 1 else None,
                "authority": accounts[2] if len(accounts) > 2 else None,
                "amount": amount,
                "decimals": decimals,
            })
        elif ix_type == 8:  # Burn
            amount = struct.unpack_from("<Q", raw, 1)[0]
            params.update({
                "source": accounts[0] if len(accounts) > 0 else None,
                "mint": accounts[1] if len(accounts) > 1 else None,
                "authority": accounts[2] if len(accounts) > 2 else None,
                "amount": amount,
            })
        elif ix_type == 15:  # BurnChecked
            amount = struct.unpack_from("<Q", raw, 1)[0]
            decimals = raw[9] if len(raw) > 9 else None
            params.update({
                "source": accounts[0] if len(accounts) > 0 else None,
                "mint": accounts[1] if len(accounts) > 1 else None,
                "authority": accounts[2] if len(accounts) > 2 else None,
                "amount": amount,
                "decimals": decimals,
            })
        elif ix_type == 9:  # CloseAccount
            params.update({
                "account": accounts[0] if len(accounts) > 0 else None,
                "destination": accounts[1] if len(accounts) > 1 else None,
                "authority": accounts[2] if len(accounts) > 2 else None,
            })
        elif ix_type in (0, 20):  # InitializeMint / InitializeMint2
            decimals = raw[1] if len(raw) > 1 else None
            params.update({
                "mint": accounts[0] if accounts else None,
                "decimals": decimals,
            })
        elif ix_type in (1, 16, 18):  # InitializeAccount variants
            params.update({
                "account": accounts[0] if len(accounts) > 0 else None,
                "mint": accounts[1] if len(accounts) > 1 else None,
                "owner": accounts[2] if len(accounts) > 2 else None,
            })
        elif ix_type == 4:  # Approve
            amount = struct.unpack_from("<Q", raw, 1)[0]
            params.update({
                "source": accounts[0] if len(accounts) > 0 else None,
                "delegate": accounts[1] if len(accounts) > 1 else None,
                "owner": accounts[2] if len(accounts) > 2 else None,
                "amount": amount,
            })
        elif ix_type == 5:  # Revoke
            params.update({
                "source": accounts[0] if len(accounts) > 0 else None,
                "owner": accounts[1] if len(accounts) > 1 else None,
            })
    except (struct.error, IndexError):
        pass

    return {"type": name, "params": params}
