# System Architecture

## Data Flow
1. **Inputs:** Drone telemetry JSON/checkpoints, uploaded images, MP4/AVI/MOV patrol videos, or synthetic description scenarios.
2. **Media Extraction (`core/video_extractor.py`):** OpenCV samples video frames at configurable intervals, computes offset timestamps and inter-frame motion deltas, and stores JPEG evidence frames.
3. **Vision Abstraction (`core/vlm_providers.py`, `core/object_detection.py`):** `VisionAnalyzer` routes frames to `OpenAIVLMProvider`, `GeminiVLMProvider`, `OllamaVLMProvider`, `OpenCVHeuristicAnalyzer`, or `SimulatedVLMProvider` with exponential retry and explicit fallback tagging.
4. **Correlation & Alerting (`core/event_analyzer.py`, `core/alert_engine.py`, `core/pipeline.py`):** Single-frame rules and cross-frame sequence correlations (repeated vehicles, entry/exit patterns, loitering) feed prioritized alerts with configurable duplicate suppression.
5. **Indexed Persistence (`database/database.py`, `database/repository.py`):** SQLite WAL database stores `telemetry`, `frames`, `detections`, `events`, `alerts`, and `model_runs` with 14 indexes.
6. **Agent & Dashboard (`core/context_manager.py`, `agent/`, `app.py`, `ui/`):** Multi-turn grounded retrieval powers 8 LangChain-compatible tools, offline/LLM Q&A, daily reports, and a 7-view tactile Streamlit security console.
