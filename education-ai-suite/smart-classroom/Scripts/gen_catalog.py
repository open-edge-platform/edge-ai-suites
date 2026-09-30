#!/usr/bin/env python
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Write the UI's copies of utils/pipeline_catalog.py and utils/requirements.py.

    python Scripts/gen_catalog.py            # write the files
    python Scripts/gen_catalog.py --check    # exit 1 if any is stale

The copies are committed because neither consumer can read the Python: the
Electron main process is packaged without it and runs before the backend
starts, and the renderer needs `SessionStage` as a compile-time union type.

tests/unit/test_catalog_generated.py runs --check.
"""

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from utils import pipeline_catalog as pc  # noqa: E402  (needs _ROOT on the path)
from utils import requirements as req  # noqa: E402

_BANNER_TEMPLATE = """\
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// GENERATED FILE - do not edit.
// Written by Scripts/gen_catalog.py from {source}. Edit there and re-run it.
"""


def _banner(source: str) -> str:
    return _BANNER_TEMPLATE.format(source=source)


_CATALOG_BANNER = _banner("utils/pipeline_catalog.py")


def _js(value) -> str:
    """A JS literal for a str / None / list / tuple, single-quoted to match the
    surrounding code."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value).replace('"', "'")
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_js(v) for v in value) + "]"
    raise TypeError(f"no JS form for {value!r}")


def _by(attr: str) -> dict:
    """Group feature ids by one nullable spec attribute, in catalog order."""
    grouped: dict = {}
    for spec in pc.CATALOG:
        key = getattr(spec, attr)
        if key is None:
            continue
        grouped.setdefault(key, []).append(spec.id)
    return grouped


# ---------------------------------------------------------------------------
# ui/electron/services/feature-catalog.cjs
# ---------------------------------------------------------------------------

def _electron_catalog() -> str:
    rows = []
    for spec in pc.CATALOG:
        rows.append(
            f"  {spec.id}: {{ label: {_js(spec.label)}, "
            f"dependsOn: {_js(list(spec.depends_on))}, "
            f"stage: {_js(spec.stage)}, "
            f"input: {_js(spec.input)}, "
            f"screen: {_js(spec.screen)} }},"
        )
    required_by = "\n".join(
        f"  {fid}: {_js(list(consumers))},"
        for fid, consumers in pc.REQUIRED_BY.items()
    )
    return f"""{_CATALOG_BANNER}
// Every feature, in settings-screen toggle order. `dependsOn` is what must be
// ENABLED; features/resolver.py auto-enables it at startup.
const FEATURES = {{
{chr(10).join(rows)}
}};

// Feature id -> every feature whose presence drags it in, however deep.
const REQUIRED_BY = {{
{required_by}
}};

// Every pipeline stage, in run order.
const STAGE_ORDER = {_js(list(pc.ALL_STAGES))};

module.exports = {{ FEATURES, REQUIRED_BY, STAGE_ORDER }};
"""


# ---------------------------------------------------------------------------
# ui/src/generated/pipeline.ts
# ---------------------------------------------------------------------------

def _ts_union(values) -> str:
    return " | ".join(_js(v) for v in values)


def _ts_record(mapping, value_fn=_js, indent="  ") -> str:
    return "\n".join(f"{indent}{k}: {value_fn(v)}," for k, v in mapping.items())


def _renderer_catalog() -> str:
    by_input = _by("input")
    by_screen = _by("screen")
    return f"""{_CATALOG_BANNER}
/** Every feature the backend can expose. */
export type FeatureId = {_ts_union(pc.FEATURE_IDS)};

/** The pipeline stages the session API knows about. */
export type SessionStage = {_ts_union(pc.ALL_STAGES)};

/** The source a stage needs to be worth declaring. */
export type PipelineInput = {_ts_union(sorted(by_input))};

/** The screen a feature belongs to, for the app's auto-switch. */
export type FeatureScreen = {_ts_union(sorted(by_screen))};

export const FEATURE_IDS: readonly FeatureId[] = {_js(list(pc.FEATURE_IDS))};

/**
 * Stage order, as the backend runs them. A session's table always carries every
 * one; the stages it did not declare are 'skipped' rather than absent.
 */
export const STAGE_ORDER: readonly SessionStage[] = {_js(list(pc.ALL_STAGES))};

/** The stage each feature owns. Features without one are absent. */
export const FEATURE_STAGE: Readonly<Partial<Record<FeatureId, SessionStage>>> = {{
{_ts_record(pc.FEATURE_STAGE)}
}};

/** The feature that owns each stage. */
export const STAGE_FEATURE: Readonly<Record<SessionStage, FeatureId>> = {{
{_ts_record(pc.STAGE_TO_FEATURE)}
}};

/**
 * What has to have FINISHED before a stage may start. A different graph from
 * `dependsOn`, which is what has to be ENABLED.
 */
export const STAGE_RUN_AFTER: Readonly<Record<SessionStage, readonly SessionStage[]>> = {{
{_ts_record({k: list(v) for k, v in pc.STAGE_RUN_AFTER.items()})}
}};

/** The input a stage needs before a session should declare it. */
export const STAGE_INPUT: Readonly<Record<SessionStage, PipelineInput>> = {{
{_ts_record(pc.STAGE_INPUT)}
}};

/** Features grouped by the input they work from. */
export const FEATURES_BY_INPUT: Readonly<Record<PipelineInput, readonly FeatureId[]>> = {{
{_ts_record(by_input)}
}};

/** Features grouped by the screen they belong to. */
export const FEATURES_BY_SCREEN: Readonly<Record<FeatureScreen, readonly FeatureId[]>> = {{
{_ts_record(by_screen)}
}};

/** Every value a stage's status can take. */
export const STAGE_STATUSES: readonly string[] = {_js(list(pc.STAGE_STATUSES))};

/** A stage that will not change again on its own. */
export const SETTLED_STAGE_STATUSES: readonly string[] = {_js(list(pc.SETTLED_STAGE_STATUSES))};

export const SESSION_STATES: readonly string[] = {_js(list(pc.SESSION_STATES))};

/** States a session cannot move out of. */
export const TERMINAL_SESSION_STATES: readonly string[] = {_js(list(pc.TERMINAL_SESSION_STATES))};
"""


# ---------------------------------------------------------------------------
# ui/electron/services/requirements-catalog.cjs
# ---------------------------------------------------------------------------

def _electron_requirements() -> str:
    return f"""{_banner("utils/requirements.py")}
// Only the thresholds the backend checks too. Disk space, driver versions and
// download URLs are the Setup screen's own; see setup-runner.cjs.

const MIN_MEMORY_GB = {req.MIN_MEMORY_GB};
const REQUIRED_OS = {_js(req.REQUIRED_OS)};
const MIN_WINDOWS_BUILD = {req.MIN_WINDOWS_BUILD};
const PYTHON_TARGET = [{req.REQUIRED_PYTHON_MAJOR}, {req.REQUIRED_PYTHON_MINOR}];
const REQUIRED_DLSTREAMER = {_js(req.dlstreamer_version_str())};

module.exports = {{
  MIN_MEMORY_GB,
  REQUIRED_OS,
  MIN_WINDOWS_BUILD,
  PYTHON_TARGET,
  REQUIRED_DLSTREAMER,
}};
"""


# ---------------------------------------------------------------------------

OUTPUTS = {
    "ui/electron/services/feature-catalog.cjs": _electron_catalog,
    "ui/electron/services/requirements-catalog.cjs": _electron_requirements,
    "ui/src/generated/pipeline.ts": _renderer_catalog,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if any generated file is missing or stale",
    )
    args = parser.parse_args()

    stale = []
    for rel, render in OUTPUTS.items():
        path = _ROOT / rel
        wanted = render()
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == wanted:
            continue
        if args.check:
            stale.append(rel)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(wanted, encoding="utf-8", newline="\n")
        print(f"wrote {rel}")

    if stale:
        print(
            "Stale generated file(s): "
            + ", ".join(stale)
            + "\nRun: python Scripts/gen_catalog.py",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
