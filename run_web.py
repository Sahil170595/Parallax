"""Run the Parallax web UI server."""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any, Dict

import uvicorn

# Fix for Windows asyncio subprocess limitations (Playwright requires Proactor loop)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the Parallax web UI server.")
    parser.add_argument("--host", default="0.0.0.0", help="Interface to bind (default: 0.0.0.0).")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000).")
    parser.add_argument(
        "--reload",
        dest="reload",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable auto-reload on code changes (default: enabled).",
    )
    return parser.parse_args()


def _should_disable_reload(args: argparse.Namespace) -> tuple[bool, str | None]:
    """
    Determine whether reload should be disabled on Windows.

    `watchfiles` (used by uvicorn's reload) currently forces the Windows selector
    event loop, which breaks Playwright on Python >= 3.13. Until upstream support
    lands, we disable reload by default on Windows to avoid NotImplementedError
    when launching browsers.
    """
    if sys.platform != "win32":
        return args.reload, None
    if not args.reload:
        return False, None
    message = (
        "Auto-reload disabled on Windows because the selector event loop cannot launch "
        "Playwright subprocesses on Python 3.13+. Re-run with `--reload` explicitly if "
        "you have patched asyncio to use a Proactor loop."
    )
    return False, message


def main() -> None:
    args = _parse_args()
    reload_enabled, warning = _should_disable_reload(args)

    if warning:
        print(f"[parallax-web] {warning}")

    uvicorn_kwargs: Dict[str, Any] = {
        "app": "parallax.web.server:app",
        "host": args.host,
        "port": args.port,
        "reload": reload_enabled,
        "log_level": "info",
        "loop": "asyncio",
    }

    try:
        uvicorn.run(**uvicorn_kwargs)
    except KeyboardInterrupt:
        print("\n[parallax-web] Shutdown requested by user.")
    except asyncio.CancelledError:
        # Uvicorn may surface CancelledError when the loop stops; treat as clean exit
        print("\n[parallax-web] Event loop cancelled; server stopped.")


if __name__ == "__main__":
    main()

