# Scalability & Experimentation Report

All measurements below were recorded locally on **2026-11-27** (`2026-11-27T15:36:52`) using `.\venv\Scripts\python.exe -m scripts.run_experiments` on **Windows 11, Python 3.13.7, Intel64 Family 6 Model 154**.

## Experiment 1: Video Frame Extraction Interval Trade-Off (`property_patrol_demo.mp4`, 16s @ 10 FPS)

| Interval (s) | Extracted Frames | Extraction (ms) | Total Pipeline (s) | Avg ms/Frame | Disk (KB) | Detections | Active Scenes Covered |
|---:|---:|---:|---:|---:|---:|---:|:---:|
| 0.5 | 32 | 633.74 | 2.2396 | 69.99 | 608.91 | 24 | 3/3 |
| 1.0 | 16 | 143.28 | 0.6876 | 42.98 | 303.67 | 12 | 3/3 |
| 2.0 | 8 | 92.15 | 0.3575 | 44.68 | 151.63 | 6 | 3/3 |
| 4.0 | 4 | 72.99 | 0.1931 | 48.28 | 75.04 | 3 | 3/3 |
| 8.0 | 2 | 41.01 | 0.1112 | 55.62 | 37.08 | 2 | **2/3** |

**Finding:** Sampling at `2.0s` reduces storage and compute by **75%** compared to `0.5s` while preserving **100% (3/3)** scene recall. Increasing to `8.0s` drops recall to `2/3` by skipping a 4-second perimeter event.

## Experiment 2: Offline Vision Modes (3 Generated Security Images)

| Mode | Frames | Total Time (ms) | Avg ms/Frame | Detections | Errors | API Key Needed |
|---|---:|---:|---:|---:|---:|:---:|
| `simulation` | 3 | 14.51 | 4.84 | 4 | 0 | No |
| `opencv_heuristic` | 3 | 32.95 | 10.98 | 4 | 0 | No |

## Experiment 3: Alert Deduplication Window Sensitivity (6-Frame Burst)

| Dedup Window (s) | Raw Alerts Triggered | Stored Alerts | Alert Fatigue Reduction |
|---:|---:|---:|---:|
| 0 | 10 | 10 | 0.0% |
| 60 | 10 | 2 | 80.0% |
| 300 | 10 | 2 | 80.0% |

## Experiment 4: SQLite Frame Indexing & Query Scalability

| Frames | Batch Insert (s) | Throughput (fps) | DB Size (MB) | Desc `LIKE` (ms) | Object+Color Index (ms) | Time+Loc Index (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 0.0282 | 3,548.55 | 0.109 | 6.301 | 4.972 | 5.923 |
| 1,000 | 0.0400 | 24,981.20 | 0.379 | 8.258 | 5.986 | 7.427 |
| 5,000 | 0.1305 | 38,326.48 | 1.504 | 13.249 | 11.026 | 9.365 |
| 10,000 | 0.2461 | 40,641.72 | 2.910 | 21.601 | 24.539 | 17.640 |
| 25,000 | 1.7783 | 14,058.14 | 7.148 | 49.029 | 65.187 | 9.258 |
