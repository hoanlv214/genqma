// Actual external services; no stubbed HTTP, signatures, transfers or consensus.
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { GatewayClient } from '@circle-fin/x402-batching/client';

const base = 'http://127.0.0.1:8767';
const directory = process.env.QMA_DATA_DIR;
const checkpointPath = join(directory, 'live-checkpoint.json');
const resultPath = join(directory, 'live-result.json');
const checkpoint = existsSync(checkpointPath) ? JSON.parse(readFileSync(checkpointPath, 'utf8')) : {};
const result = { started_at: new Date().toISOString(), checks: [] };
function persist() { writeFileSync(checkpointPath, JSON.stringify(checkpoint, null, 2)); }
function record(name, data = {}) {
  result.checks.push({ name, ...data });
  writeFileSync(resultPath, JSON.stringify(result, null, 2));
  console.log(JSON.stringify({ name, ...data }));
}
async function call(path, body, headers = {}) {
  const response = await fetch(`${base}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(180000),
  });
  return { status: response.status, data: await response.json() };
}

try {
  const client = new GatewayClient({ chain: 'arcTestnet', privateKey: process.env.AGENT_PRIVATE_KEY });
  assert.equal(await client.publicClient.getChainId(), 5042002);
  const balances = await client.getBalances();
  record('actual_wallet_and_network', { address: client.address, chain_id: 5042002,
    wallet_raw: balances.wallet.balance.toString(), gateway_available_raw: balances.gateway.available.toString() });
  const query = { symbol: 'BTC_USDT', fundingRate: 0.0001 };
  for (const name of ['payment-signature', 'x-payment', 'authorization']) {
    const rejected = await call('/api/v1/providers/funding_memory/preview', query, { [name]: 'e30=' });
    assert.equal(rejected.status, 402);
    record('forged_header_rejected', { header: name, http_status: rejected.status });
  }
  const jobRequest = { provider_id: 'funding_memory', tier: 'preview', query, max_budget_usdc: 0.01, buyer_agent_id: 'financial-integrity-live' };
  if (!checkpoint.invoice) {
    const unpaid = await call('/api/v1/agent/jobs', jobRequest);
    assert.equal(unpaid.status, 402);
    const detail = unpaid.data.detail || unpaid.data.details;
    checkpoint.invoice = detail?.invoice || unpaid.data.invoice;
    assert.ok(checkpoint.invoice?.invoice_id, '402 must include a usable invoice');
    persist();
    record('unpaid_job_requires_payment', { http_status: 402 });
  }
  const invoice = checkpoint.invoice;
  const expectedRaw = BigInt(Math.round(Number(invoice.amount) * 1e6));
  assert.ok(expectedRaw > 0n && expectedRaw <= 10000n, 'Maximum test purchase is 0.01 USDC');
  assert.equal(new URL(invoice.arc_gateway_url).origin, 'http://127.0.0.1:8768');
  client.onBeforePaymentCreation(({ selectedRequirements: requirement }) => {
    assert.equal(requirement.network, 'eip155:5042002');
    assert.equal(BigInt(requirement.amount), expectedRaw);
    assert.equal(requirement.payTo.toLowerCase(), invoice.wallet_address.toLowerCase());
    assert.equal(requirement.extra.verifyingContract.toLowerCase(), '0x0077777d7eba4688bdef3e311b846f25870a19b9');
  });
  if (!checkpoint.settlement_id) {
    assert.ok(!checkpoint.payment_started, 'Previous payment result is uncertain; reconcile before any new charge');
    assert.ok(balances.gateway.available >= expectedRaw, 'Gateway balance insufficient; no deposit made automatically');
    checkpoint.payment_started = true;
    persist();
    const paid = await client.pay(invoice.arc_gateway_url);
    checkpoint.settlement_id = paid.data.settlementId || paid.data.settlement_id || paid.transaction;
    assert.ok(checkpoint.settlement_id);
    persist();
    record('circle_payment_accepted', { settlement_id: checkpoint.settlement_id, amount_raw: expectedRaw.toString() });
  } else {
    record('existing_circle_payment_reused', { settlement_id: checkpoint.settlement_id, amount_raw: expectedRaw.toString() });
  }
  const verified = await call(`/api/v1/payment/verify?invoice_id=${encodeURIComponent(invoice.invoice_id)}`, {
    invoice_secret: invoice.invoice_secret, settlement_id: checkpoint.settlement_id, payer_address: client.address,
  });
  record('verify_http', { http_status: verified.status, status: verified.data.status,
    verdict: verified.data.genlayer?.verdict });
  assert.equal(verified.status, 200, 'Real payment verification must succeed or remain explicitly pending');
  let state = verified.data;
  for (let attempt = 0; attempt < 12 && !['paid', 'refunded', 'verification_rejected'].includes(state.status); attempt++) {
    await new Promise(resolve => setTimeout(resolve, 5000));
    const current = await call(`/api/v1/payment/invoices/${invoice.invoice_id}/status?refresh=true`, undefined,
      { 'X-QMA-Invoice-Secret': invoice.invoice_secret });
    assert.equal(current.status, 200);
    state = current.data;
    record('actual_consensus_state', { status: state.status, verdict: state.genlayer?.verdict,
      transaction_hash: state.genlayer?.transaction_hash });
  }
  const second = await call('/api/v1/payment/invoice', { ...query, provider_id: 'funding_memory', tier: 'preview' });
  assert.equal(second.status, 200);
  const replay = await call(`/api/v1/payment/verify?invoice_id=${second.data.invoice_id}`, {
    invoice_secret: second.data.invoice_secret, settlement_id: checkpoint.settlement_id, payer_address: client.address,
  });
  assert.equal(replay.status, 409);
  record('actual_settlement_replay_rejected', { http_status: replay.status });
  const unauthorized = await call(`/api/v1/agent/jobs/job_${invoice.invoice_id}`);
  assert.ok([402, 403].includes(unauthorized.status));
  record('job_without_token_rejected', { http_status: unauthorized.status });
  if (state.status === 'paid') {
    assert.equal(state.genlayer?.verdict, 'VALID');
    const delivered = await call('/api/v1/agent/jobs', { ...jobRequest, invoice_id: invoice.invoice_id },
      { 'X-QMA-Access-Token': state.access_token });
    assert.equal(delivered.status, 200);
    assert.ok(Object.keys(delivered.data.report_payload).length);
    assert.equal(delivered.data.reputation_points_accrued, 0);
    const restored = await call(`/api/v1/agent/jobs/job_${invoice.invoice_id}`, undefined,
      { 'X-QMA-Access-Token': state.access_token });
    assert.equal(restored.status, 200);
    assert.deepEqual(restored.data.report_payload, delivered.data.report_payload);
    const tampered = await call('/api/v1/agent/jobs', { ...jobRequest, query: { ...query, fundingRate: 0.99 }, invoice_id: invoice.invoice_id },
      { 'X-QMA-Access-Token': state.access_token });
    assert.equal(tampered.status, 403);
    record('actual_paid_job_delivered', { verdict: delivered.data.consensus_verification.verdict,
      transaction_hash: state.genlayer?.transaction_hash, durable_job_get: restored.status, changed_query_rejected: tampered.status });
  } else {
    record('delivery_remains_closed', { status: state.status, verdict: state.genlayer?.verdict });
  }
  const refreshed = await call(`/api/v1/payment/invoices/${invoice.invoice_id}/status?refresh=true`, undefined,
    { 'X-QMA-Invoice-Secret': invoice.invoice_secret });
  assert.equal(refreshed.status, 200);
  record('arc_payout_state', { gateway_status: refreshed.data.gateway_status,
    status: refreshed.data.arc_settlement?.status, action: refreshed.data.arc_settlement?.action,
    transaction_hash: refreshed.data.arc_settlement?.transaction_hash });
  record('finished', { invoice_id: invoice.invoice_id, settlement_id: checkpoint.settlement_id, status: state.status });
} catch (error) {
  // SDK errors may contain signed authorizations or credentials; never print them.
  record('failed', { error_type: error?.constructor?.name || 'Error', code: error.code || null,
    cause_code: error.cause?.code, location: String(error.stack || '').split('\n').filter(line => line.includes('live_financial_buyer.mjs')).map(line => line.trim()),
    assertion: error.code === 'ERR_ASSERTION' ? error.message : undefined });
  process.exitCode = 1;
}
