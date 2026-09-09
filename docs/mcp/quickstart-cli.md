# Quickstart — Claude Code, Cursor, LangChain (`@qma/mcp-server`)

Local MCP hosts speak stdio; the `@qma/mcp-server` package bridges them to the
hosted QMA MCP server using a **connection token** (30-day TTL). All spend
caps and revocation stay server-side — nothing sensitive lives on your machine
except the token itself.

## 1. Mint a connection token

The hosted OAuth flow with an empty `redirect_uri` returns the code directly
(the consent page shows it on screen):

```bash
# 1a. Register a local client
curl -s -X POST https://qma-api-7o9v.onrender.com/api/v1/oauth/register \
  -H "Content-Type: application/json" \
  -d '{"client_name":"my-local-agent"}'
# → {"client_id":"qma_..."}

# 1b. Compute a PKCE challenge (macOS/Linux)
VERIFIER=$(openssl rand -hex 48)
CHALLENGE=$(printf %s "$VERIFIER" | openssl dgst -sha256 -binary | base64 | tr '/+' '_-' | tr -d '=')

# 1c. Open the consent page in a browser, fill caps, approve:
#   https://<frontend>/connect?client_id=qma_...&code_challenge=$CHALLENGE
#   (use a URL-encoder or your own script; the page displays the code)

# 1d. Exchange code → 30-day token
curl -s -X POST https://qma-api-7o9v.onrender.com/api/v1/oauth/token \
  -H "Content-Type: application/json" \
  -d "{\"grant_type\":\"authorization_code\",\"code\":\"<CODE>\",\"client_id\":\"qma_...\",\"code_verifier\":\"$VERIFIER\"}"
# → {"access_token":"...","expires_in":2592000,"scope":"mcp"}
```

Windows PowerShell one-liners for the PKCE pair:

```powershell
$verifier = -join ((48..57)+(97..122) | Get-Random -Count 64 | % {[char]$_})
$sha = [System.Security.Cryptography.SHA256]::Create()
$challenge = [Convert]::ToBase64String($sha.ComputeHash([Text.Encoding]::ASCII.GetBytes($verifier))).TrimEnd('=').Replace('+','-').Replace('/','_')
```

## 2. Configure your host

**Claude Code** (`~/.claude.json` → `mcpServers`, or `claude mcp add`):

```json
{
  "mcpServers": {
    "qma": {
      "command": "npx",
      "args": ["-y", "@qma/mcp-server"],
      "env": {
        "QMA_MCP_URL": "https://qma-api-7o9v.onrender.com/mcp",
        "QMA_MCP_TOKEN": "<your 30-day connection token>"
      }
    }
  }
}
```

**Cursor** (`~/.cursor/mcp.json`) — same shape.

**LangChain / Python** (`langchain-mcp-adapters`):

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "qma": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@qma/mcp-server"],
        "env": {"QMA_MCP_TOKEN": "<token>"},
    }
})
```

## 3. Verify

```bash
QMA_MCP_TOKEN=<token> npx -y @qma/mcp-server
# stderr: qma-mcp: bridging stdio → https://qma-api-7o9v.onrender.com/mcp
```

Then in Claude Code: *"Scan QMA anomalies"* → *"check my QMA budget"*.

## Security notes

- The token spends from your Agent Wallet within your caps — treat it like a
  prepaid debit card, not a password. Revoke at `<frontend>/connect` any time.
- Keep it in environment config, never commit it. (Your shell history is the
  biggest leak vector; prefer a dotenv file outside the repo.)
