"""Configurable security and drone-safety alert generation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from config import (
    CRITICAL_BATTERY_THRESHOLD,
    LOW_BATTERY_THRESHOLD,
    MAX_ALTITUDE_METERS,
    NIGHT_END_HOUR,
    NIGHT_START_HOUR,
)


def telemetry_alerts(
    record: dict[str, Any],
    low_battery: float = LOW_BATTERY_THRESHOLD,
    critical_battery: float = CRITICAL_BATTERY_THRESHOLD,
    max_altitude: float = MAX_ALTITUDE_METERS,
) -> list[dict[str, Any]]:
    """Evaluate drone telemetry against battery and altitude safety thresholds."""
    alerts: list[dict[str, Any]] = []
    battery = float(record["battery_percentage"])
    altitude = float(record["altitude"])
    drone_id = record.get("drone_id", "DRONE-001")
    location = record.get("location_name", "Unknown")

    if battery < critical_battery:
        alerts.append(
            {
                "alert_type": "critical_battery",
                "severity": "critical",
                "location": location,
                "message": (
                    f"{drone_id} battery critically low at {battery}% "
                    f"(below critical {critical_battery}%) near {location}"
                ),
                "recommended_action": "Initiate immediate automated Return-to-Home (RTH) and emergency dock landing.",
            }
        )
    elif battery < low_battery:
        alerts.append(
            {
                "alert_type": "low_battery",
                "severity": "medium",
                "location": location,
                "message": f"Drone battery is {battery}% (below {low_battery}%) near {location}",
                "recommended_action": "Return the drone to dock and inspect battery health.",
            }
        )

    if altitude > max_altitude:
        severity = "critical" if altitude > max_altitude * 1.5 else "high"
        alerts.append(
            {
                "alert_type": "altitude_violation",
                "severity": severity,
                "location": location,
                "message": (
                    f"Drone altitude {altitude}m exceeds configured limit "
                    f"({max_altitude}m) over {location}"
                ),
                "recommended_action": "Reduce altitude immediately and verify airspace/geofence configuration.",
            }
        )
    return alerts


def event_alerts(frame: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert classified and correlated security events into prioritized alerts."""
    alerts: list[dict[str, Any]] = []
    location = frame.get("location", "Unknown")
    ts = frame.get("timestamp", "")
    frame_id = frame.get("frame_id")

    for event in events:
        etype = event["event_type"]
        if etype in ("midnight_person_presence", "restricted_area_presence", "loitering_suspected"):
            severity = event.get("severity", "high")
            action = (
                "Dispatch security guard / trigger dock spotlight and verify frame evidence immediately."
                if severity == "critical"
                else "Review the associated frame evidence and verify whether escalation is required."
            )
            alerts.append(
                {
                    "alert_type": etype,
                    "severity": severity,
                    "frame_id": frame_id,
                    "location": location,
                    "message": f"{event['explanation']} at {location}, {ts}",
                    "recommended_action": action,
                }
            )
        elif etype == "repeated_vehicle_observation":
            alerts.append(
                {
                    "alert_type": etype,
                    "severity": "medium",
                    "frame_id": frame_id,
                    "location": location,
                    "message": f"{event['explanation']} (trigger frame {frame_id})",
                    "recommended_action": "Compare referenced frames to confirm whether the vehicle is authorized.",
                }
            )
    return alerts


def is_night(
    timestamp: str,
    start_hour: int = NIGHT_START_HOUR,
    end_hour: int = NIGHT_END_HOUR,
) -> bool:
    hour = datetime.fromisoformat(timestamp).hour
    if start_hour <= end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour
