# JARVIS — Native Desktop UI Design (Linux Mint / Cinnamon)

> Status: v1 implementation in progress. This document is the single source of truth for the
> redesigned UI and MUST be updated as each feature is finished (loop-engineering).

## 1. Research (why these choices)

- **Environment audit**
  - OS: Linux Mint 21, **Cinnamon** desktop (`XDG_CURRENT_DESKTOP=X-Cinnamon`), GTK3 (3.24) + GTK4 (4.14) present.
  - Display: `DISPLAY=:0` (real), `Xvfb`/`xvfb-run` available for headless testing.
  - Python 3.12.3. Project runs in `.venv` (py3.12).
  - System has `PyGObject 3.48.2` + `Gtk-3.0` typelib. The venv now sees it via
    `.venv/lib/python3.12/site-packages/00-system-site.pth` (points to `/usr/lib/python3/dist-packages`).
    No Qt/PyQt/PySide present — avoid adding heavyweight toolkits; GTK3 is already native to Mint.
  - Headless smoke testing works under `xvfb-run -a`.

- **Existing code (integration anchors)**
  - `cognitive.orchestrator.CognitiveOrchestrator` — `process_goal(goal, session_id)` runs the full
    Observe→Understand→Plan→Act→Verify→Record loop. This is the chat "brain".
  - `cognitive.world_state` — `WorldState` dataclass with `cpu_percent`, `task_status`, `workflow_state`,
    `estimated_progress`, `current_goal`, etc. and `to_dict()`.
  - `perception.event_bus` — async pub/sub. `event_bus.subscribe(EventType, cb)` / `subscribe_all(cb)`.
    Event types in `perception.event_models.EventType` (USER, SYSTEM, APP, WORKFLOW, TOOL, MEMORY, ERROR…).
  - `perception.system_monitor` — `SystemMonitor.get_snapshot()`.
  - `proactive.engine` — `add_callback(cb)` to receive proactive suggestions.
  - `llm.gateway.llm_gateway` — async `generate(prompt, task_type, …)`.
  - Old UI: `ui/tray.py` (pystray) + `webapp/` (HTTP dashboard). **Web dashboard is being replaced**
    by the native window; the tray icon stays as a secondary affordance.

- **User requirements (verbatim intent)**
  - Redesign UI, make it *Jarvis-like*. Center **ORB** must be present.
  - **Floating window** that runs in the background and "keeps watching" (always-on-top, low footprint).
  - Must run as a **normal Linux Mint desktop app**, NOT a webapp.
  - Modify everything for Linux Mint specifically; optimise/compress for this device.
  - Document every feature; tick it off and **test** it as soon as it's done (loop-engineering).
  - Parallel agents (codex/opencode/antigravity) may help plan/code, but research is mine.

## 2. Integration plan

The UI is a thin, decoupled frontend. It never imports the heavy engine at module import time;
it receives the already-constructed engine objects (`cognitive_orchestrator`, `event_bus`,
`world_state`, `system_monitor`, `proactive_engine`, `llm_gateway`) through a `UIBridge`.

```
                 run.py (async engine)
                        │  constructs engine, then:
                        │  ui_app = JarvisApp(bridge=UIBridge(engine))
                        ▼
   UIBridge  ─── reads world_state / system_monitor (poll 1s)
             ─── subscribes event_bus (live events)
             ─── registers proactive_engine callback (suggestions)
             ─── forwards chat to orchestrator.process_goal() (async)
                        │  emits UIState / UIEvent over its own GLib idle queue
                        ▼
   JarvisApp (Gtk.Application)
      ├─ MainWindow       (orb HUD + chat + panels; normal window)
      ├─ FloatingOrb      (always-on-top 96px orb; click → toggle MainWindow; drag to move)
      └─ tray icon        (pystray; Show / Quit)
   Close (X) on MainWindow → HIDE, keep engine + floating orb alive (background "watching").
```

Threads: GTK runs its own main loop on the main thread. The async engine runs on a separate
thread with its own `asyncio` loop; `UIBridge` marshals state/events into GTK via `GLib.idle_add`.

## 3. Implementation plan (vertical slices, each tested before next)

| Slice | Deliverable | Test |
|-------|-------------|------|
| 1 | `ui/theme.py` (Cinnamon-friendly dark palette + CSS) + `ui/orb.py` (`OrbWidget` cairo arc-reactor) | import + offscreen cairo render to PNG |
| 2 | `ui/floating_orb.py` (`FloatingOrb` always-on-top, draggable, toggle) | `xvfb-run` launch, assert window present & click handler |
| 3 | `ui/main_window.py` (`MainWindow`: orb HUD + chat + system/memory/tools panels) | render + send fake message, assert chat row |
| 4 | `ui/bridge.py` (`UIBridge`: bind engine → UI) | run with a stub engine, assert events propagate |
| 5 | `ui/app.py` (`JarvisApp` Gtk.Application) + wire into `run.py` (tray + hide-on-close) | full app boots under Xvfb, chat reaches orchestrator |
| 6 | `ui/linux_mint.py` packaging: `.desktop` file, autostart, native libnotify notifications | `desktop-file-validate`, install script dry-run |
| 7 | Optimise/compress (single CSS, no per-frame allocs, debounce), final Xvfb smoke test, README update | launch + interaction script pass |

## 4. Compatibility plan (Linux Mint / this device)

- **Toolkit:** GTK3 via system PyGObject — already matches Cinnamon; no separate Qt theme hacks.
- **Theme:** Load a dark CSS that respects Mint/Cinnamon fonts (`Cantarell`/`Noto`) and the
  system accent where detectable; otherwise JARVIS blue/cyan palette.
- **Notifications:** Use `gi.repository.Notify` (libnotify) — native Mint popups — instead of plyer.
- **Autostart:** install `~/.config/autostart/jarvis.desktop` so it launches at login and floats.
- **Always-on-top:** `set_keep_above(True)` + skip taskbar pager for the floating orb.
- **Perf/compression:** orb animation uses a single `DrawingArea` with `cairo`; timers via
  `GLib.timeout_add` (not Python threads); state poll at 1 Hz; event-driven updates otherwise.
- **Graceful degrade:** if `Notify`/`pystray` missing → log + continue. If no display → headless mode.

## 5. Loop-engineering log

Each finished item is checked and the verification note is recorded here.

- [x] **Research** — env + engine integration points mapped (see §1).
- [x] **Slice 1** OrbWidget — _test: offscreen PNG (6 states) + live GTK draw fired under Xvfb; visual check passed._
- [x] **Slice 2** FloatingOrb — _test: Xvfb — visible, keep_above, click=toggle main, drag=no-toggle._
- [x] **Slice 3** MainWindow — _test: Xvfb render + chat rows + system update + send callback + hide; visual screenshot verified._
- [x] **Slice 4** UIBridge — _test: Xvfb — poll fires (system/orb/tools), chat→process_goal, reply streamed._
- [x] **Slice 5** JarvisApp + run.py wiring — _test: Xvfb — MainWindow+FloatingOrb+bridge created, chat→orchestrator, quit; full run.py UI-mode boot clean (no GTK errors)._
- [x] **Slice 6** Mint packaging — _test: desktop-file-validate OK; launcher + icon + autostart install to ~/.local; app launches via Mint menu Exec._
- [x] **Slice 7** Optimise + docs + smoke test — _test: all 6 slice tests pass under Xvfb; full run.py UI-mode boot clean; README + UI_DESIGN + packaging updated; PyGIWarning fixed._
