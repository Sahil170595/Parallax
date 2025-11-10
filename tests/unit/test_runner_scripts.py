from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_dashboard
import run_web
from streamlit_dashboard import normalize_app_name


def test_normalize_app_name_strips_and_slugifies():
    label, slug = normalize_app_name("  Cake  Automation  ")
    assert label == "Cake  Automation"
    assert slug == "cake-automation"


def test_normalize_app_name_raises_for_empty():
    with pytest.raises(ValueError):
        normalize_app_name("   ")


def test_run_dashboard_invokes_streamlit(monkeypatch):
    recorded = {}

    def fake_run(cmd, check):
        recorded["cmd"] = cmd
        recorded["check"] = check
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_dashboard.subprocess, "run", fake_run)
    monkeypatch.setattr(run_dashboard.sys, "executable", sys.executable)
    run_dashboard.main()

    assert recorded["cmd"][0] == sys.executable
    assert recorded["cmd"][1:4] == ["-m", "streamlit", "run"]
    assert recorded["check"] is True


def test_run_web_should_disable_reload_windows(monkeypatch):
    args = SimpleNamespace(reload=True)
    monkeypatch.setattr(run_web.sys, "platform", "win32")
    reload_flag, warning = run_web._should_disable_reload(args)
    assert reload_flag is False
    assert "Auto-reload" in warning


def test_run_web_should_disable_reload_non_windows(monkeypatch):
    args = SimpleNamespace(reload=False)
    monkeypatch.setattr(run_web.sys, "platform", "linux")
    reload_flag, warning = run_web._should_disable_reload(args)
    assert reload_flag is False
    assert warning is None


def test_run_web_main_invokes_uvicorn(monkeypatch):
    args = SimpleNamespace(host="127.0.0.1", port=9000, reload=False)
    monkeypatch.setattr(run_web, "_parse_args", lambda: args)
    monkeypatch.setattr(run_web, "_should_disable_reload", lambda _: (False, None))

    captured = {}

    def fake_uvicorn_run(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(run_web.uvicorn, "run", fake_uvicorn_run)
    run_web.main()

    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9000
    assert captured["reload"] is False
