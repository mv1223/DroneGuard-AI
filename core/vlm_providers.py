"""Vision-Language Model (VLM) provider abstraction and implementations.

Supports:
- OpenAI Vision (gpt-4o-mini / gpt-4o) via HTTPS
- Google Gemini Vision (gemini-2.0-flash) via HTTPS
- Local Ollama VLM (llava / qwen2.5vl) via HTTP
- Local OpenCV heuristic analyzer (HOG pedestrian + color/contour + motion)
- Deterministic text simulation fallback

Every provider returns a normalized VisionAnalysisResult that clearly separates
actual VLM inference, local OpenCV heuristics, and deterministic simulation.
"""

from __future__ import annotations

import base64
import json
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import cv2
import httpx
import numpy as np
from PIL import Image, UnidentifiedImageError

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    LOG_DIR,
    OLLAMA_BASE_URL,
    OLLAMA_VLM_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    VLM_MAX_RETRIES,
    VLM_TIMEOUT_SECONDS,
)
from core.logger import get_logger
from core.schemas import VisionAnalysisResult

logger = get_logger("droneguard.vlm", LOG_DIR)

VLM_SYSTEM_PROMPT = """You are a drone perimeter security vision analyst.
Analyze the provided drone image strictly from visible pixels.
Rules:
1. Never invent objects, colors, license plates, or identities that are not clearly visible.
2. Separate direct visual evidence from uncertainty.
3. Return ONLY valid JSON matching this schema:
{
  "description": "Concise factual observation of the frame",
  "detected_objects": [
    {
      "object_type": "person | truck | vehicle | bicycle | animal | package | activity",
      "description": "Short factual object description",
      "color": "color name or null",
      "confidence": 0.0,
      "evidence": "Visible cues supporting this detection"
    }
  ],
  "activity": "vehicle_present | person_present | restricted_area_activity | area_clear | monitoring",
  "location_hint": "Visible zone clue or null",
  "confidence": 0.0,
  "evidence": "Summary of visible evidence and any visual ambiguity/limitations"
}"""


class VLMProviderError(RuntimeError):
    """Raised when a configured VLM provider fails or returns invalid output."""


def validate_image_file(image_path: str | Path) -> Path:
    """Validate that an image file exists, is non-empty, and can be decoded."""
    path = Path(image_path)
    if not path.exists() or not path.is_file():
        raise ValueError(f"Image file does not exist: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Image file is empty (0 bytes): {path}")
    try:
        with Image.open(path) as img:
            img.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"Invalid or corrupted image file '{path.name}': {exc}") from exc
    return path


def _encode_image_base64(image_path: Path) -> tuple[str, str]:
    suffix = image_path.suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(suffix, "image/jpeg")
    return base64.b64encode(image_path.read_bytes()).decode("ascii"), mime


def _extract_json_payload(raw_text: str) -> dict[str, Any]:
    """Extract a JSON object from raw model text (including markdown fenced JSON)."""
    cleaned = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, flags=re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    else:
        brace_match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if brace_match:
            cleaned = brace_match.group(0)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Model JSON output must be an object.")
    return data


def _normalize_detections(raw_objects: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_objects, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in raw_objects:
        if not isinstance(item, dict):
            continue
        obj_type = str(item.get("object_type", "unknown")).strip().lower()
        if obj_type in ("car", "van", "suv", "pickup", "pickup truck"):
            obj_type = "truck" if "pickup" in obj_type else "vehicle"
        conf = item.get("confidence")
        try:
            conf_val = round(max(0.0, min(1.0, float(conf))), 3) if conf is not None else None
        except (TypeError, ValueError):
            conf_val = None
        color = item.get("color")
        if isinstance(color, str):
            color = color.strip().lower() or None
            if color in ("none", "null", "unknown", "n/a"):
                color = None
        desc = str(item.get("description") or "").strip()
        evidence = str(item.get("evidence") or "VLM visual observation").strip()
        normalized.append(
            {
                "object_type": obj_type,
                "description": desc or obj_type,
                "color": color,
                "confidence": conf_val,
                "attributes": {"evidence": evidence, "description": desc},
            }
        )
    return normalized


class BaseVLMProvider(ABC):
    """Abstract base class for visual analysis providers."""

    provider_name: str = "base"
    analysis_mode: str = "simulation"

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if the provider has required credentials/runtime."""

    @abstractmethod
    def analyze_image(
        self,
        image_path: str | Path,
        location: str | None = None,
        prev_image_path: str | Path | None = None,
        description_hint: str | None = None,
    ) -> VisionAnalysisResult:
        """Analyze one image and return structured observations."""


class OpenAIVLMProvider(BaseVLMProvider):
    """OpenAI Vision API provider using httpx."""

    analysis_mode = "actual_vlm"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int = VLM_TIMEOUT_SECONDS,
        max_retries: int = VLM_MAX_RETRIES,
    ):
        self.api_key = api_key if api_key is not None else OPENAI_API_KEY
        self.model = model or OPENAI_MODEL
        self.base_url = (base_url or OPENAI_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.provider_name = f"openai:{self.model}"

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def analyze_image(
        self,
        image_path: str | Path,
        location: str | None = None,
        prev_image_path: str | Path | None = None,
        description_hint: str | None = None,
    ) -> VisionAnalysisResult:
        if not self.is_configured():
            raise VLMProviderError("OPENAI_API_KEY is not configured.")
        path = validate_image_file(image_path)
        b64, mime = _encode_image_base64(path)
        user_text = (
            f"Analyze this drone security frame. Known zone/location context: {location or 'Unknown'}."
        )
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "max_tokens": 500,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": VLM_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        return _execute_http_vlm(
            url=f"{self.base_url}/chat/completions",
            headers=headers,
            payload=payload,
            extract_text=lambda r: r["choices"][0]["message"]["content"],
            provider_name=self.provider_name,
            analysis_mode=self.analysis_mode,
            location=location,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )


class GeminiVLMProvider(BaseVLMProvider):
    """Google Gemini Vision API provider using httpx."""

    analysis_mode = "actual_vlm"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = VLM_TIMEOUT_SECONDS,
        max_retries: int = VLM_MAX_RETRIES,
    ):
        self.api_key = api_key if api_key is not None else GEMINI_API_KEY
        self.model = model or GEMINI_MODEL
        self.timeout = timeout
        self.max_retries = max_retries
        self.provider_name = f"gemini:{self.model}"

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def analyze_image(
        self,
        image_path: str | Path,
        location: str | None = None,
        prev_image_path: str | Path | None = None,
        description_hint: str | None = None,
    ) -> VisionAnalysisResult:
        if not self.is_configured():
            raise VLMProviderError("GEMINI_API_KEY is not configured.")
        path = validate_image_file(image_path)
        b64, mime = _encode_image_base64(path)
        prompt = (
            f"{VLM_SYSTEM_PROMPT}\n\nKnown zone/location context: {location or 'Unknown'}."
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime, "data": b64}},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        return _execute_http_vlm(
            url=url,
            headers={"Content-Type": "application/json"},
            payload=payload,
            extract_text=lambda r: r["candidates"][0]["content"]["parts"][0]["text"],
            provider_name=self.provider_name,
            analysis_mode=self.analysis_mode,
            location=location,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )


class OllamaVLMProvider(BaseVLMProvider):
    """Local Ollama VLM provider (e.g., llava, qwen2.5vl)."""

    analysis_mode = "actual_vlm"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = VLM_TIMEOUT_SECONDS,
        max_retries: int = VLM_MAX_RETRIES,
    ):
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self.model = model or OLLAMA_VLM_MODEL
        self.timeout = timeout
        self.max_retries = max_retries
        self.provider_name = f"ollama:{self.model}"

    def is_configured(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=2.0)
            return resp.status_code == 200
        except Exception:
            return False

    def analyze_image(
        self,
        image_path: str | Path,
        location: str | None = None,
        prev_image_path: str | Path | None = None,
        description_hint: str | None = None,
    ) -> VisionAnalysisResult:
        path = validate_image_file(image_path)
        b64, _ = _encode_image_base64(path)
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": VLM_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Analyze this drone frame. Zone: {location or 'Unknown'}.",
                    "images": [b64],
                },
            ],
        }
        return _execute_http_vlm(
            url=f"{self.base_url}/api/chat",
            headers={"Content-Type": "application/json"},
            payload=payload,
            extract_text=lambda r: r["message"]["content"],
            provider_name=self.provider_name,
            analysis_mode=self.analysis_mode,
            location=location,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )


def _execute_http_vlm(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    extract_text: Any,
    provider_name: str,
    analysis_mode: str,
    location: str | None,
    timeout: int,
    max_retries: int,
) -> VisionAnalysisResult:
    started = time.perf_counter()
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, json=payload)
            if response.status_code == 429 or response.status_code >= 500:
                raise VLMProviderError(
                    f"Provider HTTP {response.status_code}: {response.text[:250]}"
                )
            if response.status_code >= 400:
                raise VLMProviderError(
                    f"Provider rejected request (HTTP {response.status_code}): {response.text[:250]}"
                )
            raw_json = response.json()
            raw_text = extract_text(raw_json)
            parsed = _extract_json_payload(raw_text)
            detections = _normalize_detections(parsed.get("detected_objects", []))
            conf = parsed.get("confidence")
            conf_val = round(max(0.0, min(1.0, float(conf))), 3) if conf is not None else None
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            return VisionAnalysisResult(
                description=str(parsed.get("description") or "No description returned.").strip(),
                detected_objects=detections,
                activity=str(parsed.get("activity") or "monitoring").strip(),
                location_hint=parsed.get("location_hint") or location,
                confidence=conf_val,
                evidence=str(
                    parsed.get("evidence") or "Direct VLM frame analysis."
                ).strip(),
                provider=provider_name,
                analysis_mode=analysis_mode,
                latency_ms=latency_ms,
                raw_response=raw_text[:2000],
            )
        except (httpx.TimeoutException, httpx.TransportError, VLMProviderError, json.JSONDecodeError, KeyError, ValueError) as exc:
            last_error = exc
            logger.warning(
                "VLM call failed (%s, attempt %d/%d): %s",
                provider_name,
                attempt + 1,
                max_retries + 1,
                exc,
            )
            if attempt < max_retries:
                time.sleep(min(2.0 * (attempt + 1), 5.0))
    raise VLMProviderError(f"{provider_name} failed after {max_retries + 1} attempts: {last_error}")


class OpenCVHeuristicAnalyzer(BaseVLMProvider):
    """Offline pixel-level OpenCV analyzer (HOG/silhouette + HSV color/contour + motion).

    Explicitly reports analysis_mode='local_cv_heuristic' rather than claiming VLM inference.
    """

    provider_name = "opencv-motion-hog-heuristic"
    analysis_mode = "local_cv_heuristic"

    def __init__(self):
        hog_cls = getattr(cv2, "HOGDescriptor", None)
        get_det = getattr(cv2, "HOGDescriptor_getDefaultPeopleDetector", None)
        if hog_cls is not None and get_det is not None:
            self._hog = hog_cls()
            self._hog.setSVMDetector(get_det())
        else:
            self._hog = None

    def is_configured(self) -> bool:
        return True

    def analyze_image(
        self,
        image_path: str | Path,
        location: str | None = None,
        prev_image_path: str | Path | None = None,
        description_hint: str | None = None,
    ) -> VisionAnalysisResult:
        started = time.perf_counter()
        path = validate_image_file(image_path)
        bgr = cv2.imread(str(path))
        if bgr is None:
            raise ValueError(f"OpenCV could not decode image: {path}")

        height, width = bgr.shape[:2]
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        mean_luma = float(np.mean(gray))
        lighting = "low-light/night" if mean_luma < 65 else "daylight/lit"

        # Motion delta vs previous frame if available
        motion_ratio = 0.0
        if prev_image_path:
            prev_path = Path(prev_image_path)
            if prev_path.exists():
                prev_bgr = cv2.imread(str(prev_path))
                if prev_bgr is not None and prev_bgr.shape == bgr.shape:
                    diff = cv2.absdiff(cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY), gray)
                    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                    motion_ratio = float(np.count_nonzero(thresh)) / float(thresh.size)

        detections: list[dict[str, Any]] = []

        # 1. Upright pedestrian detection (HOG+SVM when available, else vertical warm/high-contrast silhouette)
        scale = 640.0 / max(width, 1)
        resized = cv2.resize(bgr, (640, max(128, int(height * scale)))) if width > 640 else bgr
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        frame_area = float(resized.shape[0] * resized.shape[1])

        person_hits = []
        person_method = "HOG+SVM"
        if self._hog is not None:
            rects, weights = self._hog.detectMultiScale(
                resized, winStride=(8, 8), padding=(8, 8), scale=1.05
            )
            person_hits = [w for w in (weights.flatten().tolist() if len(weights) else []) if w > 0.35]
        else:
            # OpenCV 5.x headless fallback: detect tall upright high-saturation/contrast pedestrian silhouettes
            person_method = "HSV-vertical-silhouette"
            sat_mask = cv2.inRange(hsv, np.array([0, 95, 70]), np.array([35, 255, 255]))
            p_contours, _ = cv2.findContours(sat_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in p_contours:
                area = cv2.contourArea(cnt)
                if 0.002 * frame_area <= area <= 0.08 * frame_area:
                    _, _, bw, bh = cv2.boundingRect(cnt)
                    aspect = bh / max(bw, 1)
                    if 1.1 <= aspect <= 3.8 and bh >= 28:
                        person_hits.append(min(0.8, 0.45 + area / (0.05 * frame_area)))

        if person_hits:
            best_conf = round(min(0.95, 0.5 + 0.15 * max(person_hits)), 3)
            detections.append(
                {
                    "object_type": "person",
                    "description": f"Pedestrian silhouette heuristic ({len(person_hits)} region(s))",
                    "color": None,
                    "confidence": best_conf,
                    "attributes": {
                        "evidence": f"OpenCV {person_method} matched {len(person_hits)} upright human-scale region(s)",
                        "method": person_method,
                    },
                }
            )

        # 2. Dominant colored vehicle-scale contour heuristic (blue/red rectangular regions)
        color_masks = {
            "blue": cv2.inRange(hsv, np.array([95, 70, 50]), np.array([135, 255, 255])),
            "red": cv2.bitwise_or(
                cv2.inRange(hsv, np.array([0, 80, 60]), np.array([10, 255, 255])),
                cv2.inRange(hsv, np.array([165, 80, 60]), np.array([180, 255, 255])),
            ),
        }
        for color_name, mask in color_masks.items():
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            large_boxes = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if 0.02 * frame_area <= area <= 0.65 * frame_area:
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    aspect = bw / max(bh, 1)
                    if 0.8 <= aspect <= 4.0:
                        large_boxes.append((area, bw, bh))
            if large_boxes:
                top_area = max(b[0] for b in large_boxes)
                detections.append(
                    {
                        "object_type": "vehicle",
                        "description": f"{color_name.capitalize()} vehicle-scale object region",
                        "color": color_name,
                        "confidence": round(min(0.78, 0.45 + (top_area / frame_area)), 3),
                        "attributes": {
                            "evidence": (
                                f"HSV {color_name} contour covering {top_area / frame_area * 100:.1f}% "
                                f"of frame (heuristic region, not semantic vehicle ID)"
                            ),
                            "method": "HSV-contour",
                        },
                    }
                )

        # Restricted-zone context from caller metadata only (never fabricated from pixels)
        if location and any(tok in location.lower() for tok in ("restricted", "server", "loading dock")) and detections:
            detections.append(
                {
                    "object_type": "activity",
                    "description": f"Activity in designated restricted zone ({location})",
                    "color": None,
                    "confidence": 0.75,
                    "attributes": {"activity": "restricted_area_presence", "evidence": "Zone metadata + visual detection"},
                }
            )

        if detections:
            obj_summary = ", ".join(d["description"] for d in detections)
            description = (
                f"[{lighting}, luma={mean_luma:.0f}] OpenCV heuristic detected: {obj_summary}."
            )
            activity = (
                "restricted_area_activity"
                if any(d["object_type"] == "activity" for d in detections)
                else ("person_present" if any(d["object_type"] == "person" for d in detections) else "vehicle_present")
            )
        else:
            description = (
                f"[{lighting}, luma={mean_luma:.0f}] No HOG person or prominent colored vehicle region detected"
                + (f" (frame motion {motion_ratio * 100:.1f}%)." if motion_ratio > 0.01 else ".")
            )
            activity = "motion_detected" if motion_ratio > 0.03 else "area_clear"

        confs = [d["confidence"] for d in detections if d.get("confidence") is not None]
        avg_conf = round(sum(confs) / len(confs), 3) if confs else None
        evidence = (
            f"Local OpenCV pixel heuristics (mean luminance {mean_luma:.1f}/255, "
            f"motion delta {motion_ratio * 100:.2f}%). "
            "Limitation: Classical CV heuristics cannot perform open-vocabulary semantic reasoning."
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return VisionAnalysisResult(
            description=description,
            detected_objects=detections,
            activity=activity,
            location_hint=location,
            confidence=avg_conf,
            evidence=evidence,
            provider=self.provider_name,
            analysis_mode=self.analysis_mode,
            latency_ms=latency_ms,
        )


class SimulatedVLMProvider(BaseVLMProvider):
    """Deterministic text/keyword simulation provider for offline testing and fallback."""

    provider_name = "deterministic-simulation"
    analysis_mode = "simulation"

    def is_configured(self) -> bool:
        return True

    def analyze_description(self, description: str, location: str | None = None) -> VisionAnalysisResult:
        started = time.perf_counter()
        text = description.lower()
        detections: list[dict[str, Any]] = []

        if any(w in text for w in ("person", "people", "man", "woman", "pedestrian", "intruder")):
            detections.append(
                {
                    "object_type": "person",
                    "description": "Person observed in simulated description",
                    "color": None,
                    "confidence": 0.90,
                    "attributes": {"evidence": "description keyword match"},
                }
            )
        vehicle_words = ("truck", "car", "vehicle", "pickup", "ford", "motorcycle", "van", "suv")
        if any(w in text for w in vehicle_words):
            color_match = re.search(r"\b(blue|red|black|white|silver|grey|gray|green)\b", text)
            kind = "truck" if ("truck" in text or "pickup" in text) else "vehicle"
            color = color_match.group(1) if color_match else None
            label = f"{color} {kind}".strip() if color else kind
            detections.append(
                {
                    "object_type": kind,
                    "description": f"{label.capitalize()} observed in simulated description",
                    "color": color,
                    "confidence": 0.85,
                    "attributes": {"evidence": "description keyword match"},
                }
            )
        if "restricted" in text or (location and "restricted" in location.lower() and detections):
            detections.append(
                {
                    "object_type": "activity",
                    "description": "Restricted-area activity indicated",
                    "color": None,
                    "confidence": 0.90,
                    "attributes": {"activity": "restricted_area_presence", "evidence": "zone/description keyword"},
                }
            )

        activity = "area_clear"
        if any(d["object_type"] == "activity" for d in detections):
            activity = "restricted_area_activity"
        elif any(d["object_type"] == "person" for d in detections):
            activity = "person_present"
        elif any(d["object_type"] in ("truck", "vehicle") for d in detections):
            activity = "vehicle_present"

        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return VisionAnalysisResult(
            description=description,
            detected_objects=detections,
            activity=activity,
            location_hint=location,
            confidence=0.88 if detections else None,
            evidence="Deterministic text-keyword simulation (not visual pixel inference).",
            provider=self.provider_name,
            analysis_mode=self.analysis_mode,
            latency_ms=latency_ms,
        )

    def analyze_image(
        self,
        image_path: str | Path,
        location: str | None = None,
        prev_image_path: str | Path | None = None,
        description_hint: str | None = None,
    ) -> VisionAnalysisResult:
        path = validate_image_file(image_path)
        hint = description_hint or f"Simulated frame observation from file {path.name} at {location or 'Unknown'}."
        result = self.analyze_description(hint, location=location)
        result.evidence = (
            "Simulated analysis mode (no actual VLM inference performed on pixels). "
            f"Derived from metadata/filename '{path.name}'."
        )
        return result


def available_vlm_providers() -> dict[str, bool]:
    """Report configuration readiness of each vision provider."""
    return {
        "openai": OpenAIVLMProvider().is_configured(),
        "gemini": GeminiVLMProvider().is_configured(),
        "ollama": OllamaVLMProvider().is_configured(),
        "opencv_heuristic": True,
        "simulation": True,
    }


def create_vlm_provider(provider_name: str = "auto") -> BaseVLMProvider:
    """Instantiate the requested provider or auto-select the best configured one."""
    choice = (provider_name or "auto").strip().lower()
    if choice == "openai":
        return OpenAIVLMProvider()
    if choice == "gemini":
        return GeminiVLMProvider()
    if choice == "ollama":
        return OllamaVLMProvider()
    if choice in ("opencv", "opencv_heuristic", "local_cv"):
        return OpenCVHeuristicAnalyzer()
    if choice == "simulation":
        return SimulatedVLMProvider()

    # Auto mode: prefer configured real VLM -> Ollama -> OpenCV heuristic
    for cls in (OpenAIVLMProvider, GeminiVLMProvider, OllamaVLMProvider):
        instance = cls()
        if instance.is_configured():
            return instance
    return OpenCVHeuristicAnalyzer()
