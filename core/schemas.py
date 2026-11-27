from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class Telemetry:
    timestamp: str
    drone_id: str
    latitude: float
    longitude: float
    altitude: float
    battery_percentage: float
    speed: float
    location_name: str
    flight_status: str = "MONITORING"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DetectionItem:
    object_type: str
    description: str = ""
    color: str | None = None
    confidence: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    observation_group_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VisionAnalysisResult:
    description: str
    detected_objects: list[dict[str, Any]]
    activity: str
    location_hint: str | None
    confidence: float | None
    evidence: str
    provider: str
    analysis_mode: str  # actual_vlm | local_cv_heuristic | simulation | simulation_fallback
    latency_ms: float = 0.0
    error: str | None = None
    raw_response: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FrameObservation:
    frame_id: str
    timestamp: str
    description: str
    location: str
    source_type: str = "simulation"
    source_video: str | None = None
    image_path: str | None = None
    processing_status: str = "processed"
    model_provider: str = "deterministic-simulation"
    analysis_mode: str = "simulation"
    activity: str = "observation"
    evidence: str = ""
    confidence: float | None = None
    processing_ms: float = 0.0
    error_message: str | None = None
    detections: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
