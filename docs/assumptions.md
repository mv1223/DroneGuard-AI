# Assumptions and Limitations

1. **Synthetic Sample Media & Scenarios:** Included sample images, `property_patrol_demo.mp4`, `sample_frames.json`, and `sample_telemetry.json` are synthetic test artifacts created for reproducible evaluation.
2. **Naive Local Timestamps:** Demo timestamps use ISO-8601 local timestamps; production systems should normalize to UTC with explicit timezone offsets.
3. **Attribute-Based Correlation (No Persistent Re-ID):** `repeated_vehicle_observation` and `loitering_suspected` correlate objects across timestamps using object category, color, and zone/time windows. The prototype does not perform license-plate OCR, facial recognition, or persistent multi-object tracking (ByteTrack/DeepSORT).
4. **Local OpenCV Heuristic Scope:** When no cloud/Ollama VLM key is configured, `OpenCVHeuristicAnalyzer` inspects pixel luminance, HSV color contours, and silhouette/motion cues rather than semantic scene understanding.
5. **Cloud VLM Verification Boundary:** Cloud VLM adapters (`OpenAIVLMProvider`, `GeminiVLMProvider`, `OllamaVLMProvider`) were verified via mocked HTTP/429 retry unit tests because no live API key was present in the local `.env`.
6. **Production Hardening:** Live deployment requires RBAC authentication, TLS, encrypted object storage for media, asynchronous message queues for video ingest, and external paging/webhook alert delivery.
