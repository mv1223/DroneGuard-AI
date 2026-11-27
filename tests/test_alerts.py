from core.alert_engine import event_alerts, telemetry_alerts
from core.pipeline import SecurityPipeline
from database.repository import Repository


def test_low_and_critical_battery_and_altitude_alerts():
    low = {"drone_id": "D1", "location_name": "Gate", "battery_percentage": 18, "altitude": 20}
    crit = {"drone_id": "D1", "location_name": "Gate", "battery_percentage": 10, "altitude": 95}

    assert telemetry_alerts(low)[0]["alert_type"] == "low_battery"
    assert telemetry_alerts(low)[0]["severity"] == "medium"

    crit_alerts = telemetry_alerts(crit)
    assert any(a["alert_type"] == "critical_battery" and a["severity"] == "critical" for a in crit_alerts)
    assert any(a["alert_type"] == "altitude_violation" and a["severity"] == "critical" for a in crit_alerts)


def test_midnight_and_restricted_zone_alerts():
    frame = {"frame_id": "FR-1", "timestamp": "2026-11-27T00:01:00", "location": "Main Gate"}
    event = {"event_type": "midnight_person_presence", "severity": "high", "explanation": "Person at night"}
    assert event_alerts(frame, [event])[0]["severity"] == "high"


def test_repeated_vehicle_and_loitering_correlation(tmp_path):
    repo = Repository(tmp_path / "corr.db")
    pipe = SecurityPipeline(repo)

    pipe.ingest_description(
        {
            "frame_id": "FR-1",
            "timestamp": "2026-11-27T12:00:00",
            "location": "Main Gate",
            "description": "A blue pickup truck enters through the main gate.",
        }
    )
    r2 = pipe.ingest_description(
        {
            "frame_id": "FR-2",
            "timestamp": "2026-11-27T15:30:00",
            "location": "Garage",
            "description": "A blue pickup truck observed again near the garage.",
        }
    )
    assert any(e["event_type"] == "repeated_vehicle_observation" for e in r2["events"])
    assert any(e["event_type"] == "vehicle_entry_exit_pattern" for e in r2["events"])

    # Loitering across 3 minutes at Main Gate
    pipe.ingest_description(
        {
            "frame_id": "FR-3",
            "timestamp": "2026-11-27T00:01:00",
            "location": "Main Gate",
            "description": "A person standing near the main gate.",
        }
    )
    r4 = pipe.ingest_description(
        {
            "frame_id": "FR-4",
            "timestamp": "2026-11-27T00:04:00",
            "location": "Main Gate",
            "description": "A person remains near the main gate.",
        }
    )
    assert any(e["event_type"] == "loitering_suspected" for e in r4["events"])


def test_duplicate_alert_suppression_and_status_updates(tmp_path):
    repo = Repository(tmp_path / "dedup.db")
    alert = {
        "alert_type": "midnight_person_presence",
        "severity": "high",
        "location": "Main Gate",
        "message": "Person observed during configured night window at Main Gate, 2026-11-27T00:01:00",
    }
    id1 = repo.add_alert(alert, "2026-11-27T00:01:00", dedup_window_seconds=300)
    id2 = repo.add_alert(
        {**alert, "message": "Person observed during configured night window at Main Gate, 2026-11-27T00:02:00"},
        "2026-11-27T00:02:00",
        dedup_window_seconds=300,
    )
    assert id1 == id2
    alerts = repo.list_alerts()
    assert len(alerts) == 1
    assert alerts[0]["occurrence_count"] == 2

    repo.update_alert_status(id1, "resolved")
    assert repo.list_alerts()[0]["status"] == "resolved"
