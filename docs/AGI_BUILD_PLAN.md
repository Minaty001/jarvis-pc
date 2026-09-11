# JARVIS — AGI Capability Build Plan

> Status: **steps 1-9 done (2026-09-12)** — core reliability, voice, RAG, GTK3 desktop HUD, and reflection/pattern learning are complete.
> Terminology note (from source spec): "JARVIS / AGI / self-healing / dreaming"
> are product/architecture goals, not claims of proven AGI capability.

---

## Current state (what already exists)

| Area | Status | Evidence |
|---|---|---|
| LLM gateway, OpenAI-compatible, model pick | ✅ Have | `src/jarvis/brain/client.py`, Groq free tier live |
| Tool registry (schema, risk, capabilities) | ✅ Have | `src/jarvis/tools/base.py`, `policy.py`, `registry.py` |
| Permission model (Low/Med/High → auto/confirm/critical) | ✅ Have | `src/jarvis/tools/policy.py`, `executor.py`, `confirmation.py` |
| Human-in-the-loop confirmation | ✅ Have | REPL prompt; `/chat`, `/execute` |
| Guardrails (rate-limit, audit) | ✅ Have | `src/jarvis/tools/rate_limit.py`, `audit.py` |
| ReAct agent loop | ✅ Have | `src/jarvis/brain/agent.py` |
| JARVIS persona | ✅ Have | `src/jarvis/brain/persona.py` |
| Clients (CLI, FastAPI `/chat`, `/execute`) | ✅ Have | `src/jarvis/cli/main.py`, `api/app.py` |
| Long-term conversational memory | ✅ Have (upgraded) | `src/jarvis/brain/memory.py` — SQLite FTS5 BM25 ranked recall; auto-migrates old JSONL |

---

## Build order (recommended sequence)

### 🟢 Phase 1 — Foundation (reliability spine)
1. **Persistent task state** — SQLite store for agent tasks (goal / plan / step /
   artifacts / resume). ✅ Done — `tasks/store.py`, stdlib sqlite3 at
   `state/tasks.db`, sessions persist/resume their transcript across restarts.
2. **Planner + verifier** — extra LLM pass before/after the ReAct loop; bounded
   re-plan. ✅ Done — `brain/goals.py`: planner emits a step list into
   `tasks.plan`, verifier judges the work log, `JarvisAgent.run_goal` re-plans up
   to 2× when unverified. `jarvis goal "..."` runs a full plan→act→verify.
3. **Bounded retry/recovery** — backoff, alternate tool, re-plan, hard caps.
   ✅ Done — `brain/client._chat_with_retry`: exponential backoff (1s/2s/4s) on
   429/5xx/timeouts, max 3 retries, then graceful degradation. Live-verified
   against a real Groq 429 (retried, recovered).

### 🟢 Phase 2 — Reliability
4. **Scheduler** — `APScheduler` + `AsyncIOScheduler` (NOT Celery — single-node
   async is the right fit). ✅ Done — `scheduler/__init__.py` thin wrapper
   (`at`/`every`), wired into Application start/stop, `apscheduler` extra.
   Gives §1.4 proactive automation, reminders, reports.
5. **RAG memory** — ✅ Done — `memory.py` rebuilt on SQLite **FTS5** (stdlib, no
   new dep): BM25-ranked recall replaces JSONL keyword overlap, auto-migrates the
   old file, trims to 500 episodes. NO standalone vector DB (per plan). Local
   embeddings deferred until retrieval quality demands them.

### 🟡 Phase 3–4 — later, higher cost
6. **Playwright browser tool** — ✅ Done — `tools/builtin/browser.py`: spawns
   headless Chrome (`--remote-debugging-port` on an ephemeral port + CDP over
   WebSocket), reads rendered DOM text + title via `Runtime.evaluate`. No vision,
   no screenshots. `browse_web(url)` = SAFE-risk, `network.read`; registered +
   exposed to the LLM. Completes `§7.1` + the "open youtube" gap.
7. **Real-time voice** — ✅ Done — `voice/` rebuilt earlier: Whisper STT via Groq
   (`whisper-large-v3-turbo`) with Vosk offline fallback, edge-tts TTS (+spd-say
   offline fallback), wake word, full `jarvis voice session` loop.
   Live-verified: Groq transcript of the wake fixture + offline Vosk tests green.
   Streaming/barge-in deferred — batched loop is enough for free-tier single-user.
8. **Remote clients** — ✅ Done — `remote/telegram.py` Telegram bridge: long-polls
   `getUpdates` (no webhook/firewall) and proxies every message through the
   *existing* authenticated `/chat` gateway (Bearer `JARVIS_API_TOKEN`, per-chat
   `session_id`). Allow-list gated (`JARVIS_TELEGRAM_ALLOWED_CHATS`). `jarvis
   telegram`, `httpx` only. Live-verified bridge→gateway request shape + auth.
9. **Reflection / pattern learning** — ✅ Done — `brain/reflection.py` + `brain/memory.py`: autonomous metacognitive critique after goal runs; extracts actionable lessons and procedural patterns, indexes into SQLite FTS5 (`reflections_fts`), and primes the planner with past lessons via BM25 recall. `jarvis reflections` CLI inspects learned rules.

### 🔴 Later / only-if (experimental, behind everything)
- **Screen/computer-use control** — needs a vision model; free Groq vision tier is
  brutally limited (50 RPM / 1K RPD). Skip until off free tier or narrowly scoped.
  Prefer DOM/CDP path above. §1.1, §7.
- **MCP client** — DON'T build; all tools local, already first-class in registry.
  §1.3.
- **Multi-agent frameworks** (LangGraph/CrewAI/AutoGen) — DON'T build; re-planning
  gives the same benefit at small scale. §4.
- **Knowledge graph** — SKIP. SQLite + RAG covers it. §14.2.
- **Tool generation / self-modifying workflows** — high risk, behind everything. §10.
- **Persona adaptivity** — prompt tweak, not a build. §18.

---

## Recommended first move (when resumed)
Build **#1 + #2**: SQLite task state + planner/verifier loop. This is the step
from "chatbot with tools" toward "agent that finishes goals." Pure Python, deps
already available. Prove live with Groq key before touching anything else.

## Design principles (always keep)
1. Autonomy with control — strong permissions with high autonomy.
2. Observe before acting — never destructive without understanding state.
3. Verify before declaring success — tool-call-success ≠ goal-complete.
4. Persist task state — long workflows resume after restart.
5. Deterministic checks for critical decisions — LLM is never sole authority.
6. Every risky action auditable — who/what/when/why/result.
7. Bound retries and budgets — never infinite loops.
8. Prefer structured interfaces (DOM/APIs/typed tools) over screenshots.
9. Separate experimentation from production.
10. Treat confidence as uncertainty, not truth.
