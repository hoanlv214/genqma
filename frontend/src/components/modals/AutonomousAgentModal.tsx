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

interface AutonomousAgentModalProps {
  open: boolean;
  onClose: () => void;
  wallet: string; // The user's wallet address (simulated deposit source)
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
    case "stopped": return purchases > 0 ? 2 : 1;
    case "error": return purchases > 0 ? 2 : 1;
    case "completed": return 3;
    default: return 0;
  }
}

export function AutonomousAgentModal({ open, onClose, wallet }: AutonomousAgentModalProps) {
  const [prompt, setPrompt] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "creating" | "queued" | "running" | "completed" | "error" | "stopped">("idle");
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

  useEffect(() => {
    if (wallet && open) void refreshAgentWallet({ silent: true });
  }, [wallet, open, refreshAgentWallet]);

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
          const active = sessions.find(s => s.status === "running" || s.status === "queued" || s.status === "stopped");
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

    if (sessionId && (status === "queued" || status === "running")) {
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
                } else if (a.action === "retry_backoff") {
                  const timeStr = new Date(a.at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                  addIfUnique(
                    `action-${data.id}-${index}`,
                    <div>
                      ❌ Purchase failed: <span style={{ color: 'var(--c-red, #ff5c5c)', fontFamily: 'monospace' }}>{String(a.reason)}</span>
                      <div className="agent-runner-purchase-time">{timeStr}</div>
                    </div>
                  );
                }
              });

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
                    <p style={{ color: "var(--t2)" }}>I've finished researching and executing purchases based on your prompt.</p>

                    <div className="agent-runner-complete-stats" style={{ gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: '11px', color: 'var(--t3)', textTransform: 'uppercase' }}>Target Budget</span>
                        <strong style={{ color: '#fff' }}>${Number(data.budget_usdc || 0).toFixed(4)} USDC</strong>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: '11px', color: 'var(--t3)', textTransform: 'uppercase' }}>Actually Spent</span>
                        <strong style={{ color: 'var(--accent)' }}>${currentSpent.toFixed(4)} USDC</strong>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: '11px', color: 'var(--t3)', textTransform: 'uppercase' }}>Purchased Reports</span>
                        <strong style={{ color: '#fff' }}>{data.runtime_state.purchaseCount || 0}</strong>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: '11px', color: 'var(--t3)', textTransform: 'uppercase' }}>Duration</span>
                        <strong style={{ color: '#fff' }}>{durationStr}</strong>
                      </div>

                      {data.runtime_state.candidatesEvaluated > 0 && (
                        <div style={{ gridColumn: 'span 2', display: 'flex', flexDirection: 'column', marginTop: '4px', paddingTop: '8px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                          <span style={{ fontSize: '11px', color: 'var(--t3)', textTransform: 'uppercase' }}>Evaluated Candidates</span>
                          <span style={{ fontSize: '12px', color: 'var(--t2)' }}>Analyzed {data.runtime_state.candidatesEvaluated} reports before making decisions.</span>
                        </div>
                      )}
                    </div>
                  </div>
                ));
              }
              if (data.status === "error") addIfUnique(`status-error-${data.id}`, "❌ Session Failed!");

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
      <div className="agent-funding-widget" style={{
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid rgba(255,255,255,0.05)',
        borderRadius: '8px',
        padding: '12px',
        marginTop: '8px'
      }}>
        <p style={{ margin: '0 0 12px 0', fontSize: '13px', lineHeight: 1.5 }}>
          {messageText}
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <div style={{ position: 'relative', width: '90px' }}>
              <input
                id={`fund-input-${targetAddress}`}
                type="number"
                step="0.01"
                min="0.01"
                defaultValue={defaultAmount}
                style={{
                  width: '100%',
                  background: 'rgba(0,0,0,0.3)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '4px',
                  padding: '6px 8px',
                  color: '#fff',
                  fontSize: '12px',
                  outline: 'none'
                }}
              />
              <span style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', fontSize: '9px', color: 'var(--t3)' }}>USDC</span>
            </div>

            <button
              type="button"
              className="connect-btn-primary"
              onClick={() => {
                const inputEl = document.getElementById(`fund-input-${targetAddress}`) as HTMLInputElement;
                const amt = inputEl ? parseFloat(inputEl.value) : parseFloat(defaultAmount);
                if (isNaN(amt) || amt <= 0) {
                  alert("Please enter a valid amount.");
                  return;
                }
                handleMetaMaskTransfer(targetAddress, amt);
              }}
              style={{
                flex: 1,
                padding: '8px 12px',
                fontSize: '11px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                background: 'var(--accent)',
                color: '#000'
              }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="12" height="12"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
              Deposit via Wallet (Arc Testnet)
            </button>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              onClick={handleManualRefreshBalance}
              disabled={refreshCooldown || isRefreshingBal}
              style={{
                flex: 1,
                padding: '8px 12px',
                fontSize: '11px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '4px',
                cursor: (refreshCooldown || isRefreshingBal) ? 'not-allowed' : 'pointer',
                background: 'rgba(255,255,255,0.05)',
                color: '#fff',
                opacity: (refreshCooldown || isRefreshingBal) ? 0.6 : 1
              }}
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                width="12"
                height="12"
                style={{ animation: isRefreshingBal ? "qma-spin 1s linear infinite" : "none" }}
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
                  qrEl.style.display = qrEl.style.display === 'none' ? 'flex' : 'none';
                }
              }}
              style={{
                padding: '8px 12px',
                fontSize: '11px',
                fontWeight: 600,
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '4px',
                cursor: 'pointer',
                background: 'rgba(255,255,255,0.05)',
                color: 'var(--t2)',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="12" height="12"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
              Show QR
            </button>
          </div>

          <div
            id={`qr-container-${targetAddress}`}
            style={{
              display: 'none',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '16px',
              background: 'rgba(0,0,0,0.2)',
              borderRadius: '6px',
              marginTop: '6px',
              border: '1px dashed rgba(255,255,255,0.1)'
            }}
          >
            <img
              src={`https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${targetAddress}`}
              alt="QR Code"
              style={{ width: '120px', height: '120px', borderRadius: '4px', background: '#fff', padding: '6px', marginBottom: '10px' }}
            />
            <span style={{ fontSize: '11px', color: '#fff', fontWeight: 600, marginBottom: '2px' }}>Arc Testnet (Chain: 5042002)</span>
            <span style={{ fontSize: '10px', color: 'var(--t3)', marginBottom: '8px' }}>Scan with Mobile Wallet</span>
            <span className="mono" style={{ fontSize: '10px', color: 'var(--accent)', wordBreak: 'break-all', textAlign: 'center' }}>{targetAddress}</span>
          </div>
        </div>
      </div>
    );
  };

  const getErc20TransferData = (recipient: string, amountDecimal: number): string => {
    const cleanRecipient = recipient.toLowerCase().replace("0x", "");
    const paddedRecipient = cleanRecipient.padStart(64, "0");
    const rawAmount = BigInt(Math.round(amountDecimal * 1_000_000));
    const hexAmount = rawAmount.toString(16).padStart(64, "0");
    return `0xa9059cbb${paddedRecipient}${hexAmount}`;
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
    const provider = window.ethereum || (window as any).rabby || (window as any).okxwallet;
    if (!provider) {
      alert("Please install MetaMask or another EVM wallet to fund your Agent Wallet.");
      return;
    }
    try {
      setMessages(prev => [...prev, {
        id: `sys-funding-switch-${Date.now()}`,
        role: "agent",
        content: `⏳ Switching your wallet to Arc Testnet (Chain ID: 5042002)...`
      }]);

      try {
        await provider.request({
          method: "wallet_switchEthereumChain",
          params: [{ chainId: "0x4cef52" }],
        });
      } catch (switchError: any) {
        if (switchError.code === 4902) {
          await provider.request({
            method: "wallet_addEthereumChain",
            params: [{
              chainId: "0x4cef52",
              chainName: "Arc Testnet",
              nativeCurrency: { name: "USDC", symbol: "USDC", decimals: 18 },
              rpcUrls: ["https://rpc.testnet.arc.network"],
              blockExplorerUrls: ["https://testnet.arcscan.app"]
            }]
          });
        } else {
          throw switchError;
        }
      }



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
            data: getErc20TransferData(toAddress, amount),
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

    // Queued sessions can be edited before claim. Stopped sessions are edited
    // and then explicitly re-queued so the new instruction actually continues.
    if (sessionId && (status === "queued" || status === "running" || status === "stopped")) {
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
        if (status === "stopped") {
          await sessionRequest(wallet, `/api/v1/sessions/${sessionId}/resume`, { method: "POST" });
          setStatus("queued");
        }
        setMessages(prev => [...prev, {
          id: `sys-${Date.now()}`,
          role: "agent",
          content: `Got it! I've updated your instructions${newBudget !== null ? ` and set the budget to $${newBudget} USDC` : ''}${status === "stopped" ? " and re-queued the session" : ""}.`
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

      // Fetch the latest wallet balance to check if it's funded now
      const latestAgentWallet = await refreshAgentWallet();
      const currentBal = latestAgentWallet?.balanceUsdc || 0;

      if (currentBal < parsedBudget) {
        setStatus("idle");
        setMessages(prev => [...prev, {
          id: `sys-fund-${Date.now()}`,
          role: "agent",
          content: (
            <div>
              <p style={{ margin: '0 0 10px 0' }}>
                ℹ️ Agent Wallet created at <span className="mono" style={{ color: 'var(--accent)', fontSize: '11px', fontWeight: 'bold' }}>{createdWalletAddress || "..."}</span>.
                Please fund at least <strong>${parsedBudget.toFixed(2)} USDC</strong> to this address to start.
              </p>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className="connect-btn-primary"
                  onClick={() => handleMetaMaskTransfer(createdWalletAddress, parsedBudget)}
                  style={{
                    padding: '8px 12px',
                    fontSize: '11px',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    background: 'var(--accent)',
                    color: '#000'
                  }}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="12" height="12"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                  Fund ${parsedBudget.toFixed(2)} USDC via MetaMask
                </button>
                <button
                  type="button"
                  onClick={handleManualRefreshBalance}
                  disabled={refreshCooldown || isRefreshingBal}
                  style={{
                    padding: '8px 12px',
                    fontSize: '11px',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '4px',
                    cursor: (refreshCooldown || isRefreshingBal) ? 'not-allowed' : 'pointer',
                    background: 'rgba(255,255,255,0.05)',
                    color: '#fff',
                    opacity: (refreshCooldown || isRefreshingBal) ? 0.6 : 1
                  }}
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    width="12"
                    height="12"
                    style={{ animation: isRefreshingBal ? "qma-spin 1s linear infinite" : "none" }}
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

  const handleStop = async () => {
    if (!sessionId) return;
    try {
      await sessionRequest<any>(wallet, `/api/v1/sessions/${sessionId}/stop`, { method: "POST" });
      setStatus("stopped");
    } catch (err: any) {
      console.error(err);
    }
  };

  const handleResume = async () => {
    if (!sessionId) return;
    try {
      await sessionRequest<any>(wallet, `/api/v1/sessions/${sessionId}/resume`, { method: "POST" });
      setStatus("queued");
    } catch (err: any) {
      console.error(err);
    }
  };

  const currentWalletBalance = Math.max(0, globalBalance - spent);
  const remainingBudget = Math.max(0, budget - spent);
  const shortWallet = wallet ? `${wallet.slice(0, 6)}…${wallet.slice(-4)}` : "—";

  let statusText = "Active";
  let statusClass = "ready";

  if (currentWalletBalance <= 0) {
    statusText = "Gateway Empty";
    statusClass = "failed";
  } else if (remainingBudget <= 0) {
    statusText = "Budget Exhausted";
    statusClass = "failed";
  } else if (status === "stopped") {
    statusText = "User Paused";
    statusClass = "failed";
  } else if (status === "error") {
    statusText = "Error";
    statusClass = "failed";
  } else if (status === "completed") {
    statusText = "Completed";
    statusClass = "ready";
  }

  const curStage = stageIndex(status, purchases);
  const stageFailed = status === "error" || status === "stopped";
  const stageProgressPct = (curStage / (STAGE_LABELS.length - 1)) * 100;

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
          <div className="agent-stage-progress-bar" style={{ left: "12.5%", right: "12.5%" }}>
            <div
              className={`agent-stage-progress-fill${stageFailed ? " is-failed" : ""}`}
              style={{ width: `${stageProgressPct}%` }}
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
              <span className={`agent-live-pill${status === "running" ? " active" : ""}${status === "error" ? " error" : ""}`}>
                {status}
              </span>
              <span className="agent-chat-wallet">{shortWallet}</span>
            </div>

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
                <div className="agent-funding-row" style={{ borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: "6px", marginTop: "4px" }}>
                  <span className="agent-funding-label" style={{ fontWeight: 600 }}>Total Balance</span>
                  <span className="agent-funding-val" style={{ fontWeight: 600, color: "var(--accent)" }}>${(globalBalance + gatewayBalance).toFixed(4)} USDC</span>
                </div>
                <div className="agent-funding-row" style={{ marginTop: "4px" }}>
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

            <div className="agent-dp-block" style={{ flex: 1, minHeight: 0 }}>
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

            {(status === "queued" || status === "running" || status === "stopped" || status === "error" || status === "completed") && (
              <div className="agent-modal-actions">
                {status === "queued" || status === "running" ? (
                  <button className="agent-modal-cancel" onClick={handleStop}>
                    Pause Agent
                  </button>
                ) : (
                  <div style={{ display: "flex", gap: "10px", width: "100%" }}>
                    {status === "stopped" && (
                      <button className="agent-modal-primary" style={{ flex: 1 }} onClick={handleResume}>
                        Resume Agent
                      </button>
                    )}
                    <button
                      className="agent-modal-cancel"
                      style={{ flex: 1 }}
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
