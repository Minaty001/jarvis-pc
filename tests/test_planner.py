import pytest
from jarvis.planner import TaskPlanner


def test_split_single_clause():
    planner = TaskPlanner()
    clauses = planner.split_clauses("what time is it")
    assert clauses == ["what time is it"]


def test_split_multi_clauses_with_and():
    planner = TaskPlanner()
    clauses = planner.split_clauses("what time is it and what is today's date")
    assert len(clauses) == 2
    assert "time" in clauses[0]
    assert "date" in clauses[1]


def test_split_multi_clauses_complex_conjunctions():
    planner = TaskPlanner()
    command = "open terminal, then search google for AI, and also check system status"
    clauses = planner.split_clauses(command)
    assert len(clauses) == 3
    assert clauses[0] == "open terminal"
    assert "search google for AI" in clauses[1]
    assert "check system status" in clauses[2]


def test_plan_single_task():
    planner = TaskPlanner()
    steps = planner.plan("tell me the time")
    assert len(steps) == 1
    assert steps[0].action.name == "tell_time"


def test_plan_multi_action_tasks():
    planner = TaskPlanner()
    command = "what time is it and check battery status and tell me the date"
    steps = planner.plan(command)
    assert len(steps) == 3
    assert steps[0].action.name == "tell_time"
    assert steps[1].action.name == "system_stats"
    assert steps[2].action.name == "tell_date"


def test_execute_multi_action_plan():
    planner = TaskPlanner()
    report = planner.process("what is the time, tell me the date, and check system status")
    assert report.success is True
    assert len(report.results) == 3
    assert "It is" in report.summary_message
    assert "Today is" in report.summary_message
    assert "CPU at" in report.summary_message
