import { createOnrampKit, type OnrampWidget } from "@circle-fin/onramp-kit";

export interface OnrampSessionData {
  sessionToken?: string;
  sessionId?: string;
  widgetUrl: string;
  destinationWallet: string;
  expiresAt?: string;
  traceId?: string;
}

export interface OnrampMountCallbacks {
  onInitializationSuccess?: () => void;
  onInitializationError?: (err: unknown) => void;
  onDepositSubmitted?: () => void;
  onDepositSettled?: (details: { amount?: string; tokenSymbol?: string; txHash?: string }) => void;
  onDepositNotCompleted?: (reason?: string) => void;
  onSessionExpired?: () => void;
}

export async function requestOnrampSession(
  destinationAddress: string,
  appUserId?: string
): Promise<OnrampSessionData> {
  const resp = await fetch("/api/v1/onramp/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      destinationAddress,
      appUserId: appUserId || "qma-user",
    }),
  });

  if (!resp.ok) {
    const errData = await resp.json().catch(() => null);
    throw new Error(errData?.detail || `Failed to create onramp session (${resp.status})`);
  }

  return (await resp.json()) as OnrampSessionData;
}

let onrampKitInstance: ReturnType<typeof createOnrampKit> | null = null;

export function getOnrampKit() {
  if (!onrampKitInstance) {
    onrampKitInstance = createOnrampKit();
  }
  return onrampKitInstance;
}

export function mountOnrampIframe(
  container: HTMLElement,
  session: OnrampSessionData,
  callbacks?: OnrampMountCallbacks
): OnrampWidget {
  const kit = getOnrampKit();

  return kit.mountIframe({
    session: {
      sessionToken: session.sessionToken,
      sessionId: session.sessionId,
      widgetUrl: session.widgetUrl,
      destinationWallet: session.destinationWallet,
      expiresAt: session.expiresAt,
      traceId: session.traceId,
    } as any,
    container,
    title: "Arc USDC Onramp",
    onInitializationSuccess: () => {
      callbacks?.onInitializationSuccess?.();
    },
    onInitializationError: (envelope) => {
      console.warn("[Onramp] Initialization error:", envelope);
      callbacks?.onInitializationError?.(envelope);
    },
    onDepositSubmitted: () => {
      callbacks?.onDepositSubmitted?.();
    },
    onDepositSettled: (envelope) => {
      const payload = envelope?.payload as any;
      callbacks?.onDepositSettled?.({
        amount: payload?.amount,
        tokenSymbol: payload?.tokenSymbol,
        txHash: payload?.transactionHash || payload?.txHash,
      });
    },
    onDepositNotCompleted: (envelope) => {
      console.info("[Onramp] Deposit not completed:", envelope);
      callbacks?.onDepositNotCompleted?.((envelope?.payload as any)?.reason);
    },
    onSessionExpired: () => {
      callbacks?.onSessionExpired?.();
    },
  });
}

export function openOnrampPopup(
  session: OnrampSessionData,
  callbacks?: OnrampMountCallbacks
): "opened" | "blocked" {
  const kit = getOnrampKit();

  const result = kit.openWindow({
    session: {
      sessionToken: session.sessionToken,
      sessionId: session.sessionId,
      widgetUrl: session.widgetUrl,
      destinationWallet: session.destinationWallet,
      expiresAt: session.expiresAt,
      traceId: session.traceId,
    } as any,
    target: "arc-onramp-window",
    onInitializationSuccess: () => {
      callbacks?.onInitializationSuccess?.();
    },
    onInitializationError: (envelope) => {
      callbacks?.onInitializationError?.(envelope);
    },
    onDepositSubmitted: () => {
      callbacks?.onDepositSubmitted?.();
    },
    onDepositSettled: (envelope) => {
      const payload = envelope?.payload as any;
      callbacks?.onDepositSettled?.({
        amount: payload?.amount,
        tokenSymbol: payload?.tokenSymbol,
        txHash: payload?.transactionHash || payload?.txHash,
      });
    },
    onDepositNotCompleted: (envelope) => {
      callbacks?.onDepositNotCompleted?.((envelope?.payload as any)?.reason);
    },
    onSessionExpired: () => {
      callbacks?.onSessionExpired?.();
    },
  });

  return result.status;
}
