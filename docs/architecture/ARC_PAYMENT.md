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
QMA_PRICE_PREVIEW_USDC=0.001
QMA_PRICE_FULL_USDC=0.005
QMA_PAYMENT_AMOUNT_USDC=0.005
QMA_PLATFORM_TREASURY_ADDRESS=0x23e7c029a287a83d80b2e084e008211658dda11d
QMA_ARC_SELLER_ADDRESS=0x23e7c029a287a83d80b2e084e008211658dda11d
QMA_ARC_GATEWAY_URL=http://127.0.0.1:3000
QMA_CIRCLE_GATEWAY_API=https://gateway-api-testnet.circle.com
QMA_ARC_EXPLORER=https://testnet.arcscan.app
QMA_SPLIT_LEG_URL_SECRET=replace-with-split-url-secret
QMA_ARC_GATEWAY_INTERNAL_SECRET=replace-with-sidecar-internal-secret
```

The platform treasury receives the platform leg of direct split payments. Keep buyer, creator, and platform treasury wallets separate during testing. `QMA_ARC_SELLER_ADDRESS` is kept as a backward-compatible alias for older single-seller payment flows.

## Demo Flow

1. Open `http://127.0.0.1:8000` for the legacy shell, or the Vite dev URL for
   the rebuild.
2. Submit a QMA query as either Preview or Full Report to create a tier-bound invoice.
3. Click `Pay on Arc Testnet`.
4. Wallet switches/adds Arc Testnet and asks you to sign `TransferWithAuthorization`.
5. The Arc Gateway sidecar settles the signed authorization through Circle Gateway.
6. QMA verifies the returned settlement UUID through Circle's transfer API.
7. The report unlocks only after the backend settlement policy accepts all
   required payment legs. A pending, expired, failed, or disputed invoice does
   not issue a new access token.

If your Circle Gateway balance on Arc is lower than the report price, the UI now asks wallet to send two real transactions first:

1. `approve(USDC, GatewayWallet, amount)`
2. `GatewayWallet.deposit(USDC, amount)`

This is required because x402 settlement spends from Circle Gateway balance, not directly from the wallet's plain on-chain USDC balance.

For UX, QMA preloads Gateway balance instead of depositing exactly one report at a time:

- Default deposit: `1.00 USDC`
- Default allowance approval: `10.00 USDC`
- Preview price: `0.001 USDC`
- Full report price: `0.005 USDC`

After the first preload, the next reports only need the final x402 signature until the buyer's Gateway balance drops below the report price.

The Arc gateway sidecar reads `amount_usdc` from the invoice resource URL, so the wallet signs the exact tier amount. QMA still verifies the Circle settlement amount against the server-side invoice before issuing access.

Invoices are provider-aware:

- `provider_id`: currently `funding_memory`
- `buyer_type`: `human` for UI purchases, `agent` for external API buyers
- `tier`: `preview` or `full`
- `query_hash`: exact market snapshot fingerprint

This prevents one settlement from being reused for another provider, another tier, or changed signal data.

The settlement UUID is immediate. The on-chain `submitBatch` transaction may appear several minutes later on testnet because Circle batches low-volume payments. Use:

```text
GET /api/v1/payment/settlement/{settlement_id}
```

to poll Circle status and resolve the Arcscan tx link when available.
