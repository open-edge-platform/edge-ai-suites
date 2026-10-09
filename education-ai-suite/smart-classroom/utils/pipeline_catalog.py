# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Every feature and pipeline stage, declared once.

The Electron main process and the React renderer read generated copies of this
(`Scripts/gen_catalog.py`, checked by `tests/unit/test_catalog_generated.py`).
Edit here, then re-run the generator.

Imports nothing but `dataclasses`, and lives in `utils/` rather than
`model_manager/features/`, so reading it never pulls in OpenVINO.

Two separate graphs: `depends_on` is what must be *enabled* (resolver.py
auto-enables it), `run_after` is what must have *finished* (the orchestrator and
the UI stage chain wait on it). Segmentation runs after `va` without requiring
it to be on, which is why they are not one field.
"""

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class FeatureSpec:
    """One row of the catalog.

    A feature owns a `stage` if its work gets a row in the session store, a
    status and a history pip. Features reached straight from the UI (board OCR,
    content search, QA, grading) own none.
    """

    id: str
    label: str                              # plain English, for the settings screen
    depends_on: Tuple[str, ...] = ()        # features that must be ENABLED
    stage: Optional[str] = None             # the pipeline stage this feature owns
    run_after: Tuple[str, ...] = ()         # stages that must have FINISHED
    input: Optional[str] = None             # source the stage needs
    screen: Optional[str] = None            # UI screen this feature belongs to


# Declaration order must track the `features:` block of config.yaml: it is the
# settings-screen toggle order and the tie-break for ALL_STAGES.
CATALOG: Tuple[FeatureSpec, ...] = (
    FeatureSpec(
        id="asr",
        label="Speech recognition",
        stage="transcribe",
        input="audio",
        screen="main",
    ),
    FeatureSpec(
        id="summary",
        label="Summary",
        depends_on=("asr",),
        stage="summarize",
        run_after=("transcribe",),
        input="audio",
        screen="main",
    ),
    FeatureSpec(
        id="mindmap",
        label="Mind map",
        depends_on=("summary",),
        stage="mindmap",
        run_after=("summarize",),
        input="audio",
        screen="main",
    ),
    FeatureSpec(
        id="topic_segmentation",
        label="Topic segmentation",
        depends_on=("asr", "content_search"),
        stage="segmentation",
        # Includes `va`: topics are matched against the video timeline.
        run_after=("transcribe", "summarize", "mindmap", "va"),
        input="audio",
        screen="main",
    ),
    FeatureSpec(
        id="video_analytics",
        label="Video analytics",
        stage="va",
        input="video",
        screen="main",
    ),
    FeatureSpec(
        id="board_ocr",
        label="Board OCR",
        depends_on=("video_analytics",),
        # No screen: it feeds the summary and never decides which screen opens.
    ),
    FeatureSpec(
        id="content_search",
        label="Content search",
        screen="content_search",
    ),
    FeatureSpec(
        id="qa",
        label="Question answering",
        depends_on=("content_search",),
        screen="content_search",
    ),
    FeatureSpec(
        id="grading",
        label="Grading",
        screen="grading",
    ),
    FeatureSpec(
        id="report",
        label="Report",
        depends_on=("summary", "mindmap", "topic_segmentation", "video_analytics"),
        stage="report",
        run_after=("segmentation",),
        input="audio",
        screen="main",
    ),
)


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

def topo_sort(
    ids: Sequence[str],
    edges_of: Callable[[str], Iterable[str]],
    what: str = "node",
) -> List[str]:
    """Dependency-first ordering: every edge target comes out before its source.

    Independent nodes keep the order of `ids`, so the result is reproducible.
    Raises ValueError on a cycle or an edge pointing outside `ids`.
    """
    known = set(ids)
    ordered: List[str] = []
    done: set = set()

    def visit(node: str, stack: List[str]) -> None:
        if node in done:
            return
        if node in stack:
            raise ValueError(f"Dependency cycle detected: {' -> '.join([*stack, node])}")
        if node not in known:
            raise ValueError(f"Unknown {what}: {node!r}")
        for dep in edges_of(node):
            visit(dep, [*stack, node])
        done.add(node)
        ordered.append(node)

    for node in ids:
        visit(node, [])
    return ordered


# ---------------------------------------------------------------------------
# Derived views
# ---------------------------------------------------------------------------

FEATURES: Dict[str, FeatureSpec] = {spec.id: spec for spec in CATALOG}

FEATURE_IDS: Tuple[str, ...] = tuple(FEATURES)

#: Feature id -> the stage it owns. Features without one are absent.
FEATURE_STAGE: Dict[str, str] = {
    spec.id: spec.stage for spec in CATALOG if spec.stage
}

#: Stage -> the feature that owns it.
STAGE_TO_FEATURE: Dict[str, str] = {
    stage: fid for fid, stage in FEATURE_STAGE.items()
}

STAGE_RUN_AFTER: Dict[str, Tuple[str, ...]] = {
    spec.stage: spec.run_after for spec in CATALOG if spec.stage
}

#: Stage -> the input a session needs before declaring it.
STAGE_INPUT: Dict[str, Optional[str]] = {
    spec.stage: spec.input for spec in CATALOG if spec.stage
}

#: Every stage, in run order, derived from `run_after`. Pinned by
#: tests/unit/test_pipeline_catalog.py: reordering rewrites session rows.
ALL_STAGES: Tuple[str, ...] = tuple(
    topo_sort(
        list(STAGE_RUN_AFTER),
        lambda stage: STAGE_RUN_AFTER[stage],
        what="stage",
    )
)


def _required_by() -> Dict[str, Tuple[str, ...]]:
    """Feature id -> every feature whose presence drags it in, however deep.

    The reverse of resolver.py's closure. registry.cjs uses it to decide which
    services boot.
    """
    reverse: Dict[str, set] = {spec.id: set() for spec in CATALOG}

    def walk(root: str, node: str, stack: Tuple[str, ...]) -> None:
        for dep in FEATURES[node].depends_on:
            if dep in stack:  # cycle guard; topo_sort reports it
                continue
            reverse[dep].add(root)
            walk(root, dep, (*stack, dep))

    for spec in CATALOG:
        walk(spec.id, spec.id, (spec.id,))

    # Declaration order, so generated output is byte-stable.
    return {
        fid: tuple(f for f in FEATURE_IDS if f in consumers)
        for fid, consumers in reverse.items()
    }


REQUIRED_BY: Dict[str, Tuple[str, ...]] = _required_by()


# ---------------------------------------------------------------------------
# Status vocabularies
# ---------------------------------------------------------------------------

#: Written by stage_tracker.py. A session's table always holds every stage in
#: ALL_STAGES; the ones it did not declare carry 'skipped'.
STAGE_STATUSES: Tuple[str, ...] = (
    "pending",
    "running",
    "done",
    "failed",
    "interrupted",
    "skipped",
)

#: A stage that will not change again on its own.
SETTLED_STAGE_STATUSES: Tuple[str, ...] = ("done", "failed", "interrupted")

SESSION_STATES: Tuple[str, ...] = (
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
)

#: States a session cannot move out of.
TERMINAL_SESSION_STATES: Tuple[str, ...] = ("completed", "failed", "cancelled")
