import { QmaAgent } from "../src/index.js";
import { createCircleAgentWalletSigner } from "../src/wallets/circleSigner.js";

async function main() {
  // 1. Configure the Circle Agent Wallet
  const signer = createCircleAgentWalletSigner({
    address: "0x4859d0d0babdcc8c4d8d2d116258fd0e5f7ff67d",
    chain: "ARC-TESTNET"
  });

  // 2. Initialize the Agent
  const agent = new QmaAgent({ signer });

  // 3. Monitor purchases
  agent.on("purchase_completed", (event) => {
    console.log(`✅ Purchased ${event.symbol} report! Paid ${event.amount_usdc} USDC.`);
  });

  agent.on("purchase_failed", (event) => {
    console.log(`❌ Purchase failed: ${event.error}`);
  });

  // 4. Run the loop
  await agent.run({
    task: "Buy 3 reports on trending layer-2 networks",
    sessionBudgetUsdc: 15, // Max 15 USDC
    maxPricePerReportUsdc: 5,
    maxPurchases: 3, // Stop after 3 buys
    executionMode: "live"
  });
}

main().catch(console.error);
