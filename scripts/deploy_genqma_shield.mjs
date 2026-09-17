// Deploy the fail-closed GenQMAShield verifier to GenLayer Studio Next.
// This script prints the address; it does not edit environment files.

import { createRequire } from "node:module";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(scriptDir, "..");

// Auto-load .env if present
const envPath = resolve(repoRoot, ".env");
if (existsSync(envPath)) {
  if (typeof process.loadEnvFile === "function") {
    process.loadEnvFile(envPath);
  } else {
    for (const rawLine of readFileSync(envPath, "utf8").split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line || line.startsWith("#") || !line.includes("=")) continue;
      const [key, ...rest] = line.split("=");
      if (!process.env[key.trim()]) {
        process.env[key.trim()] = rest.join("=").trim().replace(/^['"]|['"]$/g, "");
      }
    }
  }
}

const requireFromFrontend = createRequire(resolve(repoRoot, "frontend", "package.json"));
const genlayerModule = pathToFileURL(requireFromFrontend.resolve("genlayer-js")).href;
const chainsModule = pathToFileURL(requireFromFrontend.resolve("genlayer-js/chains")).href;
const { createAccount, createClient } = await import(genlayerModule);
const { studionet } = await import(chainsModule);

const privateKey = String(process.env.GENLAYER_PRIVATE_KEY || "").trim();
if (!privateKey) {
  throw new Error("GENLAYER_PRIVATE_KEY is required. Please set it in your .env file.");
}

const network = String(process.env.GENLAYER_NETWORK || "studio-next").trim().toLowerCase();
const defaultEndpoint = network.includes("studionet")
  ? "https://studio.genlayer.com/api"
  : "https://studio-next.genlayer.com/api";
const endpoint = String(process.env.GENLAYER_RPC_ENDPOINT || defaultEndpoint);

const isStudioNext = endpoint.includes("studio-next") || network.includes("next");
const chain = isStudioNext
  ? {
      ...studionet,
      id: 61997,
      isStudio: true,
      name: "GenLayer Studio Next",
      rpcUrls: { default: { http: [endpoint] } },
      blockExplorers: { default: { name: "Explorer", url: "https://explorer-studio-dev.genlayer.com" } },
    }
  : studionet;

console.log(`Targeting GenLayer Network: ${chain.name} (Chain ID ${chain.id}) at ${endpoint}`);

const contractPath = resolve(repoRoot, "contracts", "GenQMAShield.py");
const code = readFileSync(contractPath, "utf8");
const account = createAccount(privateKey.startsWith("0x") ? privateKey : `0x${privateKey}`);
const client = createClient({ chain, endpoint, account });

const fees = await client.estimateTransactionFees();
const transactionHash = await client.deployContract({ code, args: [], fees });
console.log("Deployment transaction:", transactionHash);

const receipt = await client.waitForTransactionReceipt({
  hash: transactionHash,
  status: "FINALIZED",
  retries: 200,
  interval: 3000,
});

const executionResult = receipt?.txExecutionResultName || receipt?.tx_execution_result_name;
if (executionResult !== "FINISHED_WITH_RETURN") {
  throw new Error(`Contract deployment failed: ${executionResult || "unknown execution result"}`);
}

const contractAddress =
  receipt?.txDataDecoded?.contractAddress ||
  receipt?.data?.contract_address ||
  receipt?.data?.contractAddress ||
  receipt?.contract_address ||
  receipt?.contractAddress ||
  receipt?.to_address;
if (!contractAddress) {
  throw new Error("Deployment finalized but the receipt contained no contract address");
}

console.log("GENLAYER_CONTRACT_ADDRESS=", contractAddress);
