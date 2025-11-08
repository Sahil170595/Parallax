from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PlanStep:
    """
    A single step in an execution plan.
    
    Attributes:
        action: Action type (e.g., "navigate", "click", "type", "submit", "select", "drag", "upload", "hover")
        target: Target URL for navigation actions, or end target for drag actions
        role: ARIA role for semantic selection (e.g., "button", "textbox")
        name: ARIA name or accessible name for semantic selection
        selector: CSS selector or data-testid for element selection
        value: Value to type into text inputs, select option value, or file path for upload
        start_selector: Start selector for drag actions
        end_selector: End selector for drag actions
        file_path: File path for upload actions
        option_value: Option value for select actions
    """
    action: str
    target: Optional[str] = None
    role: Optional[str] = None
    name: Optional[str] = None
    selector: Optional[str] = None
    value: Optional[str] = None
    start_selector: Optional[str] = None
    end_selector: Optional[str] = None
    file_path: Optional[str] = None
    option_value: Optional[str] = None


@dataclass
class ExecutionPlan:
    """
    A complete execution plan with ordered steps.
    
    Attributes:
        steps: List of PlanStep objects in execution order
    """
    steps: List[PlanStep] = field(default_factory=list)


@dataclass
class RoleNode:
    """
    A node in the ARIA role tree.
    
    Attributes:
        role: ARIA role (e.g., "button", "dialog", "textbox")
        name: Accessible name or ARIA label
        selector: CSS selector for the element
    """
    role: str
    name: Optional[str] = None
    selector: Optional[str] = None


@dataclass
class UIState:
    """
    A captured UI state with screenshots and metadata.
    
    Attributes:
        id: Unique identifier for the state (e.g., "state_abc12345")
        url: Current page URL
        description: Human-readable description of the state
        has_modal: Whether a modal/dialog is present
        action: Description of the action that led to this state
        screenshots: Dictionary mapping viewport names to screenshot filenames
        metadata: Dictionary with additional metadata (roles, toasts, forms, etc.)
        state_signature: Hash-based signature for state deduplication
    """
    id: str
    url: str
    description: str
    has_modal: bool
    action: Optional[str]
    screenshots: Dict[str, str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    state_signature: Optional[str] = None


