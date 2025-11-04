from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from parallax.agents.constitutions import OBSERVER_CONSTITUTION
from parallax.core.constitution import FailureStore
from parallax.core.logging import get_logger
from parallax.core.schemas import UIState, RoleNode


log = get_logger("observer")


class Observer:
    """
    Agent A3: Observer - Captures UI states and screenshots.
    
    The Observer agent captures UI states at each step of workflow execution.
    It uses Detectors to identify UI changes (modals, toasts, forms, role-tree
    differences) and captures multi-viewport screenshots. Validates state capture
    against the Observer constitution.
    
    Args:
        page: Playwright Page object for screenshot capture
        detectors: Detectors instance for state detection
        save_dir: Optional directory path for saving screenshots
        failure_store: Optional store for tracking constitution failures
        task_context: Optional task context string for vision analysis
    
    Example:
        >>> from parallax.observer.detectors import Detectors
        >>> 
        >>> detectors = Detectors(config)
        >>> observer = Observer(page, detectors, save_dir=Path("output"))
        >>> state = await observer.observe("click(button[Create])")
        >>> print(f"Captured {len(observer.states)} states")
    """
    
    def __init__(
        self,
        page,
        detectors,
        save_dir: Optional[Path] = None,
        failure_store: Optional[FailureStore] = None,
        task_context: Optional[str] = None,
    ) -> None:
        self.page = page
        self.detectors = detectors
        self._states: List[UIState] = []
        self._save_dir = save_dir
        self._idx = 0
        self.failure_store = failure_store
        self.constitution = OBSERVER_CONSTITUTION
        self.task_context = task_context
        
        # Set task context in detectors for vision analysis
        if task_context:
            detectors.set_task_context(task_context)

    async def start(self) -> None:
        pass

    async def observe(self, action_desc: Optional[str]) -> Optional[UIState]:
        """
        Capture a UI state after an action.
        
        Captures the current UI state including screenshots, role-tree snapshots,
        and metadata (modals, toasts, forms, etc.). Validates state capture
        against the Observer constitution.
        
        Args:
            action_desc: Optional description of the action that led to this state
        
        Returns:
            UIState object with screenshots and metadata, or None if capture failed
        
        Example:
            >>> state = await observer.observe("click(button[Create])")
            >>> if state:
            ...     print(f"State: {state.description}, URL: {state.url}")
            ...     print(f"Screenshots: {list(state.screenshots.keys())}")
        """
        state = await self.detectors.capture_state(
            self.page, action_desc, self._save_dir, self._idx
        )
        if state:
            # Validate state capture against constitution
            validation_context = {
                "save_dir": self._save_dir,
                "action_desc": action_desc,
                "index": self._idx,
            }
            report = self.constitution.validate(None, state, validation_context)
            
            if not report.passed:
                log.error(
                    "constitution_failed",
                    agent="A3_Observer",
                    failures=[f.rule_name for f in report.failures],
                )
                if self.failure_store:
                    self.failure_store.save_failure(report)
                # For critical failures, raise exception
                self.constitution.must_pass(None, state, validation_context)
            elif report.warnings:
                log.warning(
                    "constitution_warnings",
                    agent="A3_Observer",
                    warnings=[w.rule_name for w in report.warnings],
                )
                if self.failure_store:
                    self.failure_store.save_failure(report)
            
            self._states.append(state)
            self._idx += 1
        return state

    @property
    def states(self) -> List[UIState]:
        return list(self._states)


