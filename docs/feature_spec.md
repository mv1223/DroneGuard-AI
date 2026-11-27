# Feature Specification

## Value Proposition
DroneGuard AI automates perimeter security analysis for docked drone operations by converting video/image feeds and telemetry into indexed, queryable intelligence, correlated security alerts, and operator-ready Q&A.

## Functional Requirements
- **FR1 — Media & Telemetry Ingestion:** Validate and ingest drone telemetry plus uploaded images (`.jpg`, `.png`, `.webp`) and videos (`.mp4`, `.avi`, `.mov`) with configurable OpenCV frame sampling intervals.
- **FR2 — Structured Vision Analysis:** Extract structured frame observations (`frame_id`, `timestamp`, `detected_objects`, `activity`, `location`, `confidence`, `evidence`, `provider`, `analysis_mode`) with clear separation between cloud/local VLM inference, local OpenCV heuristics, and simulation.
- **FR3 — Temporal Event Correlation & Alerting:** Detect single-frame and multi-frame events (midnight person presence, restricted-area intrusion, repeated vehicle sightings, loitering windows, critical/low battery, altitude violations) with `Critical/High/Medium/Low` prioritization and time-window duplicate suppression.
- **FR4 — Frame-by-Frame Indexing & Search:** Persist and query frames by text description, object category, color, timestamp range, location/zone, event type, source video, and analysis mode.
- **FR5 — Context-Aware Security Analyst Agent:** Answer operator queries and multi-turn follow-ups strictly from indexed SQLite records, with optional LLM synthesis and LangChain-compatible tools.
- **FR6 — Summarization & Reporting:** Generate one-sentence video summaries, daily intelligence reports, and exportable Markdown/JSON briefs.

## Non-Functional Requirements
- **Reliability:** Graceful handling of missing API keys, HTTP 429 rate limits, corrupt uploads, and Windows SQLite connection lifecycle management.
- **Transparency:** Simulated and heuristic results are explicitly tagged and never misrepresented as cloud VLM detections.
- **Scalability:** WAL-mode SQLite with covering indexes and batch transactions supporting 25,000+ indexed frames with sub-75ms search latency.
- **Security:** Environment-variable credentials (`.env`), parameterized SQL, and local-first media handling.
