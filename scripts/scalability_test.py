"""Reproducible SQLite ingestion & multi-facet query scalability benchmark."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from database.repository import Repository


def run_benchmark(size: int) -> dict:
    with tempfile.TemporaryDirectory() as td:
        db_file = Path(td) / "bench.db"
        repo = Repository(db_file)

        frames = []
        for i in range(size):
            hr = (12 + (i // 3600)) % 24
            mn = (i // 60) % 60
            sc = i % 60
            ts = f"2026-11-27T{hr:02d}:{mn:02d}:{sc:02d}"
            is_blue = (i % 10 == 0)
            loc = "Main Gate" if i % 3 == 0 else ("Garage" if i % 3 == 1 else "Parking Area")
            frames.append(
                {
                    "frame_id": f"BENCH-{i:06d}",
                    "timestamp": ts,
                    "description": f"{'Blue pickup truck' if is_blue else 'Perimeter clear'} at {loc}",
                    "location": loc,
                    "source_video": "patrol_bench.mp4",
                    "analysis_mode": "simulation",
                    "model_provider": "deterministic-simulation",
                    "detections": (
                        [{"object_type": "truck", "color": "blue", "confidence": 0.85, "description": "Blue truck"}]
                        if is_blue
                        else []
                    ),
                }
            )

        t0 = time.perf_counter()
        repo.add_frames_batch(frames)
        insert_s = time.perf_counter() - t0

        q1_start = time.perf_counter()
        desc_hits = repo.search_frames(query="Blue pickup")
        q1_ms = (time.perf_counter() - q1_start) * 1000

        q2_start = time.perf_counter()
        obj_hits = repo.search_frames(object_type="truck", color="blue")
        q2_ms = (time.perf_counter() - q2_start) * 1000

        q3_start = time.perf_counter()
        range_hits = repo.search_frames(
            location="Main Gate",
            start="2026-11-27T12:00:00",
            end="2026-11-27T12:30:00",
        )
        q3_ms = (time.perf_counter() - q3_start) * 1000

        db_mb = round(os.path.getsize(db_file) / (1024 * 1024), 3)
        return {
            "frames": size,
            "insert_seconds": round(insert_s, 4),
            "frames_per_second": round(size / max(insert_s, 1e-6), 2),
            "db_size_mb": db_mb,
            "query_description_ms": round(q1_ms, 3),
            "query_object_color_ms": round(q2_ms, 3),
            "query_time_location_ms": round(q3_ms, 3),
            "matched_blue_trucks": len(obj_hits),
            "matched_time_loc": len(range_hits),
            "matched_desc": len(desc_hits),
        }


if __name__ == "__main__":
    for n in (100, 1000, 5000, 10000):
        print(run_benchmark(n))
