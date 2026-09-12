import pytest
from jarvis.engine import EngineState, JarvisEngine


def test_engine_initialization():
    engine = JarvisEngine(threshold=0.35, auto_start=False)
    assert not engine.is_running
    assert engine.wakeword_model is not None
    assert engine.transcriber is not None
    assert engine.planner is not None
    assert engine.state == EngineState.WAKE_WORD_LISTENING


def test_engine_process_text_command():
    engine = JarvisEngine(auto_start=False)
    report = engine.process_text_command("what time is it and what day is today")
    assert report.success is True
    assert len(report.results) == 2
    assert "It is" in report.summary_message
    assert "Today is" in report.summary_message
