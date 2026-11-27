from unittest.mock import patch

from agent.security_agent import SecurityAgent
from core.video_summarizer import one_sentence_video_summary
from database.repository import Repository
from scripts.generate_sample_data import load_demo


def test_agent_handles_empty_database(tmp_path):
    agent = SecurityAgent(Repository(tmp_path / "agent.db"))
    assert "No vehicle observations" in agent.ask("How many trucks were observed?")


def test_agent_queries_and_followup_context(tmp_path):
    repo = load_demo(reset=True, db_path=tmp_path / "demo.db")
    agent = SecurityAgent(repo)

    blue_ans = agent.ask("Show all observations of blue vehicles")
    assert "FR-0001" in blue_ans and "FR-0004" in blue_ans

    followup = agent.ask("Which frames were those?")
    assert "FR-0001" in followup

    midnight = agent.ask("Was anyone near the main gate at midnight?")
    assert "FR-0003" in midnight

    repeated = agent.ask("Did the same vehicle appear more than once?")
    assert "repeated" in repeated.lower()

    window = agent.ask("What happened between 12 PM and 3 PM?")
    assert "FR-0001" in window
    assert "FR-0003" not in window  # 00:01 AM must be excluded

    summary = agent.ask("Summarize today's drone activity")
    assert "6 frame(s)" in summary


def test_agent_llm_mode_with_mock_and_fallback(tmp_path):
    repo = load_demo(reset=True, db_path=tmp_path / "llm.db")
    agent = SecurityAgent(repo, llm_provider="openai")
    # Missing API key falls back cleanly to offline grounded response
    out = agent.ask_structured("Which security events require attention?")
    assert out["mode"] == "offline-grounded"
    assert "HIGH" in out["answer"] or "CRITICAL" in out["answer"]

    with patch("agent.security_agent.OPENAI_API_KEY", "fake-key"), patch(
        "agent.security_agent.httpx.post"
    ) as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = lambda: None
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "Two blue truck sightings (FR-0001, FR-0004)."}}]
        }
        out2 = agent.ask_structured("How many vehicles were detected?")
    assert out2["mode"] == "llm:openai"
    assert "FR-0001" in out2["answer"]


def test_one_sentence_video_summary(tmp_path):
    repo = Repository(tmp_path / "vid.db")
    repo.add_frame(
        {
            "frame_id": "FR-V1",
            "timestamp": "2026-11-27T12:00:00",
            "description": "Blue truck",
            "location": "Main Gate",
            "source_video": "patrol.mp4",
            "detections": [{"object_type": "truck", "color": "blue", "confidence": 0.9}],
        }
    )
    summary = one_sentence_video_summary(repo, "patrol.mp4")
    assert "patrol.mp4" in summary and "1 frames" in summary
