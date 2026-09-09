import {
  createPublicClient,
  decodeFunctionData,
  getAddress,
  hexToBigInt,
  http,
  parseAbi,
  type Hex,
} from "viem";

const RPC = process.env.ARC_TESTNET_RPC ?? "https://rpc.testnet.arc.network";
const GATEWAY_API =
  process.env.GATEWAY_API ?? "https://gateway-api-testnet.circle.com";
const SETTLEMENT_WINDOW_MS = 10_000;

const SUBMIT_BATCH_ABI = parseAbi([
  "function submitBatch(bytes calldataBytes, bytes signature)",
]);

export type BatchEntry = {
  address: `0x${string}`;
  delta: bigint;
  usdc: string;
};

export type NetTransfer = {
  from: `0x${string}`;
  to: `0x${string}`;
  usdc: string;
};

export type Settlement = {
  id: string;
  status: string;
  fromAddress: string;
  toAddress: string;
  amount: string;
  createdAt: string;
  updatedAt: string;
};

export async function decodeBatch(txHash: `0x${string}`) {
  const client = createPublicClient({ transport: http(RPC) });
  const tx = await client.getTransaction({ hash: txHash });
  if (!tx.to) throw new Error("contract creation, not a submitBatch");

  const decoded = decodeFunctionData({
    abi: SUBMIT_BATCH_ABI,
    data: tx.input,
  });
  if (decoded.functionName !== "submitBatch") {
    throw new Error(`not submitBatch (got ${decoded.functionName})`);
  }

  const [calldataBytesHex] = decoded.args;
  const calldata = (calldataBytesHex as Hex).slice(2);
  const word = (i: number) => calldata.slice(i * 64, (i + 1) * 64);
  const addrFromWord = (i: number) =>
    getAddress(("0x" + word(i).slice(24)) as `0x${string}`);
  const intFromWord = (i: number, signed = false) =>
    hexToBigInt(("0x" + word(i)) as Hex, { signed });

  const batchId = ("0x" + word(1)) as Hex;
  const domain = Number(intFromWord(2));
  const token = addrFromWord(3);
  const innerContract = addrFromWord(4);
  const count = Number(intFromWord(5));

  const entries: BatchEntry[] = [];
  for (let i = 0; i < count; i++) {
    const address = addrFromWord(6 + i * 2);
    const delta = intFromWord(7 + i * 2, true);
    entries.push({ address, delta, usdc: formatSignedUsdc(delta) });
  }

  const negatives = entries.filter((e) => e.delta < 0n);
  const positives = [...entries.filter((e) => e.delta > 0n)];
  const netTransfers: NetTransfer[] = [];
  for (const n of negatives) {
    const idx = positives.findIndex((p) => p.delta === -n.delta);
    if (idx >= 0) {
      netTransfers.push({
        from: n.address,
        to: positives[idx].address,
        usdc: formatSignedUsdc(-n.delta),
      });
      positives.splice(idx, 1);
    }
  }

  const blockNumber = tx.blockNumber ?? 0n;
  const block = await client.getBlock({ blockNumber });
  const blockTimestamp = Number(block.timestamp);
  const buyerAddrs = Array.from(
    new Set(
      entries.filter((e) => e.delta < 0n).map((e) => e.address.toLowerCase()),
    ),
  );
  const settlementsByBuyer: Record<string, Settlement[]> = {};

  await Promise.all(
    buyerAddrs.map(async (addr) => {
      try {
        const r = await fetch(`${GATEWAY_API}/v1/x402/transfers?from=${addr}`);
        if (!r.ok) return;
        const data = (await r.json()) as { transfers?: Settlement[] };
        const blockMs = blockTimestamp * 1000;
        settlementsByBuyer[addr] = (data.transfers ?? []).filter((t) => {
          if (t.status !== "completed" && t.status !== "confirmed") return false;
          return (
            Math.abs(new Date(t.updatedAt).getTime() - blockMs) <
            SETTLEMENT_WINDOW_MS
          );
        });
      } catch {
        // Keep decoding useful even when the facilitator lookup is unavailable.
      }
    }),
  );

  return {
    txHash,
    blockNumber,
    blockTimestamp,
    relayer: tx.from,
    contract: tx.to,
    batchId,
    domain,
    token,
    innerContract,
    entries,
    netTransfers,
    settlementsByBuyer,
  };
}

function formatSignedUsdc(v: bigint): string {
  const sign = v < 0n ? "-" : "";
  const abs = v < 0n ? -v : v;
  const whole = abs / 1_000_000n;
  const frac = (abs % 1_000_000n).toString().padStart(6, "0");
  return `${sign}${whole}.${frac}`;
}

if (process.argv[1]?.endsWith("decode-batch.ts")) {
  const txHash = process.argv[2] as `0x${string}` | undefined;
  if (!txHash?.startsWith("0x")) {
    console.error("usage: tsx decode-batch.ts <tx-hash>");
    process.exit(1);
  }
  decodeBatch(txHash)
    .then((decoded) => console.log(JSON.stringify(decoded, bigintJson, 2)))
    .catch((err) => {
      console.error(err);
      process.exit(1);
    });
}

function bigintJson(_key: string, value: unknown) {
  return typeof value === "bigint" ? value.toString() : value;
}
