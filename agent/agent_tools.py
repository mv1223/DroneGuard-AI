"""LangChain-compatible security analyst tools grounded in SQLite."""

from __future__ import annotations

import json
from typing import Any

from core.video_summarizer import (
    generate_daily_intelligence_report,
    one_sentence_video_summary,
)


def build_tools(repository: Any) -> list[Any]:
    """Build structured tools for LangChain or direct invocation.

    Falls back gracefully to an empty list if langchain_core is unavailable.
    """
    try:
        from langchain_core.tools import tool
    except ImportError:
        return []

    @tool
    def search_frames_tool(
        query: str = "",
        object_type: str = "",
        color: str = "",
        location: str = "",
        start_time: str = "",
        end_time: str = "",
        source_video: str = "",
    ) -> str:
        """Search indexed drone frames by description, object category, color, zone, time range, or video."""
        rows = repository.search_frames(
            query=query or None,
            object_type=object_type or None,
            color=color or None,
            location=location or None,
            start=start_time or None,
            end=end_time or None,
            source_video=source_video or None,
        )
        return json.dumps(rows[:25], default=str) if rows else "No matching frames found."

    @tool
    def search_vehicle_events(color: str = "", location: str = "") -> str:
        """Search indexed vehicle and truck detections, optionally filtered by color or zone."""
        rows = repository.search_detections(
            object_type="vehicle",
            color=color or None,
            location=location or None,
        )
        return json.dumps(rows[:25], default=str) if rows else "No vehicle observations found."

    @tool
    def search_person_events(location: str = "") -> str:
        """Search all indexed person observations, optionally filtered by zone/location."""
        rows = repository.search_detections(
            object_type="person",
            location=location or None,
        )
        return json.dumps(rows[:25], default=str) if rows else "No person observations found."

    @tool
    def get_security_alerts(severity: str = "", unacknowledged_only: bool = False) -> str:
        """Retrieve prioritized security and drone-safety alerts."""
        rows = repository.list_alerts(
            severity=severity or None,
            unacknowledged_only=unacknowledged_only,
        )
        return json.dumps(rows[:25], default=str) if rows else "No alerts found."

    @tool
    def check_repeated_observations() -> str:
        """Retrieve correlated repeated-vehicle and loitering events across frames."""
        rep = repository.search_events(event_type="repeated_vehicle_observation")
        loiter = repository.search_events(event_type="loitering_suspected")
        return json.dumps({"repeated_vehicles": rep, "loitering": loiter}, default=str)

    @tool
    def get_telemetry_summary() -> str:
        """Retrieve the latest drone telemetry state and recent telemetry history."""
        latest = repository.get_latest_telemetry()
        history = repository.list_telemetry(limit=10)
        return json.dumps({"latest": latest, "recent": history}, default=str)

    @tool
    def get_daily_summary() -> str:
        """Generate a structured daily intelligence summary from indexed SQLite records."""
        return json.dumps(generate_daily_intelligence_report(repository), default=str)

    @tool
    def summarize_video_tool(source_video: str) -> str:
        """Return a one-sentence grounded summary for a processed source video."""
        return one_sentence_video_summary(repository, source_video)

    return [
        search_frames_tool,
        search_vehicle_events,
        search_person_events,
        get_security_alerts,
        check_repeated_observations,
        get_telemetry_summary,
        get_daily_summary,
        summarize_video_tool,
    ]
