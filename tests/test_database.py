import sqlite3
from database.repository import Repository


def test_frame_persistence_and_multi_facet_search(tmp_path):
    repo = Repository(tmp_path / "test.db")
    repo.add_frame(
        {
            "frame_id": "FR-X",
            "timestamp": "2026-11-27T12:00:00",
            "description": "Blue truck at gate",
            "location": "Main Gate",
            "source_video": "patrol1.mp4",
            "analysis_mode": "actual_vlm",
            "detections": [
                {"object_type": "truck", "color": "blue", "confidence": 0.9, "description": "Blue pickup truck"}
            ],
        }
    )
    repo.add_frame(
        {
            "frame_id": "FR-Z",
            "timestamp": "2026-11-27T16:00:00",
            "description": "Red car at garage",
            "location": "Garage",
            "source_video": "patrol2.mp4",
            "analysis_mode": "simulation",
            "detections": [
                {"object_type": "vehicle", "color": "red", "confidence": 0.85, "description": "Red sedan"}
            ],
        }
    )

    assert len(repo.search_frames(query="truck")) == 1
    assert len(repo.search_frames(object_type="vehicle", color="blue")) == 1
    assert len(repo.search_frames(object_description="sedan")) == 1
    assert len(repo.search_frames(source_video="patrol1.mp4")) == 1
    assert len(repo.search_frames(start="2026-11-27T11:00:00", end="2026-11-27T13:00:00")) == 1
    assert repo.counts()["frames"] == 2


def test_event_search_and_indexes_exist(tmp_path):
    db_file = tmp_path / "idx.db"
    repo = Repository(db_file)
    frame = {
        "frame_id": "FR-Y",
        "timestamp": "2026-11-27T00:01:00",
        "description": "Person at gate",
        "location": "Main Gate",
        "detections": [{"object_type": "person", "confidence": 0.9}],
    }
    repo.add_frame(frame)
    repo.add_event(
        "FR-Y",
        {"event_type": "person_detected", "severity": "low", "explanation": "Person observed"},
        frame["timestamp"],
        frame["location"],
    )
    assert len(repo.search_events(object_type="person")) == 1

    with sqlite3.connect(db_file) as conn:
        indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
    assert {"idx_frames_timestamp", "idx_frames_location", "idx_detections_object", "idx_events_timestamp"} <= indexes
