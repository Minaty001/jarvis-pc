# Memory and Routines Architecture

## Routine Manager
`RoutineManager` provides named templates for common automated workflows:
1. `morning_briefing`: Weather + Calendar + Task summary + TTS speech
2. `work_start`: Launch dev apps (VS Code, Chrome) + Calendar check
3. `evening_routine`: Daily task completion summary + Notification
4. `night_routine`: File sync + Desktop cleanup reminder
5. `weekly_report`: Week-in-review task aggregation + Markdown export

## Task Memory Integration
Task runs, execution metrics, and step outputs write to `TaskRepository` (`task_events` and `checkpoints`), allowing `MemoryManager` to query historical outcomes for proactive learning and failure analysis.
