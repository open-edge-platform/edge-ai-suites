"""Shared test utilities for MCP Server development tests."""

import os
import sys
import tempfile
import shutil
import sqlite3
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MCP_SERVER_DIST = REPO_ROOT / "packages" / "mcp-server" / "dist"


def get_temp_dir(prefix: str) -> Path:
    """Create a temporary directory for test isolation."""
    d = Path(tempfile.mkdtemp(prefix=f"smartbuilding-test-{prefix}-"))
    return d


def cleanup_dir(path: Path):
    """Remove temporary directory."""
    shutil.rmtree(path, ignore_errors=True)


def init_test_db(db_path: str) -> sqlite3.Connection:
    """Initialize a test database with the same schema as SmartBuildingDB."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS monitors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'offline',
            use_case_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            event TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            acked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (source_id) REFERENCES monitors(id)
        );

        CREATE TABLE IF NOT EXISTS video_summary_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            monitor_id TEXT NOT NULL,
            video_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            summary TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT,
            FOREIGN KEY (monitor_id) REFERENCES monitors(id)
        );
    """)
    conn.commit()
    return conn


class TestResult:
    """Simple test result tracker."""

    def __init__(self, suite_name: str):
        self.suite_name = suite_name
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def check(self, condition: bool, message: str):
        if condition:
            self.passed += 1
            print(f"  ✓ {message}")
        else:
            self.failed += 1
            self.errors.append(message)
            print(f"  ✗ {message}")

    def check_equal(self, actual, expected, message: str):
        if actual == expected:
            self.passed += 1
            print(f"  ✓ {message}")
        else:
            self.failed += 1
            self.errors.append(f"{message} (expected={expected!r}, actual={actual!r})")
            print(f"  ✗ {message}")
            print(f"    expected: {expected!r}")
            print(f"    actual:   {actual!r}")

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n[{self.suite_name}] {self.passed}/{total} passed")
        if self.errors:
            print("  Failures:")
            for e in self.errors:
                print(f"    - {e}")
        return self.failed == 0
