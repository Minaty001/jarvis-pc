# Task 4 Brief: Remove default confirmation secret & add token expiry

**Fixes issues:** #10 (dangerous fallback secret), #11 (no token expiry)

## Problem

1. `ToolExecutor` uses `effective_secret = secret or "jarvis-default-secret"` — a predictable secret.
2. Confirmation tokens have no expiry, nonce, or issued_at. They're valid forever.

## Target

1. Executor fails closed if no secret is configured.
2. Tokens include `nonce`, `issued_at`, `expires_at` (default 300s TTL).
3. Verification rejects expired tokens.
4. `Settings` has `confirmation_secret` field loaded from `JARVIS_CONFIRMATION_SECRET` env var.

## Files to modify

### 1. MODIFY `src/jarvis/config/settings.py`

Add field:
```python
confirmation_secret: str | None = None
```

### 2. REWRITE `src/jarvis/tools/confirmation.py`

New token format uses JSON payload:
```python
import hashlib, hmac, json, time, uuid
from typing import Any

TOKEN_TTL_SECONDS = 300  # 5 minutes

def hash_arguments(args: Any) -> str:
    if args is None:
        serialized = "null"
    else:
        try:
            serialized = json.dumps(args, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            serialized = str(args)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def create_confirmation_token(tool_name: str, args: Any, session_id: str, secret: str, ttl: int = TOKEN_TTL_SECONDS) -> str:
    now = time.time()
    payload = {
        "v": 1,
        "tool": tool_name,
        "args_hash": hash_arguments(args),
        "session": session_id,
        "nonce": uuid.uuid4().hex,
        "iat": now,
        "exp": now + ttl,
    }
    payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    sig = hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
    # Token = base64(payload) + "." + signature
    import base64
    encoded_payload = base64.urlsafe_b64encode(payload_str.encode()).decode()
    return f"{encoded_payload}.{sig}"


def verify_confirmation_token(tool_name: str, args: Any, session_id: str, secret: str, token: str) -> bool:
    if not token or not isinstance(token, str) or "." not in token:
        return False
    try:
        import base64
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            return False
        encoded_payload, provided_sig = parts
        payload_str = base64.urlsafe_b64decode(encoded_payload).decode()
        # Verify HMAC
        expected_sig = hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, provided_sig):
            return False
        payload = json.loads(payload_str)
        # Check expiry
        if time.time() > payload.get("exp", 0):
            return False
        # Check tool and args match
        if payload.get("tool") != tool_name:
            return False
        if payload.get("args_hash") != hash_arguments(args):
            return False
        if payload.get("session") != session_id:
            return False
        return True
    except Exception:
        return False
```

### 3. MODIFY `src/jarvis/tools/executor.py`

Replace the confirmation token section:
```python
if tool.risk == RiskLevel.CONFIRM:
    if not confirmation_token:
        raise ConfirmationRequired(f"Execution of tool '{target_name}' requires explicit user confirmation.")
    confirmation_secret = secret or self._confirmation_secret
    if not confirmation_secret:
        raise ToolDenied("Confirmation secret is not configured. Cannot verify confirmation tokens.")
    if not verify_confirmation_token(target_name, verify_args, context.session_id, confirmation_secret, confirmation_token):
        raise ToolDenied("Invalid, expired, or tampered confirmation token")
```

Add `_confirmation_secret` to `__init__`:
```python
def __init__(self, registry=None, rate_limiter=None, audit_logger=None, confirmation_secret=None):
    ...
    self._confirmation_secret = confirmation_secret
```

Remove the `effective_secret = secret or "jarvis-default-secret"` line.

### 4. WRITE TEST `tests/security/test_confirmation_expiry.py`

```python
import time
import pytest
from jarvis.tools.confirmation import create_confirmation_token, verify_confirmation_token

def test_valid_token_accepted():
    token = create_confirmation_token("tool", {"a": 1}, "s1", "secret")
    assert verify_confirmation_token("tool", {"a": 1}, "s1", "secret", token)

def test_expired_token_rejected(monkeypatch):
    token = create_confirmation_token("tool", {"a": 1}, "s1", "secret", ttl=1)
    # Fast-forward time
    monkeypatch.setattr("jarvis.tools.confirmation.time.time", lambda: time.time() + 10)
    # Need to also patch time in verify
    import jarvis.tools.confirmation as conf
    original_time = time.time
    monkeypatch.setattr(conf, "time", type("FakeTime", (), {"time": staticmethod(lambda: original_time() + 10)})())
    assert not verify_confirmation_token("tool", {"a": 1}, "s1", "secret", token)

def test_wrong_tool_rejected():
    token = create_confirmation_token("tool_a", {"a": 1}, "s1", "secret")
    assert not verify_confirmation_token("tool_b", {"a": 1}, "s1", "secret", token)

def test_tampered_token_rejected():
    token = create_confirmation_token("tool", {"a": 1}, "s1", "secret")
    assert not verify_confirmation_token("tool", {"a": 1}, "s1", "secret", token + "x")

def test_missing_secret_fails_closed():
    from jarvis.tools.executor import ToolExecutor, ToolDenied
    from jarvis.tools.registry import ToolRegistry
    from jarvis.tools.base import ToolDefinition
    from jarvis.tools.policy import RiskLevel
    from jarvis.cognitive.context import ExecutionContext
    import asyncio

    registry = ToolRegistry()
    async def dummy(): return "ok"
    registry.register(ToolDefinition("risky", RiskLevel.CONFIRM, frozenset(), dummy))
    executor = ToolExecutor(registry)  # No confirmation_secret
    ctx = ExecutionContext("s1", "t1", "u1", "r1")

    with pytest.raises((ToolDenied, Exception)):
        asyncio.get_event_loop().run_until_complete(
            executor.execute("risky", context=ctx, confirmation_token="fake", arguments={})
        )
```

## Execution steps

1. Write test `tests/security/test_confirmation_expiry.py`
2. Run: `PYTHONPATH=src pytest tests/security/test_confirmation_expiry.py`
3. Modify `src/jarvis/config/settings.py`, `src/jarvis/tools/confirmation.py`, `src/jarvis/tools/executor.py`
4. Update Application in `src/jarvis/app/application.py` to pass `confirmation_secret=self.settings.confirmation_secret` to ToolExecutor
5. Run test again
6. Run broader security suite: `PYTHONPATH=src pytest tests/security/`
7. Fix any test regressions (existing confirmation tests need updating for new token format)
8. Commit: `git add -A && git commit -m "security(confirmation): add token expiry/nonce, remove dangerous default secret, fail closed"`
9. Write report to `/home/shanu/Desktop/jarvis-pc/.superpowers/sdd/2026-09-03-composition-root-plan/task-4-report.md`
