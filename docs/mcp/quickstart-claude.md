# Quickstart — Claude.ai / Claude Desktop (5 minutes)

## What you need

- A browser wallet extension (Rabby, OKX Wallet, or MetaMask)
- ~5 USDC on **Arc Testnet** in your QMA Agent Wallet (you can fund it after connecting — the first free tools work without any funding)

## Steps

1. **Open the QMA connect page** (`https://<frontend>/connect`) and press
   **"Connect with Claude"** — it opens Claude's *Add custom connector* dialog
   with the name and URL pre-filled; press Continue/Connect there.
   (Manual path: Claude → Settings → Connectors → Add custom connector →
   Name `QMA`, URL `https://qma-api-7o9v.onrender.com/mcp`, or the deep link
   `https://claude.ai/new?modal=add-custom-connector&connectorName=QMA&connectorUrl=https%3A%2F%2Fqma-api-7o9v.onrender.com%2Fmcp#settings/customize-connectors`.)

2. **Claude opens the QMA consent page in your browser.** Connect your wallet
   (Rabby/OKX/MetaMask) and sign the one-time message when prompted. This
   signature proves you own the wallet — it grants nothing by itself.

3. **Set your spending caps** on the consent page:
   - *Max spend per report* (suggested `0.05`)
   - *Total budget for this connection* (suggested `5`)
   Then press **Connect wallet & authorize**. Your browser returns to Claude.

4. **Try it in Claude:**

   > "Scan QMA for the most extreme funding-rate anomaly right now."

   This uses the free scan tool. Then:

   > "Buy a preview historical analog report for the most extreme signal,
   > within my budget."

   Claude calls `qma_query_market_memory`; QMA runs a durable purchase session
   from your Agent Wallet and returns the purchased report in the chat.

## Managing the connection

- Review spend and balances any time: ask Claude *"check my QMA budget"* (free tool), or open
  `https://<frontend>/connect` with your wallet connected to list connections and **revoke** instantly.
- Withdraw remaining Agent Wallet funds from the QMA app (Agent Wallet panel → Withdraw).
- Caps too tight? Re-run the connector flow and re-approve — caps are clamped
  server-side to QMA ceilings.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Claude says "connector unreachable" | The backend must be deployed with the `/mcp` route; check `https://qma-api-7o9v.onrender.com/health` |
| `budget_exceeded` | Raise caps by re-approving, or top up the Agent Wallet |
| `purchase_not_completed` | The durable session keeps retrying server-side; ask again in ~1 minute or run *check my QMA budget* |
| Signature popup rejected | Nothing was authorized — retry the connector flow |
