import { useState } from "react";
import "../../styles/app-demo.css";

interface IntelligenceItem {
  id: string;
  category: "Quant & Markets" | "Deep Research" | "Security" | "IoT";
  tagClass: "tag-quant" | "tag-research" | "tag-audit" | "tag-iot";
  tagLabel: string;
  title: string;
  shortDesc: string;
  provider: string;
  priceUsdc: number;
  timeAgo: string;
  confidenceScore: number;
  impact: "High" | "Medium" | "Critical";
  impactColor: string;
  timeframe: string;
  detectedAt: string;
  whyImportant: string;
  takeaways: string[];
  historicalTable: Array<{ date: string; value: string; impact: string; outcome: string }>;
  chartPoints: Array<{ label: string; v1: number; v2: number }>;
  rawJson: object;
}

const DEMO_ITEMS: IntelligenceItem[] = [
  {
    id: "eth-funding",
    category: "Quant & Markets",
    tagClass: "tag-quant",
    tagLabel: "Quant",
    title: "ETH Funding Rate Spike",
    shortDesc: "Extreme positive funding detected on 8h timeframe across major derivatives exchanges.",
    provider: "FundingMemory",
    priceUsdc: 0.03,
    timeAgo: "2m ago",
    confidenceScore: 89,
    impact: "High",
    impactColor: "#ef4444",
    timeframe: "8h",
    detectedAt: "14:20 UTC",
    whyImportant: "Sustained high positive funding often indicates long position crowding. Potential short-term reversal or liquidation cascade risk.",
    takeaways: [
      "ETH funding rate spiked to 0.145% (top 1% percentile historical distribution).",
      "Long crowding indicates high probability of an impending leverage flush.",
      "Watch for liquidation cascade cluster between $3,280 – $3,420.",
      "Similar historical patterns showed a ~2.3% mean reversion within 6 hours."
    ],
    historicalTable: [
      { date: "2024-05-15", value: "0.142%", impact: "-2.41%", outcome: "Reverted" },
      { date: "2024-03-29", value: "0.158%", impact: "-3.15%", outcome: "Flushed" },
      { date: "2024-01-11", value: "0.139%", impact: "-1.85%", outcome: "Reverted" },
    ],
    chartPoints: [
      { label: "May 10", v1: 0.02, v2: 3100 },
      { label: "May 11", v1: 0.04, v2: 3250 },
      { label: "May 12", v1: 0.09, v2: 3400 },
      { label: "May 13", v1: 0.15, v2: 3580 },
      { label: "May 14", v1: 0.06, v2: 3420 },
      { label: "May 15", v1: 0.01, v2: 3350 },
    ],
    rawJson: {
      provider: "funding_memory",
      symbol: "ETH-USDT",
      metric: "funding_rate_divergence",
      z_score: 3.42,
      percentile: 0.991,
      estimated_liquidation_volume_usdc: 142000000,
      predicted_reversion_prob: 0.887,
      settlement_rail: "arc_testnet_circle_x402"
    }
  },
  {
    id: "quantum-llm",
    category: "Deep Research",
    tagClass: "tag-research",
    tagLabel: "Research",
    title: "Quantum LLM Paper Extract",
    shortDesc: "arXiv: 2405.20481v2 summary & patent-pending quantum tensor attention equations.",
    provider: "ArxivDigest",
    priceUsdc: 0.02,
    timeAgo: "5m ago",
    confidenceScore: 94,
    impact: "Medium",
    impactColor: "#a855f7",
    timeframe: "24h",
    detectedAt: "14:15 UTC",
    whyImportant: "Pre-print contains verified mathematical proofs for sub-quadratic attention scaling on cryogenic superconducting chips.",
    takeaways: [
      "Decomposes multi-head self-attention into unitary quantum gate operations.",
      "Reduces memory footprint from O(N²) to O(N log N) for sequences > 1M tokens.",
      "Benchmark demonstrates 4.2x faster inference latency on QPU emulators.",
      "Identified 3 patent application claims pending approval in EPO/USPTO."
    ],
    historicalTable: [
      { date: "2024-04-02", value: "v1 Draft", impact: "+12% Acc", outcome: "Verified" },
      { date: "2024-05-18", value: "v2 Peer-Rev", impact: "+28% Speed", outcome: "Accepted" },
    ],
    chartPoints: [
      { label: "1K", v1: 10, v2: 12 },
      { label: "10K", v1: 45, v2: 24 },
      { label: "100K", v1: 350, v2: 48 },
      { label: "1M", v1: 2800, v2: 95 },
    ],
    rawJson: {
      provider: "arxiv_digest",
      paper_id: "2405.20481v2",
      authors: ["Dr. H. Vance", "T. Takahashi"],
      domain: "quantum_computing_transformers",
      citation_toll_usdc: 0.02,
      math_proofs_verified: true
    }
  },
  {
    id: "solidity-reentrancy",
    category: "Security",
    tagClass: "tag-audit",
    tagLabel: "Audit",
    title: "Solidity Reentrancy Pattern",
    shortDesc: "Critical read-only reentrancy vector discovered in unhedged DeFi yield vault.",
    provider: "SecGuard",
    priceUsdc: 0.05,
    timeAgo: "12m ago",
    confidenceScore: 98,
    impact: "Critical",
    impactColor: "#ef4444",
    timeframe: "Real-time",
    detectedAt: "14:02 UTC",
    whyImportant: "Smart contract developer and audit agents can immediately patch vulnerable balance accounting routines before public exploit.",
    takeaways: [
      "Vulnerability stems from transient storage balance queries during token transfers.",
      "Affects fork contracts utilizing outdated OpenZeppelin ERC4626 implementation.",
      "Estimated protocol TVL at risk across 2 chains: $8,400,000.",
      "Mitigation: Enforce ReentrancyGuard on view functions calculating LP shares."
    ],
    historicalTable: [
      { date: "2024-02-14", value: "Vyper Bug", impact: "$12M Risk", outcome: "Patched" },
      { date: "2024-05-01", value: "Vault Exploit", impact: "$3.5M Lost", outcome: "Postmortem" },
    ],
    chartPoints: [
      { label: "Block 1", v1: 100, v2: 100 },
      { label: "Block 2", v1: 250, v2: 100 },
      { label: "Block 3", v1: 580, v2: 40 },
    ],
    rawJson: {
      provider: "sec_guard",
      cve_candidate: "2026-QMA-0914",
      vulnerability_type: "read_only_reentrancy",
      severity: "CRITICAL",
      affected_bytecode_hash: "0x89ab...ef12",
      patch_diff_available: true
    }
  },
  {
    id: "btc-oi",
    category: "Quant & Markets",
    tagClass: "tag-quant",
    tagLabel: "Quant",
    title: "BTC OI & Liquidation Map",
    shortDesc: "High risk $420M liquidation cluster detected around $62,400 price band.",
    provider: "OpenInterestHub",
    priceUsdc: 0.02,
    timeAgo: "18m ago",
    confidenceScore: 91,
    impact: "High",
    impactColor: "#f59e0b",
    timeframe: "4h",
    detectedAt: "13:55 UTC",
    whyImportant: "Market makers are heavily skewed; sweep of the $62.4k level could trigger cascading stop triggers.",
    takeaways: [
      "Aggregated Open Interest rose +8.4% while spot CVD declined.",
      "Cumulative liquidation leverage concentrated in $62,100 – $62,600 zone.",
      "Recommended action for trading bots: widen trailing stops to 2.5%."
    ],
    historicalTable: [
      { date: "2024-04-18", value: "Cluster $64k", impact: "-4.2%", outcome: "Swept" },
      { date: "2024-03-05", value: "Cluster $61k", impact: "+5.1%", outcome: "Squeezed" },
    ],
    chartPoints: [
      { label: "00:00", v1: 400, v2: 64200 },
      { label: "04:00", v1: 410, v2: 63800 },
      { label: "08:00", v1: 430, v2: 63100 },
      { label: "12:00", v1: 475, v2: 62450 },
    ],
    rawJson: {
      provider: "open_interest_hub",
      symbol: "BTC-USDT",
      cluster_low: 62100,
      cluster_high: 62600,
      estimated_leverage_usd: 420000000
    }
  },
  {
    id: "ai-patents",
    category: "Deep Research",
    tagClass: "tag-research",
    tagLabel: "Research",
    title: "Patents: AI Chip Cooling Tech",
    shortDesc: "Microfluidic immersion cooling patent claims analysis across 5 new semiconductor filings.",
    provider: "PatentOracle",
    priceUsdc: 0.04,
    timeAgo: "25m ago",
    confidenceScore: 95,
    impact: "Medium",
    impactColor: "#38bdf8",
    timeframe: "7d",
    detectedAt: "13:40 UTC",
    whyImportant: "Identifies patent protection boundaries for next-generation 3nm TPU datacenter cooling solutions.",
    takeaways: [
      "Cross-analyzes TSMC and NVIDIA patent filings on microfluidic channel geometries.",
      "Exposes 2 critical unpatented whitespace claims in dielectric fluid composition.",
      "Accelerates hardware IP clearance for autonomous robotics & datacenter builders."
    ],
    historicalTable: [
      { date: "2024-01-10", value: "USPTO #819", impact: "Prior Art", outcome: "Cleared" },
    ],
    chartPoints: [
      { label: "2021", v1: 12, v2: 20 },
      { label: "2022", v1: 34, v2: 45 },
      { label: "2023", v1: 89, v2: 98 },
      { label: "2024", v1: 184, v2: 240 },
    ],
    rawJson: {
      provider: "patent_oracle",
      patent_ids: ["US2026014891A1", "EP4182910A1"],
      freedom_to_operate_score: 0.84,
      toll_fee_usdc: 0.04
    }
  }
];

interface ActivityRow {
  time: string;
  actor: string;
  item: string;
  cost: string;
  txHash: string;
}

export function AppDemoPage({ onNavigate }: { onNavigate: (route: any) => void }) {
  const [activeCategory, setActiveCategory] = useState<string>("All");
  const [selectedId, setSelectedId] = useState<string>("eth-funding");
  const [unlockedIds, setUnlockedIds] = useState<Set<string>>(new Set(["eth-funding"]));
  const [isUnlocking, setIsUnlocking] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"summary" | "analysis" | "historical" | "json">("summary");

  // Wallet and Agent Dock state
  const [walletBalance, setWalletBalance] = useState<number>(4.95);
  const [sessionSpent, setSessionSpent] = useState<number>(2.15);
  const [activities, setActivities] = useState<ActivityRow[]>([
    { time: "14:20:05", actor: "Bot Purchase", item: "Funding Anomaly Snapshot", cost: "-$0.03", txHash: "0x4a75...8f2c" },
    { time: "14:18:22", actor: "Claude Query", item: "Arxiv Paper Summary", cost: "-$0.02", txHash: "0x812b...7e91" },
    { time: "14:15:41", actor: "Bot Purchase", item: "OI Liquidation Map", cost: "-$0.02", txHash: "0x9c21...3b7a" },
  ]);

  // Copilot mini chat state
  const [copilotInput, setCopilotInput] = useState("");
  const [copilotReply, setCopilotReply] = useState<string | null>(null);

  const selectedItem = DEMO_ITEMS.find((item) => item.id === selectedId) || DEMO_ITEMS[0];
  const isUnlocked = unlockedIds.has(selectedItem.id);

  const filteredItems = DEMO_ITEMS.filter((item) => {
    if (activeCategory === "All") return true;
    return item.category === activeCategory;
  });

  const handleUnlock = () => {
    if (isUnlocked) return;
    setIsUnlocking(true);

    // Simulate ~800ms Circle Gateway settlement
    setTimeout(() => {
      setUnlockedIds((prev) => new Set([...prev, selectedItem.id]));
      setIsUnlocking(false);

      const newBal = Math.max(0, Number((walletBalance - selectedItem.priceUsdc).toFixed(2)));
      const newSpent = Number((sessionSpent + selectedItem.priceUsdc).toFixed(2));
      setWalletBalance(newBal);
      setSessionSpent(newSpent);

      const now = new Date();
      const timeStr = `${now.getHours().toString().padStart(2, "0")}:${now.getMinutes().toString().padStart(2, "0")}:${now.getSeconds().toString().padStart(2, "0")}`;
      const randomHex = Math.random().toString(16).substring(2, 6);

      setActivities((prev) => [
        {
          time: timeStr,
          actor: "Manual Unlock",
          item: selectedItem.title,
          cost: `-$${selectedItem.priceUsdc.toFixed(2)}`,
          txHash: `0x${randomHex}...${randomHex}`
        },
        ...prev
      ]);
    }, 850);
  };

  const handleCopilotSend = () => {
    if (!copilotInput.trim()) return;
    const q = copilotInput.trim();
    setCopilotInput("");
    setCopilotReply(`Evaluating "${selectedItem.title}"... Based on historical analog clustering, this pattern indicates an 84.6% correlation with short-term mean reversion. Suggested bot policy: hedge position with $0.05 budget.`);
  };

  return (
    <div className="app-demo-root">
      {/* Top Switcher Banner */}
      <div className="app-demo-banner">
        <div>
          <strong style={{ color: "#38bdf8" }}>✨ PREVIEW MODE:</strong> Exploring the new <strong>Agent Intelligence Console</strong> design.
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="app-demo-banner-btn" onClick={() => onNavigate("app")}>
            ← Return to Classic /app
          </button>
          <button className="app-demo-banner-btn" onClick={() => onNavigate("connect")}>
            Connect Claude / ChatGPT →
          </button>
        </div>
      </div>

      {/* Top Navbar */}
      <header className="app-demo-nav">
        <div className="app-demo-brand" onClick={() => onNavigate("landing")}>
          <div className="app-demo-logo-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
              <path d="M2 12h20" />
            </svg>
          </div>
          <div>
            <div className="app-demo-brand-name">QMA</div>
            <div className="app-demo-brand-tag">Intelligence Exchange</div>
          </div>
        </div>

        <div className="app-demo-search-wrap">
          <svg className="app-demo-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
          </svg>
          <input
            type="text"
            className="app-demo-search-input"
            placeholder="Search intelligence, providers, topics..."
          />
          <kbd className="app-demo-search-kbd">⌘ K</kbd>
        </div>

        <div className="app-demo-nav-actions">
          <div className="app-demo-network-pill">
            <span className="app-demo-status-dot"></span>
            <span>Arc Testnet</span>
          </div>

          <div className="app-demo-account-pill" onClick={() => onNavigate("profile")}>
            <div className="app-demo-avatar">A</div>
            <span style={{ fontWeight: 600 }}>Agent Wallet</span>
            <span style={{ fontSize: 10, opacity: 0.6 }}>▾</span>
          </div>
        </div>
      </header>

      {/* Main 3-Column Studio Grid */}
      <div className="app-demo-grid">

        {/* ==============================================================
            LEFT COLUMN: INTELLIGENCE FEED
            ============================================================== */}
        <aside className="app-demo-sidebar">
          <div className="app-demo-feed-header">
            <div className="app-demo-feed-title">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2.5">
                <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z" />
              </svg>
              <span>Intelligence Feed</span>
            </div>

            <div className="app-demo-feed-categories">
              {["All", "Quant & Markets", "Deep Research", "Security", "IoT"].map((cat) => (
                <button
                  key={cat}
                  className={`app-demo-cat-pill ${activeCategory === cat ? "active" : ""}`}
                  onClick={() => setActiveCategory(cat)}
                >
                  {cat}
                </button>
              ))}
            </div>

            <div className="app-demo-feed-filter-row">
              <input
                type="text"
                className="app-demo-filter-input"
                placeholder="Filter events, providers..."
              />
              <button className="app-demo-filter-btn" title="Filter options">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
                </svg>
              </button>
            </div>
          </div>

          <div className="app-demo-feed-list">
            {filteredItems.map((item) => (
              <div
                key={item.id}
                className={`app-demo-feed-card ${selectedId === item.id ? "active" : ""}`}
                onClick={() => setSelectedId(item.id)}
              >
                <div className="app-demo-card-top">
                  <span className={`app-demo-card-tag ${item.tagClass}`}>[{item.tagLabel}]</span>
                  <span style={{ fontSize: 10, color: item.impactColor, fontWeight: 700 }}>● {item.impact}</span>
                </div>
                <div className="app-demo-card-title">{item.title}</div>
                <div className="app-demo-card-desc">{item.shortDesc}</div>
                <div className="app-demo-card-footer">
                  <span>{item.provider}</span>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span className="app-demo-card-price">${item.priceUsdc.toFixed(2)}</span>
                    <span>·</span>
                    <span>{item.timeAgo}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="app-demo-sidebar-footer">
            <button className="app-demo-add-feed-btn" onClick={() => onNavigate("marketplace")}>
              <span>+ Add Custom Feed / Provider</span>
            </button>
            <div className="app-demo-nav-links">
              <a href="/docs" onClick={(e) => { e.preventDefault(); onNavigate("docs"); }}>Docs</a>
              <a href="/api/v1/metrics" target="_blank" rel="noreferrer">API</a>
              <a href="/marketplace" onClick={(e) => { e.preventDefault(); onNavigate("marketplace"); }}>Pricing</a>
              <a href="/traction" onClick={(e) => { e.preventDefault(); onNavigate("traction"); }}>Traction</a>
              <span style={{ cursor: "pointer" }}>⚙️</span>
            </div>
          </div>
        </aside>

        {/* ==============================================================
            CENTER COLUMN: INTELLIGENCE CANVAS
            ============================================================== */}
        <main className="app-demo-canvas">
          {/* Top Breadcrumb & Actions */}
          <div className="app-demo-canvas-header">
            <div>
              <button className="app-demo-back-btn" onClick={() => setActiveCategory("All")}>
                ← Back to Feed
              </button>
              <div className="app-demo-canvas-title-row">
                <h1 className="app-demo-canvas-title">{selectedItem.title}</h1>
                <span className={`app-demo-card-tag ${selectedItem.tagClass}`}>[{selectedItem.tagLabel}]</span>
              </div>
              <div className="app-demo-canvas-provider">
                <span>Provider: <strong>{selectedItem.provider}</strong></span>
                <span className="app-demo-verified-badge" title="Verified Creator">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="#38bdf8">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                  </svg>
                </span>
              </div>
            </div>

            <div className="app-demo-header-actions">
              <button className="app-demo-btn-sm" onClick={() => alert("Shareable research permalink copied!")}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" />
                  <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
                </svg>
                <span>Share</span>
              </button>
              <button className="app-demo-btn-sm">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z" />
                </svg>
                <span>Save</span>
              </button>
            </div>
          </div>

          {/* Upper Card: FREE TEASER */}
          <div className="app-demo-teaser-card">
            <div className="app-demo-teaser-badge">⭐ Free Teaser</div>

            <div className="app-demo-teaser-content">
              <div>
                <h2 className="app-demo-teaser-headline">{selectedItem.title} Anomaly</h2>
                <p className="app-demo-teaser-body">{selectedItem.shortDesc}</p>

                <div className="app-demo-metrics-grid">
                  <div className="app-demo-metric-box">
                    <div className="app-demo-metric-label">Confidence Score</div>
                    <div className="app-demo-metric-val">
                      <span>{selectedItem.confidenceScore}%</span>
                      <span style={{ color: "#10b981", fontSize: 11 }}>●</span>
                    </div>
                  </div>
                  <div className="app-demo-metric-box">
                    <div className="app-demo-metric-label">Impact</div>
                    <div className="app-demo-metric-val" style={{ color: selectedItem.impactColor }}>
                      ● {selectedItem.impact}
                    </div>
                  </div>
                  <div className="app-demo-metric-box">
                    <div className="app-demo-metric-label">Timeframe</div>
                    <div className="app-demo-metric-val">{selectedItem.timeframe}</div>
                  </div>
                  <div className="app-demo-metric-box">
                    <div className="app-demo-metric-label">Detected At</div>
                    <div className="app-demo-metric-val" style={{ fontSize: 12 }}>{selectedItem.detectedAt}</div>
                  </div>
                </div>

                <div className="app-demo-teaser-why">
                  <strong>Why is this important?</strong> {selectedItem.whyImportant}
                </div>

                <div className="app-demo-teaser-cta-row">
                  <button
                    className="app-demo-unlock-btn"
                    onClick={handleUnlock}
                    disabled={isUnlocking}
                  >
                    {isUnlocking ? (
                      <span>Settling on Arc (~800ms)...</span>
                    ) : isUnlocked ? (
                      <span>✓ Snapshot Already Unlocked</span>
                    ) : (
                      <>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                        </svg>
                        <span>Unlock Snapshot — ${selectedItem.priceUsdc.toFixed(2)} USDC</span>
                      </>
                    )}
                  </button>

                  <button className="app-demo-simulate-btn" onClick={() => alert("Simulation triggered: Running Monte-Carlo scenario on historical sample.")}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a855f7" strokeWidth="2">
                      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                    </svg>
                    <span>Simulate with AI</span>
                  </button>
                </div>

                <div className="app-demo-protected-hint">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                  <span>Encrypted by QMA · Circle Gateway x402 Micropayment Protected</span>
                </div>
              </div>

              {/* 3D Isometric Chart Graphic */}
              <div style={{ padding: 12, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <svg width="160" height="140" viewBox="0 0 160 140" fill="none">
                  <path d="M80 15 L140 45 L80 75 L20 45 Z" fill="url(#cubeTop)" stroke="#60a5fa" strokeWidth="1.5" />
                  <path d="M20 45 L80 75 L80 115 L20 85 Z" fill="url(#cubeLeft)" stroke="#3b82f6" strokeWidth="1" />
                  <path d="M80 75 L140 45 L140 85 L80 115 Z" fill="url(#cubeRight)" stroke="#2563eb" strokeWidth="1" />
                  <path d="M30 65 Q 80 40 140 90" stroke="#f59e0b" strokeWidth="3" fill="none" strokeLinecap="round" filter="drop-shadow(0 0 6px #f59e0b)" />
                  <defs>
                    <linearGradient id="cubeTop" x1="20" y1="15" x2="140" y2="75" gradientUnits="userSpaceOnUse">
                      <stop stopColor="#38bdf8" stopOpacity="0.4" />
                      <stop offset="1" stopColor="#818cf8" stopOpacity="0.1" />
                    </linearGradient>
                    <linearGradient id="cubeLeft" x1="20" y1="45" x2="80" y2="115" gradientUnits="userSpaceOnUse">
                      <stop stopColor="#1e3a8a" stopOpacity="0.6" />
                      <stop offset="1" stopColor="#0f172a" stopOpacity="0.9" />
                    </linearGradient>
                    <linearGradient id="cubeRight" x1="80" y1="45" x2="140" y2="115" gradientUnits="userSpaceOnUse">
                      <stop stopColor="#2563eb" stopOpacity="0.5" />
                      <stop offset="1" stopColor="#0f172a" stopOpacity="0.9" />
                    </linearGradient>
                  </defs>
                </svg>
              </div>
            </div>
          </div>

          {/* Lower Card: DECRYPTED SNAPSHOT */}
          <div className={`app-demo-decrypted-card ${isUnlocked ? "" : "locked-state"}`}>
            <div className="app-demo-decrypted-header">
              <div className="app-demo-decrypted-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5">
                  <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z" />
                </svg>
                <span>Decrypted Snapshot</span>
                {isUnlocked ? (
                  <span className="app-demo-unlocked-pill">UNLOCKED</span>
                ) : (
                  <span style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600 }}>LOCKED (Pay to decrypt)</span>
                )}
              </div>

              {isUnlocked && (
                <a
                  href="https://testnet.arcscan.app"
                  target="_blank"
                  rel="noreferrer"
                  className="app-demo-tx-link"
                >
                  <span>Tx: 0x4a75...8f2c</span>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" />
                  </svg>
                </a>
              )}
            </div>

            {/* Navigation Tabs */}
            <div className="app-demo-tabs-row">
              {(["summary", "analysis", "historical", "json"] as const).map((tab) => (
                <button
                  key={tab}
                  className={`app-demo-tab-btn ${activeTab === tab ? "active" : ""}`}
                  onClick={() => setActiveTab(tab)}
                >
                  {tab === "summary" && "Executive Summary"}
                  {tab === "analysis" && "Deep Analysis"}
                  {tab === "historical" && "Historical Context"}
                  {tab === "json" && "Raw JSON"}
                </button>
              ))}
            </div>

            {/* Tab 1: Executive Summary */}
            {activeTab === "summary" && (
              <div className="app-demo-details-grid">
                <div>
                  <h4 style={{ margin: "0 0 10px", fontSize: 13, color: "#f1f5f9" }}>Key Takeaways</h4>
                  <div className="app-demo-takeaways-list">
                    {selectedItem.takeaways.map((takeaway, idx) => (
                      <div key={idx} className="app-demo-takeaway-item">
                        <span className="app-demo-check-icon">✓</span>
                        <span>{takeaway}</span>
                      </div>
                    ))}
                  </div>

                  <h4 style={{ margin: "16px 0 8px", fontSize: 13, color: "#f1f5f9" }}>Historical Comparison</h4>
                  <table className="app-demo-mini-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Metric Value</th>
                        <th>Impact (24h)</th>
                        <th>Outcome</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedItem.historicalTable.map((row, idx) => (
                        <tr key={idx}>
                          <td style={{ fontFamily: "monospace" }}>{row.date}</td>
                          <td style={{ fontWeight: 600 }}>{row.value}</td>
                          <td style={{ color: "#f87171" }}>{row.impact}</td>
                          <td><span className="app-demo-badge-green">{row.outcome}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Right Mini Visual */}
                <div style={{ background: "rgba(0,0,0,0.3)", borderRadius: 12, padding: 14, border: "1px solid rgba(255,255,255,0.06)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#94a3b8", marginBottom: 8 }}>
                    <strong>Correlation Chart</strong>
                    <div style={{ display: "flex", gap: 10 }}>
                      <span style={{ color: "#10b981" }}>● Indicator</span>
                      <span style={{ color: "#38bdf8" }}>● Reference</span>
                    </div>
                  </div>

                  {/* SVG Line Chart */}
                  <svg width="100%" height="180" viewBox="0 0 300 180" fill="none">
                    {/* Grid lines */}
                    <line x1="20" y1="30" x2="280" y2="30" stroke="rgba(255,255,255,0.05)" strokeDasharray="3 3" />
                    <line x1="20" y1="80" x2="280" y2="80" stroke="rgba(255,255,255,0.05)" strokeDasharray="3 3" />
                    <line x1="20" y1="130" x2="280" y2="130" stroke="rgba(255,255,255,0.05)" strokeDasharray="3 3" />

                    {/* Line 1 (Green) */}
                    <path
                      d="M 30 140 Q 90 100 150 50 T 270 70"
                      fill="none"
                      stroke="#10b981"
                      strokeWidth="2.5"
                    />
                    {/* Line 2 (Blue) */}
                    <path
                      d="M 30 90 Q 90 120 150 140 T 270 40"
                      fill="none"
                      stroke="#38bdf8"
                      strokeWidth="2"
                      strokeDasharray="4 2"
                    />

                    {/* Point highlight */}
                    <circle cx="270" cy="70" r="5" fill="#10b981" stroke="#fff" strokeWidth="2" />
                    <circle cx="270" cy="40" r="4" fill="#38bdf8" />
                  </svg>

                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#64748b", marginTop: 4 }}>
                    <span>T-24h</span>
                    <span>T-12h</span>
                    <span>T-4h</span>
                    <span style={{ color: "#f1f5f9", fontWeight: 700 }}>Current</span>
                  </div>
                </div>
              </div>
            )}

            {/* Tab 2: Deep Analysis */}
            {activeTab === "analysis" && (
              <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.6 }}>
                <p>
                  <strong>Cross-provider synthesis:</strong> The current event was captured across 4 independent anomaly sensors. The statistical z-score indicates a <strong>3.42 sigma divergence</strong> from the 30-day trailing baseline.
                </p>
                <div style={{ background: "rgba(0,0,0,0.25)", padding: 12, borderRadius: 8, marginTop: 10 }}>
                  <code style={{ fontSize: 12, color: "#38bdf8" }}>
                    Formula: Z = (X_t - μ_30d) / σ_30d = 3.42 (High statistical significance, p &lt; 0.001)
                  </code>
                </div>
              </div>
            )}

            {/* Tab 3: Historical Context */}
            {activeTab === "historical" && (
              <div style={{ fontSize: 13, color: "#cbd5e1" }}>
                <p>Examining 48 matching historical instances dating back to January 2024:</p>
                <ul style={{ paddingLeft: 18, margin: "10px 0" }}>
                  <li>42 instances resulted in prompt mean reversion within 4 to 8 hours.</li>
                  <li>4 instances continued expansion before an aggressive volatility spike.</li>
                  <li>2 instances produced no measurable price impact.</li>
                </ul>
              </div>
            )}

            {/* Tab 4: Raw JSON */}
            {activeTab === "json" && (
              <pre style={{
                background: "rgba(0,0,0,0.4)",
                padding: 14,
                borderRadius: 10,
                fontSize: 12,
                fontFamily: "monospace",
                color: "#93c5fd",
                overflowX: "auto",
                margin: 0
              }}>
                {JSON.stringify(selectedItem.rawJson, null, 2)}
              </pre>
            )}
          </div>
        </main>

        {/* ==============================================================
            RIGHT COLUMN: AGENT DOCK
            ============================================================== */}
        <aside className="app-demo-dock">
          <div className="app-demo-dock-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#818cf8" strokeWidth="2.5">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <span>Agent Dock</span>
          </div>

          {/* Card 1: Agent Wallet */}
          <div className="app-demo-dock-card">
            <div className="app-demo-wallet-header">
              <span className="app-demo-wallet-title">Agent Wallet</span>
              <button className="app-demo-btn-link" onClick={() => onNavigate("profile")}>Manage</button>
            </div>

            <div className="app-demo-balance-row">
              <div>
                <div className="app-demo-balance-val">${walletBalance.toFixed(2)} <span style={{ fontSize: 13, color: "#94a3b8" }}>USDC</span></div>
                <div className="app-demo-balance-chain">
                  <span className="app-demo-status-dot"></span>
                  <span>on Arc Testnet</span>
                </div>
              </div>
              <div className="app-demo-usdc-badge">$</div>
            </div>

            <div className="app-demo-progress-wrap">
              <div className="app-demo-progress-labels">
                <span>Session Spend</span>
                <span>${sessionSpent.toFixed(2)} / $10.00</span>
              </div>
              <div className="app-demo-progress-bar">
                <div
                  className="app-demo-progress-fill"
                  style={{ width: `${Math.min(100, (sessionSpent / 10.0) * 100)}%` }}
                />
              </div>
            </div>

            <div className="app-demo-btn-group-3">
              <button className="app-demo-btn-action" onClick={() => { setWalletBalance((b) => Number((b + 5).toFixed(2))); alert("Deposited $5.00 USDC to Agent Wallet!"); }}>
                <span>+ Deposit</span>
              </button>
              <button className="app-demo-btn-action" onClick={() => alert("Withdraw initiated via Arc Gateway burnIntent.")}>
                <span>↑ Withdraw</span>
              </button>
              <button className="app-demo-btn-action" onClick={() => onNavigate("profile")}>
                <span>History</span>
              </button>
            </div>
          </div>

          {/* Card 2: MCP Connectors */}
          <div className="app-demo-dock-card">
            <div className="app-demo-wallet-header">
              <span className="app-demo-wallet-title">MCP Connectors</span>
              <button className="app-demo-btn-link" onClick={() => onNavigate("connect")}>Configure</button>
            </div>

            <div className="app-demo-connector-row">
              <div className="app-demo-connector-name">
                <span style={{ fontSize: 13 }}>🤖</span>
                <span>Claude (Anthropic)</span>
              </div>
              <span className="app-demo-connector-status">
                <span className="app-demo-status-dot"></span>
                <span>Connected</span>
              </span>
            </div>

            <div className="app-demo-connector-row">
              <div className="app-demo-connector-name">
                <span style={{ fontSize: 13 }}>⚡</span>
                <span>ChatGPT (OpenAI)</span>
              </div>
              <span className="app-demo-connector-status">
                <span className="app-demo-status-dot"></span>
                <span>Connected</span>
              </span>
            </div>
          </div>

          {/* Card 3: Live On-chain Activity */}
          <div className="app-demo-dock-card">
            <div className="app-demo-wallet-header">
              <span className="app-demo-wallet-title">Live On-chain Activity</span>
              <a href="https://testnet.arcscan.app" target="_blank" rel="noreferrer" className="app-demo-btn-link">View All</a>
            </div>

            <div>
              {activities.map((act, idx) => (
                <div key={idx} className="app-demo-activity-item">
                  <div className="app-demo-act-top">
                    <span>{act.time} · {act.actor}</span>
                    <span style={{ fontSize: 10, color: "#10b981" }}>Arc</span>
                  </div>
                  <div className="app-demo-act-desc">
                    <span>{act.item}</span>
                    <span className="app-demo-act-amount">{act.cost}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Card 4: QMA Copilot (BETA) */}
          <div className="app-demo-copilot-card">
            <div className="app-demo-copilot-header">
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 14 }}>👾</span>
                <strong style={{ fontSize: 12, color: "#fff" }}>QMA Copilot</strong>
                <span style={{ fontSize: 9, background: "#7c3aed", color: "#fff", padding: "1px 5px", borderRadius: 4, fontWeight: 700 }}>BETA</span>
              </div>
            </div>

            <p style={{ fontSize: 11, color: "#cbd5e1", margin: "0 0 10px" }}>
              Ask anything about <em>{selectedItem.title}</em>...
            </p>

            {copilotReply && (
              <div style={{
                background: "rgba(0,0,0,0.35)",
                padding: "8px 10px",
                borderRadius: 8,
                fontSize: 11,
                color: "#e2e8f0",
                marginBottom: 8,
                borderLeft: "2px solid #a855f7"
              }}>
                {copilotReply}
              </div>
            )}

            <div className="app-demo-copilot-input-wrap">
              <input
                type="text"
                className="app-demo-copilot-input"
                placeholder="Ask QMA Copilot..."
                value={copilotInput}
                onChange={(e) => setCopilotInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleCopilotSend(); }}
              />
              <button className="app-demo-copilot-send" onClick={handleCopilotSend} title="Send prompt">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </div>
          </div>
        </aside>

      </div>
    </div>
  );
}
