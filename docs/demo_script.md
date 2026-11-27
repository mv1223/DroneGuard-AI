# Demo Recording & Voiceover Script (5-7 Minutes)

1. **Launch & Overview (0:00–0:45):**
   - Start the dashboard (`streamlit run app.py`) and show the 5 KPI metrics and Sidebar Provider Readiness panel.
   - Explain the architecture boundary: offline OpenCV heuristic & simulation modes work with zero keys, while OpenAI/Gemini/Ollama plug into the exact same `VisionAnalyzer` interface.
2. **Sample Data & Media Upload (0:45–2:00):**
   - Open **Tab 2 (Video & Image Analysis)**, upload or select `sample_media/property_patrol_demo.mp4`, set interval to `2.0s`, choose `opencv_heuristic` (or `openai` if configured), and click **Process**.
   - Highlight the extracted frames gallery, structured detections, latency, mode badge (`local_cv_heuristic` or `actual_vlm`), and the **one-sentence video summary**.
3. **Frame Intelligence Search (2:00–2:45):**
   - Switch to **Tab 3 (Frame Intelligence)**, filter by `Color = blue` and `Object Category = vehicle`, and inspect frame evidence + linked detections.
4. **Contextual Correlation & Security Alerts (2:45–3:45):**
   - Load the 6-frame scenario or show **Tab 4 (Security Alerts)**, highlighting `Critical`/`High`/`Medium` severity tiers, midnight gate presence (`FR-0003`), repeated blue pickup truck correlation (`FR-0001` & `FR-0004`), duplicate-alert occurrence counters, and Acknowledge/Resolve actions.
5. **Drone Telemetry (3:45–4:15):**
   - Open **Tab 5 (Drone Telemetry)** to show battery/altitude trend lines and ingest a simulated `14%` battery checkpoint triggering a `CRITICAL` RTH alert.
6. **Grounded AI Security Analyst (4:15–5:15):**
   - Open **Tab 6 (AI Security Analyst)** and ask:
     1. *"Show all observations of blue vehicles"*
     2. *"Which frames were those?"* (multi-turn follow-up)
     3. *"Was anyone near the main gate at midnight?"*
     4. *"What happened between 12 PM and 3 PM?"*
   - Point out that every answer cites exact `frame_id`s and timestamps from SQLite without hallucination.
7. **Daily Intelligence Report, Benchmarks & QA (5:15–6:30):**
   - Open **Tab 7** to show the daily report, Markdown/JSON export, and the measured scalability/interval tables (up to 25,000 frames).
   - Switch to terminal and run `.\venv\Scripts\python.exe -m pytest -v` showing all 22 tests passing.
   - Conclude honestly with current limitations (attribute-based matching vs persistent Re-ID) and production roadmap.
