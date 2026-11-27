"""Video summarization and structured daily intelligence reporting."""

from __future__ import annotations

from collections import Counter
from typing import Any


def summarize_records(repository: Any, start: str | None = None, end: str | None = None) -> str:
    """Produce a concise monitoring summary paragraph for the selected period."""
    frames = repository.search_frames(start=start, end=end)
    events = repository.search_events(start=start, end=end)
    alerts = repository.list_alerts(start=start, end=end)
    vehicles = sum(1 for e in events if "vehicle" in e["event_type"])
    people = sum(
        1
        for e in events
        if e["event_type"] in ("person_detected", "midnight_person_presence", "loitering_suspected")
    )
    critical = sum(1 for a in alerts if str(a["severity"]).lower() == "critical")
    high = sum(1 for a in alerts if str(a["severity"]).lower() == "high")
    if not frames:
        return "No indexed frames are available for the selected monitoring period."
    return (
        f"Monitoring summary: {len(frames)} frame(s) processed, "
        f"{vehicles} vehicle-related event(s), {people} person-related event(s), "
        f"and {len(alerts)} alert(s) ({critical} critical, {high} high priority)."
    )


def one_sentence_video_summary(repository: Any, source_video: str) -> str:
    """Generate an evidence-grounded one-sentence summary of a processed video."""
    frames = repository.search_frames(source_video=source_video)
    if not frames:
        return f"No indexed frames were found for video '{source_video}'."

    frame_ids = [f["frame_id"] for f in frames]
    dets = repository.get_detections_for_frames(frame_ids)
    obj_counts = Counter(d["object_type"] for d in dets)
    locations = sorted({f["location"] for f in frames if f.get("location")})
    alerts = [a for a in repository.list_alerts() if a.get("frame_id") in set(frame_ids)]

    det_parts = [f"{cnt} {obj}" for obj, cnt in obj_counts.most_common(3)]
    det_text = ", ".join(det_parts) if det_parts else "no objects detected"
    alert_text = f"triggering {len(alerts)} alert(s)" if alerts else "with no security alerts"
    return (
        f"Video '{source_video}' ({len(frames)} frames, {frames[0]['timestamp']} to {frames[-1]['timestamp']} "
        f"at {', '.join(locations) or 'Perimeter'}) recorded {det_text}, {alert_text}."
    )


def generate_daily_intelligence_report(
    repository: Any, start: str | None = None, end: str | None = None
) -> dict[str, Any]:
    """Compile a structured daily security intelligence report from SQLite."""
    frames = repository.search_frames(start=start, end=end)
    events = repository.search_events(start=start, end=end)
    alerts = repository.list_alerts(start=start, end=end)
    telemetry = repository.list_telemetry(limit=500)
    dets = repository.get_detections_for_frames([f["frame_id"] for f in frames]) if frames else []

    object_counts = dict(Counter(d["object_type"] for d in dets))
    location_counts = dict(Counter(f.get("location", "Unknown") for f in frames))
    mode_counts = dict(Counter(f.get("analysis_mode", "simulation") for f in frames))
    severity_counts = dict(Counter(str(a["severity"]).lower() for a in alerts))
    repeated = [e for e in events if e["event_type"] == "repeated_vehicle_observation"]
    loitering = [e for e in events if e["event_type"] == "loitering_suspected"]

    recommendations: list[str] = []
    if severity_counts.get("critical", 0) > 0:
        recommendations.append(
            "Investigate all CRITICAL alerts immediately and verify linked frame evidence."
        )
    if any(a["alert_type"] in ("low_battery", "critical_battery") for a in alerts):
        recommendations.append(
            "Schedule drone battery health diagnostics and verify dock charging contacts."
        )
    if any(a["alert_type"] == "midnight_person_presence" for a in alerts):
        recommendations.append(
            "Review perimeter lighting and gate access logs for overnight personnel activity."
        )
    if repeated:
        recommendations.append(
            "Cross-check repeated vehicle sightings against authorized visitor/delivery schedules."
        )
    if not recommendations:
        recommendations.append(
            "Perimeter nominal. Continue routine scheduled patrol intervals."
        )

    return {
        "summary_text": summarize_records(repository, start=start, end=end),
        "total_frames": len(frames),
        "total_detections": len(dets),
        "total_events": len(events),
        "total_alerts": len(alerts),
        "object_counts": object_counts,
        "location_counts": location_counts,
        "analysis_modes": mode_counts,
        "severity_counts": severity_counts,
        "repeated_observations": repeated,
        "loitering_events": loitering,
        "alerts": alerts,
        "telemetry_count": len(telemetry),
        "recommendations": recommendations,
    }


def format_daily_report_markdown(report: dict[str, Any]) -> str:
    """Format a structured daily intelligence report as clean Markdown."""
    lines = [
        "# DroneGuard AI — Daily Security Intelligence Report",
        "",
        "## Executive Summary",
        report["summary_text"],
        "",
        "## Operational Metrics",
        f"- **Indexed Frames:** {report['total_frames']}",
        f"- **Object Detections:** {report['total_detections']}",
        f"- **Correlated Events:** {report['total_events']}",
        f"- **Alerts:** {report['total_alerts']} ({report['severity_counts']})",
        f"- **Telemetry Records:** {report['telemetry_count']}",
        f"- **Analysis Modes Used:** {report['analysis_modes']}",
        "",
        "## Detections by Category",
    ]
    if report["object_counts"]:
        for k, v in report["object_counts"].items():
            lines.append(f"- `{k}`: {v}")
    else:
        lines.append("- None recorded.")

    lines.extend(["", "## Repeated Observations & Loitering"])
    combined = report["repeated_observations"] + report["loitering_events"]
    if combined:
        for e in combined:
            lines.append(f"- **[{e['severity'].upper()}] {e['timestamp']} ({e['location']}):** {e['explanation']}")
    else:
        lines.append("- No repeated-vehicle or loitering events recorded.")

    lines.extend(["", "## Prioritized Security & Safety Alerts"])
    if report["alerts"]:
        for a in report["alerts"]:
            lines.append(
                f"- **[{a['severity'].upper()} | {a.get('status', 'open')}] {a['alert_type']}** "
                f"({a['timestamp']}, count={a.get('occurrence_count', 1)}): {a['message']}"
            )
    else:
        lines.append("- No alerts recorded.")

    lines.extend(["", "## Operator Recommendations"])
    for rec in report["recommendations"]:
        lines.append(f"- {rec}")

    return "\n".join(lines)
