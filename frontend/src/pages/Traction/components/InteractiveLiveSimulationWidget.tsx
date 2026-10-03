import { useEffect, useState } from "react";
import { apiUrl } from "@/services/api";
import { ARC_CHAIN } from "@/config/network";
import { cn } from "@/utils/cn";

interface SimulationStep {
  id: number;
  title: string;
  badge: string;
  badgeColor: string;
  description: string;
  details: Record<string, string>;
  link?: { label: string; url: string };
}

interface LivePaymentEvent {
  invoice_id: string;
  symbol: string;
  tier: string;
  provider_id: string;
  amount_usdc: number;
  gateway_status: string;
  transaction_hash: string | null;
  explorer_url: string | null;
  paid_at: number;
}

interface EuthynaRecord {
  action: string;
  amount_usdc: number;
  status: string;
  genlayer_consensus: string | null;
  integrity_hash: string;
  arcscan_url: string | null;
  policy_rule_applied: string;
}

interface TreasuryPosition {
  treasury_liquid_usdc: number;
  usyc_shares: number;
  current_apy_percent: number;
  earn_protocol: string;
}

interface LiveLedger {
  payment: LivePaymentEvent | null;
  verdict: EuthynaRecord | null;
  position: TreasuryPosition | null;
}

function shortHash(hash: string | null | undefined): string {
  if (!hash) return "-";
  return `${hash.slice(0, 10)}…${hash.slice(-6)}`;
}

export function InteractiveLiveSimulationWidget() {
  const [isRunning, setIsRunning] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(0);
  const [isCompleted, setIsCompleted] = useState(false);
  const [elapsedMs, setElapsedMs] = useState<number>(0);
  const [ledger, setLedger] = useState<LiveLedger | null>(null);

  // Every step below renders values pulled live from the platform API —
  // payment ledger, Euthyna hash-chained audit trail and the on-chain
  // treasury position. Nothing here is mocked: when a source has no data yet
  // the step says so instead of inventing numbers.
  const fetchLiveLedger = async () => {
    const next: LiveLedger = { payment: null, verdict: null, position: null };
    const [paymentsRes, euthynaRes, positionRes] = await Promise.allSettled([
      fetch(apiUrl("/api/v1/platform/payments?page_size=1")),
      fetch(apiUrl("/api/v1/treasury/audit/euthyna?limit=5")),
      fetch(apiUrl("/api/v1/treasury/usyc/position")),
    ]);
    try {
      if (paymentsRes.status === "fulfilled" && paymentsRes.value.ok) {
        const data = await paymentsRes.value.json();
        next.payment = (data?.recent_payments?.[0] as LivePaymentEvent) || null;
      }
    } catch { /* keep null */ }
    try {
      if (euthynaRes.status === "fulfilled" && euthynaRes.value.ok) {
        const data = await euthynaRes.value.json();
        const records = Array.isArray(data) ? (data as EuthynaRecord[]) : [];
        next.verdict = records.find((r) => r.genlayer_consensus) || records[0] || null;
      }
    } catch { /* keep null */ }
    try {
      if (positionRes.status === "fulfilled" && positionRes.value.ok) {
        next.position = (await positionRes.value.json()) as TreasuryPosition;
      }
    } catch { /* keep null */ }
    setLedger(next);
  };

  useEffect(() => {
    fetchLiveLedger();
  }, []);

  const runSimulation = async () => {
    if (isRunning) return;
    setIsRunning(true);
    setIsCompleted(false);
    setActiveStep(1);
    setElapsedMs(0);

    const startTime = Date.now();
    const timerInterval = setInterval(() => {
      setElapsedMs(Date.now() - startTime);
    }, 50);

    // Re-read the live ledger so the replay always reflects the latest
    // on-chain state, then walk the four steps.
    await fetchLiveLedger();

    // Step 1 -> Step 2
    await new Promise((resolve) => setTimeout(resolve, 750));
    setActiveStep(2);

    // Step 2 -> Step 3
    await new Promise((resolve) => setTimeout(resolve, 950));
    setActiveStep(3);

    // Step 3 -> Step 4
    await new Promise((resolve) => setTimeout(resolve, 800));
    setActiveStep(4);

    // Complete
    await new Promise((resolve) => setTimeout(resolve, 850));
    clearInterval(timerInterval);
    setIsRunning(false);
    setIsCompleted(true);
  };

  const payment = ledger?.payment ?? null;
  const verdict = ledger?.verdict ?? null;
  const position = ledger?.position ?? null;

  const steps: SimulationStep[] = [
    {
      id: 1,
      title: "Verified Alpha Report Acquired",
      badge: payment ? "LIVE PURCHASE" : "AWAITING PURCHASE",
      badgeColor: "var(--accent)",
      description: payment
        ? `Latest report bought on the marketplace: the ${payment.tier} tier report on ${payment.symbol} from ${payment.provider_id}.`
        : "No report has been purchased yet. This step binds to the platform's live payment ledger.",
      details: payment
        ? {
            "Target Asset": `${payment.symbol} (${payment.tier})`,
            "Provider": payment.provider_id,
            "Invoice": payment.invoice_id,
            "Price": `${payment.amount_usdc} USDC`,
          }
        : {
            "Target Asset": "awaiting first purchase",
            "Source": "live payment ledger",
          },
    },
    {
      id: 2,
      title: "Autonomous x402 Micropayment",
      badge: payment?.transaction_hash ? "ON-CHAIN SETTLED" : payment ? "GATEWAY SETTLED" : "AWAITING SETTLEMENT",
      badgeColor: "var(--green)",
      description: payment
        ? `Circle Gateway settled ${payment.amount_usdc} USDC for invoice ${payment.invoice_id} on ${ARC_CHAIN.name}.`
        : "Settlement happens through Circle Gateway x402 pay-per-query the moment a report is bought.",
      details: payment
        ? {
            "Settlement Layer": `Arc Network (${ARC_CHAIN.name})`,
            "Amount Settled": `${payment.amount_usdc} USDC`,
            "Gateway Status": payment.gateway_status,
            "Tx": payment.transaction_hash ? shortHash(payment.transaction_hash) : "batched by Gateway",
          }
        : {
            "Settlement Layer": `Arc Network (${ARC_CHAIN.name})`,
            "Protocol": "Circle Gateway x402",
          },
      link: payment?.explorer_url
        ? { label: "View Arcscan Transaction", url: payment.explorer_url }
        : undefined,
    },
    {
      id: 3,
      title: "GenLayer SLA Verification",
      badge: verdict?.genlayer_consensus ? `SLA ${verdict.genlayer_consensus}` : "AWAITING VERDICT",
      badgeColor: "var(--purple)",
      description: verdict
        ? `${verdict.action} recorded in the hash-chained Euthyna ledger with GenLayer consensus ${verdict.genlayer_consensus ?? "pending"}.`
        : "Every settlement is written to the Euthyna SHA-256 hash chain once GenLayer consensus finalizes.",
      details: verdict
        ? {
            "Verdict": verdict.genlayer_consensus ?? "PENDING",
            "Status": verdict.status,
            "Payout": `${verdict.amount_usdc} USDC`,
            "Ledger Seal": `${verdict.integrity_hash.slice(0, 14)}…`,
          }
        : {
            "Verdict": "awaiting first verified settlement",
            "Ledger": "Euthyna SHA-256 hash chain",
          },
      link: verdict?.arcscan_url ? { label: "Inspect Ledger Tx", url: verdict.arcscan_url } : undefined,
    },
    {
      id: 4,
      title: "Autonomous CFO Treasury Sweep",
      badge: position ? "LIVE POSITION" : "AWAITING POSITION",
      badgeColor: "var(--amber)",
      description: position
        ? `Treasury engine tracks ${position.treasury_liquid_usdc} USDC liquid against the configured yield position (${position.earn_protocol}).`
        : "The CFO engine evaluates idle cash for the configured yield vault on every cycle.",
      details: position
        ? {
            "Liquid USDC": `${position.treasury_liquid_usdc}`,
            "Yield Shares": `${position.usyc_shares}`,
            "Target APY": `${position.current_apy_percent}%`,
            "Sweep Status": position.usyc_shares > 0 ? "position active" : "no sweep yet — below policy threshold",
          }
        : {
            "Sweep Status": "awaiting treasury position",
          },
    },
  ];

  const progressBarWidth = isCompleted
    ? "w-full"
    : activeStep === 1
    ? "w-1/4"
    : activeStep === 2
    ? "w-2/4"
    : activeStep === 3
    ? "w-3/4"
    : activeStep === 4
    ? "w-full"
    : "w-0";

  return (
    <section className="traction-panel interactive-simulation-panel">
      {/* Header */}
      <div className="traction-panel-heading">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="eyebrow">Interactive Protocol Verification</span>
            <span className="chip chip-live">1-Click Live Loop</span>
          </div>
          <h2>Autonomous Agent Financial Loop</h2>
          <p className="text-sm text-t2 mt-1 max-w-3xl leading-relaxed">
            Anomaly detection, sub-second Arc x402 settlement, GenLayer SLA verification, and automated treasury idle yield sweep — replayed from the platform's live ledger, not mock data.
          </p>
        </div>

        {/* Primary CTA Button */}
        <button
          type="button"
          onClick={runSimulation}
          disabled={isRunning}
          className="btn btn-primary cursor-pointer"
        >
          {isRunning ? (
            <>
              <span className="simulation-spinner" />
              Executing Step {activeStep} of 4... ({(elapsedMs / 1000).toFixed(1)}s)
            </>
          ) : isCompleted ? (
            "Re-run Simulation"
          ) : (
            "Run 1-Click Autonomous Loop"
          )}
        </button>
      </div>

      {/* Progress Track & Bar */}
      <div className="simulation-progress-track mt-5">
        <div className={cn("simulation-progress-bar transition-all duration-300", progressBarWidth)} />
      </div>

      {/* 4 Steps Visual Grid */}
      <div className="simulation-steps-grid">
        {steps.map((step) => {
          const isCurrent = activeStep === step.id && isRunning;
          const isPassed = isCompleted || activeStep > step.id;
          const statusChipClass = isPassed
            ? "chip chip-live"
            : isCurrent
            ? "chip chip-info"
            : "chip chip-neutral";

          return (
            <div
              key={step.id}
              className={`simulation-step-card ${isCurrent ? "is-current" : isPassed ? "is-passed" : ""}`}
            >
              {/* Step Top */}
              <div className="simulation-step-head">
                <span className="simulation-step-num">STEP 0{step.id}</span>
                <span className={statusChipClass}>
                  {isPassed ? step.badge : isCurrent ? "PROCESSING" : "PENDING"}
                </span>
              </div>

              {/* Title & Description */}
              <div>
                <h4 className="simulation-step-title">{step.title}</h4>
                <p className="simulation-step-desc">{step.description}</p>
              </div>

              {/* Key Details */}
              <div className="simulation-details-box">
                {Object.entries(step.details).map(([k, v]) => (
                  <div key={k} className="simulation-detail-row">
                    <span className="simulation-detail-key">{k}:</span>
                    <strong className={cn("simulation-detail-val", isPassed ? "text-t1" : "text-t2")}>
                      {v}
                    </strong>
                  </div>
                ))}
              </div>

              {/* Link if available */}
              {step.link && isPassed && (
                <a
                  href={step.link.url}
                  target="_blank"
                  rel="noreferrer"
                  className="tx-link mt-auto pt-1.5 text-[11px]"
                >
                  {step.link.label} &rarr;
                </a>
              )}
            </div>
          );
        })}
      </div>

      {/* Completion Banner */}
      {isCompleted && (
        <div className="simulation-completion-banner">
          <div className="flex flex-col gap-0.5">
            <span className="font-mono text-[11px] font-bold text-qmaGreen uppercase tracking-wider">
              Loop Replayed From Live Platform Data ({(elapsedMs / 1000).toFixed(1)}s)
            </span>
            <small className="text-xs text-t2">
              {payment
                ? `Report ${payment.symbol} acquired for ${payment.amount_usdc} USDC · ${
                    verdict?.genlayer_consensus
                      ? `GenLayer consensus ${verdict.genlayer_consensus}`
                      : "settlement recorded"
                  } · Treasury ${position ? `${position.treasury_liquid_usdc} USDC liquid` : "position pending"}.`
                : "All steps bind to the live payment ledger, Euthyna audit trail and on-chain treasury position."}
            </small>
          </div>

          {(payment?.explorer_url || verdict?.arcscan_url) && (
            <a
              href={payment?.explorer_url || verdict?.arcscan_url || "#"}
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary btn-sm"
            >
              Verify on Arcscan
            </a>
          )}
        </div>
      )}
    </section>
  );
}

export default InteractiveLiveSimulationWidget;
