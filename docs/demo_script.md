# Demo Recording & Voiceover Script (5-6 Minutes)

1. **Launch & Overview (0:00-0:50):**
   - Start the console (`streamlit run app.py`) and open **Overview** in the left navigation rail.
   - Show the 5 KPI cards, active drone unit card, and Sidebar Vision Providers panel.
   - Explain the architecture boundary: offline OpenCV heuristic and simulation modes work with zero API keys, while OpenAI, Gemini, and Ollama plug into the exact same `VisionAnalyzer` interface.
2. **Sample Data & Media Upload (0:50-2:00):**
   - Click **Video & Image Analysis** in the left sidebar.
   - Select **Run Built-in Sample Media** -> `property_patrol_demo.mp4`, set interval to `2.0s`, and click **Process Selected Sample Media**.
   - Highlight the extracted frame gallery, structured detections, latency, mode badge (`local_cv_heuristic` or `actual_vlm`), and the **one-sentence video summary**.
3. **Frame Intelligence Search (2:00-2:40):**
   - Click **Frame Intelligence**, filter by `Object Category = vehicle` and `Color = blue`, and inspect frame evidence + linked detections.
4. **Contextual Correlation & Security Alerts (2:40-3:35):**
   - Load the 6-frame scenario if needed and click **Security Alerts**, highlighting `Critical`/`High`/`Medium` severity badges, midnight gate presence (`FR-0003`), repeated blue pickup truck correlation (`FR-0001` & `FR-0004`), occurrence counters, and **Acknowledge** / **Resolve** actions.
5. **Drone Telemetry (3:35-4:05):**
   - Click **Drone Telemetry** to show battery/altitude trend lines and ingest a simulated `14%` battery checkpoint triggering a `CRITICAL` RTH alert.
6. **Grounded AI Security Analyst (4:05-4:55):**
   - Click **AI Security Analyst** and ask:
     1. *"Show all observations of blue vehicles"*
     2. *"Which frames were those?"* (multi-turn follow-up)
     3. *"Was anyone near the main gate at midnight?"*
     4. *"What happened between 12 PM and 3 PM?"*
   - Point out that every answer cites exact `frame_id`s and timestamps from SQLite without hallucination.
7. **Daily Intelligence Report, Benchmarks & QA (4:55-6:00):**
   - Click **Daily Report & Benchmarks** to show the daily report, Markdown/JSON export, and measured scalability/interval tables (up to 25,000 frames).
   - Switch to terminal and run `.\venv\Scripts\python.exe -m pytest -v` showing all 23 tests passing.
   - Conclude honestly with current limitations (attribute-based matching vs persistent Re-ID) and next steps.
