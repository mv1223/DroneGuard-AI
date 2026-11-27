"""Frame normalization and multi-modal image/video processing pipeline."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from config import DEFAULT_FRAME_INTERVAL_SECONDS, FRAME_STORAGE, MAX_VIDEO_FRAMES
from core.object_detection import SimulatedDetector, VisionAnalyzer
from core.video_extractor import VideoExtractionResult, extract_video_frames


class FrameProcessor:
    """Processes text-described frames, uploaded images, and extracted video frames."""

    def __init__(
        self,
        detector: SimulatedDetector | None = None,
        vision_analyzer: VisionAnalyzer | None = None,
    ):
        self.detector = detector or SimulatedDetector()
        self.vision_analyzer = vision_analyzer

    def _get_analyzer(self, provider_name: str | None = None) -> VisionAnalyzer:
        if provider_name:
            return VisionAnalyzer(provider=provider_name, fallback_to_simulation=True)
        return self.vision_analyzer or VisionAnalyzer(fallback_to_simulation=True)

    def process_description(self, item: dict[str, Any]) -> dict[str, Any]:
        """Process a synthetic/text-described frame record."""
        description = item["description"]
        location = item.get("location", "Unknown")
        result = self.detector.analyze_description_structured(description, location=location)
        return {
            "frame_id": item.get("frame_id") or f"FR-{uuid4().hex[:8].upper()}",
            "timestamp": item["timestamp"],
            "description": description,
            "location": location,
            "source_type": item.get("source_type", "simulation"),
            "source_video": item.get("source_video"),
            "image_path": item.get("image_path"),
            "processing_status": "processed",
            "model_provider": result.provider,
            "analysis_mode": result.analysis_mode,
            "activity": result.activity,
            "evidence": result.evidence,
            "confidence": result.confidence,
            "processing_ms": result.latency_ms,
            "error_message": result.error,
            "detections": result.detected_objects,
        }

    def process_image(
        self,
        image_path: str | Path,
        timestamp: str | None = None,
        location: str = "Perimeter",
        frame_id: str | None = None,
        source_type: str = "image_upload",
        source_video: str | None = None,
        prev_image_path: str | Path | None = None,
        description_hint: str | None = None,
        provider_name: str | None = None,
    ) -> dict[str, Any]:
        """Analyze an image file through the configured VisionAnalyzer."""
        analyzer = self._get_analyzer(provider_name)
        ts = timestamp or datetime.now().replace(microsecond=0).isoformat()
        fid = frame_id or f"FR-{uuid4().hex[:8].upper()}"

        try:
            result = analyzer.analyze_image(
                image_path=image_path,
                location=location,
                prev_image_path=prev_image_path,
                description_hint=description_hint,
            )
            status = "fallback" if result.error else "processed"
            return {
                "frame_id": fid,
                "timestamp": ts,
                "description": result.description,
                "location": result.location_hint or location,
                "source_type": source_type,
                "source_video": source_video,
                "image_path": str(image_path),
                "processing_status": status,
                "model_provider": result.provider,
                "analysis_mode": result.analysis_mode,
                "activity": result.activity,
                "evidence": result.evidence,
                "confidence": result.confidence,
                "processing_ms": result.latency_ms,
                "error_message": result.error,
                "detections": result.detected_objects,
            }
        except Exception as exc:
            return {
                "frame_id": fid,
                "timestamp": ts,
                "description": f"Frame processing failed: {exc}",
                "location": location,
                "source_type": source_type,
                "source_video": source_video,
                "image_path": str(image_path),
                "processing_status": "failed",
                "model_provider": analyzer.provider_name,
                "analysis_mode": analyzer.analysis_mode,
                "activity": "error",
                "evidence": str(exc),
                "confidence": None,
                "processing_ms": 0.0,
                "error_message": str(exc),
                "detections": [],
            }

    def process_video(
        self,
        video_path: str | Path,
        interval_seconds: float = DEFAULT_FRAME_INTERVAL_SECONDS,
        max_frames: int = MAX_VIDEO_FRAMES,
        base_timestamp: str | None = None,
        location: str = "Perimeter",
        provider_name: str | None = None,
        output_dir: str | Path | None = None,
        source_video_name: str | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[VideoExtractionResult, list[dict[str, Any]]]:
        """Extract video frames at configurable intervals and analyze each frame."""
        extraction = extract_video_frames(
            video_path=video_path,
            output_dir=output_dir or FRAME_STORAGE / Path(video_path).stem,
            interval_seconds=interval_seconds,
            max_frames=max_frames,
            base_timestamp=base_timestamp,
            location=location,
            source_video_name=source_video_name,
        )

        processed_frames: list[dict[str, Any]] = []
        total = len(extraction.frames)
        prev_img: str | None = None
        for idx, info in enumerate(extraction.frames):
            frame_record = self.process_image(
                image_path=info.image_path,
                timestamp=info.timestamp,
                location=info.location,
                frame_id=info.frame_id,
                source_type="video_frame",
                source_video=info.source_video,
                prev_image_path=prev_img,
                provider_name=provider_name,
            )
            processed_frames.append(frame_record)
            prev_img = info.image_path
            if progress_callback:
                progress_callback(idx + 1, total)

        return extraction, processed_frames
