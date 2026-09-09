import { QmaAgent } from "../src/index.js";
import { createCircleAgentWalletSigner } from "../src/wallets/circleSigner.js";
// Local FastAPI endpoint
const API_BASE_URL = process.env.API_BASE_URL || "http://127.0.0.1:8000";

async function main() {
  const task = process.argv[2] || "Buy 3 reports on trending layer-2 networks";
  const budgetUsdc = 15;

  console.log(`[1] Creating session via API...`);
  
  // 1. Create session row in backend
  const createRes = await fetch(`${API_BASE_URL}/api/v1/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: "CLI Session",
      task: task,
      budget_usdc: budgetUsdc,
    })
  });
  
  if (!createRes.ok) {
    console.error("Failed to create session:", await createRes.text());
    process.exit(1);
  }
  
  const session = await createRes.json();
  const sessionId = session.id;
  console.log(`[1] Created session ${sessionId}`);

  // 2. Start session in backend
  const startRes = await fetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: "running" })
  });
  if (!startRes.ok) {
    console.error("Failed to mark session as running:", await startRes.text());
    process.exit(1);
  }
  console.log(`[2] Session marked as running`);

  // 3. Initialize Agent with CLI Wallet Signer
  const signer = createCircleAgentWalletSigner({
    address: process.env.AGENT_WALLET_ADDRESS || "0x4859d0d0babdcc8c4d8d2d116258fd0e5f7ff67d",
    chain: "ARC-TESTNET"
  });

  const agent = new QmaAgent({ signer });

  agent.on("state_change", async (state) => {
    console.log(`[State Change] Persisting state to backend... status: ${state.status}, purchases: ${state.purchaseCount}`);
    try {
      const updateRes = await fetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          runtime_state: state
        })
      });
      if (!updateRes.ok) {
        console.error("Failed to update runtime state:", await updateRes.text());
      }
    } catch (e) {
      console.error("Network error updating runtime state:", e);
    }
  });

  async function pushEvent(sessionId: string, eventType: string, payload: any) {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/sessions/${sessionId}/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
    console.log(`✅ Purchased ${event.symbol} report! Paid ${event.amount_usdc} USDC.`);
    await pushEvent(session.id, "purchase_completed", event);
  });

  agent.on("purchase_failed", async (event) => {
    console.log(`❌ Purchase failed: ${event.error}`);
    await pushEvent(session.id, "purchase_failed", event);
  });

  console.log(`[3] Running agent...`);
  
  // 5. Run the loop
  await agent.run({
    task: task,
    sessionBudgetUsdc: budgetUsdc,
    maxPricePerReportUsdc: 5,
    maxPurchases: 3,
    executionMode: "live"
  });
  
  console.log(`[4] Agent finished.`);
}

main().catch(console.error);
