import { useMemo, useState } from "react";
import type { InvoiceResponse, PaymentVerifyResponse, QmaQuery, Tier } from "../types/qma";

export function useInvoiceStore() {
  const [query, setQuery] = useState<QmaQuery | null>(null);
  const [tier, setTier] = useState<Tier>("full");
  const [invoice, setInvoice] = useState<InvoiceResponse | null>(null);
  const [verification, setVerification] = useState<PaymentVerifyResponse | null>(null);

  return useMemo(() => ({
    query,
    setQuery,
    tier,
    setTier,
    invoice,
    setInvoice,
    verification,
    setVerification,
    resetInvoice() {
      setInvoice(null);
      setVerification(null);
    },
  }), [invoice, query, tier, verification]);
}
