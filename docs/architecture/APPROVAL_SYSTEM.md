# Approval System Architecture

## Risk Gate Policy
Before running task steps, `ApprovalEngine.filter_risky()` inspects the tool name and command parameters:
- **Low Risk** (`web_search`, `open_app`, `media_play`): Auto-approved.
- **High Risk** (`run_command` with `rm`, `sudo`, `format`, `curl -o`, `delete_file`): Suspends task in `WAITING_FOR_APPROVAL` state and notifies user via UI/Voice bridge.

## Human Decision Flow
- **Grant**: Step resumes execution immediately.
- **Deny**: Task transitions to `CANCELLED` state.
- **Timeout**: If no response within 300 seconds, the step automatically times out and denies execution for safety.
