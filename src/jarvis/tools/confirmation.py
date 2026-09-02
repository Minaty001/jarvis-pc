"""Server-side action confirmation token architecture.

Provides HMAC-SHA256 token generation and verification for high-risk tool execution,
binding tool_name, hash_arguments(args), and session_id.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def hash_arguments(args: Any) -> str:
    """Deterministically hash tool arguments into a SHA-256 hex string.

    Args:
        args: Tool argument payload (typically a dictionary or JSON-serializable structure).

    Returns:
        SHA-256 hex digest of the canonical JSON representation.
    """
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
) -> str:
    """Generate an HMAC-SHA256 confirmation token binding tool_name, args, and session_id.

    Args:
        tool_name: Name of the tool being invoked.
        args: Payload of tool arguments.
        session_id: Active session identifier.
        secret: HMAC secret key.

    Returns:
        HMAC-SHA256 hex string token.
    """
    args_hash = hash_arguments(args)
    msg = f"{tool_name}:{args_hash}:{session_id}"
    key = secret.encode("utf-8")
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_confirmation_token(
    tool_name: str,
    args: Any,
    session_id: str,
    secret: str,
    token: str,
) -> bool:
    """Verify if a provided confirmation token matches the expected HMAC-SHA256 digest.

    Args:
        tool_name: Name of the tool being invoked.
        args: Payload of tool arguments.
        session_id: Active session identifier.
        secret: HMAC secret key.
        token: Provided confirmation token to verify.

    Returns:
        True if token matches expected HMAC-SHA256 digest, False otherwise.
    """
    if not token or not isinstance(token, str):
        return False

    expected_token = create_confirmation_token(tool_name, args, session_id, secret)
    return hmac.compare_digest(expected_token, token)
