from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, Optional

import typer
import yaml
from playwright.async_api import async_playwright

try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    pass  # python-dotenv not installed, skip

from parallax.core.constitution import ConstitutionViolation, FailureStore
from parallax.core.logging import configure_logging, get_logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn, TaskProgressColumn
from rich.markdown import Markdown
from parallax.core.schemas import ExecutionPlan
from parallax.agents.interpreter import Interpreter
from parallax.agents.navigator import Navigator
from parallax.agents.observer import Observer
from parallax.observer.detectors import Detectors
from parallax.agents.archivist import Archivist
from parallax.llm.openai_provider import OpenAIPlanner
from parallax.llm.local_provider import LocalPlanner
from parallax.core.trace import TraceController


app = typer.Typer()
log = get_logger("cli")
console = Console()


def _load_config() -> dict:
    cfg_path = Path("configs/config.yaml")
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


def _planner_from_config(cfg: dict):
    provider = os.getenv("PARALLAX_PROVIDER", cfg.get("provider", "auto"))
    if provider == "openai":
        return OpenAIPlanner()
    if provider == "local":
        return LocalPlanner()
    # auto: prefer OpenAI, then Local
    try:
        return OpenAIPlanner()
    except Exception:
        return LocalPlanner()


@app.command()
def run(task: str, app_name: str = "linear", start_url: str = "https://linear.app") -> None:
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
        planner = _planner_from_config(cfg)

        datasets_dir = Path(cfg.get("output", {}).get("base_dir", "datasets"))
        failure_store = FailureStore(datasets_dir / "_constitution_failures")
        interpreter = Interpreter(planner, failure_store=failure_store)
        
        # Initialize vision analyzer if enabled
        vision_analyzer = None
        vision_enabled = cfg.get("vision", {}).get("enabled", False)
        if vision_enabled:
            try:
                from parallax.vision.analyzer import VisionAnalyzer
                vision_provider = cfg.get("vision", {}).get("provider", "openai")
                vision_analyzer = VisionAnalyzer(provider=vision_provider)
                log.info("vision_analyzer_enabled", provider=vision_provider)
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

            console.print(f"[green]✓[/green] Generated [bold]{len(plan.steps)}[/bold] steps")

            async with async_playwright() as p:
                browser_type = cfg.get("playwright", {}).get("project", "chromium")
                headless = cfg.get("playwright", {}).get("headless", False)
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
                        default_wait_ms=navigation_cfg.get("default_wait_ms", 1000),
                        scroll_margin_px=navigation_cfg.get("scroll_margin_px", 64),
                        failure_store=failure_store,
                        vision_analyzer=vision_analyzer,
                        task_context=task,
                        progress_callback=progress_callback,
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
                    await browser.close()
                    raise

                if nav_report.warnings:
                    console.print("[yellow]⚠ Navigation warnings[/yellow]")
                    for warning in nav_report.warnings:
                        console.print(f"  [yellow]-[/yellow] {warning.rule_name}: {warning.reason}")

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
                await browser.close()

        last_failure: ConstitutionViolation | None = None
        for attempt in range(total_runs):
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
                    del failure_history[:-20]
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
