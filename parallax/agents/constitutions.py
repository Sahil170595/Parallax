"""Agent-specific constitution rules and validators."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from parallax.core.constitution import AgentConstitution, ValidationLevel, ValidationRule
from parallax.core.schemas import ExecutionPlan, PlanStep, UIState


# ============================================================================
# Agent A1 - Interpreter Constitution
# ============================================================================

def validate_plan_structure(input_data: Any, output_data: ExecutionPlan, context: Dict) -> tuple[bool, str, Dict]:
    """Validate that plan has required structure."""
    if not isinstance(output_data, ExecutionPlan):
        return False, "Output is not an ExecutionPlan", {"type": type(output_data).__name__}
    
    if not hasattr(output_data, "steps"):
        return False, "Plan missing 'steps' attribute", {}
    
    if not isinstance(output_data.steps, list):
        return False, "Plan 'steps' must be a list", {"type": type(output_data.steps).__name__}
    
    return True, "Plan structure valid", {"steps_count": len(output_data.steps)}


def validate_plan_non_empty(input_data: Any, output_data: ExecutionPlan, context: Dict) -> tuple[bool, str, Dict]:
    """Validate that plan has at least one step."""
    if len(output_data.steps) == 0:
        return False, "Plan has no steps", {"steps_count": 0}
    
    return True, "Plan has steps", {"steps_count": len(output_data.steps)}


def validate_plan_step_validity(input_data: Any, output_data: ExecutionPlan, context: Dict) -> tuple[bool, str, Dict]:
    """Validate that all plan steps have valid actions."""
    valid_actions = {
        "navigate", "click", "type", "submit", "wait", "scroll",
        "select", "drag", "upload", "hover", "double_click", "right_click",
        "key_press", "screenshot", "evaluate", "fill", "check", "uncheck",
        "focus", "blur", "press_key", "go_back", "go_forward", "reload"
    }
    invalid_steps = []
    
    for idx, step in enumerate(output_data.steps):
        if not isinstance(step, PlanStep):
            invalid_steps.append({"index": idx, "reason": "Not a PlanStep instance"})
            continue
        
        if not hasattr(step, "action") or not step.action:
            invalid_steps.append({"index": idx, "reason": "Missing action"})
            continue
        
        if step.action not in valid_actions:
            invalid_steps.append({"index": idx, "reason": f"Invalid action: {step.action}"})
            continue
        
        # Validate action-specific requirements
        if step.action == "navigate" and not step.target:
            invalid_steps.append({"index": idx, "reason": "Navigate action missing target"})
        elif step.action == "type" and (not step.selector or not step.value):
            invalid_steps.append({"index": idx, "reason": "Type action missing selector or value"})
        elif step.action == "select" and (not step.selector or not (step.value or step.option_value)):
            invalid_steps.append({"index": idx, "reason": "Select action missing selector or value"})
        elif step.action == "drag" and (not step.start_selector or not (step.end_selector or step.target)):
            invalid_steps.append({"index": idx, "reason": "Drag action missing start_selector or end_selector/target"})
        elif step.action == "upload" and (not step.selector or not (step.file_path or step.value)):
            invalid_steps.append({"index": idx, "reason": "Upload action missing selector or file_path"})
        elif step.action == "fill" and (not step.selector or not step.value):
            invalid_steps.append({"index": idx, "reason": "Fill action missing selector or value"})
        elif step.action == "check" and not step.selector:
            invalid_steps.append({"index": idx, "reason": "Check action missing selector"})
        elif step.action == "uncheck" and not step.selector:
            invalid_steps.append({"index": idx, "reason": "Uncheck action missing selector"})
        elif step.action == "hover" and not step.selector:
            invalid_steps.append({"index": idx, "reason": "Hover action missing selector"})
        elif step.action == "key_press" and not step.value:
            invalid_steps.append({"index": idx, "reason": "Key press action missing value (key name)"})
    
    if invalid_steps:
        return False, f"Invalid steps found: {len(invalid_steps)}", {"invalid_steps": invalid_steps}
    
    return True, "All steps valid", {"steps_count": len(output_data.steps)}


INTERPRETER_CONSTITUTION = AgentConstitution(
    agent_name="A1_Interpreter",
    rules=[
        ValidationRule(
            name="plan_structure",
            description="Plan must have valid ExecutionPlan structure",
            level=ValidationLevel.CRITICAL,
            validator=validate_plan_structure,
        ),
        ValidationRule(
            name="plan_non_empty",
            description="Plan must have at least one step",
            level=ValidationLevel.CRITICAL,
            validator=validate_plan_non_empty,
        ),
        ValidationRule(
            name="plan_step_validity",
            description="All plan steps must have valid actions and required fields",
            level=ValidationLevel.CRITICAL,
            validator=validate_plan_step_validity,
        ),
    ],
)


# ============================================================================
# Agent A2 - Navigator Constitution
# ============================================================================

def validate_navigation_success(input_data: ExecutionPlan, output_data: Any, context: Dict) -> tuple[bool, str, Dict]:
    """Validate that navigation completed without critical errors."""
    page = context.get("page")
    if not page:
        return True, "No page context to validate", {}
    
    # Check if page is still valid (not crashed or closed)
    try:
        # Try to access the URL - if this fails, the page is likely crashed or closed
        url = page.url
        
        # Check if we have a valid URL
        # Allow data: and blob: URLs as they are valid
        if not url:
            return False, "Page did not load properly (empty URL)", {"url": url}
        
        # Only fail on "about:blank" if we actually executed navigation steps
        # If the plan has navigation steps, we should have navigated away from about:blank
        has_navigation = any(step.action == "navigate" for step in input_data.steps)
        if url == "about:blank" and has_navigation:
            return False, "Page did not load properly (still on about:blank after navigation)", {"url": url}
        
        # If we have a valid URL (not about:blank, or about:blank but no navigation was expected)
        return True, "Navigation successful", {"final_url": url}
    except Exception as e:
        # If accessing page.url raises an exception, the page is likely crashed or closed
        error_msg = str(e)
        if "Target closed" in error_msg or "Target page, context or browser has been closed" in error_msg:
            return False, "Page was closed or crashed", {"error": error_msg}
        # Return failure for unexpected exceptions
        return False, f"Page navigation failed: {error_msg}", {"error": error_msg}


def validate_action_budget(input_data: ExecutionPlan, output_data: Any, context: Dict) -> tuple[bool, str, Dict]:
    """Validate that action budget was respected."""
    action_budget = context.get("action_budget", 30)
    action_count = context.get("action_count", 0)
    
    if action_count > action_budget:
        return False, f"Action budget exceeded: {action_count} > {action_budget}", {
            "action_count": action_count,
            "action_budget": action_budget,
        }
    
    return True, "Action budget respected", {
        "action_count": action_count,
        "action_budget": action_budget,
    }


def validate_no_auth_redirects(input_data: ExecutionPlan, output_data: Any, context: Dict) -> tuple[bool, str, Dict]:
    """Validate that workflow didn't redirect to auth pages unexpectedly."""
    page = context.get("page")
    if not page:
        return True, "No page context to validate", {}
    
    try:
        url = page.url
        auth_indicators = ["/login", "/auth", "/signin"]
        if any(indicator in url.lower() for indicator in auth_indicators):
            return False, f"Unexpected auth redirect to: {url}", {"url": url}
        return True, "No auth redirects", {"url": url}
    except Exception:
        return True, "Could not check URL", {}


NAVIGATOR_CONSTITUTION = AgentConstitution(
    agent_name="A2_Navigator",
    rules=[
        ValidationRule(
            name="navigation_success",
            description="Navigation must complete without page crashes",
            level=ValidationLevel.CRITICAL,
            validator=validate_navigation_success,
        ),
        ValidationRule(
            name="action_budget",
            description="Action budget must not be exceeded",
            level=ValidationLevel.WARNING,
            validator=validate_action_budget,
        ),
        ValidationRule(
            name="no_auth_redirects",
            description="Workflow should not redirect to auth pages unexpectedly",
            level=ValidationLevel.WARNING,
            validator=validate_no_auth_redirects,
        ),
    ],
)


# ============================================================================
# Agent A3 - Observer Constitution
# ============================================================================

def validate_state_captured(input_data: Any, output_data: UIState, context: Dict) -> tuple[bool, str, Dict]:
    """Validate that state was successfully captured."""
    if not isinstance(output_data, UIState):
        return False, "Output is not a UIState", {"type": type(output_data).__name__}
    
    if not output_data.screenshots:
        return False, "State missing screenshots", {}
    
    if not output_data.state_signature:
        return False, "State missing signature", {}
    
    return True, "State captured successfully", {
        "screenshot_count": len(output_data.screenshots),
        "has_signature": bool(output_data.state_signature),
    }


def validate_state_description(input_data: Any, output_data: UIState, context: Dict) -> tuple[bool, str, Dict]:
    """Ensure states have meaningful descriptions."""
    description = (output_data.description or "").strip().lower()
    if not description or description in {"ui state", "ui state (stable)"}:
        return False, "State description lacks detail", {"description": output_data.description}
    return True, "State description present", {}


def validate_minimum_states_captured(input_data: Any, output_data: List[UIState], context: Dict) -> tuple[bool, str, Dict]:
    """Validate that minimum number of states were captured."""
    states: List[UIState] | None = None
    if isinstance(output_data, list):
        states = output_data
    elif isinstance(input_data, list):
        states = input_data
    if states is None:
        return False, "No states provided for validation", {
            "input_type": type(input_data).__name__,
            "output_type": type(output_data).__name__,
        }

    min_states = context.get("min_states", 1)

    if len(states) < min_states:
        return False, f"Only {len(states)} states captured, expected at least {min_states}", {
            "captured": len(states),
            "expected_min": min_states,
        }

    return True, f"Captured {len(states)} states", {
        "captured": len(states),
        "expected_min": min_states,
    }


def validate_screenshot_quality(input_data: Any, output_data: UIState, context: Dict) -> tuple[bool, str, Dict]:
    """Validate that screenshots exist and are accessible."""
    if not output_data.screenshots:
        return False, "No screenshots in state", {}
    
    save_dir = context.get("save_dir")
    if not save_dir:
        return True, "No save_dir to validate files", {}
    
    missing_files = []
    for viewport, filename in output_data.screenshots.items():
        file_path = save_dir / filename
        if not file_path.exists():
            missing_files.append({"viewport": viewport, "filename": filename})
    
    if missing_files:
        return False, f"Missing screenshot files: {len(missing_files)}", {"missing_files": missing_files}
    
    return True, "All screenshots exist", {"screenshot_count": len(output_data.screenshots)}


OBSERVER_CONSTITUTION = AgentConstitution(
    agent_name="A3_Observer",
    rules=[
        ValidationRule(
            name="state_captured",
            description="State must have screenshots and signature",
            level=ValidationLevel.CRITICAL,
            validator=validate_state_captured,
        ),
        ValidationRule(
            name="screenshot_quality",
            description="All screenshot files must exist",
            level=ValidationLevel.CRITICAL,
            validator=validate_screenshot_quality,
        ),
        ValidationRule(
            name="state_description",
            description="State should include a meaningful description",
            level=ValidationLevel.WARNING,
            validator=validate_state_description,
        ),
    ],
)


# ============================================================================
# Agent A4 - Archivist Constitution
# ============================================================================

def validate_dataset_created(input_data: List[UIState], output_data: Path, context: Dict) -> tuple[bool, str, Dict]:
    """Validate that dataset directory was created."""
    if not isinstance(output_data, Path):
        return False, "Output is not a Path", {"type": type(output_data).__name__}
    
    if not output_data.exists():
        return False, f"Dataset directory does not exist: {output_data}", {"path": str(output_data)}
    
    return True, "Dataset directory created", {"path": str(output_data)}


def validate_dataset_files(input_data: List[UIState], output_data: Path, context: Dict) -> tuple[bool, str, Dict]:
    """Validate that required dataset files exist."""
    required_files = ["steps.jsonl", "report.html", "report.md"]
    missing_files = []
    
    for filename in required_files:
        file_path = output_data / filename
        if not file_path.exists():
            missing_files.append(filename)
    
    if missing_files:
        return False, f"Missing required files: {missing_files}", {"missing_files": missing_files}
    
    return True, "All required files exist", {"file_count": len(required_files)}


def validate_dataset_data_integrity(input_data: List[UIState], output_data: Path, context: Dict) -> tuple[bool, str, Dict]:
    """Validate that dataset data matches input states."""
    steps_file = output_data / "steps.jsonl"
    if not steps_file.exists():
        return False, "steps.jsonl does not exist", {}
    
    try:
        import json
        with steps_file.open("r", encoding="utf-8") as f:
            saved_states = [json.loads(line) for line in f if line.strip()]
        
        if len(saved_states) != len(input_data):
            return False, f"State count mismatch: saved {len(saved_states)}, expected {len(input_data)}", {
                "saved": len(saved_states),
                "expected": len(input_data),
            }
        
        return True, "Dataset data integrity valid", {"state_count": len(saved_states)}
    except Exception as e:
        return False, f"Could not validate data integrity: {str(e)}", {"error": str(e)}


ARCHIVIST_CONSTITUTION = AgentConstitution(
    agent_name="A4_Archivist",
    rules=[
        ValidationRule(
            name="dataset_created",
            description="Dataset directory must be created",
            level=ValidationLevel.CRITICAL,
            validator=validate_dataset_created,
        ),
        ValidationRule(
            name="dataset_files",
            description="All required dataset files must exist",
            level=ValidationLevel.CRITICAL,
            validator=validate_dataset_files,
        ),
        ValidationRule(
            name="minimum_states",
            description="Dataset must include at least one captured state",
            level=ValidationLevel.CRITICAL,
            validator=validate_minimum_states_captured,
        ),
        ValidationRule(
            name="dataset_data_integrity",
            description="Dataset data must match input states",
            level=ValidationLevel.WARNING,
            validator=validate_dataset_data_integrity,
        ),
    ],
)

