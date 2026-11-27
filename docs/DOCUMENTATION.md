# DroneGuard AI — Complete Project Documentation

## 1. System Overview
**DroneGuard AI** is a modular drone perimeter security analysis and monitoring system. It processes drone telemetry and visual feeds (images and MP4/AVI/MOV videos), indexes frame-by-frame observations in SQLite, correlates multi-frame security events, generates deduplicated prioritized alerts, and provides a database-grounded Security Analyst Agent inside a 7-view Streamlit console.

---

## 2. Repository Structure

```text
DroneGuard-AI/
├── app.py                         # Streamlit entrypoint & sidebar module router
├── config.py                      # Environment-driven thresholds, paths & provider config
├── requirements.txt               # Python dependencies
├── .env.example                   # Sample environment variables template
├── .streamlit/config.toml         # Tactile Paper theme defaults
├── ui/
│   ├── theme.py                   # Neo-brutalist paper CSS, Space Grotesk + Space Mono fonts
│   └── views.py                   # 7 separate page renderers
├── core/
│   ├── logger.py                  # Console + rotating file logger
│   ├── schemas.py                 # Dataclasses: Telemetry, DetectionItem, VisionAnalysisResult, FrameObservation
│   ├── telemetry.py               # Telemetry generator & validation rules
│   ├── video_extractor.py         # OpenCV interval frame extraction & motion scoring
│   ├── vlm_providers.py           # OpenAI, Gemini, Ollama, OpenCV heuristic & simulation providers
│   ├── object_detection.py        # VisionAnalyzer abstraction + SimulatedDetector
│   ├── frame_processor.py         # Image, video, and description processing orchestrator
│   ├── event_analyzer.py          # Single-frame classifier & cross-frame sequence correlator
│   ├── alert_engine.py            # 4-tier security & safety alert rules
│   ├── pipeline.py                # End-to-end SecurityPipeline (ingest -> index -> correlate -> alert)
│   ├── context_manager.py         # Multi-turn state & natural-language time-window SQLite retrieval
│   └── video_summarizer.py        # One-sentence video summary & Markdown/JSON daily reports
├── agent/
│   ├── agent_tools.py             # 8 LangChain-compatible @tool definitions
│   └── security_agent.py          # Grounded offline / optional LLM SecurityAgent
├── database/
│   ├── database.py                # SQLite schema, WAL mode, safe migrations, 14 indexes
│   └── repository.py              # Parameterized CRUD, search, and alert deduplication
├── scripts/
│   ├── generate_sample_media.py   # Synthetic OpenCV test images & 16s patrol MP4 generator
│   ├── generate_sample_data.py    # 6-frame demo scenario loader
│   ├── scalability_test.py        # SQLite throughput & query latency micro-benchmark
│   ├── run_experiments.py         # Reproducible 4-experiment suite + chart generator
│   └── generate_pdf_report.py     # Pure-Python technical PDF report builder
├── docs/                          # Detailed specs, architecture, DB design, test & benchmark reports
├── reports/                       # final_report.pdf, experiment_results.json, and PNG charts
├── sample_media/                  # Generated test images and patrol MP4 video
└── tests/                         # 23 automated pytest unit & end-to-end tests
```

---

## 3. Core Pipelines & Technical Design

### 3.1 Vision-Language Model (VLM) Pipeline
- **Provider Abstraction:** `BaseVLMProvider` in `core/vlm_providers.py` defines `is_configured()` and `analyze_image()`.
- **Supported Providers:**
  1. `OpenAIVLMProvider` (`openai:gpt-4o-mini`) — HTTPS Vision API with strict JSON response schema and HTTP 429/5xx exponential retry.
  2. `GeminiVLMProvider` (`gemini:gemini-2.0-flash`) — Google Generative Language Vision REST API (`responseMimeType: application/json`).
  3. `OllamaVLMProvider` (`ollama:llava`) — Local open-weight VLM endpoint.
  4. `OpenCVHeuristicAnalyzer` (`opencv-motion-hog-heuristic`) — Offline pixel analysis (mean luminance, HSV color-contour vehicle regions, upright silhouette/HOG person detection, inter-frame motion delta).
  5. `SimulatedVLMProvider` (`deterministic-simulation`) — Keyword-based deterministic extraction for synthetic text scenarios and explicit fallbacks.
- **Transparency Rule:** Every observation stores both `model_provider` and `analysis_mode` (`actual_vlm`, `local_cv_heuristic`, `simulation`, `local_cv_fallback`, `simulation_fallback`).

### 3.2 Cross-Frame Correlation & Alert Rules
- **Single-Frame Events (`classify_events`):** `vehicle_observation`, `person_detected`, `restricted_area_presence`, `midnight_person_presence` (`NIGHT_START_HOUR=0` to `NIGHT_END_HOUR=5`).
- **Sequence Correlation (`correlate_sequence_events`):**
  - `repeated_vehicle_observation`: Matches vehicles with identical category + color across timestamps/zones.
  - `vehicle_entry_exit_pattern`: Tracks vehicle appearances between gate/entry and interior zones (garage/parking/dock).
  - `loitering_suspected`: Fires when `>= LOITERING_MIN_OBSERVATIONS` person detections occur in the same zone spanning `>= LOITERING_SECONDS`.
- **Telemetry Rules (`telemetry_alerts`):**
  - `critical_battery` (`< 15%`, severity `critical`), `low_battery` (`< 20%`, severity `medium`).
  - `altitude_violation` (`> 60m` `high`, `> 90m` `critical`).
- **Deduplication:** `Repository.add_alert()` merges repeated un-resolved alerts of the same type/target within `DUPLICATE_ALERT_WINDOW_SECONDS` (`300s`) by incrementing `occurrence_count`.

### 3.3 SQLite Database Schema & Indexing
- Tables: `telemetry`, `frames`, `detections`, `events`, `alerts`, `model_runs`.
- Mode: `PRAGMA journal_mode = WAL`, `PRAGMA foreign_keys = ON`, deterministic connection closing via `@contextmanager`, and automatic `ALTER TABLE` column migrations.
- 14 indexes across `frames(timestamp, location, source_video, analysis_mode)`, `detections(object_type, color, frame_id)`, `events(timestamp, event_type, severity, frame_id)`, `alerts(timestamp, severity, status)`, and `telemetry(timestamp, drone_id)`.

### 3.4 Grounded Security Analyst Agent
- `ContextManager` parses time windows (`"between 12 PM and 3 PM"`, `"midnight"`), object types, colors, and locations, and retains multi-turn state for follow-ups (`"Which frames were those?"`).
- `agent/agent_tools.py` exposes 8 LangChain-compatible `@tool` functions.
- `SecurityAgent` runs deterministically offline from SQLite or uses OpenAI/Gemini/Ollama strictly to summarize retrieved database JSON with mandatory `frame_id` and `timestamp` citations.

---

## 4. Setup, Execution & Testing (Windows)

```powershell
# Setup
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

# Run Dashboard
.\venv\Scripts\python.exe -m streamlit run app.py

# Run All 23 Automated Tests
.\venv\Scripts\python.exe -m pytest -v

# Run Reproducible Experiments & Regenerate PDF Report
.\venv\Scripts\python.exe -m scripts.run_experiments
.\venv\Scripts\python.exe -m scripts.generate_pdf_report
```

---

## 5. Additional Documentation Files
- [README.md](file:///c:/Users/mohan/OneDrive/Desktop/DroneGuard-AI/README.md) — Quick-start & configuration guide
- [docs/feature_spec.md](file:///c:/Users/mohan/OneDrive/Desktop/DroneGuard-AI/docs/feature_spec.md) — Functional & non-functional specification
- [docs/architecture.md](file:///c:/Users/mohan/OneDrive/Desktop/DroneGuard-AI/docs/architecture.md) & [docs/architecture_diagram.mmd](file:///c:/Users/mohan/OneDrive/Desktop/DroneGuard-AI/docs/architecture_diagram.mmd) — Architecture & Mermaid flowchart
- [docs/database_design.md](file:///c:/Users/mohan/OneDrive/Desktop/DroneGuard-AI/docs/database_design.md) — Relational schema & indexing strategy
- [docs/scalability_report.md](file:///c:/Users/mohan/OneDrive/Desktop/DroneGuard-AI/docs/scalability_report.md) — Measured experiment & benchmark results
- [docs/test_report.md](file:///c:/Users/mohan/OneDrive/Desktop/DroneGuard-AI/docs/test_report.md) — 23/23 automated test results
- [docs/assumptions.md](file:///c:/Users/mohan/OneDrive/Desktop/DroneGuard-AI/docs/assumptions.md) — Assumptions & known limitations
- [docs/demo_script.md](file:///c:/Users/mohan/OneDrive/Desktop/DroneGuard-AI/docs/demo_script.md) — Screen-recording voiceover script
- [reports/final_report.pdf](file:///c:/Users/mohan/OneDrive/Desktop/DroneGuard-AI/reports/final_report.pdf) — Full formatted PDF technical report
