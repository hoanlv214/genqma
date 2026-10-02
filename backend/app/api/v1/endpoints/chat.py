"""Paid report chat endpoints."""

from types import SimpleNamespace

from typing import Optional

from fastapi import APIRouter, Body, HTTPException, status, Security

from backend.app.schemas import ChatRequest, ChatResponse
from backend.app.core.enums import DecisionSource
from backend.app.core.openapi_responses import documented_errors
from backend.app.core.security_schemes import qma_access_token_header
from backend.app.core.x402_spec import build_402_challenge_payload


router = APIRouter(tags=["Report chat"])


def create_chat_router(deps: SimpleNamespace) -> APIRouter:
    migrated = APIRouter(tags=["Report chat"])

    @migrated.get(
        "/api/v1/chat",
        responses=documented_errors(402),
        include_in_schema=False,
    )
    def handle_chat_probe():
        """Returns 402 challenge for agents probing chat endpoint."""
        challenge_body, challenge_headers = build_402_challenge_payload(
            url="/api/v1/chat",
            amount_decimal="0.005000",
            description="GenQMA AI Report Chat",
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=challenge_body,
            headers=challenge_headers,
        )

    @migrated.post(
        "/api/v1/chat",
        response_model=ChatResponse,
        response_model_exclude_unset=True,
        responses=documented_errors(402, 404, 429, 500),
    )
    def handle_chat_request(
        payload: Optional[ChatRequest] = Body(None),
        qma_access_token: Optional[str] = Security(qma_access_token_header),
    ):
        """Answers interactive user queries regarding a paid report."""
        if payload is None:
            challenge_body, challenge_headers = build_402_challenge_payload(
                url="/api/v1/chat",
                amount_decimal="0.005000",
                description="GenQMA AI Report Chat",
            )
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=challenge_body,
                headers=challenge_headers,
            )

        invoice_id = payload.invoice_id
        user_message = payload.message

        token_payload = deps.verify_access_token(qma_access_token or "")
        if token_payload.get("invoice_id") != invoice_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access token does not match requested invoice.")

        deps.reload_persistent_state()

        invoices_db = deps.get_invoices_db()
        paid_reports = deps.get_paid_reports()
        invoice = invoices_db.get(invoice_id)
        report_record = None

        if invoice:
            settlement_id = invoice.get("settlement_id")
            for record in paid_reports.values():
                rec_report = record.get("report") or {}
                rec_inv = rec_report.get("invoice") or {}
                if rec_inv.get("invoice_id") == invoice_id or (settlement_id and record.get("settlement_id") == settlement_id):
                    report_record = record
                    break
        else:
            for record in paid_reports.values():
                rec_report = record.get("report") or {}
                rec_inv = rec_report.get("invoice") or {}
                if rec_inv.get("invoice_id") == invoice_id:
                    report_record = record
                    invoice = rec_inv
                    break

        if not invoice or invoice.get("status") != "paid":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="A valid, paid invoice is required to use AI Chat.",
            )

        if not report_record or not report_record.get("report"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report data not found for this invoice. Settle and retrieve the report first.",
            )

        report = report_record["report"]
        symbol = report.get("query_symbol") or report.get("query", {}).get("symbol") or "this asset"
        regime_cluster = report.get("regime_cluster", "Unknown")
        regime_description = report.get("regime_description", "No description available.")

        win_rate = report.get("weighted_win_rate") or report.get("rough_win_rate") or 0.0
        avg_profit = report.get("weighted_avg_profit") or report.get("rough_avg_profit") or 0.0

        ci_win = report.get("ci_win_rate_95") or [0.0, 0.0]
        ci_profit = report.get("ci_avg_profit_95") or [0.0, 0.0]

        ci_win_str = f"[{ci_win[0]:.1f}% - {ci_win[1]:.1f}%]"
        ci_profit_str = f"[{ci_profit[0]:.2f}% - {ci_profit[1]:.2f}%]"

        perc = report.get("percentiles") or {}
        p10 = perc.get("P10", 0.0)
        p50 = perc.get("P50_median", 0.0)
        worst = perc.get("worst_case_max_loss") or report.get("worst_case_max_loss") or 0.0

        is_ood = report.get("is_ood", False)
        ood_p = report.get("ood_p_value", 1.0)
        novelty_status = "High Novelty (Out-of-Distribution)" if is_ood else "Familiar Pattern (In-Distribution)"

        analogs = report.get("analogs") or report.get("top_analogs") or []
        analogs_list = ", ".join([a.get("symbol", "") for a in analogs[:4] if a.get("symbol")])
        if not analogs_list:
            analogs_list = "None"

        warnings = report.get("validation_warnings") or []
        risk_flags = report.get("risk_flags") or []

        msg_lower = user_message.lower()

        if any(k in msg_lower for k in ["risk", "loss", "drawdown", "worst", "danger", "safe", "liquidat", "warning"]):
            warnings_str = "\n".join([f"- {w}" for w in (warnings + risk_flags)])
            if not warnings_str:
                warnings_str = "- No critical statistical anomalies flagged."
            answer = f"""Regarding the risk profile for {symbol}, our backtest of the **{regime_cluster}** shows a historical worst-case maximum loss of **{worst * 100:.1f}%** (or P10 outcome of **{p10:.1f}%**) among the closest historical analogs.

Additionally, our validation pipeline flagged these diagnostics:
{warnings_str}

In this regime, anomalous negative funding rates can mean-revert violently or persist if the asset has structural sell pressure. We advise keeping position sizes conservative and using strict stop-losses. Past performance does not guarantee future results."""

        elif any(k in msg_lower for k in ["win", "rate", "percent", "probability", "chance", "profit", "earn", "return"]):
            answer = f"""The historical win rate of **{win_rate:.1f}%** is calculated across **{len(analogs)}** similar historical events, weighted by similarity score and time-decay. This indicates that situations matching {symbol}'s current parameters (funding rate, market cap, and volume) had a high frequency of positive outcomes in our backtest window.

Specifically, the 95% confidence interval for the win rate is **{ci_win_str}**, with a median outcome of **{p50:.1f}%** and an average peak profit of **{avg_profit:.2f}%** (CI: {ci_profit_str}). However, outlier outcomes are common in high-novelty situations. Past performance does not guarantee future results."""

        elif any(k in msg_lower for k in ["regime", "cluster", "context", "market", "situation", "analog", "similar"]):
            answer = f"""The asset {symbol} currently falls under the **{regime_cluster}** cluster. This regime is described as: *{regime_description}*.

The novelty check shows a p-value of **{ood_p:.5f}**, classifying this signal as a **{novelty_status}**. The closest historical analogs matched in this regime include: **{analogs_list}**. Past performance does not guarantee future results."""

        else:
            answer = f"""Here is a quantitative executive summary for the {symbol} anomaly report:
- **Market Regime:** {regime_cluster} ({novelty_status})
- **Backtest Win Rate:** {win_rate:.1f}% ({ci_win_str} 95% CI)
- **Average Peak Outcome:** {avg_profit:+.2f}% (95% CI: {ci_profit_str})
- **Top Historical Analogs:** {analogs_list}

Feel free to ask me details about:
1. What are the main **risks and warnings** for this anomaly?
2. How is the **win rate** and percentiles computed?
3. What are the **closest historical analogs** matched?

Past performance does not guarantee future results."""

        return {"answer": answer, "engine": DecisionSource.HEURISTIC.value}

    return migrated
