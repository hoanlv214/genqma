"""Wallet profile request schemas."""

from pydantic import BaseModel, Field


class WalletProfileSessionRequest(BaseModel):
    nonce: str = Field(..., min_length=8, max_length=120, examples=["profile_nonce_01JQMA7Y8A"])
    issued_at: int = Field(..., gt=0, examples=[1784371200])
    signature: str = Field(..., min_length=20, max_length=300, examples=["0x" + "ef" * 65])
