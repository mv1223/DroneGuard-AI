import json
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from core.frame_processor import FrameProcessor
from core.object_detection import VisionAnalyzer
from core.video_extractor import extract_video_frames
from core.vlm_providers import (
    GeminiVLMProvider,
    OllamaVLMProvider,
    OpenAIVLMProvider,
    VLMProviderError,
)
from scripts.generate_sample_media import generate_sample_media


def test_video_frame_extraction_intervals(tmp_path):
    media = generate_sample_media(tmp_path / "media")
    video = media["property_patrol_demo"]

    res_2s = extract_video_frames(video, output_dir=tmp_path / "f2", interval_seconds=2.0)
    res_4s = extract_video_frames(video, output_dir=tmp_path / "f4", interval_seconds=4.0)

    assert res_2s.extracted_count == 8
    assert res_4s.extracted_count == 4
    assert res_2s.frames[0].source_video == "property_patrol_demo.mp4"


def test_opencv_heuristic_analyzes_generated_images(tmp_path):
    media = generate_sample_media(tmp_path / "media")
    analyzer = VisionAnalyzer(provider="opencv_heuristic")
    res = analyzer.analyze_image(media["garage_blue_truck"], location="Garage")
    assert res.analysis_mode == "local_cv_heuristic"
    assert any(d.get("color") == "blue" for d in res.detected_objects)


def test_invalid_media_files_raise_value_error(tmp_path):
    bad_img = tmp_path / "corrupt.jpg"
    bad_img.write_bytes(b"not-a-jpeg")
    analyzer = VisionAnalyzer(provider="opencv_heuristic", fallback_to_simulation=False)
    with pytest.raises(ValueError):
        analyzer.analyze_image(bad_img)

    bad_vid = tmp_path / "empty.mp4"
    bad_vid.write_bytes(b"")
    with pytest.raises(ValueError):
        extract_video_frames(bad_vid, output_dir=tmp_path / "out")


def test_missing_api_key_graceful_fallback(tmp_path):
    media = generate_sample_media(tmp_path / "media")
    provider = OpenAIVLMProvider(api_key="")
    assert not provider.is_configured()
    with pytest.raises(VLMProviderError):
        provider.analyze_image(media["garage_blue_truck"])

    analyzer = VisionAnalyzer(provider=provider, fallback_to_simulation=True)
    res = analyzer.analyze_image(media["garage_blue_truck"], location="Garage")
    assert res.analysis_mode == "local_cv_fallback"
    assert res.error is not None


def test_mocked_openai_vlm_and_rate_limit_retry(tmp_path):
    media = generate_sample_media(tmp_path / "media")

    class FakeResp:
        def __init__(self, status_code, data, text=""):
            self.status_code = status_code
            self._data = data
            self.text = text

        def json(self):
            return self._data

    vlm_json = json.dumps(
        {
            "description": "A blue pickup truck parked near the garage.",
            "detected_objects": [
                {
                    "object_type": "truck",
                    "description": "Blue pickup truck",
                    "color": "blue",
                    "confidence": 0.94,
                    "evidence": "Blue cab and truck bed visible",
                }
            ],
            "activity": "vehicle_present",
            "location_hint": "Garage",
            "confidence": 0.94,
            "evidence": "Clear daytime frame showing blue pickup.",
        }
    )
    calls = {"n": 0}

    def fake_post(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResp(429, {}, "Rate limit exceeded")
        return FakeResp(200, {"choices": [{"message": {"content": vlm_json}}]})

    provider = OpenAIVLMProvider(api_key="test-key", max_retries=1)
    with patch("core.vlm_providers.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.side_effect = fake_post
        with patch("core.vlm_providers.time.sleep"):
            res = provider.analyze_image(media["garage_blue_truck"], location="Garage")

    assert calls["n"] == 2
    assert res.analysis_mode == "actual_vlm"
    assert res.provider.startswith("openai:")
    assert res.detected_objects[0]["color"] == "blue"


def test_mocked_gemini_and_ollama_providers(tmp_path):
    media = generate_sample_media(tmp_path / "media")

    class FakeResp:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    gem_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "description": "Person standing near main gate.",
                                    "detected_objects": [
                                        {
                                            "object_type": "person",
                                            "description": "Standing pedestrian",
                                            "color": None,
                                            "confidence": 0.91,
                                            "evidence": "Human figure visible",
                                        }
                                    ],
                                    "activity": "person_present",
                                    "location_hint": "Main Gate",
                                    "confidence": 0.91,
                                    "evidence": "Night gate view",
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }
    gem = GeminiVLMProvider(api_key="test-gem")
    with patch("core.vlm_providers.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = FakeResp(gem_payload)
        res_g = gem.analyze_image(media["gate_midnight_person"], location="Main Gate")
    assert res_g.analysis_mode == "actual_vlm"
    assert res_g.detected_objects[0]["object_type"] == "person"

    ollama_payload = {
        "message": {
            "content": json.dumps(
                {
                    "description": "Intruder in restricted zone.",
                    "detected_objects": [],
                    "activity": "restricted_area_activity",
                    "location_hint": "Restricted Zone",
                    "confidence": 0.8,
                    "evidence": "Zone view",
                }
            )
        }
    }
    oll = OllamaVLMProvider()
    with patch("core.vlm_providers.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = FakeResp(ollama_payload)
        res_o = oll.analyze_image(media["restricted_zone_intruder"])
    assert res_o.provider.startswith("ollama:")


def test_frame_processor_video_end_to_end(tmp_path):
    media = generate_sample_media(tmp_path / "media")
    proc = FrameProcessor()
    ext, frames = proc.process_video(
        media["property_patrol_demo"],
        interval_seconds=4.0,
        output_dir=tmp_path / "extracted",
        provider_name="simulation",
    )
    assert ext.extracted_count == 4
    assert all(f["analysis_mode"] == "simulation" for f in frames)
