from unittest.mock import MagicMock, patch
import pytest

from jarvis.brain import LLMBrain
from jarvis.config import LLMConfig
from jarvis.planner import TaskPlanner


def test_brain_offline_math():
    brain = LLMBrain(config=LLMConfig(provider="ollama", api_key=None, base_url="", model=""))
    
    res1 = brain.ask("what is 25 plus 15")
    assert "40" in res1
    assert "boss" in res1

    res2 = brain.ask("calculate 12 times 8")
    assert "96" in res2


def test_brain_offline_greetings_and_identity():
    brain = LLMBrain(config=LLMConfig(provider="ollama", api_key=None, base_url="", model=""))

    res_hi = brain.ask("hello jarvis")
    assert "boss" in res_hi.lower()
    assert "operational" in res_hi.lower()

    res_id = brain.ask("who are you")
    assert "JARVIS" in res_id
    assert "boss" in res_id.lower()


def test_brain_speech_cleaner():
    brain = LLMBrain()
    dirty_text = "**Yes boss**, here is the _answer_: `sudo apt update` # Important [link](http://test.com)"
    cleaned = brain._clean_speech_output(dirty_text)
    assert "**" not in cleaned
    assert "_" not in cleaned
    assert "`" not in cleaned
    assert "#" not in cleaned
    assert "link" not in cleaned
    assert "Yes boss, here is the answer: sudo apt update Important" == cleaned


def test_brain_llm_api_call_success():
    config = LLMConfig(provider="groq", api_key="gsk_test_key", base_url="https://api.groq.com/openai/v1", model="test-model")
    brain = LLMBrain(config=config)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {"message": {"content": "Nikola Tesla was an electrical engineer and inventor, boss."}}
        ]
    }

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        answer = brain.ask("who was Nikola Tesla")
        assert "Nikola Tesla" in answer
        assert "boss" in answer
        assert mock_post.called


def test_planner_fallback_to_brain():
    planner = TaskPlanner()
    report = planner.process("how are you doing today")

    assert report.success is True
    assert len(report.results) == 1
    assert report.results[0].data.get("source") == "llm_brain"
    assert "boss" in report.summary_message.lower()
