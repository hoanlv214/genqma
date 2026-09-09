import { requestJson } from "./api";
import type { PaidReport, QmaQuery, Tier } from "../types/qma";

export function getProviderReport(options: {
  providerId: string;
  tier: Tier;
  invoiceId: string;
  accessToken: string;
  query: QmaQuery | Record<string, any>;
}) {
  const endpoint =
    options.tier === "preview"
      ? `/api/v1/providers/${encodeURIComponent(options.providerId)}/preview`
      : `/api/v1/providers/${encodeURIComponent(options.providerId)}/full-report`;

  return requestJson<PaidReport>(`${endpoint}?invoice_id=${encodeURIComponent(options.invoiceId)}`, {
    method: "POST",
    headers: { "X-QMA-Access-Token": options.accessToken },
    body: JSON.stringify(options.query),
  });
}

export function getWalletReport(address: string, entitlementId: string, walletToken: string) {
  if (!walletToken) throw new Error("Wallet profile session required to open a private report.");
  return requestJson<PaidReport>(
    `/api/v1/wallets/${encodeURIComponent(address)}/reports/${encodeURIComponent(entitlementId)}`,
    { headers: { "X-QMA-Wallet-Token": walletToken } },
  );
}
