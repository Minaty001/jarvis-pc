# Durable Scheduler Architecture

## Persistence & Durability
All schedule specifications are stored in SQLite (`schedules` table). Upon system boot, `TaskManager.startup()` calls `DurableScheduler.load_from_db()`, restoring all active jobs to APScheduler. If the host crashes or reboots, schedules trigger reliably without data loss.

## Supported Triggers
- **ONCE**: `DateTrigger` — single execution at a specified timestamp.
- **CRON**: `CronTrigger` — 5-field cron string (`min hour dom month dow`).
- **INTERVAL**: `IntervalTrigger` — recurring execution every N seconds.

## Natural Language Parsing
`NLScheduleParser` translates human phrases:
- *"every weekday at 8 AM"* → Cron `0 8 * * 1-5`
- *"every 30 minutes"* → Interval `1800s`
- *"tomorrow morning at 9"* → One-shot timestamp
