from __future__ import annotations

import asyncio
import os
from pathlib import Path

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
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
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

        async def _run_attempt(attempt_index: int, attempt_slug: str) -> None:
            attempt_label = f"Attempt {attempt_index + 1}/{total_runs}"
            if attempt_index > 0:
                console.print(f"[cyan]↻ {attempt_label}[/cyan]")

            with console.status("[bold cyan]Planning workflow...", spinner="dots"):
                plan = await interpreter.plan(task, {"start_url": start_url})

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

                action_budget = navigation_cfg.get("action_budget", 30)
                navigator = Navigator(
                    page,
                    observer=observer,
                    default_wait_ms=navigation_cfg.get("default_wait_ms", 1000),
                    failure_store=failure_store,
                    vision_analyzer=vision_analyzer,
                    task_context=task,
                )

                with console.status("[bold cyan]Executing workflow...", spinner="dots"):
                    await navigator.execute(plan, action_budget=action_budget)

                nav_context = {
                    "page": page,
                    "action_budget": action_budget,
                    "action_count": navigator.action_count,
                }
                trace_zip_path = task_dir / "trace.zip"

                try:
                    nav_report = navigator.finalize(plan, nav_context)
                except ConstitutionViolation:
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
                console.print("[red]⚠ Navigation validation failed[/red]")
                for failure in exc.failures:
                    console.print(f"  [red]✗[/red] {failure.rule_name}: {failure.reason}")
                if attempt == total_runs - 1:
                    console.print("[red]✖ Exhausted self-heal attempts[/red]")
                    raise
                console.print("[yellow]Attempting self-heal and retry...[/yellow]")
        else:
            if last_failure:
                raise last_failure

    asyncio.run(_main())


def _slugify(text: str) -> str:
    return "-".join("".join(c.lower() if c.isalnum() else " " for c in text).split())


if __name__ == "__main__":
    app()


