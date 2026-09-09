# QMA Funding Readiness

Funding Readiness is a diagnostic layer before QMA's payment engine. It does not add a new payment method and it does not change invoice creation, Circle Gateway settlement, x402 signing, backend verification, or report unlock.

The purpose is to show how an autonomous buyer gets ready to pay:

```text
External USDC
  -> Circle CCTP / Arc App Kit
  -> Arc Wallet
  -> Circle Gateway
  -> x402
  -> Wallet-bound QMA Paid Report
```

## Why This Layer Exists

QMA spends from Circle Gateway during checkout. A wallet can hold Arc USDC and still be unable to complete an x402 payment if its Gateway balance is too low.

Funding Readiness answers:

- Is a wallet connected?
- Is the wallet on Arc Testnet?
- Does the Arc wallet have USDC?
- Does Circle Gateway already have enough balance?
- Should the user get testnet USDC, bridge USDC into Arc, or continue to checkout for a Gateway Deposit prompt?

The browser modal is read-only by default. It never automatically bridges, deposits, or switches networks. Any network switch must be an explicit user action.

## Circle And Arc Roles

Circle CCTP and Arc App Kit are funding infrastructure before payment. They are the route for moving external USDC into an Arc wallet.

Circle Gateway is the payment balance QMA actually spends from during x402 checkout. If Gateway is low but the wallet has enough Arc USDC, the existing payment flow prompts the user to deposit into Gateway.

Arc Testnet is the settlement network used by the wallet and Gateway integration.

## Browser Judge Mode Vs Autonomous Agent

Browser Judge Mode intentionally keeps private keys inside the connected wallet. QMA can rank live opportunities, choose an affordable report, and create an agent invoice, but the judge wallet confirms x402 signing.

Full autonomous payment runs outside the browser in the CLI/server agent with an isolated `AGENT_PRIVATE_KEY`.

Both modes share the same payment engine:

```text
Discover Signal
  -> Funding Readiness
  -> Gateway Balance
  -> x402 Payment
  -> Wallet-bound Paid Report
```

## Out Of Scope

Funding Readiness does not:

- integrate the App Kit SDK
- execute CCTP bridging
- add Circle Wallets custody
- add Solana frontend support
- modify x402 settlement
- modify Circle Gateway deposit or withdrawal logic
