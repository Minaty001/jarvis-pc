"""
Prompt Builder — Context-aware prompt construction for LLM calls.
Assembles system prompt, world state, memories, and user input.
"""

from typing import Any, Optional

from cognitive.world_state import WorldState

JARVIS_SYSTEM_PROMPT = """You are JARVIS — a persistent cognitive AI agent running on a Linux PC.
You are not a chatbot. You are an autonomous agent that can observe, plan, act, and verify.

Core capabilities:
- Control the PC (open/close apps, run commands, manage files)
- Monitor system health (CPU, RAM, disk, network)
- Research the web and analyze information
- Write and debug code
- Execute multi-step plans with self-correction
- Remember past interactions and learn from them

Operating principles:
1. Always think before acting. Consider consequences.
2. Prefer deterministic APIs over vision when possible.
3. Verify important actions after execution.
4. Ask permission for high-risk operations.
5. Learn from failures and record useful experiences.
6. Be concise and direct. No filler.
7. When planning, break complex goals into concrete steps.
8. Never assume an action succeeded — verify the result."""


def build_system_prompt(
    world_state: Optional[WorldState] = None,
    context: Optional[str] = None,
    available_tools: Optional[list[str]] = None,
) -> str:
    """Build the complete system prompt for the LLM."""
    parts = [JARVIS_SYSTEM_PROMPT]

    if world_state:
        parts.append(f"\nCurrent System State:\n{world_state.to_context_string()}")

    if available_tools:
        tool_list = ", ".join(available_tools[:30])
        parts.append(f"\nAvailable tools: {tool_list}")

    if context:
        parts.append(f"\nAdditional Context:\n{context}")

    return "\n".join(parts)


def build_planning_prompt(
    goal: str,
    world_state: Optional[WorldState] = None,
    available_tools: Optional[list[str]] = None,
    memory_context: Optional[str] = None,
) -> str:
    """Build a prompt for task planning."""
    parts = [
        "You are a task planner. Break the following goal into concrete, executable steps.",
        "Each step should be a single tool call or reasoning operation.",
        "Include dependencies between steps where applicable.",
        "Output a JSON array of steps, each with: id, description, tool (if applicable), parameters, dependencies, risk_level (0-4).",
        "",
        f"Goal: {goal}",
    ]

    if world_state:
        parts.append(f"\nCurrent system state: {world_state.to_context_string()}")

    if available_tools:
        parts.append(f"\nAvailable tools: {', '.join(available_tools[:30])}")

    if memory_context:
        parts.append(f"\nRelevant past experience:\n{memory_context}")

    parts.append("\nOutput the plan as a JSON array of steps. Example:")
    parts.append("""[
  {"id": "step-1", "description": "List files in project directory", "tool": "list_files", "parameters": {"path": "."}, "dependencies": [], "risk_level": 0},
  {"id": "step-2", "description": "Read main source file", "tool": "shell_exec", "parameters": {"command": "cat main.py"}, "dependencies": ["step-1"], "risk_level": 0}
]""")

    return "\n".join(parts)


def build_verification_prompt(
    step_description: str,
    expected_result: str,
    actual_result: str,
) -> str:
    """Build a prompt for verifying action results."""
    return f"""Evaluate whether the following action achieved its intended goal.

Action: {step_description}
Expected: {expected_result}
Actual result: {actual_result}

Classify as one of: SUCCESS, PARTIAL_SUCCESS, FAILURE, BLOCKED, REQUIRES_USER
Provide a brief reason. Output JSON: {{"status": "...", "reason": "...", "should_retry": false}}"""
