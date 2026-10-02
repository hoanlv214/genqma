import { useState, useEffect, useRef, useId } from "react";
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

const SCENARIOS: Record<DecisionOutcome, ReplayScenario> = {
  paid: {
    id: "paid",
    counterparty: "QMA Research Lab",
    reference: "SRV-017 · custom diligence sprint · phase 1",
    amount: "2,800.00",
    observe: [
      "Screened · KYC & Circle Agent Wallet verified",
      "Milestone verified · quantitative findings & audit passed",
    ],
    model: {
      action: "PAY",
      confidence: "0.95",
      argument: "Milestone deliverables approved by consensus, within autonomous budget.",
    },
    checks: [
      { rule: "service.milestone_verified", passed: true },
      { rule: "invoice.duplicate_of_settled", passed: true },
      {
        rule: "counterparty.payment_limit",
        passed: true,
        note: "2,800 within the 10,000 USDC limit",
      },
      {
        rule: "treasury.agent_wallet_policy",
        passed: true,
        note: "Rule #14 spend policy enforced",
      },
    ],
    outcome: {
      verdict: "PAID",
      detail: `Settled on ${ARC_CHAIN.name} via Agent Wallet`,
      sealText: "SIGNED · ED25519 · HASH-LINKED ·",
    },
    hash: "c07e...4d28",
    prev: "8f42...a91c",
  },
  refused: {
    id: "refused",
    counterparty: "Apex Alpha Analytics",
    reference: "EXP-0931 · expedited inference compute pack",
    amount: "18,000.00",
    observe: [
      "Screened · tier 2 counterparty limit 5,000 USDC",
      "Marked urgent by provider · unscheduled compute spike",
    ],
    model: {
      action: "HOLD",
      confidence: "0.84",
      argument: "Vendor requested expedited payout, but claim breaches quarterly autonomous spend limit.",
    },
    checks: [
      { rule: "invoice.duplicate_of_settled", passed: true },
      {
        rule: "counterparty.payment_limit",
        passed: false,
        note: "18,000 exceeds 5,000 USDC autonomous policy limit",
      },
      {
        rule: "treasury.dual_custody",
        passed: false,
        note: "Requires human CFO multisig signature for > 5,000 USDC",
      },
    ],
    outcome: {
      verdict: "REFUSED BY POLICY",
      detail: "No funds moved · Rejection cryptographically logged",
      sealText: "REFUSED · SIGNED · HASH-LINKED ·",
    },
    hash: "e40a...f6d3",
    prev: "c07e...4d28",
  },
};

function Seal({ tone, words }: { tone: DecisionOutcome; words: string }) {
  const pathId = useId();
  const isRefused = tone === "refused";
  return (
    <svg
      viewBox="0 0 120 120"
      aria-hidden="true"
      className={`receipt-seal-stamp ${isRefused ? "receipt-seal-stamp--refused" : "receipt-seal-stamp--paid"}`}
    >
      <defs>
        <path
          id={pathId}
          d="M60 60 m-47 0 a47 47 0 1 1 94 0 a47 47 0 1 1 -94 0"
        />
      </defs>
      <circle cx="60" cy="60" r="57" fill="none" stroke="currentColor" strokeWidth="2" />
      <circle
        cx="60"
        cy="60"
        r="37"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeDasharray="2 3"
      />
      <text
        fill="currentColor"
        fontSize="10"
        fontWeight="600"
        letterSpacing="2.1"
        className="receipt-seal-text"
      >
        <textPath href={`#${pathId}`} startOffset="0">
          {words}
        </textPath>
      </text>
      <g transform="translate(40 40)">
        <path
          fill="currentColor"
          d="M20 2.25c1.39 0 2.61.33 3.82 1.03l9.04 5.22a7.64 7.64 0 0 1 3.82 6.62v9.76a7.64 7.64 0 0 1-3.82 6.62l-9.04 5.22a7.64 7.64 0 0 1-7.64 0L7.14 31.5a7.64 7.64 0 0 1-3.82-6.62v-9.76A7.64 7.64 0 0 1 7.14 8.5l9.04-5.22A7.64 7.64 0 0 1 20 2.25Z"
        />
        {isRefused ? (
          <path
            d="m13.5 13.5 13 13m0-13-13 13"
            fill="none"
            stroke="#fdfcf7"
            strokeWidth="3.2"
            strokeLinecap="round"
          />
        ) : (
          <path
            d="m10.6 12.25 6.8 15.05c.68 1.5 2.77 1.67 3.68.29l8.32-12.58"
            fill="none"
            stroke="#fdfcf7"
            strokeWidth="3.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
      </g>
    </svg>
  );
}

export function AgentLoopReplay() {
  const [activeTab, setActiveTab] = useState<DecisionOutcome>("paid");
  const [isPlaying, setIsPlaying] = useState(true);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isPlaying) return;
    timerRef.current = window.setTimeout(() => {
      setActiveTab((curr) => (curr === "paid" ? "refused" : "paid"));
    }, 7000);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [activeTab, isPlaying]);

  const scenario = SCENARIOS[activeTab];
  const isRefused = activeTab === "refused";

  return (
    <div className="evidence-replay-container" role="region" aria-label="Autonomous Decision Receipt Replay">
      {/* Top Controls Header */}
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
          {isPlaying ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="4" width="4" height="16" rx="1" />
              <rect x="14" y="4" width="4" height="16" rx="1" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          )}
        </button>
      </div>

      {/* Floating Perforated Paper Receipt */}
      <div className="receipt-shadow-wrap">
        <article className="receipt-perforated-slip" key={scenario.id}>
          {/* Header Row */}
          <div className="receipt-top-row">
            <span className="receipt-main-title">DECISION RECEIPT</span>
            <span className="receipt-category">qma · cfo</span>
          </div>

          {/* Counterparty & Amount */}
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

          {/* 4 Stages */}
          <ol className="receipt-stages-list">
            {/* 01 OBSERVE */}
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

            {/* 02 REASON */}
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
                <blockquote className="model-argument-quote">
                  “{scenario.model.argument}”
                </blockquote>
              </div>
            </li>

            {/* 03 ENFORCE */}
            <li className="receipt-stage-item">
              <div className="stage-marker">
                <span className="stage-num">03</span>
                <span className="stage-name">ENFORCE</span>
              </div>
              <div className="stage-content">
                <ul className="enforce-rules-list">
                  {scenario.checks.map((c, i) => (
                    <li
                      key={i}
                      className={`rule-check-item ${!c.passed ? "rule-failed" : "rule-passed"}`}
                    >
                      <span className="rule-icon" aria-hidden="true">
                        {c.passed ? (
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                        ) : (
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                          </svg>
                        )}
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

            {/* 04 SIGN */}
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
                <Seal tone={scenario.id} words={scenario.outcome.sealText} />
              </div>
            </li>
          </ol>

          <div className="receipt-dashed-separator" />

          {/* Cryptographic Footprint */}
          <div className="receipt-provenance-row">
            <span>
              hash <span className="hash-val">{scenario.hash}</span>
            </span>
            <span className="receipt-prev-hash">
              prev <span className="hash-val">{scenario.prev}</span>
            </span>
          </div>
        </article>
      </div>

      {/* Connected Live Ledger Head */}
      <div className="ledger-head-connector">
        <span className="connector-dashed-line" />
        <div className="ledger-head-badge">
          <span className="ledger-pulse-dot" />
          <span className="ledger-head-label">LIVE LEDGER HEAD</span>
        </div>

        <div className="ledger-blocks-chain">
          <div className="ledger-block-item">
            <span className="block-seq">#358</span>
            <span className="block-desc">system · cycle_complete</span>
            <span className="block-hash">03af...fefc</span>
          </div>
          <div className="ledger-block-item ledger-block-dim">
            <span className="block-seq">#357</span>
            <span className="block-desc">treasury · hold</span>
            <span className="block-hash">6c7b...2850</span>
          </div>
        </div>
      </div>

      {/* Bottom Subtitle / Explainer */}
      <p className="evidence-footnote">
        A replay with illustrative vendors and amounts. The stages, rule names and outcomes are the agent’s own; the entries beneath it are the live signed ledger.
      </p>
    </div>
  );
}

export default AgentLoopReplay;
