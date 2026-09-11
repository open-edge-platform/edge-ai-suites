# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIRECTORY))

from scan_feature_coverage import scan


class ScanFeatureCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_test_file(self, relative_path: str, content: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_scans_pytest_marker_and_structured_docstring(self) -> None:
        self.write_test_file(
            "tests/test_features.py",
            '''import pytest

@pytest.mark.jira_feature("ITEP-72525", criterion="AC-1")
def test_marker():
    pass

def test_docstring():
    """Verify another criterion.

    Jira-Feature: ITEP-83658
    Jira-Criterion: AC-2
    """
''',
        )

        result = scan(self.root)

        self.assertEqual(
            [(reference.feature, reference.criterion, reference.source) for reference in result.references],
            [
                ("ITEP-72525", "AC-1", "marker"),
                ("ITEP-83658", "AC-2", "docstring"),
            ],
        )
        self.assertEqual(result.parse_errors, [])

    def test_scans_robot_framework_tags(self) -> None:
        self.write_test_file(
            "tests/features.robot",
            """*** Test Cases ***
Deploy with Helm
    [Tags]    jira:ITEP-81717    criterion:AC-1
    No Operation
""",
        )

        result = scan(self.root)

        self.assertEqual(len(result.references), 1)
        self.assertEqual(result.references[0].feature, "ITEP-81717")
        self.assertEqual(result.references[0].criterion, "AC-1")
        self.assertEqual(result.references[0].test, "Deploy with Helm")

    def test_ignores_unstructured_jira_references(self) -> None:
        self.write_test_file(
            "tests/test_unstructured.py",
            """def test_unstructured():
    # ITEP-99999 is not structured traceability metadata.
    pass
""",
        )

        result = scan(self.root)

        self.assertEqual(result.references, [])

    def test_sorts_feature_references_with_and_without_criteria(self) -> None:
        self.write_test_file(
            "tests/test_mixed.py",
            '''import pytest

@pytest.mark.jira_feature("ITEP-72525")
def test_feature_level():
    pass

@pytest.mark.jira_feature("ITEP-72525", criterion="AC-1")
def test_criterion_level():
    pass
''',
        )

        result = scan(self.root)

        self.assertEqual(len(result.references), 2)
        self.assertIsNone(result.references[0].criterion)
        self.assertEqual(result.references[1].criterion, "AC-1")

    def test_reports_python_parse_errors(self) -> None:
        self.write_test_file("tests/test_invalid.py", "def test_invalid(:\n")

        result = scan(self.root)

        self.assertEqual(result.references, [])
        self.assertEqual(result.parse_errors[0]["path"], "tests/test_invalid.py")


if __name__ == "__main__":
    unittest.main()