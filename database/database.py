"""SQLite schema, safe column migrations, and connection management."""

from __future__ import annotations

from contextlib import contextmanager
import sqlite3
from pathlib import Path
from typing import Iterator

from config import DB_PATH

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    drone_id TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    altitude REAL,
    battery_percentage REAL,
    speed REAL,
    location_name TEXT,
    flight_status TEXT
);

CREATE TABLE IF NOT EXISTS frames (
    frame_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    description TEXT NOT NULL,
    image_path TEXT,
    location TEXT,
    source_type TEXT,
    source_video TEXT,
    processing_status TEXT,
    model_provider TEXT,
    analysis_mode TEXT,
    activity TEXT,
    evidence TEXT,
    confidence REAL,
    processing_ms REAL,
    error_message TEXT,
    telemetry_id INTEGER,
    FOREIGN KEY(telemetry_id) REFERENCES telemetry(id)
);

CREATE TABLE IF NOT EXISTS detections (
    detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    frame_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    description TEXT,
    color TEXT,
    confidence REAL,
    attributes_json TEXT,
    observation_group_id TEXT,
    FOREIGN KEY(frame_id) REFERENCES frames(frame_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    frame_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    location TEXT,
    explanation TEXT,
    metadata_json TEXT,
    FOREIGN KEY(frame_id) REFERENCES frames(frame_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER,
    frame_id TEXT,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    recommended_action TEXT,
    timestamp TEXT NOT NULL,
    last_seen_timestamp TEXT,
    occurrence_count INTEGER DEFAULT 1,
    status TEXT DEFAULT 'open',
    acknowledged INTEGER DEFAULT 0,
    FOREIGN KEY(event_id) REFERENCES events(event_id)
);

CREATE TABLE IF NOT EXISTS model_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    frame_id TEXT,
    provider TEXT,
    analysis_mode TEXT,
    status TEXT,
    latency_ms REAL,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry(timestamp);
CREATE INDEX IF NOT EXISTS idx_telemetry_drone ON telemetry(drone_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_frames_timestamp ON frames(timestamp);
CREATE INDEX IF NOT EXISTS idx_frames_location ON frames(location);
CREATE INDEX IF NOT EXISTS idx_frames_source_video ON frames(source_video);
CREATE INDEX IF NOT EXISTS idx_frames_mode ON frames(analysis_mode);
CREATE INDEX IF NOT EXISTS idx_detections_object ON detections(object_type);
CREATE INDEX IF NOT EXISTS idx_detections_color ON detections(color);
CREATE INDEX IF NOT EXISTS idx_detections_frame ON detections(frame_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);
CREATE INDEX IF NOT EXISTS idx_events_frame ON events(frame_id);
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_severity_status ON alerts(severity, status);
"""

MIGRATIONS: dict[str, list[tuple[str, str]]] = {
    "frames": [
        ("source_video", "TEXT"),
        ("analysis_mode", "TEXT"),
        ("activity", "TEXT"),
        ("evidence", "TEXT"),
        ("confidence", "REAL"),
        ("processing_ms", "REAL"),
        ("error_message", "TEXT"),
    ],
    "detections": [
        ("description", "TEXT"),
    ],
    "events": [
        ("metadata_json", "TEXT"),
    ],
    "alerts": [
        ("frame_id", "TEXT"),
        ("last_seen_timestamp", "TEXT"),
        ("occurrence_count", "INTEGER DEFAULT 1"),
        ("status", "TEXT DEFAULT 'open'"),
    ],
    "model_runs": [
        ("analysis_mode", "TEXT"),
        ("latency_ms", "REAL"),
    ],
}


@contextmanager
def connect(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for table, cols in MIGRATIONS.items():
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for col_name, col_type in cols:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")


def initialize_database(db_path: str | Path | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        _apply_migrations(conn)
        conn.executescript(INDEXES)
