"""Request schemas for internal gateway coordination endpoints."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RecordInternalSplitLegRequest(BaseModel):
    """Gateway receipt fields used to mark one invoice leg as settled."""

    model_config = ConfigDict(extra="allow")

    amount_raw: Optional[str] = Field(default=None, examples=["800"])
    settled_amount_raw: Optional[str] = Field(default=None, examples=["800"])
    pay_to: Optional[str] = Field(default=None, examples=["0xb40971a5d88f31c7b8d88bf93f7d044f1383bf01"])
    settlement_id: Optional[str] = Field(default=None, examples=["settlement_01JQMA7Y8A"])
    sidecar_receipt: Optional[str] = Field(default=None, examples=["receipt_01JQMA7Y8A_creator_abc123"])
    payer_address: Optional[str] = Field(default=None, examples=["0x4dbc321e301c82b8f8e6a5193e47c6eca656d514"])
    buyer_wallet_address: Optional[str] = Field(default=None, examples=["0x4dbc321e301c82b8f8e6a5193e47c6eca656d514"])
    gateway_status: Optional[str] = Field(default=None, examples=["completed"])
    transaction_hash: Optional[str] = Field(default=None, examples=["0x" + "cd" * 32])
    explorer_url: Optional[str] = Field(default=None, examples=["https://testnet.arcscan.app/tx/0x" + "cd" * 32])
