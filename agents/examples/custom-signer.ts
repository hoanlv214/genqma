import { QmaAgent } from "../src/index.js";

async function main() {
  // 1. Create a custom signer for any EVM wallet (e.g. ethers.js, viem)
  const myCustomSigner = {
    walletAddress: "0xYourWalletAddress",
    async signLeg(resourceUrl: string) {
      // Create x402 payment header signature...
      const mockSignature = "Base64EncodedSignature...";
      return { paymentHeader: mockSignature };
    }
  };

  // 2. Initialize the Agent
  const agent = new QmaAgent({ signer: myCustomSigner });

  // 3. Run
  await agent.run({
    task: "Buy 1 random report",
    sessionBudgetUsdc: 5,
    maxPricePerReportUsdc: 5,
    maxPurchases: 1
  });
}

main().catch(console.error);
