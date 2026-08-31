# Task Engine Test Matrix

| Subsystem | Test Module | Test Name | Assertion | Status |
|---|---|---|---|---|
| Models | `test_models.py` | `test_task_default_state` | State defaults to DRAFT | PASS |
| Models | `test_models.py` | `test_task_step_default_state` | State defaults to PENDING | PASS |
| Models | `test_models.py` | `test_action_result_success` | ok() returns verified result | PASS |
| Models | `test_models.py` | `test_action_result_failure_retryable` | Failure code flags retryable | PASS |
| Repository | `test_repository.py` | `test_create_and_get_task` | Task persists & loads from SQLite | PASS |
| Repository | `test_repository.py` | `test_update_task_state` | State transition updates SQLite | PASS |
| Repository | `test_repository.py` | `test_save_and_get_schedule` | Schedule persists & loads | PASS |
| Repository | `test_repository.py` | `test_checkpoint_roundtrip` | Step checkpoints save & load | PASS |
| DAG Executor | `test_dag_executor.py` | `test_linear_dag_all_complete` | Dependent steps run sequentially | PASS |
| DAG Executor | `test_dag_executor.py` | `test_independent_steps_run_in_parallel` | Independent steps run concurrently | PASS |
| DAG Executor | `test_dag_executor.py` | `test_failed_step_marks_dependents_skipped` | Failed required step skips dependents | PASS |
| NL Parser | `test_nl_parser.py` | `test_weekday_at_8am` | "every weekday at 8 AM" -> Cron | PASS |
| NL Parser | `test_nl_parser.py` | `test_every_30_minutes` | "every 30 minutes" -> Interval | PASS |
| Scheduler | `test_scheduler.py` | `test_one_shot_fires` | One-shot job triggers callback | PASS |
| Scheduler | `test_scheduler.py` | `test_interval_fires_repeatedly` | Interval job triggers repeatedly | PASS |
| Approval | `test_approval.py` | `test_high_risk_tool_needs_approval` | High-risk tool flags approval | PASS |
| Approval | `test_approval.py` | `test_grant_unblocks_waiting` | Grant decision unblocks step | PASS |
| Recovery | `test_recovery.py` | `test_running_task_gets_recovered` | Interrupted task resumes from DB | PASS |
| Manager | `test_manager.py` | `test_submit_creates_task` | Submit creates planned Task | PASS |
| Routines | `test_routines.py` | `test_builtin_templates_exist` | Morning/Work/Evening templates present | PASS |
| Conditions | `test_conditions.py` | `test_battery_condition_defined` | Battery low condition registered | PASS |
| Integration | `test_integration.py` | `test_orchestrator_uses_task_manager` | Orchestrator delegates to TaskManager | PASS |
