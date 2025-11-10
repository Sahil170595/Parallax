"""
Immersive, end-to-end Parallax showcase dashboard inspired by modern Streamlit
gallery storytelling apps and the Observable-style narrative walkthroughs.

Run with:
    streamlit run immersive_dashboard.py
"""
from __future__ import annotations

import html
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from PIL import Image, UnidentifiedImageError

DATASETS_DIR = Path(os.getenv("PARALLAX_DATASETS_DIR", "datasets")).expanduser()
DATASETS_BASE = DATASETS_DIR.resolve()
DEFAULT_POSTER = "https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=800&q=80"
MAX_STORYBOARD_IMAGES = 4
LOGGER = logging.getLogger(__name__)


@st.cache_data(show_spinner=False)
def _load_states(dataset_dir: Path) -> List[Dict[str, Any]]:
    """
    Load workflow states from the dataset directory with basic validation.
    """
    steps_file = dataset_dir / "steps.jsonl"
    if not steps_file.exists():
        return []
    states: List[Dict[str, Any]] = []
    skipped = 0
    try:
        with steps_file.open("r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    states.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    skipped += 1
                    LOGGER.warning(
                        "Skipping invalid JSON in %s at line %s: %s",
                        steps_file,
                        line_no,
                        exc,
                    )
    except OSError as exc:
        LOGGER.error("Unable to read %s: %s", steps_file, exc)
        return []
    if skipped:
        LOGGER.warning("Skipped %s malformed entries in %s", skipped, steps_file)
    return states


def _is_within_base(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base)
        return True
    except ValueError:
        LOGGER.warning("Skipping path outside dataset directory: %s", path)
        return False


@st.cache_data(show_spinner=False, ttl=60)
def _scan_datasets() -> List[Dict[str, Any]]:
    """
    Return available datasets without eagerly loading state payloads.
    """
    datasets: List[Dict[str, Any]] = []
    if not DATASETS_DIR.exists():
        return datasets

    for app_dir in DATASETS_DIR.iterdir():
        if not app_dir.is_dir():
            continue
        if not _is_within_base(app_dir, DATASETS_BASE):
            continue
        for task_dir in app_dir.iterdir():
            if not task_dir.is_dir():
                continue
            if not _is_within_base(task_dir, DATASETS_BASE):
                continue
            steps = task_dir / "steps.jsonl"
            if steps.exists():
                datasets.append(
                    {
                        "app": app_dir.name,
                        "task": task_dir.name.replace("-", " ").title(),
                        "path": task_dir.resolve(),
                    }
                )
    return sorted(datasets, key=lambda d: d["task"].lower())


def _hero_section(dataset: Dict[str, Any]) -> None:
    states = dataset["states"]
    total_modals = sum(1 for s in states if s.get("has_modal"))
    total_toasts = sum(1 for s in states if s.get("metadata", {}).get("has_toast"))
    total_critical = sum(
        1 for s in states if s.get("metadata", {}).get("significance") == "critical"
    )
    task_name = html.escape(dataset["task"])
    app_label = html.escape(dataset["app"].title())

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(
            f"""
            <div class="hero-card">
                <p class="eyebrow">Live Workflow Story</p>
                <h1 class="hero-title">{task_name}</h1>
                <p class="hero-subtitle">
                    {app_label} &middot; {len(states)} captured states &middot;
                    {total_critical} critical milestones
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.metric("States", len(states))
        st.metric("Modals", total_modals)
        st.metric("Toasts", total_toasts)


def _timeline(states: List[Dict[str, Any]]) -> None:
    if not states:
        st.info("No states available for this dataset.")
        return

    timeline_df = []
    for idx, state in enumerate(states, start=1):
        timeline_df.append(
            {
                "step": idx,
                "action": state.get("action") or "unknown",
                "url": state.get("url") or "N/A",
                "has_modal": bool(state.get("has_modal")),
                "toast": bool(state.get("metadata", {}).get("has_toast")),
                "significance": state.get("metadata", {}).get("significance", "optional"),
            }
        )

    fig = go.Figure()
    colors = {"critical": "#ef4444", "supporting": "#10b981", "optional": "#94a3b8"}

    fig.add_trace(
        go.Scatter(
            x=[row["step"] for row in timeline_df],
            y=[1] * len(timeline_df),
            mode="markers+lines",
            marker=dict(
                size=16,
                color=[colors.get(row["significance"], "#0ea5e9") for row in timeline_df],
                line=dict(width=2, color="#0f172a"),
                symbol=[
                    "diamond" if row["has_modal"] else ("star" if row["toast"] else "circle")
                    for row in timeline_df
                ],
            ),
            text=[
                f"Step {row['step']} · {row['action']}" for row in timeline_df
            ],
            hovertemplate="<b>%{text}</b><br>%{customdata}<extra></extra>",
            customdata=[row["url"] for row in timeline_df],
        )
    )
    fig.update_layout(
        height=260,
        showlegend=False,
        yaxis=dict(visible=False),
        xaxis=dict(title="Step #"),
        margin=dict(l=20, r=20, t=10, b=10),
        plot_bgcolor="#0f172a",
        paper_bgcolor="#0f172a",
        font=dict(color="#f8fafc"),
    )
    st.plotly_chart(fig, use_container_width=True)


def _storyboard(states: List[Dict[str, Any]], dataset_dir: Path) -> None:
    if not states:
        return
    st.markdown("### 🎬 Cinematic Storyboard")
    chunk = min(MAX_STORYBOARD_IMAGES, len(states))
    cols = st.columns(chunk)
    for idx, state in enumerate(states[:chunk]):
        with cols[idx]:
            action = str(state.get("action") or "N/A")
            significance = str(
                state.get("metadata", {}).get("significance", "optional")
            ).title()
            screenshot = _resolve_screenshot(state, dataset_dir)
            if screenshot:
                st.image(screenshot, use_container_width=True)
            else:
                st.caption("Screenshot unavailable for this step.")
            st.caption(
                f"Step {idx + 1}: {action.title()} · {significance}"
            )


def _resolve_screenshot(state: Dict[str, Any], dataset_dir: Path) -> Optional[Image.Image]:
    """
    Resolve a screenshot file from the state metadata, ensuring it stays within the dataset directory.
    """
    shots = state.get("screenshots") or {}
    filename = (
        shots.get("focus")
        or shots.get("desktop")
        or shots.get("full")
        or shots.get("mobile")
    )
    if not filename:
        return None

    candidate = dataset_dir / filename
    try:
        resolved = candidate.resolve()
        dataset_base = dataset_dir.resolve()
        resolved.relative_to(dataset_base)
    except (OSError, ValueError):
        LOGGER.warning("Screenshot path escapes dataset directory: %s", candidate)
        return None

    if not resolved.exists():
        return None

    try:
        return Image.open(resolved)
    except (OSError, UnidentifiedImageError) as exc:
        LOGGER.warning("Failed to load screenshot %s: %s", resolved, exc)
        return None


def _insights(states: List[Dict[str, Any]]) -> None:
    if not states:
        return

    st.markdown("### 📊 Insight Highlights")
    categories = ["navigate", "click", "type", "wait", "scroll", "other"]
    counts = {cat: 0 for cat in categories}
    for state in states:
        action = (state.get("action") or "").split("(")[0].lower()
        if action not in counts:
            action = "other"
        counts[action] += 1

    fig = px.bar(
        x=list(counts.keys()),
        y=list(counts.values()),
        title="Action Mix",
        labels={"x": "Action", "y": "Occurrences"},
        text_auto=True,
    )
    fig.update_layout(
        plot_bgcolor="#0f172a",
        paper_bgcolor="#0f172a",
        font=dict(color="#f8fafc"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _state_explorer(states: List[Dict[str, Any]], dataset_dir: Path) -> None:
    st.markdown("### 🔎 Deep Dive")
    if not states:
        st.info("No states available for detailed exploration.")
        return
    selected = st.slider("Select Step", 1, len(states), 1)
    state = states[selected - 1]
    screenshot = _resolve_screenshot(state, dataset_dir)
    col1, col2 = st.columns([3, 1])
    with col1:
        if screenshot:
            st.image(
                screenshot,
                caption=state.get("description") or state.get("url"),
                use_container_width=True,
            )
        else:
            st.info("Screenshot not found for this state.")
    with col2:
        st.write("**Action**", state.get("action", "N/A"))
        st.write("**URL**", state.get("url", "N/A"))
        st.write("**Modal**", state.get("has_modal", False))
        st.json(state.get("metadata") or {}, expanded=False)


def _load_report_html(dataset_dir: Path) -> Optional[str]:
    html = dataset_dir / "report.html"
    if not html.exists():
        return None
    try:
        return html.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        LOGGER.error("Failed to read HTML report %s: %s", html, exc)
        return None


def main() -> None:
    st.set_page_config(
        page_title="Parallax Immersive Demo",
        page_icon="🎥",
        layout="wide",
    )
    _inject_css()
    datasets = _scan_datasets()

    if not datasets:
        st.warning("Generate a dataset first (run any workflow) to use this dashboard.")
        return

    with st.sidebar:
        st.image(
            DEFAULT_POSTER,
            caption="Visual inspiration from Streamlit Gallery & Observable notebooks",
            use_container_width=True,
        )
        selection = st.selectbox(
            "Choose a workflow dataset",
            options=list(range(len(datasets))),
            format_func=lambda idx: f"{datasets[idx]['app']} · {datasets[idx]['task']}",
        )
        selected_dataset_meta = datasets[selection]

        st.caption("This showcase focuses on storytelling & playback, not re-running tasks.")
        report_path = selected_dataset_meta["path"] / "report.html"
        if report_path.exists():
            try:
                report_bytes = report_path.read_bytes()
            except OSError as exc:
                LOGGER.error("Failed to read report %s: %s", report_path, exc)
            else:
                st.download_button(
                    label="📥 Download HTML Report",
                    data=report_bytes,
                    file_name="report.html",
                    mime="text/html",
                )

    selected_dataset = dict(selected_dataset_meta)
    selected_dataset["states"] = _load_states(selected_dataset_meta["path"])

    st.markdown("## ✨ Immersive Workflow Walkthrough")
    _hero_section(selected_dataset)
    _timeline(selected_dataset["states"])
    _storyboard(selected_dataset["states"], selected_dataset["path"])
    _insights(selected_dataset["states"])
    _state_explorer(selected_dataset["states"], selected_dataset["path"])

    with st.expander("HTML report preview"):
        html = _load_report_html(selected_dataset["path"])
        if html:
            st.components.v1.html(html, height=400, scrolling=True)
        else:
            st.info("HTML report not found for this dataset.")


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        body, .stApp { background: #020617; color: #f8fafc; }
        .hero-card {
            border-radius: 18px;
            padding: 2rem;
            background: radial-gradient(circle at top left, #312e81, #0f172a 60%);
            border: 1px solid rgba(255,255,255,0.05);
            box-shadow: 0 20px 60px rgba(15, 23, 42, 0.6);
        }
        .hero-card .eyebrow {
            text-transform: uppercase;
            letter-spacing: 0.3rem;
            color: #818cf8;
        }
        .hero-title {
            font-size: 2.5rem;
            margin: 0;
        }
        .hero-subtitle {
            color: #cbd5f5;
            font-size: 1rem;
        }
        .stMetric {
            background: linear-gradient(135deg, #0f172a, #1e1b4b);
            padding: 1rem;
            border-radius: 12px;
        }
        .css-1dp5vir, .css-1avcm0n { background: transparent !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
