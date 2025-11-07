from __future__ import annotations

import html
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
    
    html_content = f"""<!DOCTYPE html>
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
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', 'Roboto', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%);
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
            border: 1px solid var(--border);
            backdrop-filter: blur(10px);
            animation: slideDown 0.5s ease;
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
            opacity: 0.9;
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
            box-shadow: var(--shadow);
            transition: all 0.3s ease;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .stat-card:hover {{
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
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
            animation: fadeIn 0.5s ease;
        }}
        
        .step:hover {{
            transform: translateY(-4px);
            box-shadow: var(--shadow-xl), var(--glow);
            border-color: var(--border-light);
            background: var(--card-hover);
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
            box-shadow: 0 0 0 2px var(--primary), 0 0 10px rgba(129, 140, 248, 0.5);
            animation: pulse 2s ease-in-out infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{
                transform: scale(1);
                opacity: 1;
            }}
            50% {{
                transform: scale(1.1);
                opacity: 0.8;
            }}
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
            background: rgba(129, 140, 248, 0.15);
            padding: 0.375rem 0.75rem;
            border-radius: var(--radius-sm);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border: 1px solid rgba(129, 140, 248, 0.3);
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
            background: var(--bg-secondary);
            border-radius: var(--radius-sm);
            font-size: 0.875rem;
            border: 1px solid var(--border);
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
            background: var(--bg-tertiary);
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            border: 1px solid var(--border);
            color: var(--primary);
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
            background: var(--bg-secondary);
            transition: all 0.3s ease;
        }}
        
        .screenshot-container:hover {{
            transform: scale(1.02);
            box-shadow: var(--shadow-lg), var(--glow);
            border-color: var(--border-light);
        }}
        
        .screenshot-label {{
            position: absolute;
            top: 0.5rem;
            left: 0.5rem;
            background: rgba(15, 23, 42, 0.9);
            color: var(--primary);
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: capitalize;
            z-index: 1;
            border: 1px solid var(--border-light);
            backdrop-filter: blur(10px);
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
            background: rgba(129, 140, 248, 0.15);
            border-radius: var(--radius-sm);
            transition: all 0.2s ease;
            border: 1px solid rgba(129, 140, 248, 0.3);
        }}
        
        .trace-link a:hover {{
            background: rgba(129, 140, 248, 0.25);
            transform: translateY(-2px);
            box-shadow: var(--shadow), var(--glow);
        }}
        
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(8px);
        }}
        
        .modal.active {{
            display: flex;
            align-items: center;
            justify-content: center;
            animation: fadeIn 0.3s ease;
        }}
        
        @keyframes fadeIn {{
            from {{
                opacity: 0;
                transform: translateY(10px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
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
            color: var(--text);
            font-size: 2rem;
            font-weight: bold;
            cursor: pointer;
            background: rgba(30, 41, 59, 0.8);
            width: 2.5rem;
            height: 2.5rem;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            border: 1px solid var(--border);
        }}
        
        .close:hover {{
            background: rgba(30, 41, 59, 1);
            transform: rotate(90deg);
            box-shadow: var(--shadow-lg);
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
                <code class="metadata-value">{html.escape(str(s.action))}</code>
            </div>''' if s.action else ''
        
        badges_html = f'<div class="badges">{"".join(badges)}</div>' if badges else ''
        
        screenshots_html = ""
        if s.screenshots:
            screenshots_html = '<div class="screenshots">'
            for viewport, filename in s.screenshots.items():
                screenshots_html += f'''
                <div class="screenshot-container">
                    <span class="screenshot-label">{viewport}</span>
                    <img src="{html.escape(filename)}" data-asset="{html.escape(filename)}" data-full-src="{html.escape(filename)}" alt="Step {idx:02d} - {html.escape(viewport)}" class="screenshot asset-img" onclick="openModal(this.getAttribute('data-full-src'))" />
                </div>'''
            screenshots_html += '</div>'
        
        html_content += f"""
            <div class="step">
                <div class="step-header">
                    <div>
                        <div class="step-number">Step {idx:02d}</div>
                        <div class="step-description">{html.escape(s.description)}</div>
                        {badges_html}
                    </div>
                </div>
                <div class="metadata">
                    <div class="metadata-item">
                        <span class="metadata-label">URL:</span>
                        <code class="metadata-value">{html.escape(s.url)}</code>
                    </div>
                    {action_html}
                </div>
                {screenshots_html}
            </div>
"""
    
    html_content += f"""
        </div>
        <div class="trace-link">
            <a href="{html.escape(trace_zip)}" class="asset-link" data-asset="{html.escape(trace_zip)}">
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

        // Normalize asset paths when served via the API (HTTP/HTTPS)
        (function() {{
            if (window.location.protocol === 'file:') {{
                // Local files already resolve relative to the report directory.
                document.querySelectorAll('.asset-img').forEach(img => {{
                    img.setAttribute('data-full-src', img.getAttribute('data-asset'));
                }});
                document.querySelectorAll('.asset-link').forEach(link => {{
                    link.href = link.getAttribute('data-asset');
                }});
                return;
            }}

            const basePath = window.location.pathname.endsWith('/')
                ? window.location.pathname
                : window.location.pathname + '/';

            document.querySelectorAll('.asset-img').forEach(img => {{
                const name = img.getAttribute('data-asset');
                const full = basePath + name;
                img.src = full;
                img.setAttribute('data-full-src', full);
            }});

            document.querySelectorAll('.asset-link').forEach(link => {{
                const name = link.getAttribute('data-asset');
                link.href = basePath + name;
            }});
        }})();
    </script>
</body>
</html>
"""
    
    report.write_text(html_content, encoding="utf-8")
    return report


