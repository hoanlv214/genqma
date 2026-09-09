"""Low-level wallet/address utilities."""

from typing import Optional

from fastapi import HTTPException

import paid_intelligence_kit as paid_kit


def normalize_address(value: Optional[str]) -> str:
    return paid_kit.normalize_address(value)


def bytes32_to_address(value: Optional[str]) -> str:
    raw = str(value or "").strip().lower()
    if not raw.startswith("0x") or len(raw) != 66:
        raise HTTPException(status_code=400, detail="Malformed bytes32 address in withdraw intent")
    try:
        int(raw[2:], 16)
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed bytes32 address in withdraw intent")
    return "0x" + raw[-40:]


def address_to_bytes32(address: str) -> str:
    return "0x" + normalize_address(address).replace("0x", "").rjust(64, "0")


def same_address(left: Optional[str], right: Optional[str]) -> bool:
    return normalize_address(left) == normalize_address(right)
