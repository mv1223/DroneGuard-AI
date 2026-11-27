"""SQLite repository layer with indexed multi-facet search and alert deduplication."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from config import DUPLICATE_ALERT_WINDOW_SECONDS
from .database import connect, initialize_database

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class Repository:
    def __init__(self, db_path=None):
        self.db_path = db_path
        initialize_database(db_path)

    def add_telemetry(self, row: dict[str, Any]) -> int:
        fields = (
            "timestamp",
            "drone_id",
            "latitude",
            "longitude",
            "altitude",
            "battery_percentage",
            "speed",
            "location_name",
            "flight_status",
        )
        with connect(self.db_path) as c:
            cur = c.execute(
                f"INSERT INTO telemetry ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                tuple(row.get(k) for k in fields),
            )
            return int(cur.lastrowid)

    def list_telemetry(self, limit: int = 200, drone_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM telemetry WHERE 1=1"
        args: list[Any] = []
        if drone_id:
            sql += " AND drone_id = ?"
            args.append(drone_id)
        sql += " ORDER BY timestamp ASC LIMIT ?"
        args.append(limit)
        with connect(self.db_path) as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]

    def get_latest_telemetry(self, drone_id: str | None = None) -> dict[str, Any] | None:
        sql = "SELECT * FROM telemetry WHERE 1=1"
        args: list[Any] = []
        if drone_id:
            sql += " AND drone_id = ?"
            args.append(drone_id)
        sql += " ORDER BY timestamp DESC, id DESC LIMIT 1"
        with connect(self.db_path) as c:
            row = c.execute(sql, args).fetchone()
            return dict(row) if row else None

    def add_frame(self, frame: dict[str, Any], telemetry_id: int | None = None) -> None:
        with connect(self.db_path) as c:
            self._insert_frame_in_conn(c, frame, telemetry_id)

    def add_frames_batch(self, frames: list[dict[str, Any]]) -> int:
        """Persist a batch of frames and their detections in a single transaction."""
        with connect(self.db_path) as c:
            for frame in frames:
                self._insert_frame_in_conn(c, frame, frame.get("telemetry_id"))
        return len(frames)

    @staticmethod
    def _insert_frame_in_conn(c, frame: dict[str, Any], telemetry_id: int | None) -> None:
        c.execute("DELETE FROM detections WHERE frame_id = ?", (frame["frame_id"],))
        c.execute(
            """INSERT OR REPLACE INTO frames
            (frame_id, timestamp, description, image_path, location, source_type,
             source_video, processing_status, model_provider, analysis_mode,
             activity, evidence, confidence, processing_ms, error_message, telemetry_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                frame["frame_id"],
                frame["timestamp"],
                frame["description"],
                frame.get("image_path"),
                frame.get("location", "Unknown"),
                frame.get("source_type", "simulation"),
                frame.get("source_video"),
                frame.get("processing_status", "processed"),
                frame.get("model_provider", "unknown"),
                frame.get("analysis_mode", "simulation"),
                frame.get("activity"),
                frame.get("evidence"),
                frame.get("confidence"),
                frame.get("processing_ms"),
                frame.get("error_message"),
                telemetry_id,
            ),
        )
        dets = frame.get("detections") or []
        if dets:
            c.executemany(
                """INSERT INTO detections
                (frame_id, object_type, description, color, confidence, attributes_json, observation_group_id)
                VALUES (?,?,?,?,?,?,?)""",
                [
                    (
                        frame["frame_id"],
                        d["object_type"],
                        d.get("description") or d.get("attributes", {}).get("description"),
                        d.get("color"),
                        d.get("confidence"),
                        json.dumps(d.get("attributes", {})),
                        d.get("observation_group_id"),
                    )
                    for d in dets
                ],
            )

    def add_event(
        self,
        frame_id: str,
        event: dict[str, Any],
        timestamp: str,
        location: str,
    ) -> int:
        metadata_json = (
            json.dumps(event["metadata"]) if event.get("metadata") is not None else None
        )
        with connect(self.db_path) as c:
            cur = c.execute(
                """INSERT INTO events(frame_id, event_type, severity, timestamp, location, explanation, metadata_json)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    frame_id,
                    event["event_type"],
                    event["severity"],
                    timestamp,
                    location,
                    event["explanation"],
                    metadata_json,
                ),
            )
            return int(cur.lastrowid)

    def add_alert(
        self,
        alert: dict[str, Any],
        timestamp: str,
        event_id: int | None = None,
        frame_id: str | None = None,
        dedup_window_seconds: int = DUPLICATE_ALERT_WINDOW_SECONDS,
    ) -> int | None:
        """Insert an alert or merge into an active alert within the dedup window."""
        alert_type = alert["alert_type"]
        message = alert["message"]
        with connect(self.db_path) as c:
            # 1. Exact duplicate guard
            exact = c.execute(
                "SELECT alert_id FROM alerts WHERE alert_type=? AND timestamp=? AND message=?",
                (alert_type, timestamp, message),
            ).fetchone()
            if exact:
                return int(exact["alert_id"])

            # 2. Time-windowed duplicate suppression for un-resolved alerts of same type
            if dedup_window_seconds > 0:
                candidates = c.execute(
                    """SELECT alert_id, timestamp, last_seen_timestamp, message, occurrence_count
                       FROM alerts
                       WHERE alert_type = ? AND status != 'resolved'
                       ORDER BY alert_id DESC LIMIT 10""",
                    (alert_type,),
                ).fetchall()
                try:
                    cur_dt = datetime.fromisoformat(timestamp)
                except ValueError:
                    cur_dt = None
                for cand in candidates:
                    ref_ts = cand["last_seen_timestamp"] or cand["timestamp"]
                    try:
                        ref_dt = datetime.fromisoformat(ref_ts)
                    except ValueError:
                        continue
                    if cur_dt and abs((cur_dt - ref_dt).total_seconds()) <= dedup_window_seconds:
                        # Suppress only if location/context matches or alert_type is telemetry-level
                        same_target = (
                            alert_type in ("low_battery", "critical_battery", "altitude_violation")
                            or (alert.get("location") and alert["location"].lower() in cand["message"].lower())
                            or cand["message"].split(" at ")[0] == message.split(" at ")[0]
                        )
                        if same_target:
                            c.execute(
                                """UPDATE alerts
                                   SET occurrence_count = COALESCE(occurrence_count, 1) + 1,
                                       last_seen_timestamp = ?
                                   WHERE alert_id = ?""",
                                (timestamp, cand["alert_id"]),
                            )
                            return int(cand["alert_id"])

            cur = c.execute(
                """INSERT INTO alerts
                (event_id, frame_id, alert_type, severity, message, recommended_action,
                 timestamp, last_seen_timestamp, occurrence_count, status, acknowledged)
                VALUES (?,?,?,?,?,?,?,?,1,'open',0)""",
                (
                    event_id,
                    frame_id or alert.get("frame_id"),
                    alert_type,
                    alert["severity"],
                    message,
                    alert.get("recommended_action", "Review the event."),
                    timestamp,
                    timestamp,
                ),
            )
            return int(cur.lastrowid)

    def add_model_run(
        self,
        frame_id: str | None,
        provider: str,
        analysis_mode: str,
        status: str,
        latency_ms: float | None = None,
        details: str | None = None,
    ) -> int:
        with connect(self.db_path) as c:
            cur = c.execute(
                """INSERT INTO model_runs(frame_id, provider, analysis_mode, status, latency_ms, details)
                   VALUES (?,?,?,?,?,?)""",
                (frame_id, provider, analysis_mode, status, latency_ms, details),
            )
            return int(cur.lastrowid)

    def list_model_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with connect(self.db_path) as c:
            return [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM model_runs ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            ]

    def search_frames(
        self,
        query: str | None = None,
        start: str | None = None,
        end: str | None = None,
        location: str | None = None,
        object_type: str | None = None,
        object_description: str | None = None,
        color: str | None = None,
        event_type: str | None = None,
        source_video: str | None = None,
        analysis_mode: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT f.* FROM frames f WHERE 1=1"
        args: list[Any] = []
        if query:
            sql += " AND (f.description LIKE ? OR COALESCE(f.evidence,'') LIKE ?)"
            args.extend([f"%{query}%", f"%{query}%"])
        if start:
            sql += " AND f.timestamp >= ?"
            args.append(start)
        if end:
            sql += " AND f.timestamp <= ?"
            args.append(end)
        if location:
            sql += " AND f.location LIKE ?"
            args.append(f"%{location}%")
        if source_video:
            sql += " AND f.source_video LIKE ?"
            args.append(f"%{source_video}%")
        if analysis_mode:
            sql += " AND f.analysis_mode = ?"
            args.append(analysis_mode)
        if object_type or object_description or color:
            det_conds = ["d.frame_id = f.frame_id"]
            if object_type:
                if object_type == "vehicle":
                    det_conds.append("d.object_type IN ('truck', 'vehicle', 'car', 'van', 'suv')")
                else:
                    det_conds.append("d.object_type = ?")
                    args.append(object_type)
            if object_description:
                det_conds.append("(COALESCE(d.description,'') LIKE ? OR COALESCE(d.attributes_json,'') LIKE ?)")
                args.extend([f"%{object_description}%", f"%{object_description}%"])
            if color:
                det_conds.append("LOWER(COALESCE(d.color,'')) = LOWER(?)")
                args.append(color)
            sql += f" AND EXISTS (SELECT 1 FROM detections d WHERE {' AND '.join(det_conds)})"
        if event_type:
            sql += " AND EXISTS (SELECT 1 FROM events e WHERE e.frame_id = f.frame_id AND e.event_type = ?)"
            args.append(event_type)

        sql += " ORDER BY f.timestamp ASC"
        if limit is not None:
            sql += " LIMIT ?"
            args.append(limit)
        with connect(self.db_path) as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]

    def get_frame_details(self, frame_id: str) -> dict[str, Any] | None:
        with connect(self.db_path) as c:
            frame = c.execute("SELECT * FROM frames WHERE frame_id = ?", (frame_id,)).fetchone()
            if not frame:
                return None
            dets = [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM detections WHERE frame_id = ?", (frame_id,)
                ).fetchall()
            ]
            evts = [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM events WHERE frame_id = ?", (frame_id,)
                ).fetchall()
            ]
            res = dict(frame)
            res["detections"] = dets
            res["events"] = evts
            return res

    def get_detections_for_frames(self, frame_ids: list[str] | None = None) -> list[dict[str, Any]]:
        with connect(self.db_path) as c:
            if frame_ids is None:
                return [dict(r) for r in c.execute("SELECT * FROM detections").fetchall()]
            if not frame_ids:
                return []
            placeholders = ",".join("?" for _ in frame_ids)
            return [
                dict(r)
                for r in c.execute(
                    f"SELECT * FROM detections WHERE frame_id IN ({placeholders})",
                    tuple(frame_ids),
                ).fetchall()
            ]

    def search_detections(
        self,
        object_type: str | None = None,
        color: str | None = None,
        location: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = """SELECT d.*, f.timestamp, f.location, f.description AS frame_description, f.image_path, f.source_video
                 FROM detections d JOIN frames f ON d.frame_id = f.frame_id WHERE 1=1"""
        args: list[Any] = []
        if object_type:
            if object_type == "vehicle":
                sql += " AND d.object_type IN ('truck', 'vehicle', 'car', 'van', 'suv')"
            else:
                sql += " AND d.object_type = ?"
                args.append(object_type)
        if color:
            sql += " AND LOWER(COALESCE(d.color,'')) = LOWER(?)"
            args.append(color)
        if location:
            sql += " AND f.location LIKE ?"
            args.append(f"%{location}%")
        if start:
            sql += " AND f.timestamp >= ?"
            args.append(start)
        if end:
            sql += " AND f.timestamp <= ?"
            args.append(end)
        sql += " ORDER BY f.timestamp ASC"
        with connect(self.db_path) as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]

    def search_events(
        self,
        object_type: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
        start: str | None = None,
        end: str | None = None,
        location: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = """SELECT e.*, f.image_path, f.source_video, f.analysis_mode
                 FROM events e JOIN frames f ON e.frame_id = f.frame_id WHERE 1=1"""
        args: list[Any] = []
        if object_type:
            if object_type == "vehicle":
                sql += """ AND EXISTS (SELECT 1 FROM detections d WHERE d.frame_id = e.frame_id
                           AND d.object_type IN ('truck', 'vehicle', 'car', 'van', 'suv'))"""
            else:
                sql += """ AND EXISTS (SELECT 1 FROM detections d WHERE d.frame_id = e.frame_id
                           AND d.object_type = ?)"""
                args.append(object_type)
        if event_type:
            sql += " AND e.event_type = ?"
            args.append(event_type)
        if severity:
            sql += " AND LOWER(e.severity) = LOWER(?)"
            args.append(severity)
        if start:
            sql += " AND e.timestamp >= ?"
            args.append(start)
        if end:
            sql += " AND e.timestamp <= ?"
            args.append(end)
        if location:
            sql += " AND e.location LIKE ?"
            args.append(f"%{location}%")
        sql += " ORDER BY e.timestamp ASC"
        with connect(self.db_path) as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]

    def list_alerts(
        self,
        start: str | None = None,
        end: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        unacknowledged_only: bool = False,
        prioritize: bool = True,
    ) -> list[dict[str, Any]]:
        sql = """SELECT a.*, e.frame_id AS event_frame_id
                 FROM alerts a LEFT JOIN events e ON a.event_id = e.event_id WHERE 1=1"""
        args: list[Any] = []
        if start:
            sql += " AND a.timestamp >= ?"
            args.append(start)
        if end:
            sql += " AND a.timestamp <= ?"
            args.append(end)
        if severity:
            sql += " AND LOWER(a.severity) = LOWER(?)"
            args.append(severity)
        if status:
            sql += " AND LOWER(COALESCE(a.status,'open')) = LOWER(?)"
            args.append(status)
        if unacknowledged_only:
            sql += " AND a.acknowledged = 0"
        sql += " ORDER BY a.timestamp DESC, a.alert_id DESC"
        with connect(self.db_path) as c:
            rows = [dict(r) for r in c.execute(sql, args).fetchall()]
        for r in rows:
            if not r.get("frame_id") and r.get("event_frame_id"):
                r["frame_id"] = r["event_frame_id"]
        if prioritize:
            rows.sort(
                key=lambda r: (
                    1 if r.get("status") == "resolved" else 0,
                    SEVERITY_ORDER.get(str(r.get("severity", "low")).lower(), 9),
                    r.get("timestamp", ""),
                )
            )
        return rows

    def list_source_videos(self) -> list[str]:
        with connect(self.db_path) as c:
            rows = c.execute(
                "SELECT DISTINCT source_video FROM frames WHERE source_video IS NOT NULL ORDER BY source_video"
            ).fetchall()
            return [r["source_video"] for r in rows]

    def counts(self) -> dict[str, int]:
        with connect(self.db_path) as c:
            return {
                "frames": c.execute("SELECT COUNT(*) FROM frames").fetchone()[0],
                "detections": c.execute("SELECT COUNT(*) FROM detections").fetchone()[0],
                "events": c.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                "alerts": c.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
                "active_alerts": c.execute(
                    "SELECT COUNT(*) FROM alerts WHERE COALESCE(status,'open') != 'resolved' AND acknowledged = 0"
                ).fetchone()[0],
                "critical_alerts": c.execute(
                    "SELECT COUNT(*) FROM alerts WHERE LOWER(severity) = 'critical' AND COALESCE(status,'open') != 'resolved'"
                ).fetchone()[0],
            }

    def acknowledge_alert(self, alert_id: int) -> None:
        with connect(self.db_path) as c:
            c.execute(
                "UPDATE alerts SET acknowledged = 1, status = CASE WHEN status='open' THEN 'acknowledged' ELSE status END WHERE alert_id = ?",
                (alert_id,),
            )

    def update_alert_status(self, alert_id: int, status: str) -> None:
        normalized = status.strip().lower()
        if normalized not in ("open", "acknowledged", "resolved"):
            raise ValueError(f"Unsupported alert status: {status}")
        ack = 1 if normalized in ("acknowledged", "resolved") else 0
        with connect(self.db_path) as c:
            c.execute(
                "UPDATE alerts SET status = ?, acknowledged = ? WHERE alert_id = ?",
                (normalized, ack, alert_id),
            )

    def clear_all(self) -> None:
        with connect(self.db_path) as c:
            for table in ("alerts", "events", "detections", "frames", "telemetry", "model_runs"):
                c.execute(f"DELETE FROM {table}")
