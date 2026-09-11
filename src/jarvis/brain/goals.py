"""Goal orchestration: plan a goal, execute it through the agent, verify the result.

Two extra LLM passes around the normal ReAct loop — a planner produces a step
list before execution, a verifier decides afterwards whether the goal was
achieved. The agent re-plans and retries a bounded number of times when the
verifier says the work did not satisfy the goal.
"""

from __future__ import annotations

import re

_VERDICT = re.compile(r"\b(YES|NO)\b", re.IGNORECASE)

PLANNER_PROMPT = """You are JARVIS's task planner. Given a goal below, output a plan of 2-5 concise steps (one step per line, no numbering, no bullets, no preamble) that a tool-using agent can execute. Focus on what to DO, not how to reason."""

VERIFIER_PROMPT = """You are JARVIS's verifier. A goal was attempted and a work log follows. Using ONLY the evidence in the work log, decide whether the goal was genuinely achieved. First line: exactly YES or NO. Second line: one short sentence justifying the verdict. Do not award credit for intent; there must be evidence."""

REFLECT_PROMPT = """You are JARVIS's reflection pass. A tool-using agent attempted a goal and a work log follows. In ONE short sentence, state the reusable lesson: the approach that worked, the pitfall to avoid, or what to try differently next time. If nothing is worth remembering, answer exactly: NONE"""


def _parse_plan(text: str) -> list[str]:
    steps: list[str] = []
    for raw_line in text.strip().splitlines():
        line = re.sub(r"^\s*[\d.)\-*]*\s*", "", raw_line).strip()
        if line:
            steps.append(line)
    return steps


async def plan_goal(client, goal: str, memory=None) -> list[str]:
    """One LLM pass: turn a goal into a short step list, primed with past lessons."""
    system_prompt = PLANNER_PROMPT
    if memory is not None and hasattr(memory, "recall_reflections"):
        past_lessons = memory.recall_reflections(goal, limit=3)
        if past_lessons:
            bullets = "\n".join(f"- {l['lesson']}" for l in past_lessons if l.get("lesson"))
            if bullets:
                system_prompt += f"\n\nPAST LESSONS FOR SIMILAR GOALS (take these into account):\n{bullets}"

    result = await client.chat(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": goal}]
    )
    plan = _parse_plan(result.content or "")
    return plan or [goal]


async def verify_goal(client, goal: str, transcript: list[dict]) -> tuple[bool, str]:
    """One LLM pass: does the work log evidence goal completion?"""
    log = "\n".join(
        f"{m.get('role')}: {m.get('content')}" for m in transcript[-6:] if m.get("content")
    )
    result = await client.chat(
        [
            {"role": "system", "content": VERIFIER_PROMPT},
            {"role": "user", "content": f"GOAL:\n{goal}\n\nWORK LOG:\n{log}"},
        ]
    )
    content = result.content or ""
    match = _VERDICT.search(content)
    met = (match.group(1).upper() == "YES") if match is not None else False
    return (met, content.strip())


async def reflect_goal(client, goal: str, transcript: list[dict], met: bool) -> str | None:
    """One LLM pass: distill a reusable lesson from a finished goal run so it can be
    stored in memory. Returns None when there is nothing worth remembering."""
    log = "\n".join(
        f"{m.get('role')}: {m.get('content')}" for m in transcript[-6:] if m.get("content")
    )
    result = await client.chat(
        [
            {"role": "system", "content": REFLECT_PROMPT},
            {"role": "user", "content": f"GOAL: {goal}\nOUTCOME: {'achieved' if met else 'not achieved'}\n\nWORK LOG:\n{log}"},
        ]
    )
    content = (result.content or "").strip()
    if not content or "NONE" in content.upper():
        return None
    return content