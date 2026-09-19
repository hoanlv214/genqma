import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createPublicClient, http, formatUnits, parseUnits } from 'viem';

const ARC_TESTNET_CHAIN = {
  id: 5042002,
  name: 'Arc Testnet',
  nativeCurrency: { name: 'USDC', symbol: 'USDC', decimals: 18 },
  rpcUrls: { default: { http: ['https://rpc.testnet.arc.network'] } },
};

test('USYCVaultFixed Artifact Compilation Integrity', () => {
  const artifactPath = path.resolve('contracts/artifacts/USYCVaultFixed.json');
  assert.ok(fs.existsSync(artifactPath), 'Compiled artifact must exist');

  const artifact = JSON.parse(fs.readFileSync(artifactPath, 'utf8'));
  assert.equal(artifact.contractName, 'USYCVaultFixed');
  assert.ok(artifact.bytecode.length > 1000, 'Bytecode must be generated');

  const fnNames = artifact.abi.filter(item => item.type === 'function').map(item => item.name);
  assert.ok(fnNames.includes('depositCap'), 'depositCap getter must exist');
  assert.ok(fnNames.includes('setDepositCap'), 'setDepositCap function must exist');
  assert.ok(fnNames.includes('assetDecimals'), 'assetDecimals function must exist');
  assert.ok(fnNames.includes('sweepSurplus'), 'sweepSurplus function must exist');
  assert.ok(fnNames.includes('surplus'), 'surplus function must exist');
  assert.ok(fnNames.includes('fundYield'), 'fundYield function must exist');
  assert.ok(fnNames.includes('pause'), 'pause function must exist');
  assert.ok(fnNames.includes('unpause'), 'unpause function must exist');
});

test('USYCVaultFixed Live Deployed On-Chain State on Arc Testnet', async () => {
  const deploymentPath = path.resolve('contracts/deployed_vault_arc_testnet.json');
  assert.ok(fs.existsSync(deploymentPath), 'Deployment info must exist');

  const info = JSON.parse(fs.readFileSync(deploymentPath, 'utf8'));
  assert.equal(info.chain, 'Arc Testnet');
  assert.equal(info.chainId, 5042002);
  assert.ok(info.address.startsWith('0x'));

  const artifact = JSON.parse(fs.readFileSync('contracts/artifacts/USYCVaultFixed.json', 'utf8'));
  const client = createPublicClient({ chain: ARC_TESTNET_CHAIN, transport: http() });

  // 1. Check immutable addresses and decimals
  const asset = await client.readContract({
    address: info.address,
    abi: artifact.abi,
    functionName: 'asset',
  });
  assert.equal(asset.toLowerCase(), '0x3600000000000000000000000000000000000000');

  const decimals = await client.readContract({
    address: info.address,
    abi: artifact.abi,
    functionName: 'decimals',
  });
  assert.equal(decimals, 12, 'Vault share decimals must be 12 (6 asset + 6 offset)');

  const assetDecimals = await client.readContract({
    address: info.address,
    abi: artifact.abi,
    functionName: 'assetDecimals',
  });
  assert.equal(assetDecimals, 6, 'Underlying asset decimals must be 6 for USDC');

  // 2. Check deposit cap
  const cap = await client.readContract({
    address: info.address,
    abi: artifact.abi,
    functionName: 'depositCap',
  });
  assert.ok(cap > 0n, 'Deposit cap must be configured on-chain');

  // 3. Check position of deployer
  const bal = await client.readContract({
    address: info.address,
    abi: artifact.abi,
    functionName: 'balanceOf',
    args: [info.deployer],
  });
  assert.ok(bal >= 0n, 'Balance query must succeed');
});
