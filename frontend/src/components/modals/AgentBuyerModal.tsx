import type { ReactNode } from "react";

interface AgentBuyerModalProps {
  open: boolean;
  startedAt: number | null;
  elapsed: string;
  decisionLatency: string | null;
  agentRejectedReasons: string[];
  onClose: () => void;
  children: ReactNode;
}

export function AgentBuyerModal({
  open,
  startedAt,
  elapsed,
  decisionLatency,
  agentRejectedReasons,
  onClose,
  children,
}: AgentBuyerModalProps) {
  if (!open) return null;

  return (
    <div className="modal-backdrop open agent-buyer-backdrop" style={{ display: "flex" }}>
      <div className="agent-buyer-modal" role="dialog" aria-modal="true" aria-labelledby="agent-buyer-title">
        <div className="agent-buyer-header">
          <div>
            <div className="agent-buyer-eyebrow">QMA Buyer Agent</div>
            <div className="agent-buyer-title" id="agent-buyer-title">Live report purchase session</div>
            <div className="agent-buyer-subtitle">
              The agent evaluates live opportunities, selects the best report under your policy, creates a provider-bound invoice, and requests wallet authorization for x402 payment.
            </div>
          </div>
          <div className="agent-header-right">
            {startedAt && (
              <div className="agent-timing-strip">
                <span className="agent-timing-item">
                  <span className="agent-timing-label">Started</span>
                  <span className="agent-timing-val">{new Date(startedAt).toLocaleTimeString()}</span>
                </span>
                <span className="agent-timing-item">
                  <span className="agent-timing-label">Elapsed</span>
                  <span className="agent-timing-val">{elapsed}</span>
                </span>
                {decisionLatency && (
                  <span className="agent-timing-item">
                    <span className="agent-timing-label">Decision</span>
                    <span className="agent-timing-val">{decisionLatency}</span>
                  </span>
                )}
              </div>
            )}
            <button className="icon-button" type="button" title="Close" onClick={onClose}>
              <i className="ti ti-x" />
            </button>
          </div>
        </div>
        {agentRejectedReasons.length > 0 && (
          <div className="agent-rationale agent-rejected-reasons" role="status">
            <span className="agent-rationale-icon">›</span>
            <div>
              <div>Other candidates considered and rejected:</div>
              <ul>
                {agentRejectedReasons.slice(0, 3).map((reason, index) => (
                  <li key={`${reason}-${index}`}>{reason}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
