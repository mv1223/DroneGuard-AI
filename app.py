"""DroneGuard AI — Tactile Paper Security Analyst Console."""

from __future__ import annotations

import streamlit as st

from agent.security_agent import SecurityAgent
from config import APP_NAME, APP_VERSION, DB_PATH
from core.object_detection import VisionAnalyzer
from database.repository import Repository
from scripts.generate_sample_data import load_demo
from scripts.generate_sample_media import generate_sample_media
from ui.theme import inject_theme
from ui.views import (
    render_ai_analyst,
    render_daily_report,
    render_drone_telemetry,
    render_frame_intelligence,
    render_media_analysis,
    render_overview,
    render_security_alerts,
)

st.set_page_config(
    page_title=f"{APP_NAME} — Security Analyst Console",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()

repo = Repository(DB_PATH)
if "auto_seeded" not in st.session_state:
    st.session_state.auto_seeded = True
    if repo.counts()["frames"] == 0:
        load_demo(reset=False)
if "analyst_agent" not in st.session_state:
    st.session_state.analyst_agent = SecurityAgent(repo)
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

NAV_ITEMS = [
    ("overview", "Overview", render_overview),
    ("media", "Video & Image Analysis", render_media_analysis),
    ("frames", "Frame Intelligence", render_frame_intelligence),
    ("alerts", "Security Alerts", render_security_alerts),
    ("telemetry", "Drone Telemetry", render_drone_telemetry),
    ("analyst", "AI Security Analyst", render_ai_analyst),
    ("reports", "Daily Report & Benchmarks", render_daily_report),
]

if "active_page" not in st.session_state:
    qp = st.query_params.get("view", "overview")
    valid_keys = {k for k, _, _ in NAV_ITEMS}
    st.session_state.active_page = qp if qp in valid_keys else "overview"

with st.sidebar:
    # Tactile geometric DroneGuard brand mark + crisp wordmark
    st.markdown(
        f"""
        <div style="padding: 4px 2px 10px 2px;">
            <div style="display:flex; align-items:center; gap:9px; margin-bottom:8px;">
                <svg width="26" height="26" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect x="2" y="2" width="28" height="28" fill="#FBF9F2" stroke="#141414" stroke-width="2.2"/>
                    <path d="M9 16L16 9L23 16L16 23L9 16Z" stroke="#057A36" stroke-width="2.2"/>
                    <rect x="14" y="14" width="4" height="4" fill="#141414"/>
                </svg>
                <span class="fb-brand-title" style="font-size:1.22rem;font-weight:700;letter-spacing:-0.02em;color:#141414;">
                    DroneGuard AI
                </span>
            </div>
            <div style="font-size:0.70rem;letter-spacing:0.10em;color:#5C5B55;text-transform:uppercase;">
                Perimeter Console · v{APP_VERSION}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown(
        "<div style='font-size:0.68rem;letter-spacing:0.12em;color:#5C5B55;text-transform:uppercase;margin:0 0 6px 2px;font-weight:700;'>Modules</div>",
        unsafe_allow_html=True,
    )
    for key, label, _ in NAV_ITEMS:
        is_active = st.session_state.active_page == key
        if st.button(
            label,
            key=f"nav_{key}",
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            st.session_state.active_page = key
            st.query_params["view"] = key
            st.rerun()

    st.divider()
    st.markdown(
        "<div style='font-size:0.68rem;letter-spacing:0.12em;color:#5C5B55;text-transform:uppercase;margin:0 0 6px 2px;font-weight:700;'>Controls</div>",
        unsafe_allow_html=True,
    )
    if st.button("Load Demo Scenario", key="action_load_demo", use_container_width=True, type="primary"):
        load_demo(reset=True)
        st.session_state.analyst_agent = SecurityAgent(repo)
        st.session_state.chat_messages = []
        st.success("Demo scenario loaded.")
        st.rerun()

    if st.button("Generate Sample Media", key="action_gen_media", use_container_width=True):
        created = generate_sample_media()
        st.success(f"Generated {len(created)} sample assets.")

    if st.button("Clear Database", key="action_clear_db", use_container_width=True):
        repo.clear_all()
        st.session_state.analyst_agent = SecurityAgent(repo)
        st.session_state.chat_messages = []
        st.info("Database cleared.")
        st.rerun()

    st.divider()
    st.markdown(
        "<div style='font-size:0.68rem;letter-spacing:0.12em;color:#5C5B55;text-transform:uppercase;margin:0 0 6px 2px;font-weight:700;'>Vision Providers</div>",
        unsafe_allow_html=True,
    )
    for pname, ready in VisionAnalyzer.available_providers().items():
        sq_cls = "fb-sq-ok" if ready else "fb-sq-idle"
        state_lbl = "Ready" if ready else "Idle"
        st.markdown(
            f"<div class='fb-prov-row'><span><span class='{sq_cls}'></span>{pname}</span><span>{state_lbl}</span></div>",
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown(
        f"<div style='font-size:0.70rem;color:#5C5B55;'>Store: {DB_PATH.name}</div>",
        unsafe_allow_html=True,
    )

active_renderer = dict((k, fn) for k, _, fn in NAV_ITEMS)[st.session_state.active_page]
active_renderer()
