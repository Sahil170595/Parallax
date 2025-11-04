from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from parallax.agents.constitutions import ARCHIVIST_CONSTITUTION
from parallax.core.constitution import FailureStore
from parallax.core.logging import get_logger
from parallax.core.schemas import UIState
from parallax.store.dataset import DatasetStore
from parallax.store.report import write_markdown_report, write_html_report


log = get_logger("archivist")


class Archivist:
    """
    Agent A4: Archivist - Organizes captured data into datasets.
    
    The Archivist agent organizes captured UI states into structured datasets.
    It writes JSONL files, SQLite databases, and generates human-readable reports
    (Markdown and HTML). Validates dataset creation against the Archivist constitution.
    
    Args:
        base_dir: Base directory for storing datasets (e.g., Path("datasets"))
        failure_store: Optional store for tracking constitution failures
    
    Example:
        >>> from pathlib import Path
        >>> 
        >>> archivist = Archivist(Path("datasets"))
        >>> dataset_path = archivist.write_states("linear", "create-project", states)
        >>> print(f"Dataset saved to: {dataset_path}")
    """
    
    def __init__(self, base_dir: Path, failure_store: Optional[FailureStore] = None) -> None:
        self.base_dir = base_dir
        self.store = DatasetStore(base_dir)
        self.failure_store = failure_store
        self.constitution = ARCHIVIST_CONSTITUTION

    def write_states(self, app: str, task_slug: str, states: Iterable[UIState], trace_zip: str = "trace.zip") -> Path:
        """
        Write captured states to a dataset directory.
        
        Creates a dataset directory structure with JSONL files, SQLite database,
        and HTML/Markdown reports. Validates dataset creation against the
        Archivist constitution.
        
        Args:
            app: Application name (e.g., "linear", "notion")
            task_slug: URL-safe task identifier (e.g., "create-project")
            states: Iterable of UIState objects to save
            trace_zip: Filename for Playwright trace zip (default: "trace.zip")
        
        Returns:
            Path to the created dataset directory
        
        Raises:
            ConstitutionViolation: If dataset creation fails critical validation rules
        
        Example:
            >>> dataset_path = archivist.write_states("linear", "create-project", observer.states)
            >>> print(f"Dataset: {dataset_path}")
            >>> print(f"  - JSONL: {dataset_path / 'steps.jsonl'}")
            >>> print(f"  - SQLite: {dataset_path / 'dataset.db'}")
            >>> print(f"  - Report: {dataset_path / 'report.html'}")
        """
        root = self.base_dir / app / task_slug
        root.mkdir(parents=True, exist_ok=True)
        states_list = list(states)
        
        # Write JSONL
        steps_path = root / "steps.jsonl"
        with steps_path.open("w", encoding="utf-8") as f:
            for s in states_list:
                f.write(json.dumps(s.__dict__, ensure_ascii=False) + "\n")
        
        # Write SQLite
        self.store.write_sqlite(root, states_list, app, task_slug)
        
        # Write reports
        write_markdown_report(root, states_list)
        write_html_report(root, states_list, trace_zip)
        
        # Validate dataset creation against constitution
        validation_context = {
            "app": app,
            "task_slug": task_slug,
            "states_count": len(states_list),
        }
        report = self.constitution.validate(states_list, root, validation_context)
        
        if not report.passed:
            log.error(
                "constitution_failed",
                agent="A4_Archivist",
                failures=[f.rule_name for f in report.failures],
            )
            if self.failure_store:
                self.failure_store.save_failure(report)
            # For critical failures, raise exception
            self.constitution.must_pass(states_list, root, validation_context)
        elif report.warnings:
            log.warning(
                "constitution_warnings",
                agent="A4_Archivist",
                warnings=[w.rule_name for w in report.warnings],
            )
            if self.failure_store:
                self.failure_store.save_failure(report)
        
        return root


