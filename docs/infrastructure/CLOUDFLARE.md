# QMA Cloudflare Edge Protection

QMA uses payment to protect paid intelligence, but payment does not protect the infrastructure itself. Cloudflare should sit in front of the public domains to absorb scraping, bot bursts, and accidental API abuse before requests reach Vercel or Render.

Official Cloudflare references:

- Rate limiting rules: https://developers.cloudflare.com/waf/rate-limiting-rules/
- WAF custom rules: https://developers.cloudflare.com/waf/custom-rules/
- Proxied DNS records: https://developers.cloudflare.com/dns/proxy-status/

## Recommended topology

```text
qma.yourdomain.com
  -> Cloudflare proxied DNS
  -> Vercel frontend

api.qma.yourdomain.com
  -> Cloudflare proxied DNS
  -> Render FastAPI backend

gateway.qma.yourdomain.com
  -> Cloudflare proxied DNS
  -> Render Arc Gateway service
```

Keep the raw Render/Vercel URLs available for debugging, but use the Cloudflare domains in production demos.

For the rebuild preview, point the records to the rebuild services instead:
the Vercel project built from `frontend/vite-react-rebuild`,
`qma-api-rebuild.onrender.com`, and `qma-arc-gateway-rebuild.onrender.com`.
Do not mix a rebuild frontend with the legacy API/gateway without explicitly
checking the public contract and environment variables.

## DNS setup

1. Add your domain to Cloudflare.
2. Change nameservers at your domain registrar to Cloudflare nameservers.
3. Add records:

```text
CNAME qma      -> genqma.vercel.app              Proxied
CNAME api      -> qma-api.onrender.com              Proxied
CNAME gateway  -> qma-arc-gateway.onrender.com      Proxied
```

4. In Vercel, add `qma.yourdomain.com` as a project domain.
5. In Render, add `api.qma.yourdomain.com` and `gateway.qma.yourdomain.com` as custom domains if you want clean TLS hostnames.
6. Update frontend env/config:

```js
window.QMA_API_BASE_URL = "https://api.qma.yourdomain.com";
```

7. Update backend env:

```env
QMA_ARC_GATEWAY_URL=https://gateway.qma.yourdomain.com
```

## WAF custom rules

Start in `Log` or `Managed Challenge` mode, then tighten after observing real traffic.

### Block obvious non-browser junk from app pages

Expression:

```text
(http.request.uri.path in {"/" "/app" "/marketplace" "/user"} and not http.request.method in {"GET" "HEAD"})
```

Action:

```text
Block
```

### Challenge suspicious API bursts

Expression:

```text
(http.host eq "api.qma.yourdomain.com" and starts_with(http.request.uri.path, "/api/v1/"))
```

Action:

```text
Managed Challenge
```

Use this carefully. If it breaks autonomous agent/API demos, skip this rule for `/api/v1/payment/*` and agent clients.

## Rate limiting rules

Cloudflare rate limiting rules should be coarse edge protection. Backend rate limits in `main.py` remain the app-level source of truth.

Suggested rules:

| Path | Limit | Action |
| --- | ---: | --- |
| `/api/v1/payment/invoice` | 20 requests / minute / IP | Block or Managed Challenge |
| `/api/v1/payment/verify` | 8 requests / minute / IP | Block |
| `/api/v1/creators/apply` | 6 requests / minute / IP | Managed Challenge |
| `/api/v1/providers/*/live-anomalies` | 120 requests / minute / IP | Throttle/Block |
| `/api/v1/agent/recommendations` | 120 requests / minute / IP | Throttle/Block |
| `/api/v1/providers/*/preview` | 30 requests / minute / IP | Block |
| `/api/v1/providers/*/full-report` | 30 requests / minute / IP | Block |

## Backend rate limit env

The FastAPI backend now has an in-memory limiter:

```env
QMA_RATE_LIMIT_ENABLED=true
QMA_RATE_LIMIT_WINDOW_SECONDS=60
QMA_RATE_LIMIT_PAYMENT_VERIFY_PER_MIN=8
QMA_RATE_LIMIT_INVOICE_PER_MIN=20
QMA_RATE_LIMIT_REPORT_PER_MIN=30
QMA_RATE_LIMIT_PUBLIC_MARKET_PER_MIN=120
QMA_RATE_LIMIT_CREATOR_APPLY_PER_MIN=6
QMA_RATE_LIMIT_API_DEFAULT_PER_MIN=240
```

For multi-instance production, replace the in-memory bucket with Redis/Upstash so limits are shared across instances.

## Notes for agent buyers

Autonomous agents may not pass browser challenges. Keep API routes agent-friendly by relying on:

- backend rate limits
- invoice-bound x402 payment verification
- short-lived QMA access tokens
- wallet/provider/query fingerprint validation

Use Cloudflare challenges mainly for app pages and obvious abuse, not for the core paid API path unless you explicitly support agent challenge handling.
