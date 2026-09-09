# QMA Backend API Design Standards

Goal: Every new route automatically produces accurate, comprehensive OpenAPI/Scalar documentation **at code authoring time**, avoiding future large-scale cleanup sweeps. Documentation is a direct byproduct of disciplined code conventions, not an afterthought.

Core Principle: **Disciplined Code-First**. FastAPI auto-generates OpenAPI specs from Pydantic models. The 8 rules below are mandatory standards, enforced via automated tests (Rule 8) to prevent regression over time.

---

## 1. Never Return or Accept Bare `dict`

- Every route MUST declare `response_model=`.
- Every request body MUST be a typed Pydantic model, not `payload: dict`.
- Sole exception: Routes with `include_in_schema=False` (strict internal/debug endpoints). Even internal routes should use models when receiving external input.

**Rationale**: Retrofitting `response_model` on existing production endpoints is hazardous — FastAPI filters undeclared fields, so an incomplete model silently drops data. Declaring models from day one eliminates this risk.

## 2. All Response Models Inherit from Shared Base Classes

```python
# schemas/response_base.py
class ResponseModel(BaseModel):
    """Base for all response schemas. extra='allow' serves as a safety net
    (prevents runtime data loss on undeclared fields); it is NOT an excuse to omit known fields."""
    model_config = ConfigDict(extra="allow")
```

```python
# schemas/pagination.py
class Page(ResponseModel, Generic[T]):
    items: List[T]
    page: int
    page_size: int
    total: int
    has_next: bool
```

Rule: `extra="allow"` is a **fallback for dynamic upstream fields** (e.g., third-party Gateway or provider metadata), **not a shortcut for empty models**. Any known field in code must be explicitly typed.

## 3. Dicts Returned by ≥ 2 Routes Must Become Named Shared Models

If code is about to repeat:
```python
return {"symbol": ..., "tier": ..., "amount_usdc": ...}  # identical to another route
```
— Stop, create a named model (`PaymentEventItem`, `EntitlementItem`, etc.) in `schemas/domain/`, and import it.

## 4. Standard HTTP Status Code Mapping Table

| Code | Meaning in QMA System | Do NOT Use For |
|---|---|---|
| 400 | Malformed input / business rule violation (not Pydantic validation errors — those produce 422 automatically) | |
| 402 | Payment required before accessing content (report/full-report) | |
| 403 | Missing/invalid authentication token (access token, wallet token, admin token, internal secret) | **DO NOT use 401** — QMA standardizes all auth errors to 403, including empty tokens |
| 404 | Resource not found (invoice, provider, entitlement, settlement...) | |
| 409 | State conflict (leg already settled, settlement_id already claimed...) | |
| 429 | Rate limited — always use `RateLimitErrorResponse`, not generic `ErrorResponse` | |
| 500 | Unexpected internal server error | |
| 502 | Upstream error/timeout (Circle Gateway, relayer...) | |
| 503 | Feature unconfigured (missing secret, missing storage backend...) | |

Always consult this table before assigning status codes to ensure consistency.

## 5. All `HTTPException`s Must Route Through Global Exception Handlers

Never return manual error dictionaries via `JSONResponse({"error": ...})`. Always `raise HTTPException(status_code=X, detail="...")` — the global handler (`qma_http_exception_handler`) wraps it into the standard envelope: `{error, message, status_code, detail}`. This guarantees runtime responses match OpenAPI error schemas.

## 6. All Security Schemes Defined Centrally with Descriptions

All schemes reside in `core/security_schemes.py`, rather than ad-hoc `Header(default=None)` declarations across individual routers. Header naming convention: `X-QMA-{Purpose}-Token` (Title-Case). Every scheme description must detail:
1. How to obtain the token (issuing endpoint).
2. Whether query param fallback is supported.
3. Exact behavior when missing/invalid (status code, reduced payload vs outright rejection).

## 7. Route Docstrings Follow a Mandatory 3-Part Template

```python
@router.get(..., summary="<Single line summary for Scalar sidebar>")
def my_route(...):
    """
    <Caller identity and purpose.>

    Auth: <public / optional token (public vs private differences) / required token>.

    Edge-case: <at least 1 explicit edge behavior — sort order, default bounds, nullability conditions>.
    """
```

Complete this docstring at route creation time.

## 8. New Request/Response Fields Must Include `examples`

```python
symbol: str = Field(examples=["BTC_USDT"])
```
Avoid generic placeholders (`"string"`, `"example"`). Use valid real-world samples to power Scalar's "Test Request" interface.

---

## Enforcement Mechanism (CI Automated Verification)

Enforce API standards through automated CI tests inspecting the generated OpenAPI schema:

```python
# tests/test_api_design_standards.py
def test_every_public_route_has_response_model(app_openapi_schema):
    for path, methods in app_openapi_schema["paths"].items():
        for method, op in methods.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            responses = op.get("responses", {})
            ok = responses.get("200", {}).get("content") or responses.get("201", {}).get("content")
            assert ok, f"{method.upper()} {path} missing response schema for 2xx"

def test_every_route_has_description(app_openapi_schema):
    for path, methods in app_openapi_schema["paths"].items():
        for method, op in methods.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            assert op.get("summary"), f"{method.upper()} {path} missing summary"
            assert op.get("description"), f"{method.upper()} {path} missing description"

def test_every_429_uses_rate_limit_error_schema(app_openapi_schema):
    for path, methods in app_openapi_schema["paths"].items():
        for method, op in methods.items():
            resp_429 = op.get("responses", {}).get("429")
            if not resp_429:
                continue
            schema_ref = resp_429["content"]["application/json"]["schema"].get("$ref", "")
            assert "RateLimitErrorResponse" in schema_ref, f"{method.upper()} {path} 429 invalid schema"

def test_no_401_used_anywhere(app_openapi_schema):
    for path, methods in app_openapi_schema["paths"].items():
        for method, op in methods.items():
            assert "401" not in op.get("responses", {}), f"{method.upper()} {path} uses 401; QMA standard is 403"

def test_every_field_has_example(app_openapi_schema):
    schemas = app_openapi_schema["components"]["schemas"]
    missing = []
    for name, schema in schemas.items():
        for field, prop in schema.get("properties", {}).items():
            if "example" not in prop and "examples" not in prop and "$ref" not in prop:
                missing.append(f"{name}.{field}")
    assert not missing, f"Fields missing example: {missing}"
```

---

## Recommended Directory Structure

```
backend/app/schemas/
  response_base.py       # ResponseModel(extra=allow)
  pagination.py          # Page[T] generic
  errors.py              # ErrorResponse, RateLimitErrorResponse
  domain/                # Shared models (≥2 routes): PaymentEventItem, EntitlementItem, PayerBreakdownItem
  requests/              # Request models by domain
  responses/             # Response models by domain
backend/app/core/
  security_schemes.py    # All APIKeyHeader declarations + descriptions
  status_codes.md        # Reference table for status codes
  openapi_responses.py   # Helper applying responses={} from status code table
tests/
  test_api_design_standards.py   # CI enforcement test
```

---

## Pull Request Review Checklist (30 seconds)

- [ ] Declares `response_model=` and typed Pydantic request model (no bare `dict`)?
- [ ] `summary` + `description` follow the 3-part template (Purpose / Auth / Edge-case)?
- [ ] Status codes match the standard mapping table (no 401)?
- [ ] New fields declare valid `examples`?
- [ ] Reuses shared domain models instead of duplicate dict structures?
- [ ] `pytest tests/test_api_design_standards.py` passes?
