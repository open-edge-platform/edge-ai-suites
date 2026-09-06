# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Scan automated tests for structured Jira Feature traceability metadata."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


JIRA_KEY_PATTERN = re.compile(r"^ITEP-\d+$", re.IGNORECASE)
JIRA_DOCSTRING_PATTERN = re.compile(
    r"^\s*Jira-Feature:\s*(ITEP-\d+)\s*$", re.IGNORECASE | re.MULTILINE
)
CRITERION_DOCSTRING_PATTERN = re.compile(
    r"^\s*Jira-Criterion:\s*(AC-\d+)\s*$", re.IGNORECASE | re.MULTILINE
)
ROBOT_JIRA_PATTERN = re.compile(r"\bjira:(ITEP-\d+)\b", re.IGNORECASE)
ROBOT_CRITERION_PATTERN = re.compile(r"\bcriterion:(AC-\d+)\b", re.IGNORECASE)
IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "env",
    "node_modules",
    "venv",
}


@dataclass(frozen=True)
class CoverageReference:
    """One structured link from an automated test to a Jira Feature."""

    feature: str
    criterion: str | None
    framework: str
    path: str
    test: str
    source: str


@dataclass
class ScanResult:
    """Serializable result of a repository test-metadata scan."""

    root: str
    files_scanned: int
    references: list[CoverageReference]
    parse_errors: list[dict[str, str]]


def _reference_sort_key(reference: CoverageReference) -> tuple[str, str, str, str, str, str]:
    return (
        reference.feature,
        reference.criterion or "",
        reference.path,
        reference.test,
        reference.framework,
        reference.source,
    )


def _is_test_file(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    in_test_directory = any(part.lower() in {"test", "tests"} for part in relative_parts[:-1])
    if path.suffix == ".robot":
        return in_test_directory
    if path.suffix != ".py":
        return False
    return in_test_directory or path.name.startswith("test_") or path.name.endswith("_test.py")


def _iter_test_files(root: Path) -> Iterable[Path]:
    for directory, directory_names, file_names in os.walk(root):
        directory_names[:] = sorted(
            name for name in directory_names if name not in IGNORED_DIRECTORIES
        )
        for file_name in sorted(file_names):
            path = Path(directory, file_name)
            if _is_test_file(path, root):
                yield path


def _string_constant(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _metadata_pairs(features: list[str], criteria: list[str]) -> list[tuple[str, str | None]]:
    normalized_features = [feature.upper() for feature in features]
    normalized_criteria = [criterion.upper() for criterion in criteria]
    if not normalized_criteria:
        return [(feature, None) for feature in normalized_features]
    if len(normalized_criteria) == len(normalized_features):
        return list(zip(normalized_features, normalized_criteria))
    if len(normalized_criteria) == 1:
        return [(feature, normalized_criteria[0]) for feature in normalized_features]
    return [(feature, None) for feature in normalized_features]


def _pytest_marker_metadata(
    decorators: list[ast.expr],
) -> list[tuple[str, str | None]]:
    metadata: list[tuple[str, str | None]] = []
    for decorator in decorators:
        if not isinstance(decorator, ast.Call):
            continue
        marker_name = decorator.func.attr if isinstance(decorator.func, ast.Attribute) else None
        if marker_name != "jira_feature" or not decorator.args:
            continue
        feature = _string_constant(decorator.args[0])
        if not feature or not JIRA_KEY_PATTERN.fullmatch(feature):
            continue
        criterion = None
        for keyword in decorator.keywords:
            if keyword.arg == "criterion":
                criterion = _string_constant(keyword.value)
                break
        metadata.append(
            (feature.upper(), criterion.upper() if criterion else None)
        )
    return metadata


def _docstring_metadata(node: ast.AST) -> list[tuple[str, str | None]]:
    docstring = ast.get_docstring(node, clean=False) or ""
    features = JIRA_DOCSTRING_PATTERN.findall(docstring)
    criteria = CRITERION_DOCSTRING_PATTERN.findall(docstring)
    return _metadata_pairs(features, criteria)


def _scan_python(path: Path, root: Path) -> tuple[list[CoverageReference], str | None]:
    relative_path = path.relative_to(root).as_posix()
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeError) as error:
        return [], str(error)

    references: set[CoverageReference] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.ClassDef):
            is_test_node = node.name.startswith("Test")
        else:
            is_test_node = node.name.startswith("test")
        if not is_test_node:
            continue

        marker_metadata = _pytest_marker_metadata(node.decorator_list)
        docstring_metadata = _docstring_metadata(node)
        for feature, criterion in marker_metadata:
            references.add(
                CoverageReference(
                    feature=feature,
                    criterion=criterion,
                    framework="pytest",
                    path=relative_path,
                    test=node.name,
                    source="marker",
                )
            )
        marker_features = {feature for feature, _ in marker_metadata}
        for feature, criterion in docstring_metadata:
            if feature in marker_features:
                continue
            references.add(
                CoverageReference(
                    feature=feature,
                    criterion=criterion,
                    framework="python",
                    path=relative_path,
                    test=node.name,
                    source="docstring",
                )
            )
    return sorted(references, key=_reference_sort_key), None


def _scan_robot(path: Path, root: Path) -> tuple[list[CoverageReference], str | None]:
    relative_path = path.relative_to(root).as_posix()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        return [], str(error)

    references: set[CoverageReference] = set()
    in_test_cases = False
    current_test = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("***"):
            in_test_cases = stripped.lower() == "*** test cases ***"
            current_test = ""
            continue
        if not in_test_cases or not stripped or stripped.startswith("#"):
            continue
        if not line[0].isspace():
            current_test = stripped
            continue
        if not current_test or not stripped.lower().startswith("[tags]"):
            continue
        features = ROBOT_JIRA_PATTERN.findall(stripped)
        criteria = ROBOT_CRITERION_PATTERN.findall(stripped)
        for feature, criterion in _metadata_pairs(features, criteria):
            references.add(
                CoverageReference(
                    feature=feature,
                    criterion=criterion,
                    framework="robot",
                    path=relative_path,
                    test=current_test,
                    source="tag",
                )
            )
    return sorted(references, key=_reference_sort_key), None


def scan(root: Path) -> ScanResult:
    """Scan test files below root and return structured Jira references."""

    resolved_root = root.resolve()
    references: list[CoverageReference] = []
    parse_errors: list[dict[str, str]] = []
    files_scanned = 0
    for path in _iter_test_files(resolved_root):
        files_scanned += 1
        if path.suffix == ".py":
            file_references, error = _scan_python(path, resolved_root)
        else:
            file_references, error = _scan_robot(path, resolved_root)
        references.extend(file_references)
        if error:
            parse_errors.append(
                {"path": path.relative_to(resolved_root).as_posix(), "error": error}
            )

    return ScanResult(
        root=str(resolved_root),
        files_scanned=files_scanned,
        references=sorted(set(references), key=_reference_sort_key),
        parse_errors=parse_errors,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan tests for Jira Feature traceability metadata."
    )
    parser.add_argument("root", type=Path, help="Repository or component root to scan")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.root.is_dir():
        raise SystemExit(f"Scan root is not a directory: {args.root}")
    result = scan(args.root)
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 1 if result.parse_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())