# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""The settings UI transcribes the feature dependency graph; this catches drift.

model_manager/features/resolver.py auto-enables whatever a live feature depends
on, so the Configuration screen warns when a toggle in config.yaml will be
overridden. It cannot ask the backend for the graph — that screen is what you use
before the backend has ever started — so config-schema.cjs carries a copy, and
adding a feature or changing its `depends_on` without updating that copy makes
the warning quietly wrong.

Both sides are read from source with no imports: model_manager/features/
asr_feature.py pulls in `pipeline` and `components.ffmpeg`, so importing REGISTRY
would drag OpenVINO into a unit test.
"""

import ast
import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_FEATURES_DIR = _ROOT / "model_manager" / "features"
_SCHEMA = _ROOT / "ui" / "electron" / "services" / "config-schema.cjs"


def _class_literal(node: ast.ClassDef, name: str):
    """A class-level `name: T = <literal>`, or None when absent."""
    for statement in node.body:
        target = getattr(statement, "target", None)
        if isinstance(statement, ast.AnnAssign) and isinstance(target, ast.Name) and target.id == name:
            return ast.literal_eval(statement.value)
    return None


def _python_graph() -> dict:
    graph = {}
    for source in sorted(_FEATURES_DIR.glob("*_feature.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            feature_id = _class_literal(node, "id")
            if feature_id is None:
                continue
            graph[feature_id] = sorted(_class_literal(node, "depends_on") or [])
    return graph


def _schema_graph() -> dict:
    text = _SCHEMA.read_text(encoding="utf-8")
    block = re.search(r"^const FEATURES = (\{.*?^\});$", text, re.DOTALL | re.MULTILINE)
    assert block, f"FEATURES table not found in {_SCHEMA}"

    # JS object literal -> JSON: quote the bare keys, swap the quote style, drop
    # the trailing commas JSON rejects.
    body = block.group(1)
    body = re.sub(r"(^|[{,\s])([A-Za-z_][A-Za-z0-9_]*):", r'\1"\2":', body)
    body = body.replace("'", '"')
    body = re.sub(r",(\s*[}\]])", r"\1", body)
    table = json.loads(body)

    return {fid: sorted(spec["dependsOn"]) for fid, spec in table.items()}


def test_schema_lists_every_feature():
    assert set(_schema_graph()) == set(_python_graph())


def test_schema_mirrors_depends_on():
    assert _schema_graph() == _python_graph()


def test_every_dependency_is_a_known_feature():
    graph = _python_graph()
    for feature_id, dependencies in graph.items():
        unknown = [dep for dep in dependencies if dep not in graph]
        assert not unknown, f"{feature_id} depends on unregistered feature(s): {unknown}"


def test_schema_labels_every_feature():
    text = _SCHEMA.read_text(encoding="utf-8")
    block = re.search(r"^const FEATURES = (\{.*?^\});$", text, re.DOTALL | re.MULTILINE)
    for feature_id in _python_graph():
        assert f"{feature_id}:" in block.group(1), f"{feature_id} has no entry in the UI FEATURES table"
        assert re.search(rf"{feature_id}: \{{ label: '[^']+'", block.group(1)), f"{feature_id} has no label"
