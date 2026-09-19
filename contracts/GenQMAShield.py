# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

import genlayer as gl
from genlayer import *
from genlayer.storage import TreeMap
import json


def _address_text(address) -> str:
    try:
        return str(address)
    except Exception:
        return address.as_hex


class Contract(gl.contract.Contract):
    """On-chain verifier for the exact GenQMA report selected by an invoice.

    This contract deliberately does not claim to custody or transfer Arc USDC.
    Arc settlement is a separate payment rail; this contract only records the
    validator verdict that gates report access and downstream Arc payout logic.
    """

    admin: Address
    orders: TreeMap[str, str]
    slashes: TreeMap[str, int]
    provider_bonds: TreeMap[str, int]

    def __init__(self):
        self.admin = gl.message.sender_address

    def _require_admin(self) -> None:
        if _address_text(gl.message.sender_address).lower() != _address_text(self.admin).lower():
            raise gl.vm.UserError("Only the GenQMA verifier relayer may submit reports")

    def _load_order(self, invoice_id: str) -> dict:
        raw = self.orders.get(invoice_id, "")
        if not raw:
            raise gl.vm.UserError("Order not found")
        return json.loads(raw)

    @gl.public.view
    def get_order(self, invoice_id: str) -> str:
        """Return an empty string when an invoice has not been submitted."""
        return self.orders.get(invoice_id, "")

    @gl.public.view
    def get_provider_slashes(self, provider_address: str) -> int:
        """Return the cumulative count of invalidated reports for this provider."""
        return self.slashes.get(provider_address.lower(), 0)

    @gl.public.view
    def get_provider_bond(self, provider_address: str) -> int:
        """Return the active bonded stake for this provider in micro USDC."""
        return self.provider_bonds.get(provider_address.lower(), 0)

    @gl.public.write
    def register_provider_bond(self, provider_address: str, bond_amount_micro_usdc: int) -> None:
        """Deposit or register a security bond for an intelligence provider."""
        self._require_admin()
        if bond_amount_micro_usdc <= 0:
            raise gl.vm.UserError("Bond amount must be positive")
        prev = self.provider_bonds.get(provider_address.lower(), 0)
        self.provider_bonds[provider_address.lower()] = prev + bond_amount_micro_usdc

    @gl.public.write
    def submit_and_verify(
        self,
        invoice_id: str,
        buyer_address: str,
        provider_address: str,
        symbol: str,
        expected_anomaly: str,
        query_hash: str,
        report_hash: str,
        verification_manifest: str,
        evidence_url: str,
    ) -> None:
        """Verify and permanently bind one invoice to one report hash."""
        self._require_admin()
        if not invoice_id.strip():
            raise gl.vm.UserError("Invoice id is required")
        if self.orders.get(invoice_id, ""):
            raise gl.vm.UserError("Invoice already submitted")
        if not query_hash.strip() or not report_hash.strip():
            raise gl.vm.UserError("Query and report hashes are required")
        if not verification_manifest.strip():
            raise gl.vm.UserError("Verification manifest is required")
        if len(verification_manifest.encode("utf-8")) > 12000:
            raise gl.vm.UserError("Verification manifest exceeds 12 KB")
        try:
            manifest = json.loads(verification_manifest)
        except Exception:
            raise gl.vm.UserError("Verification manifest must be valid JSON")
        if not isinstance(manifest, dict) or not isinstance(manifest.get("claims"), dict):
            raise gl.vm.UserError("Verification manifest must contain a claims object")
        if str(manifest.get("invoice_id", "")) != invoice_id:
            raise gl.vm.UserError("Verification manifest invoice binding mismatch")
        if str(manifest.get("query_hash", "")) != query_hash:
            raise gl.vm.UserError("Verification manifest query binding mismatch")
        if str(manifest.get("symbol", "")).upper() != symbol.upper():
            raise gl.vm.UserError("Verification manifest symbol binding mismatch")
        ALLOWED_EVIDENCE_PREFIXES = (
            "https://contract.mexc.com/",
            "https://clob.polymarket.com/",
            "https://gamma-api.polymarket.com/",
            "https://hermes.pyth.network/",
            "https://api.binance.com/",
        )
        if not any(evidence_url.startswith(prefix) for prefix in ALLOWED_EVIDENCE_PREFIXES):
            raise gl.vm.UserError("Evidence URL must use an authoritative whitelisted API (MEXC, Polymarket, Pyth, Binance)")

        order = {
            "invoice_id": invoice_id,
            "buyer": buyer_address,
            "provider": provider_address,
            "symbol": symbol,
            "expected_anomaly": expected_anomaly,
            "query_hash": query_hash,
            "report_hash": report_hash,
            "evidence_url": evidence_url,
            "status": "VERIFYING",
            "verdict": "PENDING",
            "confidence": 0,
            "reasoning": "",
        }

        def leader_fn():
            try:
                market_data = gl.nondet.web.render(evidence_url, mode="text")
            except Exception as exc:
                return json.dumps({
                    "verdict": "INVALID",
                    "confidence": 100,
                    "reasoning": "The authoritative evidence URL could not be fetched: " + str(exc)[:160],
                })
            if not market_data or len(market_data.strip()) < 10:
                return json.dumps({
                    "verdict": "INVALID",
                    "confidence": 100,
                    "reasoning": "The authoritative evidence URL returned no usable market data.",
                })

            prompt = f"""You are an impartial quantitative-report verifier on GenLayer.
Evaluate whether the supplied GenQMA report excerpt is supported by the live
market evidence and satisfies the invoice SLA.

INVOICE
Symbol: {symbol} (trading pairs on MEXC are formatted as {symbol}_USDT or {symbol}USDT)
Expected anomaly: {expected_anomaly}
Query hash: {query_hash}
Full report hash: {report_hash}

LIVE EVIDENCE FROM {evidence_url}
{market_data[:4000]}

PUBLIC VERIFICATION MANIFEST
{verification_manifest}

Return only JSON with this exact shape:
{{"verdict":"VALID" or "INVALID","confidence":<integer 0-100>,"reasoning":"<specific evidence-based explanation>"}}
Evaluation criteria:
1. Asset / Market match: The requested symbol or event matches the authoritative live evidence from the provider.
2. Authenticity: Confirm the market data from the source is valid and active.
3. Report claims: Check that the claims in the public verification manifest are structurally consistent with market conditions.
If the asset exists and the claims are plausible, return VALID with confidence between 85 and 95.
Return INVALID only if the market data is missing, completely unrelated to {symbol}, or the report appears fabricated."""

            return gl.nondet.exec_prompt(prompt, response_format="json")

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                leader_data = leader_result.calldata
                if isinstance(leader_data, str):
                    leader_data = json.loads(leader_data)
                validator_data = leader_fn()
                if isinstance(validator_data, str):
                    validator_data = json.loads(validator_data)
                if leader_data.get("verdict") not in ("VALID", "INVALID"):
                    return False
                if validator_data.get("verdict") != leader_data.get("verdict"):
                    return False
                leader_confidence = int(leader_data.get("confidence", -1))
                validator_confidence = int(validator_data.get("confidence", -1))
                if not 0 <= leader_confidence <= 100:
                    return False
                if not 0 <= validator_confidence <= 100:
                    return False
                if abs(leader_confidence - validator_confidence) > 20:
                    return False
                return bool(str(leader_data.get("reasoning", "")).strip())
            except Exception:
                return False

        result = gl.vm.run_nondet(leader_fn, validator_fn)
        if isinstance(result, str):
            result = json.loads(result)
        verdict = str(result.get("verdict", "")).upper()
        confidence = int(result.get("confidence", -1))
        reasoning = str(result.get("reasoning", "")).strip()
        if verdict not in ("VALID", "INVALID"):
            raise gl.vm.UserError("Validator returned an unsupported verdict")
        if not 0 <= confidence <= 100 or not reasoning:
            raise gl.vm.UserError("Validator returned an invalid response")
        if verdict == "VALID" and confidence < 70:
            verdict = "INVALID"
            reasoning = "Confidence below the 70% release threshold. " + reasoning

        if verdict == "INVALID":
            order["status"] = "REJECTED"
            order["slashed"] = True
            current_slashes = self.slashes.get(provider_address.lower(), 0)
            self.slashes[provider_address.lower()] = current_slashes + 1
        else:
            order["status"] = "VERIFIED"
            order["slashed"] = False

        order["verdict"] = verdict
        order["confidence"] = confidence
        order["reasoning"] = reasoning
        self.orders[invoice_id] = json.dumps(order)
