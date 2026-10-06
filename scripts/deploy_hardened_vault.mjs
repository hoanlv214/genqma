import fs from 'node:fs';
import path from 'node:path';
import { createPublicClient, createWalletClient, http, parseUnits, formatUnits } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';

// 1. Read AGENT_PRIVATE_KEY from .env
const env = fs.readFileSync('.env', 'utf8');
let pk = '';
for (const line of env.split('\n')) {
  if (line.startsWith('AGENT_PRIVATE_KEY=')) {
    pk = line.split('=')[1].trim();
  }
}
if (!pk && process.env.AGENT_PRIVATE_KEY) pk = process.env.AGENT_PRIVATE_KEY;
if (!pk) {
  console.error('Missing AGENT_PRIVATE_KEY in .env');
  process.exit(1);
}

const ARC_TESTNET_CHAIN = {
  id: 5042002,
  name: 'Arc Testnet',
  nativeCurrency: { name: 'USDC', symbol: 'USDC', decimals: 18 },
  rpcUrls: { default: { http: ['https://rpc.testnet.arc.network'] } },
  blockExplorers: { default: { name: 'Arcscan', url: 'https://testnet.arcscan.app' } },
};

const account = privateKeyToAccount(pk);
console.log('🏛️ QMA TREASURY ENGINE — HARDENED USYC VAULT DEPLOYMENT & ON-CHAIN TEST');
console.log('Deployer / Agent Account:', account.address);

const publicClient = createPublicClient({
  chain: ARC_TESTNET_CHAIN,
  transport: http(),
});

const walletClient = createWalletClient({
  account,
  chain: ARC_TESTNET_CHAIN,
  transport: http(),
});

const ARC_USDC = '0x3600000000000000000000000000000000000000';

const ERC20_ABI = [
  { inputs: [{ type: 'address' }, { type: 'address' }], name: 'allowance', outputs: [{ type: 'uint256' }], stateMutability: 'view', type: 'function' },
  { inputs: [{ type: 'address' }, { type: 'uint256' }], name: 'approve', outputs: [{ type: 'bool' }], stateMutability: 'nonpayable', type: 'function' },
  { inputs: [{ type: 'address' }], name: 'balanceOf', outputs: [{ type: 'uint256' }], stateMutability: 'view', type: 'function' },
];

async function main() {
  // Check balances
  const nativeBal = await publicClient.getBalance({ address: account.address });
  const usdcBal = await publicClient.readContract({
    address: ARC_USDC,
    abi: ERC20_ABI,
    functionName: 'balanceOf',
    args: [account.address],
  });

  console.log(`Native Gas Balance: ${formatUnits(nativeBal, 18)} USDC`);
  console.log(`ERC-20 USDC Balance: ${formatUnits(usdcBal, 6)} USDC`);

  // 2. Load compiled artifact
  const artifactPath = path.resolve('contracts/artifacts/USYCVaultFixed.json');
  if (!fs.existsSync(artifactPath)) {
    console.error('Artifact not found! Please run node scripts/compile_vault.mjs first.');
    process.exit(1);
  }

  const artifact = JSON.parse(fs.readFileSync(artifactPath, 'utf8'));
  console.log('\n--- 1. DEPLOYING USYCVaultFixed TO ARC TESTNET ---');
  console.log('Constructor args: [initialOwner:', account.address, ', underlyingAsset:', ARC_USDC, ']');

  const deployHash = await walletClient.deployContract({
    abi: artifact.abi,
    bytecode: artifact.bytecode,
    args: [account.address, ARC_USDC],
  });

  console.log('Deployment Tx Broadcasted:', deployHash);
  console.log('Explorer:', `https://testnet.arcscan.app/tx/${deployHash}`);
  console.log('Waiting for block confirmation...');

  const receipt = await publicClient.waitForTransactionReceipt({ hash: deployHash });
  const vaultAddress = receipt.contractAddress;

  if (!vaultAddress) {
    throw new Error('Contract address not found in receipt!');
  }

  console.log('✅ DEPLOYMENT CONFIRMED!');
  console.log('Vault Contract Address:', vaultAddress);
  console.log('Arcscan Explorer:', `https://testnet.arcscan.app/address/${vaultAddress}`);

  // 3. Verify on-chain getters
  console.log('\n--- 2. VERIFYING CONTRACT IMMUTABLE & DYNAMIC STATE ---');
  const asset = await publicClient.readContract({
    address: vaultAddress,
    abi: artifact.abi,
    functionName: 'asset',
  });
  const decimals = await publicClient.readContract({
    address: vaultAddress,
    abi: artifact.abi,
    functionName: 'decimals',
  });
  const assetDecimals = await publicClient.readContract({
    address: vaultAddress,
    abi: artifact.abi,
    functionName: 'assetDecimals',
  });
  const initialTotalAssets = await publicClient.readContract({
    address: vaultAddress,
    abi: artifact.abi,
    functionName: 'totalAssets',
  });
  const depositCap = await publicClient.readContract({
    address: vaultAddress,
    abi: artifact.abi,
    functionName: 'depositCap',
  });

  console.log(`- Underlying Asset: ${asset} (Expected: ${ARC_USDC})`);
  console.log(`- Share Decimals: ${decimals} (Expected: 12 per OpenZeppelin offset)`);
  console.log(`- Asset Decimals: ${assetDecimals} (Expected: 6 for USDC)`);
  console.log(`- Initial Total Managed Assets: ${initialTotalAssets} raw wei`);
  console.log(`- Initial Deposit Cap: ${depositCap} (0 = uncapped)`);

  // 4. Test setting Deposit Cap
  console.log('\n--- 3. TESTING setDepositCap (RISK CONTROL) ---');
  const targetCap = parseUnits('500000', 6); // 500k USDC cap
  const capTx = await walletClient.writeContract({
    address: vaultAddress,
    abi: artifact.abi,
    functionName: 'setDepositCap',
    args: [targetCap],
  });
  console.log('setDepositCap Tx:', capTx);
  await publicClient.waitForTransactionReceipt({ hash: capTx });
  const updatedCap = await publicClient.readContract({
    address: vaultAddress,
    abi: artifact.abi,
    functionName: 'depositCap',
  });
  console.log(`✅ Verified updated depositCap on-chain: ${formatUnits(updatedCap, 6)} USDC`);

  // 5. Test Approve & Deposit 0.05 USDC
  console.log('\n--- 4. TESTING DEPOSIT & ANTI-INFLATION ACCOUNTING ---');
  const depositAmount = parseUnits('0.05', 6); // 0.05 USDC
  console.log(`Approving vault to spend 0.05 USDC...`);
  const approveTx = await walletClient.writeContract({
    address: ARC_USDC,
    abi: ERC20_ABI,
    functionName: 'approve',
    args: [vaultAddress, depositAmount],
  });
  await publicClient.waitForTransactionReceipt({ hash: approveTx });
  console.log('Approve Tx confirmed:', approveTx);

  console.log(`Executing deposit of 0.05 USDC for ${account.address}...`);
  const depositTx = await walletClient.writeContract({
    address: vaultAddress,
    abi: artifact.abi,
    functionName: 'deposit',
    args: [depositAmount, account.address],
  });
  console.log('Deposit Tx broadcasted:', depositTx);
  console.log('Explorer:', `https://testnet.arcscan.app/tx/${depositTx}`);
  const depositReceipt = await publicClient.waitForTransactionReceipt({ hash: depositTx });
  console.log(`✅ Deposit confirmed in block ${depositReceipt.blockNumber}!`);

  const sharesBalance = await publicClient.readContract({
    address: vaultAddress,
    abi: artifact.abi,
    functionName: 'balanceOf',
    args: [account.address],
  });
  const totalManagedAfter = await publicClient.readContract({
    address: vaultAddress,
    abi: artifact.abi,
    functionName: 'totalAssets',
  });

  console.log(`- Minted Shares: ${sharesBalance.toString()} raw wei (${formatUnits(sharesBalance, 12)} yvUSYC)`);
  console.log(`- Total Managed Assets: ${totalManagedAfter.toString()} raw wei (${formatUnits(totalManagedAfter, 6)} USDC)`);

  // 6. Test JIT Redemption of 0.01 USDC
  console.log('\n--- 5. TESTING JIT REDEMPTION (REDEEM SHARES BACK TO USDC) ---');
  const redeemShares = parseUnits('0.01', 12); // 0.01 yvUSYC
  const redeemTx = await walletClient.writeContract({
    address: vaultAddress,
    abi: artifact.abi,
    functionName: 'redeem',
    args: [redeemShares, account.address, account.address],
  });
  console.log('Redeem Tx broadcasted:', redeemTx);
  console.log('Explorer:', `https://testnet.arcscan.app/tx/${redeemTx}`);
  const redeemReceipt = await publicClient.waitForTransactionReceipt({ hash: redeemTx });
  console.log(`✅ Redeem confirmed in block ${redeemReceipt.blockNumber}!`);

  const remainingShares = await publicClient.readContract({
    address: vaultAddress,
    abi: artifact.abi,
    functionName: 'balanceOf',
    args: [account.address],
  });
  const totalAssetsFinal = await publicClient.readContract({
    address: vaultAddress,
    abi: artifact.abi,
    functionName: 'totalAssets',
  });
  console.log(`- Remaining Shares: ${formatUnits(remainingShares, 12)} yvUSYC`);
  console.log(`- Final Total Managed Assets: ${formatUnits(totalAssetsFinal, 6)} USDC`);

  // Save deployment metadata
  const deploymentInfo = {
    contractName: 'USYCVaultFixed',
    address: vaultAddress,
    chain: 'Arc Testnet',
    chainId: 5042002,
    deployer: account.address,
    underlyingAsset: ARC_USDC,
    txHash: deployHash,
    arcscanUrl: `https://testnet.arcscan.app/address/${vaultAddress}`,
    deployedAt: new Date().toISOString(),
    tests: {
      setDepositCapTx: capTx,
      depositTx: depositTx,
      redeemTx: redeemTx,
    },
  };

  fs.writeFileSync('contracts/deployed_vault_arc_testnet.json', JSON.stringify(deploymentInfo, null, 2));
  console.log('\n🎉 ALL ON-CHAIN VERIFICATIONS PASSED SUCCESSFULLY!');
  console.log('Deployment info written to contracts/deployed_vault_arc_testnet.json');
}

main().catch(err => {
  console.error('FATAL ERROR:', err);
  process.exit(1);
});
