# JARVIS PC — Personal AI Voice Assistant for Linux Mint

JARVIS PC is a persistent, tool-using, environment-aware AI voice assistant built for Linux (optimized for Linux Mint Cinnamon / GTK3 desktop environments). It features a native GTK3 user interface, an ONNX-based voice pipeline, a 6-phase Cognitive Engine architecture, a 6-type memory system, hardware perception monitors, camera control tools, and a proactive background engine.

---

## 🌟 Key Features

- **Native Linux Mint GTK Desktop UI**:
  - **Center ORB HUD**: Animated Cairo-rendered arc-reactor core visually indicating state (`idle`, `listening`, `thinking`, `speaking`, `working`, `error`).
  - **Floating ORB**: Compact, always-on-top floating widget that keeps JARVIS active in the background. Click to toggle the main window; drag to position anywhere on screen.
  - **Main Window & Panels**: Interactive chat interface integrated with live System Monitor (CPU, RAM, Disk, Battery), Registered Tools Explorer, and Memory Subsystem viewer.
  - **Desktop Integration**: Installs natively into the Linux Mint Application Menu (`jarvis.desktop`), installs launcher (`jarvis-ui`), icon, and optional autostart at login.
- **Local Voice Pipeline**:
  - **Wake Word**: 3-stage ONNX neural detector for **"Hey Jarvis"**.
  - **STT**: Fast local speech recognition via `faster-whisper`.
  - **TTS**: High-quality streaming neural text-to-speech via `edge-tts`.
  - **VAD**: CPU-friendly energy-based Voice Activity Detection.
  - **Hardware Permission Manager**: Automatic detection and permission management for microphones, speakers, and webcams via PulseAudio/PipeWire.
- **Cognitive Engine Architecture**:
  - Autonomous 6-phase execution loop: **Observe → Understand → Plan → Act → Verify → Record**.
  - Multi-step task planning, goal execution, and retry management.
- **6-Type Memory System**:
  - **Working**: Short-term task context and transient session state.
  - **Episodic**: Historical interaction logs and past experiences.
  - **Semantic**: Structured persistent facts and knowledge base.
  - **Procedural**: Actionable workflows, shell recipes, and task strategies.
  - **Preference**: User-configured preferences and options.
  - **Failure**: Diagnostic log of past execution errors and mitigation steps.
- **System Tools & Camera Support**:
  - Application control (open/close apps), media controls (volume, play/pause), web search, and shell execution.
  - OpenCV webcam tools (`take_photo`, `take_photo_sequence`, `record_video`, `list_cameras`).
- **Proactive Background Engine**:
  - Contextual background rules monitoring user idle duration, high CPU usage, low disk space, and time-of-day greetings.
- **Multi-LLM Gateway**:
  - Unified interface supporting Groq (default conversation), NVIDIA NIM (vision/multimodal), OpenCode Zen (coding), and OpenRouter (fallback).

---

## 📁 Repository Structure

```
Jarvis/
├── assets/                 # Icons and ONNX wake-word models
│   ├── icons/              # System tray & window icons
│   └── wakeword/           # ONNX model files (melspectrogram, embedding, hey_jarvis)
├── bin/
│   └── jarvis-ui           # Executable bash launcher script
├── cognitive/              # Cognitive Engine (orchestrator, context, prompt builder, world state)
├── config/                 # Pydantic settings & logging setup (.env configuration)
├── core/                   # Brain, intent resolver, planner, observability (metrics & tracing)
├── execution/              # Computer control, plan executor, critic, retry manager
├── llm/                    # LLM providers (Groq, NVIDIA NIM, OpenCode Zen, OpenRouter)
├── memory/                 # 6 memory modules (working, episodic, semantic, procedural, preference, failure)
├── models/                 # Internal Pydantic schema definitions
├── observability/          # Metrics collector & distributed tracer
├── perception/             # Event bus, system monitor, app monitor, workflow monitor
├── planning/               # Task planner, plan models, and task state tracking
├── proactive/              # Proactive background rule engine
├── security/               # Tool security policy, risk-level gating, and audit logs
├── skills/                 # High-level skills (file manager, web research, dev tools)
├── tools/                  # Tool registry, executor, builtin tools, camera tools, gen_icon.py
├── ui/                     # Native GTK3 Desktop App (MainWindow, FloatingOrb, OrbWidget, UIBridge, installer)
├── voice/                  # Voice pipeline (microphone, VAD, wake word, STT, TTS, permissions)
├── tests/                  # Integration tests & UI test suite
├── run.py                  # Main entry point (UI mode or headless mode)
├── pyproject.toml          # Project configuration & package settings
└── requirements.txt        # Python dependencies
```

---

## ⚙️ System Requirements

- **Operating System**: Linux Mint 21+ / Ubuntu 22.04+ (Cinnamon, MATE, Xfce, or GNOME desktop environment)
- **Python**: Python 3.10 or higher
- **System Dependencies**: GTK3 (`libgtk-3-dev`), PyGObject, PulseAudio or PipeWire, PortAudio (`portaudio19-dev`), FFmpeg
- **Hardware**:
  - Microphone & Speaker (for voice mode)
  - Webcam (optional, for camera tools)
  - RAM: 1 GB free RAM minimum (2 GB+ recommended for local Whisper STT)

---

## 🛠️ Quick Installation Options (Direct Install Images)

You can install and run JARVIS directly on Linux (Linux Mint, Ubuntu, Debian, etc.) using one of the prebuilt packages in `dist/`:

### 🚀 Option 1: Standalone AppImage (No Installation Required)
Directly executable, completely portable single binary:
```bash
chmod +x dist/JARVIS-x86_64.AppImage
./dist/JARVIS-x86_64.AppImage
```

### 📦 Option 2: Debian Package (.deb) (Linux Mint / Ubuntu Native)
Native system integration with Application Menu entry, desktop icon, and systemd service:
```bash
sudo apt install ./dist/jarvis_1.0.0_all.deb
# Or using dpkg:
# sudo dpkg -i ./dist/jarvis_1.0.0_all.deb
```

### ⚡ Option 3: Self-Extracting Installer (.run)
Automated single-file installer with diagnostics check:
```bash
chmod +x dist/jarvis-installer.run
./dist/jarvis-installer.run
```

---

## 🔨 Building Installer Images from Source

Aap unified builder script ya `make` ka use karke distribution packages 1-command me build kar sakte hain:

```bash
# Option A: Using make (Sabse easy)
make build

# Option B: Using unified builder script
./scripts/build.sh all --verify

# Specific target build:
# make appimage   OR   ./scripts/build.sh appimage
# make deb        OR   ./scripts/build.sh deb
# make run-pkg    OR   ./scripts/build.sh run
```
All outputs are generated into the `dist/` directory with automatic integrity verification.

---

## 💻 Running JARVIS

After installation, the `jarvis` command is available system-wide:

```bash
# Check system diagnostics & dependencies
jarvis doctor

# Start the JARVIS assistant service
jarvis run

# Execute an autonomous multi-step goal
jarvis goal "Check system health and notify me"

# Check background daemon status
jarvis status
```

---

## ☁️ Render.com Cloud Deployment

JARVIS backend is pre-configured for 1-click cloud deployment on **Render.com** (via Native Python Web Service or Docker container):

### Deployment Files
- [`render_app.py`](file:///home/shanu/Desktop/Jarvis/render_app.py): Cloud production API entrypoint listening on `0.0.0.0:$PORT`.
- [`render.yaml`](file:///home/shanu/Desktop/Jarvis/render.yaml): Render Blueprint file for automated service & disk setup.
- [`Dockerfile`](file:///home/shanu/Desktop/Jarvis/Dockerfile): Containerized deployment spec.
- [`Procfile`](file:///home/shanu/Desktop/Jarvis/Procfile): Web process declaration (`web: python render_app.py`).

### How to Deploy on Render.com

1. **Push Repository to GitHub / GitLab**.
2. **Open Render Dashboard**: Go to [dashboard.render.com](https://dashboard.render.com).
3. **Option A (Blueprint - Recommended)**:
   - Click **New +** → **Blueprint**.
   - Connect your GitHub repo. Render will automatically detect [`render.yaml`](file:///home/shanu/Desktop/Jarvis/render.yaml) and configure the web service, build commands, and health check.
4. **Option B (Manual Web Service)**:
   - Click **New +** → **Web Service**.
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python render_app.py`
   - Health Check Path: `/health`
5. **Environment Variables**:
   Add your API keys under Service Settings → **Environment**:
   - `GROQ_API_KEY`: `gsk_...`
   - `OPENROUTER_API_KEY`: `sk-or-...` (optional)
   - `NVIDIA_API_KEY`: `nvapi-...` (optional)

---

## 🔌 REST API Endpoints

When running, JARVIS exposes an HTTP API at `http://127.0.0.1:3000`:

- **Health Check**:
  ```bash
  curl http://127.0.0.1:3000/health
  ```
- **System Status**:
  ```bash
  curl http://127.0.0.1:3000/status
  ```
- **Send Chat Message**:
  ```bash
  curl -X POST http://127.0.0.1:3000/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "What is the system CPU usage?"}'
  ```
- **Execute Tool**:
  ```bash
  curl -X POST http://127.0.0.1:3000/execute \
    -H "Content-Type: application/json" \
    -d '{"tool": "web_search", "args": {"query": "Linux Mint news"}}'
  ```

---

## 🧪 Testing & Verification

Run the test suite to verify UI components, packaging, and cognitive subsystems:

```bash
source .venv/bin/activate

# Test desktop packaging and launcher setup
python3 tests/test_packaging.py

# Test cognitive engine integration
python3 tests/test_integration.py

# Test UI bridge and window modules
python3 tests/test_bridge.py
python3 tests/test_floating_orb.py
python3 tests/test_main_window.py
python3 tests/test_jarvis_app.py
```

---

## ❓ Troubleshooting

- **Microphone / Speaker permissions**:
  Ensure PulseAudio or PipeWire is running:
  ```bash
  pactl list sources short
  pulseaudio --start
  ```
- **Wake Word Sensitivity**:
  If the wake word triggers too easily or not enough, adjust `JARVIS_WAKE_THRESHOLD` in your `.env` file (default: `0.8`).
- **GTK Import Check**:
  Verify PyGObject and GTK3 bindings:
  ```bash
  python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk; print('GTK 3 OK')"
  ```

---

## 📄 License

Personal Project — Designed for Linux Mint Desktop Automation.
