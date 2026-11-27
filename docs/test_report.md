# Automated Test Report

**Execution Date:** 2026-11-27  
**Environment:** Windows 11, Python 3.13.7 (`pytest 9.2.0`)  
**Command:** `.\venv\Scripts\python.exe -m pytest -v`  
**Result:** **23 passed, 0 failed in 14.32s**

| Test Module & Case | Purpose | Outcome |
|---|---|---|
| `test_agent::test_agent_handles_empty_database` | Verify graceful empty-DB guidance | PASSED |
| `test_agent::test_agent_queries_and_followup_context` | Multi-turn blue vehicle, follow-up frames, midnight gate, repeated vehicle, 12–3 PM window, daily summary | PASSED |
| `test_agent::test_agent_llm_mode_with_mock_and_fallback` | Missing API key fallback + mocked OpenAI grounded synthesis | PASSED |
| `test_agent::test_one_sentence_video_summary` | Evidence-grounded one-sentence video summary | PASSED |
| `test_alerts::test_low_and_critical_battery_and_altitude_alerts` | Medium/Critical battery & High/Critical altitude alerts | PASSED |
| `test_alerts::test_midnight_and_restricted_zone_alerts` | Night person & restricted zone alerting | PASSED |
| `test_alerts::test_repeated_vehicle_and_loitering_correlation` | Cross-frame repeated vehicle, entry/exit, and loitering correlation | PASSED |
| `test_alerts::test_duplicate_alert_suppression_and_status_updates` | Time-window alert deduplication + open/ack/resolved lifecycle | PASSED |
| `test_database::test_frame_persistence_and_multi_facet_search` | Search by description, object category, color, source video, time range | PASSED |
| `test_database::test_event_search_and_indexes_exist` | Event search + SQLite index creation verification | PASSED |
| `test_integration::test_demo_pipeline_populates_database` | Full demo pipeline end-to-end persistence | PASSED |
| `test_internal_workflows::test_full_internal_workflows_end_to_end` | End-to-end telemetry, image, video, search, alert triage, agent follow-up, and daily report verification | PASSED |
| `test_scalability_smoke::test_scalability_1000_frames_benchmark` | 1,000-frame batch ingest and <1s indexed query check | PASSED |
| `test_telemetry::test_generate_telemetry_valid` | Valid telemetry generation & schema validation | PASSED |
| `test_telemetry::test_invalid_battery_rejected` | Reject battery > 100% | PASSED |
| `test_telemetry::test_missing_field_rejected` | Reject incomplete telemetry dictionary | PASSED |
| `test_video_and_vlm::test_video_frame_extraction_intervals` | OpenCV frame extraction at 2.0s & 4.0s intervals | PASSED |
| `test_video_and_vlm::test_opencv_heuristic_analyzes_generated_images` | Offline OpenCV heuristic detection on generated truck image | PASSED |
| `test_video_and_vlm::test_invalid_media_files_raise_value_error` | Corrupt image and empty MP4 error handling | PASSED |
| `test_video_and_vlm::test_missing_api_key_graceful_fallback` | Missing `OPENAI_API_KEY` error + `local_cv_fallback` recovery | PASSED |
| `test_video_and_vlm::test_mocked_openai_vlm_and_rate_limit_retry` | Mocked HTTP 429 retry + structured OpenAI JSON parsing | PASSED |
| `test_video_and_vlm::test_mocked_gemini_and_ollama_providers` | Mocked Gemini & Ollama VLM provider structured outputs | PASSED |
| `test_video_and_vlm::test_frame_processor_video_end_to_end` | Full video extraction + frame processing pipeline | PASSED |
