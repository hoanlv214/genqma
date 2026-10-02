# QMA Arc Testnet Payment

QMA now uses Circle x402 batching on Arc Testnet instead of a simulated payment.

## Services

Run both services:

```powershell
python qma\main.py
```

```powershell
cd qma\arc_gateway
npm install
npm start
```

Default URLs:

- QMA app: `http://127.0.0.1:8000`
- Arc Gateway sidecar: `http://127.0.0.1:3000`
- Circle facilitator: `https://gateway-api-testnet.circle.com`
- Arc explorer: `https://testnet.arcscan.app`

The React rebuild runs separately with Vite and uses the same backend payment
contract. Start it with `cd frontend && npm run dev`, then set
`VITE_QMA_API_BASE_URL` when the API is not same-origin. The legacy root HTML
pages and the rebuild frontend are different clients; a successful legacy page
load does not prove that the rebuild deployment is configured.

New buyer wallets can request Arc Testnet USDC from the Circle Faucet:

```text
https://faucet.circle.com/
```

Faucet USDC lands in the wallet first. QMA may still ask for an approve/deposit step because x402 spends from Circle Gateway balance, not directly from plain wallet balance.

## Environment

Optional overrides:

```env
QMA_PRICE_PREVIEW_USDC=0.002
QMA_PRICE_FULL_USDC=0.005
QMA_PAYMENT_AMOUNT_USDC=0.005
QMA_PLATFORM_TREASURY_ADDRESS=0x23e7c029a287a83d80b2e084e008211658dda11d
QMA_ARC_SELLER_ADDRESS=0x23e7c029a287a83d80b2e084e008211658dda11d
QMA_ARC_GATEWAY_URL=http://127.0.0.1:3000
QMA_CIRCLE_GATEWAY_API=https://gateway-api-testnet.circle.com
QMA_ARC_EXPLORER=https://testnet.arcscan.app
QMA_SPLIT_LEG_URL_SECRET=replace-with-split-url-secret
QMA_ARC_GATEWAY_INTERNAL_SECRET=replace-with-sidecar-internal-secret
GENLAYER_NETWORK=studionet
GENLAYER_RPC_ENDPOINT=https://studio.genlayer.com/api
GENLAYER_CONTRACT_ADDRESS=replace-after-deploy
GENLAYER_PRIVATE_KEY=backend-relayer-private-key
CIRCLE_CONSOLE_API_KEY=gateway-only-circle-api-key
CIRCLE_ENTITY_SECRET=gateway-only-circle-entity-secret
TREASURY_WALLET_ID=circle-wallet-id-matching-platform-treasury
QMA_GATEWAY_MAX_FEE_RAW=2010000
# SCA treasury only: pre-register this EOA as its Gateway delegate
QMA_GATEWAY_DELEGATE_WALLET_ID=circle-eoa-wallet-id
QMA_GATEWAY_DELEGATE_ADDRESS=0xregistered-gateway-delegate
```

New invoices route one x402 payment to the platform treasury so buyers sign once.
Direct-split invoice parsing remains only for older persisted invoices. Keep buyer,
creator, and treasury wallets separate during testing.

## Demo Flow

1. Open `http://127.0.0.1:8000` for the legacy shell, or the Vite dev URL for
   the rebuild.
2. Submit a QMA query as either Preview or Full Report to create a tier-bound invoice.
3. Click `Pay on Arc Testnet`.
4. Wallet switches/adds Arc Testnet and asks you to sign `TransferWithAuthorization`.
5. The Arc Gateway sidecar settles the signed authorization through Circle Gateway.
6. QMA verifies the returned settlement UUID through Circle's transfer API.
7. GenQMA generates the report once, hashes the exact payload, and submits that
   hash and a public claim manifest to `GenQMAShield`; paid analog rows are not
   placed in public transaction calldata.
8. The report unlocks only after a finalized GenLayer `VALID` verdict. Pending,
   rejected, expired, failed, or disputed invoices do not issue an access token.
9. `VALID` persists one idempotent Arc creator payout for the exact integer share;
   the platform remainder stays in treasury. `INVALID` persists one full refund
   to Circle's authoritative `fromAddress`. The sidecar resumes stored
   attestation/transaction checkpoints and polls Circle to a terminal state.

If your Circle Gateway balance on Arc is lower than the report price, the UI now asks wallet to send two real transactions first:

1. `approve(USDC, GatewayWallet, amount)`
2. `GatewayWallet.deposit(USDC, amount)`

This is required because x402 settlement spends from Circle Gateway balance, not directly from the wallet's plain on-chain USDC balance.

For UX, QMA preloads Gateway balance instead of depositing exactly one report at a time:

- Default deposit: `1.00 USDC`
- Default allowance approval: `10.00 USDC`
- Preview price: `0.002 USDC`
- Full report price: `0.005 USDC`

After the first preload, each report needs one x402 signature until the buyer's
Gateway balance drops below the report price. The backend relayer, not the buyer,
submits the separate GenLayer verification transaction.

The Arc gateway sidecar reads `amount_usdc` from the invoice resource URL, so the wallet signs the exact tier amount. QMA still verifies the Circle settlement amount against the server-side invoice before issuing access.

Invoices are provider-aware:

- `provider_id`: currently `funding_memory`
- `buyer_type`: `human` for UI purchases, `agent` for external API buyers
- `tier`: `preview` or `full`
- `query_hash`: exact market snapshot fingerprint

This prevents one settlement from being reused for another provider, another tier, or changed signal data.

GenLayer does not custody Arc USDC. An `INVALID` verdict blocks delivery and
schedules the refund, but the invoice becomes `refunded` only after the sidecar
records Circle transaction state `COMPLETE`. See `docs/agent/PAYMENT_FLOW.md`
for the exact state machine and retry/idempotency boundary.

The settlement UUID is immediate. The on-chain `submitBatch` transaction may appear several minutes later on testnet because Circle batches low-volume payments. Use:

```text
GET /api/v1/payment/settlement/{settlement_id}
```

to poll Circle status and resolve the Arcscan tx link when available.
