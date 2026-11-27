# Scalability & Experimentation Report

All measurements below were recorded locally on **2026-11-26** using `.\venv\Scripts\python.exe -m scripts.run_experiments` on **Windows 11, Python 3.13.7, Intel64 Family 6 Model 154**.

## Experiment 1: Video Frame Extraction Interval Trade-Off (`property_patrol_demo.mp4`, 16s @ 10 FPS)

| Interval (s) | Extracted Frames | Extraction (ms) | Total Pipeline (s) | Avg ms/Frame | Disk (KB) | Detections | Active Scenes Covered |
|---:|---:|---:|---:|---:|---:|---:|:---:|
| 0.5 | 32 | 312.11 | 1.4619 | 45.69 | 608.91 | 24 | 3/3 |
| 1.0 | 16 | 158.64 | 0.7347 | 45.92 | 303.67 | 12 | 3/3 |
| 2.0 | 8 | 101.10 | 0.3814 | 47.67 | 151.63 | 6 | 3/3 |
| 4.0 | 4 | 56.84 | 0.2030 | 50.76 | 75.04 | 3 | 3/3 |
| 8.0 | 2 | 43.59 | 0.1095 | 54.75 | 37.08 | 2 | **2/3** |

**Finding:** Sampling at `2.0s` reduces storage and compute by **75%** compared to `0.5s` while preserving **100% (3/3)** scene recall. Increasing to `8.0s` drops recall to `2/3` by skipping a 4-second perimeter event.

## Experiment 2: Offline Vision Modes (3 Generated Security Images)

| Mode | Frames | Total Time (ms) | Avg ms/Frame | Detections | Errors | API Key Needed |
|---|---:|---:|---:|---:|---:|:---:|
| `simulation` | 3 | 11.57 | 3.86 | 4 | 0 | No |
| `opencv_heuristic` | 3 | 36.36 | 12.12 | 4 | 0 | No |

## Experiment 3: Alert Deduplication Window Sensitivity (6-Frame Burst)

| Dedup Window (s) | Raw Alerts Triggered | Stored Alerts | Alert Fatigue Reduction |
|---:|---:|---:|---:|
| 0 | 10 | 10 | 0.0% |
| 60 | 10 | 2 | 80.0% |
| 300 | 10 | 2 | 80.0% |

## Experiment 4: SQLite Frame Indexing & Query Scalability

| Frames | Batch Insert (s) | Throughput (fps) | DB Size (MB) | Desc `LIKE` (ms) | Object+Color Index (ms) | Time+Loc Index (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 0.0244 | 4,102.88 | 0.109 | 12.979 | 8.479 | 8.904 |
| 1,000 | 0.0491 | 20,349.27 | 0.379 | 13.499 | 10.038 | 11.171 |
| 5,000 | 0.1763 | 28,367.20 | 1.504 | 24.762 | 23.174 | 15.907 |
| 10,000 | 0.3299 | 30,313.35 | 2.910 | 32.278 | 37.467 | 16.484 |
| 25,000 | 2.0797 | 12,021.18 | 7.148 | 67.093 | 70.730 | 17.877 |
