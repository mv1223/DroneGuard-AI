"""OpenCV-based video validation and configurable interval frame extraction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from config import DEFAULT_FRAME_INTERVAL_SECONDS, FRAME_STORAGE, LOG_DIR, MAX_VIDEO_FRAMES
from core.logger import get_logger

logger = get_logger("droneguard.video", LOG_DIR)

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass
class ExtractedFrameInfo:
    frame_id: str
    frame_index: int
    offset_seconds: float
    timestamp: str
    image_path: str
    location: str
    source_video: str
    motion_score: float


@dataclass
class VideoExtractionResult:
    source_video: str
    fps: float
    total_video_frames: int
    duration_seconds: float
    interval_seconds: float
    extracted_count: int
    frames: list[ExtractedFrameInfo]
    extraction_ms: float


def validate_video_file(video_path: str | Path) -> tuple[Path, cv2.VideoCapture, float, int]:
    """Validate a video file and return an opened VideoCapture plus metadata."""
    path = Path(video_path)
    if not path.exists() or not path.is_file():
        raise ValueError(f"Video file does not exist: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Video file is empty (0 bytes): {path}")
    if path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
        raise ValueError(
            f"Unsupported video extension '{path.suffix}'. Supported: {sorted(SUPPORTED_VIDEO_EXTENSIONS)}"
        )

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise ValueError(f"Unable to open video stream '{path.name}'. File may be corrupted.")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if fps <= 0:
        fps = 10.0  # Safe fallback for streams missing FPS metadata
    if total_frames <= 0:
        # Probe first frame to verify readability
        ok, _ = cap.read()
        if not ok:
            cap.release()
            raise ValueError(f"Video '{path.name}' contains no readable frames.")
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        total_frames = 1

    return path, cap, fps, total_frames


def extract_video_frames(
    video_path: str | Path,
    output_dir: str | Path | None = None,
    interval_seconds: float = DEFAULT_FRAME_INTERVAL_SECONDS,
    max_frames: int = MAX_VIDEO_FRAMES,
    base_timestamp: str | None = None,
    location: str = "Perimeter",
    source_video_name: str | None = None,
) -> VideoExtractionResult:
    """Extract frames from a video at a fixed time interval using OpenCV."""
    import time

    started = time.perf_counter()
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than 0.")
    if max_frames <= 0:
        raise ValueError("max_frames must be greater than 0.")

    path, cap, fps, total_frames = validate_video_file(video_path)
    video_label = source_video_name or path.name
    base_dt = (
        datetime.fromisoformat(base_timestamp)
        if base_timestamp
        else datetime.now().replace(microsecond=0)
    )

    slug = f"{path.stem}_{uuid4().hex[:6]}"
    target_dir = Path(output_dir) if output_dir else (FRAME_STORAGE / slug)
    target_dir.mkdir(parents=True, exist_ok=True)

    step_frames = max(1, int(round(interval_seconds * fps)))
    duration_seconds = round(total_frames / fps, 3)

    extracted: list[ExtractedFrameInfo] = []
    prev_gray = None
    frame_idx = 0

    try:
        while len(extracted) < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, bgr = cap.read()
            if not ok or bgr is None:
                break

            offset_sec = round(frame_idx / fps, 3)
            frame_ts = (base_dt + timedelta(seconds=offset_sec)).replace(microsecond=0).isoformat()
            frame_id = f"FR-{uuid4().hex[:8].upper()}"
            out_file = target_dir / f"frame_{len(extracted) + 1:04d}_{frame_id}.jpg"
            cv2.imwrite(str(out_file), bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])

            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            motion_score = 0.0
            if prev_gray is not None and prev_gray.shape == gray.shape:
                diff = cv2.absdiff(prev_gray, gray)
                _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                motion_score = round(float(np.count_nonzero(thresh)) / float(thresh.size), 4)
            prev_gray = gray

            extracted.append(
                ExtractedFrameInfo(
                    frame_id=frame_id,
                    frame_index=frame_idx,
                    offset_seconds=offset_sec,
                    timestamp=frame_ts,
                    image_path=str(out_file),
                    location=location,
                    source_video=video_label,
                    motion_score=motion_score,
                )
            )
            frame_idx += step_frames
            if frame_idx >= total_frames and total_frames > 1:
                break
    finally:
        cap.release()

    if not extracted:
        raise ValueError(f"No frames could be extracted from '{path.name}'.")

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "Extracted %d frame(s) from '%s' (interval=%.2fs, duration=%.2fs) in %.1fms",
        len(extracted),
        video_label,
        interval_seconds,
        duration_seconds,
        elapsed_ms,
    )
    return VideoExtractionResult(
        source_video=video_label,
        fps=round(fps, 2),
        total_video_frames=total_frames,
        duration_seconds=duration_seconds,
        interval_seconds=interval_seconds,
        extracted_count=len(extracted),
        frames=extracted,
        extraction_ms=elapsed_ms,
    )
