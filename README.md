# JARVIS PC — Personal AI Voice Assistant

A persistent, tool-using, environment-aware AI voice assistant for Linux with a full Cognitive Engine architecture.

## Architecture

```
JARVIS Cognitive Engine
├── cognitive/          → orchestrator, world_state, context_manager, prompt_builder
├── perception/         → event_bus, event_models, system_monitor, app_monitor, workflow_monitor
├── planning/           → task_planner, task_state, plan_models
├── execution/          → executor, critic, retry_manager, computer_control
├── memory/             → 6 types (working, episodic, semantic, procedural, preference, failure) + manager
├── tools/              → registry, security, executor (policy-gated)
├── proactive/          → engine (idle/CPU/disk/morning rules)
├── api/                → REST server (health, status, chat, execute)
├── core/               → observability (metrics, tracer)
├── llm/                → Groq, NVIDIA NIM, OpenCode Zen, OpenRouter providers
├── voice/              → mic, wake word, STT, TTS, pipeline
├── skills/             → file_manager, web_research, dev_tools, etc.
└── tests/              → integration tests
```

## Quick Start

### 1. Setup Environment

```bash
cd /home/shanu/Desktop/Jarvis

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install pydantic pydantic-settings python-dotenv httpx numpy psutil edge-tts groq
```

### 2. Configure API Keys

Create a `.env` file in the project root:

```bash
# Required: Groq (for conversation)
GROQ_API_KEY=your_groq_api_key_here

# Optional: Other providers
NVIDIA_API_KEY=your_nvidia_api_key
ZEN_API_KEY=your_zen_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
```

### 3. Run JARVIS

```bash
cd /home/shanu/Desktop/Jarvis
source .venv/bin/activate
python3 run.py
```

JARVIS will start in text-only mode (API available) since voice hardware may not be available.

## API Endpoints

Once running, the API is available at `http://127.0.0.1:3000`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info and available endpoints |
| `/health` | GET | Health check |
| `/status` | GET | System status, world state, metrics |
| `/metrics` | GET | Detailed metrics snapshot |
| `/memory` | GET | Memory system summary |
| `/tasks` | GET | Active and pending tasks |
| `/tools` | GET | Registered tools list |
| `/chat` | POST | Send a message to JARVIS |
| `/execute` | POST | Execute a tool directly |

### Example API Calls

**Health check:**
```bash
curl http://127.0.0.1:3000/health
```

**Send a chat message:**
```bash
curl -X POST http://127.0.0.1:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the capital of France?"}'
```

**Execute a tool:**
```bash
curl -X POST http://127.0.0.1:3000/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "web_search", "args": {"query": "latest news"}}'
```

**Check system status:**
```bash
curl http://127.0.0.1:3000/status
```

## Cognitive Engine Loop

JARVIS processes every request through a 6-phase loop:

1. **OBSERVE** — Perceive the environment (system metrics, events, user input)
2. **UNDERSTAND** — Classify intent and extract key information
3. **PLAN** — Create an execution plan (single-step or multi-step)
4. **ACT** — Execute tools through the security policy layer
5. **VERIFY** — Check results against the goal
6. **RECORD** — Store experience in memory for future learning

## Memory System

JARVIS has 6 memory types:

| Type | Purpose |
|------|---------|
| **Working** | Current task context, temporary state |
| **Episodic** | Past experiences and conversation episodes |
| **Semantic** | Facts, entities, and persistent knowledge |
| **Procedural** | How-to knowledge and successful strategies |
| **Preference** | User-approved preferences and settings |
| **Failure** | Past failures, causes, and recovery strategies |

## Security

- All tool calls pass through a security policy layer
- Risk levels: SAFE, LOW, MEDIUM, HIGH, CRITICAL
- Blocked dangerous patterns (rm -rf, etc.)
- Audit logging of all security decisions
- High-risk actions require confirmation

## Proactive Engine

JARVIS can act proactively based on context:

- **Idle reminder** — Notifies after 30 minutes of inactivity
- **High CPU warning** — Alerts when CPU usage exceeds 90%
- **Low disk warning** — Warns when disk space is low
- **Morning greeting** — Greets user in the morning

## Voice Features (Optional)

For full voice mode, install additional dependencies:

```bash
pip install onnxruntime faster-whisper sounddevice scipy
```

Voice features include:
- Wake word detection ("Hey Jarvis")
- Speech-to-text (faster-whisper)
- Text-to-speech (edge-tts)
- Voice Activity Detection (VAD)

## Testing

Run integration tests:

```bash
cd /home/shanu/Desktop/Jarvis
source .venv/bin/activate
python3 tests/test_integration.py
```

## LLM Providers

| Provider | Use Case | Status |
|----------|----------|--------|
| Groq | Conversation (default) | Active |
| NVIDIA NIM | Vision tasks | Optional |
| OpenCode Zen | Coding tasks | Optional |
| OpenRouter | Fallback | Optional |

## Project Structure

```
Jarvis/
├── cognitive/           # Core cognitive engine
├── perception/          # Event bus and monitoring
├── planning/            # Task planning and state
├── execution/           # Tool execution and verification
├── memory/              # 6-type memory system
├── tools/               # Tool registry and security
├── proactive/           # Proactive behavior engine
├── api/                 # REST API server
├── core/                # Observability and utilities
├── llm/                 # LLM provider integrations
├── voice/               # Voice pipeline (mic, STT, TTS)
├── skills/              # Built-in skills
├── config/              # Settings and logging
├── tests/               # Integration tests
├── assets/              # Wake word models, icons
├── run.py               # Main entry point
├── .env                 # API keys (not in git)
└── README.md            # This file
```

## Troubleshooting

**"sounddevice not available"** — No microphone detected. JARVIS runs in text-only API mode.

**"onnxruntime not installed"** — Wake word detection disabled. Install with `pip install onnxruntime`.

**"faster-whisper not installed"** — Speech-to-text disabled. Install with `pip install faster-whisper`.

**Groq model not found** — Update `groq_model` in `config/settings.py` to a valid model (e.g., `qwen/qwen3.8-27b`).

**Port 3000 in use** — Change the port in `api/server.py` (default: 3000).

## License

Personal project — not for distribution.
