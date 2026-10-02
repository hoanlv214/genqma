import React, { useState, useEffect, useCallback, useRef } from "react";
import type { QmaRoute } from "@/app/routes";
import { GlobalHeader } from "@/components/layout/GlobalHeader";
import { WalletAppKitModal } from "@/components/modals/WalletAppKitModal";
import { useWalletStore } from "@/state/walletStore";
import { getWalletProvider, ensureArcTestnet, shortAddress } from "@/services/wallet";
import {
  SUPPORTED_CCTP_CHAINS,
  executeCctpBridgeToArc,
  executeStableFxSwap,
  getStableFxQuote,
  getArcErc20Balance,
  ARC_TOKENS,
  type StableFxQuote,
  type BridgeProgressEvent,
} from "@/services/circleAppKit";
import "./SwapPage.css";
import { ARC_CHAIN, IS_TESTNET } from "@/config/network";
import { apiUrl } from "@/services/api";
import type { SwapProps } from "./Swap.types";

type TreasurySubTab = "cctp_transfer" | "stablefx";

// SVG Logos for Chains matching exact Circle brand specs
function BaseLogo({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="11" fill="#0052FF" />
      <circle cx="12" cy="12" r="5" fill="#FFFFFF" />
    </svg>
  );
}

function ArbitrumLogo({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 2L2 8.5v7L12 22l10-6.5v-7L12 2z" fill="#28A0F0" />
      <path d="M12 6.5l-5.5 3.5v4l3-2v-2l2.5-1.5 2.5 1.5v2l3 2v-4L12 6.5z" fill="#FFFFFF" />
    </svg>
  );
}

function EthereumLogo({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 2L5.5 13.5l6.5 4 6.5-4L12 2z" fill="#627EEA" />
      <path d="M12 2L5.5 13.5l6.5 4v-17.5z" fill="#8A92B2" />
      <path d="M12 17.5l-6.5-4 6.5 10.5 6.5-10.5-6.5 4z" fill="#627EEA" />
      <path d="M12 17.5v10.5l6.5-10.5-6.5 0z" fill="#454A75" />
    </svg>
  );
}

function ArcLogo({ size = 18 }: { size?: number }) {
  return (
    <img
      src="/arc-logo.svg"
      alt="Arc"
      className="swap-token-img"
      width={size}
      height={size}
    />
  );
}

function UsdcLogo({ size = 18 }: { size?: number }) {
  return (
    <img
      src="/usdc-logo.svg"
      alt="USDC"
      className="swap-token-img"
      width={size}
      height={size}
    />
  );
}

const NETWORKS_LIST = [
  { id: "base_sepolia", name: IS_TESTNET ? "Base Sepolia" : "Base", logo: <BaseLogo size={16} />, domain: 6, latency: "12s" },
  { id: "arbitrum_sepolia", name: IS_TESTNET ? "Arbitrum Sepolia" : "Arbitrum One", logo: <ArbitrumLogo size={16} />, domain: 3, latency: "18s" },
  { id: "ethereum_sepolia", name: IS_TESTNET ? "Ethereum Sepolia" : "Ethereum", logo: <EthereumLogo size={16} />, domain: 0, latency: "22s" },
  { id: "arc", name: ARC_CHAIN.name, logo: <ArcLogo size={16} />, domain: ARC_CHAIN.cctpDomain, latency: "<1s" },
];

const RECENT_SETTLEMENTS = [
  { id: "1", amount: "+50.00 USDC", route: "Base Sepolia → Ethereum Sepolia", timeAgo: "2m ago" },
  { id: "2", amount: "+12.50 USDC", route: "Arbitrum Sepolia → Arc", timeAgo: "8m ago" },
  { id: "3", amount: "+256.00 USDC", route: "Base Sepolia → Arbitrum Sepolia", timeAgo: "15m ago" },
  { id: "4", amount: "+75.00 USDC", route: "Ethereum Sepolia → Arc", timeAgo: "32m ago" },
];

export function SwapPage({ onNavigate }: SwapProps) {
  const { address: wallet, setAddress, disconnect } = useWalletStore();
  const [showAppKitModal, setShowAppKitModal] = useState(false);

  // Sub-tab inside Treasury Terminal: CCTP Transfer vs Arc StableFX
  const [activeTab, setActiveTab] = useState<TreasurySubTab>("cctp_transfer");

  // Chain state
  const [currentChainId, setCurrentChainId] = useState<number | null>(null);
  const [switchingNetwork, setSwitchingNetwork] = useState(false);

  // Cross-Chain Transfer State (Wormhole / LayerZero style dropdown selectors)
  const [originChain, setOriginChain] = useState("base_sepolia");
  const [destinationChain, setDestinationChain] = useState("arc");
  const [originDropdownOpen, setOriginDropdownOpen] = useState(false);
  const [destDropdownOpen, setDestDropdownOpen] = useState(false);
  const originDropdownRef = useRef<HTMLDivElement>(null);
  const destDropdownRef = useRef<HTMLDivElement>(null);
  const [transferAmount, setTransferAmount] = useState("5.0");
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [transferLoading, setTransferLoading] = useState(false);
  const [transferStep, setTransferStep] = useState(0); // 0: Idle, 1: Lock, 2: Attest, 3: Mint, 4: Settle
  const [transferMessage, setTransferMessage] = useState("");
  const [transferTxHash, setTransferTxHash] = useState("");
  const [transferExplorerUrl, setTransferExplorerUrl] = useState("");
  const [transferError, setTransferError] = useState("");
  const [copiedTx, setCopiedTx] = useState(false);

  // Close chain dropdowns when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (originDropdownRef.current && !originDropdownRef.current.contains(event.target as Node)) {
        setOriginDropdownOpen(false);
      }
      if (destDropdownRef.current && !destDropdownRef.current.contains(event.target as Node)) {
        setDestDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // FX Conversion State (Institutional StableFX RFQ Desk)
  const [fxFromToken, setFxFromToken] = useState<"USDC" | "EURC">("EURC");
  const [fxAmount, setFxAmount] = useState("10.0");
  const [fxLoading, setFxLoading] = useState(false);
  const [fxMessage, setFxMessage] = useState("");
  const [fxTxHash, setFxTxHash] = useState("");
  const [fxSettlementTxHash, setFxSettlementTxHash] = useState("");
  const [fxSettlementExplorerUrl, setFxSettlementExplorerUrl] = useState("");
  const [fxError, setFxError] = useState("");
  const [eurcBalance, setEurcBalance] = useState("0.00");
  const [usdcBalance, setUsdcBalance] = useState("0.00");
  const [fxQuote, setFxQuote] = useState<StableFxQuote | null>(null);
  const [fxQuoteLoading, setFxQuoteLoading] = useState(false);
  const [quoteSecondsLeft, setQuoteSecondsLeft] = useState(24);
  const [settlementRows, setSettlementRows] = useState(RECENT_SETTLEMENTS);

  const targetArcChainId = ARC_CHAIN.chainId;
  const isArcChain = currentChainId === targetArcChainId;

  const handleCopyTx = (tx: string) => {
    if (!tx) return;
    navigator.clipboard?.writeText(tx);
    setCopiedTx(true);
    setTimeout(() => setCopiedTx(false), 2000);
  };

  // Poll live recent settlements from Euthyna audit trail
  useEffect(() => {
    fetch(apiUrl("/api/v1/treasury/audit/euthyna?limit=5"))
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          const mapped = data.map((item: any, idx: number) => {
            const timeAgo = item.timestamp
              ? new Date(item.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
              : `${(idx + 1) * 3}m ago`;
            const actionLabel =
              item.action === "IDLE_SWEEP"
                ? "Treasury → USYC Vault"
                : item.action === "JIT_REDEMPTION"
                ? "USYC Vault → Liquid USDC"
                : item.action === "STABLEFX_SWAP"
                ? "USDC ↔ EURC StableFX"
                : `${item.action} on Arc`;
            return {
              id: item.record_id || String(idx),
              amount: `${item.amount_usdc >= 0 ? "+" : ""}${Number(item.amount_usdc || 0).toFixed(2)} USDC`,
              route: actionLabel,
              timeAgo,
              txHash: item.tx_hash,
              arcscanUrl: item.arcscan_url,
            };
          });
          setSettlementRows(mapped);
        }
      })
      .catch(() => {});
  }, [transferTxHash, fxTxHash]);

  // Listen to chain changes
  useEffect(() => {
    const provider = getWalletProvider();
    if (!provider) return;

    provider.request<string>({ method: "eth_chainId" }).then((hexId) => {
      if (hexId) setCurrentChainId(parseInt(hexId, 16));
    }).catch(() => { });

    const handleChainChanged = (hexId: any) => {
      if (typeof hexId === "string") setCurrentChainId(parseInt(hexId, 16));
    };

    provider.on?.("chainChanged", handleChainChanged as any);
    return () => {
      provider.removeListener?.("chainChanged", handleChainChanged as any);
    };
  }, [wallet]);

  // Fetch balances on Arc
  const fetchBalances = useCallback(async () => {
    if (!wallet) return;
    const provider = getWalletProvider();
    if (!provider) return;
    try {
      const [eurcBal, usdcBal] = await Promise.all([
        getArcErc20Balance(ARC_TOKENS.EURC.address, wallet, provider),
        getArcErc20Balance(ARC_TOKENS.USDC.address, wallet, provider),
      ]);
      setEurcBalance(eurcBal);
      setUsdcBalance(usdcBal);
    } catch {
      // Ignored
    }
  }, [wallet]);

  useEffect(() => {
    fetchBalances();
    const timer = setInterval(fetchBalances, 12000);
    return () => clearInterval(timer);
  }, [fetchBalances]);

  // RFQ Quote fetcher
  const fetchQuote = useCallback(async () => {
    const toToken = fxFromToken === "EURC" ? "USDC" : "EURC";
    const parsedAmt = parseFloat(fxAmount);
    if (isNaN(parsedAmt) || parsedAmt <= 0) {
      setFxQuote(null);
      return;
    }

    setFxQuoteLoading(true);
    try {
      const quote = await getStableFxQuote(fxFromToken, toToken, parsedAmt);
      setFxQuote(quote);
      setQuoteSecondsLeft(24);
    } catch {
      // Fallback quote
    } finally {
      setFxQuoteLoading(false);
    }
  }, [fxFromToken, fxAmount]);

  useEffect(() => {
    const debounceTimer = setTimeout(fetchQuote, 300);
    return () => clearTimeout(debounceTimer);
  }, [fetchQuote]);

  useEffect(() => {
    if (!fxQuote) return;
    const interval = setInterval(() => {
      setQuoteSecondsLeft((prev) => {
        if (prev <= 1) {
          fetchQuote();
          return 24;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [fxQuote, fetchQuote]);

  // Switch to Arc
  const handleSwitchToArc = async () => {
    const provider = getWalletProvider();
    if (!provider) return;
    setSwitchingNetwork(true);
    try {
      await ensureArcTestnet(provider);
      const hexId = await provider.request<string>({ method: "eth_chainId" });
      if (hexId) setCurrentChainId(parseInt(hexId, 16));
    } catch {
      // Ignored
    } finally {
      setSwitchingNetwork(false);
    }
  };

  // Open review modal or connect wallet
  const handleContinueToReview = () => {
    if (!wallet) {
      setShowAppKitModal(true);
      return;
    }
    const amt = parseFloat(transferAmount);
    if (isNaN(amt) || amt <= 0) {
      setTransferError("Please enter a valid transfer amount.");
      return;
    }
    setTransferError("");
    setShowReviewModal(true);
  };

  // Execute CCTP Transfer
  const handleExecuteTransfer = async () => {
    setShowReviewModal(false);
    const provider = getWalletProvider();
    if (!provider) {
      setTransferError("No Web3 provider detected.");
      return;
    }

    setTransferLoading(true);
    setTransferError("");
    setTransferMessage("Locking USDC on source chain...");
    setTransferStep(1); // Lock on Origin
    setTransferTxHash("");
    setTransferExplorerUrl("");

    try {
      const res = await executeCctpBridgeToArc({
        sourceChainId: originChain === "arc" ? "base_sepolia" : originChain,
        amountUsdc: transferAmount,
        recipientAddress: wallet,
        provider,
        onProgress: (evt: BridgeProgressEvent) => {
          setTransferMessage(evt.message);
          if (evt.step === "burning") setTransferStep(1);
          if (evt.step === "fetching_attestation") setTransferStep(2);
          if (evt.step === "minting") setTransferStep(3);
          if (evt.step === "completed") setTransferStep(4);
          if (evt.txHash) setTransferTxHash(evt.txHash);
          if (evt.explorerUrl) setTransferExplorerUrl(evt.explorerUrl);
          if (evt.error) setTransferError(evt.error);
        },
      });

      if (!res.success) {
        setTransferError(res.error || "Transfer failed.");
      } else {
        setTransferStep(4);
        setTransferMessage("CCTP V2 Transfer settled successfully.");
        await fetchBalances();
      }
    } catch (err: any) {
      setTransferError(err?.message || "Transfer failed.");
    } finally {
      setTransferLoading(false);
    }
  };

  // Execute FX Swap
  const handleExecuteFx = async () => {
    if (!wallet) {
      setShowAppKitModal(true);
      return;
    }
    const provider = getWalletProvider();
    if (!provider) return;

    setFxLoading(true);
    setFxError("");
    setFxMessage("Initializing Arc StableFX atomic settlement...");
    setFxTxHash("");
    setFxSettlementTxHash("");

    try {
      await ensureArcTestnet(provider);
      const toToken = fxFromToken === "EURC" ? "USDC" : "EURC";

      const res = await executeStableFxSwap({
        fromToken: fxFromToken,
        toToken,
        amount: fxAmount,
        address: wallet,
        provider,
        quoteId: fxQuote?.quote_id,
        settlementCounterparty: fxQuote?.settlement_counterparty,
        onProgress: (_step, msg) => {
          setFxMessage(msg);
        },
      });

      if (!res.success) {
        setFxError(res.error || "StableFX settlement failed.");
      } else {
        setFxTxHash(res.userTxHash || "");
        setFxSettlementTxHash(res.settlementTxHash || "");
        setFxSettlementExplorerUrl(res.settlementExplorerUrl || "");
        setFxMessage(`Successfully settled ${fxAmount} ${fxFromToken} to ${toToken}!`);
        await fetchBalances();
      }
    } catch (err: any) {
      setFxError(err?.message || "Execution encountered an error.");
    } finally {
      setFxLoading(false);
    }
  };

  const toToken = fxFromToken === "EURC" ? "USDC" : "EURC";
  const currentPayBalance = fxFromToken === "EURC" ? eurcBalance : usdcBalance;
  const currentReceiveBalance = toToken === "EURC" ? eurcBalance : usdcBalance;
  const estOutput = fxQuote
    ? fxQuote.to_amount.toFixed(4)
    : (
      parseFloat(fxAmount) > 0
        ? (fxFromToken === "USDC" ? (parseFloat(fxAmount) * 0.9212).toFixed(4) : (parseFloat(fxAmount) / 0.9212).toFixed(4))
        : "0.00"
    );

  const originNetObj = NETWORKS_LIST.find((n) => n.id === originChain) || NETWORKS_LIST[0];
  const destNetObj = NETWORKS_LIST.find((n) => n.id === destinationChain) || NETWORKS_LIST[3] || NETWORKS_LIST[0];

  return (
    <div className="swap-body">
      {/* Global Header */}
      <GlobalHeader
        activePage="swap"
        onNavigate={onNavigate}
        walletAddress={wallet}
        onConnect={() => setShowAppKitModal(true)}
        onDisconnect={disconnect}
      />

      <main className="swap-page">
        <div className="swap-container">
          {/* Calm Header Area */}
          <div className="swap-header-area">
            <div className="swap-header-meta">
              <span className="eyebrow">
                <span className="eyebrow-dot" />
                Treasury &amp; Liquidity
              </span>
              <span className="chip chip-live">
                {ARC_CHAIN.name} • CCTP V2
              </span>
            </div>
            <h1 className="swap-page-title">Money Movement &amp; Liquidity</h1>
            <p className="swap-page-desc">
              Bridge native USDC across EVM chains via Circle CCTP V2, or exchange USDC and EURC on Arc with sub-second finality.
            </p>
          </div>

          {/* Two-Column Grid */}
          <div className="swap-grid">
            {/* Left 65%: Main Action Cards */}
            <div className="swap-main-col">
              {/* Segmented Mode Navigation */}
              <div className="swap-tabs-nav" role="tablist" aria-label="Treasury modes">
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "cctp_transfer"}
                  className={`swap-tab-btn ${activeTab === "cctp_transfer" ? "active" : ""}`}
                  onClick={() => setActiveTab("cctp_transfer")}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M7 16V4m0 0L3 8m4-4l4 4" />
                    <path d="M17 8v12m0 0l4-4m-4 4l-4-4" />
                  </svg>
                  <span>Cross-Chain USDC Transfer</span>
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "stablefx"}
                  className={`swap-tab-btn ${activeTab === "stablefx" ? "active" : ""}`}
                  onClick={() => setActiveTab("stablefx")}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 6v12" />
                    <path d="M8 10h8" />
                  </svg>
                  <span>Arc StableFX (EURC ↔ USDC)</span>
                </button>
              </div>

              {activeTab === "cctp_transfer" ? (
                <>
                  {/* CARD 1: Cross-Chain USDC Transfer */}
                  <div className="swap-card">
                    <div className="swap-card-header">
                      <div className="swap-card-header-left">
                        <div className="swap-card-icon-wrap">
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                            <path d="M7 16V4m0 0L3 8m4-4l4 4" />
                            <path d="M17 8v12m0 0l4-4m-4 4l-4-4" />
                          </svg>
                        </div>
                        <div>
                          <h2 className="swap-card-title">Cross-Chain USDC Transfer</h2>
                          <p className="swap-card-subtitle">Bridge native USDC across supported networks using CCTP V2 Iris attestation.</p>
                        </div>
                      </div>
                      <span className="chip chip-info">CCTP V2</span>
                    </div>

                    {/* Transfer Box */}
                    <div className="swap-transfer-box">
                      {/* Source Section */}
                      <div className="swap-field-group">
                        <div className="swap-field-meta">
                          <span>Source Network</span>
                          <span className="swap-balance-row">
                            Available:{" "}
                            <button
                              type="button"
                              className="swap-balance-trigger"
                              onClick={() => {
                                const b = parseFloat(usdcBalance || "0");
                                if (b > 0) setTransferAmount(usdcBalance);
                              }}
                              title="Click to use MAX balance"
                            >
                              {usdcBalance} USDC
                            </button>
                          </span>
                        </div>

                        <div className="swap-field-interactive">
                          {/* Chain Dropdown Anchor */}
                          <div className="chain-dropdown-anchor" ref={originDropdownRef}>
                            <button
                              type="button"
                              className="chain-select-btn"
                              aria-haspopup="true"
                              aria-expanded={originDropdownOpen}
                              onClick={() => {
                                setOriginDropdownOpen(!originDropdownOpen);
                                setDestDropdownOpen(false);
                              }}
                            >
                              <div className="chain-btn-logo">{originNetObj.logo}</div>
                              <div className="chain-btn-text">
                                <span className="chain-btn-name">{originNetObj.name}</span>
                                <span className="chain-btn-badge">Testnet</span>
                              </div>
                              <span className="chain-btn-caret">▾</span>
                            </button>

                            {originDropdownOpen && (
                              <div className="chain-dropdown-menu">
                                <div className="dropdown-menu-header">Select Source Chain</div>
                                <div className="dropdown-menu-list">
                                  {NETWORKS_LIST.map((net) => {
                                    const isSelected = originChain === net.id;
                                    return (
                                      <button
                                        key={`src-${net.id}`}
                                        type="button"
                                        className={`dropdown-chain-item ${isSelected ? "selected" : ""}`}
                                        onClick={() => {
                                          setOriginChain(net.id);
                                          if (destinationChain === net.id) {
                                            setDestinationChain(net.id === "arc" ? "ethereum_sepolia" : "arc");
                                          }
                                          setOriginDropdownOpen(false);
                                        }}
                                      >
                                        <div className="dropdown-chain-left">
                                          <div className="dropdown-chain-logo">{net.logo}</div>
                                          <div className="dropdown-chain-info">
                                            <span className="dropdown-chain-title">{net.name}</span>
                                            <span className="dropdown-chain-sub">Domain {net.domain} • {net.latency}</span>
                                          </div>
                                        </div>
                                        {isSelected && <span className="dropdown-chain-check">✓</span>}
                                      </button>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Amount Input */}
                          <div className="swap-amount-input-box">
                            <input
                              type="number"
                              className="swap-big-input tabular-nums"
                              value={transferAmount}
                              onChange={(e) => setTransferAmount(e.target.value)}
                              placeholder="0.0"
                              step="any"
                              min="0.01"
                              aria-label="Transfer amount in USDC"
                            />
                            <div className="swap-token-badge">
                              <UsdcLogo size={18} />
                              <span>USDC</span>
                            </div>
                          </div>
                        </div>

                        {/* Footer row with Presets */}
                        <div className="swap-field-footer">
                          <span className="swap-approx-val">
                            ≈ ${parseFloat(transferAmount || "0").toFixed(2)} USD
                          </span>
                          <div className="amount-presets-row">
                            <button
                              type="button"
                              className="preset-btn"
                              onClick={() => {
                                const b = parseFloat(usdcBalance || "0");
                                if (b > 0) setTransferAmount((b * 0.25).toFixed(2));
                              }}
                            >
                              25%
                            </button>
                            <button
                              type="button"
                              className="preset-btn"
                              onClick={() => {
                                const b = parseFloat(usdcBalance || "0");
                                if (b > 0) setTransferAmount((b * 0.5).toFixed(2));
                              }}
                            >
                              50%
                            </button>
                            <button
                              type="button"
                              className="preset-btn"
                              onClick={() => {
                                const b = parseFloat(usdcBalance || "0");
                                if (b > 0) setTransferAmount(b.toString());
                              }}
                            >
                              MAX
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Direction Switch Divider */}
                      <div className="swap-switch-divider">
                        <div className="swap-divider-line" />
                        <button
                          type="button"
                          className="swap-switch-btn"
                          aria-label="Switch source and destination chains"
                          onClick={() => {
                            const prevOrigin = originChain;
                            setOriginChain(destinationChain);
                            setDestinationChain(prevOrigin);
                          }}
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M7 16V4m0 0L3 8m4-4l4 4" />
                            <path d="M17 8v12m0 0l4-4m-4 4l-4-4" />
                          </svg>
                        </button>
                        <div className="swap-divider-line" />
                      </div>

                      {/* Destination Section */}
                      <div className="swap-field-group">
                        <div className="swap-field-meta">
                          <span>Destination Network</span>
                          <span className="chip chip-live">1:1 Native USDC</span>
                        </div>

                        <div className="swap-field-interactive">
                          {/* Dest Chain Dropdown Anchor */}
                          <div className="chain-dropdown-anchor" ref={destDropdownRef}>
                            <button
                              type="button"
                              className="chain-select-btn"
                              aria-haspopup="true"
                              aria-expanded={destDropdownOpen}
                              onClick={() => {
                                setDestDropdownOpen(!destDropdownOpen);
                                setOriginDropdownOpen(false);
                              }}
                            >
                              <div className="chain-btn-logo">{destNetObj.logo}</div>
                              <div className="chain-btn-text">
                                <span className="chain-btn-name">{destNetObj.name}</span>
                                <span className="chain-btn-badge">Testnet</span>
                              </div>
                              <span className="chain-btn-caret">▾</span>
                            </button>

                            {destDropdownOpen && (
                              <div className="chain-dropdown-menu">
                                <div className="dropdown-menu-header">Select Destination Chain</div>
                                <div className="dropdown-menu-list">
                                  {NETWORKS_LIST.map((net) => {
                                    const isSelected = destinationChain === net.id;
                                    return (
                                      <button
                                        key={`dest-${net.id}`}
                                        type="button"
                                        className={`dropdown-chain-item ${isSelected ? "selected" : ""}`}
                                        onClick={() => {
                                          setDestinationChain(net.id);
                                          if (originChain === net.id) {
                                            setOriginChain(net.id === "arc" ? "base_sepolia" : "arc");
                                          }
                                          setDestDropdownOpen(false);
                                        }}
                                      >
                                        <div className="dropdown-chain-left">
                                          <div className="dropdown-chain-logo">{net.logo}</div>
                                          <div className="dropdown-chain-info">
                                            <span className="dropdown-chain-title">{net.name}</span>
                                            <span className="dropdown-chain-sub">Domain {net.domain} • {net.latency}</span>
                                          </div>
                                        </div>
                                        {isSelected && <span className="dropdown-chain-check">✓</span>}
                                      </button>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Readonly Output */}
                          <div className="swap-amount-input-box">
                            <div className="swap-big-output tabular-nums">
                              {transferAmount && parseFloat(transferAmount) > 0 ? parseFloat(transferAmount).toFixed(2) : "0.00"}
                            </div>
                            <div className="swap-token-badge">
                              <UsdcLogo size={18} />
                              <span>USDC</span>
                            </div>
                          </div>
                        </div>

                        <div className="swap-field-footer">
                          <span>Zero slippage (Circle Iris Burn &amp; Mint)</span>
                          <span className="spec-value speed">Est. &lt; 60s finality</span>
                        </div>
                      </div>
                    </div>

                    {/* Route & Protocol Specs */}
                    <div className="bridge-specs-card">
                      <div className="bridge-spec-item">
                        <span className="spec-label">Route Path</span>
                        <span className="spec-value">
                          {originNetObj.name} <span className="spec-arrow">→</span> {destNetObj.name}
                        </span>
                      </div>
                      <div className="bridge-spec-item">
                        <span className="spec-label">Protocol</span>
                        <span className="spec-value highlight">Circle CCTP V2 (Iris Attestation)</span>
                      </div>
                      <div className="bridge-spec-item">
                        <span className="spec-label">Transfer Speed</span>
                        <span className="spec-value speed">&lt; 60 seconds</span>
                      </div>
                      <div className="bridge-spec-item">
                        <span className="spec-label">Gas &amp; Network Fee</span>
                        <span className="spec-value free">0.00 USDC (Gas-Abstracted)</span>
                      </div>
                    </div>

                    {/* Dominant Primary Action CTA */}
                    {!wallet ? (
                      <button
                        type="button"
                        className="btn btn-primary btn-lg swap-cta-btn"
                        onClick={() => setShowAppKitModal(true)}
                      >
                        Connect Wallet to Transfer →
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-primary btn-lg swap-cta-btn"
                        onClick={handleContinueToReview}
                        disabled={transferLoading || !transferAmount || parseFloat(transferAmount) <= 0}
                      >
                        {transferLoading ? "Broadcasting CCTP Transfer..." : "Review Transfer →"}
                      </button>
                    )}

                    {/* Status Feedback Banner */}
                    {(transferMessage || transferError || transferTxHash) && (
                      <div className={`swap-feedback-banner ${transferError ? "error" : "success"}`} role={transferError ? "alert" : "status"}>
                        <div className="feedback-icon">{transferError ? "✕" : "✓"}</div>
                        <div className="feedback-content">
                          <div className="feedback-title">{transferError ? "Transfer Issue" : "Status Update"}</div>
                          <p className="feedback-desc">{transferError || transferMessage}</p>
                          {transferExplorerUrl && (
                            <div className="feedback-links">
                              <a
                                href={transferExplorerUrl}
                                target="_blank"
                                rel="noreferrer"
                                className="feedback-link"
                              >
                                View on Explorer ↗
                              </a>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* CARD 2: Execution Pipeline (Status Timeline) */}
                  <div className="pipeline-card">
                    <div className="pipeline-header">
                      <div className="pipeline-header-title">
                        <div className="pipeline-badge-icon">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                          </svg>
                        </div>
                        <div>
                          <h3 className="pipeline-title">Execution Pipeline</h3>
                          <p className="pipeline-subtitle">Live CCTP V2 Iris attestation and native mint steps</p>
                        </div>
                      </div>
                      <div>
                        {transferLoading && <span className="chip chip-pending">Processing</span>}
                        {!transferLoading && transferStep === 4 && <span className="chip chip-live">Settled</span>}
                        {!transferLoading && transferStep === 0 && <span className="chip chip-neutral">Idle</span>}
                      </div>
                    </div>

                    <div className="pipeline-timeline">
                      {/* Step 1: Lock on Origin */}
                      <div className={`timeline-step ${transferStep > 1 ? "completed" : transferStep === 1 ? (transferError ? "error" : "active") : ""}`}>
                        <div className="timeline-rail">
                          <div className="timeline-node">{transferStep > 1 ? "✓" : "1"}</div>
                          <div className="timeline-connector" />
                        </div>
                        <div className="timeline-content">
                          <div className="timeline-row">
                            <span className="timeline-step-name">Lock on Origin</span>
                            {transferStep > 1 ? (
                              <span className="chip chip-live">Confirmed</span>
                            ) : transferStep === 1 ? (
                              transferError ? <span className="chip chip-error">Failed</span> : <span className="chip chip-pending">In Progress</span>
                            ) : (
                              <span className="chip chip-neutral">Pending</span>
                            )}
                          </div>
                          <p className="timeline-step-detail">USDC locked and burned via Iris contract on origin network</p>
                          {transferStep === 1 && transferMessage && (
                            <div className="timeline-live-msg">{transferMessage}</div>
                          )}
                          {transferTxHash && (
                            <div className="timeline-tx-block">
                              <span className="timeline-tx-label">Tx:</span>
                              <code className="timeline-tx-code" title={transferTxHash}>{shortAddress(transferTxHash)}</code>
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm timeline-copy-btn"
                                onClick={() => handleCopyTx(transferTxHash)}
                                title="Copy transaction hash"
                              >
                                {copiedTx ? "Copied" : "Copy"}
                              </button>
                              {transferExplorerUrl && (
                                <a href={transferExplorerUrl} target="_blank" rel="noreferrer" className="timeline-link">
                                  Explorer ↗
                                </a>
                              )}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Step 2: Circle Iris Attestation */}
                      <div className={`timeline-step ${transferStep > 2 ? "completed" : transferStep === 2 ? (transferError ? "error" : "active") : ""}`}>
                        <div className="timeline-rail">
                          <div className="timeline-node">{transferStep > 2 ? "✓" : "2"}</div>
                          <div className="timeline-connector" />
                        </div>
                        <div className="timeline-content">
                          <div className="timeline-row">
                            <span className="timeline-step-name">Circle Iris Attestation</span>
                            {transferStep > 2 ? (
                              <span className="chip chip-live">Attested</span>
                            ) : transferStep === 2 ? (
                              transferError ? <span className="chip chip-error">Failed</span> : <span className="chip chip-pending">Verifying</span>
                            ) : (
                              <span className="chip chip-neutral">Pending</span>
                            )}
                          </div>
                          <p className="timeline-step-detail">Circle attestation service verifies block finality and signs transfer</p>
                          {transferStep === 2 && transferMessage && (
                            <div className="timeline-live-msg">{transferMessage}</div>
                          )}
                        </div>
                      </div>

                      {/* Step 3: Burn & Mint */}
                      <div className={`timeline-step ${transferStep > 3 ? "completed" : transferStep === 3 ? (transferError ? "error" : "active") : ""}`}>
                        <div className="timeline-rail">
                          <div className="timeline-node">{transferStep > 3 ? "✓" : "3"}</div>
                          <div className="timeline-connector" />
                        </div>
                        <div className="timeline-content">
                          <div className="timeline-row">
                            <span className="timeline-step-name">Destination Mint</span>
                            {transferStep > 3 ? (
                              <span className="chip chip-live">Minted</span>
                            ) : transferStep === 3 ? (
                              transferError ? <span className="chip chip-error">Failed</span> : <span className="chip chip-pending">Minting</span>
                            ) : (
                              <span className="chip chip-neutral">Pending</span>
                            )}
                          </div>
                          <p className="timeline-step-detail">Native USDC minted directly into recipient balance on destination</p>
                          {transferStep === 3 && transferMessage && (
                            <div className="timeline-live-msg">{transferMessage}</div>
                          )}
                        </div>
                      </div>

                      {/* Step 4: Settlement */}
                      <div className={`timeline-step ${transferStep >= 4 ? "completed" : ""}`}>
                        <div className="timeline-rail">
                          <div className="timeline-node">{transferStep >= 4 ? "✓" : "4"}</div>
                        </div>
                        <div className="timeline-content">
                          <div className="timeline-row">
                            <span className="timeline-step-name">Final Settlement</span>
                            {transferStep >= 4 ? (
                              <span className="chip chip-live">Settled</span>
                            ) : (
                              <span className="chip chip-neutral">Pending</span>
                            )}
                          </div>
                          <p className="timeline-step-detail">Transfer finalized with sub-second finality; balances updated</p>
                          {transferStep >= 4 && transferMessage && (
                            <div className="timeline-live-msg success">{transferMessage}</div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                /* ARC STABLEFX RFQ DESK */
                <div className="swap-card">
                  <div className="swap-card-header">
                    <div className="swap-card-header-left">
                      <div className="swap-card-icon-wrap">
                        <ArcLogo size={22} />
                      </div>
                      <div>
                        <h2 className="swap-card-title">Arc Native StableFX Desk</h2>
                        <p className="swap-card-subtitle">Institutional currency exchange with atomic settlement.</p>
                      </div>
                    </div>
                    <span className="chip chip-info">Spread: 5 bps</span>
                  </div>

                  <div className="swap-transfer-box">
                    {/* You Sell Section */}
                    <div className="swap-field-group">
                      <div className="swap-field-meta">
                        <span>You Sell</span>
                        <span className="swap-balance-row">
                          Available:{" "}
                          <button
                            type="button"
                            className="swap-balance-trigger"
                            onClick={() => {
                              const b = parseFloat(currentPayBalance || "0");
                              if (b > 0) setFxAmount(currentPayBalance);
                            }}
                            title="Click to use MAX balance"
                          >
                            {currentPayBalance} {fxFromToken}
                          </button>
                        </span>
                      </div>

                      <div className="swap-field-interactive">
                        {/* Token Pill */}
                        <div className="chain-select-btn">
                          <div className="chain-btn-logo">
                            <img
                              src={fxFromToken === "USDC" ? "/usdc-logo.svg" : "/eurc-logo.svg"}
                              alt={fxFromToken}
                              className="swap-token-img"
                            />
                          </div>
                          <div className="chain-btn-text">
                            <span className="chain-btn-name">{fxFromToken}</span>
                            <span className="chain-btn-badge">{fxFromToken === "EURC" ? "Euro Coin" : "USD Coin"}</span>
                          </div>
                        </div>

                        {/* Amount Input */}
                        <div className="swap-amount-input-box">
                          <input
                            type="number"
                            className="swap-big-input tabular-nums"
                            value={fxAmount}
                            onChange={(e) => setFxAmount(e.target.value)}
                            placeholder="0.0"
                            step="any"
                            min="0"
                            aria-label={`Sell amount in ${fxFromToken}`}
                          />
                        </div>
                      </div>

                      <div className="swap-field-footer">
                        <span className="swap-approx-val">
                          ≈ {fxFromToken === "USDC"
                            ? (parseFloat(fxAmount || "0") * 0.9212).toFixed(2) + " EUR"
                            : (parseFloat(fxAmount || "0") * 1.0855).toFixed(2) + " USD"}
                        </span>
                        <div className="amount-presets-row">
                          <button
                            type="button"
                            className="preset-btn"
                            onClick={() => {
                              const b = parseFloat(currentPayBalance || "0");
                              if (b > 0) setFxAmount((b * 0.25).toFixed(2));
                            }}
                          >
                            25%
                          </button>
                          <button
                            type="button"
                            className="preset-btn"
                            onClick={() => {
                              const b = parseFloat(currentPayBalance || "0");
                              if (b > 0) setFxAmount((b * 0.5).toFixed(2));
                            }}
                          >
                            50%
                          </button>
                          <button
                            type="button"
                            className="preset-btn"
                            onClick={() => {
                              const b = parseFloat(currentPayBalance || "0");
                              if (b > 0) setFxAmount(b.toString());
                            }}
                          >
                            MAX
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Switch Direction Button */}
                    <div className="swap-switch-divider">
                      <div className="swap-divider-line" />
                      <button
                        type="button"
                        className="swap-switch-btn"
                        aria-label="Switch exchange pair"
                        onClick={() => setFxFromToken((prev) => (prev === "EURC" ? "USDC" : "EURC"))}
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M7 16V4m0 0L3 8m4-4l4 4" />
                          <path d="M17 8v12m0 0l4-4m-4 4l-4-4" />
                        </svg>
                      </button>
                      <div className="swap-divider-line" />
                    </div>

                    {/* You Receive Section */}
                    <div className="swap-field-group">
                      <div className="swap-field-meta">
                        <span>You Receive (Guaranteed)</span>
                        <span className="chip chip-live">Atomic Settlement</span>
                      </div>

                      <div className="swap-field-interactive">
                        {/* Token Pill */}
                        <div className="chain-select-btn">
                          <div className="chain-btn-logo">
                            <img
                              src={toToken === "USDC" ? "/usdc-logo.svg" : "/eurc-logo.svg"}
                              alt={toToken}
                              className="swap-token-img"
                            />
                          </div>
                          <div className="chain-btn-text">
                            <span className="chain-btn-name">{toToken}</span>
                            <span className="chain-btn-badge">{toToken === "EURC" ? "Euro Coin" : "USD Coin"}</span>
                          </div>
                        </div>

                        {/* Readonly Output */}
                        <div className="swap-amount-input-box">
                          <div className="swap-big-output tabular-nums">
                            {fxQuoteLoading ? "Calculating..." : estOutput}
                          </div>
                        </div>
                      </div>

                      <div className="swap-field-footer">
                        <span>Balance on Arc: {currentReceiveBalance} {toToken}</span>
                        <span className="spec-value speed">Sub-second Finality</span>
                      </div>
                    </div>
                  </div>

                  {/* RFQ Live Specs */}
                  <div className="bridge-specs-card">
                    <div className="bridge-spec-item">
                      <span className="spec-label">Market Exchange Rate</span>
                      <span className="spec-value">
                        {fxFromToken === "USDC" ? "1 USDC ≈ 0.9212 EURC" : "1 EURC ≈ 1.0855 USDC"}
                      </span>
                    </div>
                    <div className="bridge-spec-item">
                      <span className="spec-label">Desk RFQ Spread</span>
                      <span className="spec-value highlight">5 bps (0.05%) Institutional</span>
                    </div>
                    <div className="bridge-spec-item">
                      <span className="spec-label">RFQ Quote Expiry</span>
                      <span className="spec-value speed">
                        ⏱ Expires in 00:{quoteSecondsLeft.toString().padStart(2, "0")}
                      </span>
                    </div>
                    <div className="bridge-spec-item">
                      <span className="spec-label">Settlement Engine</span>
                      <span className="spec-value free">Arc Atomic Finality (&lt;500ms)</span>
                    </div>
                  </div>

                  {!wallet ? (
                    <button
                      type="button"
                      className="btn btn-primary btn-lg swap-cta-btn"
                      onClick={() => setShowAppKitModal(true)}
                    >
                      Connect Wallet to Swap →
                    </button>
                  ) : !isArcChain ? (
                    <button
                      type="button"
                      className="btn btn-primary btn-lg swap-cta-btn"
                      onClick={handleSwitchToArc}
                      disabled={switchingNetwork}
                    >
                      {switchingNetwork ? "Switching..." : `Switch to ${ARC_CHAIN.name}`}
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-primary btn-lg swap-cta-btn"
                      onClick={handleExecuteFx}
                      disabled={fxLoading || parseFloat(fxAmount) <= 0}
                    >
                      {fxLoading ? "Settling Atomically on Arc..." : `Execute FX Settlement (${fxFromToken} → ${toToken})`}
                    </button>
                  )}

                  {(fxMessage || fxError || fxTxHash) && (
                    <div className={`swap-feedback-banner ${fxError ? "error" : "success"}`} role={fxError ? "alert" : "status"}>
                      <div className="feedback-icon">{fxError ? "✕" : "✓"}</div>
                      <div className="feedback-content">
                        <div className="feedback-title">{fxError ? "Settlement Failed" : "Settled on Arc"}</div>
                        <p className="feedback-desc">{fxError || fxMessage}</p>
                        {fxTxHash && (
                          <div className="feedback-links">
                            <a
                              href={`https://testnet.arcscan.app/tx/${fxTxHash}`}
                              target="_blank"
                              rel="noreferrer"
                              className="feedback-link"
                            >
                              Leg 1: Deposit Receipt ↗
                            </a>
                            {fxSettlementTxHash && (
                              <a
                                href={fxSettlementExplorerUrl || `https://testnet.arcscan.app/tx/${fxSettlementTxHash}`}
                                target="_blank"
                                rel="noreferrer"
                                className="feedback-link"
                              >
                                Leg 2: Payout Receipt ↗
                              </a>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Right 35%: Calm Supporting Panels */}
            <div className="swap-side-col">
              {/* Card 1: Recent Settlements */}
              <div className="side-card">
                <div className="side-card-header">
                  <h3 className="side-card-title">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10" />
                      <polyline points="12 6 12 12 16 14" />
                    </svg>
                    <span>Recent Settlements</span>
                  </h3>
                  <span className="chip chip-live">Live</span>
                </div>

                <div className="settlement-rows-list">
                  {settlementRows.map((row: any) => (
                    <div key={row.id} className="settlement-row-item">
                      <div className="settlement-row-left">
                        <UsdcLogo size={20} />
                        <div className="settlement-row-texts">
                          <span className="settlement-row-amount tabular-nums">{row.amount}</span>
                          <span className="settlement-row-route">{row.route}</span>
                        </div>
                      </div>
                      <div className="settlement-row-right">
                        {row.arcscanUrl ? (
                          <a
                            href={row.arcscanUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="settlement-status-link"
                            title="View on Arcscan"
                          >
                            Arcscan ↗
                          </a>
                        ) : (
                          <span className="chip chip-live">Settled</span>
                        )}
                        <span className="settlement-time-ago tabular-nums">{row.timeAgo}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Card 2: Network Status */}
              <div className="side-card">
                <div className="side-card-header">
                  <h3 className="side-card-title">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M5 12.55a11 11 0 0 1 14.08 0" />
                      <path d="M1.42 9a16 16 0 0 1 21.16 0" />
                      <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
                      <line x1="12" y1="20" x2="12.01" y2="20" />
                    </svg>
                    <span>Supported Networks</span>
                  </h3>
                  <span className="chip chip-live">Operational</span>
                </div>

                <div className="network-status-list">
                  {NETWORKS_LIST.map((net) => (
                    <div key={net.id} className="network-status-item">
                      <span className="network-status-name">
                        {net.logo} {net.name}
                      </span>
                      <div className="network-status-metrics">
                        <span className="network-latency tabular-nums">{net.latency}</span>
                        <span className="network-uptime"><span className="uptime-dot" /> 100%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Card 3: Powered by CCTP V2 */}
              <div className="cctp-info-box">
                <div className="cctp-info-icon-badge">i</div>
                <div>
                  <div className="cctp-info-title">Powered by Circle CCTP V2</div>
                  <p className="cctp-info-desc">
                    Arc uses Circle's Cross-Chain Transfer Protocol (CCTP V2), Iris Attestation, and native burn &amp; mint for secure, fast, and gas-abstracted USDC movement.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* TRANSFER REVIEW MODAL */}
      {showReviewModal && (
        <div className="review-modal-backdrop" onClick={() => setShowReviewModal(false)}>
          <div className="review-modal-card" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="review-modal-heading">
            <div className="review-modal-header">
              <h3 id="review-modal-heading" className="review-modal-title">Review Cross-Chain Transfer</h3>
              <button
                type="button"
                className="review-modal-close"
                aria-label="Close review modal"
                onClick={() => setShowReviewModal(false)}
              >
                ✕
              </button>
            </div>

            <div className="review-route-banner">
              <div className="review-route-item">
                <div className="chain-btn-logo">{originNetObj.logo}</div>
                <span className="review-net-name">{originNetObj.name}</span>
              </div>
              <div className="review-route-arrow">→</div>
              <div className="review-route-item">
                <div className="chain-btn-logo">{destNetObj.logo}</div>
                <span className="review-net-name">{destNetObj.name}</span>
              </div>
            </div>

            <div className="review-details-card">
              <div className="review-detail-row">
                <span>Send Amount:</span>
                <strong className="tabular-nums">{transferAmount} USDC</strong>
              </div>
              <div className="review-detail-row">
                <span>Destination Receives:</span>
                <strong className="review-detail-value-green tabular-nums">{transferAmount} USDC (1:1 Native)</strong>
              </div>
              <div className="review-detail-row">
                <span>Protocol:</span>
                <span>Circle CCTP V2</span>
              </div>
              <div className="review-detail-row">
                <span>Attestation Service:</span>
                <span>Circle Iris Attestation</span>
              </div>
              <div className="review-detail-row">
                <span>Estimated Time:</span>
                <span className="spec-value speed">&lt; 1 minute</span>
              </div>
              <div className="review-detail-row">
                <span>Gas &amp; Network Fee:</span>
                <span className="review-detail-value-green">0.00 USDC (Gas-Abstracted)</span>
              </div>
              <div className="review-detail-row">
                <span>Recipient Address:</span>
                <code>{shortAddress(wallet)}</code>
              </div>
            </div>

            <button
              type="button"
              className="btn btn-primary btn-lg review-confirm-btn"
              onClick={handleExecuteTransfer}
            >
              Confirm &amp; Initiate Transfer →
            </button>
          </div>
        </div>
      )}

      {/* Wallet AppKit Connect Modal */}
      <WalletAppKitModal
        open={showAppKitModal}
        onClose={() => setShowAppKitModal(false)}
        onConnected={(addr) => {
          setAddress(addr);
          setShowAppKitModal(false);
        }}
      />
    </div>
  );
}

export default SwapPage;
