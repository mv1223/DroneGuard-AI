"""End-to-end internal workflow verification across media, DB, alerts, agent, and reports."""

from __future__ import annotations

import json

from agent.security_agent import SecurityAgent
from core.pipeline import SecurityPipeline
from core.telemetry import generate_telemetry
from core.video_summarizer import (
    format_daily_report_markdown,
    generate_daily_intelligence_report,
    one_sentence_video_summary,
)
from database.repository import Repository
from scripts.generate_sample_media import generate_sample_media


def test_full_internal_workflows_end_to_end(tmp_path):
    media = generate_sample_media(tmp_path / "media")
    repo = Repository(tmp_path / "full.db")
    pipeline = SecurityPipeline(repo)

    # 1. Telemetry ingestion + critical alert check
    tel = generate_telemetry(
        timestamp="2026-11-27T12:00:00",
        location="Main Gate",
        battery=12,
        altitude=75,
    ).to_dict()
    tid, tel_alerts = pipeline.ingest_telemetry(tel)
    assert tid > 0
    assert any(a["alert_type"] == "critical_battery" for a in tel_alerts)
    assert any(a["alert_type"] == "altitude_violation" for a in tel_alerts)

    # 2. Image analysis & persistence
    img_res = pipeline.ingest_image(
        image_path=media["garage_blue_truck"],
        timestamp="2026-11-27T12:00:05",
        location="Garage",
        provider_name="opencv_heuristic",
        telemetry_id=tid,
    )
    assert img_res["frame"]["analysis_mode"] == "local_cv_heuristic"

    # 3. Video extraction & multi-frame indexing
    vid_res = pipeline.ingest_video(
        video_path=media["property_patrol_demo"],
        interval_seconds=4.0,
        max_frames=10,
        base_timestamp="2026-11-27T12:10:00",
        location="Perimeter",
        provider_name="opencv_heuristic",
        source_video_name="property_patrol_demo.mp4",
    )
    assert vid_res["extraction"].extracted_count == 4
    summary_sentence = one_sentence_video_summary(repo, "property_patrol_demo.mp4")
    assert "property_patrol_demo.mp4" in summary_sentence

    # 4. Multi-facet Frame Intelligence search
    blue_frames = repo.search_frames(object_type="vehicle", color="blue")
    assert len(blue_frames) >= 1
    details = repo.get_frame_details(blue_frames[0]["frame_id"])
    assert details is not None and len(details["detections"]) >= 1

    # 5. Alert triage workflow (open -> acknowledged -> resolved)
    alerts = repo.list_alerts()
    assert len(alerts) >= 2
    repo.update_alert_status(alerts[0]["alert_id"], "acknowledged")
    repo.update_alert_status(alerts[0]["alert_id"], "resolved")
    updated = [a for a in repo.list_alerts() if a["alert_id"] == alerts[0]["alert_id"]][0]
    assert updated["status"] == "resolved"

    # 6. Grounded SecurityAgent + multi-turn follow-up
    agent = SecurityAgent(repo)
    ans1 = agent.ask_structured("Show all observations of blue vehicles")
    assert len(ans1["cited_frame_ids"]) >= 1
    ans2 = agent.ask_structured("Which frames were those?")
    assert ans1["cited_frame_ids"][0] in ans2["answer"]

    # 7. Daily intelligence report & JSON/Markdown serialization
    report = generate_daily_intelligence_report(repo)
    md = format_daily_report_markdown(report)
    assert report["total_frames"] == 5
    assert "DroneGuard AI" in md
    assert json.dumps(report, default=str)
