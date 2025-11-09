"""
Immersive, end-to-end Parallax showcase dashboard inspired by modern Streamlit
gallery storytelling apps and the Observable-style narrative walkthroughs.

Run with:
    streamlit run immersive_dashboard.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

DATASETS_DIR = Path("datasets")
DEFAULT_POSTER = "https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=800&q=80"


@st.cache_data(show_spinner=False)
def _load_states(dataset_dir: Path) -> List[Dict[str, Any]]:
    steps_file = dataset_dir / "steps.jsonl"
    if not steps_file.exists():
        return []
    states: List[Dict[str, Any]] = []
    with steps_file.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                states.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return states


def _scan_datasets() -> List[Dict[str, Any]]:
    datasets: List[Dict[str, Any]] = []
    if not DATASETS_DIR.exists():
        return datasets

    for app_dir in DATASETS_DIR.iterdir():
        if not app_dir.is_dir():
            continue
        for task_dir in app_dir.iterdir():
            steps = task_dir / "steps.jsonl"
            if steps.exists():
                states = _load_states(task_dir)
                datasets.append(
                    {
                        "app": app_dir.name,
                        "task": task_dir.name.replace("-", " ").title(),
                        "path": task_dir,
                        "states_count": len(states),
                        "states": states,
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

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(
            f"""
            <div class="hero-card">
                <p class="eyebrow">Live Workflow Story</p>
                <h1 class="hero-title">{dataset['task']}</h1>
                <p class="hero-subtitle">
                    {dataset['app'].title()} • {len(states)} captured states •
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
    chunk = min(4, len(states))
    cols = st.columns(chunk)
    for idx in range(chunk):
        state = states[idx]
        with cols[idx]:
            screenshot = _resolve_screenshot(state, dataset_dir)
            if screenshot:
                st.image(screenshot, use_container_width=True)
            st.caption(
                f"Step {idx + 1}: {state.get('action', 'N/A').title()} · "
                f"{state.get('metadata', {}).get('significance', 'optional').title()}"
            )


def _resolve_screenshot(state: Dict[str, Any], dataset_dir: Path) -> Optional[Image.Image]:
    shots = state.get("screenshots") or {}
    filename = (
        shots.get("focus")
        or shots.get("desktop")
        or shots.get("full")
        or shots.get("mobile")
    )
    if not filename:
        return None
    path = dataset_dir / filename
    if not path.exists():
        return None
    try:
        return Image.open(path)
    except Exception:
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
    return html.read_text(encoding="utf-8", errors="ignore")


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
        selected_dataset = datasets[selection]

        st.caption("This showcase focuses on storytelling & playback, not re-running tasks.")
        st.markdown(
            "[Open original HTML report]"
            f"(file://{selected_dataset['path'] / 'report.html'})",
            unsafe_allow_html=True,
        )

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
