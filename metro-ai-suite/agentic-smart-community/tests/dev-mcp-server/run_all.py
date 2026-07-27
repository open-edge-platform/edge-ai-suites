#!/usr/bin/env python3
"""Run all MCP Server development tests sequentially."""

import subprocess
import sys
from pathlib import Path

TEST_DIR = Path(__file__).parent

TESTS = [
    "test_db.py",
    "test_schema.py",
    "test_rule_engine.py",
    "test_use_cases.py",
    "test_events_webhook.py",
    # test_video_worker.py removed — the end-to-end video-worker path is exercised
    # by tests/mock/videostream-analytics/mock_server.py against a real
    # multilevel-video-understanding container (WW27 e2e work).
    "test_tools_mcp.py",
    "test_use_case_register.py",
]


def main():
    print("╔══════════════════════════════════════════╗")
    print("║  SmartBuilding Video MCP Server Tests    ║")
    print("╚══════════════════════════════════════════╝")
    print()

    passed = 0
    failed = 0

    for test in TESTS:
        test_path = TEST_DIR / test
        try:
            result = subprocess.run(
                [sys.executable, str(test_path)],
                cwd=str(TEST_DIR.parent.parent),
                timeout=30,
            )
            if result.returncode == 0:
                passed += 1
            else:
                failed += 1
        except subprocess.TimeoutExpired:
            print(f"\n  ⚠ {test} timed out!")
            failed += 1
        except Exception as e:
            print(f"\n  ⚠ {test} error: {e}")
            failed += 1
        print()

    total = len(TESTS)
    print("═══════════════════════════════════════════")
    print(f"Results: {passed} passed, {failed} failed, {total} total")
    print("═══════════════════════════════════════════")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
