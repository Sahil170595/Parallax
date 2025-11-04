from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from parallax.core.schemas import UIState


def write_markdown_report(path: Path, states: Iterable[UIState]) -> Path:
    report = path / "report.md"
    states_list = list(states)
    lines = ["# Workflow Report", ""]
    lines.append(f"Total steps: {len(states_list)}")
    lines.append("")
    
    for idx, s in enumerate(states_list):
        lines.append(f"## Step {idx:02d} — {s.description}")
        lines.append(f"- URL: `{s.url}`")
        if s.action:
            lines.append(f"- Action: `{s.action}`")
        if s.has_modal:
            lines.append("- **Modal/Dialog present**")
        if s.metadata.get("has_toast"):
            lines.append("- **Toast visible**")
        img = s.screenshots.get("desktop")
        if img:
            lines.append(f"![Step {idx:02d}]({img})")
        lines.append("")
    
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def write_html_report(path: Path, states: Iterable[UIState], trace_zip: str = "trace.zip") -> Path:
    report = path / "report.html"
    states_list = list(states)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Parallax Workflow Report</title>
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
            --bg-dark: #1e293b;
            --card: #ffffff;
            --card-dark: #334155;
            --text: #1e293b;
            --text-light: #64748b;
            --border: #e2e8f0;
            --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
            --radius: 12px;
            --radius-sm: 8px;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', 'Roboto', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem;
            color: var(--text);
            line-height: 1.6;
        }}
        
        .header {{
            max-width: 1400px;
            margin: 0 auto 2rem;
            background: var(--card);
            padding: 2rem;
            border-radius: var(--radius);
            box-shadow: var(--shadow-lg);
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem;
        }}
        
        .header .subtitle {{
            color: var(--text-light);
            font-size: 1.1rem;
            margin-bottom: 1.5rem;
        }}
        
        .stats {{
            display: flex;
            gap: 1.5rem;
            flex-wrap: wrap;
            margin-top: 1.5rem;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: var(--radius-sm);
            flex: 1;
            min-width: 150px;
        }}
        
        .stat-label {{
            font-size: 0.875rem;
            opacity: 0.9;
            margin-bottom: 0.25rem;
        }}
        
        .stat-value {{
            font-size: 1.75rem;
            font-weight: 700;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .timeline {{
            position: relative;
            padding-left: 2rem;
        }}
        
        .timeline::before {{
            content: '';
            position: absolute;
            left: 0.5rem;
            top: 0;
            bottom: 0;
            width: 2px;
            background: linear-gradient(180deg, var(--primary) 0%, var(--secondary) 100%);
        }}
        
        .step {{
            position: relative;
            background: var(--card);
            margin-bottom: 2rem;
            padding: 2rem;
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            transition: all 0.3s ease;
            border: 1px solid var(--border);
        }}
        
        .step:hover {{
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }}
        
        .step::before {{
            content: '';
            position: absolute;
            left: -2.5rem;
            top: 2rem;
            width: 1rem;
            height: 1rem;
            background: var(--primary);
            border-radius: 50%;
            border: 3px solid var(--card);
            box-shadow: 0 0 0 2px var(--primary);
        }}
        
        .step-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1rem;
            flex-wrap: wrap;
            gap: 1rem;
        }}
        
        .step-number {{
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--primary);
            background: rgba(99, 102, 241, 0.1);
            padding: 0.375rem 0.75rem;
            border-radius: var(--radius-sm);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .step-description {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text);
            flex: 1;
        }}
        
        .badges {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-top: 0.5rem;
        }}
        
        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 0.375rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            transition: all 0.2s ease;
        }}
        
        .badge:hover {{
            transform: scale(1.05);
        }}
        
        .badge-modal {{
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: white;
        }}
        
        .badge-toast {{
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
        }}
        
        .badge-loading {{
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            color: white;
        }}
        
        .badge-form-valid {{
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
        }}
        
        .badge-form-invalid {{
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white;
        }}
        
        .metadata {{
            margin: 1.5rem 0;
            padding: 1rem;
            background: var(--bg);
            border-radius: var(--radius-sm);
            font-size: 0.875rem;
        }}
        
        .metadata-item {{
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .metadata-item:last-child {{
            margin-bottom: 0;
        }}
        
        .metadata-label {{
            font-weight: 600;
            color: var(--text-light);
            min-width: 80px;
        }}
        
        .metadata-value {{
            color: var(--text);
            font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
            font-size: 0.8125rem;
            background: white;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            border: 1px solid var(--border);
        }}
        
        .screenshots {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
            margin-top: 1.5rem;
        }}
        
        .screenshot-container {{
            position: relative;
            border-radius: var(--radius-sm);
            overflow: hidden;
            border: 1px solid var(--border);
            background: var(--bg);
            transition: all 0.3s ease;
        }}
        
        .screenshot-container:hover {{
            transform: scale(1.02);
            box-shadow: var(--shadow-lg);
        }}
        
        .screenshot-label {{
            position: absolute;
            top: 0.5rem;
            left: 0.5rem;
            background: rgba(0, 0, 0, 0.7);
            color: white;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: capitalize;
            z-index: 1;
        }}
        
        .screenshot {{
            width: 100%;
            height: auto;
            display: block;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        
        .screenshot:hover {{
            opacity: 0.9;
        }}
        
        .trace-link {{
            margin-top: 1.5rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border);
        }}
        
        .trace-link a {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--primary);
            text-decoration: none;
            font-weight: 600;
            padding: 0.75rem 1.5rem;
            background: rgba(99, 102, 241, 0.1);
            border-radius: var(--radius-sm);
            transition: all 0.2s ease;
        }}
        
        .trace-link a:hover {{
            background: rgba(99, 102, 241, 0.2);
            transform: translateY(-1px);
        }}
        
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            backdrop-filter: blur(4px);
        }}
        
        .modal.active {{
            display: flex;
            align-items: center;
            justify-content: center;
            animation: fadeIn 0.3s ease;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        
        .modal-content {{
            max-width: 90vw;
            max-height: 90vh;
            border-radius: var(--radius);
            overflow: hidden;
            box-shadow: var(--shadow-lg);
            animation: scaleIn 0.3s ease;
        }}
        
        @keyframes scaleIn {{
            from {{ transform: scale(0.9); opacity: 0; }}
            to {{ transform: scale(1); opacity: 1; }}
        }}
        
        .modal-content img {{
            width: 100%;
            height: auto;
            display: block;
        }}
        
        .close {{
            position: absolute;
            top: 1rem;
            right: 1rem;
            color: white;
            font-size: 2rem;
            font-weight: bold;
            cursor: pointer;
            background: rgba(0, 0, 0, 0.5);
            width: 2.5rem;
            height: 2.5rem;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
        }}
        
        .close:hover {{
            background: rgba(0, 0, 0, 0.8);
            transform: rotate(90deg);
        }}
        
        @media (max-width: 768px) {{
            body {{
                padding: 1rem;
            }}
            
            .header h1 {{
                font-size: 2rem;
            }}
            
            .step {{
                padding: 1.5rem;
            }}
            
            .screenshots {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Parallax Workflow Report</h1>
        <p class="subtitle">Autonomous multi-agent system workflow capture</p>
        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">Total Steps</div>
                <div class="stat-value">{len(states_list)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">States Captured</div>
                <div class="stat-value">{len(states_list)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Screenshots</div>
                <div class="stat-value">{sum(len(s.screenshots) for s in states_list)}</div>
            </div>
        </div>
    </div>
    
    <div class="container">
        <div class="timeline">
"""
    
    for idx, s in enumerate(states_list):
        badges = []
        if s.has_modal:
            badges.append('<span class="badge badge-modal">Modal</span>')
        if s.metadata.get("has_toast"):
            badges.append('<span class="badge badge-toast">Toast</span>')
        if s.metadata.get("has_loader"):
            badges.append('<span class="badge badge-loading">Loading</span>')
        if s.metadata.get("form_validity") is True:
            badges.append('<span class="badge badge-form-valid">Form Valid</span>')
        elif s.metadata.get("form_validity") is False:
            badges.append('<span class="badge badge-form-invalid">Form Invalid</span>')
        
        action_html = f'''<div class="metadata-item">
                <span class="metadata-label">Action:</span>
                <code class="metadata-value">{s.action}</code>
            </div>''' if s.action else ''
        
        badges_html = f'<div class="badges">{"".join(badges)}</div>' if badges else ''
        
        screenshots_html = ""
        if s.screenshots:
            screenshots_html = '<div class="screenshots">'
            for viewport, filename in s.screenshots.items():
                screenshots_html += f'''
                <div class="screenshot-container">
                    <span class="screenshot-label">{viewport}</span>
                    <img src="{filename}" alt="Step {idx:02d} - {viewport}" class="screenshot" onclick="openModal(this.src)" />
                </div>'''
            screenshots_html += '</div>'
        
        html += f"""
            <div class="step">
                <div class="step-header">
                    <div>
                        <div class="step-number">Step {idx:02d}</div>
                        <div class="step-description">{s.description}</div>
                        {badges_html}
                    </div>
                </div>
                <div class="metadata">
                    <div class="metadata-item">
                        <span class="metadata-label">URL:</span>
                        <code class="metadata-value">{s.url}</code>
                    </div>
                    {action_html}
                </div>
                {screenshots_html}
            </div>
"""
    
    html += f"""
        </div>
        <div class="trace-link">
            <a href="{trace_zip}">
                <span>📦</span>
                <span>Download trace.zip</span>
            </a>
        </div>
    </div>
    
    <div id="modal" class="modal" onclick="closeModal(event)">
        <span class="close" onclick="closeModal(event)">&times;</span>
        <div class="modal-content">
            <img id="modal-img" src="" alt="Screenshot">
        </div>
    </div>
    
    <script>
        function openModal(src) {{
            const modal = document.getElementById('modal');
            const modalImg = document.getElementById('modal-img');
            modalImg.src = src;
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }}
        
        function closeModal(event) {{
            if (event.target.id === 'modal' || event.target.classList.contains('close')) {{
                const modal = document.getElementById('modal');
                modal.classList.remove('active');
                document.body.style.overflow = 'auto';
            }}
        }}
        
        document.addEventListener('keydown', function(event) {{
            if (event.key === 'Escape') {{
                closeModal({{ target: {{ id: 'modal' }} }});
            }}
        }});
    </script>
</body>
</html>
"""
    
    report.write_text(html, encoding="utf-8")
    return report


