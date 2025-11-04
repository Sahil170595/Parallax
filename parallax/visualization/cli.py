"""CLI for visualization dashboard."""
import typer
from pathlib import Path

from parallax.visualization.dashboard import generate_dashboard, serve_dashboard

app = typer.Typer()


@app.command()
def generate(
    base_dir: str = "datasets",
    output: str = "datasets/dashboard.html",
) -> None:
    """Generate a static dashboard HTML file."""
    base_path = Path(base_dir)
    output_path = Path(output)
    
    dashboard_path = generate_dashboard(base_path, output_path)
    print(f"✅ Dashboard generated: {dashboard_path}")
    print(f"   Open it in your browser to view all workflows!")


@app.command()
def serve(
    base_dir: str = "datasets",
    port: int = 8080,
    host: str = "localhost",
) -> None:
    """Serve the dashboard via HTTP server."""
    base_path = Path(base_dir)
    serve_dashboard(base_path, port=port, host=host)


if __name__ == "__main__":
    app()

