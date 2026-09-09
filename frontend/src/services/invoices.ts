import { requestJson, withSyntheticFlag } from "./api";
import type { InvoiceRequest, InvoiceResponse, PaymentVerifyRequest, PaymentVerifyResponse } from "../types/qma";

export function quotePrice(payload: Record<string, any>) {
  return requestJson<{ amount_usdc: number; complexity_score?: number }>("/api/v1/payment/quote", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createInvoice(payload: InvoiceRequest) {
  return requestJson<InvoiceResponse>("/api/v1/payment/invoice", {
    method: "POST",
    body: JSON.stringify(withSyntheticFlag({
      resource_type: "qma_signal_report",
      ...payload,
    })),
  });
}

export function verifyPayment(invoiceId: string, payload: PaymentVerifyRequest) {
  return requestJson<PaymentVerifyResponse>(`/api/v1/payment/verify?invoice_id=${encodeURIComponent(invoiceId)}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getInvoiceStatus(invoiceId: string, invoiceSecret: string) {
  return requestJson<any>(
    `/api/v1/payment/invoices/${encodeURIComponent(invoiceId)}/status`,
    {
      headers: {
        "X-QMA-Invoice-Secret": invoiceSecret,
      },
    }
  );
}

export function getSettlement(settlementId: string) {
  return requestJson<Record<string, unknown>>(`/api/v1/payment/settlement/${encodeURIComponent(settlementId)}`);
}

export function submitWithdrawal(payload: Record<string, unknown>) {
  return requestJson<Record<string, any>>("/api/v1/payment/withdraw", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
