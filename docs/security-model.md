# Security Model for JARVIS-PC

## Core Security Rules

### Rule 1: Single Execution Gate
No code path may execute a side-effecting, system, filesystem, or process tool directly. All execution MUST pass through `ToolExecutor.execute()`.

### Rule 2: Risk-Based Tool Classification
Every tool registered in `ToolRegistry` carries an explicit `RiskLevel`:
- **`SAFE`**: Read-only operations, system metrics, directory listings. Executed immediately.
- **`CONFIRM`**: Actions modifying user environment or launching apps. Requires cryptographic or server-side confirmation token.
- **`PRIVILEGED`**: Admin-level actions. Requires explicit user administrator workflow.
- **`FORBIDDEN`**: Dangerous actions (arbitrary shell, raw code injection). Explicitly denied.

### Rule 3: No Arbitrary Shell Execution
- No `run_shell` tool exposed to LLM or user.
- Subprocesses execute using `asyncio.create_subprocess_exec` with `shell=False` and explicit argument lists.
- Process sessions isolated via `start_new_session=True` so process groups can be cleanly reaped via `os.killpg`.

### Rule 4: Server-Side Confirmation Architecture
Client requests setting `"confirmed": true` are insufficient. Sensitive tools require a server-issued `ConfirmationRequest` and a signed `ConfirmationToken` hashing `(tool_name + arguments_hash + session_id)`. Modifying arguments invalidates the confirmation token.

### Rule 5: Non-Root Execution
- Application runs as unprivileged user via systemd user service (`~/.config/systemd/user/jarvis.service`).
- Device permission failures (e.g. `/dev/video0`) trigger diagnostic setup advice via `jarvis doctor`, never silent runtime `sudo usermod` or privilege escalation.
