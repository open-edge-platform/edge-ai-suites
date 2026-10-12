import ast
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from robot_files.test_suite import test_suite


ROOT = Path(__file__).parents[1]


class SubprocessSecurityTests(TestCase):
    def test_python_suite_does_not_enable_shell_parsing(self):
        for path in ROOT.rglob("*.py"):
            if any(part in {".venv", "node_modules", "artifacts", "logs"} for part in path.parts):
                continue
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr not in {"run", "call", "check_output", "Popen"}:
                    continue
                self.assertFalse(
                    any(
                        keyword.arg == "shell"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                        for keyword in node.keywords
                    ),
                    f"unsafe shell parsing found in {path}:{node.lineno}",
                )

    @patch("robot_files.test_suite.subprocess.call", return_value=0)
    def test_robot_launcher_passes_arguments_without_a_shell(self, call):
        self.assertEqual(test_suite().TC_001_SP(), 0)
        self.assertEqual(
            call.call_args.args[0],
            [sys.executable, "-m", "unittest", "functional_tests.apps.TestCaseManager.test_apps", "-v"],
        )
        self.assertEqual(call.call_args.kwargs["cwd"], str(ROOT))
        self.assertFalse(call.call_args.kwargs.get("shell", False))


if __name__ == "__main__":
    import unittest

    unittest.main()
