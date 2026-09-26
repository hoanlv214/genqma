import { encodeFunctionData, erc20Abi, maxUint256, pad, parseUnits } from "viem";
import { ARC_CHAIN } from "../config/network";

export const GATEWAY_MINTER_ABI = [
  {
    type: "function",
    name: "gatewayMint",
    inputs: [
      { name: "attestationPayload", type: "bytes" },
      { name: "signature", type: "bytes" },
    ],
    outputs: [],
    stateMutability: "nonpayable",
  },
] as const;

export const GATEWAY_WALLET_ABI = [
  {
    type: "function",
    name: "deposit",
    inputs: [
      { name: "token", type: "address" },
      { name: "amount", type: "uint256" },
    ],
    outputs: [],
    stateMutability: "nonpayable",
  },
] as const;

export const utf8ToHex = (value: string) => {
  const bytes = new TextEncoder().encode(String(value || ""));
  return `0x${Array.from(bytes).map((byte) => byte.toString(16).padStart(2, "0")).join("")}`;
};

export const randomHexBytes = (length: number) => {
  const bytes = new Uint8Array(length);
  const cryptoObj =
    typeof window !== "undefined" && window.crypto
      ? window.crypto
      : typeof globalThis !== "undefined" && (globalThis as any).crypto
        ? (globalThis as any).crypto
        : null;

  if (cryptoObj?.getRandomValues) {
    cryptoObj.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  return `0x${Array.from(bytes).map((byte) => byte.toString(16).padStart(2, "0")).join("")}`;
};

export const randomHexNonce = () => randomHexBytes(16);

export const addressToBytes32 = (address: string): `0x${string}` => {
  const clean = String(address || "").replace(/^0x/i, "").toLowerCase();
  if (!/^[0-9a-f]{40}$/.test(clean)) {
    throw new Error(`Invalid EVM address: ${address || "empty"}`);
  }
  return pad(`0x${clean}` as `0x${string}`, { size: 32, dir: "left" });
};

export const encodeGatewayMintCalldata = (attestationHex: string, signatureHex: string): `0x${string}` => {
  const normAtt = (String(attestationHex || "").startsWith("0x")
    ? String(attestationHex || "")
    : `0x${String(attestationHex || "")}`) as `0x${string}`;
  const normSig = (String(signatureHex || "").startsWith("0x")
    ? String(signatureHex || "")
    : `0x${String(signatureHex || "")}`) as `0x${string}`;

  return encodeFunctionData({
    abi: GATEWAY_MINTER_ABI,
    functionName: "gatewayMint",
    args: [normAtt, normSig],
  });
};

export const encodeErc20TransferCalldata = (recipient: string, amountDecimal: number, decimals = 6): `0x${string}` => {
  const normRecipient = (recipient.startsWith("0x") ? recipient : `0x${recipient}`) as `0x${string}`;
  const rawUnits = parseUnits(amountDecimal.toFixed(decimals), decimals);
  return encodeFunctionData({
    abi: erc20Abi,
    functionName: "transfer",
    args: [normRecipient, rawUnits],
  });
};

export const buildCreatorClaimMessage = ({
  claimant,
  providerIds,
  amountUsdc,
  nonce,
  issuedAt,
  network,
}: {
  claimant: string;
  providerIds: string[];
  amountUsdc: number;
  nonce: string;
  issuedAt: number;
  network?: string;
}) => {
  const providersValue = [...(providerIds || [])].sort().join(",");
  return [
    "QMA Creator Claim",
    `claimant: ${String(claimant || "").toLowerCase()}`,
    `providers: ${providersValue}`,
    `amount_usdc: ${Number(amountUsdc || 0).toFixed(6)}`,
    `nonce: ${nonce}`,
    `issued_at: ${Number(issuedAt)}`,
    `network: ${network || ARC_CHAIN.name}`,
  ].join("\n");
};

export interface GatewayWithdrawAddresses {
  gatewayContractAddress: string;
  gatewayMinterAddress: string;
  arcUsdcAddress: string;
  wallet: string;
}

export const buildGatewayWithdrawIntent = (
  amountUsdc: number,
  { gatewayContractAddress, gatewayMinterAddress, arcUsdcAddress, wallet }: GatewayWithdrawAddresses,
) => ({
  maxBlockHeight: maxUint256.toString(),
  maxFee: parseUnits("2.01", 6).toString(),
  spec: {
    version: 1,
    sourceDomain: 26,
    destinationDomain: 26,
    sourceContract: addressToBytes32(gatewayContractAddress),
    destinationContract: addressToBytes32(gatewayMinterAddress),
    sourceToken: addressToBytes32(arcUsdcAddress),
    destinationToken: addressToBytes32(arcUsdcAddress),
    sourceDepositor: addressToBytes32(wallet),
    destinationRecipient: addressToBytes32(wallet),
    sourceSigner: addressToBytes32(wallet),
    destinationCaller: addressToBytes32("0x0000000000000000000000000000000000000000"),
    value: parseUnits(Number(amountUsdc || 0).toFixed(6), 6).toString(),
    salt: randomHexBytes(32),
    hookData: "0x",
  },
});

export const buildGatewayWithdrawTypedData = (burnIntent: any) => ({
  domain: { name: "GatewayWallet", version: "1" },
  message: burnIntent,
  primaryType: "BurnIntent",
  types: {
    EIP712Domain: [
      { name: "name", type: "string" },
      { name: "version", type: "string" },
    ],
    TransferSpec: [
      { name: "version", type: "uint32" },
      { name: "sourceDomain", type: "uint32" },
      { name: "destinationDomain", type: "uint32" },
      { name: "sourceContract", type: "bytes32" },
      { name: "destinationContract", type: "bytes32" },
      { name: "sourceToken", type: "bytes32" },
      { name: "destinationToken", type: "bytes32" },
      { name: "sourceDepositor", type: "bytes32" },
      { name: "destinationRecipient", type: "bytes32" },
      { name: "sourceSigner", type: "bytes32" },
      { name: "destinationCaller", type: "bytes32" },
      { name: "value", type: "uint256" },
      { name: "salt", type: "bytes32" },
      { name: "hookData", type: "bytes" },
    ],
    BurnIntent: [
      { name: "maxBlockHeight", type: "uint256" },
      { name: "maxFee", type: "uint256" },
      { name: "spec", type: "TransferSpec" },
    ],
  },
});

export const getOnChainUsdcBalance = (walletStatus: any) => (
  walletStatus?.usdc?.formatted ?? walletStatus?.usdcBalance?.formatted ?? null
);

export const extractGatewayBalanceUsdc = (data: any): number | null => {
  const candidates = [
    data?.balance,
    data?.available,
    data?.amount,
    data?.balances?.[0]?.amount,
    data?.balances?.[0]?.balance,
    data?.sources?.[0]?.amount,
    data?.sources?.[0]?.balance,
    data?.data?.balances?.[0]?.amount,
  ];
  for (const c of candidates) {
    if (c === undefined || c === null) continue;
    const raw = Number(c);
    if (!Number.isFinite(raw)) continue;
    return raw > 1000 ? raw / 1_000_000 : raw;
  }
  return null;
};
