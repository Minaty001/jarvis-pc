# JARVIS Wake Word Engine

Lightweight, high-accuracy wake word detection service for JARVIS powered by `openWakeWord`.

## Features
- **Automatic Start**: Starts listening immediately on launch.
- **Background Operation**: Runs non-blockingly in a background thread or as a detached daemon process.
- **Low Latency & Efficient**: Real-time 80ms inference chunks using ONNX runtime.
- **Customizable Sensitivity**: Adjustable confidence threshold and debounce cooldown.

## Quick Start

### 1. Automatic Foreground Mode
Starts listening immediately in the background thread with live console feedback:
```bash
.venv/bin/python main.py
```

### 2. Background Daemon Mode
Run as a background background service:
```bash
# Start background service
.venv/bin/python main.py --background

# Check status
.venv/bin/python main.py --status

# Stop background service
.venv/bin/python main.py --stop
```

### 3. Programmatic Usage in Python
```python
from jarvis.wake_word import WakeWordDetector

def handle_wake_word(name: str, score: float):
    print(f"Triggered by {name} with score {score}!")

# Automatically starts listening in background thread
detector = WakeWordDetector(
    wake_words=["hey_jarvis"],
    threshold=0.5,
    on_wake_word=handle_wake_word,
    auto_start=True
)
```
