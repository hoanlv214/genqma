# QMA ast-grep Rules

Use these with `sg scan -r <rule-file>` from the repo root.

- `python-fastapi-app-route.yml`: finds direct `@app.get/post/put/delete` routes that should move into `backend/app/api/v1/endpoints/*`.
- `python-save-invoice-call.yml`: finds invoice persistence calls for payment state-machine audits.
- `python-save-payment-ledger-call.yml`: finds ledger persistence calls for idempotency and fallback audits.
- `python-payment-required-exception.yml`: finds HTTP 402 gates that must keep frontend-compatible response shapes.
- `python-state-invoices-direct-write.yml`: finds direct writes to `state.invoices_db`.
- `python-requests-post-call.yml`: finds outgoing HTTP POST calls; route/app layers should move these into service/client modules.

For one-off structural searches, prefer direct patterns, for example:

```powershell
sg -p 'save_invoice($INVOICE)' -l python .
sg -p 'invoice["status"] = $STATUS' -l python main.py backend/
sg -p 'app.include_router($ROUTER)' -l python main.py backend/
```
