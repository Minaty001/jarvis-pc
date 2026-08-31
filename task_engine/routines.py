# task_engine/routines.py
"""Routine Manager — first-class named task templates with schedules."""
from __future__ import annotations
from config.logger import get_logger
from task_engine.models import Task, TaskTemplate, TaskStep, TaskPriority

logger = get_logger("task_engine.routines")

_BUILTIN_TEMPLATES = [
    TaskTemplate(
        name="morning_briefing",
        description="Check weather, calendar, tasks, and speak a morning briefing",
        step_blueprints=[
            {"action": "get_weather", "parameters": {}},
            {"action": "get_calendar", "parameters": {}},
            {"action": "get_tasks", "parameters": {}},
            {"action": "summarize", "parameters": {"style": "brief"}},
            {"action": "tts_speak", "parameters": {}},
        ],
        default_schedule="every weekday at 8 AM",
        tags=["daily", "briefing"],
    ),
    TaskTemplate(
        name="work_start",
        description="Open work apps, check calendar, and prioritize tasks",
        step_blueprints=[
            {"action": "open_app", "parameters": {"app_name": "code"}},
            {"action": "open_app", "parameters": {"app_name": "chrome"}},
            {"action": "get_calendar", "parameters": {}},
            {"action": "get_tasks", "parameters": {}},
        ],
        default_schedule="every weekday at 9 AM",
        tags=["work", "setup"],
    ),
    TaskTemplate(
        name="evening_routine",
        description="Summarize completed tasks and preview tomorrow",
        step_blueprints=[
            {"action": "get_tasks", "parameters": {"filter": "completed_today"}},
            {"action": "summarize", "parameters": {"style": "evening"}},
            {"action": "send_notification", "parameters": {"message": "Evening summary ready"}},
        ],
        default_schedule="every day at 9 PM",
        tags=["daily", "evening"],
    ),
    TaskTemplate(
        name="night_routine",
        description="Save work, close apps, prepare for next day",
        step_blueprints=[
            {"action": "run_command", "parameters": {"command": "sync"}},
            {"action": "send_notification", "parameters": {"message": "Time to wrap up"}},
        ],
        default_schedule="every day at 11 PM",
        tags=["daily", "night"],
    ),
    TaskTemplate(
        name="weekly_report",
        description="Summarize completed tasks and create weekly report file",
        step_blueprints=[
            {"action": "get_tasks", "parameters": {"filter": "this_week"}},
            {"action": "summarize", "parameters": {"style": "report"}},
            {"action": "write_file", "parameters": {"path": "~/reports/weekly.md"}},
            {"action": "send_notification", "parameters": {"message": "Weekly report ready"}},
        ],
        default_schedule="every Friday at 6 PM",
        tags=["weekly", "report"],
    ),
]


class RoutineManager:
    """Manages named task templates and their scheduled instances."""

    def __init__(self):
        self._templates: dict[str, TaskTemplate] = {
            t.name: t for t in _BUILTIN_TEMPLATES
        }
        self._task_manager = None  # injected at startup

    def inject_task_manager(self, tm) -> None:
        self._task_manager = tm

    def register_template(self, tmpl: TaskTemplate) -> None:
        self._templates[tmpl.name] = tmpl
        logger.info("Registered routine template: %s", tmpl.name)

    def list_templates(self) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "tags": t.tags,
             "default_schedule": t.default_schedule}
            for t in self._templates.values()
        ]

    async def create_routine(self, template_name: str, schedule_nl: str) -> Task:
        """Instantiate a template as a scheduled Task."""
        tmpl = self._templates.get(template_name)
        if not tmpl:
            raise ValueError(f"Unknown template: {template_name}")
        goal = f"{tmpl.description} [{template_name}]"
        if not self._task_manager:
            from task_engine.manager import task_manager
            self._task_manager = task_manager
        task = await self._task_manager.submit(goal, schedule_nl=schedule_nl)
        logger.info("Created routine '%s' scheduled: %s", template_name, schedule_nl)
        return task


routine_manager = RoutineManager()
