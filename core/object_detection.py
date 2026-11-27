"""Object detection & Vision-Language Model abstraction.

Preserves SimulatedDetector for deterministic text-based scenarios while
providing a production-ready VisionAnalyzer supporting real VLMs, local OpenCV
heuristics, and transparent fallback handling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config import LOG_DIR, VLM_MODE, VLM_PROVIDER
from core.logger import get_logger
from core.schemas import VisionAnalysisResult
from core.vlm_providers import (
    BaseVLMProvider,
    OpenCVHeuristicAnalyzer,
    SimulatedVLMProvider,
    VLMProviderError,
    available_vlm_providers,
    create_vlm_provider,
    validate_image_file,
)

logger = get_logger("droneguard.vision", LOG_DIR)


class SimulatedDetector:
    """Deterministic text-keyword extractor for synthetic descriptions."""

    provider_name = "deterministic-simulation"
    analysis_mode = "simulation"

    def __init__(self):
        self._sim = SimulatedVLMProvider()

    def analyze_description(self, description: str, location: str | None = None) -> list[dict[str, Any]]:
        return self._sim.analyze_description(description, location=location).detected_objects

    def analyze_description_structured(
        self, description: str, location: str | None = None
    ) -> VisionAnalysisResult:
        return self._sim.analyze_description(description, location=location)


class VisionAnalyzer:
    """Configurable visual analyzer with provider abstraction and graceful fallback."""

    def __init__(
        self,
        provider: BaseVLMProvider | str | None = None,
        fallback_to_simulation: bool = True,
    ):
        if isinstance(provider, BaseVLMProvider):
            self._provider = provider
        elif isinstance(provider, str):
            self._provider = create_vlm_provider(provider)
        else:
            default_choice = "simulation" if VLM_MODE == "simulation" and VLM_PROVIDER == "auto" else VLM_PROVIDER
            self._provider = create_vlm_provider(default_choice)

        self.fallback_to_simulation = fallback_to_simulation
        self.provider_name = self._provider.provider_name
        self.analysis_mode = self._provider.analysis_mode

    @staticmethod
    def available_providers() -> dict[str, bool]:
        return available_vlm_providers()

    def analyze_image(
        self,
        image_path: str | Path,
        location: str | None = None,
        prev_image_path: str | Path | None = None,
        description_hint: str | None = None,
    ) -> VisionAnalysisResult:
        """Analyze an image using the configured provider, with honest fallback."""
        path = validate_image_file(image_path)
        try:
            return self._provider.analyze_image(
                path,
                location=location,
                prev_image_path=prev_image_path,
                description_hint=description_hint,
            )
        except VLMProviderError as exc:
            logger.warning("Vision provider '%s' failed: %s", self._provider.provider_name, exc)
            if not self.fallback_to_simulation:
                raise
            # Prefer OpenCV local heuristic over pure text simulation when pixels exist,
            # or fall back to SimulatedVLMProvider if heuristic also fails.
            try:
                fallback = OpenCVHeuristicAnalyzer().analyze_image(
                    path,
                    location=location,
                    prev_image_path=prev_image_path,
                    description_hint=description_hint,
                )
                fallback.analysis_mode = "local_cv_fallback"
                fallback.error = str(exc)
                fallback.evidence = f"[Fallback after {self._provider.provider_name} error: {exc}] " + fallback.evidence
                return fallback
            except Exception:
                sim = SimulatedVLMProvider().analyze_image(
                    path, location=location, description_hint=description_hint
                )
                sim.analysis_mode = "simulation_fallback"
                sim.error = str(exc)
                sim.evidence = f"[Simulation fallback after error: {exc}] " + sim.evidence
                return sim
