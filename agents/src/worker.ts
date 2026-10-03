/**
 * QMA Autonomous Background Worker
 * 
 * This worker polls the database for queued agent sessions, automates prepaid
 * Gateway deposits from the agent's on-chain wallet if needed, and spins up
 * the QmaAgent lifecycle loops. It also hosts a minimal HTTP server for
 * Render web service health checks and external keep-alive cron pings.
 */

import { QmaAgent } from "./index.js";
import * as fs from "node:fs";
import * as path from "node:path";
import * as http from "node:http";
import { SessionTaskPool } from "./workerPool.js";

function loadEnv() {
  try {
    const candidatePaths = [
      path.resolve(process.cwd(), ".env"),
      path.resolve(process.cwd(), "..", ".env"),
    ];
    for (const envPath of candidatePaths) {
      if (fs.existsSync(envPath)) {
        const content = fs.readFileSync(envPath, "utf-8");
        for (const line of content.split("\n")) {
          const trimmed = line.trim();
          if (trimmed && !trimmed.startsWith("#") && trimmed.includes("=")) {
            const [key, ...valueParts] = trimmed.split("=");
            const val = valueParts.join("=").trim().replace(/^['"]|['"]$/g, "");
            const varKey = key.trim();
            if (!process.env[varKey]) {
              process.env[varKey] = val;
            }
          }
        }
      }
    }
  } catch (e) {
    console.error("Failed to load .env file:", e);
  }
}
loadEnv();

const API_BASE_URL = process.env.QMA_API_URL || process.env.API_BASE_URL || "http://127.0.0.1:8000";
const ARC_GATEWAY_URL = process.env.QMA_ARC_GATEWAY_URL || process.env.ARC_GATEWAY_URL || "http://127.0.0.1:3000";
const INTERNAL_SECRET = process.env.QMA_ARC_GATEWAY_INTERNAL_SECRET ?? "";
const POLL_INTERVAL_MS = 5000;
const SESSION_STATUS_POLL_INTERVAL_MS = 10000;
const DEFAULT_MAX_CONCURRENT_SESSIONS = 10;

function positiveIntegerEnv(name: string, fallback: number): number {
  const parsed = Number.parseInt(process.env[name] ?? "", 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

const MAX_CONCURRENT_SESSIONS = positiveIntegerEnv(
  "QMA_WORKER_MAX_CONCURRENT_SESSIONS",
  DEFAULT_MAX_CONCURRENT_SESSIONS,
);
const sessionPool = new SessionTaskPool(MAX_CONCURRENT_SESSIONS);

// Render runs this as a web service. The HTTP surface is health/keep-alive
// only; autonomous sessions run as independent asynchronous tasks in the pool.
const PORT = process.env.PORT || 10000;
http.createServer((req, res) => {
  const url = req.url || "/";
  if (url === "/health") {
    console.log(`[Worker] Keep-alive health check ping received from ${req.socket.remoteAddress}`);
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      status: "ok",
      service: "qma-agent-worker",
      uptime: process.uptime(),
      active_sessions: sessionPool.activeCount,
      max_concurrent_sessions: sessionPool.maxConcurrency,
      available_slots: sessionPool.availableSlots,
    }));
  } else {
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.end("QMA Worker is active\n");
  }
}).listen(PORT, () => {
  console.log(
    `[Worker] Health server listening on port ${PORT}; session concurrency=${MAX_CONCURRENT_SESSIONS}.`,
  );
});

function sessionHeaders(includeJson = false): Record<string, string> {
  const headers: Record<string, string> = {};
  if (includeJson) headers["Content-Type"] = "application/json";
  if (INTERNAL_SECRET) headers["x-qma-internal-secret"] = INTERNAL_SECRET;
  return headers;
}

async function updateSessionState(sessionId: string, state: any, status?: string) {
  try {
    const body: any = { runtime_state: state };
    if (status) body.status = status;

    const res = await fetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}`, {
      method: "PATCH",
      headers: sessionHeaders(true),
      body: JSON.stringify(body)
    });

    if (!res.ok) {
      console.error(`Failed to update session state:`, await res.text());
    }
  } catch (e) {
    console.error(`Network error updating session state:`, e);
  }
}

const WORKER_ID = `worker_${process.env.RENDER_INSTANCE_ID || process.pid}_${Math.random().toString(36).substring(2, 7)}`;

async function acquireSessionLease() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/sessions/acquire-lease`, {
      method: "POST",
      headers: sessionHeaders(true),
      body: JSON.stringify({ worker_id: WORKER_ID, lease_duration_sec: 60 }),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.acquired && data.session) {
        return data.session;
      }
    } else {
      console.error(`[Worker ${WORKER_ID}] Acquire lease failed: HTTP ${res.status}: ${(await res.text()).slice(0, 240)}`);
    }
  } catch (e) {
    console.error(`[Worker ${WORKER_ID}] Acquire lease error (${API_BASE_URL}):`, e);
  }
  return null;
}

async function heartbeatSessionLease(sessionId: string, runGeneration: number): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}/heartbeat`, {
      method: "POST",
      headers: sessionHeaders(true),
      body: JSON.stringify({
        worker_id: WORKER_ID,
        run_generation: runGeneration,
        lease_duration_sec: 60,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      return Boolean(data.ok);
    }
  } catch (e) {
    console.error(`[Worker ${WORKER_ID}] Heartbeat network error for session ${sessionId}:`, e);
  }
  return false;
}

async function checkpointSessionTick(sessionId: string, runGeneration: number, status: string, runtimeState: any, nextRunInSec: number = 15): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}/checkpoint`, {
      method: "POST",
      headers: sessionHeaders(true),
      body: JSON.stringify({
        worker_id: WORKER_ID,
        run_generation: runGeneration,
        status,
        runtime_state: runtimeState,
        next_run_in_sec: nextRunInSec,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      if (!data.updated) {
        console.warn(`[Worker ${WORKER_ID}] Checkpoint rejected for session ${sessionId} (runGen=${runGeneration}). Lease lost or session stopped.`);
        return false;
      }
      return true;
    } else {
      console.error(`[Worker ${WORKER_ID}] Checkpoint failed for session ${sessionId}:`, await res.text());
    }
  } catch (e) {
    console.error(`[Worker ${WORKER_ID}] Checkpoint network error for session ${sessionId}:`, e);
  }
  return false;
}

async function runWorkerLoop() {
  console.log(`[Worker ${WORKER_ID}] Started. Polling backend session queue at ${API_BASE_URL} for session ticks...`);

  // Background sweeper to reclaim expired leases every 60s
  setInterval(async () => {
    try {
      await fetch(`${API_BASE_URL}/api/v1/sessions/reclaim-leases`, {
        method: "POST",
        headers: sessionHeaders(),
      });
    } catch (e) { /* ignore */ }
  }, 60000);

  while (true) {
    if (sessionPool.isFull) {
      await sessionPool.waitForCapacity(POLL_INTERVAL_MS);
      continue;
    }

    try {
      const session = await acquireSessionLease();
      if (session) {
        const runGen = Number(session.run_generation || 1);
        const started = sessionPool.tryStart(session.id, async () => {
          console.log(
            `[Worker ${WORKER_ID}] Acquired tick lease for session ${session.id} (gen ${runGen}); active=${sessionPool.activeCount}/${sessionPool.maxConcurrency}.`,
          );

          const abortController = new AbortController();
          const heartbeatInterval = setInterval(async () => {
            const ok = await heartbeatSessionLease(session.id, runGen);
            if (!ok) {
              console.warn(`[Worker ${WORKER_ID}] Heartbeat failed for session ${session.id} (gen ${runGen}). Aborting active tick execution.`);
              abortController.abort();
              clearInterval(heartbeatInterval);
            }
          }, 15000);

          try {
            let signer;
            const runtimeState = session.runtime_state || {};
            const agentWalletAddress = runtimeState.agent_wallet_address;
            const agentWalletId = runtimeState.agent_wallet_id;

            if (agentWalletAddress && agentWalletId) {
              console.log(`[Worker] Using session-specific Circle Developer-Controlled Wallet: ${agentWalletAddress}`);
              signer = {
                walletAddress: agentWalletAddress,
                async signLeg(resourceUrl: string) {
                  const resp = await fetch(resourceUrl);
                  if (resp.status !== 402) {
                    throw new Error(`Expected x402 402 challenge, got ${resp.status}: ${await resp.text()}`);
                  }
                  const requiredHeader = resp.headers.get("PAYMENT-REQUIRED") || resp.headers.get("payment-required");
                  if (!requiredHeader) {
                    throw new Error("Arc Gateway did not return PAYMENT-REQUIRED header.");
                  }
                  const challenge = JSON.parse(Buffer.from(requiredHeader, "base64").toString("utf8"));
                  const accepted = challenge.accepts[0];

                  const now = Math.floor(Date.now() / 1000);
                  const validAfter = now - 600;
                  const validBefore = now + Math.max(Number(accepted.maxTimeoutSeconds || 0), 7 * 24 * 3600 + 600);
                  const crypto = await import("node:crypto");
                  const nonce = "0x" + Array.from(crypto.randomBytes(32)).map((b: any) => b.toString(16).padStart(2, "0")).join("");

                  const typedData = {
                    types: {
                      EIP712Domain: [
                        { name: "name", type: "string" },
                        { name: "version", type: "string" },
                        { name: "chainId", type: "uint256" },
                        { name: "verifyingContract", type: "address" },
                      ],
                      TransferWithAuthorization: [
                        { name: "from", type: "address" },
                        { name: "to", type: "address" },
                        { name: "value", type: "uint256" },
                        { name: "validAfter", type: "uint256" },
                        { name: "validBefore", type: "uint256" },
                        { name: "nonce", type: "bytes32" },
                      ],
                    },
                    primaryType: "TransferWithAuthorization" as const,
                    domain: {
                      name: "GatewayWalletBatched",
                      version: "1",
                      chainId: 5042002, // Arc Testnet
                      verifyingContract: accepted.extra.verifyingContract,
                    },
                    message: {
                      from: agentWalletAddress,
                      to: accepted.payTo,
                      value: accepted.amount,
                      validAfter: String(validAfter),
                      validBefore: String(validBefore),
                      nonce,
                    },
                  };

                  const headers: Record<string, string> = { "Content-Type": "application/json" };
                  if (INTERNAL_SECRET) {
                    headers["x-qma-internal-secret"] = INTERNAL_SECRET;
                  }

                  console.log(`[Worker] Requesting EIP-712 signature from Gateway for wallet ${agentWalletId}`);
                  const signResp = await fetch(`${ARC_GATEWAY_URL.replace(/\/$/, "")}/api/wallet/sign-typed-data`, {
                    method: "POST",
                    headers,
                    body: JSON.stringify({
                      walletId: agentWalletId,
                      data: typedData,
                    })
                  });

                  if (!signResp.ok) {
                    throw new Error(`Failed to sign typed data via Gateway: ${await signResp.text()}`);
                  }

                  const signResult = await signResp.json();
                  const signature = signResult.signature;

                  return {
                    paymentHeader: Buffer.from(JSON.stringify({
                      x402Version: 2,
                      payload: {
                        signature,
                        authorization: {
                          from: agentWalletAddress,
                          to: accepted.payTo,
                          value: accepted.amount,
                          validAfter: String(validAfter),
                          validBefore: String(validBefore),
                          nonce,
                        },
                      },
                      accepted,
                      resource: challenge.resource,
                    })).toString("base64")
                  };
                }
              };
            } else {
              // Hosted sessions must pay only from their own provisioned Agent
              // Wallet. Earlier builds silently fell back to a platform wallet
              // (AGENT_PRIVATE_KEY / a hardcoded address), spending operator
              // funds for sessions that lost their wallet binding. Fail the
              // tick instead so the session surfaces the error to its owner.
              throw new Error(
                "Session has no Agent Wallet binding (runtime_state.agent_wallet_id / agent_wallet_address missing). " +
                "Refusing to pay from a platform wallet. Delete and recreate this session to provision a fresh Agent Wallet.",
              );
            }

            const agent = new QmaAgent({ signer, apiUrl: API_BASE_URL });

            // Gateway balance payloads have drifted between micro-USDC base
            // units and decimal strings across service versions; probe the
            // known fields and normalize anything that looks like base units.
            function gatewayBalanceUsdc(data: any): number {
              const candidates = [
                data?.balance,
                data?.available,
                data?.amount,
                data?.total,
                data?.balances?.[0]?.amount,
                data?.balances?.[0]?.balance,
                data?.sources?.[0]?.amount,
                data?.sources?.[0]?.balance,
                data?.data?.balance,
                data?.data?.available,
                data?.data?.amount,
                data?.data?.total,
                data?.data?.balances?.[0]?.amount,
                data?.data?.balances?.[0]?.balance,
              ];
              for (const candidate of candidates) {
                if (candidate === undefined || candidate === null) continue;
                const raw = Number(candidate);
                if (!Number.isFinite(raw)) continue;
                return raw > 1000 ? raw / 1_000_000 : raw;
              }
              return 0;
            }

            async function ensureAgentGatewayBalance(requiredBudget: number) {
              if (!agentWalletAddress || !agentWalletId) return;

              let gwBalance = 0;
              try {
                const gwBalRes = await fetch(`${ARC_GATEWAY_URL.replace(/\/$/, "")}/api/balance/${agentWalletAddress}`);
                if (gwBalRes.ok) {
                  gwBalance = gatewayBalanceUsdc(await gwBalRes.json());
                }
              } catch (e) {
                console.error("[Worker] Error checking Gateway balance:", e);
              }

              if (gwBalance >= requiredBudget) return;

              let onChainUsdc = 0;
              try {
                const balRes = await fetch(`${ARC_GATEWAY_URL.replace(/\/$/, "")}/api/wallet/${agentWalletId}/balance`);
                if (balRes.ok) {
                  const bdata = await balRes.json();
                  const tokenBalances = bdata.tokenBalances || [];
                  for (const tb of tokenBalances) {
                    if (tb?.token?.symbol === "USDC") {
                      onChainUsdc = parseFloat(tb.amount || "0");
                      break;
                    }
                  }
                }
              } catch (e) {
                console.error("[Worker] Error checking on-chain balance:", e);
              }

              const requiredTopUp = Math.max(requiredBudget - gwBalance, 0);
              if (onChainUsdc < requiredTopUp) {
                throw new Error(`Insufficient funds. Agent Wallet has ${onChainUsdc} USDC on-chain, but needs ${requiredTopUp} USDC more to satisfy Gateway budget.`);
              }

              console.log(`[Worker] Automatically depositing ${requiredTopUp.toFixed(6)} USDC from Agent Wallet into Gateway...`);
              const headers: Record<string, string> = { "Content-Type": "application/json" };
              if (INTERNAL_SECRET) {
                headers["x-qma-internal-secret"] = INTERNAL_SECRET;
              }
              const depRes = await fetch(`${ARC_GATEWAY_URL.replace(/\/$/, "")}/api/wallet/deposit`, {
                method: "POST",
                headers,
                body: JSON.stringify({
                  walletId: agentWalletId,
                  amountUsdc: requiredTopUp.toFixed(6)
                })
              });

              if (!depRes.ok) {
                throw new Error(`Gateway auto-deposit failed: ${await depRes.text()}`);
              }

              for (let i = 0; i < 20; i++) {
                await new Promise(resolve => setTimeout(resolve, 3000));
                try {
                  const checkRes = await fetch(`${ARC_GATEWAY_URL.replace(/\/$/, "")}/api/balance/${agentWalletAddress}`);
                  if (checkRes.ok) {
                    const currentGwBal = gatewayBalanceUsdc(await checkRes.json());
                    if (currentGwBal >= requiredBudget) {
                      return;
                    }
                  }
                } catch (e) { /* ignore */ }
              }
              throw new Error("Timeout waiting for Gateway balance to settle after deposit.");
            }

            async function pushEvent(sessionId: string, eventType: string, payload: any) {
              try {
                const res = await fetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}/events`, {
                  method: "POST",
                  headers: sessionHeaders(true),
                  body: JSON.stringify({ event_type: eventType, payload })
                });
                if (!res.ok) {
                  console.error(`Failed to push event ${eventType}:`, await res.text());
                }
              } catch (e) {
                console.error(`Network error pushing event ${eventType}:`, e);
              }
            }

            agent.on("purchase_completed", async (event) => {
              console.log(`[Worker ${WORKER_ID}] Session ${session.id} purchased ${event.symbol} for ${event.amount_usdc} USDC.`);
              await pushEvent(session.id, "purchase_completed", event);
            });

            agent.on("purchase_failed", async (event) => {
              console.log(`[Worker ${WORKER_ID}] Session ${session.id} purchase failed: ${event.error}`);
              await pushEvent(session.id, "purchase_failed", event);
            });

            let parsedMaxPurchases: number | null = null;
            const qtyMatch = (session.task || "").match(/(?:buy|purchase|get|mua)\s+(\d+)/i);
            if (qtyMatch) {
              parsedMaxPurchases = parseInt(qtyMatch[1], 10);
            }

            // Structured tasks from the MCP connector ("... for SYMBOL: query")
            // carry a hard symbol constraint: the planner may never substitute
            // a different (higher-ranked) symbol. Free-text web sessions do
            // not match the pattern and keep the old autonomous behavior.
            const symbolMatch = (session.task || "").match(/\bfor\s+([A-Za-z0-9]{2,20})\s*:/);
            const requiredSymbols = symbolMatch ? [symbolMatch[1]] : [];

            // Auto-deposit only based on remaining session budget
            const currentSpent = Number(runtimeState.spentUsdc || 0);
            const remainingBudget = Math.max(0, Number(session.budget_usdc || 0) - currentSpent);
            if (remainingBudget > 0) {
              await ensureAgentGatewayBalance(remainingBudget);
            }

            const initialState = session.runtime_state ? { ...session.runtime_state } : undefined;
            if (initialState?.status === "completed" && initialState?.stopReason === "manual_interrupt") {
              initialState.status = "paused";
              initialState.endedAt = null;
            }

            // Execute single session tick with abort signal
            console.log(`[Worker ${WORKER_ID}] Running session tick for ${session.id}...`);
            const tickResult = await agent.runTick({
              task: session.task,
              sessionBudgetUsdc: session.budget_usdc,
              maxPricePerReportUsdc: Math.min(5, session.budget_usdc),
              maxPurchases: parsedMaxPurchases,
              requiredSymbols,
              pollIntervalSeconds: 5,
              executionMode: "live",
              initialState,
              ownerWalletAddress: runtimeState.owner_wallet || undefined,
              runSource: `agent_session_${session.id}`,
            }, abortController.signal);

            clearInterval(heartbeatInterval);

            if (!abortController.signal.aborted) {
              const nextStatus = tickResult.state.status || "running";
              console.log(`[Worker ${WORKER_ID}] Tick complete for session ${session.id}: status=${nextStatus}, finished=${tickResult.finished}`);
              await checkpointSessionTick(
                session.id,
                runGen,
                nextStatus,
                tickResult.state,
                tickResult.nextRunInSec || 15
              );
            }
          } catch (err) {
            clearInterval(heartbeatInterval);
            if (abortController.signal.aborted) {
              console.warn(`[Worker ${WORKER_ID}] Session ${session.id} tick execution aborted due to lost lease or stop signal.`);
            } else {
              console.error(`[Worker ${WORKER_ID}] Session ${session.id} tick failed:`, err);
              const fallbackState = session.runtime_state || {};
              fallbackState.status = "failed";
              fallbackState.lastError = err instanceof Error ? err.message : String(err);
              await checkpointSessionTick(session.id, runGen, "failed", fallbackState, 0);
            }
          }
        });

        if (!started) {
          console.error(`[Worker ${WORKER_ID}] No execution slot available for claimed session ${session.id}.`);
        }
        continue;
      }
    } catch (e) {
      console.error("[Worker] Worker poll error:", e);
    }

    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}

runWorkerLoop().catch(console.error);
