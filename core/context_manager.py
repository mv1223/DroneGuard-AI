"""Context management, multi-turn follow-up resolution, and grounded offline Q&A."""

from __future__ import annotations

import re
from typing import Any

from core.video_summarizer import (
    generate_daily_intelligence_report,
    one_sentence_video_summary,
    summarize_records,
)

KNOWN_COLORS = ("blue", "red", "black", "white", "silver", "grey", "gray", "green")
KNOWN_ZONES = ("main gate", "parking area", "restricted zone", "restricted area", "garage", "loading dock", "perimeter")


def _parse_hour_token(hour_str: str, ampm: str | None) -> int:
    hour = int(hour_str)
    if ampm:
        ap = ampm.lower()
        if ap == "pm" and hour != 12:
            hour += 12
        elif ap == "am" and hour == 12:
            hour = 0
    return max(0, min(23, hour))


def extract_time_window(question: str) -> tuple[str | None, str | None]:
    """Parse natural-language time windows such as 'between 12 PM and 3 PM' or '12:00 to 15:00'."""
    q = question.lower()
    m = re.search(
        r"between\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+(?:and|to|-)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
        q,
    )
    if not m:
        m = re.search(
            r"from\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
            q,
        )
    if m:
        h1 = _parse_hour_token(m.group(1), m.group(3))
        min1 = int(m.group(2) or 0)
        h2 = _parse_hour_token(m.group(4), m.group(6))
        min2 = int(m.group(5) or 0)
        return f"{h1:02d}:{min1:02d}:00", f"{h2:02d}:{min2:02d}:59"
    if "midnight" in q or "night" in q:
        return "00:00:00", "05:00:00"
    return None, None


class ContextManager:
    """Maintains multi-turn analyst state and executes grounded SQLite queries."""

    def __init__(self, repository: Any):
        self.repo = repository
        self.history: list[dict[str, str]] = []
        self.state: dict[str, Any] = {
            "last_object_type": None,
            "last_color": None,
            "last_location": None,
            "last_time_window": (None, None),
            "last_frame_ids": [],
        }

    def reset(self) -> None:
        self.history.clear()
        self.state = {
            "last_object_type": None,
            "last_color": None,
            "last_location": None,
            "last_time_window": (None, None),
            "last_frame_ids": [],
        }

    def _extract_entities(self, question: str) -> dict[str, Any]:
        q = question.lower()
        color = next((c for c in KNOWN_COLORS if re.search(rf"\b{c}\b", q)), None)
        location = next((z.title() for z in KNOWN_ZONES if z in q), None)
        if not location and "gate" in q:
            location = "Main Gate"
        elif not location and "parking" in q:
            location = "Parking Area"
        elif not location and "restricted" in q:
            location = "Restricted"

        time_start, time_end = extract_time_window(question)

        obj_type = None
        if any(w in q for w in ("truck", "vehicle", "car", "pickup", "suv", "van")):
            obj_type = "vehicle"
        elif any(w in q for w in ("person", "people", "someone", "anyone", "intruder", "pedestrian")):
            obj_type = "person"

        # Follow-up resolution if user omits entity and references prior turn
        is_followup = any(
            w in q
            for w in ("what about", "how about", "those", "them", "that", "which frames", "show frames", "there")
        )
        if is_followup:
            obj_type = obj_type or self.state.get("last_object_type")
            color = color or self.state.get("last_color")
            if not location:
                location = self.state.get("last_location")
        return {
            "object_type": obj_type,
            "color": color,
            "location": location,
            "time_start": time_start,
            "time_end": time_end,
            "is_followup": is_followup,
        }

    def _filter_by_time_of_day(
        self, rows: list[dict[str, Any]], start_hms: str | None, end_hms: str | None
    ) -> list[dict[str, Any]]:
        if not start_hms or not end_hms:
            return rows
        matched = []
        for r in rows:
            ts = r.get("timestamp", "")
            time_part = ts.split("T")[-1][:8] if "T" in ts else ts[-8:]
            if start_hms <= time_part <= end_hms:
                matched.append(r)
        return matched

    def build_grounded_context(self, question: str) -> dict[str, Any]:
        """Retrieve all relevant database records needed to answer the question."""
        entities = self._extract_entities(question)
        q = question.lower()

        frames = self.repo.search_frames(
            location=entities["location"],
            object_type=entities["object_type"],
            color=entities["color"],
        )
        frames = self._filter_by_time_of_day(frames, entities["time_start"], entities["time_end"])
        events = self.repo.search_events(
            object_type=entities["object_type"],
            location=entities["location"],
        )
        events = self._filter_by_time_of_day(events, entities["time_start"], entities["time_end"])
        alerts = self.repo.list_alerts()
        telemetry = self.repo.get_latest_telemetry()
        counts = self.repo.counts()

        return {
            "question": question,
            "entities": entities,
            "counts": counts,
            "matching_frames": frames[:25],
            "matching_events": events[:25],
            "alerts": alerts[:20],
            "latest_telemetry": telemetry,
            "daily_summary": summarize_records(self.repo),
            "wants_repeated": any(w in q for w in ("same", "more than once", "repeat", "again", "twice", "multiple")),
            "wants_summary": any(w in q for w in ("summarize", "summary", "report", "overview", "today's drone activity")),
            "wants_alerts": any(w in q for w in ("alert", "attention", "critical", "warning", "security event", "threat", "loiter")),
            "wants_telemetry": any(w in q for w in ("battery", "altitude", "telemetry", "drone status", "speed", "position")),
        }

    def answer_offline(self, question: str) -> str:
        """Answer a security question deterministically from indexed SQLite records."""
        ctx = self.build_grounded_context(question)
        entities = ctx["entities"]
        q = question.lower()
        answer_lines: list[str] = []
        cited_frames: list[str] = []

        # 1. Which frames follow-up
        if ("which frames" in q or "frame id" in q) and self.state.get("last_frame_ids"):
            fids = self.state["last_frame_ids"]
            details = [self.repo.get_frame_details(fid) for fid in fids]
            details = [d for d in details if d]
            if details:
                lines = [
                    f"- **{d['frame_id']}** ({d['timestamp']} | {d['location']} | mode={d.get('analysis_mode', 'simulation')}): {d['description']}"
                    for d in details
                ]
                reply = "Evidence frames from the previous query:\n" + "\n".join(lines)
                self._record_turn(question, reply, entities, [d["frame_id"] for d in details])
                return reply

        # 2. Repeated vehicle question
        if ctx["wants_repeated"]:
            rep_events = self.repo.search_events(event_type="repeated_vehicle_observation")
            veh_dets = self.repo.search_detections(object_type="vehicle", color=entities["color"])
            if rep_events:
                lines = [f"- **{e['frame_id']}** ({e['timestamp']} | {e['location']}): {e['explanation']}" for e in rep_events]
                cited_frames = [e["frame_id"] for e in rep_events]
                reply = (
                    f"Found {len(rep_events)} repeated vehicle correlation(s) across {len(veh_dets)} total vehicle detection(s):\n"
                    + "\n".join(lines)
                )
            elif len(veh_dets) > 1:
                lines = [f"- **{d['frame_id']}** ({d['timestamp']} | {d['location']}): {d.get('color') or 'unspecified'} {d['object_type']}" for d in veh_dets]
                cited_frames = [d["frame_id"] for d in veh_dets]
                reply = (
                    f"Found {len(veh_dets)} vehicle observation(s) with matching attributes "
                    "(note: persistent vehicle re-ID is not performed):\n" + "\n".join(lines)
                )
            else:
                reply = "No repeated vehicle observations were found in the indexed records."
            self._record_turn(question, reply, entities, cited_frames)
            return reply

        # 3. Daily summary / video summary
        if ctx["wants_summary"]:
            videos = self.repo.list_source_videos()
            report = generate_daily_intelligence_report(self.repo)
            parts = [report["summary_text"]]
            if videos:
                parts.append("Video summaries:")
                for v in videos:
                    parts.append(f"- {one_sentence_video_summary(self.repo, v)}")
            if report["alerts"]:
                parts.append(
                    f"Top alert: [{report['alerts'][0]['severity'].upper()}] {report['alerts'][0]['message']}"
                )
            reply = "\n".join(parts)
            self._record_turn(question, reply, entities, [])
            return reply

        # 4. Telemetry status query
        if ctx["wants_telemetry"]:
            t = ctx["latest_telemetry"]
            if not t:
                reply = "No drone telemetry records are currently indexed."
            else:
                reply = (
                    f"Latest telemetry for **{t['drone_id']}** ({t['timestamp']}): "
                    f"Status={t['flight_status']}, Location={t['location_name']} "
                    f"({t['latitude']:.4f}, {t['longitude']:.4f}), Altitude={t['altitude']}m, "
                    f"Battery={t['battery_percentage']}%, Speed={t['speed']} m/s."
                )
            self._record_turn(question, reply, entities, [])
            return reply

        # 5. Alerts / security attention query
        if ctx["wants_alerts"]:
            alerts = ctx["alerts"]
            if "critical" in q:
                alerts = [a for a in alerts if str(a["severity"]).lower() == "critical"]
            elif "require attention" in q or "open" in q or "unacknowledged" in q:
                alerts = [a for a in alerts if a.get("status", "open") != "resolved" and not a.get("acknowledged")]
            if not alerts:
                reply = "There are no matching alerts requiring attention in the indexed records."
            else:
                lines = [
                    f"- **[{a['severity'].upper()} | {a.get('status', 'open')}]** {a['timestamp']} "
                    f"(frame={a.get('frame_id') or 'telemetry'}, count={a.get('occurrence_count', 1)}): {a['message']}"
                    for a in alerts
                ]
                cited_frames = [a["frame_id"] for a in alerts if a.get("frame_id")]
                reply = f"Found {len(alerts)} alert(s):\n" + "\n".join(lines)
            self._record_turn(question, reply, entities, cited_frames)
            return reply

        # 6. Vehicle / Person / Time-range / Zone query
        if entities["object_type"] == "vehicle":
            dets = self.repo.search_detections(
                object_type="vehicle",
                color=entities["color"],
                location=entities["location"],
            )
            dets = self._filter_by_time_of_day(dets, entities["time_start"], entities["time_end"])
            if not dets:
                reply = "No vehicle observations were found in the indexed records."
            else:
                lines = [
                    f"- **{d['frame_id']}** ({d['timestamp']} — {d['location']}): "
                    f"{d.get('description') or d['frame_description']}"
                    for d in dets
                ]
                cited_frames = [d["frame_id"] for d in dets]
                label = f"{entities['color']} vehicle" if entities["color"] else "vehicle"
                reply = f"Found {len(dets)} {label} observation(s):\n" + "\n".join(lines)
            self._record_turn(question, reply, entities, cited_frames)
            return reply

        if entities["object_type"] == "person" or "midnight" in q:
            dets = self.repo.search_detections(
                object_type="person",
                location=entities["location"],
            )
            dets = self._filter_by_time_of_day(dets, entities["time_start"], entities["time_end"])
            if not dets:
                reply = "No person observations were found in the indexed records for that filter."
            else:
                lines = [
                    f"- **{d['frame_id']}** ({d['timestamp']} — {d['location']}): {d['frame_description']}"
                    for d in dets
                ]
                cited_frames = [d["frame_id"] for d in dets]
                reply = f"Found {len(dets)} person observation(s):\n" + "\n".join(lines)
            self._record_turn(question, reply, entities, cited_frames)
            return reply

        # 7. General time-window or location query
        if entities["time_start"] or entities["location"]:
            frames = ctx["matching_frames"]
            if not frames:
                reply = "No frames were found matching that time window or zone."
            else:
                lines = [
                    f"- **{f['frame_id']}** ({f['timestamp']} — {f['location']}): {f['description']}"
                    for f in frames
                ]
                cited_frames = [f["frame_id"] for f in frames]
                reply = f"Found {len(frames)} frame(s) in that window/zone:\n" + "\n".join(lines)
            self._record_turn(question, reply, entities, cited_frames)
            return reply

        # Fallback guidance
        reply = (
            "I can search indexed vehicle observations, person observations, time windows, "
            "alerts, telemetry, and daily summaries. Try: "
            "'How many vehicles were detected today?', 'Show all observations of blue vehicles', "
            "'Was anyone near the main gate at midnight?', or 'What happened between 12 PM and 3 PM?'"
        )
        self._record_turn(question, reply, entities, [])
        return reply

    def _record_turn(
        self,
        question: str,
        answer: str,
        entities: dict[str, Any],
        cited_frames: list[str],
    ) -> None:
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": answer})
        if entities.get("object_type"):
            self.state["last_object_type"] = entities["object_type"]
        if entities.get("color"):
            self.state["last_color"] = entities["color"]
        if entities.get("location"):
            self.state["last_location"] = entities["location"]
        if entities.get("time_start"):
            self.state["last_time_window"] = (entities["time_start"], entities["time_end"])
        if cited_frames:
            self.state["last_frame_ids"] = cited_frames
