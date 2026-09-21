import { API_BASE_URL } from "./api";
import { requireWalletProfileHeaders } from "./walletProfileSession";

export async function withdrawAgentFunds(owner: string, amount: number): Promise<void> {
  const storageKey = `qma:pending-withdrawal:${owner.toLowerCase()}:${amount.toFixed(6)}`;
  const requestId = localStorage.getItem(storageKey) || crypto.randomUUID();
  // Persist before submitting. A timeout or page reload must reuse this UUID.
  localStorage.setItem(storageKey, requestId);
  const walletHeaders = await requireWalletProfileHeaders(owner);
  const response = await fetch(`${API_BASE_URL}/api/v1/sessions/withdraw`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "1", ...walletHeaders },
    body: JSON.stringify({ owner_wallet: owner, amount_usdc: amount, request_id: requestId }),
  });
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.message || (typeof result.detail === "string" ? result.detail : "Withdrawal failed. Retry to check the same request."));
  }
  localStorage.removeItem(storageKey);
}
