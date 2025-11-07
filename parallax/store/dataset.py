from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from parallax.core.schemas import UIState


class DatasetStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def path_for(self, app: str, task_slug: str) -> Path:
        p = self.base_dir / app / task_slug
        p.mkdir(parents=True, exist_ok=True)
        return p

    def write_steps_jsonl(self, path: Path, states: Iterable[UIState]) -> None:
        with (path / "steps.jsonl").open("w", encoding="utf-8") as f:
            for s in states:
                f.write(json.dumps(s.__dict__, ensure_ascii=False) + "\n")

    def write_sqlite(self, path: Path, states: Iterable[UIState], app: str, task_slug: str) -> Path:
        db_path = path / "dataset.db"
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            
            # Create tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS states (
                    id TEXT PRIMARY KEY,
                    url TEXT,
                    description TEXT,
                    has_modal INTEGER,
                    action TEXT,
                    state_signature TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS screenshots (
                    state_id TEXT,
                    viewport TEXT,
                    filename TEXT,
                    FOREIGN KEY (state_id) REFERENCES states(id)
                )
            """)
            
            # Insert states
            for state in states:
                cursor.execute("""
                    INSERT OR REPLACE INTO states 
                    (id, url, description, has_modal, action, state_signature, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    state.id,
                    state.url,
                    state.description,
                    1 if state.has_modal else 0,
                    state.action,
                    state.state_signature,
                    json.dumps(state.metadata),
                ))
                
                # Insert screenshots
                for viewport, filename in state.screenshots.items():
                    cursor.execute("""
                        INSERT OR REPLACE INTO screenshots (state_id, viewport, filename)
                        VALUES (?, ?, ?)
                    """, (state.id, viewport, filename))
            
            conn.commit()
        return db_path


