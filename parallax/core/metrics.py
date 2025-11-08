from __future__ import annotations

import threading

from prometheus_client import Counter, Histogram, start_http_server

workflow_success = Counter(
    "parallax_workflow_success_total", "Successful workflows"
)
workflow_failure = Counter(
    "parallax_workflow_failure_total", "Failed workflows"
)
states_per_workflow = Histogram(
    "parallax_states_per_workflow", "Number of states captured per workflow"
)
llm_tokens = Histogram("parallax_llm_tokens", "LLM tokens used per plan")
trace_size_bytes = Histogram(
    "parallax_trace_size_bytes", "Playwright trace size in bytes"
)

_METRICS_SERVER_STARTED = False
_METRICS_LOCK = threading.Lock()


def ensure_metrics_server(port: int) -> None:
    """Start the Prometheus metrics HTTP server once per process."""
    global _METRICS_SERVER_STARTED

    if _METRICS_SERVER_STARTED:
        return

    with _METRICS_LOCK:
        if _METRICS_SERVER_STARTED:
            return
        try:
            start_http_server(port)
            _METRICS_SERVER_STARTED = True
        except OSError:
            # Another process/thread might already be using the port. Swallow the
            # error so metrics recording can continue even without HTTP export.
            _METRICS_SERVER_STARTED = True
            return


