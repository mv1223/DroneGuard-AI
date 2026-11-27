# Database Design

## Tables
- `telemetry`: Timestamped drone state (`drone_id`, `latitude`, `longitude`, `altitude`, `battery_percentage`, `speed`, `location_name`, `flight_status`).
- `frames`: One row per indexed frame (`frame_id` PK, `timestamp`, `description`, `image_path`, `location`, `source_type`, `source_video`, `processing_status`, `model_provider`, `analysis_mode`, `activity`, `evidence`, `confidence`, `processing_ms`, `error_message`, `telemetry_id` FK).
- `detections`: Zero or more structured object detections per frame (`detection_id` PK, `frame_id` FK ON DELETE CASCADE, `object_type`, `description`, `color`, `confidence`, `attributes_json`, `observation_group_id`).
- `events`: Classified single-frame and cross-frame correlated events (`event_id` PK, `frame_id` FK ON DELETE CASCADE, `event_type`, `severity`, `timestamp`, `location`, `explanation`, `metadata_json`).
- `alerts`: Prioritized alerts with deduplication metadata (`alert_id` PK, `event_id` FK, `frame_id`, `alert_type`, `severity`, `message`, `recommended_action`, `timestamp`, `last_seen_timestamp`, `occurrence_count`, `status`, `acknowledged`).
- `model_runs`: Provider audit trail (`id` PK, `frame_id`, `provider`, `analysis_mode`, `status`, `latency_ms`, `details`, `created_at`).

## Indexing & Query Strategy
- SQLite runs in `WAL` mode with `PRAGMA foreign_keys = ON` and deterministic connection cleanup.
- 14 indexes accelerate range and join queries across `frames(timestamp, location, source_video, analysis_mode)`, `detections(object_type, color, frame_id)`, `events(timestamp, event_type, severity, frame_id)`, `alerts(timestamp, severity, status)`, and `telemetry(timestamp, drone_id)`.
- All repository methods use bound SQL parameters to prevent injection.
