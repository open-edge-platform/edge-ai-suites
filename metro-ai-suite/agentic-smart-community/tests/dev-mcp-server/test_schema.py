#!/usr/bin/env python3
"""Test Case 2: Schema Customization — ALTER TABLE + prompt validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conftest import get_temp_dir, cleanup_dir, init_test_db, TestResult


def get_columns(conn, table: str) -> dict[str, str]:
    """Return {column_name: column_type} for a table."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1]: row[2].lower() for row in rows}


def add_column_if_missing(conn, table: str, name: str, col_type: str) -> str:
    """Mimic SchemaManager.addColumnIfMissing. Returns 'added', 'exists', or 'type_mismatch'."""
    columns = get_columns(conn, table)
    if name in columns:
        if columns[name] != col_type.lower():
            return "type_mismatch"
        return "exists"
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type.upper()}")
    conn.commit()
    return "added"


def validate_prompt_schema(required_fields: list[str], prompt: str) -> dict:
    """Mimic SchemaManager.validatePromptSchema."""
    missing = [f for f in required_fields if f.lower() not in prompt.lower()]
    return {"valid": len(missing) == 0, "missing": missing}


def main():
    print("\n=== Test: Schema Customization ===\n")
    t = TestResult("Schema Customization")

    tmp = get_temp_dir("schema")
    db_path = str(tmp / "test.db")
    conn = init_test_db(db_path)

    # --- Apply schema extensions ---
    extensions = [
        ("event", "text"),
        ("severity", "text"),
        ("desc", "text"),
        ("confidence", "real"),
    ]
    added = []
    for name, col_type in extensions:
        result = add_column_if_missing(conn, "video_summary_tasks", name, col_type)
        if result == "added":
            added.append(f"video_summary_tasks.{name}")

    t.check_equal(len(added), 4, f"Added 4 columns (got {len(added)})")
    t.check("video_summary_tasks.event" in added, "Added event column")
    t.check("video_summary_tasks.confidence" in added, "Added confidence column")

    # --- Re-apply same schema (idempotent) ---
    re_added = []
    for name, col_type in extensions[:2]:
        result = add_column_if_missing(conn, "video_summary_tasks", name, col_type)
        if result == "added":
            re_added.append(name)
    t.check_equal(len(re_added), 0, "Re-apply same columns = no additions")

    # --- Verify columns exist in DB ---
    columns = get_columns(conn, "video_summary_tasks")
    t.check("event" in columns, "event column exists in DB")
    t.check("severity" in columns, "severity column exists in DB")
    t.check("desc" in columns, "desc column exists in DB")
    t.check("confidence" in columns, "confidence column exists in DB")

    # --- Type mismatch detection ---
    result = add_column_if_missing(conn, "video_summary_tasks", "event", "integer")
    t.check_equal(result, "type_mismatch", "Type mismatch detected for existing column")

    # --- Custom table creation ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            monitor_id TEXT,
            date TEXT,
            report_json TEXT
        )
    """)
    conn.commit()
    table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_summaries'"
    ).fetchone()
    t.check(table_exists is not None, "Custom table daily_summaries created")

    # --- Prompt ↔ Schema validation ---
    prompt1 = """Please analyze the video and output:
EVENT: <event type>
SEVERITY: <low/medium/high/critical>
DESC: <description of what happened>"""

    v1 = validate_prompt_schema(["event", "severity", "desc"], prompt1)
    t.check_equal(v1["valid"], True, "Prompt with all required fields passes validation")
    t.check_equal(len(v1["missing"]), 0, "No missing fields")

    prompt2 = "Please tell me what you notice in this clip."
    v2 = validate_prompt_schema(["event", "severity", "desc"], prompt2)
    t.check_equal(v2["valid"], False, "Prompt missing fields fails validation")
    t.check_equal(len(v2["missing"]), 3, f"3 missing fields (got {len(v2['missing'])})")

    prompt3 = "Output the EVENT and SEVERITY for this clip."
    v3 = validate_prompt_schema(["event", "severity", "desc"], prompt3)
    t.check_equal(v3["valid"], False, "Partial prompt fails validation")
    t.check("desc" in v3["missing"], "Reports 'desc' as missing")

    conn.close()
    cleanup_dir(tmp)

    passed = t.summary()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
