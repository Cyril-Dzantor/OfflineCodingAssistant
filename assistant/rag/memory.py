# assistant/rag/memory.py

import os
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any

from assistant.config import settings
from assistant.utils.logger import setup_logger

logger = setup_logger("ProjectMemory")


@dataclass
class MemoryEntry:
    """Represents a discrete persistent fact or development record."""

    id: Optional[int]
    category: str  # "project", "development", "decision"
    key: str
    content: str
    timestamp: float
    project_id: str = "default"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProjectMemory:
    """
    Persistent SQLite-backed memory store for project architecture,
    architectural decisions, and ongoing development context across sessions.
    """

    def __init__(self, db_path: Optional[str] = None, project_id: Optional[str] = None):
        self.db_path = db_path or getattr(settings, "PROJECT_MEMORY_PATH", ".cydags/memory.db")
        self.project_id = project_id or os.path.basename(os.path.abspath("."))
        self._ensure_dir()
        self._init_db()

    def _ensure_dir(self) -> None:
        parent = os.path.dirname(self.db_path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_entries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        category TEXT NOT NULL,
                        key TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp REAL NOT NULL
                    )
                    """
                )
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_mem_proj_cat ON memory_entries(project_id, category)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_mem_proj_key ON memory_entries(project_id, key)")
        finally:
            conn.close()

    def record(self, category: str, key: str, content: str) -> int:
        """
        Record or update a persistent memory entry.

        Args:
            category: 'project', 'development', or 'decision'.
            key: Semantic identifier (e.g. 'architecture', 'active_task').
            content: Factual description or decision detail.

        Returns:
            The entry id.
        """
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                # Update existing if key and category match for project
                cursor.execute(
                    """
                    SELECT id FROM memory_entries
                    WHERE project_id = ? AND category = ? AND key = ?
                    """,
                    (self.project_id, category, key),
                )
                row = cursor.fetchone()
                if row:
                    entry_id = row["id"]
                    cursor.execute(
                        """
                        UPDATE memory_entries
                        SET content = ?, timestamp = ?
                        WHERE id = ?
                        """,
                        (content.strip(), time.time(), entry_id),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO memory_entries (project_id, category, key, content, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (self.project_id, category, key, content.strip(), time.time()),
                    )
                    entry_id = cursor.lastrowid
            logger.info(f"Recorded memory [{category}] '{key}' (id={entry_id})")
            return entry_id
        finally:
            conn.close()

    def get_by_key(self, key: str, category: Optional[str] = None) -> Optional[MemoryEntry]:
        """Retrieve a specific memory entry by key."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if category:
                cursor.execute(
                    "SELECT * FROM memory_entries WHERE project_id = ? AND category = ? AND key = ?",
                    (self.project_id, category, key),
                )
            else:
                cursor.execute(
                    "SELECT * FROM memory_entries WHERE project_id = ? AND key = ? ORDER BY timestamp DESC LIMIT 1",
                    (self.project_id, key),
                )
            row = cursor.fetchone()
            if row:
                return MemoryEntry(
                    id=row["id"],
                    category=row["category"],
                    key=row["key"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                    project_id=row["project_id"],
                )
            return None
        finally:
            conn.close()

    def get_by_category(self, category: str) -> List[MemoryEntry]:
        """Retrieve all memory entries within a category."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM memory_entries WHERE project_id = ? AND category = ? ORDER BY timestamp ASC",
                (self.project_id, category),
            )
            return [
                MemoryEntry(
                    id=r["id"],
                    category=r["category"],
                    key=r["key"],
                    content=r["content"],
                    timestamp=r["timestamp"],
                    project_id=r["project_id"],
                )
                for r in cursor.fetchall()
            ]
        finally:
            conn.close()

    def get_recent(self, limit: int = 10) -> List[MemoryEntry]:
        """Retrieve most recent memory entries."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM memory_entries WHERE project_id = ? ORDER BY timestamp DESC LIMIT ?",
                (self.project_id, limit),
            )
            return [
                MemoryEntry(
                    id=r["id"],
                    category=r["category"],
                    key=r["key"],
                    content=r["content"],
                    timestamp=r["timestamp"],
                    project_id=r["project_id"],
                )
                for r in cursor.fetchall()
            ]
        finally:
            conn.close()

    def format_memory_summary(self, max_chars: int = 1200) -> str:
        """
        Format persistent memory entries into a structured markdown block for context inclusion.
        """
        all_entries = self.get_recent(limit=15)
        if not all_entries:
            return ""

        sections: Dict[str, List[str]] = {
            "project": [],
            "development": [],
            "decision": [],
        }

        for entry in all_entries:
            cat = entry.category if entry.category in sections else "project"
            sections[cat].append(f"- **{entry.key}**: {entry.content}")

        lines = ["### Persistent Project Memory"]
        for cat, items in sections.items():
            if items:
                lines.append(f"**{cat.capitalize()} Knowledge:**")
                lines.extend(items)

        result = "\n".join(lines).strip()
        if len(result) > max_chars:
            return result[:max_chars] + "\n[...memory truncated...]"
        return result

    def clear(self, category: Optional[str] = None) -> int:
        """Clear memory entries for this project, optionally filtered by category."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                if category:
                    cursor.execute(
                        "DELETE FROM memory_entries WHERE project_id = ? AND category = ?",
                        (self.project_id, category),
                    )
                else:
                    cursor.execute(
                        "DELETE FROM memory_entries WHERE project_id = ?",
                        (self.project_id,),
                    )
                return cursor.rowcount
        finally:
            conn.close()

    def handle_command(self, cmd: str) -> str:
        """
        Handle CLI slash commands for inspecting and managing persistent memory:
          /memory
          /memory project
          /memory recent
          /memory clear
        """
        parts = cmd.strip().split()
        sub = parts[1].lower() if len(parts) > 1 else "summary"

        if sub in ("summary", "all"):
            entries = self.get_recent(20)
            if not entries:
                return "No persistent project memory recorded yet."
            out = ["--- Persistent Project Memory ---"]
            for e in entries:
                out.append(f"• [{e.category.upper()}] {e.key}: {e.content}")
            return "\n".join(out)

        elif sub in ("project", "development", "decision"):
            entries = self.get_by_category(sub)
            if not entries:
                return f"No entries found in category '{sub}'."
            out = [f"--- Memory Category: {sub.upper()} ---"]
            for e in entries:
                out.append(f"• {e.key}: {e.content}")
            return "\n".join(out)

        elif sub == "clear":
            cleared = self.clear()
            return f"Cleared {cleared} memory entries for project '{self.project_id}'."

        else:
            return (
                f"Unknown memory command '{cmd}'. Available options:\n"
                "  /memory\n"
                "  /memory project\n"
                "  /memory development\n"
                "  /memory decision\n"
                "  /memory clear"
            )


if __name__ == "__main__":
    print("=" * 60)
    print("      Sub-Phase 5.9: Project Memory Verification")
    print("=" * 60)

    test_mem_db = ".cydags/test_memory.db"
    mem = ProjectMemory(db_path=test_mem_db, project_id="test_proj")
    mem.clear()

    # Record entries across categories
    mem.record("project", "architecture", "Local-first modular architecture with deterministic AST parsing and offline RAG.")
    mem.record("project", "tech_stack", "Python 3.14, llama-cpp-python, FastEmbed (ONNX), SQLite, Tree-Sitter.")
    mem.record("development", "phase_status", "Phase 5 Advanced Context & RAG in active development.")
    mem.record("decision", "embedding_choice", "Selected BGE-small-en-v1.5 running on ONNX CPU to protect 4GB GPU VRAM.")

    print(f"\n[+] Total recent entries: {len(mem.get_recent())}")
    assert len(mem.get_recent()) == 4, "Expected 4 entries recorded"

    # Test update existing key
    mem.record("development", "phase_status", "Phase 5 sub-phases 5.1 through 5.9 verified.")
    updated = mem.get_by_key("phase_status", "development")
    print(f"[+] Updated entry: {updated.key} -> {updated.content}")
    assert "sub-phases 5.1 through 5.9" in updated.content, "Update failed"

    # Test formatted summary for LLM context
    summary = mem.format_memory_summary()
    print("\n--- Formatted Context Summary ---")
    print(summary)
    assert "### Persistent Project Memory" in summary, "Summary format invalid"

    # Test command handler
    cmd_res = mem.handle_command("/memory project")
    print("\n--- CLI Command Output (/memory project) ---")
    print(cmd_res)
    assert "architecture" in cmd_res, "CLI handler failed"

    # Cleanup test db
    mem.clear()
    if os.path.exists(test_mem_db):
        os.remove(test_mem_db)

    print("\n[PASS] Sub-Phase 5.9 Verification Complete.")

