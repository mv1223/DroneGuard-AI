"""FlytBase Assignment Tactile Paper / Neo-Brutalist Design System.

Warm cream paper canvas (#F7F4EB), sharp-cornered #FBF9F2 cards with 2px solid
#141414 borders and 4px hard offset shadows, Forest Green (#057A36) primary
action buttons, Warm Stone (#EFECE1) sidebar rail, and Space Grotesk + Space Mono
engineering typography.
"""

from __future__ import annotations

import streamlit as st

FONT_LINKS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
"""

TACTILE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap');

:root {
    --paper: #F7F4EB;
    --paper-card: #FBF9F2;
    --paper-top: #F2EFE4;
    --stone: #EFECE1;
    --stone-deep: #DFD9C8;
    --ink: #141414;
    --ink-muted: #5C5B55;
    --green: #057A36;
    --green-hover: #068F3F;
    --amber: #EAB308;
    --red: #DC2626;
    --blue: #1D4ED8;
    --shadow-sm: 3px 3px 0px #141414;
    --shadow-md: 4px 4px 0px #141414;
}

@keyframes tactileFadeIn {
    from {
        opacity: 0;
        transform: translateY(8px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

/* Base monospace engineering typography matching the assignment UI */
html, body, .stApp, p, span, label, input, select, textarea, button, td, th {
    font-family: 'Space Mono', Consolas, 'Courier New', monospace !important;
    color: var(--ink);
}

h1, h2, h3, .fb-h1, .fb-brand-title {
    font-family: 'Space Grotesk', 'Segoe UI', sans-serif !important;
    color: var(--ink) !important;
}

.stApp {
    background-color: var(--paper) !important;
}

header[data-testid="stHeader"] {
    background-color: var(--paper-top) !important;
    border-bottom: 1.5px solid var(--ink) !important;
}

/* Main workspace smooth transition */
[data-testid="stMainBlockContainer"] {
    animation: tactileFadeIn 0.28s cubic-bezier(0.22, 1, 0.36, 1);
    padding-top: 1.4rem !important;
    padding-bottom: 3rem !important;
    max-width: 1360px;
}

/* Left Navigation Rail in Warm Stone */
[data-testid="stSidebar"] {
    background-color: var(--stone) !important;
    border-right: 2px solid var(--ink) !important;
}

[data-testid="stSidebar"] hr {
    border-color: #C9C4B4 !important;
    margin: 0.85rem 0 !important;
}

[data-testid="stSidebarNav"] {
    display: none !important;
}

/* Sidebar Navigation Buttons (sharp corners, tactile shadow on hover/active) */
[data-testid="stSidebar"] [class*="st-key-nav_"] button {
    width: 100%;
    justify-content: flex-start !important;
    text-align: left !important;
    background-color: var(--paper-card) !important;
    border: 1.5px solid var(--ink) !important;
    border-radius: 0px !important;
    color: var(--ink) !important;
    padding: 0.55rem 0.78rem !important;
    font-size: 0.80rem !important;
    font-weight: 400 !important;
    gap: 10px !important;
    box-shadow: none !important;
    transition: transform 0.16s cubic-bezier(0.22, 1, 0.36, 1),
                box-shadow 0.16s cubic-bezier(0.22, 1, 0.36, 1),
                background-color 0.16s ease !important;
}

[data-testid="stSidebar"] [class*="st-key-nav_"] button:hover {
    background-color: #FFFFFF !important;
    transform: translate(-2px, -2px);
    box-shadow: 3px 3px 0px #141414 !important;
}

[data-testid="stSidebar"] [class*="st-key-nav_"] button[kind="primary"] {
    background-color: var(--green) !important;
    border: 2px solid var(--ink) !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    box-shadow: 3px 3px 0px #141414 !important;
}

[data-testid="stSidebar"] [class*="st-key-nav_"] button[kind="primary"] p,
[data-testid="stSidebar"] [class*="st-key-nav_"] button[kind="primary"] span {
    color: #FFFFFF !important;
}

[data-testid="stSidebar"] [class*="st-key-nav_"] button::before {
    content: "";
    width: 14px;
    height: 14px;
    flex-shrink: 0;
    background-size: contain;
    background-repeat: no-repeat;
    background-position: center;
}

.st-key-nav_overview button::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23141414' stroke-width='2'%3E%3Crect x='3' y='3' width='7' height='7'/%3E%3Crect x='14' y='3' width='7' height='7'/%3E%3Crect x='14' y='14' width='7' height='7'/%3E%3Crect x='3' y='14' width='7' height='7'/%3E%3C/svg%3E");
}
.st-key-nav_media button::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23141414' stroke-width='2'%3E%3Crect x='2' y='6' width='14' height='12'/%3E%3Cpath d='m22 8-6 4 6 4V8Z'/%3E%3C/svg%3E");
}
.st-key-nav_frames button::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23141414' stroke-width='2'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='m21 21-4.3-4.3'/%3E%3C/svg%3E");
}
.st-key-nav_alerts button::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23141414' stroke-width='2'%3E%3Cpath d='M10.29 3.86 1.82 18h20.36L13.71 3.86a2 2 0 0 0-3.42 0Z'/%3E%3Cline x1='12' y1='9' x2='12' y2='13'/%3E%3Cline x1='12' y1='16' x2='12.01' y2='16'/%3E%3C/svg%3E");
}
.st-key-nav_telemetry button::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23141414' stroke-width='2'%3E%3Cpath d='M22 12h-4l-3 9L9 3l-3 9H2'/%3E%3C/svg%3E");
}
.st-key-nav_analyst button::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23141414' stroke-width='2'%3E%3Cpath d='M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'/%3E%3C/svg%3E");
}
.st-key-nav_reports button::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23141414' stroke-width='2'%3E%3Cpath d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/%3E%3Cpolyline points='14 2 14 8 20 8'/%3E%3C/svg%3E");
}

[data-testid="stSidebar"] [class*="st-key-nav_"] button[kind="primary"]::before {
    filter: invert(1);
}

/* Sidebar utility buttons */
[data-testid="stSidebar"] [class*="st-key-action_"] button {
    background-color: var(--stone-deep) !important;
    border: 1.5px solid var(--ink) !important;
    border-radius: 0px !important;
    color: var(--ink) !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    box-shadow: 2px 2px 0px #141414 !important;
    transition: transform 0.14s ease, box-shadow 0.14s ease !important;
}

[data-testid="stSidebar"] [class*="st-key-action_"] button:hover {
    transform: translate(-1px, -1px);
    box-shadow: 3px 3px 0px #141414 !important;
}

[data-testid="stSidebar"] [class*="st-key-action_"] button:active {
    transform: translate(2px, 2px);
    box-shadow: none !important;
}

[data-testid="stSidebar"] [class*="st-key-action_"] button[kind="primary"] {
    background-color: var(--green) !important;
    color: #FFFFFF !important;
}

[data-testid="stSidebar"] [class*="st-key-action_"] button[kind="primary"] p {
    color: #FFFFFF !important;
}

/* Main Workspace Page Header & Notice Bar */
.fb-page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    padding-bottom: 0.85rem;
    margin-bottom: 1.1rem;
    gap: 16px;
}

.fb-eyebrow {
    font-size: 0.70rem;
    font-weight: 400;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--ink-muted);
    margin-bottom: 0.25rem;
}

.fb-h1 {
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 2.0rem;
    font-weight: 700;
    letter-spacing: -0.025em;
    line-height: 1.12;
    color: var(--ink);
    margin: 0 0 0.25rem 0;
}

.fb-subtitle {
    font-size: 0.83rem;
    color: var(--ink-muted);
    margin: 0;
}

.fb-header-pill {
    background: var(--green);
    color: #FFFFFF !important;
    border: 2px solid var(--ink);
    box-shadow: var(--shadow-sm);
    padding: 7px 14px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    white-space: nowrap;
}

.fb-notice-strip {
    background: var(--paper-card);
    border: 2px solid var(--ink);
    box-shadow: var(--shadow-sm);
    padding: 10px 14px;
    margin-bottom: 1.35rem;
    font-size: 0.82rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
}

.fb-tactile-dots {
    display: inline-flex;
    gap: 5px;
    align-items: center;
}

.fb-sq {
    width: 9px;
    height: 9px;
    border: 1.5px solid var(--ink);
    display: inline-block;
}

/* KPI Grid with hard black offset shadows */
.fb-kpi-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 14px;
    margin-bottom: 1.4rem;
}

@media (max-width: 1024px) {
    .fb-kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

.fb-kpi-card {
    background: var(--paper-card);
    border: 2px solid var(--ink);
    border-radius: 0px;
    padding: 15px 16px;
    box-shadow: var(--shadow-md);
    transition: transform 0.18s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.18s ease;
}

.fb-kpi-card:hover {
    transform: translate(-2px, -2px);
    box-shadow: 6px 6px 0px #141414;
}

.fb-kpi-label {
    font-size: 0.70rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink-muted);
    margin-bottom: 8px;
}

.fb-kpi-value {
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 1.85rem;
    font-weight: 700;
    color: var(--ink);
    line-height: 1.05;
}

.fb-kpi-meta {
    margin-top: 7px;
    font-size: 0.72rem;
    color: var(--ink-muted);
}

/* Bordered Streamlit containers -> Sharp neo-brutalist paper cards */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--paper-card) !important;
    border: 2px solid var(--ink) !important;
    border-radius: 0px !important;
    box-shadow: var(--shadow-md) !important;
}

/* Native stMetric */
[data-testid="stMetric"] {
    background: var(--paper-card);
    border: 2px solid var(--ink);
    border-radius: 0px;
    padding: 14px 16px;
    box-shadow: var(--shadow-sm);
}

/* Main Workspace Buttons */
[data-testid="stMainBlockContainer"] .stButton > button,
[data-testid="stMainBlockContainer"] .stDownloadButton > button {
    border-radius: 0px !important;
    border: 2px solid var(--ink) !important;
    background-color: var(--paper-card) !important;
    color: var(--ink) !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    box-shadow: var(--shadow-sm) !important;
    transition: transform 0.15s cubic-bezier(0.22, 1, 0.36, 1),
                box-shadow 0.15s ease,
                background-color 0.15s ease !important;
}

[data-testid="stMainBlockContainer"] .stButton > button:hover,
[data-testid="stMainBlockContainer"] .stDownloadButton > button:hover {
    transform: translate(-1px, -1px);
    box-shadow: 4px 4px 0px #141414 !important;
    background-color: #FFFFFF !important;
}

[data-testid="stMainBlockContainer"] .stButton > button:active,
[data-testid="stMainBlockContainer"] .stDownloadButton > button:active {
    transform: translate(2px, 2px);
    box-shadow: none !important;
}

[data-testid="stMainBlockContainer"] .stButton > button[kind="primary"] {
    background-color: var(--green) !important;
    border: 2px solid var(--ink) !important;
    color: #FFFFFF !important;
}

[data-testid="stMainBlockContainer"] .stButton > button[kind="primary"] p {
    color: #FFFFFF !important;
}

[data-testid="stMainBlockContainer"] .stButton > button[kind="primary"]:hover {
    background-color: var(--green-hover) !important;
}

/* Inputs & Selects */
[data-baseweb="input"] > div,
[data-baseweb="select"] > div,
[data-testid="stFileUploader"] section {
    border-radius: 0px !important;
    border: 1.5px solid var(--ink) !important;
    background-color: #FFFFFF !important;
}

/* DataFrames */
[data-testid="stDataFrame"] {
    background: var(--paper-card);
    border: 2px solid var(--ink);
    border-radius: 0px;
    box-shadow: var(--shadow-sm);
}

/* Status Badges */
.fb-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 8px;
    border-radius: 0px;
    font-size: 0.70rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    border: 1.5px solid var(--ink);
}
.fb-badge-critical { background: #FEE2E2; color: #991B1B; }
.fb-badge-high { background: #FFEDD5; color: #9A3412; }
.fb-badge-medium { background: #FEF3C7; color: #92400E; }
.fb-badge-low { background: #DBEAFE; color: #1E40AF; }
.fb-badge-ok { background: var(--green); color: #FFFFFF; }
.fb-badge-neutral { background: var(--stone); color: var(--ink); }

.fb-section-label {
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--ink);
    margin: 0.35rem 0 0.70rem 0;
}

/* Sidebar provider status rows */
.fb-prov-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.73rem;
    padding: 4px 2px;
    color: var(--ink);
}
.fb-sq-ok {
    width: 8px; height: 8px; background: var(--green); border: 1px solid var(--ink);
    display: inline-block; margin-right: 6px;
}
.fb-sq-idle {
    width: 8px; height: 8px; background: var(--stone-deep); border: 1px solid var(--ink);
    display: inline-block; margin-right: 6px;
}
</style>
"""


def inject_theme() -> None:
    st.markdown(FONT_LINKS + TACTILE_CSS, unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, subtitle: str, right_badge: str = "") -> None:
    badge_html = f"<div class='fb-header-pill'>{right_badge}</div>" if right_badge else ""
    st.markdown(
        f"""
        <div class="fb-page-header">
            <div>
                <div class="fb-eyebrow">{eyebrow}</div>
                <h1 class="fb-h1">{title}</h1>
                <p class="fb-subtitle">{subtitle}</p>
            </div>
            {badge_html}
        </div>
        <div class="fb-notice-strip">
            <span><strong>DroneGuard AI</strong> — Grounded VLM &amp; SQLite perimeter intelligence console.</span>
            <span class="fb-tactile-dots">
                <span class="fb-sq" style="background:#141414;"></span>
                <span class="fb-sq" style="background:#EAB308;"></span>
                <span class="fb-sq" style="background:#057A36;"></span>
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def severity_badge(severity: str) -> str:
    s = (severity or "low").lower()
    cls = s if s in {"critical", "high", "medium", "low"} else "low"
    return f"<span class='fb-badge fb-badge-{cls}'>{s}</span>"
