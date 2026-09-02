# Task 4 Report: Remove Default Confirmation Secret & Add Token Expiry

- **Status**: DONE
- **Commit Hash**: `ded5269`

## Summary of Changes
1. Added security unit tests in `tests/security/test_confirmation_expiry.py` verifying token creation, TTL expiry, tamper detection, wrong tool rejection, and fail-closed behavior when no secret is configured.
2. Updated `src/jarvis/config/settings.py` to add `confirmation_secret: str | None = None`.
3. Rewrote `src/jarvis/tools/confirmation.py` with signed JSON payload structure containing `nonce`, `iat`, `exp` (300s TTL), and URL-safe base64 encoding.
4. Updated `ToolExecutor` in `src/jarvis/tools/executor.py` to accept `confirmation_secret` in constructor, remove default secret fallback `"jarvis-default-secret"`, and fail closed with `ToolDenied` if no secret is provided.
5. Updated `Application` in `src/jarvis/app/application.py` to inject `settings.confirmation_secret` into `ToolExecutor`.

## Verification
- Test command: `PYTHONPATH=src pytest tests/security/`
- Result: 41 passed in 2.51s.
