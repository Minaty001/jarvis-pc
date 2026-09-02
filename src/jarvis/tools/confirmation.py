"""Server-side action confirmation token architecture.

Provides HMAC-SHA256 token generation and verification for high-risk tool execution,
binding tool_name, hash_arguments(args), session_id, iat, exp, and nonce.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

TOKEN_TTL_SECONDS: int = 300  # 5 minutes


def hash_arguments(args: Any) -> str:
    """Deterministically hash tool arguments into a SHA-256 hex string."""
    if args is None:
        serialized = "null"
    else:
        try:
            serialized = json.dumps(args, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            serialized = str(args)

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def create_confirmation_token(
    tool_name: str,
    args: Any,
    session_id: str,
    secret: str,
    ttl: int = TOKEN_TTL_SECONDS,
) -> str:
    """Generate a signed confirmation token binding tool_name, args, session_id, and TTL."""
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
    sig = hmac.new(secret.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256).hexdigest()
    encoded_payload = base64.urlsafe_b64encode(payload_str.encode("utf-8")).decode("utf-8")
    return f"{encoded_payload}.{sig}"


def verify_confirmation_token(
    tool_name: str,
    args: Any,
    session_id: str,
    secret: str,
    token: str,
) -> bool:
    """Verify if a provided confirmation token is valid, unexpired, and matches expected HMAC-SHA256 signature."""
    if not token or not isinstance(token, str) or "." not in token:
        return False

    try:
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            return False

        encoded_payload, provided_sig = parts
        payload_str = base64.urlsafe_b64decode(encoded_payload.encode("utf-8")).decode("utf-8")
        expected_sig = hmac.new(secret.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_sig, provided_sig):
            return False

        payload = json.loads(payload_str)
        if time.time() > payload.get("exp", 0):
            return False

        if payload.get("tool") != tool_name:
            return False

        if payload.get("args_hash") != hash_arguments(args):
            return False

        if payload.get("session") != session_id:
            return False

        return True
    except Exception:
        return False
