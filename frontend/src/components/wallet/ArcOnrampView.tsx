import { useEffect, useRef, useState } from "react";
import {
  requestOnrampSession,
  mountOnrampIframe,
  openOnrampPopup,
  type OnrampSessionData,
} from "../../services/circleOnramp";

interface ArcOnrampViewProps {
  wallet: string;
  onBack: () => void;
  onSettled?: (details: { amount?: string; tokenSymbol?: string; txHash?: string }) => void;
}

export function ArcOnrampView({ wallet, onBack, onSettled }: ArcOnrampViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [session, setSession] = useState<OnrampSessionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [settledInfo, setSettledInfo] = useState<{ amount?: string; tokenSymbol?: string; txHash?: string } | null>(null);
  const [widgetReady, setWidgetReady] = useState(false);

  useEffect(() => {
    let unmounted = false;
    let widgetInstance: { close: () => void } | null = null;

    async function initSession() {
      if (!wallet) {
        setError("Please connect your wallet first to purchase USDC.");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError("");
        const sessionData = await requestOnrampSession(wallet);
        if (unmounted) return;
        setSession(sessionData);

        if (containerRef.current) {
          widgetInstance = mountOnrampIframe(containerRef.current, sessionData, {
            onInitializationSuccess: () => {
              if (!unmounted) {
                setWidgetReady(true);
                setLoading(false);
              }
            },
            onInitializationError: (err) => {
              console.warn("Onramp init error:", err);
              if (!unmounted) {
                setLoading(false);
              }
            },
            onDepositSettled: (details) => {
              if (!unmounted) {
                setSettledInfo(details);
                onSettled?.(details);
              }
            },
            onDepositNotCompleted: (reason) => {
              console.info("Deposit not completed:", reason);
            },
            onSessionExpired: () => {
              if (!unmounted) {
                setError("Onramp session expired. Please refresh.");
              }
            },
          });
        }
      } catch (err: any) {
        if (!unmounted) {
          setError(err?.message || "Failed to initialize Arc Onramp");
          setLoading(false);
        }
      }
    }

    initSession();

    return () => {
      unmounted = true;
      if (widgetInstance) {
        try {
          widgetInstance.close();
        } catch {
          // ignore cleanup errors
        }
      }
    };
  }, [wallet, onSettled]);

  const handleOpenPopup = () => {
    if (!session) return;
    const outcome = openOnrampPopup(session, {
      onDepositSettled: (details) => {
        setSettledInfo(details);
        onSettled?.(details);
      },
    });
    if (outcome === "blocked") {
      alert("Popup was blocked by your browser. Please allow popups for this site or use the embedded widget.");
    }
  };

  return (
    <div style={{ display: "grid", gap: "12px", marginTop: "4px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "1.2rem" }}>💳</span>
          <div>
            <strong style={{ fontSize: "0.95rem", color: "#f0f6fc" }}>Buy USDC (Arc Onramp)</strong>
            <div style={{ fontSize: "0.75rem", color: "#8b949e" }}>Card / Apple Pay / Google Pay</div>
          </div>
        </div>
        <button
          type="button"
          onClick={onBack}
          style={{
            background: "transparent",
            border: "none",
            color: "#8b949e",
            cursor: "pointer",
            fontSize: "0.8rem",
          }}
        >
          ← Back to options
        </button>
      </div>

      {settledInfo && (
        <div
          style={{
            background: "rgba(46, 160, 67, 0.15)",
            border: "1px solid rgba(46, 160, 67, 0.4)",
            borderRadius: "8px",
            padding: "10px 14px",
            color: "#3fb950",
            fontSize: "0.85rem",
          }}
        >
          ✓ <strong>Deposit Settled!</strong> Received {settledInfo.amount || ""}{" "}
          {settledInfo.tokenSymbol || "USDC"} on Arc.
          {settledInfo.txHash && (
            <div style={{ fontSize: "0.75rem", color: "#8b949e", marginTop: "4px" }}>
              Tx: {settledInfo.txHash.slice(0, 10)}...{settledInfo.txHash.slice(-8)}
            </div>
          )}
        </div>
      )}

      {error ? (
        <div
          style={{
            padding: "12px",
            borderRadius: "8px",
            background: "rgba(248, 81, 73, 0.1)",
            border: "1px solid rgba(248, 81, 73, 0.3)",
            color: "#f85149",
            fontSize: "0.85rem",
          }}
        >
          <p style={{ margin: "0 0 8px 0" }}>{error}</p>
          {session && (
            <button
              type="button"
              className="funding-action-btn"
              onClick={handleOpenPopup}
              style={{ fontSize: "0.8rem" }}
            >
              Open in Secure Popup Window
            </button>
          )}
        </div>
      ) : (
        <div style={{ position: "relative", minHeight: "440px", borderRadius: "10px", overflow: "hidden" }}>
          {loading && !widgetReady && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                background: "rgba(13, 17, 23, 0.8)",
                zIndex: 10,
                gap: "10px",
                color: "#8b949e",
                fontSize: "0.85rem",
              }}
            >
              <div
                style={{
                  width: "28px",
                  height: "28px",
                  border: "2px solid rgba(255,255,255,0.1)",
                  borderTopColor: "#58a6ff",
                  borderRadius: "50%",
                  animation: "spin 1s linear infinite",
                }}
              />
              <span>Connecting to Arc Onramp service...</span>
            </div>
          )}

          {/* Iframe mount container */}
          <div
            ref={containerRef}
            id="onramp-mount-root"
            style={{
              width: "100%",
              minHeight: "440px",
              height: "440px",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              borderRadius: "8px",
              background: "#0d1117",
            }}
          />
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.75rem", color: "#8b949e" }}>
        <span>Destination: <code style={{ color: "#c9d1d9" }}>{wallet.slice(0, 8)}...{wallet.slice(-6)}</code></span>
        {session && (
          <button
            type="button"
            onClick={handleOpenPopup}
            style={{
              background: "transparent",
              border: "none",
              color: "#58a6ff",
              cursor: "pointer",
              fontSize: "0.75rem",
              textDecoration: "underline",
            }}
          >
            Launch in Popup ↗
          </button>
        )}
      </div>
    </div>
  );
}
