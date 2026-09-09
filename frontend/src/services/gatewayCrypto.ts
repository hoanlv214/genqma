export const utf8ToHex = (value: string) => {
  const bytes = new TextEncoder().encode(String(value || ""));
  return `0x${Array.from(bytes).map((byte) => byte.toString(16).padStart(2, "0")).join("")}`;
};

export const randomHexBytes = (length: number) => {
  const bytes = new Uint8Array(length);
  if (window.crypto?.getRandomValues) {
    window.crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  return `0x${Array.from(bytes).map((byte) => byte.toString(16).padStart(2, "0")).join("")}`;
};

export const randomHexNonce = () => randomHexBytes(16);

export const addressToBytes32 = (address: string) => {
  const clean = String(address || "").replace(/^0x/i, "").toLowerCase();
  if (!/^[0-9a-f]{40}$/.test(clean)) {
    throw new Error(`Invalid EVM address: ${address || "empty"}`);
  }
  return `0x${clean.padStart(64, "0")}`;
};

export const encodeGatewayMintCalldata = (attestationHex: string, signatureHex: string) => {
  const att = String(attestationHex || "").replace(/^0x/i, "").toLowerCase();
  const sig = String(signatureHex || "").replace(/^0x/i, "").toLowerCase();
  const attLen = att.length / 2;
  const sigLen = sig.length / 2;
  const offset1 = 64;
  const attPaddedLen = Math.ceil(attLen / 32) * 32;
  const offset2 = 64 + 32 + attPaddedLen;
  const toWord = (value: number) => value.toString(16).padStart(64, "0");
  const padTo32 = (hex: string) => hex.padEnd(Math.ceil(hex.length / 64) * 64, "0");
  return `0x9fb01cc5${toWord(offset1)}${toWord(offset2)}${toWord(attLen)}${padTo32(att)}${toWord(sigLen)}${padTo32(sig)}`;
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
    `network: ${network || "Arc Testnet"}`,
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
  maxBlockHeight: "115792089237316195423570985008687907853269984665640564039457584007913129639935",
  maxFee: String(Math.round(2.01 * 1_000_000)),
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
    value: String(Math.round(Number(amountUsdc || 0) * 1_000_000)),
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
