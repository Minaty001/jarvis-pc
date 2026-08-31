# Multi-Action Workflows Architecture

## Compound Goal Decomposition
Natural language compound requests containing conjunctions (e.g., *"aur uske baad"*, *"or uske baad"*, *"and then"*, *"after that"*, *"phir"*) are automatically decomposed by `TaskManager._build_steps()` into an ordered sequence of dependent `TaskStep` objects.

Each `TaskStep` specifies:
- `action`: Registered tool name or reasoning action
- `parameters`: Action arguments
- `dependencies`: List of parent `step.id`s required before execution

## DAG Parallelism & Safety
- **Concurrent Execution**: Steps without inter-dependencies execute concurrently up to `max_parallel_steps` (default 4).
- **Dependency Isolation**: If a required step fails, all downstream dependent steps transition to `SKIPPED` with `reason="dependency failed"`.
- **Optional Steps**: Steps with `required=False` log failures without interrupting execution of parallel or dependent steps.
