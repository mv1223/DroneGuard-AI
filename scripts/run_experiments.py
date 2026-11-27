"""Execute reproducible DroneGuard AI experiments and generate benchmark artifacts."""

from __future__ import annotations

import json
import platform
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config import REPORTS_DIR, SAMPLE_MEDIA_DIR
from core.alert_engine import event_alerts
from core.event_analyzer import classify_events, correlate_sequence_events
from core.frame_processor import FrameProcessor
from core.pipeline import SecurityPipeline
from database.repository import Repository
from scripts.generate_sample_media import generate_sample_media
from scripts.scalability_test import run_benchmark


def experiment_frame_intervals(video_path: Path) -> list[dict]:
    """Experiment 1: Evaluate frame extraction interval vs speed, storage, and scene recall."""
    intervals = [0.5, 1.0, 2.0, 4.0, 8.0]
    results = []
    for interval in intervals:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            processor = FrameProcessor()
            t0 = time.perf_counter()
            extraction, frames = processor.process_video(
                video_path=video_path,
                interval_seconds=interval,
                max_frames=100,
                base_timestamp="2026-11-27T12:00:00",
                location="Perimeter",
                provider_name="opencv_heuristic",
                output_dir=td_path / "frames",
            )
            total_s = time.perf_counter() - t0
            disk_kb = round(
                sum(Path(f["image_path"]).stat().st_size for f in frames if f.get("image_path")) / 1024.0,
                2,
            )
            det_count = sum(len(f.get("detections", [])) for f in frames)
            errors = sum(1 for f in frames if f.get("processing_status") == "failed")
            # Scene coverage across the 4 video segments (0-4s truck, 4-8s clear, 8-12s person, 12-16s truck)
            offsets = [info.offset_seconds for info in extraction.frames]
            segments_hit = sum(
                1
                for lo, hi in ((0.0, 4.0), (8.0, 12.0), (12.0, 16.0))
                if any(lo <= off < hi for off in offsets)
            )
            results.append(
                {
                    "interval_seconds": interval,
                    "extracted_frames": extraction.extracted_count,
                    "extraction_ms": extraction.extraction_ms,
                    "total_pipeline_seconds": round(total_s, 4),
                    "avg_ms_per_frame": round((total_s * 1000) / max(len(frames), 1), 2),
                    "storage_kb": disk_kb,
                    "detections": det_count,
                    "active_scenes_covered": f"{segments_hit}/3",
                    "errors": errors,
                }
            )
    return results


def experiment_provider_modes(media: dict[str, Path]) -> list[dict]:
    """Experiment 2: Compare Deterministic Simulation vs OpenCV Heuristic CV on sample images."""
    image_specs = [
        ("garage_blue_truck.jpg", "Garage", "2026-11-27T12:00:05", "A blue pickup truck parked near the garage."),
        ("gate_midnight_person.jpg", "Main Gate", "2026-11-27T00:01:15", "A person standing near the main gate at midnight."),
        ("restricted_zone_intruder.jpg", "Restricted Zone", "2026-11-27T14:12:00", "A person inside the restricted zone."),
    ]
    rows = []
    for mode in ("simulation", "opencv_heuristic"):
        processor = FrameProcessor()
        t0 = time.perf_counter()
        detections_total = 0
        errors = 0
        for fname, loc, ts, hint in image_specs:
            path = media[Path(fname).stem]
            out = processor.process_image(
                image_path=path,
                timestamp=ts,
                location=loc,
                description_hint=hint if mode == "simulation" else None,
                provider_name=mode,
            )
            detections_total += len(out.get("detections", []))
            if out.get("processing_status") == "failed":
                errors += 1
        elapsed_ms = (time.perf_counter() - t0) * 1000
        rows.append(
            {
                "provider_mode": mode,
                "frames_processed": len(image_specs),
                "total_ms": round(elapsed_ms, 2),
                "avg_ms_per_frame": round(elapsed_ms / len(image_specs), 2),
                "total_detections": detections_total,
                "errors": errors,
                "requires_api_key": False,
            }
        )
    return rows


def experiment_alert_thresholds() -> list[dict]:
    """Experiment 3: Measure alert deduplication and loitering window sensitivity."""
    results = []
    burst_frames = [
        {"frame_id": f"BURST-{i:02d}", "timestamp": f"2026-11-27T00:01:{i * 20:02d}" if i < 3 else f"2026-11-27T00:{1 + i // 3:02d}:{(i * 20) % 60:02d}",
         "location": "Main Gate", "description": "A person near the main gate at midnight."}
        for i in range(6)
    ]
    for dedup_window in (0, 60, 300):
        with tempfile.TemporaryDirectory() as td:
            repo = Repository(Path(td) / "alerts.db")
            proc = FrameProcessor()
            raw_alerts = 0
            for item in burst_frames:
                fr = proc.process_description(item)
                repo.add_frame(fr)
                evts = classify_events(fr) + correlate_sequence_events(fr, repo, loitering_seconds=30)
                for ev in evts:
                    eid = repo.add_event(fr["frame_id"], ev, fr["timestamp"], fr["location"])
                    for al in event_alerts(fr, [ev]):
                        raw_alerts += 1
                        repo.add_alert(al, fr["timestamp"], event_id=eid, frame_id=fr["frame_id"], dedup_window_seconds=dedup_window)
            stored = len(repo.list_alerts())
            results.append(
                {
                    "dedup_window_seconds": dedup_window,
                    "input_frames": len(burst_frames),
                    "raw_alerts_triggered": raw_alerts,
                    "stored_alerts_after_dedup": stored,
                    "reduction_pct": round((1 - stored / max(raw_alerts, 1)) * 100, 1),
                }
            )
    return results


def _draw_charts(results: dict, chart_dir: Path) -> None:
    chart_dir.mkdir(parents=True, exist_ok=True)

    # Chart 1: Scalability (frames vs throughput & query ms)
    scal = results["scalability"]
    w, h = 900, 440
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((30, 18), "SQLite Scalability: Frame Count vs Indexed Query Latency (ms)", fill=(20, 35, 60))

    # Plot bars for query_object_color_ms and query_description_ms
    margin_l, margin_b, margin_t = 80, 70, 65
    plot_w, plot_h = w - margin_l - 40, h - margin_b - margin_t
    draw.line((margin_l, margin_t, margin_l, h - margin_b), fill=(60, 60, 60), width=2)
    draw.line((margin_l, h - margin_b, w - 40, h - margin_b), fill=(60, 60, 60), width=2)

    max_ms = max(max(r["query_description_ms"], r["query_object_color_ms"], r["query_time_location_ms"]) for r in scal) * 1.25
    max_ms = max(max_ms, 1.0)
    group_w = plot_w / len(scal)
    for idx, row in enumerate(scal):
        gx = margin_l + idx * group_w + 18
        bw = max(14, int((group_w - 40) / 3))
        metrics = [
            (row["query_description_ms"], (52, 115, 220), "Desc LIKE"),
            (row["query_object_color_ms"], (35, 165, 120), "Obj+Color"),
            (row["query_time_location_ms"], (235, 130, 45), "Time+Loc"),
        ]
        for m_idx, (val, color, _) in enumerate(metrics):
            bh = int((val / max_ms) * (plot_h - 15))
            x0 = int(gx + m_idx * (bw + 4))
            y0 = h - margin_b - bh
            draw.rectangle((x0, y0, x0 + bw, h - margin_b), fill=color)
            draw.text((x0, max(margin_t, y0 - 14)), f"{val:.1f}", fill=(30, 30, 30))
        draw.text((int(gx + 10), h - margin_b + 10), f"{row['frames']} frames", fill=(30, 30, 30))

    # Legend
    lx = margin_l + 10
    for color, lbl in [((52, 115, 220), "Description LIKE"), ((35, 165, 120), "Object+Color Index"), ((235, 130, 45), "Time+Location Index")]:
        draw.rectangle((lx, 42, lx + 14, 54), fill=color)
        draw.text((lx + 20, 41), lbl, fill=(30, 30, 30))
        lx += 165
    img.save(chart_dir / "scalability_chart.png")

    # Chart 2: Frame Interval Trade-off
    iv = results["frame_intervals"]
    img2 = Image.new("RGB", (w, h), (255, 255, 255))
    draw2 = ImageDraw.Draw(img2)
    draw2.text((30, 18), "Video Extraction Interval vs Processing Time (s) & Frames Extracted", fill=(20, 35, 60))
    draw2.line((margin_l, margin_t, margin_l, h - margin_b), fill=(60, 60, 60), width=2)
    draw2.line((margin_l, h - margin_b, w - 40, h - margin_b), fill=(60, 60, 60), width=2)

    max_t = max(r["total_pipeline_seconds"] for r in iv) * 1.25
    max_t = max(max_t, 0.1)
    gw = plot_w / len(iv)
    for idx, row in enumerate(iv):
        bx = int(margin_l + idx * gw + gw * 0.25)
        bw = int(gw * 0.45)
        bh = int((row["total_pipeline_seconds"] / max_t) * (plot_h - 15))
        y0 = h - margin_b - bh
        draw2.rectangle((bx, y0, bx + bw, h - margin_b), fill=(45, 110, 210))
        draw2.text((bx, max(margin_t, y0 - 16)), f"{row['total_pipeline_seconds']:.2f}s ({row['extracted_frames']}f)", fill=(20, 20, 20))
        draw2.text((bx, h - margin_b + 10), f"{row['interval_seconds']}s ({row['active_scenes_covered']})", fill=(30, 30, 30))
    img2.save(chart_dir / "interval_tradeoff_chart.png")

    # Chart 3: Clean Architecture Block Diagram PNG
    aw, ah = 960, 480
    arch = Image.new("RGB", (aw, ah), (248, 250, 253))
    ad = ImageDraw.Draw(arch)
    ad.text((28, 18), "DroneGuard AI v2.0 — System Architecture & Data Flow", fill=(18, 32, 58))
    boxes = [
        (40, 75, 240, 155, (226, 238, 255), "1. Inputs\nImages / MP4 Video\nJSON Telemetry"),
        (290, 75, 510, 155, (226, 238, 255), "2. Media Pipeline\nOpenCV Extractor\nInterval Sampling"),
        (560, 75, 860, 155, (218, 244, 232), "3. Vision Providers\nOpenAI / Gemini / Ollama\nOpenCV HOG + Sim Fallback"),
        (560, 205, 860, 285, (255, 242, 218), "4. Reasoning & Rules\nEvent Classifier + Correlation\nLoitering & Repeat-Vehicle"),
        (290, 205, 510, 285, (238, 232, 255), "5. SQLite Repository\nIndexed Frames, Detections\nEvents, Alerts, Model Runs"),
        (40, 205, 240, 285, (255, 228, 228), "6. Alert Engine\nCritical/High/Med/Low\nTime-Window Dedup"),
        (160, 345, 460, 430, (225, 240, 250), "7. Security Analyst Agent\nContextManager + LangChain Tools\nGrounded Offline / LLM Mode"),
        (520, 345, 820, 430, (225, 240, 250), "8. Streamlit Dashboard\n7 Tabs: Media, Frame Index,\nAlerts, Telemetry, Q&A, Reports"),
    ]
    for x0, y0, x1, y1, fill, text in boxes:
        ad.rounded_rectangle((x0, y0, x1, y1), radius=10, fill=fill, outline=(70, 95, 130), width=2)
        ad.multiline_text((x0 + 12, y0 + 14), text, fill=(20, 30, 45), spacing=4)

    arrows = [
        ((240, 115), (290, 115)),
        ((510, 115), (560, 115)),
        ((710, 155), (710, 205)),
        ((560, 245), (510, 245)),
        ((290, 245), (240, 245)),
        ((380, 285), (320, 345)),
        ((430, 285), (630, 345)),
        ((460, 388), (520, 388)),
    ]
    for p1, p2 in arrows:
        ad.line((p1[0], p1[1], p2[0], p2[1]), fill=(55, 80, 120), width=3)
    arch.save(chart_dir / "architecture_diagram.png")


def run_all_experiments() -> dict:
    media = generate_sample_media(SAMPLE_MEDIA_DIR)
    intervals = experiment_frame_intervals(media["property_patrol_demo"])
    providers = experiment_provider_modes(media)
    thresholds = experiment_alert_thresholds()
    scalability = [run_benchmark(n) for n in (100, 1000, 5000, 10000, 25000)]

    payload = {
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "environment": {
            "os": platform.platform(),
            "python_version": sys.version.split()[0],
            "processor": platform.processor() or "x86_64",
        },
        "frame_intervals": intervals,
        "provider_comparison": providers,
        "alert_thresholds": thresholds,
        "scalability": scalability,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = REPORTS_DIR / "experiment_results.json"
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _draw_charts(payload, REPORTS_DIR / "charts")
    return payload


if __name__ == "__main__":
    res = run_all_experiments()
    print(json.dumps(res, indent=2))
