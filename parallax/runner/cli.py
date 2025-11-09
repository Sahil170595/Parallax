from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import typer
import yaml
from playwright.async_api import async_playwright

try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    pass  # python-dotenv not installed, skip

from parallax.core.config import ParallaxConfig
from parallax.core.constitution import ConstitutionViolation, FailureStore
from parallax.core.completion import CompletionValidationError, validate_completion
from parallax.core.plan_overrides import apply_site_overrides
from parallax.core.logging import configure_logging, get_logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn, TaskProgressColumn
from rich.markdown import Markdown
from parallax.core.schemas import ExecutionPlan
from parallax.agents.archivist import Archivist
from parallax.agents.interpreter import Interpreter
from parallax.agents.navigator import Navigator
from parallax.agents.observer import Observer
from parallax.agents.strategy_generator import StrategyGenerator
from parallax.llm.anthropic_provider import AnthropicPlanner
from parallax.llm.local_provider import LocalPlanner
from parallax.llm.openai_provider import OpenAIPlanner
from parallax.observer.detectors import Detectors
from parallax.core.metrics import ensure_metrics_server
from parallax.core.trace import TraceController


app = typer.Typer()
log = get_logger("cli")
console = Console()

# Graceful shutdown handling
shutdown_event = asyncio.Event()

def signal_handler(sig: int, frame) -> None:
    """Handle shutdown signals gracefully."""
    signal_name = signal.Signals(sig).name if hasattr(signal.Signals, sig) else str(sig)
    log.info("shutdown_signal_received", signal=signal_name)
    shutdown_event.set()
    console.print("\n[yellow]Shutdown signal received. Finishing current task...[/yellow]")

# Register signal handlers
if sys.platform != "win32":
    signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def _load_config() -> ParallaxConfig:
    cfg_path = Path(os.getenv("PARALLAX_CONFIG", "configs/config.yaml"))
    return ParallaxConfig.from_yaml(cfg_path)


def _planner_from_config(cfg: ParallaxConfig):
    provider = os.getenv("PARALLAX_PROVIDER", cfg.provider)
    if provider == "openai":
        return OpenAIPlanner()
    if provider == "anthropic":
        return AnthropicPlanner()
    if provider == "local":
        return LocalPlanner()
    # auto: prefer OpenAI, Anthropic, then Local
    planner_factories = (OpenAIPlanner, AnthropicPlanner, LocalPlanner)
    last_error: Exception | None = None
    for factory in planner_factories:
        try:
            return factory()
        except Exception as exc:  # pragma: no cover - depends on env config
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError("No LLM planner available")


def _validate_url(url: str) -> str:
    """Validate URL has scheme and netloc."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise typer.BadParameter(
            f"Invalid URL: '{url}'. URL must include scheme (http:// or https://). "
            f"Example: 'https://example.com'"
        )
    return url


@app.command()
def run(
    task: str,
    app_name: str = "linear",
    start_url: str = typer.Option(
        "https://linear.app",
        "--start-url",
        callback=_validate_url,
        help="Starting URL for the workflow (must include http:// or https://)",
    ),
    multi_viewport: Optional[bool] = typer.Option(
        None,
        "--multi-viewport/--single-viewport",
        help="Capture tablet/mobile screenshots in addition to desktop (default from config).",
    ),
) -> None:
    """Run a Parallax workflow for a natural-language task."""

    async def _main():
        configure_logging()
        
        # Beautiful header
        console.print("\n")
        console.print(Panel.fit(
            f"[bold cyan]🎯 Parallax[/bold cyan] - [dim]Autonomous workflow capture[/dim]\n"
            f"[bold]Task:[/bold] {task}\n"
            f"[bold]App:[/bold] {app_name} | [bold]URL:[/bold] {start_url}",
            border_style="cyan",
            padding=(1, 2)
        ))
        console.print("\n")
        
        cfg = _load_config()
        if multi_viewport is not None:
            cfg.capture.multi_viewport = multi_viewport
        ensure_metrics_server(cfg.metrics.prometheus_port)
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
        
        # Initialize vision analyzer if enabled
        vision_analyzer = None
        vision_enabled = cfg.vision.enabled
        if vision_enabled:
            try:
                from parallax.vision.analyzer import VisionAnalyzer
                vision_provider = cfg.vision.provider
                vision_analyzer = VisionAnalyzer(provider=vision_provider)
                log.info("vision_analyzer_enabled", provider=vision_provider)
            except Exception as e:
                log.warning(
                    "vision_analyzer_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    provider=vision_provider,
                )

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

        async def _run_attempt(attempt_index: int, attempt_slug: str) -> None:
            nonlocal start_url_current, action_budget_override, plan_context_overrides

            attempt_label = f"Attempt {attempt_index + 1}/{total_runs}"
            if attempt_index > 0:
                console.print(f"[cyan]↻ {attempt_label}[/cyan]")

            plan_context: Dict[str, Any] = {
                "start_url": start_url_current,
                "retry": attempt_index,
            }
            if failure_history:
                plan_context["failure_history"] = failure_history[-10:]
            if plan_context_overrides:
                plan_context.update(plan_context_overrides)

            with console.status("[bold cyan]Planning workflow...", spinner="dots"):
                plan = await interpreter.plan(task, plan_context)
                plan = apply_site_overrides(plan, start_url_current)

            console.print(f"[green]✓[/green] Generated [bold]{len(plan.steps)}[/bold] steps")

            async with async_playwright() as p:
                browser_type = cfg.playwright.project
                headless = cfg.playwright.headless
                channel = cfg.playwright.channel
                user_data_dir = cfg.playwright.user_data_dir
                
                browser = None  # Will be None for persistent contexts
                
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

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    TextColumn("[dim]{task.completed}/{task.total}[/dim]"),
                    TimeRemainingColumn(),
                    console=console,
                ) as progress:
                    task_id = progress.add_task(
                        "[cyan]Executing workflow...", total=total_steps
                    )

                    async def progress_callback(idx: int, total: int, _step: Any) -> None:
                        progress.update(
                            task_id,
                            total=max(total, 1),
                            completed=min(idx, total),
                        )

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

                    try:
                        await navigator.execute(plan, action_budget=action_budget)
                    finally:
                        progress.update(
                            task_id,
                            completed=min(navigator.action_count, total_steps),
                        )

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
                    with console.status("[bold cyan]Saving trace...", spinner="dots"):
                        await tracer.stop(trace_zip_path)
                    await context.close()
                    if browser:
                        await browser.close()
                    raise

                if nav_report.warnings:
                    console.print("[yellow]⚠ Navigation warnings[/yellow]")
                    for warning in nav_report.warnings:
                        console.print(f"  [yellow]-[/yellow] {warning.rule_name}: {warning.reason}")

                try:
                    validate_completion(
                        plan,
                        observer.states,
                        min_targets=cfg.completion.min_targets,
                    )
                except CompletionValidationError as exc:
                    console.print("\n[red]❌ Completion validation failed[/red]")
                    for item in exc.missing:
                        console.print(f"  [red]-[/red] Missing navigation: {item}")
                    raise

                arch = Archivist(datasets_dir, failure_store=failure_store)

                with console.status("[bold cyan]Saving trace...", spinner="dots"):
                    await tracer.stop(trace_zip_path)

                with console.status("[bold cyan]Generating reports...", spinner="dots"):
                    root = arch.write_states(app_name, attempt_slug, observer.states, trace_zip="trace.zip")

                from parallax.core.metrics import workflow_success, states_per_workflow, trace_size_bytes

                workflow_success.inc()
                states_per_workflow.observe(len(observer.states))
                if trace_zip_path.exists():
                    trace_size_bytes.observe(trace_zip_path.stat().st_size)

                console.print("\n")
                summary_table = Table(show_header=True, header_style="bold cyan", box=None)
                summary_table.add_column("Metric", style="dim")
                summary_table.add_column("Value", justify="right", style="bold")

                summary_table.add_row("Steps Executed", str(len(plan.steps)))
                summary_table.add_row("States Captured", str(len(observer.states)))
                summary_table.add_row("Screenshots", str(sum(len(s.screenshots) for s in observer.states)))
                if trace_zip_path.exists():
                    size_mb = trace_zip_path.stat().st_size / (1024 * 1024)
                    summary_table.add_row("Trace Size", f"{size_mb:.2f} MB")

                title = "[bold green]✓ Workflow Complete[/bold green]"
                if attempt_index > 0:
                    title = "[bold green]✓ Workflow Recovered[/bold green]"
                console.print(Panel(summary_table, title=title, border_style="green"))

                console.print(f"\n[bold cyan]📁 Dataset:[/bold cyan] {root}")
                console.print(f"[bold cyan]📄 Report:[/bold cyan] {root / 'report.html'}")
                console.print(f"[bold cyan]📦 Trace:[/bold cyan] {trace_zip_path}\n")

                log.info("dataset_saved", path=str(root), states=len(observer.states))

                await context.close()
                if browser:
                    await browser.close()

        last_failure: ConstitutionViolation | None = None
        for attempt in range(total_runs):
            # Check for shutdown signal
            if shutdown_event.is_set():
                console.print("\n[yellow]Shutdown requested. Stopping workflow...[/yellow]")
                log.info("workflow_cancelled_by_signal", attempt=attempt + 1)
                return
            
            attempt_slug = slug if attempt == 0 else f"{slug}-retry-{attempt}"
            try:
                await _run_attempt(attempt, attempt_slug)
                break
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
                console.print("\n[red]❌ Navigation validation failed[/red]")
                console.print("[dim]The workflow did not meet quality requirements.[/dim]\n")
                
                for failure in exc.failures:
                    console.print(f"  [red]✗[/red] [bold]{failure.rule_name}[/bold]")
                    console.print(f"      [dim]{failure.reason}[/dim]")
                    
                    # Add recovery suggestions based on rule
                    suggestions = _get_recovery_suggestions(failure.rule_name)
                    if suggestions:
                        console.print(f"      [yellow]💡 Suggestions:[/yellow]")
                        for suggestion in suggestions:
                            console.print(f"         • {suggestion}")
                    console.print()

                recovery_info = getattr(exc, "recovery", {})
                adjustments = recovery_info.get("adjustments") or {}
                recovered = recovery_info.get("recovered", False)

                notes = adjustments.get("notes") or []
                if notes:
                    console.print("[cyan]Self-heal actions:[/cyan]")
                    for note in notes:
                        console.print(f"  [cyan]-[/cyan] {note}")

                if adjustments.get("start_url"):
                    start_url_current = adjustments["start_url"]

                if adjustments.get("plan_context"):
                    plan_context_overrides.update(adjustments["plan_context"])

                if adjustments.get("action_budget"):
                    action_budget_override = adjustments["action_budget"]

                if attempt == total_runs - 1:
                    console.print("[red]✖ Exhausted self-heal attempts[/red]")
                    console.print("[yellow]💡 Try:[/yellow] Review the task description or check if the website structure has changed.\n")
                    raise
                if not recovered and not adjustments:
                    console.print("[yellow]No automated recovery steps were available.[/yellow]")
                console.print("[yellow]🔄 Attempting self-heal and retry...[/yellow]\n")
        else:
            if last_failure:
                raise last_failure

    asyncio.run(_main())


def _slugify(text: str) -> str:
    return "-".join("".join(c.lower() if c.isalnum() else " " for c in text).split())


def _get_recovery_suggestions(rule_name: str) -> list[str]:
    """Get recovery suggestions based on failed rule."""
    suggestions_map = {
        "plan_structure": [
            "Check if the task description is clear and actionable",
            "Try rephrasing the task with more specific instructions",
        ],
        "plan_non_empty": [
            "Add more detail so the planner can infer at least one actionable step",
        ],
        "plan_step_validity": [
            "Check if the task uses supported actions (navigate, click, type, submit)",
            "Try breaking down complex tasks into simpler steps",
        ],
        "navigation_success": [
            "Check if the website is accessible and responsive",
            "Verify that the start URL is correct",
            "Try increasing the action budget in config.yaml",
        ],
        "action_budget": [
            "Increase action_budget in config.yaml",
            "Simplify the task to require fewer steps",
        ],
        "no_auth_redirects": [
            "Ensure the account has access and is already authenticated",
            "Consider providing login steps in the task description",
        ],
        "state_captured": [
            "Check if screenshots directory is writable",
            "Verify Playwright browser installation",
        ],
        "screenshot_quality": [
            "Ensure the page finished loading before actions continue",
            "Check for modal dialogs blocking the viewport",
        ],
        "dataset_created": [
            "Check if datasets directory is writable",
            "Verify disk space is available",
        ],
        "dataset_files": [
            "Verify the archivist has permission to write report files",
            "Look for antivirus or sync tools locking files during write",
        ],
        "dataset_data_integrity": [
            "Check if the workflow captured the expected number of states",
            "Ensure no external process is modifying dataset files mid-run",
        ],
    }
    return suggestions_map.get(rule_name, [])


if __name__ == "__main__":
    app()
