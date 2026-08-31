"""
Cognitive Orchestrator — Main agent loop.
Implements: OBSERVE → UNDERSTAND → PLAN → POLICY CHECK → ACT → VERIFY → UPDATE MEMORY → CONTINUE/COMPLETE
"""

import asyncio
import json
import time
import uuid
from typing import Any, Optional

from config.logger import get_logger
from config.settings import settings
from cognitive.world_state import WorldState, world_state
from cognitive.context_manager import context_manager
from cognitive.prompt_builder import (
    build_system_prompt,
    build_planning_prompt,
    build_verification_prompt,
)

logger = get_logger("cognitive.orchestrator")


class CognitiveOrchestrator:
    """
    Main cognitive engine loop.
    Coordinates: perception → planning → policy → execution → verification → memory
    """

    def __init__(self):
        self._running = False
        self._active_task: Optional[dict] = None
        self._task_history: list[dict] = []
        self._llm_gateway = None
        self._tool_executor = None
        self._event_bus = None
        self._memory_manager = None
        self._permission_engine = None

    def inject_dependencies(
        self,
        llm_gateway=None,
        tool_executor=None,
        event_bus=None,
        memory_manager=None,
        permission_engine=None,
    ):
        """Inject dependencies (avoids circular imports at module level)."""
        self._llm_gateway = llm_gateway
        self._tool_executor = tool_executor
        self._event_bus = event_bus
        self._memory_manager = memory_manager
        self._permission_engine = permission_engine

    async def start(self) -> None:
        """Start the cognitive engine."""
        self._running = True
        logger.info("Cognitive engine started")

    async def stop(self) -> None:
        """Stop the cognitive engine."""
        self._running = False
        logger.info("Cognitive engine stopped")

    async def process_goal(
        self,
        goal: str,
        session_id: str = "default",
        task_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Main entry point: process a user goal through the canonical TaskManager engine.
        Returns the final result.
        """
        from task_engine.manager import task_manager
        start_time = time.time()
        logger.info("Processing goal: '%s'", goal[:80])

        world_state.update(
            current_goal=goal,
            task_status="running",
        )

        try:
            task = await task_manager.submit(goal)
            # Poll for task completion (max 120s)
            for _ in range(240):
                await asyncio.sleep(0.5)
                status = await task_manager.status(task.id)
                if status.get("state") in ("COMPLETED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED"):
                    break
            duration = time.time() - start_time
            steps_summary = status.get("steps", [])
            results = [
                s.get("result") for s in steps_summary
                if s.get("result") and s.get("result") != "None"
            ]
            final_result = {
                "task_id": task.id,
                "status": "completed" if status.get("state") in ("COMPLETED", "PARTIALLY_COMPLETED") else "failed",
                "goal": goal,
                "plan_steps": len(steps_summary),
                "result": {
                    "results": [{"result": r} for r in results],
                    "steps_summary": steps_summary,
                },
                "duration_sec": round(duration, 2),
            }
            world_state.update(task_status="idle", current_goal="", active_task_id="")
            return final_result
        except Exception as e:
            logger.error("Goal processing failed: %s", e, exc_info=True)
            world_state.update(task_status="idle")
            return {
                "task_id": task_id or "task-failed",
                "status": "failed",
                "goal": goal,
                "error": str(e),
                "duration_sec": round(time.time() - start_time, 2),
            }

    async def _understand(self, goal: str) -> dict:
        """Classify user intent and extract key information."""
        logger.info("Phase 1: UNDERSTAND — classifying intent")

        # Fast path: check for simple deterministic intents
        goal_lower = goal.lower().strip()

        # Check if it's a simple query vs complex task
        complex_indicators = [
            "build", "test", "deploy", "debug", "fix", "create", "implement",
            "refactor", "analyze", "research", "compare", "setup", "configure",
            "optimize", "migrate", "review", "write a", "develop",
        ]
        is_complex = any(ind in goal_lower for ind in complex_indicators)

        intent = {
            "text": goal,
            "is_complex": is_complex,
            "requires_tools": not goal_lower.startswith(("what", "how", "why", "explain")),
            "estimated_steps": 1 if not is_complex else 5,
        }

        # Use LLM for complex intent classification if available
        if is_complex and self._llm_gateway:
            try:
                classification = await self._llm_gateway.generate(
                    prompt=f"Classify this user goal into one of: [QUERY, COMMAND, TASK, CREATION, DEBUGGING, RESEARCH]\n\nGoal: {goal}\n\nOutput JSON: {{\"category\": \"...\", \"key_entities\": [...], \"complexity\": \"low/medium/high\"}}",
                    task_type="reasoning",
                    max_tokens=200,
                )
                if classification.text:
                    try:
                        parsed = json.loads(classification.text)
                        intent["category"] = parsed.get("category", "TASK")
                        intent["key_entities"] = parsed.get("key_entities", [])
                        intent["complexity"] = parsed.get("complexity", "medium")
                    except json.JSONDecodeError:
                        intent["category"] = "TASK"
            except Exception as e:
                logger.warning("LLM classification failed: %s", e)

        if "category" not in intent:
            intent["category"] = "TASK" if is_complex else "QUERY"

        return intent

    async def _plan(self, goal: str, intent: dict) -> dict:
        """Create an execution plan for the goal."""
        logger.info("Phase 2: PLAN — creating execution plan")

        import re
        from core.intent_resolver import intent_resolver

        # Compound check: split goal on conjunctions like "aur uske baad", "or uske baad", "and then", "after that"
        compound_splitters = [
            r"\s+aur\s+uske\s+baad\s+", r"\s+or\s+uske\s+baad\s+", r"\s+phir\s+",
            r"\s+and\s+then\s+", r"\s+after\s+that\s+", r"\s+then\s+",
        ]
        regex = "|".join(compound_splitters)
        sub_goals = [s.strip() for s in re.split(regex, goal, flags=re.IGNORECASE) if s.strip()]

        if len(sub_goals) > 1:
            steps = []
            for i, sub_g in enumerate(sub_goals):
                sub_res = intent_resolver.resolve(sub_g)
                tool_n = sub_res.action
                params = sub_res.parameters
                if tool_n == "chat" or not tool_n:
                    tool_n = "web_search"
                    params = {"query": sub_g}
                steps.append({
                    "id": f"step-{i+1}",
                    "description": sub_g,
                    "tool": tool_n,
                    "parameters": params,
                    "dependencies": [f"step-{i}"] if i > 0 else [],
                    "risk_level": 0,
                    "status": "pending",
                })
            logger.info("Decomposed compound goal into %d sequential steps", len(steps))
            return {"goal": goal, "steps": steps}

        # Fast path: deterministic intents via pattern matching
        resolved = intent_resolver.resolve(goal)
        if resolved.confidence >= 0.9 and resolved.action != "chat":
            # Map intent actions to registered tool names
            tool_name = resolved.action
            if tool_name in (
                "open_app", "close_app",
                "media_play", "media_pause", "set_volume",
                "play_on_youtube", "play_on_spotify",
                "web_search",
            ):
                pass  # name already matches registered tool
            elif tool_name == "shell_exec":
                tool_name = "run_command"
            elif tool_name in (
                "screenshot", "clipboard_copy", "clipboard_paste",
                "get_time", "get_date", "get_battery", "get_cpu",
                "get_memory", "get_disk", "get_network",
                "list_files", "create_file", "delete_file",
            ):
                pass  # system tools — pass through
            else:
                tool_name = None

            if tool_name:
                logger.info("Fast-path: intent '%s' -> tool '%s'", resolved.action, tool_name)
                return {
                    "goal": goal,
                    "steps": [{
                        "id": "step-1",
                        "description": goal,
                        "tool": tool_name,
                        "parameters": resolved.parameters,
                        "dependencies": [],
                        "risk_level": 0,
                        "status": "pending",
                    }],
                }

        is_complex = intent.get("is_complex", False)

        if not is_complex:
            # Simple goal: single-step plan
            return {
                "goal": goal,
                "steps": [{
                    "id": "step-1",
                    "description": goal,
                    "tool": None,
                    "parameters": {"query": goal},
                    "dependencies": [],
                    "risk_level": 0,
                    "status": "pending",
                }],
            }

        # Complex goal: use LLM to decompose
        if self._llm_gateway:
            try:
                tools = []
                if self._tool_executor:
                    from tools.registry import tool_registry
                    tools = [t.name for t in tool_registry.list_tools()]

                planning_prompt = build_planning_prompt(
                    goal=goal,
                    world_state=world_state,
                    available_tools=tools,
                )

                response = await self._llm_gateway.generate(
                    prompt=planning_prompt,
                    task_type="reasoning",
                    max_tokens=2000,
                    temperature=0.3,
                )

                if response.text:
                    # Try to extract JSON plan from response
                    plan = self._extract_json_plan(response.text, goal)
                    if plan:
                        return plan
            except Exception as e:
                logger.warning("LLM planning failed: %s", e)

        # Fallback: simple single-step plan
        return {
            "goal": goal,
            "steps": [{
                "id": "step-1",
                "description": goal,
                "tool": None,
                "parameters": {"query": goal},
                "dependencies": [],
                "risk_level": 0,
                "status": "pending",
            }],
        }

    def _extract_json_plan(self, text: str, goal: str) -> Optional[dict]:
        """Extract and validate JSON plan using Pydantic plan_validator."""
        import re
        from planning.plan_validator import plan_validator
        # Try to find JSON array in response
        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        if json_match:
            try:
                steps = json.loads(json_match.group())
                if isinstance(steps, list) and len(steps) > 0:
                    # Normalize steps
                    normalized = []
                    for i, step in enumerate(steps):
                        normalized.append({
                            "id": step.get("id", f"step-{i+1}"),
                            "description": step.get("description", ""),
                            "tool": step.get("tool"),
                            "parameters": step.get("parameters", {}),
                            "dependencies": step.get("dependencies", []),
                            "risk_level": 0,
                        })
                    raw = {"goal": goal, "steps": normalized}
                    valid, validated, reason = plan_validator.validate(raw)
                    if valid and validated:
                        return validated.model_dump()
                    else:
                        logger.warning("Extracted plan failed validation: %s", reason)
            except Exception as e:
                logger.debug("JSON plan parsing error: %s", e)
        return None

    async def _execute_plan(self, plan: dict, task_id: str) -> dict:
        """Execute all steps in the plan."""
        logger.info("Phase 3: EXECUTE — running %d steps", len(plan.get("steps", [])))

        world_state.update(task_status="executing")
        results = []
        completed_steps = set()

        steps = plan.get("steps", [])
        max_retries = 3

        for step in steps:
            step_id = step.get("id", "unknown")

            # Check dependencies
            deps = step.get("dependencies", [])
            if deps:
                unmet = [d for d in deps if d not in completed_steps]
                if unmet:
                    logger.warning("Step %s has unmet dependencies: %s", step_id, unmet)
                    results.append({"step": step_id, "status": "skipped", "reason": "unmet dependencies"})
                    continue

            # Execute step with retries
            step_result = None
            for attempt in range(max_retries):
                step_result = await self._execute_step(step, task_id)
                if step_result.get("status") == "success":
                    completed_steps.add(step_id)
                    break
                elif step_result.get("status") == "blocked":
                    break
                elif attempt < max_retries - 1:
                    logger.info("Retrying step %s (attempt %d)", step_id, attempt + 2)
                    await asyncio.sleep(1 * (attempt + 1))

            results.append({"step": step_id, **step_result})

            # Update world state with progress
            completed_count = len(completed_steps)
            total_count = len(steps)
            world_state.update(estimated_progress=completed_count / total_count if total_count > 0 else 0)

        return {
            "steps_executed": len(results),
            "steps_completed": len(completed_steps),
            "results": results,
        }

    async def _execute_step(self, step: dict, task_id: str) -> dict:
        """Execute a single plan step."""
        step_id = step.get("id", "unknown")
        description = step.get("description", "")
        tool = step.get("tool")
        params = step.get("parameters", {})
        risk_level = step.get("risk_level", 0)

        logger.info("Executing step %s: %s", step_id, description[:60])

        world_state.add_recent_action({"step": step_id, "description": description})

        # Policy check: evaluate deterministic SecurityPolicy (never trust model risk_level)
        if tool and self._tool_executor:
            from tools.registry import tool_registry
            from tools.security import security_policy
            tool_def = tool_registry.get(tool)
            if tool_def:
                allowed, reason, _ = security_policy.evaluate(tool_def, params)
                if not allowed:
                    logger.warning("Step %s blocked by security_policy: %s", step_id, reason)
                    return {"status": "blocked", "reason": reason}

        # Execute: either tool call or LLM reasoning
        if tool and self._tool_executor:
            return await self._execute_tool_step(tool, params, step)
        else:
            return await self._execute_reasoning_step(description, params)

    async def _execute_tool_step(self, tool: str, params: dict, step: dict) -> dict:
        """Execute a tool-based step."""
        try:
            result = await self._tool_executor.execute(tool, params)
            success = result.get("success", False)
            return {
                "status": "success" if success else "failure",
                "tool": tool,
                "result": result.get("result", ""),
                "error": result.get("error"),
            }
        except Exception as e:
            logger.error("Tool execution failed: %s", e)
            return {"status": "failure", "tool": tool, "error": str(e)}

    async def _execute_reasoning_step(self, description: str, params: dict) -> dict:
        """Execute a reasoning/LLM step."""
        if not self._llm_gateway:
            return {"status": "failure", "error": "No LLM gateway available"}

        try:
            prompt = params.get("query", description)
            response = await self._llm_gateway.generate(
                prompt=prompt,
                task_type="reasoning",
                max_tokens=1000,
            )
            return {
                "status": "success",
                "result": response.text,
                "provider": response.provider,
            }
        except Exception as e:
            return {"status": "failure", "error": str(e)}

    async def _verify_final(self, execution_result: dict, goal: str) -> dict:
        """Verify the final execution result against the goal."""
        logger.info("Phase 4: VERIFY — checking final result")

        completed = execution_result.get("steps_completed", 0)
        total = execution_result.get("steps_executed", 0)
        failures = sum(1 for r in execution_result.get("results", []) if r.get("status") == "failure")

        if failures == 0 and completed > 0:
            status = "success"
        elif completed > failures:
            status = "partial_success"
        elif completed == 0 and total > 0:
            status = "failure"
        else:
            status = "unknown"

        # Use LLM to evaluate if goal was achieved (for complex tasks)
        if self._llm_gateway and total > 3:
            try:
                eval_response = await self._llm_gateway.generate(
                    prompt=build_verification_prompt(
                        step_description=goal,
                        expected_result="Goal should be achieved",
                        actual_result=json.dumps(execution_result.get("results", []), default=str)[:1000],
                    ),
                    task_type="reasoning",
                    max_tokens=200,
                )
                if eval_response.text:
                    try:
                        parsed = json.loads(eval_response.text)
                        status = parsed.get("status", status).lower()
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass

        return {
            "status": status,
            "completed_steps": completed,
            "total_steps": total,
            "failures": failures,
        }

    async def _record_experience(
        self,
        task_id: str,
        goal: str,
        plan: dict,
        result: dict,
        verification: dict,
    ) -> None:
        """Record the experience for future learning."""
        logger.info("Phase 5: RECORD — storing experience")

        experience = {
            "task_id": task_id,
            "goal": goal,
            "plan_summary": f"{len(plan.get('steps', []))} steps",
            "result_status": verification.get("status", "unknown"),
            "completed_steps": result.get("steps_completed", 0),
            "total_steps": result.get("steps_executed", 0),
            "timestamp": time.time(),
        }

        self._task_history.append(experience)

        # Store in memory if available
        if self._memory_manager:
            try:
                content = f"Task: {goal}\nResult: {verification.get('status', 'unknown')} ({result.get('steps_completed', 0)}/{result.get('steps_executed', 0)} steps)"
                await self._memory_manager.remember(
                    content=content,
                    memory_type="episodic",
                    metadata=experience,
                )
            except Exception as e:
                logger.warning("Failed to record experience: %s", e)

    async def process_utterance(
        self,
        text: str,
        session_id: str = "default",
    ) -> dict[str, Any]:
        """Process a voice/text utterance (backward-compatible interface)."""
        return await self.process_goal(text, session_id)


# Global singleton
cognitive_orchestrator = CognitiveOrchestrator()
