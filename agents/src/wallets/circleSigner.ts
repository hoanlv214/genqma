import { spawn } from "node:child_process";
import type { AgentPaymentSigner, PaymentSettlement } from "./signer.js";
import { createPaymentExecutor, type PaymentExecutor } from "../executor/paymentExecutor.js";

export interface CircleAgentWalletExecutorOptions {
  address: string;
  chain: string;
  runCircle?: CircleCommandRunner;
}

export type CircleCommandRunner = (args: string[]) => Promise<unknown>;

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function settlementBody(value: unknown): Record<string, unknown> {
  const root = record(value);
  return record(root.data) && Object.keys(record(root.data)).length ? record(root.data) : root;
}

function circleCliBinary(): string {
  return process.platform === "win32" ? "circle.cmd" : "circle";
}

function quoteWindowsArg(value: string): string {
  if (value.includes('"') || value.includes('%')) throw new Error("Circle CLI argument contains an unsupported character.");
  return `"${value}"`;
}

function defaultRunCircle(args: string[]): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const isWindows = process.platform === "win32";
    const child = isWindows
      ? spawn(process.env.ComSpec || "cmd.exe", [
        "/d", "/s", "/c", [circleCliBinary(), ...args.map(quoteWindowsArg)].join(" "),
      ], { windowsVerbatimArguments: true, stdio: ["ignore", "pipe", "pipe"], env: process.env })
      : spawn(circleCliBinary(), args, { stdio: ["ignore", "pipe", "pipe"], env: process.env });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk: Buffer) => { stdout += chunk.toString(); });
    child.stderr.on("data", (chunk: Buffer) => { stderr += chunk.toString(); });
    child.once("error", reject);
    child.once("exit", (code) => {
      if (code !== 0) {
        reject(new Error(`Circle CLI failed (${code}): ${(stderr || stdout).trim().slice(0, 500) || "unknown error"}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch {
        reject(new Error(`Circle CLI returned non-JSON output: ${stdout.trim().slice(0, 500)}`));
      }
    });
  });
}

/** Circle Agent Wallet adapter for the shared sequential executor. */
export function createCircleAgentWalletSigner(options: CircleAgentWalletExecutorOptions): AgentPaymentSigner {
  const address = text(options.address);
  const chain = text(options.chain);
  if (!address) throw new Error("Circle Agent Wallet address is required.");
  if (!chain) throw new Error("Circle Agent Wallet chain is required.");
  const runCircle = options.runCircle || defaultRunCircle;

  return {
    walletAddress: address,
    async payLeg({ resourceUrl, amountUsdc }): Promise<PaymentSettlement> {
      if (!amountUsdc) throw new Error("Circle Agent Wallet payment requires a positive leg amount.");
      const result = await runCircle([
        "services", "pay", resourceUrl,
        "--address", address,
        "--chain", chain,
        "--max-amount", String(amountUsdc),
        "--output", "json",
        "--quiet",
      ]);
      return settlementBody(result);
    },
  };
}

export function createCircleAgentWalletExecutor(options: CircleAgentWalletExecutorOptions): PaymentExecutor {
  const signer = createCircleAgentWalletSigner(options);
  return createPaymentExecutor(signer);
}
