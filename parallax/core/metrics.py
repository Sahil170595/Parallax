from prometheus_client import Counter, Histogram

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


