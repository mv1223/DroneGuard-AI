# AI-Assisted Development Log

This log documents the engineering workflow and verification practices used to transform DroneGuard AI from a starter prototype into a full assignment deliverable.

1. **Codebase Audit & Gap Analysis:** Inspected all existing modules, SQLite schema, sample data, and the 9 starter tests; identified missing VLM provider execution, OpenCV video extraction, multi-frame sequence correlation, duplicate alert suppression, multi-turn Q&A, and benchmark experiments.
2. **Vision Pipeline Engineering:** Designed `core/vlm_providers.py` with a unified `BaseVLMProvider` interface (`OpenAIVLMProvider`, `GeminiVLMProvider`, `OllamaVLMProvider`, `OpenCVHeuristicAnalyzer`, `SimulatedVLMProvider`) and `core/video_extractor.py` for OpenCV interval sampling.
3. **Database & Windows Reliability Fix:** Extended `database/database.py` with safe schema migrations, 14 indexes, WAL mode, and deterministic connection closing via `@contextmanager` after initial pytest runs caught Windows SQLite file-handle locking (`WinError 32`).
4. **OpenCV 5 Compatibility Fix:** Detected during initial test execution that `opencv-python-headless 5.1.0` omitted `cv2.HOGDescriptor`; added an upright silhouette fallback so local pixel analysis runs reliably across OpenCV 4.x and 5.x.
5. **Verification & Honesty Boundaries:** Executed all 22 automated pytest cases and 4 reproducible benchmark suites directly in the local environment; cloud VLM API calls were verified using mocked HTTP 429/200 responses due to no live API keys in `.env`.
