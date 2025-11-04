"""FastAPI web server for Parallax UI."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# Fix for Windows + Python 3.13 asyncio subprocess issue
if sys.platform == "win32" and sys.version_info >= (3, 13):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from playwright.async_api import async_playwright

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from parallax.core.constitution import ConstitutionViolation, FailureStore
from parallax.core.logging import configure_logging, get_logger
from parallax.core.schemas import ExecutionPlan
from parallax.agents.interpreter import Interpreter
from parallax.agents.navigator import Navigator
from parallax.agents.observer import Observer
from parallax.observer.detectors import Detectors
from parallax.agents.archivist import Archivist
from parallax.llm.openai_provider import OpenAIPlanner
from parallax.llm.anthropic_provider import AnthropicPlanner
from parallax.llm.local_provider import LocalPlanner
from parallax.core.trace import TraceController


app = FastAPI(title="Parallax Web UI")
log = get_logger("web")
configure_logging()

# Configuration
CONFIG_PATH = Path("configs/config.yaml")
DATASETS_DIR = Path("datasets")


def _load_config() -> dict:
    """Load configuration from YAML file."""
    if not CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _planner_from_config(cfg: dict):
    """Get planner from config."""
    provider = os.getenv("PARALLAX_PROVIDER", cfg.get("provider", "auto"))
    if provider == "openai":
        return OpenAIPlanner()
    if provider == "anthropic":
        return AnthropicPlanner()
    if provider == "local":
        return LocalPlanner()
    # auto: prefer OpenAI, then Anthropic, then Local
    try:
        return OpenAIPlanner()
    except Exception:
        try:
            return AnthropicPlanner()
        except Exception:
            return LocalPlanner()


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
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


class TaskRequest(BaseModel):
    """Task request model."""
    task: str
    app_name: str = "demo"
    start_url: str = "https://example.com"


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
        
        datasets_dir = Path(cfg.get("output", {}).get("base_dir", "datasets"))
        failure_store = FailureStore(datasets_dir / "_constitution_failures")
        interpreter = Interpreter(planner, failure_store=failure_store)

        vision_analyzer = None
        vision_enabled = cfg.get("vision", {}).get("enabled", False)
        if vision_enabled:
            try:
                from parallax.vision.analyzer import VisionAnalyzer

                vision_provider = cfg.get("vision", {}).get("provider", "openai")
                vision_analyzer = VisionAnalyzer(provider=vision_provider)
            except Exception as e:
                log.warning("vision_analyzer_failed", error=str(e))

        navigation_cfg = cfg.get("navigation", {})
        heal_value = navigation_cfg.get("self_heal_attempts", 1)
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

            await manager.send_progress({
                "type": "planned",
                "task_id": task_id,
                "attempt": attempt_number,
                "steps": len(plan.steps),
            })

            async with async_playwright() as p:
                browser_type = cfg.get("playwright", {}).get("project", "chromium")
                headless = cfg.get("playwright", {}).get("headless", True)
                browser = await getattr(p, browser_type).launch(headless=headless)
                context = await browser.new_context()
                page = await context.new_page()

                detectors = Detectors(cfg.get("observer", {}), vision_analyzer=vision_analyzer)
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

                action_budget = action_budget_override or navigation_cfg.get("action_budget", 30)
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
                    default_wait_ms=navigation_cfg.get("default_wait_ms", 1000),
                    failure_store=failure_store,
                    vision_analyzer=vision_analyzer,
                    task_context=task,
                    progress_callback=progress_callback,
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

                    await tracer.stop(trace_zip_path)
                    await context.close()
                    await browser.close()
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

                await tracer.stop(trace_zip_path)

                archivist = Archivist(datasets_dir, failure_store=failure_store)
                root = archivist.write_states(app_name, attempt_slug, observer.states, trace_zip="trace.zip")

                await context.close()
                await browser.close()

                result = {
                    "success": True,
                    "task_id": task_id,
                    "path": str(root),
                    "report_url": f"/api/reports/{app_name}/{attempt_slug}",
                    "states": len(observer.states),
                }

                await manager.send_progress({"type": "completed", **result})
                return result

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
                    del failure_history[:-20]

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

    except Exception as e:
        await manager.send_progress({
            "type": "error",
            "task_id": task_id,
            "message": f"Workflow failed: {str(e)}",
        })
        raise HTTPException(status_code=500, detail=str(e))


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

