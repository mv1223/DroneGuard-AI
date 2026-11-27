"""Single-frame event classification and cross-frame temporal correlation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from config import (
    LOITERING_MIN_OBSERVATIONS,
    LOITERING_SECONDS,
    NIGHT_END_HOUR,
    NIGHT_START_HOUR,
    RESTRICTED_ZONES,
)


def _is_night_hour(hour: int, start_hour: int, end_hour: int) -> bool:
    if start_hour <= end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def is_restricted_location(
    location: str | None, restricted_zones: list[str] | None = None
) -> bool:
    if not location:
        return False
    loc_lower = location.lower()
    zones = restricted_zones or RESTRICTED_ZONES
    if "restricted" in loc_lower:
        return True
    return any(z.lower() in loc_lower for z in zones)


def classify_events(
    frame: dict[str, Any],
    night_start: int = NIGHT_START_HOUR,
    night_end: int = NIGHT_END_HOUR,
    restricted_zones: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Classify security events for a single processed frame."""
    events: list[dict[str, Any]] = []
    ts = datetime.fromisoformat(frame["timestamp"])
    location = frame.get("location", "Unknown")
    detections = frame.get("detections") or []
    is_night = _is_night_hour(ts.hour, night_start, night_end)
    restricted_loc = is_restricted_location(location, restricted_zones)

    has_person = False
    has_restricted_activity = False

    for det in detections:
        obj = str(det.get("object_type", "")).lower()
        color = det.get("color")
        if obj in ("truck", "vehicle", "car", "van", "suv"):
            label = f"{color} {obj}".strip() if color else f"Unspecified {obj}"
            events.append(
                {
                    "event_type": "vehicle_observation",
                    "severity": "medium" if is_night else "low",
                    "explanation": f"{label.capitalize()} observed at {location}",
                    "metadata": {"object_type": obj, "color": color, "frame_id": frame.get("frame_id")},
                }
            )
        elif obj == "person":
            has_person = True
            events.append(
                {
                    "event_type": "person_detected",
                    "severity": "low",
                    "explanation": f"Person observed in monitored area ({location})",
                    "metadata": {"object_type": "person", "frame_id": frame.get("frame_id")},
                }
            )
        elif obj == "activity":
            has_restricted_activity = True

    if has_restricted_activity or (restricted_loc and detections):
        sev = "critical" if (is_night and has_person) else "high"
        events.append(
            {
                "event_type": "restricted_area_presence",
                "severity": sev,
                "explanation": (
                    f"Unauthorized presence indicated in restricted zone ({location})"
                    + (" during night hours" if is_night else "")
                ),
                "metadata": {"location": location, "night": is_night, "frame_id": frame.get("frame_id")},
            }
        )

    if is_night and has_person:
        sev = "critical" if restricted_loc else "high"
        events.append(
            {
                "event_type": "midnight_person_presence",
                "severity": sev,
                "explanation": f"Person observed during configured night window ({night_start:02d}:00-{night_end:02d}:00)",
                "metadata": {"location": location, "hour": ts.hour, "frame_id": frame.get("frame_id")},
            }
        )

    return events


def correlate_sequence_events(
    frame: dict[str, Any],
    repository: Any,
    loitering_seconds: int = LOITERING_SECONDS,
    loitering_min_observations: int = LOITERING_MIN_OBSERVATIONS,
) -> list[dict[str, Any]]:
    """Correlate a newly processed frame against historical indexed frames.

    Detects:
    - Repeated vehicle attribute observations across timestamps/locations.
    - Vehicle entry/exit movement patterns across zones.
    - Potential loitering when person observations persist in one zone over time.
    """
    correlated: list[dict[str, Any]] = []
    cur_fid = frame["frame_id"]
    cur_loc = frame.get("location", "Unknown")
    try:
        cur_dt = datetime.fromisoformat(frame["timestamp"])
    except ValueError:
        return correlated

    detections = frame.get("detections") or []

    # 1. Repeated vehicle observations & entry/exit patterns
    for det in detections:
        obj = str(det.get("object_type", "")).lower()
        if obj not in ("truck", "vehicle", "car", "van", "suv"):
            continue
        color = det.get("color")
        prior_vehicles = repository.search_detections(
            object_type="vehicle",
            color=color,
        )
        prior_matches = [
            p for p in prior_vehicles
            if p["frame_id"] != cur_fid and p["timestamp"] <= frame["timestamp"]
        ]
        if prior_matches:
            # Avoid duplicate correlation if a repeated_vehicle_observation was already logged for cur_fid
            related_ids = sorted({p["frame_id"] for p in prior_matches} | {cur_fid})
            locations = sorted({p["location"] for p in prior_matches if p.get("location")} | {cur_loc})
            first_seen = prior_matches[0]["timestamp"]
            color_label = f"{color} " if color else ""
            correlated.append(
                {
                    "event_type": "repeated_vehicle_observation",
                    "severity": "medium",
                    "explanation": (
                        f"Repeated {color_label}{obj} observation across {len(related_ids)} frame(s) "
                        f"({first_seen} to {frame['timestamp']}) at {', '.join(locations)}. "
                        "Note: Matched by visual attributes (category/color); persistent vehicle re-ID is not performed."
                    ),
                    "metadata": {
                        "related_frame_ids": related_ids,
                        "color": color,
                        "locations": locations,
                        "first_seen": first_seen,
                    },
                }
            )
            # Entry / exit pattern check (gate/entry vs interior zone or return to gate)
            gate_seen = any("gate" in loc.lower() or "entry" in loc.lower() for loc in locations)
            interior_seen = any(
                any(k in loc.lower() for k in ("garage", "parking", "dock", "yard"))
                for loc in locations
            )
            if gate_seen and (interior_seen or len(prior_matches) >= 1 and "gate" in cur_loc.lower()):
                correlated.append(
                    {
                        "event_type": "vehicle_entry_exit_pattern",
                        "severity": "low",
                        "explanation": (
                            f"{color_label.capitalize()}{obj} movement correlated across perimeter zones "
                            f"({', '.join(locations)}) between {first_seen} and {frame['timestamp']}."
                        ),
                        "metadata": {"related_frame_ids": related_ids, "locations": locations},
                    }
                )

    # 2. Loitering detection across consecutive/windowed person observations in same zone
    if any(str(d.get("object_type", "")).lower() == "person" for d in detections):
        prior_people = repository.search_detections(object_type="person", location=cur_loc)
        window_hits: list[tuple[datetime, str]] = []
        for p in prior_people:
            if p["frame_id"] == cur_fid:
                continue
            try:
                p_dt = datetime.fromisoformat(p["timestamp"])
            except ValueError:
                continue
            delta = (cur_dt - p_dt).total_seconds()
            if 0 <= delta <= max(loitering_seconds * 10, 1800):
                window_hits.append((p_dt, p["frame_id"]))

        window_hits.append((cur_dt, cur_fid))
        window_hits.sort(key=lambda x: x[0])
        if len(window_hits) >= loitering_min_observations:
            span_seconds = (window_hits[-1][0] - window_hits[0][0]).total_seconds()
            if span_seconds >= loitering_seconds:
                frame_ids = [fid for _, fid in window_hits]
                is_night = _is_night_hour(cur_dt.hour, NIGHT_START_HOUR, NIGHT_END_HOUR)
                restricted_loc = is_restricted_location(cur_loc)
                sev = "critical" if (is_night or restricted_loc) else "high"
                correlated.append(
                    {
                        "event_type": "loitering_suspected",
                        "severity": sev,
                        "explanation": (
                            f"Potential loitering at {cur_loc}: {len(frame_ids)} person observations "
                            f"spanning {int(span_seconds)}s (threshold {loitering_seconds}s). "
                            "Note: Inferred from zone-level detections over time without persistent person re-ID."
                        ),
                        "metadata": {
                            "related_frame_ids": frame_ids,
                            "duration_seconds": round(span_seconds, 1),
                            "location": cur_loc,
                        },
                    }
                )

    return correlated
