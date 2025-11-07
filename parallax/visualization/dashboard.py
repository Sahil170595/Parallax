"""Interactive visualization dashboard for Parallax workflows."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from parallax.core.logging import get_logger

log = get_logger("visualization")


def generate_dashboard(base_dir: Path, output_path: Optional[Path] = None) -> Path:
    """Generate an interactive dashboard showing all workflows."""
    base_dir = Path(base_dir)
    output_path = output_path or base_dir / "dashboard.html"
    
    # Discover all workflows
    workflows = _discover_workflows(base_dir)
    
    # Generate HTML dashboard
    html = _generate_dashboard_html(workflows, base_dir)
    
    output_path.write_text(html, encoding="utf-8")
    log.info("dashboard_generated", path=str(output_path), workflows=len(workflows))
    
    return output_path


def _discover_workflows(base_dir: Path) -> List[Dict]:
    """Discover all workflows in the dataset directory."""
    workflows = []
    
    for app_dir in base_dir.iterdir():
        if app_dir.name.startswith("_") or not app_dir.is_dir():
            continue
        
        app_name = app_dir.name
        
        for task_dir in app_dir.iterdir():
            if not task_dir.is_dir():
                continue
            
            task_slug = task_dir.name
            steps_file = task_dir / "steps.jsonl"
            report_html = task_dir / "report.html"
            dataset_db = task_dir / "dataset.db"
            
            if not steps_file.exists():
                continue
            
            # Load states
            states = []
            try:
                with steps_file.open(encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            states.append(json.loads(line))
            except Exception as e:
                log.warning("failed_to_load_states", app=app_name, task=task_slug, error=str(e))
                continue
            
            # Get stats from database if available
            stats = _get_stats_from_db(dataset_db) if dataset_db.exists() else {}
            
            workflow = {
                "app": app_name,
                "task": task_slug,
                "states_count": len(states),
                "screenshots_count": sum(len(s.get("screenshots", {})) for s in states),
                "first_state": states[0] if states else None,
                "last_state": states[-1] if states else None,
                "report_html": report_html.relative_to(base_dir) if report_html.exists() else None,
                "steps_file": steps_file.relative_to(base_dir),
                "dataset_db": dataset_db.relative_to(base_dir) if dataset_db.exists() else None,
                "stats": stats,
            }
            workflows.append(workflow)
    
    return workflows


def _get_stats_from_db(db_path: Path) -> Dict:
    """Get statistics from SQLite database."""
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            
            # Count states
            cursor.execute("SELECT COUNT(*) FROM states")
            states_count = cursor.fetchone()[0]
            
            # Count screenshots
            cursor.execute("SELECT COUNT(*) FROM screenshots")
            screenshots_count = cursor.fetchone()[0]
            
            # Get unique URLs
            cursor.execute("SELECT COUNT(DISTINCT url) FROM states")
            unique_urls = cursor.fetchone()[0]
        
        return {
            "states_count": states_count,
            "screenshots_count": screenshots_count,
            "unique_urls": unique_urls,
        }
    except Exception as e:
        log.warning("failed_to_read_db", path=str(db_path), error=str(e))
        return {}


def _generate_dashboard_html(workflows: List[Dict], base_dir: Path) -> str:
    """Generate HTML dashboard."""
    
    workflows_html = ""
    for idx, workflow in enumerate(workflows):
        first_state = workflow.get("first_state", {})
        last_state = workflow.get("last_state", {})
        
        # Get screenshot preview
        screenshot_preview = ""
        if first_state and first_state.get("screenshots"):
            desktop_img = first_state["screenshots"].get("desktop") or first_state["screenshots"].get("full")
            if desktop_img:
                screenshot_preview = f'<img src="{workflow["steps_file"].parent / desktop_img}" alt="Preview" class="workflow-preview" />'
        
        badges = []
        if first_state and first_state.get("has_modal"):
            badges.append('<span class="badge badge-modal">Modal</span>')
        if first_state and first_state.get("metadata", {}).get("has_toast"):
            badges.append('<span class="badge badge-toast">Toast</span>')
        if first_state and first_state.get("metadata", {}).get("form_validity"):
            badges.append('<span class="badge badge-form">Form</span>')
        
        workflows_html += f"""
        <div class="workflow-card" onclick="openWorkflow('{workflow["report_html"]}')">
            <div class="workflow-header">
                <div class="workflow-title">
                    <h3>{workflow["app"]}</h3>
                    <p class="workflow-task">{workflow["task"]}</p>
                </div>
                <div class="workflow-badges">
                    {''.join(badges)}
                </div>
            </div>
            <div class="workflow-preview-container">
                {screenshot_preview}
            </div>
            <div class="workflow-stats">
                <div class="stat">
                    <span class="stat-label">States</span>
                    <span class="stat-value">{workflow["states_count"]}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Screenshots</span>
                    <span class="stat-value">{workflow["screenshots_count"]}</span>
                </div>
                {f'<div class="stat"><span class="stat-label">URLs</span><span class="stat-value">{workflow["stats"].get("unique_urls", "N/A")}</span></div>' if workflow["stats"].get("unique_urls") else ""}
            </div>
            {f'<div class="workflow-url"><code>{first_state.get("url", "N/A")}</code></div>' if first_state else ""}
        </div>
        """
    
    total_workflows = len(workflows)
    total_states = sum(w["states_count"] for w in workflows)
    total_screenshots = sum(w["screenshots_count"] for w in workflows)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Parallax Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        :root {{
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --secondary: #8b5cf6;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --bg: #f8fafc;
            --card: rgba(255, 255, 255, 0.95);
            --card-glass: rgba(255, 255, 255, 0.1);
            --text: #1e293b;
            --text-light: #64748b;
            --border: rgba(255, 255, 255, 0.2);
            --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 20px 25px -5px rgb(0 0 0 / 0.15), 0 10px 10px -5px rgb(0 0 0 / 0.1);
            --shadow-xl: 0 25px 50px -12px rgb(0 0 0 / 0.25);
            --radius: 20px;
            --radius-sm: 12px;
            --radius-lg: 24px;
        }}
        
        * {{
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', 'Roboto', 'SF Pro Display', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
            background-attachment: fixed;
            min-height: 100vh;
            padding: 2rem;
            color: var(--text);
            position: relative;
            overflow-x: hidden;
        }}
        
        body::before {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 50%, rgba(120, 119, 198, 0.3) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(255, 119, 198, 0.3) 0%, transparent 50%);
            pointer-events: none;
            z-index: 0;
        }}
        
        body > * {{
            position: relative;
            z-index: 1;
        }}
        
        .header {{
            max-width: 1400px;
            margin: 0 auto 2rem;
            background: var(--card-glass);
            backdrop-filter: blur(20px) saturate(180%);
            -webkit-backdrop-filter: blur(20px) saturate(180%);
            padding: 3rem;
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-xl);
            border: 1px solid var(--border);
            animation: slideDown 0.6s ease-out;
        }}
        
        @keyframes slideDown {{
            from {{
                opacity: 0;
                transform: translateY(-20px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        .header h1 {{
            font-size: 3rem;
            font-weight: 800;
            background: linear-gradient(135deg, #ffffff 0%, rgba(255, 255, 255, 0.8) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem;
            letter-spacing: -0.02em;
        }}
        
        .header p {{
            color: rgba(255, 255, 255, 0.9);
            font-size: 1.125rem;
            font-weight: 400;
        }}
        
        .header-stats {{
            display: flex;
            gap: 2rem;
            margin-top: 1.5rem;
            flex-wrap: wrap;
        }}
        
        .header-stat {{
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            color: white;
            padding: 1.5rem 2rem;
            border-radius: var(--radius);
            flex: 1;
            min-width: 150px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        
        .header-stat::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
            transition: left 0.5s;
        }}
        
        .header-stat:hover::before {{
            left: 100%;
        }}
        
        .header-stat:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
            background: rgba(255, 255, 255, 0.2);
        }}
        
        .header-stat-label {{
            font-size: 0.875rem;
            opacity: 0.9;
            margin-bottom: 0.5rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .header-stat-value {{
            font-size: 2.5rem;
            font-weight: 800;
            letter-spacing: -0.02em;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .workflows-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 2rem;
            margin-top: 2rem;
        }}
        
        @media (max-width: 768px) {{
            .workflows-grid {{
                grid-template-columns: 1fr;
                gap: 1.5rem;
            }}
            
            .header {{
                padding: 2rem;
            }}
            
            .header h1 {{
                font-size: 2rem;
            }}
            
            .header-stats {{
                flex-direction: column;
            }}
        }}
        
        .workflow-card {{
            background: var(--card-glass);
            backdrop-filter: blur(20px) saturate(180%);
            -webkit-backdrop-filter: blur(20px) saturate(180%);
            border-radius: var(--radius);
            box-shadow: var(--shadow-lg);
            overflow: hidden;
            cursor: pointer;
            border: 1px solid var(--border);
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            animation: fadeInUp 0.6s ease-out;
            animation-fill-mode: both;
        }}
        
        @keyframes fadeInUp {{
            from {{
                opacity: 0;
                transform: translateY(20px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        .workflow-card:nth-child(1) {{ animation-delay: 0.1s; }}
        .workflow-card:nth-child(2) {{ animation-delay: 0.2s; }}
        .workflow-card:nth-child(3) {{ animation-delay: 0.3s; }}
        .workflow-card:nth-child(4) {{ animation-delay: 0.4s; }}
        .workflow-card:nth-child(5) {{ animation-delay: 0.5s; }}
        .workflow-card:nth-child(n+6) {{ animation-delay: 0.6s; }}
        
        .workflow-card:hover {{
            transform: translateY(-8px) scale(1.02);
            box-shadow: var(--shadow-xl);
            border-color: rgba(255, 255, 255, 0.4);
            background: rgba(255, 255, 255, 0.15);
        }}
        
        .workflow-card:active {{
            transform: translateY(-4px) scale(1.01);
        }}
        
        .workflow-header {{
            padding: 2rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%);
        }}
        
        .workflow-title h3 {{
            font-size: 1.5rem;
            font-weight: 700;
            color: white;
            margin-bottom: 0.5rem;
            letter-spacing: -0.01em;
        }}
        
        .workflow-task {{
            color: rgba(255, 255, 255, 0.8);
            font-size: 0.875rem;
            word-break: break-word;
            line-height: 1.5;
        }}
        
        .workflow-badges {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }}
        
        .badge {{
            padding: 0.375rem 0.875rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            transition: all 0.3s ease;
        }}
        
        .badge:hover {{
            transform: scale(1.05);
        }}
        
        .badge-modal {{
            background: rgba(99, 102, 241, 0.3);
            color: #e0e7ff;
            box-shadow: 0 4px 6px rgba(99, 102, 241, 0.2);
        }}
        
        .badge-toast {{
            background: rgba(245, 158, 11, 0.3);
            color: #fef3c7;
            box-shadow: 0 4px 6px rgba(245, 158, 11, 0.2);
        }}
        
        .badge-form {{
            background: rgba(16, 185, 129, 0.3);
            color: #d1fae5;
            box-shadow: 0 4px 6px rgba(16, 185, 129, 0.2);
        }}
        
        .workflow-preview-container {{
            height: 220px;
            overflow: hidden;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }}
        
        .workflow-preview-container::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(180deg, transparent 0%, rgba(0, 0, 0, 0.1) 100%);
            pointer-events: none;
        }}
        
        .workflow-preview {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            transition: transform 0.4s ease;
            filter: drop-shadow(0 4px 6px rgba(0, 0, 0, 0.1));
        }}
        
        .workflow-card:hover .workflow-preview {{
            transform: scale(1.05);
        }}
        
        .workflow-stats {{
            padding: 1.5rem 2rem;
            display: flex;
            gap: 2rem;
            border-top: 1px solid var(--border);
            background: rgba(255, 255, 255, 0.05);
        }}
        
        .stat {{
            display: flex;
            flex-direction: column;
            gap: 0.375rem;
            flex: 1;
        }}
        
        .stat-label {{
            font-size: 0.75rem;
            color: rgba(255, 255, 255, 0.7);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 500;
        }}
        
        .stat-value {{
            font-size: 1.5rem;
            font-weight: 800;
            color: white;
            letter-spacing: -0.02em;
        }}
        
        .workflow-url {{
            padding: 1rem 2rem;
            background: rgba(0, 0, 0, 0.1);
            border-top: 1px solid var(--border);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
        }}
        
        .workflow-url code {{
            font-size: 0.75rem;
            color: rgba(255, 255, 255, 0.8);
            word-break: break-all;
            font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', monospace;
        }}
        
        .empty-state {{
            text-align: center;
            padding: 4rem 2rem;
            background: var(--card-glass);
            backdrop-filter: blur(20px) saturate(180%);
            -webkit-backdrop-filter: blur(20px) saturate(180%);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-lg);
            border: 1px solid var(--border);
        }}
        
        .empty-state h2 {{
            font-size: 1.75rem;
            color: white;
            margin-bottom: 0.5rem;
            font-weight: 700;
        }}
        
        .empty-state p {{
            color: rgba(255, 255, 255, 0.8);
            font-size: 1.125rem;
        }}
        
        /* Smooth scroll */
        html {{
            scroll-behavior: smooth;
        }}
        
        /* Loading animation */
        @keyframes pulse {{
            0%, 100% {{
                opacity: 1;
            }}
            50% {{
                opacity: 0.5;
            }}
        }}
        
        .workflow-card.loading {{
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Parallax Dashboard</h1>
        <p>Interactive visualization of all captured workflows</p>
        <div class="header-stats">
            <div class="header-stat">
                <div class="header-stat-label">Total Workflows</div>
                <div class="header-stat-value">{total_workflows}</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-label">Total States</div>
                <div class="header-stat-value">{total_states}</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-label">Total Screenshots</div>
                <div class="header-stat-value">{total_screenshots}</div>
            </div>
        </div>
    </div>
    
    <div class="container">
        {f'<div class="workflows-grid">{workflows_html}</div>' if workflows else '<div class="empty-state"><h2>No workflows found</h2><p>Run some tasks to see them here!</p></div>'}
    </div>
    
    <script>
        function openWorkflow(path) {{
            if (path) {{
                window.open(path, '_blank');
            }}
        }}
    </script>
</body>
</html>"""
    
    return html


def serve_dashboard(base_dir: Path, port: int = 8080, host: str = "localhost") -> None:
    """Serve the dashboard via HTTP server."""
    try:
        import http.server
        import socketserver
        from urllib.parse import urlparse
        
        class DashboardHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(base_dir), **kwargs)
            
            def end_headers(self):
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                super().end_headers()
        
        with socketserver.TCPServer((host, port), DashboardHandler) as httpd:
            dashboard_path = generate_dashboard(base_dir)
            print(f"\n🚀 Parallax Dashboard running at:")
            print(f"   http://{host}:{port}/dashboard.html")
            print(f"\n📊 Found {len(_discover_workflows(base_dir))} workflows")
            print(f"\nPress Ctrl+C to stop\n")
            httpd.serve_forever()
    except ImportError:
        log.error("http_server_not_available", message="Python http.server module not available")
        raise
    except OSError as e:
        if e.errno == 98:  # Address already in use
            log.error("port_in_use", port=port, message="Port already in use, try a different port")
        else:
            raise

