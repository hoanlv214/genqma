"""Payment request schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.query import QueryModel


class InvoiceRequest(QueryModel):
    provider_id: str = Field(default="funding_memory", max_length=64, examples=["funding_memory"])
    tier: str = Field(default="full", pattern="^(preview|full)$", examples=["preview"])
    resource_type: str = Field(default="qma_signal_report", max_length=64, examples=["qma_signal_report"])
    buyer_type: str = Field(default="human", pattern="^(human|agent)$", examples=["agent"])
    buyer_wallet_address: Optional[str] = Field(
        default=None, min_length=8, max_length=80, examples=["0x742d35Cc6634C0532925a3b844Bc454e4438f44e"]
    )
    synthetic: bool = Field(default=False, examples=[False])
    agent_label: Optional[str] = Field(default=None, max_length=120, examples=["autonomous-session"])
    run_source: Optional[str] = Field(default=None, max_length=120, examples=["cli-agent"])


class QuoteRequest(QueryModel):
    provider_id: str = Field(default="funding_memory", max_length=64, examples=["oi_memory"])
    tier: str = Field(default="full", pattern="^(preview|full)$", examples=["preview"])


class SplitSettlementProof(BaseModel):
    leg_id: str = Field(..., min_length=2, max_length=32, examples=["creator"])
    settlement_id: str = Field(..., min_length=8, examples=["settlement_01JQMA7Y8A"])
    pay_to: str = Field(..., min_length=8, max_length=80, examples=["0xb40971a5d88f31c7b8d88bf93f7d044f1383bf01"])
    amount_raw: str = Field(..., min_length=1, max_length=80, examples=["800"])
    sidecar_receipt: str = Field(..., min_length=20, max_length=300, examples=["receipt_01JQMA7Y8A_creator_abc123"])
    payer_address: Optional[str] = Field(
        default=None, min_length=8, max_length=80, examples=["0x4dbc321e301c82b8f8e6a5193e47c6eca656d514"]
    )
    gateway_status: Optional[str] = Field(default=None, min_length=1, max_length=40, examples=["completed"])


class PaymentVerifyRequest(BaseModel):
    settlement_id: Optional[str] = Field(default=None, min_length=8, examples=["settlement_01JQMA7Y8A"])
    invoice_secret: str = Field(..., min_length=16, examples=["inv_secret_7f4d9a8c2b1e"])
    payer_address: Optional[str] = Field(default=None, examples=["0x4dbc321e301c82b8f8e6a5193e47c6eca656d514"])
    amount_usdc: Optional[float] = Field(default=None, examples=[0.001157])
    split_settlements: List[SplitSettlementProof] = Field(
        default_factory=list,
        examples=[
            [
                {
                    "leg_id": "creator",
                    "settlement_id": "settlement_01JQMA7Y8A",
                    "pay_to": "0xb40971a5d88f31c7b8d88bf93f7d044f1383bf01",
                    "amount_raw": "800",
                    "sidecar_receipt": "receipt_01JQMA7Y8A_creator_abc123",
                    "payer_address": "0x4dbc321e301c82b8f8e6a5193e47c6eca656d514",
                    "gateway_status": "completed",
                }
            ]
        ],
    )


class WithdrawRequest(BaseModel):
    """Signed Gateway burn intent submitted for creator withdrawal."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    burn_intent: Optional[Dict[str, Any]] = Field(
        default=None,
        alias="burnIntent",
        examples=[
            {
                "spec": {
                    "sourceDomain": 26,
                    "destinationDomain": 26,
                    "sourceContract": "0x0077777d7EBA4688BDeF3E311b846F25870A19B9",
                    "destinationContract": "0x0022222ABE238Cc2C7Bb1f21003F0a260052475B",
                    "sourceToken": "0x3600000000000000000000000000000000000000",
                    "destinationToken": "0x3600000000000000000000000000000000000000",
                    "sourceDepositor": "0x4dbc321e301c82b8f8e6a5193e47c6eca656d514",
                    "destinationRecipient": "0x4dbc321e301c82b8f8e6a5193e47c6eca656d514",
                    "sourceSigner": "0x4dbc321e301c82b8f8e6a5193e47c6eca656d514",
                    "destinationCaller": "0x0000000000000000000000000000000000000000",
                    "value": "1000000",
                }
            }
        ],
    )
    signature: Optional[str] = Field(default=None, examples=["0x" + "ab" * 65])
