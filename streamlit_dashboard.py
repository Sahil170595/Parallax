"""
Beautiful Streamlit Dashboard for Parallax Workflow Visualization
"""
import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import time

# Fix for Windows + Python 3.13 asyncio subprocess issue
if sys.platform == "win32" and sys.version_info >= (3, 13):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from PIL import Image

# Import Parallax components
from parallax.core.config import ParallaxConfig
from parallax.core.constitution import FailureStore
from parallax.core.metrics import ensure_metrics_server
from parallax.core.schemas import ExecutionPlan, PlanStep, UIState
from parallax.core.plan_overrides import apply_site_overrides
from parallax.agents.archivist import Archivist
from parallax.agents.interpreter import Interpreter
from parallax.agents.navigator import Navigator
from parallax.agents.observer import Observer
from parallax.agents.strategy_generator import StrategyGenerator
from parallax.observer.detectors import Detectors
from parallax.llm.anthropic_provider import AnthropicPlanner
from parallax.llm.local_provider import LocalPlanner
from parallax.llm.openai_provider import OpenAIPlanner
from parallax.core.trace import TraceController
from playwright.async_api import async_playwright
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Page config
st.set_page_config(
    page_title="Parallax Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for beautiful styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(135deg, #818cf8 0%, #a78bfa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .state-card {
        background: #1e293b;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #818cf8;
        margin-bottom: 1rem;
    }
    .step-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.875rem;
        font-weight: 600;
        margin-right: 0.5rem;
    }
    .badge-navigate { background: #3b82f6; color: white; }
    .badge-click { background: #10b981; color: white; }
    .badge-type { background: #f59e0b; color: white; }
    .badge-wait { background: #8b5cf6; color: white; }
    .badge-scroll { background: #ec4899; color: white; }
</style>
""", unsafe_allow_html=True)


def load_config() -> ParallaxConfig:
    """Load configuration from YAML file."""
    cfg_path = Path("configs/config.yaml")
    return ParallaxConfig.from_yaml(cfg_path)


def planner_from_config(cfg: ParallaxConfig):
    """Get planner from config."""
    provider = os.getenv("PARALLAX_PROVIDER", cfg.provider)
    if provider == "openai":
        return OpenAIPlanner()
    if provider == "anthropic":
        return AnthropicPlanner()
    if provider == "local":
        return LocalPlanner()
    planner_factories = (OpenAIPlanner, AnthropicPlanner, LocalPlanner)
    for factory in planner_factories:
        try:
            return factory()
        except Exception:
            continue
    raise RuntimeError("No LLM planner available")


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    return "-".join("".join(c.lower() if c.isalnum() else " " for c in text).split())


def load_datasets() -> List[Dict[str, Any]]:
    """Load all datasets from the datasets directory."""
    datasets = []
    datasets_dir = Path("datasets")
    if not datasets_dir.exists():
        return datasets
    
    for app_dir in datasets_dir.iterdir():
        if app_dir.is_dir() and not app_dir.name.startswith("_"):
            for task_dir in app_dir.iterdir():
                if task_dir.is_dir():
                    report_path = task_dir / "report.html"
                    db_path = task_dir / "dataset.db"
                    steps_path = task_dir / "steps.jsonl"
                    
                    # Load states count
                    states_count = 0
                    if steps_path.exists():
                        with open(steps_path, "r", encoding="utf-8") as f:
                            states_count = sum(1 for line in f if line.strip())
                    
                    datasets.append({
                        "app": app_dir.name,
                        "task": task_dir.name,
                        "path": str(task_dir),
                        "has_report": report_path.exists(),
                        "has_db": db_path.exists(),
                        "states_count": states_count,
                    })
    
    return sorted(datasets, key=lambda x: x["task"], reverse=True)


def load_states_from_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load states from JSONL file."""
    states = []
    steps_path = path / "steps.jsonl"
    if not steps_path.exists():
        return states
    
    with open(steps_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                states.append(json.loads(line))
    
    return states


def load_states_from_db(path: Path) -> List[Dict[str, Any]]:
    """Load states from SQLite database."""
    states = []
    db_path = path / "dataset.db"
    if not db_path.exists():
        return states
    
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, url, description, has_modal, action, state_signature, metadata
            FROM states
            ORDER BY created_at
        """)
        
        for row in cursor.fetchall():
            state_id, url, description, has_modal, action, state_signature, metadata_json = row
            metadata = json.loads(metadata_json) if metadata_json else {}
            
            # Get screenshots
            cursor.execute("""
                SELECT viewport, filename FROM screenshots WHERE state_id = ?
            """, (state_id,))
            screenshots = {viewport: filename for viewport, filename in cursor.fetchall()}
            
            states.append({
                "id": state_id,
                "url": url,
                "description": description,
                "has_modal": bool(has_modal),
                "action": action,
                "state_signature": state_signature,
                "screenshots": screenshots,
                "metadata": metadata,
            })
    return states


def get_badge_class(action: str) -> str:
    """Get CSS class for action badge."""
    action_lower = action.lower()
    if "navigate" in action_lower:
        return "badge-navigate"
    elif "click" in action_lower:
        return "badge-click"
    elif "type" in action_lower:
        return "badge-type"
    elif "wait" in action_lower:
        return "badge-wait"
    elif "scroll" in action_lower:
        return "badge-scroll"
    return "badge-navigate"


def main():
    """Main dashboard application."""
    
    # Header
    st.markdown('<h1 class="main-header">🎯 Parallax Dashboard</h1>', unsafe_allow_html=True)
    st.markdown("**Autonomous Workflow Capture & Visualization**")
    
    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Select Page",
            ["Run New Task", "View Datasets", "Task Analytics"],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        st.header("Configuration")
        cfg = load_config()
        st.json({
            "Provider": os.getenv("PARALLAX_PROVIDER", cfg.provider),
            "Action Budget": cfg.navigation.action_budget,
            "Headless": cfg.playwright.headless,
        })
    
    # Main content based on selected page
    if page == "Run New Task":
        show_run_task_page(cfg)
    elif page == "View Datasets":
        show_datasets_page()
    elif page == "Task Analytics":
        show_analytics_page()


def show_run_task_page(cfg: ParallaxConfig):
    """Show the run new task page."""
    st.header("🚀 Run New Task")
    
    with st.form("task_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            task = st.text_input(
                "Task Description",
                placeholder="e.g., Navigate to example.com and explore all tabs",
                help="Describe what you want Parallax to do"
            )
            app_name = st.text_input(
                "App Name",
                value="demo",
                help="Name for organizing this task"
            )
        
        with col2:
            start_url = st.text_input(
                "Start URL",
                value="https://example.com",
                help="Initial URL to navigate to"
            )
            action_budget = st.number_input(
                "Action Budget",
                min_value=1,
                max_value=100,
                value=cfg.navigation.action_budget,
                help="Maximum number of actions to execute"
            )
        capture_multi = st.checkbox(
            "Capture tablet & mobile screenshots",
            value=cfg.capture.multi_viewport,
            help="Disable to iterate faster; re-enable before generating final datasets.",
        )
        
        submitted = st.form_submit_button("🚀 Run Task", use_container_width=True)
    
    if submitted and task:
        cfg.capture.multi_viewport = capture_multi
        run_task_execution(task, app_name, start_url, action_budget, cfg)


def run_task_execution(task: str, app_name: str, start_url: str, action_budget: int, cfg: ParallaxConfig):
    """Execute a task and show real-time progress."""
    ensure_metrics_server(cfg.metrics.prometheus_port)
    
    app_label = (app_name or "").strip()
    if not app_label:
        st.error("Please provide an app name before running a workflow.")
        return

    app_dir_name = slugify(app_label)
    if not app_dir_name:
        app_dir_name = "app"
    
    progress_container = st.container()
    status_container = st.container()
    plan_container = st.container()
    execution_container = st.container()
    
    with progress_container:
        st.subheader("📊 Execution Progress")
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    try:
        # Initialize components
        planner = planner_from_config(cfg)
        datasets_dir = Path(cfg.output.base_dir)
        failure_store = FailureStore(datasets_dir / "_constitution_failures")
        strategy_generator = StrategyGenerator(
            failure_store=failure_store,
            strategies_file=datasets_dir / "_strategies" / "strategies.json"
        )
        interpreter = Interpreter(
            planner,
            failure_store=failure_store,
            strategy_generator=strategy_generator,
        )
        
        # Planning phase
        with status_container:
            with st.status("🔄 Planning workflow...", expanded=True) as status:
                status_text.text("Planning workflow...")
                plan_context = {"start_url": start_url}
                plan = asyncio.run(interpreter.plan(task, plan_context))
                plan = apply_site_overrides(plan, start_url)
                
                status.update(label=f"✅ Plan generated: {len(plan.steps)} steps", state="complete")
                status_text.text(f"Plan generated: {len(plan.steps)} steps")
                progress_bar.progress(0.1)
        
        # Show plan
        with plan_container:
            st.subheader("📋 Execution Plan")
            plan_cols = st.columns(min(3, len(plan.steps)))
            for idx, step in enumerate(plan.steps):
                col_idx = idx % len(plan_cols)
                with plan_cols[col_idx]:
                    action_emoji = {
                        "navigate": "🌐",
                        "click": "🖱️",
                        "type": "⌨️",
                        "wait": "⏳",
                        "scroll": "📜",
                    }.get(step.action, "⚙️")
                    
                    st.markdown(f"""
                    <div class="state-card">
                        <strong>{action_emoji} Step {idx + 1}: {step.action}</strong><br>
                        <small>{step.target or step.selector or step.name or step.role or 'N/A'}</small>
                    </div>
                    """, unsafe_allow_html=True)
        
        # Execution phase
        with execution_container:
            st.subheader("🎬 Executing Workflow")
            
            async def execute_workflow():
                async with async_playwright() as p:
                    browser_type = cfg.playwright.project
                    headless = cfg.playwright.headless
                    channel = cfg.playwright.channel
                    user_data_dir = cfg.playwright.user_data_dir
                    browser = None
                    
                    # Use persistent context if user_data_dir is specified (for authentication)
                    if user_data_dir:
                        from pathlib import Path
                        user_data_path = Path(user_data_dir).expanduser().resolve()
                        user_data_path.mkdir(parents=True, exist_ok=True)
                        
                        browser_launcher = getattr(p, browser_type)
                        context_kwargs = {}
                        if channel and browser_type == "chromium":
                            context_kwargs["channel"] = channel
                        if not headless:
                            context_kwargs["headless"] = False
                        
                        # Chrome args to disable automation detection and security warnings
                        if browser_type == "chromium":
                            context_kwargs["args"] = [
                                "--disable-blink-features=AutomationControlled",
                                "--disable-dev-shm-usage",
                                "--no-first-run",
                                "--no-default-browser-check",
                                "--disable-infobars",
                            ]
                            context_kwargs["viewport"] = {"width": 1920, "height": 1080}
                            context_kwargs["user_agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        
                        # Create persistent context (saves cookies/sessions)
                        context = await browser_launcher.launch_persistent_context(
                            user_data_dir=str(user_data_path),
                            **context_kwargs
                        )
                        page = context.pages[0] if context.pages else await context.new_page()
                        
                        # Remove automation indicators from page
                        await page.add_init_script("""
                            Object.defineProperty(navigator, 'webdriver', {
                                get: () => undefined
                            });
                            window.chrome = {
                                runtime: {}
                            };
                        """)
                    else:
                        # Regular browser context
                        browser_launcher = getattr(p, browser_type)
                        launch_kwargs = {"headless": headless}
                        if channel and browser_type == "chromium":
                            launch_kwargs["channel"] = channel
                        browser = await browser_launcher.launch(**launch_kwargs)
                        context = await browser.new_context()
                        page = await context.new_page()
                    
                    # Merge observer and capture configs for Detectors
                    detector_config = cfg.observer.model_dump() if hasattr(cfg.observer, 'model_dump') else cfg.observer.dict()
                    detector_config["capture"] = cfg.capture.model_dump() if hasattr(cfg.capture, 'model_dump') else cfg.capture.dict()
                    detectors = Detectors(detector_config)
                    slug = slugify(task)
                    task_dir = datasets_dir / app_dir_name / slug
                    task_dir.mkdir(parents=True, exist_ok=True)
                    
                    observer = Observer(
                        page,
                        detectors,
                        save_dir=task_dir,
                        failure_store=failure_store,
                        task_context=task,
                    )
                    
                    tracer = TraceController(context)
                    await tracer.start()
                    
                    # Create a progress callback
                    async def progress_callback(idx: int, total: int, step: Any) -> None:
                        # Clamp progress to [0.0, 1.0] to prevent overflow
                        progress = min(1.0, max(0.0, (idx + 1) / max(total, 1)))
                        progress_bar.progress(progress)
                        status_text.text(f"Executing step {idx + 1}/{total}: {step.action}")
                        await asyncio.sleep(0.05)  # Small delay for UI update
                    
                    navigator = Navigator(
                        page,
                        observer=observer,
                        default_wait_ms=cfg.navigation.default_wait_ms,
                        scroll_margin_px=cfg.navigation.scroll_margin_px,
                        failure_store=failure_store,
                        task_context=task,
                        progress_callback=progress_callback,
                        strategy_generator=strategy_generator,
                    )
                    
                    # Execute plan
                    trace_zip_path = task_dir / "trace.zip"
                    tracer_stopped = False
                    try:
                        await navigator.execute(plan, action_budget=action_budget)
                        
                        # Finalize
                        nav_context = {
                            "page": page,
                            "action_budget": action_budget,
                            "action_count": navigator.action_count,
                            "start_url": start_url,
                        }
                        
                        await tracer.stop(trace_zip_path)
                        tracer_stopped = True
                        
                        nav_report = navigator.finalize(plan, nav_context)

                        from parallax.core.completion import CompletionValidationError, validate_completion
                        try:
                            validate_completion(
                                plan,
                                observer.states,
                                min_targets=cfg.completion.min_targets,
                            )
                        except CompletionValidationError as exc:
                            raise RuntimeError(f"Completion validation failed: {', '.join(exc.missing)}") from exc
                        
                        # Save dataset
                        archivist = Archivist(datasets_dir, failure_store=failure_store)
                        root = archivist.write_states(app_dir_name, slug, observer.states, trace_zip="trace.zip")
                        
                        return root, observer.states
                    finally:
                        # Ensure cleanup happens even if exceptions occur
                        if tracer and not tracer_stopped:
                            try:
                                await tracer.stop(trace_zip_path)
                            except Exception:
                                pass
                        if context:
                            try:
                                await context.close()
                            except Exception:
                                pass
                        if browser:
                            try:
                                await browser.close()
                            except Exception:
                                pass
            
            # Run execution
            root, states = asyncio.run(execute_workflow())
            
            progress_bar.progress(1.0)
            status_text.text("✅ Task completed successfully!")
            
            # Show results
            st.success(f"✅ Task completed! Captured {len(states)} states.")
            st.info(f"📁 Dataset saved to: `{root}`")
            
            # Show preview of captured states
            if states:
                st.subheader("📸 Captured States Preview")
                preview_cols = st.columns(min(3, len(states)))
                for idx, state in enumerate(states[:9]):  # Show first 9
                    col_idx = idx % len(preview_cols)
                    with preview_cols[col_idx]:
                        if hasattr(state, 'screenshots') and "full" in state.screenshots:
                            screenshot_path = root / state.screenshots["full"]
                            if screenshot_path.exists():
                                img = Image.open(screenshot_path)
                                st.image(img, caption=f"State {idx + 1}", use_container_width=True)
                        elif isinstance(state, dict) and "full" in state.get("screenshots", {}):
                            screenshot_path = root / state["screenshots"]["full"]
                            if screenshot_path.exists():
                                img = Image.open(screenshot_path)
                                st.image(img, caption=f"State {idx + 1}", use_container_width=True)
    
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.exception(e)


def show_datasets_page():
    """Show the datasets viewing page."""
    st.header("📚 View Datasets")
    
    datasets = load_datasets()
    
    if not datasets:
        st.info("No datasets found. Run a task to create one!")
        return
    
    # Filter and search
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("🔍 Search datasets", placeholder="Search by app or task name...")
    with col2:
        selected_app = st.selectbox("Filter by App", ["All"] + list(set(d["app"] for d in datasets)))
    
    # Filter datasets
    filtered_datasets = datasets
    if search_query:
        filtered_datasets = [d for d in filtered_datasets if search_query.lower() in d["task"].lower() or search_query.lower() in d["app"].lower()]
    if selected_app != "All":
        filtered_datasets = [d for d in filtered_datasets if d["app"] == selected_app]
    
    st.metric("Total Datasets", len(filtered_datasets))
    
    # Display datasets
    for dataset in filtered_datasets:
        with st.expander(f"📦 {dataset['app']}/{dataset['task']} ({dataset['states_count']} states)"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("States Captured", dataset["states_count"])
            
            with col2:
                st.metric("Has Report", "✅" if dataset["has_report"] else "❌")
            
            with col3:
                st.metric("Has Database", "✅" if dataset["has_db"] else "❌")
            
            # Load and display states
            # Use a unique key based on app and task to avoid duplicates
            button_key = f"view_{dataset['app']}_{dataset['task']}".replace(" ", "_").replace("/", "_").replace("-", "_")
            if st.button(f"View Details", key=button_key):
                view_dataset_details(Path(dataset["path"]))


def view_dataset_details(path: Path):
    """View detailed information about a dataset."""
    st.subheader("📊 Dataset Details")
    
    # Load states
    states = load_states_from_jsonl(path)
    if not states:
        states = load_states_from_db(path)
    
    if not states:
        st.warning("No states found in this dataset.")
        return
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total States", len(states))
    with col2:
        modals_count = sum(1 for s in states if s.get("has_modal", False))
        st.metric("States with Modals", modals_count)
    with col3:
        unique_urls = len(set(s.get("url", "") for s in states))
        st.metric("Unique URLs", unique_urls)
    with col4:
        total_screenshots = sum(len(s.get("screenshots", {})) for s in states)
        st.metric("Total Screenshots", total_screenshots)
    
    # Timeline visualization
    st.subheader("📈 State Timeline")
    
    # Create timeline data
    timeline_data = []
    for idx, state in enumerate(states):
        timeline_data.append({
            "Step": idx + 1,
            "URL": state.get("url", "")[:50] + "..." if len(state.get("url", "")) > 50 else state.get("url", ""),
            "Action": state.get("action", "N/A"),
            "Has Modal": state.get("has_modal", False),
        })
    
    if timeline_data:
        df = px.data.tips()  # Dummy data for structure
        fig = go.Figure()
        
        # Add scatter plot for states
        fig.add_trace(go.Scatter(
            x=[d["Step"] for d in timeline_data],
            y=[1] * len(timeline_data),
            mode='markers+lines',
            marker=dict(
                size=10,
                color=['#f87171' if d["Has Modal"] else '#10b981' for d in timeline_data],
                symbol=['diamond' if d["Has Modal"] else 'circle' for d in timeline_data]
            ),
            text=[f"Step {d['Step']}: {d['Action']}" for d in timeline_data],
            hovertemplate="<b>%{text}</b><br>URL: %{customdata}<extra></extra>",
            customdata=[d["URL"] for d in timeline_data],
            name="States"
        ))
        
        fig.update_layout(
            title="State Progression Timeline",
            xaxis_title="Step Number",
            yaxis_title="",
            height=300,
            showlegend=False,
            hovermode='closest'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # State viewer
    st.subheader("🖼️ State Viewer")
    
    selected_state_idx = st.slider("Select State", 0, len(states) - 1, 0)
    selected_state = states[selected_state_idx]
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Display screenshot
        if "full" in selected_state.get("screenshots", {}):
            screenshot_path = path / selected_state["screenshots"]["full"]
            if screenshot_path.exists():
                img = Image.open(screenshot_path)
                st.image(img, caption=f"State {selected_state_idx + 1}: {selected_state.get('description', 'N/A')}", use_container_width=True)
            else:
                st.warning(f"Screenshot not found: {screenshot_path}")
        else:
            st.info("No screenshot available for this state")
    
    with col2:
        st.json({
            "ID": selected_state.get("id", "N/A"),
            "URL": selected_state.get("url", "N/A"),
            "Action": selected_state.get("action", "N/A"),
            "Has Modal": selected_state.get("has_modal", False),
            "Description": selected_state.get("description", "N/A"),
        })
        
        # Show other viewports if available
        screenshots = selected_state.get("screenshots", {})
        if "mobile" in screenshots or "tablet" in screenshots:
            st.subheader("Other Viewports")
            if "mobile" in screenshots:
                mobile_path = path / screenshots["mobile"]
                if mobile_path.exists():
                    st.image(Image.open(mobile_path), caption="Mobile", use_container_width=True)
            if "tablet" in screenshots:
                tablet_path = path / screenshots["tablet"]
                if tablet_path.exists():
                    st.image(Image.open(tablet_path), caption="Tablet", use_container_width=True)


def show_analytics_page():
    """Show analytics and insights page."""
    st.header("📊 Task Analytics")
    
    datasets = load_datasets()
    
    if not datasets:
        st.info("No datasets available for analytics.")
        return
    
    # Overall metrics
    st.subheader("📈 Overall Metrics")
    
    total_states = sum(d["states_count"] for d in datasets)
    total_datasets = len(datasets)
    apps = len(set(d["app"] for d in datasets))
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Datasets", total_datasets)
    with col2:
        st.metric("Total States", total_states)
    with col3:
        st.metric("Unique Apps", apps)
    with col4:
        avg_states = total_states / total_datasets if total_datasets > 0 else 0
        st.metric("Avg States/Dataset", f"{avg_states:.1f}")
    
    # App distribution
    st.subheader("📊 App Distribution")
    app_counts = {}
    for dataset in datasets:
        app_counts[dataset["app"]] = app_counts.get(dataset["app"], 0) + 1
    
    if app_counts:
        fig = px.pie(
            values=list(app_counts.values()),
            names=list(app_counts.keys()),
            title="Datasets by App"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # States distribution
    st.subheader("📊 States Distribution")
    states_counts = [d["states_count"] for d in datasets if d["states_count"] > 0]
    
    if states_counts:
        fig = px.histogram(
            x=states_counts,
            nbins=20,
            title="Distribution of States per Dataset",
            labels={"x": "Number of States", "y": "Number of Datasets"}
        )
        st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()

