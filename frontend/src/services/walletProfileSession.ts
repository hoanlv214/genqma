import { requestJson, API_BASE_URL } from "./api";
import { getWalletProvider } from "./wallet";

interface WalletProfileCache {
  token: string;
  expiresAt: number;
}

export function walletProfileTokenCacheKey(account: string) {
  return `qma_wallet_profile_token_${account.toLowerCase()}`;
}

export function clearWalletProfileSession(account: string) {
  if (!account) return;
  const key = walletProfileTokenCacheKey(account);
  sessionStorage.removeItem(key);
  localStorage.removeItem(key);
}

export function clearAllWalletProfileSessions() {
  const sessionKeys: string[] = [];
  for (let i = 0; i < sessionStorage.length; i += 1) {
    const key = sessionStorage.key(i);
    if (key && key.startsWith("qma_wallet_profile_token_")) sessionKeys.push(key);
  }
  sessionKeys.forEach((key) => sessionStorage.removeItem(key));

  const localKeys: string[] = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key && key.startsWith("qma_wallet_profile_token_")) localKeys.push(key);
  }
  localKeys.forEach((key) => localStorage.removeItem(key));
}

export function getCachedWalletProfileToken(account: string) {
  if (!account) return "";
  const normalized = account.toLowerCase();
  const key = walletProfileTokenCacheKey(normalized);
  const raw = sessionStorage.getItem(key) || localStorage.getItem(key);
  if (!raw) return "";
  try {
    const cached = JSON.parse(raw) as WalletProfileCache;
    if (cached?.token && Number(cached.expiresAt || 0) > Date.now() + 15_000) {
      return cached.token;
    }
  } catch {
    // Older builds stored the raw JWT. Drop it so an expired token cannot poison reloads.
  }
  clearWalletProfileSession(normalized);
  return "";
}

export function walletProfileMessage(account: string, nonce: string, issuedAt: number) {
  return [
    "QMA Wallet Profile Access",
    `Wallet: ${account.toLowerCase()}`,
    `Nonce: ${nonce}`,
    `Issued At: ${issuedAt}`,
    "Purpose: unlock-paid-report-snapshots",
  ].join("\n");
}

export async function requestWalletProfileSession(account: string) {
  const normalized = account.toLowerCase();
  const cached = getCachedWalletProfileToken(normalized);
  if (cached) return cached;

  const provider = getWalletProvider();
  if (!provider) throw new Error("Connect the wallet owner to unlock private report snapshots.");

  const accounts = await provider.request<string[]>({ method: "eth_requestAccounts" });
  const active = accounts?.[0] ? String(accounts[0]) : "";
  if (active.toLowerCase() !== normalized) {
    throw new Error("Connected wallet does not match this private profile.");
  }

  const nonceData = await requestJson<{ nonce?: string; issued_at?: number }>(
    `/api/v1/wallets/${normalized}/nonce`,
  );
  const nonce = String(nonceData?.nonce || "");
  if (!nonce) throw new Error("Failed to obtain a wallet profile nonce. Retry wallet verification.");
  // Server-issued nonce + server issued_at: single-use (blocks signature
  // replay) and immune to browser clock skew in the ±300s freshness check.
  const issuedAt = Number(nonceData?.issued_at) || Math.floor(Date.now() / 1000);
  const message = walletProfileMessage(normalized, nonce, issuedAt);
  const signature = await provider.request<string>({
    method: "personal_sign",
    params: [message, active],
  });

  const data = await requestJson<{ wallet_token?: string; expires_in?: number }>(`/api/v1/wallets/${normalized}/session`, {
    method: "POST",
    body: JSON.stringify({
      nonce,
      issued_at: issuedAt,
      signature,
    }),
  });

  const token = data.wallet_token || "";
  if (!token) return "";

  const expiresInMs = Math.max(30, Number(data.expires_in || 3600)) * 1000;
  const payload = JSON.stringify({
    token,
    expiresAt: Date.now() + expiresInMs,
  });
  const key = walletProfileTokenCacheKey(normalized);
  sessionStorage.setItem(key, payload);
  localStorage.setItem(key, payload);
  return token;
}

export async function requireWalletProfileHeaders(account: string): Promise<Record<string, string>> {
  const token = await requestWalletProfileSession(account);
  if (!token) throw new Error("Wallet ownership verification is required.");
  return { "X-QMA-Wallet-Token": token };
}

export function getWalletSummary(account: string) {
  return requestJson<Record<string, any>>(`/api/v1/wallets/${encodeURIComponent(account)}/summary`);
}

export function getWalletPayments(account: string, page = 1, pageSize = 10, walletToken = "") {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return requestJson<Record<string, any>>(
    `/api/v1/wallets/${encodeURIComponent(account)}/payments?${params.toString()}`,
    walletToken ? { headers: { "X-QMA-Wallet-Token": walletToken } } : undefined,
  );
}

export function getWalletEntitlements(wallet: string) {
  return requestJson<Record<string, any>>(`/api/v1/entitlements/wallet/${encodeURIComponent(wallet)}`);
}
