# JARVIS — What It Can Do

> Capability report, 2026-09-05. JARVIS is a local, single-user AI assistant built
> as a ReAct agent: it *reasons* with an LLM and *acts* through a guarded tool box.

## 1. Talk to it

- Text conversation in a terminal (`jarvis run`) — with a JARVIS butler persona.
- Voice conversation (`jarvis voice session`): say "hey jarvis" as the wake word,
  ask something, hear the reply spoken back.
- TTS / STT on demand: `jarvis voice speak "..."`, `jarvis voice listen`.
- Remote access over HTTP: chat and tool-execution endpoints (`/chat`, `/execute`),
  auth-protected, rate-limited, with per-call permission enforcement.

## 2. Tools it can use (guarded by risk policy)

| Tool | What it does | Risk |
|---|---|---|
| `read_file` | Read a file inside your home directory | Safe (auto) |
| `write_file` | Create/edit a text file in your home directory | Confirm |
| `open_application` | Launch a desktop app (firefox, chrome, terminal) | Confirm |
| `open_url` | Open a website or YouTube search in the default browser | Confirm |
| `play_song` | Find and open the top YouTube result for a requested song | Confirm |
| `find_processes` | List running processes / check a process by name | Safe (auto) |
| `check_camera` | Check whether the camera device is present and accessible | Safe (auto) |
| `browse_web` | Fetch a web page headlessly and return its rendered text + title | Safe (auto) |

Confirmation is enforced per rule: Safe tools run automatically, risky ones
prompt you (in the terminal) or return a confirmation challenge over the API.

## 3. What makes it an agent (not a chatbot)

- **ReAct loop** — it plans tool use mid-conversation: read a file, then use its
  contents; open an app; play a song; up to 8 reasoning steps per request.
- **Goal execution** (`jarvis goal "..."`) — a *planner* turns your goal into a
  step list, the agent executes it, a *verifier* then judges the work log and,
  if the goal isn't proven done, it re-plans and retries (bounded at 2 re-plans)
  rather than claiming success. It refuses to declare victory on intent alone.
- **Long-term memory** — past conversations are stored in SQLite (FTS5 full-text
  index) and recalled by ranked relevance, so it remembers context across
  sessions.
- **Phone access via Telegram** — run `jarvis telegram` and message it from your
  phone: the bridge long-polls Telegram and proxies messages through the same
  authenticated `/chat` gateway (no open ports, no webhook; chat allow-list
  required, per-chat session continuity).
- **Persistent task state** — every conversation session (including voice) and
  every goal is saved to a local SQLite store with its goal, plan, steps,
  artifacts, status and full transcript; after a restart it resumes exactly where
  it left off.
- **Guardrails** — permission policy (Low/Med/High risk), rate limiting, and an
  audit trail of every action. Tool-call success ≠ goal-complete: a verifier
  pass backs up every "done".
- **Resilience** — LLM calls retry with exponential backoff (1s/2s/4s, max 3) on
  transient 429/5xx/timeouts before degrading gracefully; step budget (8) and
  re-plan budget (2) cap every run so it never loops forever.

## 4. Plumbing / ops

- `jarvis doctor` — system diagnostics (mic, audio, network, API key).
- `jarvis status` — service status via systemd + HTTP health check.
- `jarvis version`, `jarvis help` — informational.
- Ships as a FastAPI server for remote/automated use; local systemd service.

## What it deliberately does NOT do (yet)

No vision/screen control, no email clients, no streaming/barge-in voice —
those are deferred in the build plan. It runs on free Groq-tier LLM, single-user,
on your machine.

To phone-access JARVIS via Telegram, create a bot with @BotFather, set
`JARVIS_TELEGRAM_TOKEN` and the numeric chat id allow-list `JARVIS_TELEGRAM_ALLOWED_CHATS`,
then run `jarvis telegram`.

## Quick start

```bash
pip install -e ".[voice]"   # one-time install
jarvis run                   # text assistant
jarvis goal "write a report on the weekend weather"  # plan → act → verify
jarvis voice session         # voice assistant
jarvis doctor                # verify the machine is ready
```