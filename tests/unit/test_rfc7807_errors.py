"""Unit tests for RFC 7807 Problem Details error responses."""

from backend.app.core.errors import problem_detail_response


def test_problem_detail_response_structure():
    resp = problem_detail_response(
        status=402,
        title="Payment Required",
        detail="Invoice requires Circle x402 settlement",
        instance="/api/v1/payment/verify",
        extra={"invoice_id": "inv-123"},
    )
    assert resp.status_code == 402
    assert resp.media_type == "application/problem+json"

    import json
    data = json.loads(resp.body.decode("utf-8"))
    assert data["status"] == 402
    assert data["title"] == "Payment Required"
    assert data["detail"] == "Invoice requires Circle x402 settlement"
    assert data["instance"] == "/api/v1/payment/verify"
    assert data["invoice_id"] == "inv-123"
