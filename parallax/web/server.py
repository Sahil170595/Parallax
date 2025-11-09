"""FastAPI web server for Parallax UI."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# Fix for Windows + Python 3.13 asyncio subprocess issue
if sys.platform == "win32" and sys.version_info >= (3, 13):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl, validator
from playwright.async_api import async_playwright

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from parallax.core.config import ParallaxConfig
from parallax.core.constitution import ConstitutionViolation, FailureStore
from parallax.core.completion import CompletionValidationError, validate_completion
from parallax.core.plan_overrides import apply_site_overrides
from parallax.core.logging import configure_logging, get_logger
from parallax.core.schemas import ExecutionPlan
from parallax.agents.archivist import Archivist
from parallax.agents.interpreter import Interpreter
from parallax.agents.navigator import Navigator
from parallax.agents.observer import Observer
from parallax.agents.strategy_generator import StrategyGenerator
from parallax.core.metrics import ensure_metrics_server
from parallax.core.trace import TraceController
from parallax.observer.detectors import Detectors
from parallax.llm.anthropic_provider import AnthropicPlanner
from parallax.llm.local_provider import LocalPlanner
from parallax.llm.openai_provider import OpenAIPlanner


app = FastAPI(title="Parallax Web UI")
log = get_logger("web")
configure_logging()

# Graceful shutdown handling
shutdown_event = asyncio.Event()
active_tasks: set[asyncio.Task] = set()

def signal_handler(sig: int, frame) -> None:
    """Handle shutdown signals gracefully."""
    try:
        signal_name = signal.Signals(sig).name
    except (ValueError, AttributeError):
        signal_name = str(sig)
    log.info("shutdown_signal_received", signal=signal_name)
    shutdown_event.set()

# Register signal handlers (only on non-Windows platforms)
if sys.platform != "win32":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
else:
    # Windows doesn't support SIGTERM, only SIGINT
    signal.signal(signal.SIGINT, signal_handler)

@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    cfg = _load_config()
    ensure_metrics_server(cfg.metrics.prometheus_port)
    log.info("server_starting")

@app.on_event("shutdown")
async def shutdown_event_handler():
    """Cleanup on shutdown."""
    log.info("server_shutting_down", active_tasks=len(active_tasks))
    # Cancel all active tasks
    for task in active_tasks:
        if not task.done():
            task.cancel()
    # Wait for tasks to complete (with timeout)
    if active_tasks:
        await asyncio.wait(active_tasks, timeout=5.0, return_when=asyncio.ALL_COMPLETED)
    log.info("server_shutdown_complete")

# Configuration
CONFIG_PATH = Path("configs/config.yaml")
DATASETS_DIR = Path("datasets")


def _load_config() -> ParallaxConfig:
    """Load and validate configuration from YAML file."""
    return ParallaxConfig.from_yaml(CONFIG_PATH)


def _planner_from_config(cfg: ParallaxConfig):
    """Get planner from config."""
    provider = os.getenv("PARALLAX_PROVIDER", cfg.provider)
    if provider == "openai":
        return OpenAIPlanner()
    if provider == "anthropic":
        return AnthropicPlanner()
    if provider == "local":
        return LocalPlanner()
    planner_factories = (OpenAIPlanner, AnthropicPlanner, LocalPlanner)
    last_error: Exception | None = None
    for factory in planner_factories:
        try:
            return factory()
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError("No LLM planner available")


def _slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    return "-".join("".join(c.lower() if c.isalnum() else " " for c in text).split())


class ConnectionManager:
    """Manage WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Connect a new WebSocket client."""
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket client."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def send_progress(self, message: dict):
        """Send progress update to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                log.warning("websocket_send_failed", error=str(e), error_type=type(e).__name__)
                disconnected.append(connection)
        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


class TaskRequest(BaseModel):
    """Task request model with validation."""
    task: str = Field(..., min_length=1, max_length=1000, description="Natural language task description")
    app_name: str = Field(default="demo", pattern=r'^[a-z0-9-_]+$', description="Application name (alphanumeric, dashes, underscores)")
    start_url: HttpUrl = Field(..., description="Starting URL for the workflow")
    
    @validator('task')
    def validate_task(cls, v):
        """Validate task is not empty after stripping."""
        if not v.strip():
            raise ValueError("Task cannot be empty")
        return v.strip()
    
    @validator('app_name')
    def validate_app_name(cls, v):
        """Validate app name format."""
        if not v or len(v) > 100:
            raise ValueError("App name must be 1-100 characters")
        return v.lower()


@app.get("/health")
async def health_check():
    """Health check endpoint with dependency status."""
    checks = {
        "status": "healthy",
        "checks": {}
    }
    
    # Check Playwright availability
    try:
        from playwright.async_api import async_playwright
        checks["checks"]["playwright"] = True
    except Exception as e:
        checks["checks"]["playwright"] = False
        checks["checks"]["playwright_error"] = str(e)
    
    # Check LLM providers
    checks["checks"]["llm_providers"] = {}
    
    # Check OpenAI
    try:
        if os.getenv("OPENAI_API_KEY"):
            from parallax.llm.openai_provider import OpenAIPlanner
            planner = OpenAIPlanner()
            checks["checks"]["llm_providers"]["openai"] = True
        else:
            checks["checks"]["llm_providers"]["openai"] = "not_configured"
    except Exception as e:
        checks["checks"]["llm_providers"]["openai"] = False
        checks["checks"]["llm_providers"]["openai_error"] = str(e)
    
    # Check Anthropic
    try:
        if os.getenv("ANTHROPIC_API_KEY"):
            from parallax.llm.anthropic_provider import AnthropicPlanner
            planner = AnthropicPlanner()
            checks["checks"]["llm_providers"]["anthropic"] = True
        else:
            checks["checks"]["llm_providers"]["anthropic"] = "not_configured"
    except Exception as e:
        checks["checks"]["llm_providers"]["anthropic"] = False
        checks["checks"]["llm_providers"]["anthropic_error"] = str(e)
    
    # Check disk space
    try:
        total, used, free = shutil.disk_usage(DATASETS_DIR if DATASETS_DIR.exists() else Path("."))
        checks["checks"]["disk_space"] = {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "free_percent": round((free / total) * 100, 2)
        }
        if free / total < 0.1:  # Less than 10% free
            checks["status"] = "degraded"
    except Exception as e:
        checks["checks"]["disk_space"] = False
        checks["checks"]["disk_space_error"] = str(e)
    
    # Determine overall status
    all_healthy = all(
        v is True or (isinstance(v, dict) and v.get("free_percent", 100) > 5)
        for v in checks["checks"].values()
        if v is not False
    )
    
    status_code = 200 if checks["status"] == "healthy" else (503 if checks["status"] == "degraded" else 200)
    return JSONResponse(checks, status_code=status_code)


@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serve the main UI page."""
    return get_ui_html()


@app.get("/api/tasks")
async def list_tasks():
    """List all captured tasks."""
    tasks = []
    if DATASETS_DIR.exists():
        for app_dir in DATASETS_DIR.iterdir():
            if app_dir.is_dir() and not app_dir.name.startswith("_"):
                for task_dir in app_dir.iterdir():
                    if task_dir.is_dir():
                        report_path = task_dir / "report.html"
                        if report_path.exists():
                            tasks.append({
                                "app": app_dir.name,
                                "task": task_dir.name,
                                "path": str(task_dir),
                                "report_url": f"/api/reports/{app_dir.name}/{task_dir.name}",
                            })
    return {"tasks": tasks}


@app.get("/api/reports/{app}/{task}")
async def get_report(app: str, task: str):
    """Get HTML report for a task."""
    report_path = DATASETS_DIR / app / task / "report.html"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(report_path)


@app.get("/api/reports/{app}/{task}/{filename}")
async def get_report_file(app: str, task: str, filename: str):
    """Get a file (screenshot, etc.) from a task directory."""
    file_path = DATASETS_DIR / app / task / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    # Security: ensure file is within task directory
    try:
        file_path.resolve().relative_to((DATASETS_DIR / app / task).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    return FileResponse(file_path)


@app.post("/api/run")
async def run_task(request: TaskRequest):
    """Run a workflow task."""
    task = request.task
    app_name = request.app_name
    start_url = request.start_url
    task_id = f"{app_name}/{_slugify(task)}"
    
    # Send initial progress
    await manager.send_progress({
        "type": "started",
        "task_id": task_id,
        "task": task,
    })
    
    try:
        cfg = _load_config()
        planner = _planner_from_config(cfg)
        
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

        vision_analyzer = None
        vision_enabled = cfg.vision.enabled
        if vision_enabled:
            try:
                from parallax.vision.analyzer import VisionAnalyzer

                vision_provider = cfg.vision.provider
                vision_analyzer = VisionAnalyzer(provider=vision_provider)
            except Exception as e:
                log.warning("vision_analyzer_failed", error=str(e))

        navigation_cfg = cfg.navigation
        heal_value = navigation_cfg.self_heal_attempts
        try:
            heal_attempts = max(0, int(heal_value))
        except (TypeError, ValueError):
            heal_attempts = 0
        total_runs = 1 + heal_attempts
        slug = _slugify(task)

        start_url_current = start_url
        action_budget_override: Optional[int] = None
        plan_context_overrides: Dict[str, Any] = {}
        failure_history: list[Dict[str, Any]] = []

        async def run_attempt(attempt_index: int, attempt_slug: str) -> dict[str, Any]:
            nonlocal start_url_current, action_budget_override, plan_context_overrides

            attempt_number = attempt_index + 1
            await manager.send_progress({
                "type": "attempt",
                "task_id": task_id,
                "attempt": attempt_number,
                "total_attempts": total_runs,
            })

            plan_context: Dict[str, Any] = {
                "start_url": start_url_current,
                "retry": attempt_index,
            }
            if failure_history:
                plan_context["failure_history"] = failure_history[-10:]
            if plan_context_overrides:
                plan_context.update(plan_context_overrides)

            await manager.send_progress({
                "type": "planning",
                "task_id": task_id,
                "attempt": attempt_number,
                "message": "Planning workflow...",
            })

            plan = await interpreter.plan(task, plan_context)
            plan = apply_site_overrides(plan, start_url_current)
            
            # Log plan details for debugging
            log.info(
                "plan_generated",
                task=task,
                steps=len(plan.steps),
                planner_type=type(planner).__name__,
                step_details=[f"{s.action}:{s.target or s.selector or s.name or s.role or ''}" for s in plan.steps[:5]]
            )

            await manager.send_progress({
                "type": "planned",
                "task_id": task_id,
                "attempt": attempt_number,
                "steps": len(plan.steps),
                "plan_preview": [{"action": s.action, "target": s.target, "name": s.name, "role": s.role} for s in plan.steps[:10]]
            })

            async with async_playwright() as p:
                browser_type = cfg.playwright.project
                headless = cfg.playwright.headless
                channel = cfg.playwright.channel
                user_data_dir = cfg.playwright.user_data_dir
                browser = None
                context = None
                tracer = None
                trace_zip_path = None
                try:
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
                    detectors = Detectors(detector_config, vision_analyzer=vision_analyzer)
                    task_dir = datasets_dir / app_name / attempt_slug
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

                    action_budget = action_budget_override or navigation_cfg.action_budget
                    total_steps = max(1, min(len(plan.steps), action_budget))

                    async def progress_callback(idx: int, total: int, step: Any) -> None:
                        await manager.send_progress({
                            "type": "progress",
                            "task_id": task_id,
                            "attempt": attempt_number,
                            "current": min(idx, total),
                            "total": max(total, 1),
                            "message": f"{step.action}",
                        })

                    navigator = Navigator(
                        page,
                        observer=observer,
                        default_wait_ms=navigation_cfg.default_wait_ms,
                        scroll_margin_px=navigation_cfg.scroll_margin_px,
                        failure_store=failure_store,
                        vision_analyzer=vision_analyzer,
                        task_context=task,
                        progress_callback=progress_callback,
                        strategy_generator=strategy_generator,
                    )

                    await manager.send_progress({
                        "type": "executing",
                        "task_id": task_id,
                        "attempt": attempt_number,
                        "message": "Executing workflow...",
                    })

                    await navigator.execute(plan, action_budget=action_budget)

                    nav_context = {
                        "page": page,
                        "action_budget": action_budget,
                        "action_count": navigator.action_count,
                        "start_url": start_url_current,
                    }
                    trace_zip_path = task_dir / "trace.zip"

                    try:
                        nav_report = navigator.finalize(plan, nav_context)
                        validate_completion(
                            plan,
                            observer.states,
                            min_targets=cfg.completion.min_targets,
                        )
                    except ConstitutionViolation as exc:
                        recovered, adjustments = await navigator.heal(plan, nav_context, exc.failures)
                        exc.recovery = {"recovered": recovered, "adjustments": adjustments}

                        await manager.send_progress({
                            "type": "validation_failed",
                            "task_id": task_id,
                            "attempt": attempt_number,
                            "failures": [
                                {
                                    "rule": failure.rule_name,
                                    "reason": failure.reason,
                                }
                                for failure in exc.failures
                            ],
                        })

                        if tracer and trace_zip_path:
                            await tracer.stop(trace_zip_path)
                        raise

                    if nav_report.warnings:
                        for warning in nav_report.warnings:
                            await manager.send_progress({
                                "type": "warning",
                                "task_id": task_id,
                                "attempt": attempt_number,
                                "message": f"{warning.rule_name}: {warning.reason}",
                            })

                    await manager.send_progress({
                        "type": "saving",
                        "task_id": task_id,
                        "attempt": attempt_number,
                        "message": "Saving results...",
                    })

                    if tracer and trace_zip_path:
                        await tracer.stop(trace_zip_path)

                    archivist = Archivist(datasets_dir, failure_store=failure_store)
                    root = archivist.write_states(app_name, attempt_slug, observer.states, trace_zip="trace.zip")

                    result = {
                        "success": True,
                        "task_id": task_id,
                        "path": str(root),
                        "report_url": f"/api/reports/{app_name}/{attempt_slug}",
                        "states": len(observer.states),
                    }

                    await manager.send_progress({"type": "completed", **result})
                    return result
                finally:
                    # Ensure cleanup happens even if exceptions occur
                    if tracer is not None and trace_zip_path is not None:
                        try:
                            await tracer.stop(trace_zip_path)
                        except Exception as e:
                            log.warning("tracer_cleanup_failed", error=str(e), error_type=type(e).__name__)
                    if context is not None:
                        try:
                            await context.close()
                        except Exception as e:
                            log.warning("context_cleanup_failed", error=str(e), error_type=type(e).__name__)
                    if browser is not None:
                        try:
                            await browser.close()
                        except Exception as e:
                            log.warning("browser_cleanup_failed", error=str(e), error_type=type(e).__name__)

        last_failure: ConstitutionViolation | None = None
        for attempt in range(total_runs):
            attempt_slug = slug if attempt == 0 else f"{slug}-retry-{attempt}"
            try:
                return await run_attempt(attempt, attempt_slug)
            except ConstitutionViolation as exc:
                last_failure = exc
                failure_history.extend(
                    {
                        "rule": failure.rule_name,
                        "reason": failure.reason,
                        "details": failure.details,
                    }
                    for failure in exc.failures
                )
                if len(failure_history) > 20:
                    failure_history[:] = failure_history[-20:]

                recovery_info = getattr(exc, "recovery", {})
                adjustments = recovery_info.get("adjustments") or {}
                recovered = recovery_info.get("recovered", False)

                notes = adjustments.get("notes") or []
                for note in notes:
                    await manager.send_progress({
                        "type": "self_heal",
                        "task_id": task_id,
                        "attempt": attempt + 1,
                        "message": note,
                    })

                if adjustments.get("start_url"):
                    start_url_current = adjustments["start_url"]

                plan_ctx = dict(adjustments.get("plan_context", {}))
                plan_ctx.pop("failure_history", None)
                if plan_ctx:
                    for key, value in plan_ctx.items():
                        if isinstance(value, list) and isinstance(plan_context_overrides.get(key), list):
                            existing = plan_context_overrides[key]
                            for item in value:
                                if item not in existing:
                                    existing.append(item)
                        else:
                            plan_context_overrides[key] = value

                if adjustments.get("action_budget"):
                    action_budget_override = adjustments["action_budget"]

                if attempt == total_runs - 1:
                    raise HTTPException(status_code=500, detail="Navigation validation failed")

                if not recovered and not adjustments:
                    await manager.send_progress({
                        "type": "info",
                        "task_id": task_id,
                        "attempt": attempt + 1,
                        "message": "No automated recovery steps available. Retrying...",
                    })

        if last_failure:
            raise HTTPException(status_code=500, detail=str(last_failure))

        raise HTTPException(status_code=500, detail="Workflow did not complete")

    except (ConstitutionViolation, RuntimeError, ValueError) as e:
        await manager.send_progress({
            "type": "error",
            "task_id": task_id,
            "message": f"Workflow failed: {str(e)}",
        })
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        await manager.send_progress({
            "type": "error",
            "task_id": task_id,
            "message": f"Unexpected error: {error_msg}",
        })
        log.exception(
            "unexpected_error_in_run_task",
            error=error_msg,
            error_type=error_type,
            task=task,
            app_name=app_name,
            start_url=str(start_url),
        )
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {error_type}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for keepalive
            await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def get_ui_html() -> str:
    """Get the main UI HTML."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Parallax - Web UI</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        :root {
            --primary: #818cf8;
            --primary-dark: #6366f1;
            --secondary: #a78bfa;
            --success: #34d399;
            --warning: #fbbf24;
            --danger: #f87171;
            --bg: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --card: #1e293b;
            --card-hover: #334155;
            --text: #f1f5f9;
            --text-light: #94a3b8;
            --text-dim: #64748b;
            --border: #334155;
            --border-light: #475569;
            --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.3), 0 1px 2px -1px rgb(0 0 0 / 0.3);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.4), 0 4px 6px -4px rgb(0 0 0 / 0.4);
            --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.5), 0 8px 10px -6px rgb(0 0 0 / 0.5);
            --radius: 12px;
            --radius-sm: 8px;
            --glow: 0 0 20px rgba(129, 140, 248, 0.3);
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', 'Roboto', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%);
            min-height: 100vh;
            padding: 2rem;
            color: var(--text);
            line-height: 1.6;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            background: var(--card);
            padding: 2rem;
            border-radius: var(--radius);
            box-shadow: var(--shadow-lg);
            border: 1px solid var(--border);
            margin-bottom: 2rem;
            animation: slideDown 0.5s ease;
        }
        
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem;
        }
        
        .header .subtitle {
            color: var(--text-light);
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .card {
            background: var(--card);
            padding: 2rem;
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            border: 1px solid var(--border);
            margin-bottom: 2rem;
            transition: all 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }
        
        .card-title {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: var(--text);
        }
        
        .form-group {
            margin-bottom: 1.5rem;
        }
        
        .form-label {
            display: block;
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: var(--text-light);
        }
        
        .form-input {
            width: 100%;
            padding: 0.75rem 1rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            color: var(--text);
            font-size: 1rem;
            transition: all 0.2s ease;
        }
        
        .form-input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(129, 140, 248, 0.1);
        }
        
        .btn {
            padding: 0.75rem 1.5rem;
            border-radius: var(--radius-sm);
            font-weight: 600;
            font-size: 1rem;
            border: none;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg), var(--glow);
        }
        
        .btn-primary:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: var(--bg-secondary);
            border-radius: 9999px;
            overflow: hidden;
            margin: 1rem 0;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%);
            transition: width 0.3s ease;
            border-radius: 9999px;
        }
        
        .status-message {
            padding: 1rem;
            background: var(--bg-secondary);
            border-radius: var(--radius-sm);
            margin: 1rem 0;
            border-left: 3px solid var(--primary);
        }
        
        .tasks-list {
            display: grid;
            gap: 1rem;
        }
        
        .task-item {
            padding: 1rem;
            background: var(--bg-secondary);
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
            transition: all 0.2s ease;
        }
        
        .task-item:hover {
            border-color: var(--border-light);
            transform: translateX(4px);
        }
        
        .task-item a {
            color: var(--primary);
            text-decoration: none;
            font-weight: 600;
        }
        
        .task-item a:hover {
            text-decoration: underline;
        }
        
        .hidden {
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Parallax</h1>
            <p class="subtitle">Autonomous workflow capture - Web UI</p>
        </div>
        
        <div class="card">
            <h2 class="card-title">Run New Task</h2>
            <form id="task-form">
                <div class="form-group">
                    <label class="form-label" for="task">Task Description</label>
                    <input 
                        type="text" 
                        id="task" 
                        class="form-input" 
                        placeholder="e.g., Navigate to example.com"
                        required
                    />
                </div>
                <div class="form-group">
                    <label class="form-label" for="app-name">App Name</label>
                    <input 
                        type="text" 
                        id="app-name" 
                        class="form-input" 
                        value="demo"
                        placeholder="e.g., demo"
                    />
                </div>
                <div class="form-group">
                    <label class="form-label" for="start-url">Start URL</label>
                    <input 
                        type="url" 
                        id="start-url" 
                        class="form-input" 
                        value="https://example.com"
                        placeholder="https://example.com"
                    />
                </div>
                <button type="submit" class="btn btn-primary" id="submit-btn">
                    Run Task
                </button>
            </form>
            
            <div id="progress-container" class="hidden">
                <div class="progress-bar">
                    <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
                </div>
                <div class="status-message" id="status-message"></div>
            </div>
        </div>
        
        <div class="card">
            <h2 class="card-title">Previous Tasks</h2>
            <div id="tasks-list" class="tasks-list">
                <p style="color: var(--text-light);">Loading tasks...</p>
            </div>
        </div>
    </div>
    
    <script>
        // WebSocket connection
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleProgress(data);
        };
        
        // Task form
        document.getElementById('task-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const task = document.getElementById('task').value;
            const appName = document.getElementById('app-name').value || 'demo';
            const startUrl = document.getElementById('start-url').value || 'https://example.com';
            
            const submitBtn = document.getElementById('submit-btn');
            submitBtn.disabled = true;
            submitBtn.textContent = 'Running...';
            
            const progressContainer = document.getElementById('progress-container');
            const progressFill = document.getElementById('progress-fill');
            const statusMessage = document.getElementById('status-message');
            
            progressContainer.classList.remove('hidden');
            progressFill.style.width = '0%';
            statusMessage.textContent = 'Starting workflow...';
            
            try {
                const response = await fetch('/api/run', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        task: task,
                        app_name: appName,
                        start_url: startUrl,
                    }),
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Task failed');
                }
                
                const result = await response.json();
                
                if (result.success) {
                    progressFill.style.width = '100%';
                    statusMessage.innerHTML = `✅ Task completed! <a href="${result.report_url}" target="_blank" style="color: var(--primary);">View Report</a>`;
                    loadTasks();
                } else {
                    throw new Error('Task failed');
                }
            } catch (error) {
                statusMessage.textContent = `❌ Error: ${error.message}`;
                statusMessage.style.borderLeftColor = 'var(--danger)';
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Run Task';
            }
        });
        
        function handleProgress(data) {
            const progressContainer = document.getElementById('progress-container');
            const progressFill = document.getElementById('progress-fill');
            const statusMessage = document.getElementById('status-message');
            
            if (data.type === 'progress') {
                progressContainer.classList.remove('hidden');
                const percent = (data.current / data.total) * 100;
                progressFill.style.width = percent + '%';
                statusMessage.textContent = `${data.message} (${data.current}/${data.total})`;
            } else if (data.type === 'completed') {
                progressFill.style.width = '100%';
                statusMessage.innerHTML = `✅ Task completed! <a href="${data.report_url}" target="_blank" style="color: var(--primary);">View Report</a>`;
                loadTasks();
            } else if (data.type === 'error') {
                statusMessage.textContent = `❌ Error: ${data.message}`;
                statusMessage.style.borderLeftColor = 'var(--danger)';
            } else if (data.type === 'planning') {
                statusMessage.textContent = data.message;
            }
        }
        
        async function loadTasks() {
            const response = await fetch('/api/tasks');
            const data = await response.json();
            
            const tasksList = document.getElementById('tasks-list');
            
            if (data.tasks.length === 0) {
                tasksList.innerHTML = '<p style="color: var(--text-light);">No tasks yet. Run your first task above!</p>';
                return;
            }
            
            tasksList.innerHTML = data.tasks.map(task => `
                <div class="task-item">
                    <strong>${task.app}/${task.task}</strong>
                    <br>
                    <a href="${task.report_url}" target="_blank">View Report →</a>
                </div>
            `).join('');
        }
        
        // Load tasks on page load
        loadTasks();
    </script>
</body>
</html>"""
