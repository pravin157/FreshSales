"""
Minimal OAuth 2.0 Authorization Server for Claude Team MCP connector.

Implements Authorization Code flow (no DB — uses HMAC-signed tokens so it
works on Vercel serverless without shared state).

Env vars:
    OAUTH_CLIENT_ID     — Client ID you register in Claude Team
    OAUTH_CLIENT_SECRET — Client secret you register in Claude Team
    JWT_SECRET          — Random secret for signing tokens (keep private)
    SERVER_URL          — Public base URL, e.g. https://your-app.vercel.app
    OAUTH_ADMIN_PIN     — PIN shown on the authorize page (prevents strangers
                          from granting access; set a 6-digit number)
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
import base64
from typing import Optional

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

_CLIENT_ID     = os.environ.get("OAUTH_CLIENT_ID", "claude-freshsales-client")
_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "")
_JWT_SECRET    = os.environ.get("JWT_SECRET", "change-me")
_SERVER_URL    = os.environ.get("SERVER_URL", "http://localhost:8000")
_ADMIN_PIN     = os.environ.get("OAUTH_ADMIN_PIN", "")

_CODE_TTL  = 600          # 10 min
_TOKEN_TTL = 7 * 24 * 3600  # 7 days


# ── HMAC-signed token helpers (stateless, no DB) ─────────────────────────────

def _sign(data: str) -> str:
    return hmac.new(_JWT_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()

def _encode(payload: str) -> str:
    sig = _sign(payload)
    return base64.urlsafe_b64encode(f"{payload}||{sig}".encode()).decode().rstrip("=")

def _decode(token: str) -> Optional[str]:
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded).decode()
        payload, sig = raw.rsplit("||", 1)
        if hmac.compare_digest(_sign(payload), sig):
            return payload
    except Exception:
        pass
    return None


# ── Auth codes ────────────────────────────────────────────────────────────────

def make_auth_code(redirect_uri: str, state: str) -> str:
    exp = int(time.time()) + _CODE_TTL
    return _encode(f"code|{redirect_uri}|{state}|{exp}")

def validate_auth_code(code: str) -> Optional[dict]:
    payload = _decode(code)
    if not payload:
        return None
    try:
        kind, redirect_uri, state, exp = payload.split("|", 3)
        if kind != "code" or int(exp) < int(time.time()):
            return None
        return {"redirect_uri": redirect_uri, "state": state}
    except Exception:
        return None


# ── Access tokens ─────────────────────────────────────────────────────────────

def make_access_token() -> str:
    exp = int(time.time()) + _TOKEN_TTL
    return _encode(f"access|{exp}")

def validate_access_token(token: str) -> bool:
    payload = _decode(token)
    if not payload:
        return False
    try:
        kind, exp = payload.split("|", 1)
        return kind == "access" and int(exp) >= int(time.time())
    except Exception:
        return False


# ── OAuth discovery endpoints ─────────────────────────────────────────────────

async def oauth_metadata(request: Request) -> JSONResponse:
    """GET /.well-known/oauth-authorization-server"""
    base = _SERVER_URL.rstrip("/")
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
    })

async def protected_resource_metadata(request: Request) -> JSONResponse:
    """GET /.well-known/oauth-protected-resource"""
    base = _SERVER_URL.rstrip("/")
    return JSONResponse({
        "resource": f"{base}/mcp",
        "authorization_servers": [base],
        "bearer_methods_supported": ["header"],
    })


# ── Authorization page ────────────────────────────────────────────────────────

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Authorize — Freshsales MCP</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:system-ui,sans-serif;background:#0f0f13;color:#e2e8f0;
        display:flex;align-items:center;justify-content:center;min-height:100vh}}
  .card{{background:#1a1a2e;border:1px solid #2d3748;border-radius:16px;
         padding:40px;max-width:420px;width:90%;text-align:center;
         box-shadow:0 24px 64px #0009}}
  .logo{{font-size:2.5rem;margin-bottom:12px}}
  h1{{font-size:1.5rem;color:#60a5fa;margin-bottom:8px}}
  .sub{{color:#94a3b8;font-size:.9rem;margin-bottom:24px}}
  .scope{{background:#0f172a;border-radius:10px;padding:14px;
          font-size:.85rem;color:#7dd3fc;margin-bottom:24px;text-align:left;line-height:1.8}}
  input[type=password]{{width:100%;padding:11px 14px;border-radius:8px;
    border:1px solid #334155;background:#0f172a;color:#e2e8f0;font-size:.95rem;
    margin-bottom:16px;outline:none;transition:border .2s}}
  input[type=password]:focus{{border-color:#60a5fa}}
  .btn{{width:100%;padding:13px;border:none;border-radius:8px;
        background:linear-gradient(135deg,#3b82f6,#6366f1);
        color:#fff;font-size:1rem;font-weight:600;cursor:pointer;transition:opacity .2s}}
  .btn:hover{{opacity:.85}}
  .err{{color:#f87171;font-size:.85rem;margin-top:12px}}
</style>
</head>
<body><div class="card">
  <div class="logo">🔗</div>
  <h1>Freshsales MCP</h1>
  <p class="sub">Claude Team is requesting access to your Freshsales CRM.</p>
  <div class="scope">
    ✅ Read &amp; write Contacts<br>
    ✅ Read &amp; write Deals &amp; Accounts<br>
    ✅ Manage Tasks, Notes, Appointments<br>
    ✅ Search &amp; bulk operations
  </div>
  <form method="POST">
    <input type="hidden" name="redirect_uri" value="{redirect_uri}">
    <input type="hidden" name="state" value="{state}">
    {pin_field}
    <button class="btn" type="submit">Authorize Access</button>
  </form>
  {error}
</div></body></html>"""

_PIN_INPUT = '<input type="password" name="pin" placeholder="Admin PIN" required autocomplete="off">'
_ERR_HTML  = '<p class="err">❌ Incorrect PIN — try again.</p>'


async def oauth_authorize(request: Request) -> Response:
    """GET/POST /oauth/authorize — consent page."""
    if request.method == "GET":
        p = dict(request.query_params)
        if p.get("client_id", "") != _CLIENT_ID:
            return JSONResponse({"error": "unauthorized_client"}, status_code=400)
        html = _HTML.format(
            redirect_uri=p.get("redirect_uri", ""),
            state=p.get("state", ""),
            pin_field=_PIN_INPUT if _ADMIN_PIN else "",
            error="",
        )
        return HTMLResponse(html)

    # POST — user submitted the form
    form = await request.form()
    redirect_uri = str(form.get("redirect_uri", ""))
    state        = str(form.get("state", ""))
    pin          = str(form.get("pin", ""))

    if _ADMIN_PIN and pin != _ADMIN_PIN:
        html = _HTML.format(
            redirect_uri=redirect_uri, state=state,
            pin_field=_PIN_INPUT, error=_ERR_HTML,
        )
        return HTMLResponse(html, status_code=401)

    code = make_auth_code(redirect_uri, state)
    sep  = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}code={code}&state={state}", status_code=302)


async def oauth_token(request: Request) -> JSONResponse:
    """POST /oauth/token — exchange auth code for access token."""
    form          = await request.form()
    grant_type    = str(form.get("grant_type", ""))
    code          = str(form.get("code", ""))
    client_id     = str(form.get("client_id", ""))
    client_secret = str(form.get("client_secret", ""))

    if grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
    if client_id != _CLIENT_ID or client_secret != _CLIENT_SECRET:
        return JSONResponse({"error": "invalid_client"}, status_code=401)
    if not validate_auth_code(code):
        return JSONResponse({"error": "invalid_grant"}, status_code=400)

    token = make_access_token()
    return JSONResponse({
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": _TOKEN_TTL,
    })
