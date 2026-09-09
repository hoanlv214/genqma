import { Loader } from "../ui/Loader";
import type { CSSProperties, Dispatch, FormEvent, Ref, SetStateAction } from "react";

type AgentSessionStage = "idle" | "scanning" | "selected" | "invoicing" | "awaiting_signature" | "verifying" | "unlocked" | "error";

interface AgentBuyerModalContentProps {
  agentSessionStage: AgentSessionStage;
  stageContainerRef: Ref<HTMLDivElement>;
  progressBarStyle: CSSProperties;
  agentTrace: { text: string; tone?: string }[];
  agentSelectedPick: any;
  recommendationTier: (pick: any) => "preview" | "full";
  agentSelectReason: string | null;
  agentRejectedReasons: string[];
  agentProviderComparison: Array<{
    candidate_id: string;
    symbol?: string;
    provider_id?: string;
    provider_name?: string;
    tier?: string;
    score: number;
    price_usdc: number;
    value_density: number;
    status: string;
    reason_code?: string | null;
    reason?: string | null;
  }>;
  agentSessionInvoice: any;
  formatUsdc: (value: any, digits?: number) => string;
  agentVerifyResult: any;
  agentRunning: boolean;
  handleAgentRetry: () => void;
  handleAgentCancelSession: () => void;
  setShowAgentBuyerModal: Dispatch<SetStateAction<boolean>>;
  firstDotRef: Ref<HTMLSpanElement>;
  lastDotRef: Ref<HTMLSpanElement>;
  wallet: string;
  shortAddress: (address: string) => string;
  agentChatLogRef: Ref<HTMLDivElement>;
  handleOpenUnlockedReport: () => void;
  handleAgentRun: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
  agentPrompt: string;
  setAgentPrompt: Dispatch<SetStateAction<string>>;
  tierLabel: (value: any) => string;
}

export function AgentBuyerModalContent(props: AgentBuyerModalContentProps) {
  const { agentSessionStage, stageContainerRef, progressBarStyle, agentTrace, agentSelectedPick, recommendationTier, agentSelectReason, agentRejectedReasons, agentProviderComparison, agentSessionInvoice, formatUsdc, agentVerifyResult, agentRunning, handleAgentRetry, handleAgentCancelSession, setShowAgentBuyerModal, firstDotRef, lastDotRef, wallet, shortAddress, agentChatLogRef, handleOpenUnlockedReport, handleAgentRun, agentPrompt, setAgentPrompt, tierLabel } = props;
  return (
    <>
      <div className={`agent-session-stage stage-${agentSessionStage}`} ref={stageContainerRef}>
        <div className="agent-stage-progress-bar" style={progressBarStyle}>
          <div className="agent-stage-progress-fill" />
        </div>
        {([
          ["scanning", "Scan"],
          ["selected", "Pick"],
          ["invoicing", "Invoice"],
          ["awaiting_signature", "Signature"],
          ["verifying", "Verify"],
          ["unlocked", "Unlocked"],
        ] as [string, string][]).map(([stage, label]) => {
          const order = ["scanning", "selected", "invoicing", "awaiting_signature", "verifying", "unlocked"];
          const current = order.indexOf(agentSessionStage);
          const index = order.indexOf(stage);
          const isDone = agentSessionStage !== "error" && (current > index || agentSessionStage === "unlocked");
          const isActive = agentSessionStage === stage;
          // A stage is failed if we errored out and it was the active stage
          const isFailed = agentSessionStage === "error" && isActive;
          return (
            <div
              className={`agent-stage-dot ${isDone ? "done" : ""} ${isActive && agentSessionStage !== "error" ? "active" : ""} ${isFailed ? "failed" : ""}`}
              key={stage}
            >
              <span
                ref={
                  stage === "scanning"
                    ? firstDotRef
                    : stage === "unlocked"
                      ? lastDotRef
                      : undefined
                }
              >
                {stage === "unlocked" && agentSessionStage === "unlocked" && (
                  <>
                    <span className="fw-particle p1" />
                    <span className="fw-particle p2" />
                    <span className="fw-particle p3" />
                    <span className="fw-particle p4" />
                    <span className="fw-particle p5" />
                    <span className="fw-particle p6" />
                    <span className="fw-particle p7" />
                    <span className="fw-particle p8" />
                  </>
                )}
              </span>
              {label}
            </div>
          );
        })}
      </div>

      {/* MAIN GRID */}
      <div className="agent-buyer-grid">

        {/* LEFT: EXECUTION TRACE */}
        <section className="agent-chat-panel">
          <div className="agent-chat-topline">
            <span className={`agent-live-pill ${agentRunning ? "active" : agentSessionStage === "error" ? "error" : ""}`}>
              {agentRunning ? "agent running" : agentSessionStage === "error" ? "needs attention" : agentSessionStage === "unlocked" ? "session complete" : "session ready"}
            </span>
            <span className="agent-chat-wallet">{wallet ? shortAddress(wallet) : "wallet not connected"}</span>
          </div>
          <div className="agent-chat-log" role="log" aria-live="polite" ref={agentChatLogRef}>
            {agentTrace.length ? (
                  agentTrace.map((line: any, idx: number) => (
                <div className={`agent-chat-message ${line.tone || ""}`} key={idx}>
                  <span className="agent-message-speaker">{line.tone === "t-error" ? "System" : "Agent"}</span>
                  <span>{line.text}</span>
                </div>
              ))
            ) : (
              <div className="agent-chat-message t-dim">
                <span className="agent-message-speaker">Agent</span>
                <span>Ready to scan live opportunities.</span>
              </div>
            )}

            {agentSessionStage === "unlocked" && (
              <div className="agent-success-chat-card">
                <div className="agent-chat-message t-green" style={{ border: "none", padding: 0, margin: 0, width: "100%", maxWidth: "100%", boxShadow: "none" }}>
                  <span className="agent-message-speaker" style={{ color: "var(--green)" }}>System</span>
                  <span>Report unlocked successfully! Access token issued.</span>
                </div>
                <div className="agent-success-chat-actions">
                  <button
                    type="button"
                    className="agent-modal-primary animate-pulse"
                    onClick={() => {
                      setShowAgentBuyerModal(false);
                      handleOpenUnlockedReport();
                    }}
                  >
                    <i className="ti ti-book-open" /> Open Unlocked Report
                  </button>
                  {agentVerifyResult?.settlement_id && (
                    <span className="agent-chat-settlement-ref">
                      Ref: {shortAddress(agentVerifyResult.settlement_id)}
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
          <div className="agent-input-label">Refine agent instruction</div>
          <form onSubmit={handleAgentRun} className="agent-bar-input-wrap">
            <input
              type="text"
              className="agent-bar-input"
              value={agentPrompt}
              onChange={(e) => setAgentPrompt(e.target.value)}
              placeholder="Find the best preview under 0.010 USDC"
            />
            <button type="submit" className="submit-btn" disabled={agentRunning} title="Send">
              {agentRunning ? <Loader compact variant="spinner" size="xs" className="button-loader" /> : <i className="ti ti-send"></i>}
            </button>
          </form>
          <div className="agent-bar-presets">
            <button
              type="button"
              className="preset-btn"
              onClick={() => setAgentPrompt("find best funding_memory signal under 0.010 USDC")}
            >
              Best Funding
            </button>
            <button
              type="button"
              className="preset-btn"
              onClick={() => setAgentPrompt("find best oi_memory signal under 0.005 USDC")}
            >
              Best OI
            </button>
          </div>
        </section>

        {/* RIGHT: DECISION PACKET (3 blocks) */}
        <aside className="agent-decision-panel">

          {/* BLOCK 1: DECISION */}
          <div className="agent-dp-block">
            <div className="agent-dp-block-label">Decision</div>
            {agentSelectedPick ? (
              <div className="agent-pick-card">
                <div>
                  <span className="agent-card-kicker">Selected signal</span>
                  <strong>{agentSelectedPick.symbol}</strong>
                </div>
                <div className="agent-score-orb">{Number(agentSelectedPick.score || 0).toFixed(1)}</div>
                <div className="agent-pick-meta">
                  <span>{recommendationTier(agentSelectedPick)} report</span>
                  <span>{agentSelectedPick.provider_id || "funding_memory"}</span>
                </div>
                <p>{(agentSelectedPick.reasons || ["fresh live anomaly"]).join(" | ")}</p>
                {agentSelectReason && (
                  <div className="agent-rationale">
                    <span className="agent-rationale-icon">›</span>
                    {agentSelectReason}
                  </div>
                )}
                {agentProviderComparison.length > 1 && (
                  <div className="agent-provider-comparison" aria-label="Provider comparison">
                    <div className="agent-provider-comparison-label">Provider routing</div>
                    {agentProviderComparison.slice(0, 4).map((candidate) => (
                      <div className={`agent-provider-row ${candidate.status === "selected" ? "selected" : ""}`} key={candidate.candidate_id}>
                        <span>{candidate.provider_name || candidate.provider_id || "provider"} · {candidate.symbol || "signal"}</span>
                        <span>{Number(candidate.score).toFixed(1)} / {formatUsdc(candidate.price_usdc, 6)} USDC</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="agent-empty-card">Waiting for the agent to pick a report.</div>
            )}
          </div>

          {/* BLOCK 2: PAYMENT */}
          <div className="agent-dp-block">
            <div className="agent-dp-block-label">Payment</div>
            {agentSessionInvoice ? (
              <div className="agent-invoice-card">
                <div className="agent-invoice-shine" />
                <div className="agent-invoice-head">
                  <span>Invoice ready</span>
                  <strong>{formatUsdc(agentSessionInvoice.amount, 6)}</strong>
                </div>
                <div className="agent-invoice-row">
                  <span>Invoice</span>
                  <strong>{shortAddress(agentSessionInvoice.invoice_id)}</strong>
                </div>
                <div className="agent-invoice-row">
                  <span>Tier</span>
                  <strong>{tierLabel(agentSessionInvoice.tier)}</strong>
                </div>
                <div className="agent-invoice-row">
                  <span>Provider</span>
                  <strong>{agentSessionInvoice.provider_id || "funding_memory"}</strong>
                </div>
                <div className="agent-invoice-row">
                  <span>Buyer</span>
                  <strong>{wallet ? shortAddress(wallet) : "n/a"}</strong>
                </div>
                {Array.isArray(agentSessionInvoice.split_legs) && agentSessionInvoice.split_legs.length ? (
                  <div className="agent-split-note">
                    <span className="agent-split-badge">{agentSessionInvoice.split_legs.length} split payment legs</span>
                    <span className="agent-split-sub">Creator leg + platform leg · Both must settle before report unlock</span>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="agent-empty-card">Invoice appears here after selection.</div>
            )}
          </div>

          {/* BLOCK 3: SESSION STATUS */}
          <div className="agent-dp-block">
            <div className="agent-dp-block-label">Session Status</div>
            <div className={`agent-signature-card ${agentSessionStage}`}>
              <span className="agent-signature-dot" />
              {agentSessionStage === "awaiting_signature"
                ? "Wallet signature requested. Confirm in your wallet."
                : agentSessionStage === "verifying"
                  ? "Payment accepted. Verifying report access."
                  : agentSessionStage === "unlocked"
                    ? "Report unlocked and analytics refreshed."
                    : agentSessionStage === "error"
                      ? "Signature was rejected. No funds were spent and no report was unlocked."
                      : "Signature step will start after invoice creation."}
            </div>

            <div className="agent-modal-actions">
              {agentSessionStage === "unlocked" ? (
                <button
                  type="button"
                  className="agent-modal-secondary"
                  onClick={() => setShowAgentBuyerModal(false)}
                  style={{ width: "100%" }}
                >
                  Close Window
                </button>
              ) : agentSessionStage === "error" ? (
                <>
                  <button
                    type="button"
                    className="agent-modal-retry"
                    disabled={!agentSessionInvoice || agentRunning}
                    onClick={handleAgentRetry}
                    title="Resume with existing invoice — no funds charged yet"
                  >
                    <i className="ti ti-refresh" /> Retry Signature
                  </button>
                  <button
                    type="button"
                    className="agent-modal-cancel"
                    onClick={handleAgentCancelSession}
                    title="Void invoice and clear session"
                  >
                    <i className="ti ti-x" /> Cancel Session
                  </button>
                </>
              ) : (
                <button type="button" className="agent-modal-secondary" onClick={() => setShowAgentBuyerModal(false)}>
                  Keep Running in Background
                </button>
              )}
            </div>
          </div>

        </aside>
      </div>
    </>
  );
}
