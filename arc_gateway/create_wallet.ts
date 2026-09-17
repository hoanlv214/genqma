import { initiateDeveloperControlledWalletsClient } from "@circle-fin/developer-controlled-wallets";
import * as path from "node:path";
import { loadEnvFile } from "./load-env.js";

const envPath = path.resolve(process.cwd(), "..", ".env");
loadEnvFile(envPath);

const apiKey = process.env.CIRCLE_CONSOLE_API_KEY;
const entitySecret = process.env.CIRCLE_ENTITY_SECRET;

if (!apiKey || !entitySecret) {
  throw new Error("CIRCLE_CONSOLE_API_KEY and CIRCLE_ENTITY_SECRET are required.");
}

const circleClient = initiateDeveloperControlledWalletsClient({
  apiKey,
  entitySecret,
});

async function main() {
  console.log("Creating Wallet Set...");
  const walletSetResponse = await circleClient.createWalletSet({
    name: "Treasury WalletSet",
  });
  const walletSetId = walletSetResponse.data?.walletSet?.id;
  console.log(`Wallet Set created: ${walletSetId}`);

  if (!walletSetId) throw new Error("Failed to create Wallet Set");

  console.log("Creating SCA Wallet on ARC-TESTNET...");
  const walletsResponse = await circleClient.createWallets({
    accountType: "SCA",
    blockchains: ["ARC-TESTNET"],
    count: 1,
    walletSetId,
  });

  const wallets = walletsResponse.data?.wallets ?? [];
  const wallet = wallets[0];
  
  console.log(`✅ Treasury Wallet Created!`);
  console.log(`Wallet ID: ${wallet?.id}`);
  console.log(`Address: ${wallet?.address}`);
  console.log(`Type: ${wallet?.accountType}`);
  
  import("node:fs").then(fs => {
    fs.appendFileSync(envPath, `\nTREASURY_WALLET_ID=${wallet?.id}\n`);
    console.log("Added TREASURY_WALLET_ID to .env");
  });
}

main().catch(console.error);
