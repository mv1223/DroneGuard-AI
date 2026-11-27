"""Dedicated page views for the DroneGuard AI Hybrid Command Center."""

from __future__ import annotations

import html
import json
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from agent.security_agent import SecurityAgent
from config import (
    CRITICAL_BATTERY_THRESHOLD,
    DB_PATH,
    DEFAULT_FRAME_INTERVAL_SECONDS,
    LOW_BATTERY_THRESHOLD,
    MAX_ALTITUDE_METERS,
    REPORTS_DIR,
    SAMPLE_MEDIA_DIR,
)
from core.object_detection import VisionAnalyzer
from core.pipeline import SecurityPipeline
from core.telemetry import generate_telemetry
from core.video_summarizer import (
    format_daily_report_markdown,
    generate_daily_intelligence_report,
    one_sentence_video_summary,
)
from database.repository import Repository
from ui.theme import page_header, severity_badge


def _ctx() -> tuple[Repository, SecurityPipeline]:
    repo = Repository(DB_PATH)
    pipeline = SecurityPipeline(repo)
    if "analyst_agent" not in st.session_state:
        st.session_state.analyst_agent = SecurityAgent(repo)
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    return repo, pipeline


def _render_kpi_cards(repo: Repository) -> None:
    counts = repo.counts()
    latest_tel = repo.get_latest_telemetry()
    bat_val = f"{latest_tel['battery_percentage']:.0f}%" if latest_tel else "N/A"
    alt_meta = f"Altitude {latest_tel['altitude']:.0f}m" if latest_tel else "No telemetry"

    st.markdown(
        f"""
        <div class="fb-kpi-grid">
            <div class="fb-kpi-card">
                <div class="fb-kpi-label">Processed Frames</div>
                <div class="fb-kpi-value">{counts['frames']}</div>
                <div class="fb-kpi-meta">SQLite indexed</div>
            </div>
            <div class="fb-kpi-card">
                <div class="fb-kpi-label">Detected Objects</div>
                <div class="fb-kpi-value">{counts['detections']}</div>
                <div class="fb-kpi-meta">Across {counts['events']} events</div>
            </div>
            <div class="fb-kpi-card">
                <div class="fb-kpi-label">Active Alerts</div>
                <div class="fb-kpi-value">{counts['active_alerts']}</div>
                <div class="fb-kpi-meta">{counts['alerts']} total logged</div>
            </div>
            <div class="fb-kpi-card">
                <div class="fb-kpi-label">Critical Alerts</div>
                <div class="fb-kpi-value" style="color:{'#DC2626' if counts['critical_alerts'] else '#141414'};">{counts['critical_alerts']}</div>
                <div class="fb-kpi-meta">Immediate triage</div>
            </div>
            <div class="fb-kpi-card">
                <div class="fb-kpi-label">Drone Battery</div>
                <div class="fb-kpi-value">{bat_val}</div>
                <div class="fb-kpi-meta">{html.escape(alt_meta)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_overview() -> None:
    repo, _ = _ctx()
    counts = repo.counts()
    page_header(
        "Command Overview",
        "Autonomous Perimeter Operations",
        "Consolidated operational view of indexed drone observations, correlated alerts, and live dock telemetry.",
        right_badge=f"INDEXED: {counts['frames']} FRAMES",
    )
    _render_kpi_cards(repo)

    frames = repo.search_frames()
    events = repo.search_events()
    latest_tel = repo.get_latest_telemetry()

    col_left, col_right = st.columns([3, 2], gap="large")
    with col_left:
        st.markdown("<div class='fb-section-label'>Recent Security Activity Timeline</div>", unsafe_allow_html=True)
        if events:
            df_events = pd.DataFrame(events)[
                ["timestamp", "frame_id", "location", "event_type", "severity", "explanation"]
            ]
            st.dataframe(
                df_events.sort_values("timestamp", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "No events indexed yet. Load the Demo Scenario from the left command rail or analyze media in Video & Image Analysis."
            )

    with col_right:
        st.markdown("<div class='fb-section-label'>Active Drone Unit</div>", unsafe_allow_html=True)
        if latest_tel:
            with st.container(border=True):
                st.markdown(
                    f"**`{latest_tel['drone_id']}`** &nbsp; "
                    f"<span class='fb-badge fb-badge-ok'>● {html.escape(str(latest_tel['flight_status']))}</span>",
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"Updated `{latest_tel['timestamp']}` · Zone: **{latest_tel['location_name']}**"
                )
                c1, c2, c3 = st.columns(3)
                c1.metric("Altitude", f"{latest_tel['altitude']:.1f} m")
                c2.metric("Battery", f"{latest_tel['battery_percentage']:.0f}%")
                c3.metric("Speed", f"{latest_tel['speed']:.1f} m/s")
                st.caption(
                    f"Coordinates: `{latest_tel['latitude']:.5f}, {latest_tel['longitude']:.5f}`"
                )
        else:
            st.info("No telemetry records present.")

        st.markdown("<div class='fb-section-label' style='margin-top:1rem;'>Observations by Zone</div>", unsafe_allow_html=True)
        if frames:
            zone_df = pd.DataFrame(frames).groupby("location").size().reset_index(name="frames")
            st.bar_chart(zone_df.set_index("location"))


def render_media_analysis() -> None:
    repo, pipeline = _ctx()
    readiness = VisionAnalyzer.available_providers()
    active_vlm = next((k for k in ("openai", "gemini", "ollama") if readiness.get(k)), "opencv_heuristic")
    page_header(
        "Vision Pipeline",
        "Video & Image Analysis",
        "Extract frames at configurable intervals via OpenCV and run structured VLM or local computer-vision analysis.",
        right_badge=f"DEFAULT PROVIDER: {active_vlm.upper()}",
    )

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        provider_choice = c1.selectbox(
            "Vision Provider",
            ["auto", "opencv_heuristic", "openai", "gemini", "ollama", "simulation"],
            index=0,
            help="'auto' selects a configured VLM API/Ollama if available, otherwise OpenCV local heuristics.",
        )
        zone_input = c2.text_input("Monitoring Zone", value="Main Gate")
        interval_sec = c3.slider(
            "Frame Interval (s)", 0.5, 10.0, float(DEFAULT_FRAME_INTERVAL_SECONDS), 0.5
        )
        max_frames_val = c4.number_input("Max Video Frames", min_value=1, max_value=120, value=20)
        base_ts_str = st.text_input(
            "Base Timestamp (ISO-8601)",
            value=datetime.now().replace(microsecond=0).isoformat(),
        )

    mode = st.radio(
        "Media Input Source",
        ["Upload Image or Video", "Run Built-in Sample Media"],
        horizontal=True,
    )

    if mode == "Upload Image or Video":
        uploaded = st.file_uploader(
            "Select an image or video asset",
            type=["jpg", "jpeg", "png", "webp", "bmp", "mp4", "avi", "mov", "mkv"],
        )
        if uploaded is not None and st.button("Start Processing Upload", type="primary"):
            suffix = Path(uploaded.name).suffix.lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.getbuffer())
                tmp_path = Path(tmp.name)

            try:
                if suffix in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
                    prog = st.progress(0, text="Extracting and analyzing video frames...")
                    out = pipeline.ingest_video(
                        video_path=tmp_path,
                        interval_seconds=float(interval_sec),
                        max_frames=int(max_frames_val),
                        base_timestamp=base_ts_str,
                        location=zone_input,
                        provider_name=provider_choice,
                        source_video_name=uploaded.name,
                        progress_callback=lambda cur, tot: prog.progress(
                            cur / max(tot, 1), text=f"Analyzed {cur}/{tot} frames"
                        ),
                    )
                    prog.empty()
                    ext = out["extraction"]
                    st.success(
                        f"Processed {ext.extracted_count} frame(s) from '{uploaded.name}' "
                        f"(duration={ext.duration_seconds}s, interval={ext.interval_seconds}s)."
                    )
                    st.info(one_sentence_video_summary(repo, uploaded.name))
                else:
                    saved_img = (
                        Path("storage/frames")
                        / f"upload_{datetime.now().strftime('%H%M%S')}_{uploaded.name}"
                    )
                    saved_img.write_bytes(tmp_path.read_bytes())
                    res = pipeline.ingest_image(
                        image_path=saved_img,
                        timestamp=base_ts_str,
                        location=zone_input,
                        provider_name=provider_choice,
                    )
                    fr = res["frame"]
                    st.success(
                        f"Processed frame {fr['frame_id']} | Mode: {fr['analysis_mode']} | Provider: {fr['model_provider']}"
                    )
                    st.write(f"**Observation:** {fr['description']}")
                    st.caption(f"Evidence: {fr['evidence']}")
            except Exception as exc:
                st.error(f"Processing error: {exc}")
    else:
        sample_files = sorted(
            [p for p in SAMPLE_MEDIA_DIR.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".mp4"}]
        )
        if not sample_files:
            st.info("No sample media files found. Click 'Generate Sample Media' in the left rail.")
        else:
            chosen_name = st.selectbox("Select sample media asset", [p.name for p in sample_files])
            chosen_path = SAMPLE_MEDIA_DIR / chosen_name
            if st.button("Process Selected Sample Media", type="primary"):
                if chosen_path.suffix.lower() == ".mp4":
                    out = pipeline.ingest_video(
                        video_path=chosen_path,
                        interval_seconds=float(interval_sec),
                        max_frames=int(max_frames_val),
                        base_timestamp=base_ts_str,
                        location=zone_input,
                        provider_name=provider_choice,
                        source_video_name=chosen_path.name,
                    )
                    st.success(
                        f"Processed {out['extraction'].extracted_count} frames from {chosen_path.name}."
                    )
                    st.info(one_sentence_video_summary(repo, chosen_path.name))
                else:
                    res = pipeline.ingest_image(
                        image_path=chosen_path,
                        timestamp=base_ts_str,
                        location=zone_input,
                        provider_name=provider_choice,
                    )
                    st.success(
                        f"Processed {res['frame']['frame_id']} ({res['frame']['analysis_mode']})."
                    )

    visual_frames = [
        f for f in repo.search_frames() if f.get("image_path") and Path(f["image_path"]).exists()
    ]
    if visual_frames:
        st.divider()
        st.markdown(f"<div class='fb-section-label'>Processed Frame Gallery ({len(visual_frames)})</div>", unsafe_allow_html=True)
        for vf in reversed(visual_frames[-8:]):
            with st.container(border=True):
                c_img, c_meta = st.columns([1, 2], gap="medium")
                with c_img:
                    st.image(vf["image_path"], use_container_width=True)
                with c_meta:
                    st.markdown(
                        f"**`{vf['frame_id']}`** · `{vf['timestamp']}` · Zone: **{vf['location']}** &nbsp; "
                        f"<span class='fb-badge fb-badge-neutral'>{html.escape(str(vf.get('analysis_mode', 'unknown')))}</span>",
                        unsafe_allow_html=True,
                    )
                    st.write(vf["description"])
                    st.caption(
                        f"Provider: `{vf.get('model_provider')}` · Activity: `{vf.get('activity')}` "
                        f"· Confidence: `{vf.get('confidence')}` · Latency: `{vf.get('processing_ms')}ms`"
                    )
                    st.caption(f"Evidence: {vf.get('evidence')}")
                    dets = repo.get_detections_for_frames([vf["frame_id"]])
                    if dets:
                        st.dataframe(
                            pd.DataFrame(dets)[["object_type", "color", "confidence", "description"]],
                            use_container_width=True,
                            hide_index=True,
                        )


def render_frame_intelligence() -> None:
    repo, _ = _ctx()
    page_header(
        "Indexed Retrieval",
        "Frame-by-Frame Intelligence",
        "Search SQLite-indexed frames across object category, color, description, perimeter zone, event type, and time window.",
    )

    with st.container(border=True):
        f1, f2, f3, f4 = st.columns(4)
        q_text = f1.text_input("Description / Evidence", placeholder="e.g. blue pickup")
        q_obj = f2.selectbox("Object Category", ["", "vehicle", "truck", "person", "activity"])
        q_color = f3.selectbox("Color", ["", "blue", "red", "black", "white", "silver", "gray", "green"])
        q_loc = f4.text_input("Location / Zone", placeholder="e.g. Main Gate")

        f5, f6, f7, f8 = st.columns(4)
        q_event = f5.selectbox(
            "Event Type",
            [
                "",
                "vehicle_observation",
                "person_detected",
                "midnight_person_presence",
                "restricted_area_presence",
                "repeated_vehicle_observation",
                "loitering_suspected",
            ],
        )
        q_video = f6.selectbox("Source Video", [""] + repo.list_source_videos())
        q_start = f7.text_input("Start Timestamp (ISO)", placeholder="2026-11-27T00:00:00")
        q_end = f8.text_input("End Timestamp (ISO)", placeholder="2026-11-27T23:59:59")

    results = repo.search_frames(
        query=q_text or None,
        object_type=q_obj or None,
        color=q_color or None,
        location=q_loc or None,
        event_type=q_event or None,
        source_video=q_video or None,
        start=q_start or None,
        end=q_end or None,
    )
    st.caption(f"Matched **{len(results)}** indexed frame(s)")
    if results:
        display_cols = [
            "frame_id",
            "timestamp",
            "location",
            "activity",
            "analysis_mode",
            "model_provider",
            "source_video",
            "description",
        ]
        st.dataframe(pd.DataFrame(results)[display_cols], use_container_width=True, hide_index=True)

        selected_fid = st.selectbox("Inspect Frame Evidence", [r["frame_id"] for r in results])
        detail = repo.get_frame_details(selected_fid)
        if detail:
            with st.container(border=True):
                dc1, dc2 = st.columns([1, 2], gap="medium")
                with dc1:
                    if detail.get("image_path") and Path(detail["image_path"]).exists():
                        st.image(detail["image_path"], use_container_width=True)
                    else:
                        st.caption("Text-simulated frame (no image file attached).")
                with dc2:
                    st.markdown(
                        f"**`{detail['frame_id']}`** · `{detail['timestamp']}` · **{detail['location']}**"
                    )
                    st.write(detail["description"])
                    st.caption(f"Evidence: {detail.get('evidence')}")
                    if detail["detections"]:
                        st.write("**Detections:**", detail["detections"])
                    if detail["events"]:
                        st.write("**Linked Events:**", detail["events"])


def render_security_alerts() -> None:
    repo, _ = _ctx()
    alerts_all = repo.list_alerts()
    open_count = sum(1 for a in alerts_all if a.get("status", "open") != "resolved")
    page_header(
        "Threat Triage",
        "Prioritized Security Alerts",
        "Manage Critical, High, Medium, and Low alerts with duplicate suppression tracking and linked frame evidence.",
        right_badge=f"UNRESOLVED: {open_count}",
    )

    ac1, ac2 = st.columns(2)
    sev_filter = ac1.selectbox("Filter by Severity", ["", "critical", "high", "medium", "low"])
    status_filter = ac2.selectbox("Filter by Status", ["", "open", "acknowledged", "resolved"])

    filtered_alerts = repo.list_alerts(
        severity=sev_filter or None,
        status=status_filter or None,
    )
    if filtered_alerts:
        for a in filtered_alerts:
            status = a.get("status", "open")
            with st.container(border=True):
                top1, top2 = st.columns([4, 1], gap="medium")
                with top1:
                    st.markdown(
                        f"{severity_badge(a['severity'])} &nbsp; **`{a['alert_type']}`** &nbsp; "
                        f"<span class='fb-badge fb-badge-neutral'>{html.escape(status)}</span> &nbsp; "
                        f"<span class='mono' style='font-size:0.76rem;color:#525866;'>Occurrences: {a.get('occurrence_count', 1)}</span>",
                        unsafe_allow_html=True,
                    )
                    st.write(a["message"])
                    st.caption(
                        f"First seen: `{a['timestamp']}` · Last seen: `{a.get('last_seen_timestamp') or a['timestamp']}` "
                        f"· Frame: `{a.get('frame_id') or 'telemetry'}`"
                    )
                    st.caption(f"Recommended action: {a['recommended_action']}")
                with top2:
                    if status == "open" and st.button(
                        "Acknowledge", key=f"ack_{a['alert_id']}", use_container_width=True
                    ):
                        repo.update_alert_status(a["alert_id"], "acknowledged")
                        st.rerun()
                    if status != "resolved" and st.button(
                        "Resolve", key=f"res_{a['alert_id']}", type="primary", use_container_width=True
                    ):
                        repo.update_alert_status(a["alert_id"], "resolved")
                        st.rerun()
    else:
        st.info("No alerts match the selected filter.")


def render_drone_telemetry() -> None:
    repo, pipeline = _ctx()
    tel_rows = repo.list_telemetry(limit=500)
    latest = tel_rows[-1] if tel_rows else None
    page_header(
        "Fleet Health",
        "Drone Telemetry & Safety",
        "Track GPS coordinates, altitude safety envelopes, battery thresholds, and flight states.",
        right_badge=f"UNIT: {latest['drone_id']}" if latest else "NO TELEMETRY",
    )

    if tel_rows and latest:
        t_df = pd.DataFrame(tel_rows)
        tc1, tc2, tc3, tc4 = st.columns(4)
        tc1.metric("Drone ID", latest["drone_id"])
        tc2.metric("Flight Status", latest["flight_status"])
        tc3.metric("Altitude (m)", f"{latest['altitude']:.1f}", delta=f"Limit {MAX_ALTITUDE_METERS:.0f}m")
        tc4.metric("Battery (%)", f"{latest['battery_percentage']:.1f}", delta=f"Warn <{LOW_BATTERY_THRESHOLD}%")

        if latest["battery_percentage"] < CRITICAL_BATTERY_THRESHOLD:
            st.error(f"CRITICAL BATTERY: {latest['battery_percentage']}% (< {CRITICAL_BATTERY_THRESHOLD}%)")
        elif latest["battery_percentage"] < LOW_BATTERY_THRESHOLD:
            st.warning(f"LOW BATTERY: {latest['battery_percentage']}% (< {LOW_BATTERY_THRESHOLD}%)")
        if latest["altitude"] > MAX_ALTITUDE_METERS:
            st.error(f"ALTITUDE THRESHOLD EXCEEDED: {latest['altitude']}m (> {MAX_ALTITUDE_METERS}m)")

        ch1, ch2 = st.columns(2, gap="large")
        with ch1:
            st.markdown("<div class='fb-section-label'>Battery Percentage Trend</div>", unsafe_allow_html=True)
            st.line_chart(t_df.set_index("timestamp")[["battery_percentage"]])
        with ch2:
            st.markdown("<div class='fb-section-label'>Altitude Profile (m)</div>", unsafe_allow_html=True)
            st.line_chart(t_df.set_index("timestamp")[["altitude"]])

        st.markdown("<div class='fb-section-label'>Telemetry Log</div>", unsafe_allow_html=True)
        st.dataframe(t_df, use_container_width=True, hide_index=True)
    else:
        st.info("No telemetry logged yet.")

    with st.expander("Simulate & Ingest Telemetry Checkpoint"):
        sc1, sc2, sc3 = st.columns(3)
        sim_loc = sc1.text_input("Zone", value="Main Gate", key="tel_zone")
        sim_bat = sc2.slider("Battery %", 0, 100, 14)
        sim_alt = sc3.slider("Altitude (m)", 0, 120, 25)
        if st.button("Ingest Telemetry Point", type="primary"):
            row = generate_telemetry(location=sim_loc, battery=sim_bat, altitude=sim_alt).to_dict()
            _, generated_alerts = pipeline.ingest_telemetry(row)
            st.success(f"Logged telemetry ({len(generated_alerts)} safety alert(s) triggered).")
            st.rerun()


def render_ai_analyst() -> None:
    repo, _ = _ctx()
    agent = st.session_state.analyst_agent
    page_header(
        "Conversational Retrieval",
        "AI Security Analyst",
        "Ask natural-language and multi-turn follow-up questions grounded directly in indexed SQLite records.",
        right_badge=f"MODE: {agent.last_mode.upper()}",
    )

    quick_prompts = [
        "How many vehicles were detected today?",
        "Show all observations of blue vehicles",
        "Was anyone near the main gate at midnight?",
        "Did the same vehicle appear more than once?",
        "What happened between 12 PM and 3 PM?",
        "Which security events require attention?",
        "Summarize today's drone activity",
    ]
    q_cols = st.columns(4)
    chosen_quick = None
    for idx, qp in enumerate(quick_prompts):
        if q_cols[idx % 4].button(qp, key=f"qp_{idx}", use_container_width=True):
            chosen_quick = qp

    st.divider()
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    user_q = st.chat_input("Ask about detections, time windows, alerts, or follow up on prior frame IDs...")
    active_q = chosen_quick or user_q
    if active_q:
        st.session_state.chat_messages.append({"role": "user", "content": active_q})
        res = agent.ask_structured(active_q)
        formatted = (
            f"{res['answer']}\n\n"
            f"<div class='mono' style='font-size:0.75rem;color:#525866;margin-top:6px;'>"
            f"Mode: {html.escape(str(res['mode']))} · Cited frames: {html.escape(str(res['cited_frame_ids'] or 'summary'))}"
            f"</div>"
        )
        st.session_state.chat_messages.append({"role": "assistant", "content": formatted})
        st.rerun()


def render_daily_report() -> None:
    repo, _ = _ctx()
    page_header(
        "Reporting & Benchmarks",
        "Daily Intelligence Report",
        "Export structured security summaries and inspect measured SQLite scalability and interval trade-off results.",
    )

    rep = generate_daily_intelligence_report(repo)
    md_report = format_daily_report_markdown(rep)
    with st.container(border=True):
        st.markdown(md_report)

    dl1, dl2 = st.columns(2)
    dl1.download_button(
        "Download Markdown Report",
        data=md_report,
        file_name="droneguard_daily_report.md",
        mime="text/markdown",
        use_container_width=True,
    )
    dl2.download_button(
        "Download JSON Report",
        data=json.dumps(rep, indent=2, default=str),
        file_name="droneguard_daily_report.json",
        mime="application/json",
        use_container_width=True,
    )

    st.divider()
    st.markdown("<div class='fb-section-label'>Measured Benchmark & Experiment Results</div>", unsafe_allow_html=True)
    bench_file = REPORTS_DIR / "experiment_results.json"
    if bench_file.exists():
        bench = json.loads(bench_file.read_text(encoding="utf-8"))
        st.caption(
            f"Recorded at `{bench.get('generated_at')}` · Python `{bench.get('environment', {}).get('python_version')}`"
        )
        if bench.get("scalability"):
            st.write("**SQLite Scalability Benchmark (100 to 25,000 frames)**")
            st.dataframe(pd.DataFrame(bench["scalability"]), use_container_width=True, hide_index=True)
        if bench.get("frame_intervals"):
            st.write("**Video Frame Interval Trade-Off Experiment**")
            st.dataframe(pd.DataFrame(bench["frame_intervals"]), use_container_width=True, hide_index=True)
        if bench.get("alert_thresholds"):
            st.write("**Alert Deduplication Window Sensitivity**")
            st.dataframe(pd.DataFrame(bench["alert_thresholds"]), use_container_width=True, hide_index=True)
    else:
        st.info("Run `python -m scripts.run_experiments` to generate benchmark measurements.")
