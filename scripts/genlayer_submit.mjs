// Fail-closed relayer script for GenLayer Studio Next (Chain 61997)
// Uses genlayer-js which supports Consensus V2 with fees.

import { createRequire } from "node:module";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(scriptDir, "..");

// Auto-load .env
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
  console.error(JSON.stringify({ error: "GENLAYER_PRIVATE_KEY is required" }));
  process.exit(1);
}

const contractAddress = String(process.env.GENLAYER_CONTRACT_ADDRESS || "").trim();
if (!contractAddress) {
  console.error(JSON.stringify({ error: "GENLAYER_CONTRACT_ADDRESS is required" }));
  process.exit(1);
}

const endpoint = String(process.env.GENLAYER_RPC_ENDPOINT || "https://studio-next.genlayer.com/api").trim();
const isStudioNext = endpoint.includes("studio-next") || (process.env.GENLAYER_NETWORK || "").includes("next");

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

const account = createAccount(privateKey.startsWith("0x") ? privateKey : `0x${privateKey}`);
const client = createClient({ chain, endpoint, account });

async function main() {
  const mode = process.argv[2] || "write";

  if (mode === "read") {
    const invoiceId = process.argv[3];
    if (!invoiceId) throw new Error("invoice_id required for read");
    const raw = await client.readContract({
      address: contractAddress,
      functionName: "get_order",
      args: [invoiceId],
    });
    const hasOrder = raw && typeof raw === "string" && raw.trim() !== "";
    console.log(JSON.stringify({ success: true, order: hasOrder ? raw : null }));
    return;
  }

  if (mode === "write") {
    // Read payload from stdin as JSON
    const chunks = [];
    for await (const chunk of process.stdin) {
      chunks.push(chunk);
    }
    const rawInput = Buffer.concat(chunks).toString("utf8");
    const payload = JSON.parse(rawInput);

    const {
      invoice_id,
      buyer,
      provider,
      symbol,
      expected_anomaly,
      query_hash,
      report_hash,
      verification_manifest,
      evidence_url,
    } = payload;

    // Check if order already exists on contract
    const existingRaw = await client.readContract({
      address: contractAddress,
      functionName: "get_order",
      args: [invoice_id],
    });
    const hasExisting = existingRaw && typeof existingRaw === "string" && existingRaw.trim() !== "";
    if (hasExisting) {
      console.log(JSON.stringify({ success: true, order: existingRaw, existing: true }));
      return;
    }

    let txHash = payload.transaction_hash;
    if (!txHash) {
      const fees = await client.estimateTransactionFees();
      txHash = await client.writeContract({
        address: contractAddress,
        functionName: "submit_and_verify",
        args: [
          invoice_id,
          buyer,
          provider,
          symbol,
          expected_anomaly,
          query_hash,
          report_hash,
          verification_manifest,
          evidence_url,
        ],
        fees,
        value: 0n,
      });
    }

    // Fast check for immediate finalization (e.g. 2 retries, 1500ms -> max ~3s)
    let receipt = null;
    try {
      receipt = await client.waitForTransactionReceipt({
        hash: txHash,
        waitUntil: "finalized",
        retries: 2,
        interval: 1500,
      });
    } catch {
      receipt = null;
    }

    if (!receipt) {
      // Transaction broadcasted to Studio Next mempool/validators, consensus running asynchronously
      console.log(JSON.stringify({
        success: true,
        pending: true,
        transaction_hash: txHash,
        status: "VERIFICATION_PENDING",
        order: null,
      }));
      return;
    }

    const executionResult = receipt?.txExecutionResultName || receipt?.tx_execution_result_name;
    if (receipt && String(executionResult || "").toUpperCase() !== "FINISHED_WITH_RETURN") {
      // The transaction finalized but the genvm errored; no order will ever
      // appear for this hash. Report a hard failure so callers resubmit a
      // fresh verification instead of waiting forever.
      console.log(JSON.stringify({
        success: false,
        failed: true,
        transaction_hash: txHash,
        execution_result: executionResult,
        order: null,
      }, (k, v) => typeof v === "bigint" ? v.toString() : v));
      return;
    }
    const finalOrder = await client.readContract({
      address: contractAddress,
      functionName: "get_order",
      args: [invoice_id],
    });

    const hasOrder = finalOrder && typeof finalOrder === "string" && finalOrder.trim() !== "";
    console.log(JSON.stringify({
      success: true,
      pending: !hasOrder,
      transaction_hash: txHash,
      execution_result: executionResult,
      order: hasOrder ? finalOrder : null,
    }, (k, v) => typeof v === "bigint" ? v.toString() : v));
    return;
  }

  if (mode === "wait") {
    const txHash = process.argv[3];
    const invoiceId = process.argv[4];
    const receipt = await client.waitForTransactionReceipt({
      hash: txHash,
      waitUntil: "finalized",
      retries: 150,
      interval: 2000,
    });

    const finalOrder = invoiceId
      ? await client.readContract({
          address: contractAddress,
          functionName: "get_order",
          args: [invoiceId],
        })
      : null;
    const hasOrder = finalOrder && typeof finalOrder === "string" && finalOrder.trim() !== "";
    console.log(JSON.stringify({
      success: true,
      transaction_hash: txHash,
      execution_result: receipt?.txExecutionResultName || receipt?.tx_execution_result_name,
      order: hasOrder ? finalOrder : null,
    }, (k, v) => typeof v === "bigint" ? v.toString() : v));
    return;
  }

  throw new Error(`Unknown mode: ${mode}`);
}

main().catch((err) => {
  console.error(JSON.stringify({ error: err.message || String(err), stack: err.stack }));
  process.exit(1);
});
