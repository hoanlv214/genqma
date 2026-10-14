"""Response/request schemas for the headless swap router API.

Every field carries a description — the OpenAPI documentation gate
(tests/api_v1/test_api_openapi_docs.py) requires operation descriptions and
typed responses; these models feed that surface.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SwapTokenEntry(BaseModel):
    symbol: str = Field(..., description="Token symbol (USDC, EURC, USYC, WETH).")
    address: str = Field(..., description="Arc testnet contract address.")
    decimals: int = Field(..., description="ERC-20 decimals for raw unit conversion.")


class SwapVenueEntry(BaseModel):
    venue_id: str = Field(..., description="Stable venue identifier used in quotes and execution requests.")
    name: str = Field(..., description="Human-readable venue name.")
    kind: str = Field(..., description="Venue type: constant_product, stableswap, erc4626_redemption, relayer_desk.")


class SwapNetworkInfo(BaseModel):
    chain_id: int = Field(..., description="Arc chain ID (5042002 testnet).")
    name: str = Field(..., description="Network display name.")
    payment_network: str = Field(..., description="CAIP-2 payment network identifier.")


class SwapPairsResponse(BaseModel):
    tokens: List[SwapTokenEntry] = Field(..., description="Tokens the router can quote.")
    venues: List[SwapVenueEntry] = Field(..., description="Venues the router aggregates.")
    network: SwapNetworkInfo = Field(..., description="Arc network this router serves.")


class SwapVenueQuote(BaseModel):
    venue_id: str = Field(..., description="Venue identifier.")
    venue: str = Field(..., description="Human-readable venue name.")
    kind: str = Field(..., description="Venue type.")
    available: bool = Field(..., description="Whether this venue returned a usable non-zero quote.")
    amount_out: Optional[float] = Field(None, description="Quoted output amount in human units.")
    amount_out_raw: Optional[int] = Field(None, description="Quoted output in raw token units.")
    anchor_divergence_bps: Optional[float] = Field(
        None, description="Percent deviation of this quote from the oracle anchor, in basis points."
    )
    gas_units_estimate: int = Field(..., description="Rough gas units the venue's swap consumes (Arc needs explicit gas).")
    path: Optional[List[str]] = Field(None, description="Token contract path used by the venue call.")
    note: str = Field("", description="Implementation detail or unavailability reason.")
    rate_source: Optional[str] = Field(None, description="Oracle source when the venue is oracle-priced (e.g. StableFX desk).")


class SwapBestRoute(BaseModel):
    venue_id: str = Field(..., description="Winning venue identifier.")
    venue: str = Field(..., description="Winning venue name.")
    amount_out: float = Field(..., description="Best quoted output in human units.")
    amount_out_raw: int = Field(..., description="Best quoted output in raw units.")
    min_out_raw: int = Field(
        ..., description="Minimum acceptable output (slippage-protected) that execution must enforce."
    )
    anchor_divergence_bps: Optional[float] = Field(None, description="Best quote's deviation from the oracle anchor in bps.")
    anchor_exceeded: bool = Field(
        ..., description="True when |divergence| exceeds QMA_SWAP_MAX_ANCHOR_DIVERSION_BPS — execution should refuse."
    )
    path: List[str] = Field(..., description="On-chain token path of the winning route.")
    gas_units_estimate: int = Field(..., description="Estimated gas units for the winning swap.")


class SwapAnchorInfo(BaseModel):
    rate: float = Field(..., description="Oracle rate expressed as output-per-input.")
    source: str = Field(..., description="Oracle provenance (e.g. PYTH_EURUSD_24_7_INDEX).")
    expected_out: float = Field(..., description="Oracle-expected output for the quoted amount.")
    max_divergence_bps: int = Field(..., description="Configured divergence tolerance in basis points.")


class SwapQuoteResponse(BaseModel):
    available: bool = Field(..., description="False when no venue quoted a usable route.")
    from_token: str = Field(..., description="Input token symbol.")
    to_token: str = Field(..., description="Output token symbol.")
    amount_in: float = Field(..., description="Input amount in human units.")
    amount_in_raw: int = Field(..., description="Input amount in raw token units.")
    slippage_bps: int = Field(..., description="Slippage tolerance applied to derive min_out.")
    anchor: Optional[SwapAnchorInfo] = Field(None, description="Oracle anchor for the pair, when one exists.")
    quotes: List[SwapVenueQuote] = Field(..., description="Every venue's outcome, including unavailable ones with reasons.")
    best: Optional[SwapBestRoute] = Field(None, description="Winning route when available is true.")
    quote_id: Optional[str] = Field(None, description="Quote identifier required by the execution endpoint.")
    expires_at: Optional[int] = Field(None, description="Unix epoch after which the quote can no longer be executed.")
    ttl_seconds: int = Field(..., description="Quote time-to-live in seconds.")
    reason: Optional[str] = Field(None, description="Why no route was available (set when available is false).")
    network: SwapNetworkInfo = Field(..., description="Arc network this quote was computed on.")
    quoted_at: int = Field(..., description="Unix epoch when the quote was computed.")


class SwapExecuteRequest(BaseModel):
    quote_id: str = Field(..., description="Quote identifier returned by GET /api/v1/swap/quote.")
    executor_address: Optional[str] = Field(
        None, description="Relayer/owner wallet executing the swap; defaults to the configured relayer EOA."
    )
    idempotency_key: Optional[str] = Field(
        None, description="Optional client idempotency key to prevent duplicate execution on retry."
    )


class SwapExecutionReceipt(BaseModel):
    quote_id: str = Field(..., description="Quote that was executed.")
    venue_id: str = Field(..., description="Venue the winning route executed on.")
    from_token: str = Field(..., description="Input token symbol.")
    to_token: str = Field(..., description="Output token symbol.")
    amount_in: float = Field(..., description="Input amount in human units.")
    min_out_raw: int = Field(..., description="Slippage floor enforced on-chain.")
    mode: str = Field(..., description="Execution mode: dry_run or live.")
    calldata: Optional[str] = Field(None, description="Unsigned calldata preview (dry_run mode).")
    to_address: Optional[str] = Field(None, description="Contract the calldata targets (dry_run mode).")
    tx_hash: Optional[str] = Field(None, description="Arc transaction hash (live mode).")
    explorer_url: Optional[str] = Field(None, description="Arcscan URL for the live transaction.")
    audit_ref: Optional[str] = Field(None, description="Euthyna audit entry reference for the execution.")
    executed_at: int = Field(..., description="Unix epoch of execution.")


class SwapExecuteResponse(BaseModel):
    success: bool = Field(..., description="Whether the swap (or dry-run) completed without error.")
    receipt: Optional[SwapExecutionReceipt] = Field(None, description="Execution receipt when success is true.")
    error: Optional[str] = Field(None, description="Failure reason when success is false.")
    network: SwapNetworkInfo = Field(..., description="Arc network the swap executed on.")


class SwapSpreadVenue(BaseModel):
    venue_id: str = Field(..., description="Venue identifier.")
    venue: str = Field(..., description="Venue name.")
    available: bool = Field(..., description="Whether the venue quoted.")
    amount_out: Optional[float] = Field(None, description="Quoted output in human units.")
    anchor_divergence_bps: Optional[float] = Field(None, description="Deviation from the oracle anchor in bps.")


class SwapSpreadResponse(BaseModel):
    from_token: str = Field(..., description="Input token symbol.")
    to_token: str = Field(..., description="Output token symbol.")
    amount_in: float = Field(..., description="Reference input amount.")
    anchor_rate: Optional[float] = Field(None, description="Oracle anchor rate (output-per-input).")
    anchor_source: Optional[str] = Field(None, description="Oracle provenance.")
    best_venue_id: Optional[str] = Field(None, description="Best venue at measurement time.")
    best_amount_out: Optional[float] = Field(None, description="Best output at measurement time.")
    best_divergence_bps: Optional[float] = Field(None, description="Best venue's anchor divergence in bps.")
    best_divergence_exceeded: Optional[bool] = Field(None, description="Whether best divergence breached tolerance.")
    venues: List[SwapSpreadVenue] = Field(..., description="Per-venue measurement snapshot.")
    measured_at: int = Field(..., description="Unix epoch of the measurement.")
    note: str = Field(..., description="Honesty note: measurement only, not a realized or guaranteed profit.")


class SwapCalldataStep(BaseModel):
    step: int = Field(..., description="1-based execution order (approve, swap, gateway deposit).")
    action: str = Field(..., description="Human-readable step name.")
    to_address: str = Field(..., description="Contract the buyer signs this transaction against.")
    calldata: str = Field(..., description="Unsigned ABI calldata for the buyer's wallet to sign.")
    gas_units_estimate: int = Field(..., description="Explicit gas override (Arc: eth_estimateGas is unreliable).")


class FundGatewayPlanRequest(BaseModel):
    from_token: str = Field(..., description="Source token the buyer already holds (EURC, USYC, ...).")
    amount: float = Field(..., gt=0, description="Source amount in human token units.")
    wallet_address: str = Field(..., description="Buyer wallet that owns the source tokens and will fund its own Circle Gateway balance.")
    slippage_bps: Optional[int] = Field(None, ge=0, le=3000, description="Optional slippage tolerance in bps.")


class FundGatewayPlanResponse(BaseModel):
    available: bool = Field(..., description="False when no route exists for the requested conversion.")
    reason: Optional[str] = Field(None, description="Why the plan is unavailable (set when available is false).")
    from_token: str = Field(..., description="Source token symbol.")
    to_token: str = Field(..., description="Output token symbol (always USDC for Gateway funding).")
    amount_in: float = Field(..., description="Source amount in human units.")
    estimated_out: Optional[float] = Field(None, description="Estimated USDC out per the best route.")
    min_out_raw: Optional[int] = Field(None, description="Slippage-protected floor used in the swap calldata.")
    quote_id: Optional[str] = Field(None, description="Quote identifier backing this plan.")
    steps: List[SwapCalldataStep] = Field(..., description="Unsigned calldata steps for the buyer's wallet, in order.")
    non_custodial: bool = Field(..., description="True: every step is signed by the buyer; the backend never touches funds.")
    expires_at: Optional[int] = Field(None, description="Unix epoch after which the underlying quote expires.")
    note: str = Field(..., description="Usage guidance and promptness warning (quotes are TTL-bound).")
