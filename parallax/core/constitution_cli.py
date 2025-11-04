"""CLI tool for analyzing constitution failures."""
from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from parallax.core.constitution import FailureStore

app = typer.Typer()
console = Console()


@app.command()
def stats(failures_dir: str = "datasets/_constitution_failures") -> None:
    """Show statistics about constitution failures."""
    store = FailureStore(Path(failures_dir))
    stats_data = store.get_failure_statistics()
    
    console.print("\n[bold cyan]📊 Constitution Failure Statistics[/bold cyan]\n")
    
    # Overall stats
    table = Table(title="Overall Statistics", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right", style="bold")
    
    table.add_row("Total Failures", str(stats_data.get("total_failures", 0)))
    table.add_row("By Agent", str(len(stats_data.get("by_agent", {}))))
    table.add_row("By Rule", str(len(stats_data.get("by_rule", {}))))
    
    console.print(table)
    console.print("\n")
    
    # By agent
    if stats_data.get("by_agent"):
        agent_table = Table(title="Failures by Agent", show_header=True, header_style="bold cyan")
        agent_table.add_column("Agent", style="dim")
        agent_table.add_column("Count", justify="right", style="bold")
        
        for agent, count in sorted(stats_data["by_agent"].items(), key=lambda x: -x[1]):
            agent_table.add_row(agent, str(count))
        
        console.print(agent_table)
        console.print("\n")
    
    # By rule
    if stats_data.get("by_rule"):
        rule_table = Table(title="Failures by Rule", show_header=True, header_style="bold cyan")
        rule_table.add_column("Rule", style="dim")
        rule_table.add_column("Count", justify="right", style="bold")
        
        for rule, count in sorted(stats_data["by_rule"].items(), key=lambda x: -x[1]):
            rule_table.add_row(rule, str(count))
        
        console.print(rule_table)


@app.command()
def list(agent: str = None, limit: int = 20, failures_dir: str = "datasets/_constitution_failures") -> None:
    """List recent constitution failures."""
    store = FailureStore(Path(failures_dir))
    failures = store.get_failures(agent=agent, limit=limit)
    
    if not failures:
        console.print("[green]✓ No failures recorded[/green]")
        return
    
    console.print(f"\n[bold cyan]📋 Recent Failures[/bold cyan] (showing {len(failures)})\n")
    
    for idx, failure in enumerate(failures[-limit:], 1):
        console.print(f"[bold]{idx}. {failure.get('agent', 'unknown')}[/bold]")
        console.print(f"   Time: {failure.get('timestamp', 'unknown')}")
        console.print(f"   Passed: {'[green]Yes[/green]' if failure.get('passed') else '[red]No[/red]'}")
        
        if failure.get("failures"):
            console.print("   [red]Critical Failures:[/red]")
            for f in failure["failures"]:
                console.print(f"     - {f.get('rule_name')}: {f.get('reason')}")
        
        if failure.get("warnings"):
            console.print("   [yellow]Warnings:[/yellow]")
            for w in failure["warnings"]:
                console.print(f"     - {w.get('rule_name')}: {w.get('reason')}")
        
        console.print("")


if __name__ == "__main__":
    app()

