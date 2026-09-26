import { describe, expect, it } from "bun:test";
import {
  GATEWAY_MINTER_ABI,
  GATEWAY_WALLET_ABI,
  addressToBytes32,
  buildGatewayWithdrawIntent,
  buildGatewayWithdrawTypedData,
  encodeErc20TransferCalldata,
  encodeGatewayMintCalldata,
  extractGatewayBalanceUsdc,
  randomHexBytes,
  randomHexNonce,
} from "../gatewayCrypto";
import { toFunctionSelector } from "viem";

describe("Gateway Crypto & Calldata Encoding Suite", () => {
  it("1. GATEWAY_MINTER_ABI matches standard gatewayMint(bytes,bytes) selector 0x9fb01cc5", () => {
    const selector = toFunctionSelector(GATEWAY_MINTER_ABI[0]);
    expect(selector).toBe("0x9fb01cc5");
  });

  it("2. GATEWAY_WALLET_ABI matches standard deposit(address,uint256) selector", () => {
    const selector = toFunctionSelector(GATEWAY_WALLET_ABI[0]);
    expect(selector).toBe("0x47e7ef24");
  });

  it("3. addressToBytes32 standardizes address to 32-byte left-padded hex", () => {
    const addr = "0x1234567890123456789012345678901234567890";
    const bytes32 = addressToBytes32(addr);
    expect(bytes32).toBe("0x0000000000000000000000001234567890123456789012345678901234567890");
    expect(bytes32.length).toBe(66); // '0x' + 64 hex chars

    // Invalid address throws
    expect(() => addressToBytes32("0xinvalid")).toThrow();
  });

  it("4. encodeGatewayMintCalldata produces correct ABI calldata starting with 0x9fb01cc5", () => {
    const attestation = "0xaabbccddeeff";
    const signature = "0x112233445566";
    const calldata = encodeGatewayMintCalldata(attestation, signature);

    expect(calldata.startsWith("0x9fb01cc5")).toBe(true);
    // Attestation and signature data should be present within the encoded calldata
    expect(calldata.toLowerCase()).toContain("aabbccddeeff");
    expect(calldata.toLowerCase()).toContain("112233445566");
  });

  it("5. encodeErc20TransferCalldata produces valid ERC-20 transfer(address,uint256) calldata", () => {
    const recipient = "0x0000000000000000000000000000000000000001";
    const amountUsdc = 15.5; // 15.5 USDC = 15_500_000 micro-USDC (6 decimals)
    const calldata = encodeErc20TransferCalldata(recipient, amountUsdc);

    expect(calldata.startsWith("0xa9059cbb")).toBe(true);
    // Check recipient padded to 32 bytes
    expect(calldata).toContain("0000000000000000000000000000000000000000000000000000000000000001");
    // Check amount: 15500000 in hex is 0xec82e0
    expect(calldata.toLowerCase()).toContain("ec82e0");
  });

  it("6. randomHexBytes and randomHexNonce return valid hex strings with correct length", () => {
    const nonce = randomHexNonce();
    expect(nonce.startsWith("0x")).toBe(true);
    expect(nonce.length).toBe(34); // '0x' + 32 chars (16 bytes)

    const bytes32 = randomHexBytes(32);
    expect(bytes32.startsWith("0x")).toBe(true);
    expect(bytes32.length).toBe(66); // '0x' + 64 chars (32 bytes)
  });

  it("7. extractGatewayBalanceUsdc parses direct amounts, micro-USDC values, and nested structures", () => {
    expect(extractGatewayBalanceUsdc({ balance: 50.5 })).toBe(50.5);
    // Micro-USDC (value > 1000) converts automatically
    expect(extractGatewayBalanceUsdc({ balance: 50_000_000 })).toBe(50);
    // Nested array balances
    expect(extractGatewayBalanceUsdc({ balances: [{ amount: 25_000_000 }] })).toBe(25);
    expect(extractGatewayBalanceUsdc({})).toBeNull();
  });

  it("8. buildGatewayWithdrawIntent and buildGatewayWithdrawTypedData produce valid EIP-712 Gateway specs", () => {
    const wallet = "0x1111111111111111111111111111111111111111";
    const addresses = {
      gatewayContractAddress: "0x0077777d7EBA4688BDeF3E311b846F25870A19B9",
      gatewayMinterAddress: "0x0022222ABE238Cc2C7Bb1f21003F0a260052475B",
      arcUsdcAddress: "0x3600000000000000000000000000000000000000",
      wallet,
    };

    const intent = buildGatewayWithdrawIntent(10, addresses);
    expect(intent.spec.version).toBe(1);
    expect(intent.spec.sourceDomain).toBe(26); // Arc Testnet domain
    expect(intent.spec.destinationDomain).toBe(26);
    expect(intent.spec.value).toBe("10000000"); // 10 USDC

    const typedData = buildGatewayWithdrawTypedData(intent);
    expect(typedData.domain.name).toBe("GatewayWallet");
    expect(typedData.primaryType).toBe("BurnIntent");
    expect(typedData.types.BurnIntent).toBeDefined();
    expect(typedData.types.TransferSpec).toBeDefined();
  });
});
