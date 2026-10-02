/**
 * AutonomousAgentModal component
 * 
 * Renders the modal interface for creating, managing, and monitoring
 * autonomous research agent sessions. Displays real-time status steps,
 * chat conversation history, wallet status, and provides options for
 * funding the agent's wallet or manual balance refresh.
 */

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { requestJson } from "../../services/api";
import {
  getCachedWalletProfileToken,
  requestWalletProfileSession,
} from "../../services/walletProfileSession";
import { useAgentWalletStore } from "../../state/agentWalletStore";
import { ARC_CHAIN } from "../../config/network";
import { ensureArcTestnet, getWalletProvider } from "../../services/wallet";
import { encodeErc20TransferCalldata } from "../../services/gatewayCrypto";
import { cn } from "../../utils/cn";
import "./AutonomousAgentModal.css";

interface AutonomousAgentModalProps {
  open: boolean;
  onClose: () => void;
  wallet: string; // Wallet authorized to create and manage this agent session.
}

type AgentAction = {
  action: string;
  symbol?: string;
  provider?: string;
  tier?: string;
  at: string;
  amount_usdc?: number;
  reason?: string;
};

type ChatMessage = {
  id: string;
  role: "user" | "agent";
  content: ReactNode;
};

const STAGE_LABELS = ["Queued", "Research", "Buying", "Finished"];

async function sessionRequest<T>(
  wallet: string,
  path: string,
  init: RequestInit = {},
  allowSignature = true,
) {
  const headers = new Headers(init.headers);
  const walletToken = allowSignature
    ? await requestWalletProfileSession(wallet)
    : getCachedWalletProfileToken(wallet);
  if (!walletToken) throw new Error("Wallet authorization is required for this session action.");
  headers.set("X-QMA-Wallet-Token", walletToken);
  return requestJson<T>(path, { ...init, headers });
}

function stageIndex(status: string, purchases: number): number {
  switch (status) {
    case "queued": return 0;
    case "running": return purchases > 0 ? 2 : 1;
    case "paused":
    case "stopped": return purchases > 0 ? 2 : 1;
    case "error":
    case "failed": return purchases > 0 ? 2 : 1;
    case "completed": return 3;
    default: return 0;
  }
}

export function AutonomousAgentModal({ open, onClose, wallet }: AutonomousAgentModalProps) {
  const [prompt, setPrompt] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "creating" | "queued" | "running" | "completed" | "error" | "stopped" | "paused" | "failed">("idle");
  const [budget, setBudget] = useState<number>(0);
  const [spent, setSpent] = useState<number>(0);
  const [purchases, setPurchases] = useState<number>(0);
  const [purchasedItems, setPurchasedItems] = useState<any[]>([]);

  // Real UI state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { agentWallet, refresh: refreshAgentWallet } = useAgentWalletStore();
  const agentWalletAddress = agentWallet?.address || "";
  const globalBalance = agentWallet?.balanceUsdc || 0;
  const gatewayBalance = agentWallet?.gatewayBalanceUsdc || 0;
  const autoFetchedRef = useRef(false);
  const [isRefreshingBal, setIsRefreshingBal] = useState(false);
  const [refreshCooldown, setRefreshCooldown] = useState(false);

  // Spending Policy state
  const [cliCopied, setCliCopied] = useState(false);
  const [spendingPolicy, setSpendingPolicy] = useState<{
    max_per_tx_usdc: number;
    daily_cap_usdc: number;
    weekly_cap_usdc: number;
    monthly_cap_usdc: number;
    source?: string;
  } | null>(null);

  const handleCopyCircleCliCommand = async () => {
    if (!agentWalletAddress) return;
    try {
      const res = await requestJson<{ command: string }>(
        `/api/v1/agent/spending-policy/command?wallet_address=${agentWalletAddress}`
      );
      if (res.command) {
        await navigator.clipboard.writeText(res.command);
        setCliCopied(true);
        setTimeout(() => setCliCopied(false), 2500);
      }
    } catch {
      const fallback = `circle wallet limit set --address ${agentWalletAddress} --chain BASE --policy-type stablecoin --per-tx 0.05 --daily 1 --weekly 5 --monthly 20`;
      await navigator.clipboard.writeText(fallback);
      setCliCopied(true);
      setTimeout(() => setCliCopied(false), 2500);
    }
  };

  useEffect(() => {
    if (wallet && open) void refreshAgentWallet({ silent: true });
  }, [wallet, open, refreshAgentWallet]);

  useEffect(() => {
    if (open && agentWalletAddress) {
      requestJson<{
        max_per_tx_usdc: number;
        daily_cap_usdc: number;
        weekly_cap_usdc: number;
        monthly_cap_usdc: number;
        source?: string;
      }>(`/api/v1/agent/spending-policy?wallet_address=${agentWalletAddress}`)
        .then((res) => {
          if (res) setSpendingPolicy(res);
        })
        .catch(() => {});
    }
  }, [open, agentWalletAddress]);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, status]);

  // Handle session polling
  useEffect(() => {
    // 1. On mount, try to find an active session if we don't have one
    if (!sessionId && open && !autoFetchedRef.current && wallet) {
      const cachedWalletToken = getCachedWalletProfileToken(wallet);
      if (cachedWalletToken) {
        autoFetchedRef.current = true;
        sessionRequest<any[]>(wallet, `/api/v1/sessions?owner_wallet=${wallet}`, {}, false).then(sessions => {
          const active = sessions.find(s => s.status === "running" || s.status === "queued" || s.status === "stopped" || s.status === "paused");
          if (active) {
            setSessionId(active.id);
            setStatus(active.status);
            setBudget(active.budget_usdc || 0);

            setMessages([
              { id: "sys-0", role: "agent", content: `Resumed session ${active.id.split("-")[0]}. Currently ${active.status}.` }
            ]);
          } else {
            setMessages([
              { id: "sys-start", role: "agent", content: "Hi! I'm your Autonomous Background Runner. Tell me what reports you'd like me to purchase, and specify a budget (e.g. 'Buy 3 trending reports under $1.50 USDC')." }
            ]);
          }
        }).catch(err => console.error("Failed to fetch sessions on mount", err));
      }
    }

    let interval: ReturnType<typeof setInterval>;

    if (sessionId && (status === "queued" || status === "running" || status === "paused")) {
      interval = setInterval(async () => {
        try {
          const data = await sessionRequest<any>(wallet, `/api/v1/sessions/${sessionId}`, {}, false);

          if (data.status !== status) {
            setStatus(data.status);
          }

          if (data.runtime_state) {
            const currentSpent = data.runtime_state.spentUsdc ??
              (data.runtime_state.initialBudgetUsdc !== undefined ? data.runtime_state.initialBudgetUsdc - data.runtime_state.remainingBudgetUsdc : 0);

            setSpent(currentSpent);
            setPurchases(data.runtime_state.purchaseCount || 0);
            if (data.runtime_state.purchasedEntitlements) {
              setPurchasedItems(data.runtime_state.purchasedEntitlements);
            }

            // Format logs from actions as new chat messages
            const actions: AgentAction[] = data.runtime_state.actions || [];

            setMessages(prev => {
              const newMessages = [...prev];

              // Only add messages that we haven't added yet based on a simple unique ID
              const addIfUnique = (id: string, content: ReactNode) => {
                if (!newMessages.some(m => m.id === id)) {
                  newMessages.push({ id, role: "agent", content });
                }
              };

              if (data.status === "queued") addIfUnique(`status-queued-${data.id}`, "Session queued. Awaiting available worker...");
              if (data.status === "running") addIfUnique(`status-running-${data.id}`, "Worker started. I am analyzing your request...");

              actions.forEach((a, index) => {
                const isAttempt = a.action === "attempt_purchase" || a.action === "attempt_upgrade";
                if (a.action === "purchase" || a.action === "upgrade" || isAttempt) {
                  let tier = a.tier;
                  let provider = a.provider;

                  if (!tier || !provider) {
                    const match = (data.runtime_state.purchasedEntitlements || []).find((e: any) => e.symbol === a.symbol);
                    if (match) {
                      tier = tier || match.tier;
                      provider = provider || match.provider_id;
                    }
                  }

                  const tierStr = tier ? ` ${tier.toUpperCase()}` : "";
                  const provStr = provider ? ` from ${provider}` : "";

                  // If amount is missing, estimate it based on tier
                  const estimatedPrice = tier === "full" ? 0.0050 : 0.0010;
                  const costStr = a.amount_usdc !== undefined
                    ? ` for $${Number(a.amount_usdc).toFixed(4)} USDC`
                    : ` for $${estimatedPrice.toFixed(4)} USDC`;

                  const timeStr = new Date(a.at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });

                  if (isAttempt) {
                    addIfUnique(
                      `action-${data.id}-${index}`,
                      <div>
                        ⏳ Analyzing and purchasing{tierStr} report on <span className="agent-runner-purchase-symbol">{a.symbol}</span>{provStr}{costStr}...
                        <div className="agent-runner-purchase-time">{timeStr}</div>
                      </div>
                    );
                  } else {
                    addIfUnique(
                      `action-${data.id}-${index}`,
                      <div>
                        ✅ Purchased{tierStr} report on <span className="agent-runner-purchase-symbol">{a.symbol}</span>{provStr}{costStr}
                        <div className="agent-runner-purchase-time">{timeStr}</div>
                      </div>
                    );
                  }
                } else if (a.action === "retry_backoff" || a.action === "failure") {
                  const timeStr = new Date(a.at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                  addIfUnique(
                    `action-${data.id}-${index}`,
                    <div>
                      ❌ Purchase failed: <span className="text-red-400 font-mono">{String(a.reason)}</span>
                      <div className="agent-runner-purchase-time">{timeStr}</div>
                    </div>
                  );
                }
              });

              // Render any recorded runtime failures
              const failures = Array.isArray(data.runtime_state?.failures) ? data.runtime_state.failures : [];
              failures.forEach((f: any, fIdx: number) => {
                const timeStr = f.at ? new Date(f.at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : "";
                addIfUnique(
                  `failure-${data.id}-${fIdx}`,
                  <div>
                    ❌ <span className="text-red-400 font-mono">{String(f.error || f.message || "Execution error")}</span>
                    {timeStr && <div className="agent-runner-purchase-time">{timeStr}</div>}
                  </div>
                );
              });

              if (data.status === "paused") {
                addIfUnique(`status-paused-${data.id}`, (
                  <div className="bg-amber-500/[0.08] border border-amber-500/25 rounded-md px-2.5 py-2 text-amber-400 text-xs mt-1">
                    ⏸️ <strong>Session Auto-Paused</strong>: Risk Governance Circuit Breaker triggered. Zero-spend invariant active on Arc.
                  </div>
                ));
              }

              if (data.status === "stopped") addIfUnique(`status-stopped-${data.id}`, "⚠️ Session has been stopped.");

              if (data.status === "completed") {
                const startedAt = data.runtime_state.startedAt ? new Date(data.runtime_state.startedAt).getTime() : 0;
                const endedAt = data.runtime_state.endedAt ? new Date(data.runtime_state.endedAt).getTime() : (data.runtime_state.actions && data.runtime_state.actions.length > 0 ? new Date(data.runtime_state.actions[data.runtime_state.actions.length - 1].at).getTime() : Date.now());
                let durationStr = "0s";
                if (startedAt && endedAt) {
                  const ms = Math.max(0, endedAt - startedAt);
                  const s = Math.floor(ms / 1000) % 60;
                  const m = Math.floor(ms / (1000 * 60)) % 60;
                  const h = Math.floor(ms / (1000 * 60 * 60));
                  durationStr = `${h > 0 ? h + 'h ' : ''}${m > 0 ? m + 'm ' : ''}${s}s`;
                }

                addIfUnique(`status-completed-${data.id}`, (
                  <div className="agent-runner-complete-card">
                    <h3>🎉 Session Completed!</h3>
                    <p className="text-t-secondary">I've finished researching and executing purchases based on your prompt.</p>

                    <div className="agent-runner-complete-stats grid grid-cols-2 gap-2">
                      <div className="flex flex-col">
                        <span className="text-[11px] text-t-tertiary uppercase">Target Budget</span>
                        <strong className="text-t1">${Number(data.budget_usdc || 0).toFixed(4)} USDC</strong>
                      </div>

                      <div className="flex flex-col">
                        <span className="text-[11px] text-t-tertiary uppercase">Actually Spent</span>
                        <strong className="text-brand-cyan">${currentSpent.toFixed(4)} USDC</strong>
                      </div>

                      <div className="flex flex-col">
                        <span className="text-[11px] text-t-tertiary uppercase">Purchased Reports</span>
                        <strong className="text-t1">{data.runtime_state.purchaseCount || 0}</strong>
                      </div>

                      <div className="flex flex-col">
                        <span className="text-[11px] text-t-tertiary uppercase">Duration</span>
                        <strong className="text-t1">{durationStr}</strong>
                      </div>

                      {data.runtime_state.candidatesEvaluated > 0 && (
                        <div className="col-span-2 flex flex-col mt-1 pt-2 border-t border-bdr">
                          <span className="text-[11px] text-t-tertiary uppercase">Evaluated Candidates</span>
                          <span className="text-xs text-t-secondary">Analyzed {data.runtime_state.candidatesEvaluated} reports before making decisions.</span>
                        </div>
                      )}
                    </div>
                  </div>
                ));
              }
              if (data.status === "error" || data.status === "failed") {
                const lastFail = failures.length > 0 ? failures[failures.length - 1]?.error : null;
                const errMsg = data.runtime_state?.lastError || lastFail || "Session execution failed.";
                addIfUnique(`status-failed-${data.id}`, (
                  <div className="agent-runner-failure-card bg-red-500/[0.08] border border-red-500/20 rounded-lg px-3 py-2.5 mt-2 text-red-400">
                    <strong className="block mb-1">❌ Session Stopped / Failed</strong>
                    <span className="text-xs break-words text-t-secondary">{String(errMsg)}</span>
                  </div>
                ));
              }

              return newMessages;
            });
          }
        } catch (err) {
          console.error("Polling error", err);
        }
      }, 5000);
    }

    return () => clearInterval(interval);
  }, [sessionId, status]);

  const renderFundingWidget = (messageText: string, targetAddress: string, requiredAmount: number) => {
    const defaultAmount = Math.max(0.01, Number((requiredAmount - (globalBalance + gatewayBalance)).toFixed(2))).toString();

    return (
      <div className="agent-funding-widget bg-surface-2 border border-bdr rounded-lg p-3 mt-2">
        <p className="m-0 mb-3 text-[13px] leading-normal">
          {messageText}
        </p>

        <div className="flex flex-col gap-2.5">
          <div className="flex gap-2 items-center">
            <div className="relative w-[90px]">
              <input
                id={`fund-input-${targetAddress}`}
                type="number"
                step="0.01"
                min="0.01"
                defaultValue={defaultAmount}
                className="w-full bg-black/30 border border-bdr rounded px-2 py-1.5 text-t1 text-xs outline-none focus:border-brand-cyan/50"
              />
              <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[9px] text-t-tertiary pointer-events-none">USDC</span>
            </div>

            <button
              type="button"
              className="connect-btn-primary flex-1 py-2 px-3 text-[11px] font-semibold flex items-center justify-center gap-1.5 border-none rounded cursor-pointer bg-brand-cyan text-on-accent hover:opacity-90 transition-opacity"
              onClick={() => {
                const inputEl = document.getElementById(`fund-input-${targetAddress}`) as HTMLInputElement;
                const amt = inputEl ? parseFloat(inputEl.value) : parseFloat(defaultAmount);
                if (isNaN(amt) || amt <= 0) {
                  alert("Please enter a valid amount.");
                  return;
                }
                handleMetaMaskTransfer(targetAddress, amt);
              }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="12" height="12"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
              Deposit via Wallet ({ARC_CHAIN.name})
            </button>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleManualRefreshBalance}
              disabled={refreshCooldown || isRefreshingBal}
              className={cn(
                "flex-1 py-2 px-3 text-[11px] font-semibold flex items-center justify-center gap-1.5 border border-bdr rounded bg-surface-2 text-t1 transition-opacity",
                (refreshCooldown || isRefreshingBal) ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:bg-surface-3"
              )}
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                width="12"
                height="12"
                className={isRefreshingBal ? "animate-spin" : ""}
              >
                <path d="M23 4v6h-6"></path>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
              </svg>
              {isRefreshingBal ? "Checking..." : refreshCooldown ? "Cooldown" : "Check Balance"}
            </button>

            <button
              type="button"
              onClick={() => {
                const qrEl = document.getElementById(`qr-container-${targetAddress}`);
                if (qrEl) {
                  qrEl.classList.toggle("hidden");
                  qrEl.classList.toggle("flex");
                }
              }}
              className="py-2 px-3 text-[11px] font-semibold border border-bdr rounded cursor-pointer bg-surface-2 text-t-secondary flex items-center gap-1 hover:bg-surface-3 transition-colors"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="12" height="12"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
              Show QR
            </button>
          </div>

          <div
            id={`qr-container-${targetAddress}`}
            className="hidden flex-col items-center justify-center p-4 bg-black/20 rounded-md mt-1.5 border border-dashed border-bdr"
          >
            <img
              src={`https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${targetAddress}`}
              alt="QR Code"
              width={120}
              height={120}
              className="w-[120px] h-[120px] rounded bg-paper p-1.5 mb-2.5"
            />
            <span className="text-[11px] text-t1 font-semibold mb-0.5">{ARC_CHAIN.name} (Chain: {ARC_CHAIN.chainId})</span>
            <span className="text-[10px] text-t-tertiary mb-2">Scan with Mobile Wallet</span>
            <span className="font-mono text-[10px] text-brand-cyan break-all text-center">{targetAddress}</span>
          </div>
        </div>
      </div>
    );
  };

  const handleManualRefreshBalance = async () => {
    if (refreshCooldown || !wallet) return;

    setRefreshCooldown(true);
    setTimeout(() => setRefreshCooldown(false), 5000); // 5s cooldown

    try {
      setIsRefreshingBal(true);
      const refreshedWallet = await refreshAgentWallet();
      if (refreshedWallet) {
        const newBal = refreshedWallet.balanceUsdc;
        const newGwBal = refreshedWallet.gatewayBalanceUsdc;

        const totalAvail = newBal + newGwBal;
        if (totalAvail >= budget) {
          if (sessionId) {
            await sessionRequest(wallet, `/api/v1/sessions/${sessionId}/start`, { method: "POST" });
            setStatus("queued");
            setMessages(prev => [...prev, {
              id: `sys-started-funded-${Date.now()}`,
              role: "agent",
              content: `🎉 Funds detected! Your Agent Wallet now has $${totalAvail.toFixed(2)} USDC ($${newBal.toFixed(2)} on-chain, $${newGwBal.toFixed(2)} prepaid). Starting session...`
            }]);
          } else {
            setMessages(prev => [...prev, {
              id: `sys-funded-nobudget-${Date.now()}`,
              role: "agent",
              content: `✅ Funds detected! Current balance is $${totalAvail.toFixed(2)} USDC ($${newBal.toFixed(2)} on-chain, $${newGwBal.toFixed(2)} prepaid).`
            }]);
          }
        } else {
          setMessages(prev => [...prev, {
            id: `sys-insufficient-still-${Date.now()}`,
            role: "agent",
            content: `ℹ️ Current balance is $${totalAvail.toFixed(2)} USDC ($${newBal.toFixed(2)} on-chain, $${newGwBal.toFixed(2)} prepaid) (required: $${budget.toFixed(2)} USDC). Please send funds first.`
          }]);
        }
      }
    } catch (err) {
      console.error("Refresh balance error:", err);
    } finally {
      setIsRefreshingBal(false);
    }
  };

  const handleMetaMaskTransfer = async (toAddress: string, amount: number) => {
    const provider = getWalletProvider();
    if (!provider) {
      alert("Please install MetaMask or another EVM wallet to fund your Agent Wallet.");
      return;
    }
    try {
      setMessages(prev => [...prev, {
        id: `sys-funding-switch-${Date.now()}`,
        role: "agent",
        content: `⏳ Switching your wallet to ${ARC_CHAIN.name} (Chain ID: ${ARC_CHAIN.chainId})...`
      }]);

      await ensureArcTestnet(provider);



      setMessages(prev => [...prev, {
        id: `sys-funding-tx-${Date.now()}`,
        role: "agent",
        content: `⏳ Requesting transfer of ${amount.toFixed(2)} USDC in your MetaMask wallet...`
      }]);

      const txHash = (await provider.request({
        method: "eth_sendTransaction",
        params: [
          {
            from: wallet,
            to: "0x3600000000000000000000000000000000000000",
            data: encodeErc20TransferCalldata(toAddress, amount),
            gas: "0x186a0"
          }
        ]
      })) as string;

      setMessages(prev => [...prev, {
        id: `sys-funding-submitted-${Date.now()}`,
        role: "agent",
        content: `🚀 Transfer transaction submitted! Hash: ${txHash.slice(0, 10)}... Please click the "Check Balance" button once the transaction succeeds to activate your session.`
      }]);

    } catch (err: any) {
      console.error("MetaMask transfer error:", err);
      setMessages(prev => [...prev, {
        id: `sys-funding-failed-${Date.now()}`,
        role: "agent",
        content: `❌ Transfer aborted or failed: ${err.message || err}`
      }]);
    }
  };

  const handleStart = async (e: FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    const userText = prompt.trim();
    setPrompt("");

    // Add user message immediately
    setMessages(prev => [...prev, { id: `user-${Date.now()}`, role: "user", content: userText }]);

    // A running worker does not hot-reload task/budget. Refuse the edit instead
    // of claiming an instruction was applied while the old policy keeps running.
    if (sessionId && status === "running") {
      setMessages(prev => [...prev, {
        id: `sys-stop-first-${Date.now()}`,
        role: "agent",
        content: "Stop the current session before changing its instructions. This prevents the running worker from continuing with the old task.",
      }]);
      return;
    }

    // Queued sessions can be edited before claim. Stopped or paused sessions are edited
    // and then explicitly re-queued so the new instruction actually continues.
    if (sessionId && (status === "queued" || status === "running" || status === "stopped" || status === "paused")) {
      let newBudget: number | null = null;
      const budgetMatch = userText.toLowerCase().match(/(?:budget|under|limit|max|cap|price|of|to|up to)\s*(?:[\$]?)\s*([0-9\.]+)/i);
      const usdcMatch = userText.toLowerCase().match(/([0-9\.]+)\s*(?:usdc|usd)/i);
      const dollarMatch = userText.toLowerCase().match(/\$\s*([0-9\.]+)/i);

      if (budgetMatch) newBudget = parseFloat(budgetMatch[1]);
      else if (usdcMatch) newBudget = parseFloat(usdcMatch[1]);
      else if (dollarMatch) newBudget = parseFloat(dollarMatch[1]);

      const updatePayload: any = { task: userText };
      if (newBudget !== null) {
        updatePayload.budget_usdc = newBudget;
        setBudget(newBudget);
      }

      try {
        await sessionRequest(wallet, `/api/v1/sessions/${sessionId}`, {
          method: "PATCH",
          body: JSON.stringify(updatePayload)
        });
        if (status === "stopped" || status === "paused") {
          await sessionRequest(wallet, `/api/v1/sessions/${sessionId}/resume`, { method: "POST" });
          setStatus("queued");
        }
        setMessages(prev => [...prev, {
          id: `sys-${Date.now()}`,
          role: "agent",
          content: `Got it! I've updated your instructions${newBudget !== null ? ` and set the budget to $${newBudget} USDC` : ''}${status === "stopped" || status === "paused" ? " and re-queued the session" : ""}.`
        }]);
      } catch (err: any) {
        setMessages(prev => [...prev, { id: `err-${Date.now()}`, role: "agent", content: `❌ Failed to update session: ${err.message}` }]);
      }
      return;
    }

    // ----------------------------------------------------
    // Create new session logic
    // ----------------------------------------------------
    setSessionId(null);
    setSpent(0);
    setPurchases(0);
    setPurchasedItems([]);

    // Parse budget
    let parsedBudget = 10.0;
    const kwMatch = userText.toLowerCase().match(/(?:budget|under|limit|max|cap|price|of|to|up to)\s*(?:[\$]?)\s*([0-9\.]+)/i);
    const usdcMatch = userText.toLowerCase().match(/([0-9\.]+)\s*(?:usdc|usd)/i);
    const dollarMatch = userText.toLowerCase().match(/\$\s*([0-9\.]+)/i);

    if (kwMatch) parsedBudget = parseFloat(kwMatch[1]);
    else if (usdcMatch) parsedBudget = parseFloat(usdcMatch[1]);
    else if (dollarMatch) parsedBudget = parseFloat(dollarMatch[1]);

    // Ensure they have enough in agent wallet balance if wallet already exists
    const totalAvail = globalBalance + gatewayBalance;
    if (agentWalletAddress && parsedBudget > totalAvail) {
      setMessages(prev => [...prev, {
        id: `err-bal-${Date.now()}`,
        role: "agent",
        content: renderFundingWidget(
          `❌ You only have $${totalAvail.toFixed(2)} USDC ($${globalBalance.toFixed(2)} on-chain, $${gatewayBalance.toFixed(2)} prepaid) in your Agent Wallet, which is less than your requested budget of $${parsedBudget.toFixed(2)} USDC. Please fund your wallet to proceed.`,
          agentWalletAddress,
          parsedBudget
        )
      }]);
      return;
    }

    setBudget(parsedBudget);

    try {
      setStatus("creating");

      // 1. Check for Web3 Wallet
      if (!(window as any).ethereum) {
        setMessages(prev => [...prev, { id: `err-wallet-${Date.now()}`, role: "agent", content: `❌ Please install MetaMask or a Web3 wallet to authorize operations.` }]);
        setStatus("error");
        return;
      }

      setMessages(prev => [...prev, {
        id: `sys-started-${Date.now()}`,
        role: "agent",
        content: `✅ Submitting to backend...`
      }]);

      const sessionData = await sessionRequest<any>(wallet, `/api/v1/sessions`, {
        method: "POST",
        body: JSON.stringify({
          title: "Autonomous Web UI Session",
          task: userText,
          budget_usdc: parsedBudget,
          owner_wallet: wallet
        })
      });
      const newId = sessionData.id;
      setSessionId(newId);

      const createdWalletAddress = sessionData.runtime_state?.agent_wallet_address;

      // Fetch the latest wallet balance to check if it's funded now (on-chain or prepaid Gateway)
      const latestAgentWallet = await refreshAgentWallet();
      const currentBal = (latestAgentWallet?.balanceUsdc || 0) + (latestAgentWallet?.gatewayBalanceUsdc || 0);

      if (currentBal < parsedBudget) {
        setStatus("idle");
        setMessages(prev => [...prev, {
          id: `sys-fund-${Date.now()}`,
          role: "agent",
          content: (
            <div>
              <p className="m-0 mb-2.5">
                ℹ️ Agent Wallet created at <span className="mono text-brand-cyan text-[11px] font-bold">{createdWalletAddress || "..."}</span>.
                Please fund at least <strong>${parsedBudget.toFixed(2)} USDC</strong> to this address to start.
              </p>
              <div className="flex gap-2 flex-wrap">
                <button
                  type="button"
                  className="connect-btn-primary px-3 py-2 text-[11px] font-semibold flex items-center gap-1.5 border-none rounded cursor-pointer bg-brand-cyan text-on-accent hover:opacity-90 transition-opacity"
                  onClick={() => handleMetaMaskTransfer(createdWalletAddress, parsedBudget)}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="12" height="12"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                  Fund ${parsedBudget.toFixed(2)} USDC via MetaMask
                </button>
                <button
                  type="button"
                  onClick={handleManualRefreshBalance}
                  disabled={refreshCooldown || isRefreshingBal}
                  className={cn(
                    "px-3 py-2 text-[11px] font-semibold flex items-center gap-1.5 border border-bdr rounded bg-surface-2 text-t1 transition-opacity",
                    (refreshCooldown || isRefreshingBal) ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:bg-surface-3"
                  )}
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    width="12"
                    height="12"
                    className={isRefreshingBal ? "animate-spin" : ""}
                  >
                    <path d="M23 4v6h-6"></path>
                    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                  </svg>
                  {isRefreshingBal ? "Checking..." : refreshCooldown ? "Cooldown (5s)" : "Check Balance"}
                </button>
              </div>
            </div>
          )
        }]);
        return;
      }

      await sessionRequest<any>(wallet, `/api/v1/sessions/${newId}/start`, { method: "POST" });
      setStatus("queued");

    } catch (err: any) {
      setStatus("error");
      setMessages(prev => [...prev, { id: `err-${Date.now()}`, role: "agent", content: `❌ Error: ${err.message}` }]);
    }
  };

  const handleControl = async (action: "pause" | "resume" | "kill", reason?: string) => {
    if (!sessionId) return;
    try {
      await sessionRequest<any>(
        wallet,
        `/api/v1/agent/sessions/${sessionId}/control`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action, reason: reason || "User triggered via Agent Modal" }),
        }
      );
      if (action === "pause") setStatus("paused");
      else if (action === "resume") setStatus("running");
      else if (action === "kill") setStatus("stopped");
    } catch (err: any) {
      console.error("Session control error:", err);
    }
  };

  const handleStop = async () => {
    await handleControl("pause", "User paused session via modal");
  };

  const handleResume = async () => {
    await handleControl("resume", "User resumed session via modal");
  };

  const currentWalletBalance = Math.max(0, globalBalance - spent);
  const remainingBudget = Math.max(0, budget - spent);
  const shortWallet = wallet ? `${wallet.slice(0, 6)}…${wallet.slice(-4)}` : "—";

  let statusText = "Active";
  let statusClass = "ready";

  if (status === "error" || status === "failed") {
    statusText = "Failed";
    statusClass = "failed";
  } else if (currentWalletBalance <= 0) {
    statusText = "Gateway Empty";
    statusClass = "failed";
  } else if (remainingBudget <= 0) {
    statusText = "Budget Exhausted";
    statusClass = "failed";
  } else if (status === "paused") {
    statusText = "Auto-Paused";
    statusClass = "warning";
  } else if (status === "stopped") {
    statusText = "User Paused";
    statusClass = "failed";
  } else if (status === "completed") {
    statusText = "Completed";
    statusClass = "ready";
  }

  const curStage = stageIndex(status, purchases);
  const stageFailed = status === "error" || status === "stopped" || status === "failed" || status === "paused";
  const stageWidthClass = curStage <= 0 ? "w-0" : curStage === 1 ? "w-1/3" : curStage === 2 ? "w-2/3" : "w-full";

  const renderMessage = (msg: ChatMessage) => {
    const speaker = msg.role === "user" ? "You" : "Agent";
    const tone = msg.role === "user" ? "t-val" : "t-dim";
    return (
      <div key={msg.id} className={`agent-chat-message ${tone}`}>
        <span className="agent-message-speaker">{speaker}</span>
        <div>{msg.content}</div>
      </div>
    );
  };

  return (
    <div className="modal-backdrop open agent-buyer-backdrop">
      <div className="agent-buyer-modal" role="dialog">

        {/* Header */}
        <div className="agent-buyer-header">
          <div>
            <div className="agent-buyer-eyebrow">AGENT SESSION</div>
            <div className="agent-buyer-title">Autonomous Market Research</div>
            <div className="agent-buyer-subtitle">
              Researching market opportunities and executing strategies while you're away.
            </div>
          </div>
          <div className="agent-header-right">
            <button className="icon-button close-btn" onClick={onClose} title="Close">
              <i className="ti ti-x" />
            </button>
          </div>
        </div>

        {/* Session stage strip */}
        <div className="agent-session-stage stage-count-4">
          <div className="agent-stage-progress-bar left-[12.5%] right-[12.5%]">
            <div
              className={cn("agent-stage-progress-fill", stageWidthClass, stageFailed && "is-failed")}
            />
          </div>
          {STAGE_LABELS.map((label, i) => {
            let cls = "";
            if (stageFailed && i === curStage) cls = "failed";
            else if (i < curStage) cls = "done";
            else if (i === curStage) cls = status === "completed" ? "done" : "active";
            return (
              <div key={label} className={`agent-stage-dot ${cls}`}>
                <span />
                {label}
              </div>
            );
          })}
        </div>

        <div className="agent-buyer-grid">
          {/* Chat log */}
          <div className="agent-chat-panel">
            <div className="agent-chat-topline">
              <span className={`agent-live-pill${status === "running" ? " active" : ""}${status === "paused" ? " warning" : ""}${status === "error" || status === "failed" ? " error" : ""}`}>
                {status}
              </span>
              <span className="agent-chat-wallet">{shortWallet}</span>
            </div>

            {status === "paused" && (
              <div className="bg-gradient-to-br from-amber-500/[0.12] to-red-400/[0.08] border border-amber-500/35 rounded-lg px-3.5 py-2.5 mx-4 mt-3 mb-1 flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-amber-400 font-semibold text-xs">
                    <i className="ti ti-alert-triangle text-base" />
                    <span>Circuit Breaker Active · Auto-Paused</span>
                  </div>
                  <span className="text-[10px] text-t-tertiary font-mono">Zero-Spend Enforced</span>
                </div>
                <p className="m-0 text-[11px] text-t-secondary leading-snug">
                  Session has been halted by the Autonomous Risk Governance Engine. Any payment requests on Arc are rejected fast with HTTP 403.
                </p>
                <div className="flex gap-2 mt-0.5">
                  <button
                    type="button"
                    onClick={() => handleControl("resume", "Manual resume from Circuit Breaker banner")}
                    className="px-2.5 py-1 text-[11px] font-semibold rounded bg-amber-500 text-on-accent border-none cursor-pointer flex items-center gap-1 hover:bg-amber-400 transition-colors"
                  >
                    <i className="ti ti-player-play" /> Resume Execution
                  </button>
                  <button
                    type="button"
                    onClick={() => handleControl("kill", "Emergency Kill from Circuit Breaker banner")}
                    className="px-2.5 py-1 text-[11px] font-semibold rounded bg-red-500/15 text-red-400 border border-red-500/30 cursor-pointer flex items-center gap-1 hover:bg-red-500/25 transition-colors"
                  >
                    <i className="ti ti-power" /> Emergency Terminate
                  </button>
                </div>
              </div>
            )}

            <div className="agent-chat-log">
              {messages.map(renderMessage)}
              {status === "running" && (
                <div className="agent-chat-message t-dim">
                  <span className="agent-message-speaker">Agent</span>
                  <i className="ti ti-dots agent-runner-typing-dots" />
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <form onSubmit={handleStart} className="agent-chat-composer">
              <span className="agent-chat-caret">$</span>
              <input
                className="agent-bar-input"
                type="text"
                placeholder={status === "queued" || status === "running" || status === "creating" ? "Modify your request (e.g. 'edit budget under x$')" : "Buy 3 trending reports under $15..."}
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
                disabled={status === "creating"}
              />
              <button type="submit" className="submit-btn" disabled={!prompt.trim() || status === "creating"} title="Send">
                <i className="ti ti-send" />
              </button>
            </form>
          </div>

          {/* Decision / control panel */}
          <div className="agent-decision-panel">
            <div className="agent-dp-block">
              <div className="agent-dp-block-label">Funding</div>
              <div className="agent-funding-bar">
                <div className="agent-funding-row">
                  <span className="agent-funding-label">On-chain Wallet</span>
                  <span className="agent-funding-val">${globalBalance.toFixed(4)} USDC</span>
                </div>
                <div className="agent-funding-row">
                  <span className="agent-funding-label">Gateway Prepaid</span>
                  <span className="agent-funding-val">${gatewayBalance.toFixed(4)} USDC</span>
                </div>
                <div className="agent-funding-row border-t border-bdr pt-1.5 mt-1">
                  <span className="agent-funding-label font-semibold">Total Balance</span>
                  <span className="agent-funding-val font-semibold text-brand-cyan">${(globalBalance + gatewayBalance).toFixed(4)} USDC</span>
                </div>
                <div className="agent-funding-row mt-1">
                  <span className="agent-funding-label">Session Budget</span>
                  <span className="agent-funding-val">${spent.toFixed(4)} / ${budget.toFixed(2)} USDC</span>
                </div>
                <div className="agent-funding-row">
                  <span className="agent-funding-label">Status</span>
                  <span className={`agent-funding-status ${statusClass}`}>
                    {statusText}
                  </span>
                </div>
              </div>
            </div>

            {/* Spending Policy & Limits */}
            <div className="agent-dp-block">
              <div className="agent-dp-block-label flex justify-between items-center">
                <span>Spending Policy & Limits</span>
                <span className={cn(
                  "text-[10px] normal-case font-semibold px-1.5 py-0.5 rounded",
                  spendingPolicy?.source === "circle_cli"
                    ? "text-brand-cyan bg-[rgba(0,255,178,0.12)]"
                    : "text-t-tertiary bg-surface-2"
                )}>
                  {spendingPolicy?.source === "circle_cli" ? "Circle MPC Policy" : "Default Caps"}
                </span>
              </div>
              <div className="agent-funding-bar">
                <div className="agent-funding-row">
                  <span className="agent-funding-label">Per-Tx / Daily Cap</span>
                  <span className="agent-funding-val">
                    ${spendingPolicy?.max_per_tx_usdc?.toFixed(2) ?? "0.05"} / ${spendingPolicy?.daily_cap_usdc?.toFixed(2) ?? "1.00"} USDC
                  </span>
                </div>
                <div className="agent-funding-row">
                  <span className="agent-funding-label">Weekly / Monthly Cap</span>
                  <span className="agent-funding-val">
                    ${spendingPolicy?.weekly_cap_usdc?.toFixed(2) ?? "5.00"} / ${spendingPolicy?.monthly_cap_usdc?.toFixed(2) ?? "20.00"} USDC
                  </span>
                </div>
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={handleCopyCircleCliCommand}
                    disabled={!agentWalletAddress}
                    className={cn(
                      "w-full px-2 py-1.5 text-[11px] font-medium rounded border border-bdr bg-surface-2 text-t-secondary flex items-center justify-center gap-1.5 transition-colors",
                      !agentWalletAddress ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:bg-surface-3"
                    )}
                    title="Copy verbatim Circle CLI command to inspect or configure wallet limits with OTP"
                  >
                    <i className={cn(cliCopied ? "ti ti-check text-brand-cyan" : "ti ti-terminal")} />
                    {cliCopied ? "Circle CLI command copied!" : "Copy Circle CLI Limit Command"}
                  </button>
                </div>
              </div>
            </div>

            {/* Risk Governance & Invariants */}
            <div className="agent-dp-block">
              <div className="agent-dp-block-label flex justify-between items-center">
                <span>Risk Governance & Invariants</span>
                <span className="text-[10px] text-[var(--green)] normal-case font-semibold bg-emerald-500/10 px-1.5 py-0.5 rounded">
                  Circuit Breaker Active
                </span>
              </div>
              <div className="agent-funding-bar">
                <div className="agent-funding-row">
                  <span className="agent-funding-label">Zero-Spend Guard</span>
                  <span className="agent-funding-val text-[var(--green)]">HTTP 403 on Arc</span>
                </div>
                <div className="agent-funding-row">
                  <span className="agent-funding-label">GenLayer SLA Oracle</span>
                  <span className="agent-funding-val text-[var(--green)]">Fail-Closed</span>
                </div>
                <div className="agent-funding-row">
                  <span className="agent-funding-label">Athenian Euthyna</span>
                  <span className="agent-funding-val text-brand-cyan font-mono text-[10px]">SHA-256 Audit Trail</span>
                </div>
              </div>
            </div>

            <div className="agent-dp-block flex-1 min-h-0">
              <div className="agent-dp-block-label">Purchases ({purchases})</div>
              {purchasedItems.length === 0 ? (
                <div className="agent-empty-card">No purchases yet — the agent will list each report here as it buys.</div>
              ) : (
                <div className="agent-runner-purchases-list">
                  {purchasedItems.map((item, i) => (
                    <div key={i} className="agent-invoice-row">
                      <span>{item.symbol}{item.tier ? ` · ${String(item.tier).toUpperCase()}` : ""}</span>
                      <span>{item.provider_id || ""}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {(status === "queued" || status === "running" || status === "paused" || status === "stopped" || status === "error" || status === "failed" || status === "completed") && (
              <div className="agent-modal-actions">
                {status === "queued" || status === "running" ? (
                  <div className="flex gap-2.5 w-full">
                    <button className="agent-modal-cancel flex-1" onClick={handleStop}>
                      Pause Agent
                    </button>
                    <button className="agent-modal-cancel flex-1 border-red-500/40 text-red-400 hover:bg-red-500/10" onClick={() => handleControl("kill", "Emergency Kill from modal")}>
                      Emergency Kill
                    </button>
                  </div>
                ) : status === "paused" ? (
                  <div className="flex gap-2.5 w-full">
                    <button className="agent-modal-primary flex-1" onClick={handleResume}>
                      Resume Agent
                    </button>
                    <button className="agent-modal-cancel flex-1 border-red-500/40 text-red-400 hover:bg-red-500/10" onClick={() => handleControl("kill", "Emergency Kill from modal")}>
                      Emergency Kill
                    </button>
                  </div>
                ) : (
                  <div className="flex gap-2.5 w-full">
                    {status === "stopped" && (
                      <button className="agent-modal-primary flex-1" onClick={handleResume}>
                        Resume Agent
                      </button>
                    )}
                    <button
                      className="agent-modal-cancel flex-1"
                      onClick={() => {
                        setSessionId(null);
                        setStatus("idle");
                        setMessages([{ id: "sys-start", role: "agent", content: "Hi! I'm your Autonomous Background Runner. Tell me what reports you'd like me to purchase, and specify a budget (e.g. 'Buy 3 trending reports under $1.50 USDC')." }]);
                        setSpent(0);
                        setPurchases(0);
                        setPurchasedItems([]);
                        setPrompt("");
                      }}
                    >
                      New Session
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
