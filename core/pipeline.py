"""End-to-end ingestion, correlation, and alerting pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from config import DEFAULT_FRAME_INTERVAL_SECONDS, LOG_DIR, MAX_VIDEO_FRAMES
from core.alert_engine import event_alerts, telemetry_alerts
from core.event_analyzer import classify_events, correlate_sequence_events
from core.frame_processor import FrameProcessor
from core.logger import get_logger
from core.telemetry import validate_telemetry

logger = get_logger("droneguard.pipeline", LOG_DIR)


class SecurityPipeline:
    """Coordinates frame processing, SQLite indexing, sequence correlation, and alerts."""

    def __init__(self, repository: Any, frame_processor: FrameProcessor | None = None):
        self.repo = repository
        self.processor = frame_processor or FrameProcessor()

    def ingest_telemetry(self, row: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
        validate_telemetry(row)
        tid = self.repo.add_telemetry(row)
        alerts = telemetry_alerts(row)
        for alert in alerts:
            self.repo.add_alert(alert, row["timestamp"])
        return tid, alerts

    def _persist_and_correlate(
        self, processed: dict[str, Any], telemetry_id: int | None = None
    ) -> dict[str, Any]:
        self.repo.add_frame(processed, telemetry_id)
        self.repo.add_model_run(
            frame_id=processed["frame_id"],
            provider=processed.get("model_provider", "unknown"),
            analysis_mode=processed.get("analysis_mode", "simulation"),
            status=processed.get("processing_status", "processed"),
            latency_ms=processed.get("processing_ms"),
            details=processed.get("error_message") or processed.get("activity"),
        )

        single_events = classify_events(processed)
        corr_events = correlate_sequence_events(processed, self.repo)
        all_events = single_events + corr_events
        created_alerts: list[dict[str, Any]] = []

        for event in all_events:
            event_id = self.repo.add_event(
                processed["frame_id"],
                event,
                processed["timestamp"],
                processed["location"],
            )
            for alert in event_alerts(processed, [event]):
                self.repo.add_alert(
                    alert,
                    processed["timestamp"],
                    event_id=event_id,
                    frame_id=processed["frame_id"],
                )
                created_alerts.append(alert)

        return {
            "frame": processed,
            "events": all_events,
            "alerts": created_alerts,
        }

    def ingest_description(
        self, item: dict[str, Any], telemetry_id: int | None = None
    ) -> dict[str, Any]:
        processed = self.processor.process_description(item)
        return self._persist_and_correlate(processed, telemetry_id)

    def ingest_image(
        self,
        image_path: str | Path,
        timestamp: str | None = None,
        location: str = "Perimeter",
        provider_name: str | None = None,
        description_hint: str | None = None,
        telemetry_id: int | None = None,
    ) -> dict[str, Any]:
        processed = self.processor.process_image(
            image_path=image_path,
            timestamp=timestamp,
            location=location,
            description_hint=description_hint,
            provider_name=provider_name,
        )
        return self._persist_and_correlate(processed, telemetry_id)

    def ingest_video(
        self,
        video_path: str | Path,
        interval_seconds: float = DEFAULT_FRAME_INTERVAL_SECONDS,
        max_frames: int = MAX_VIDEO_FRAMES,
        base_timestamp: str | None = None,
        location: str = "Perimeter",
        provider_name: str | None = None,
        source_video_name: str | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        extraction, frames = self.processor.process_video(
            video_path=video_path,
            interval_seconds=interval_seconds,
            max_frames=max_frames,
            base_timestamp=base_timestamp,
            location=location,
            provider_name=provider_name,
            source_video_name=source_video_name,
            progress_callback=progress_callback,
        )
        results = [self._persist_and_correlate(f) for f in frames]
        return {
            "extraction": extraction,
            "results": results,
        }
