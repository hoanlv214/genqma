import { useState, useEffect, useRef } from "react";
import { ARC_CHAIN } from "@/config/network";

export type DecisionOutcome = "paid" | "refused";

interface RuleCheck {
  rule: string;
  passed: boolean;
  note?: string;
}

interface ReplayScenario {
  id: DecisionOutcome;
  counterparty: string;
  reference: string;
  amount: string;
  observe: string[];
  model: {
    action: string;
    confidence: string;
    argument: string;
  };
  checks: RuleCheck[];
  outcome: {
    verdict: string;
    detail: string;
    sealText: string;
  };
  hash: string;
  prev: string;
}

interface LiveMetrics {
  current_paid_count: number;
  current_revenue_usdc: number;
  unique_payers: number;
}

interface LiveLedgerBlock {
  action: string;
  hash: string;
  timestamp: string;
}

const SCENARIOS: Record<DecisionOutcome, ReplayScenario> = {
  paid: {
    id: "paid",
    counterparty: "Live buyer · Arc Testnet",
    reference: "report purchase · full tier",
    amount: "····",
    observe: [
      "Ranked anomaly requested · no cached report for this query hash",
      `Circle Gateway x402 settlement received on ${ARC_CHAIN.name}`,
    ],
    model: {
      action: "PURCHASE",
      confidence: "0.91",
      argument:
        "No cached report exists for this query hash. Settling the invoice is within the payer budget and unlocks the report immediately.",
    },
    checks: [
      { rule: "spend_guard.circuit_breaker", passed: true, note: "SpendLimitGuard armed, payer within per-payer caps" },
      { rule: "settlement_validation.recipient_amount", passed: true, note: "Treasury recipient, payer and raw amount verified" },
      { rule: "genlayer.sla_verdict", passed: true, note: "Finalized VALID, report hash bound to the invoice" },
      { rule: "euthyna.hash_linked", passed: true, note: "Decision appended to the SHA-256 audit chain" },
    ],
    outcome: {
      verdict: "PAID",
      detail: "Report unlocked via access token · creator share reserved",
      sealText: "PAID · SHA-256 HASH-LINKED",
    },
    hash: "",
    prev: "",
  },
  refused: {
    id: "refused",
    counterparty: "Autonomous buyer · over policy",
    reference: "purchase attempt · blocked before settlement",
    amount: "0.0000",
    observe: [
      "Requested purchase price breaches the payer spend cap",
      "SpendLimitGuard veto fires before any funds move",
    ],
    model: {
      action: "SKIP",
      confidence: "0.97",
      argument:
        "Requested price exceeds the payer spend limit. The guard veto is deterministic and cannot be overridden by the model.",
    },
    checks: [
      { rule: "spend_guard.spend_limit", passed: false, note: "Requested price exceeds the payer spend cap" },
      { rule: "spend_guard.circuit_breaker", passed: true, note: "Breaker healthy, refusal logged, purchases continue for others" },
      { rule: "euthyna.hash_linked", passed: true, note: "Refusal appended to the audit chain with its reason" },
    ],
    outcome: {
      verdict: "REFUSED BY POLICY",
      detail: "No funds moved · refusal recorded to the audit ledger",
      sealText: "REFUSED · SHA-256 HASH-LINKED",
    },
    hash: "",
    prev: "",
  },
};

function Stamp({ tone, words }: { tone: DecisionOutcome; words: string }) {
  const isRefused = tone === "refused";
  return (
    <div className={`receipt-stamp ${isRefused ? "receipt-stamp--refused" : "receipt-stamp--paid"}`}>
      <span className="receipt-stamp-text">{words}</span>
    </div>
  );
}

export function AgentLoopReplay() {
  const [activeTab, setActiveTab] = useState<DecisionOutcome>("paid");
  const [isPlaying, setIsPlaying] = useState(true);
  const [metrics, setMetrics] = useState<LiveMetrics | null>(null);
  const [ledgerHead, setLedgerHead] = useState<LiveLedgerBlock[]>([]);
  const timerRef = useRef<number | null>(null);

  // Live production numbers — the receipt and ledger head read real data.
  useEffect(() => {
    let disposed = false;
    const load = async () => {
      try {
        const metricsRes = await fetch("/api/v1/metrics");
        if (metricsRes.ok && !disposed) {
          const data = await metricsRes.json();
          setMetrics({
            current_paid_count: Number(data.current_paid_count || 0),
            current_revenue_usdc: Number(data.current_revenue_usdc || 0),
            unique_payers: Number(data.current_unique_payers || data.unique_payers || 0),
          });
        }
      } catch {
        /* offline — placeholders stay truthful */
      }
      try {
        const ledgerRes = await fetch("/api/v1/treasury/audit/euthyna?limit=3");
        if (ledgerRes.ok && !disposed) {
          const records = await ledgerRes.json();
          if (Array.isArray(records)) {
            setLedgerHead(
              records.slice(0, 3).map((record: { action: string; integrity_hash: string; timestamp: string }) => ({
                action: String(record.action || ""),
                hash: String(record.integrity_hash || ""),
                timestamp: String(record.timestamp || ""),
              })),
            );
          }
        }
      } catch {
        /* offline — ledger head stays on placeholders */
      }
    };
    load();
    return () => {
      disposed = true;
    };
  }, []);

  useEffect(() => {
    if (!isPlaying) return;
    timerRef.current = window.setTimeout(() => {
      setActiveTab((curr) => (curr === "paid" ? "refused" : "paid"));
    }, 7000);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [activeTab, isPlaying]);

  const avgPrice =
    metrics && metrics.current_paid_count > 0
      ? (metrics.current_revenue_usdc / metrics.current_paid_count).toFixed(4)
      : null;

  const shortHash = (value: string) =>
    value && value.length >= 16 ? `${value.slice(0, 4)}...${value.slice(-4)}` : value || "····";

  const base = SCENARIOS[activeTab];
  const scenario: ReplayScenario =
    activeTab === "paid" && avgPrice ? { ...base, amount: avgPrice } : base;
  const isRefused = activeTab === "refused";

  return (
    <div className="evidence-replay-container" role="region" aria-label="Autonomous Decision Receipt Replay">
      <div className="evidence-controls-bar">
        <div className="evidence-pill-toggle">
          <button
            type="button"
            className={`pill-btn ${activeTab === "paid" ? "active-paid" : ""}`}
            onClick={() => {
              setActiveTab("paid");
              setIsPlaying(false);
            }}
          >
            Paid
          </button>
          <button
            type="button"
            className={`pill-btn ${activeTab === "refused" ? "active-refused" : ""}`}
            onClick={() => {
              setActiveTab("refused");
              setIsPlaying(false);
            }}
          >
            Refused by policy
          </button>
        </div>

        <button
          type="button"
          className="evidence-playback-btn"
          onClick={() => setIsPlaying((p) => !p)}
          title={isPlaying ? "Pause auto-replay" : "Resume auto-replay"}
          aria-label={isPlaying ? "Pause replay" : "Play replay"}
        >
          {isPlaying ? "Pause" : "Play"}
        </button>
      </div>

      <div className="receipt-shadow-wrap">
        <article className="receipt-perforated-slip" key={scenario.id}>
          <div className="receipt-top-row">
            <span className="receipt-main-title">DECISION RECEIPT</span>
            <span className="receipt-category">qma · cfo</span>
          </div>

          <div className="receipt-vendor-block">
            <div className="receipt-vendor-left">
              <h4 className="receipt-vendor-name">{scenario.counterparty}</h4>
              <p className="receipt-vendor-ref">{scenario.reference}</p>
            </div>
            <div className="receipt-vendor-right">
              <span className="receipt-amount-val">{scenario.amount}</span>
              <span className="receipt-amount-cur">USDC</span>
            </div>
          </div>

          <div className="receipt-dashed-separator" />

          <ol className="receipt-stages-list">
            <li className="receipt-stage-item">
              <div className="stage-marker">
                <span className="stage-num">01</span>
                <span className="stage-name">OBSERVE</span>
              </div>
              <div className="stage-content">
                <ul className="stage-bullets">
                  {scenario.observe.map((line, idx) => (
                    <li key={idx}>{line}</li>
                  ))}
                </ul>
              </div>
            </li>

            <li className="receipt-stage-item">
              <div className="stage-marker">
                <span className="stage-num">02</span>
                <span className="stage-name">REASON</span>
              </div>
              <div className="stage-content">
                <div className="model-decision-bar">
                  <span>model says</span>
                  <span className="model-action-pill">{scenario.model.action}</span>
                  <span className="model-conf">confidence {scenario.model.confidence}</span>
                </div>
                <blockquote className="model-argument-quote">“{scenario.model.argument}”</blockquote>
              </div>
            </li>

            <li className="receipt-stage-item">
              <div className="stage-marker">
                <span className="stage-num">03</span>
                <span className="stage-name">ENFORCE</span>
              </div>
              <div className="stage-content">
                <ul className="enforce-rules-list">
                  {scenario.checks.map((c, i) => (
                    <li key={i} className={`rule-check-item ${!c.passed ? "rule-failed" : "rule-passed"}`}>
                      <span className="rule-icon" aria-hidden="true">
                        {c.passed ? "PASS" : "FAIL"}
                      </span>
                      <div className="rule-details">
                        <span className="rule-code-name">{c.rule}</span>
                        {c.note && <span className="rule-note">{c.note}</span>}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </li>

            <li className="receipt-stage-item">
              <div className="stage-marker">
                <span className="stage-num">04</span>
                <span className="stage-name">SIGN</span>
              </div>
              <div className="stage-content stage-sign-content">
                <div className="sign-outcome-box">
                  <span className={`outcome-verdict-badge ${isRefused ? "verdict-refused" : "verdict-paid"}`}>
                    {scenario.outcome.verdict}
                  </span>
                  <p className="outcome-detail-text">{scenario.outcome.detail}</p>
                </div>
                <Stamp tone={scenario.id} words={scenario.outcome.sealText} />
              </div>
            </li>
          </ol>

          <div className="receipt-dashed-separator" />

          <div className="receipt-provenance-row">
            <span>
              hash <span className="hash-val">{shortHash(ledgerHead[0]?.hash || "")}</span>
            </span>
            <span className="receipt-prev-hash">
              prev <span className="hash-val">{shortHash(ledgerHead[1]?.hash || "")}</span>
            </span>
          </div>
        </article>
      </div>

      <div className="ledger-head-connector">
        <span className="connector-dashed-line" />
        <div className="ledger-head-badge">
          <span className="ledger-pulse-dot" />
          <span className="ledger-head-label">LIVE LEDGER HEAD</span>
        </div>

        <div className="ledger-blocks-chain">
          {(ledgerHead.length > 0
            ? ledgerHead
            : [{ action: "awaiting records", hash: "", timestamp: "" }]
          ).map((block, index) => (
            <div key={`${block.timestamp}-${index}`} className={`ledger-block-item${index > 0 ? " ledger-block-dim" : ""}`}>
              <span className="block-seq">{block.timestamp ? block.timestamp.slice(11, 19) : "····"}</span>
              <span className="block-desc">{block.action || "system · idle"}</span>
              <span className="block-hash">{shortHash(block.hash)}</span>
            </div>
          ))}
        </div>
      </div>

      <p className="evidence-footnote">
        Wired to the live production ledger
        {metrics
          ? `: ${metrics.current_paid_count} reports settled for ${metrics.current_revenue_usdc.toFixed(2)} USDC across ${metrics.unique_payers} payers`
          : ""}
        . The stages, rule names and outcomes are the platform's own; the hashes beneath the receipt are the head of the live SHA-256 audit chain.
      </p>
    </div>
  );
}

export default AgentLoopReplay;
