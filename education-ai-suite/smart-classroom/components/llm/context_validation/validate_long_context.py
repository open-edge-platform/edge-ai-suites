# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Sweep candidate summarizer models across context lengths to find the maximum
context each one can reliably handle on this hardware, versus the customer's
target (default 160K tokens).

This is a standalone diagnostic tool: it reads its own bundled config.yaml
(next to this script), never smart-classroom/config.yaml. It is independent of
the production summarizer -- running it, or editing its config, never affects
the running application.

Simplest way to run it (handles venv creation/activation, see setup_env.ps1 /
run_validate_long_context.ps1 -- mirrors setup-smart-classroom.ps1 /
start-smart-classroom.ps1's own venv convention):

    .\\components\\llm\\context_validation\\run_validate_long_context.ps1
    .\\components\\llm\\context_validation\\run_validate_long_context.ps1 --dry-run
    .\\components\\llm\\context_validation\\run_validate_long_context.ps1 --models Qwen/Qwen3-8B --refine

Equivalent, if you already have the right interpreter active (run from the
smart-classroom/ directory so relative model paths resolve):

    python -m components.llm.context_validation.validate_long_context

See docs/dev-guide/validate_long_context.md for the full design and usage guide.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import multiprocessing
import os
import re
import sys
import time
from datetime import datetime
from queue import Empty

from components.llm.context_validation import trial_runner
from utils.config_loader import load_config
from utils.storage_manager import StorageManager

_TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG_PATH = os.path.join(_TOOL_DIR, "config.yaml")

# smart-classroom/ is 3 levels up from this file's directory
# (context_validation -> llm -> components -> smart-classroom).
_SC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_TOOL_DIR)))
# setup-smart-classroom.ps1 creates the backend venv as a sibling of smart-classroom/,
# named "smartclassroom" (no hyphen) -- see $venvBackend in that script.
_BACKEND_VENV_PYTHON = os.path.join(os.path.dirname(_SC_ROOT), "smartclassroom", "Scripts", "python.exe")
_SETUP_SCRIPT = os.path.join(_TOOL_DIR, "setup_env.ps1")
_LAUNCHER_SCRIPT = os.path.join(_TOOL_DIR, "run_validate_long_context.ps1")

_REQUIRED_MODULES = ("openvino_genai", "transformers")

# Mirrors content_search/providers/utils/model_utils.py::is_model_ready. A converted
# candidate can be a plain causal LM (openvino_model.xml) or a multimodal/VLM export
# (openvino_language_model.xml plus vision-embedding components), so this matches
# either layout instead of assuming the plain-LLM one.
_MODEL_IR_RE = re.compile(r"(.*)?openvino(.*)?_model(.*)?\.xml$")
_TOKENIZER_IR_NAME = "openvino_tokenizer.xml"
_DETOKENIZER_IR_NAME = "openvino_detokenizer.xml"

TRIAL_CSV_FIELDS = [
    "model",
    "tokens_requested",
    "device",
    "weight_format",
    "load_ok",
    "load_time_s",
    "generate_ok",
    "accuracy",
    "error",
    "probes_json",
]


def _parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Find the max context length each candidate summarizer model can "
            "handle on this hardware, against the configured target (default 160K)."
        ),
    )
    parser.add_argument(
        "--config",
        default=_DEFAULT_CONFIG_PATH,
        help="Path to this tool's own config.yaml (default: the file bundled next to this "
        "script -- independent of smart-classroom/config.yaml)",
    )
    parser.add_argument("--models", nargs="+", help="Override models.summarizer.long_context_validation.candidate_models")
    parser.add_argument("--target-tokens", type=int, help="Override target_context_tokens")
    parser.add_argument("--steps", type=int, nargs="+", help="Override context_steps_tokens")
    parser.add_argument("--device", help="Override models.summarizer.device (e.g. GPU, CPU)")
    parser.add_argument("--weight-format", help="Override models.summarizer.weight_format")
    parser.add_argument(
        "--refine",
        action="store_true",
        help="Bisect near the pass/fail boundary to tighten the reported ceiling (up to 3 extra trials per model)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Exercise the sweep/reporting pipeline with a synthetic fake trial -- no OpenVINO/GPU required",
    )
    parser.add_argument("--output-dir", help="Override output_dir")
    return parser.parse_args()


def _load_settings(args) -> dict:
    cfg = load_config(args.config)
    summarizer = getattr(cfg, "summarizer", None)
    lcv = getattr(summarizer, "long_context_validation", None) if summarizer else None
    if lcv is None:
        raise SystemExit(
            f"summarizer.long_context_validation is missing from {args.config}. "
            "See docs/dev-guide/validate_long_context.md for the expected schema."
        )
    return {
        "provider": summarizer.provider,
        "models_base_path": summarizer.models_base_path,
        "device": args.device or summarizer.device,
        "weight_format": args.weight_format or summarizer.weight_format,
        "candidate_models": args.models or lcv.candidate_models,
        "target_context_tokens": args.target_tokens or lcv.target_context_tokens,
        "context_steps_tokens": sorted(args.steps or lcv.context_steps_tokens),
        "accuracy_threshold": lcv.accuracy_threshold,
        "needle_probe_depths": lcv.needle_probe_depths,
        "max_new_tokens_probe": lcv.max_new_tokens_probe,
        "answer_preamble_chars": getattr(lcv, "answer_preamble_chars", 400),
        "trial_timeout_sec": lcv.trial_timeout_sec,
        "output_dir": args.output_dir or lcv.output_dir,
        "refine": args.refine,
    }


def _model_ir_dir(models_base_path: str, provider: str, model_name: str, weight_format: str) -> str:
    # Mirrors utils/ensure_model.py::get_model_path's path convention, parameterized
    # per candidate model instead of hardcoded to config.models.summarizer.name.
    return os.path.join(models_base_path, provider, f"{model_name.replace('/', '_')}_{weight_format}")


def _ir_ready(model_dir: str) -> bool:
    if not os.path.isdir(model_dir):
        return False
    xml_names = []
    for _root, _dirs, files in os.walk(model_dir):
        xml_names.extend(f for f in files if f.endswith(".xml"))
    has_model = any(_MODEL_IR_RE.search(name) for name in xml_names)
    has_tokenizer = _TOKENIZER_IR_NAME in xml_names
    has_detokenizer = _DETOKENIZER_IR_NAME in xml_names
    return has_model and has_tokenizer and has_detokenizer


def _prep_command(model_name: str, model_dir: str, weight_format: str) -> str:
    return (
        f'optimum-cli export openvino --model "{model_name}" --trust-remote-code '
        f'--weight-format {weight_format} "{model_dir}"'
    )


def _safe_platform_info() -> dict:
    try:
        from utils.platform_info import get_platform_and_model_info

        return get_platform_and_model_info()
    except Exception:
        return {}


def _append_trial_row(output_dir: str, row: dict) -> None:
    path = os.path.join(output_dir, "trials.csv")
    flat = {
        "model": row["model"],
        "tokens_requested": row.get("tokens_requested"),
        "device": row["device"],
        "weight_format": row["weight_format"],
        "load_ok": row.get("load_ok"),
        "load_time_s": row.get("load_time_s"),
        "generate_ok": row.get("generate_ok"),
        "accuracy": row.get("accuracy"),
        "error": row.get("error"),
        "probes_json": json.dumps(row.get("probes", []), ensure_ascii=False),
    }
    StorageManager.save_csv(path, flat, headers=TRIAL_CSV_FIELDS, append=True)


def _fake_ceiling_tokens(model_name: str, steps: list) -> int:
    """Deterministic per-model fake ceiling so --dry-run exercises a mix of
    pass/fail across the configured steps without touching any hardware."""
    digest = sum(ord(c) for c in model_name)
    return steps[digest % len(steps)]


def _run_trial_dry_run(model_name: str, tokens: int, probe_depths: list, fake_ceiling: int) -> dict:
    ok = tokens <= fake_ceiling
    return {
        "tokens_requested": tokens,
        "load_ok": True,
        "load_time_s": 0.01,
        "generate_ok": True,
        "accuracy": 0.95 if ok else 0.3,
        "probes": [
            {"depth": d, "tokens_actual": tokens, "correct": ok, "generate_time_s": 0.01}
            for d in probe_depths
        ],
        "error": None if ok else "accuracy_below_threshold(dry-run)",
    }


def _run_trial_subprocess(
    model_dir: str,
    model_name: str,
    device: str,
    tokens: int,
    probe_depths: list,
    max_new_tokens_probe: int,
    answer_preamble_chars: int,
    timeout_sec: int,
    poll_interval: float = 2.0,
) -> dict:
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=trial_runner.run_trial,
        args=(
            model_dir,
            model_name,
            device,
            tokens,
            probe_depths,
            max_new_tokens_probe,
            result_queue,
            answer_preamble_chars,
        ),
    )
    process.start()

    deadline = time.monotonic() + timeout_sec
    result = None
    while time.monotonic() < deadline:
        try:
            result = result_queue.get(timeout=poll_interval)
            break
        except Empty:
            if not process.is_alive():
                break  # child exited without publishing a result -> crash

    if process.is_alive():
        process.terminate()
    process.join(10)

    if result is not None:
        return result

    reason = "timeout" if time.monotonic() >= deadline else f"crashed:exitcode={process.exitcode}"
    return {
        "tokens_requested": tokens,
        "load_ok": False,
        "generate_ok": False,
        "accuracy": 0.0,
        "probes": [],
        "error": reason,
    }


def _classify_failure(result: dict, threshold: float) -> str:
    error = str(result.get("error") or "")
    if error == "timeout" or error.startswith("crashed"):
        return error.split(":")[0]
    if not result.get("load_ok"):
        return "oom" if "oom" in error else "load_error"
    if not result.get("generate_ok"):
        return "oom" if "oom" in error else "generate_error"
    if result.get("accuracy", 0.0) < threshold:
        return "accuracy_below_threshold"
    return "unknown"


def _passed(result: dict, threshold: float) -> bool:
    return bool(result.get("load_ok")) and bool(result.get("generate_ok")) and result.get("accuracy", 0.0) >= threshold


def _run_one(model_name, model_dir, device, tokens, settings, dry_run, fake_ceiling):
    if dry_run:
        return _run_trial_dry_run(model_name, tokens, settings["needle_probe_depths"], fake_ceiling)
    return _run_trial_subprocess(
        model_dir,
        model_name,
        device,
        tokens,
        settings["needle_probe_depths"],
        settings["max_new_tokens_probe"],
        settings["answer_preamble_chars"],
        settings["trial_timeout_sec"],
    )


def _refine_boundary(model_name, model_dir, device, settings, low, high, dry_run, fake_ceiling, max_extra=3) -> int:
    lo, hi = low, high
    smallest_step = settings["context_steps_tokens"][0]
    for _ in range(max_extra):
        if hi - lo <= max(1, smallest_step // 8):
            break
        mid = (lo + hi) // 2
        result = _run_one(model_name, model_dir, device, mid, settings, dry_run, fake_ceiling)
        _append_trial_row(
            settings["output_dir"],
            {"model": model_name, "device": device, "weight_format": settings["weight_format"], **result},
        )
        passed = _passed(result, settings["accuracy_threshold"])
        print(f"[{model_name}] refine @ {mid:>9,} tokens -> {'PASS' if passed else 'FAIL'}")
        lo, hi = (mid, hi) if passed else (lo, mid)
    return lo


def _sweep_model(model_name: str, settings: dict, dry_run: bool) -> dict:
    device = settings["device"]
    weight_format = settings["weight_format"]
    model_dir = _model_ir_dir(settings["models_base_path"], settings["provider"], model_name, weight_format)

    if not dry_run and not _ir_ready(model_dir):
        prep_command = _prep_command(model_name, model_dir, weight_format)
        print(f"[{model_name}] IR not found at {model_dir}\n  Run first: {prep_command}")
        return {
            "model": model_name,
            "status": "missing_ir",
            "max_stable_context": None,
            "meets_target": False,
            "device": device,
            "weight_format": weight_format,
            "prep_command": prep_command,
        }

    fake_ceiling = _fake_ceiling_tokens(model_name, settings["context_steps_tokens"]) if dry_run else None

    max_stable = 0
    fail_reason = None
    completed_all_steps = True
    last_tokens = settings["context_steps_tokens"][0]

    for tokens in settings["context_steps_tokens"]:
        last_tokens = tokens
        result = _run_one(model_name, model_dir, device, tokens, settings, dry_run, fake_ceiling)
        _append_trial_row(
            settings["output_dir"],
            {"model": model_name, "device": device, "weight_format": weight_format, **result},
        )

        passed = _passed(result, settings["accuracy_threshold"])
        print(
            f"[{model_name}] {tokens:>9,} tokens -> {'PASS' if passed else 'FAIL'} "
            f"(accuracy={result.get('accuracy', 0.0):.2f}, error={result.get('error')})"
        )
        if not passed:
            fail_reason = _classify_failure(result, settings["accuracy_threshold"])
            completed_all_steps = False
            break
        max_stable = tokens

    if completed_all_steps:
        fail_reason = None
    elif settings["refine"] and max_stable:
        max_stable = _refine_boundary(
            model_name, model_dir, device, settings, max_stable, last_tokens, dry_run, fake_ceiling
        )

    return {
        "model": model_name,
        "status": "ok",
        "max_stable_context": max_stable,
        "meets_target": max_stable >= settings["target_context_tokens"],
        "device": device,
        "weight_format": weight_format,
        "failure_reason": fail_reason,
    }


def _write_summary(output_dir: str, settings: dict, model_reports: list, platform_info: dict) -> None:
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_context_tokens": settings["target_context_tokens"],
        "accuracy_threshold": settings["accuracy_threshold"],
        "hardware": platform_info,
        "models": model_reports,
    }
    with open(os.path.join(output_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    lines = [
        "# Long-Context Validation Summary",
        "",
        f"Generated: {summary['generated_at']}",
        f"Target context: {settings['target_context_tokens']:,} tokens | "
        f"Accuracy threshold: {settings['accuracy_threshold']:.0%}",
        "",
        f"Hardware: {platform_info.get('Processor', '--')}, {platform_info.get('Memory', '--')} RAM, "
        f"{platform_info.get('iGPU', '--')}",
        "",
        "| Model | Device | Weight | Max stable context | Meets target | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for r in model_reports:
        if r["status"] == "missing_ir":
            lines.append(
                f"| {r['model']} | {r['device']} | {r['weight_format']} | - | - | "
                f"IR not found; run: `{r['prep_command']}` |"
            )
            continue
        max_ctx = f"{r['max_stable_context']:,}" if r["max_stable_context"] else "0"
        meets = "PASS" if r["meets_target"] else "FAIL"
        note = (
            f"capped by {r['failure_reason']}"
            if r.get("failure_reason")
            else "reached top configured step without failing"
        )
        lines.append(f"| {r['model']} | {r['device']} | {r['weight_format']} | {max_ctx} | {meets} | {note} |")

    with open(os.path.join(output_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _preflight_environment_check() -> None:
    """Fail fast with an actionable message if this interpreter can't import what
    trial_runner.py needs, instead of letting every trial in the sweep repeat the
    same import failure. Missing openvino_genai/transformers here almost always
    means "wrong Python interpreter", not a bug in this tool: those packages live
    in the project's backend venv, not the system/base Python.
    """
    missing = [name for name in _REQUIRED_MODULES if importlib.util.find_spec(name) is None]
    if not missing:
        return

    lines = [
        f"Missing required package(s) in this interpreter ({sys.executable}): {', '.join(missing)}.",
        "This is almost always the wrong Python environment, not a code bug -- the OpenVINO "
        "stack (openvino-genai, transformers, optimum-intel, torch) lives in the project's "
        "backend venv, not the interpreter picked up from PATH.",
        "Simplest fix -- use the launcher script, which creates the venv if needed (via "
        "setup_env.ps1), activates it, and re-runs this tool with the same arguments:",
        "  " + " ".join([_LAUNCHER_SCRIPT, *sys.argv[1:]]),
    ]
    if os.path.exists(_BACKEND_VENV_PYTHON):
        lines.append(f"Or run directly with the venv's interpreter, which already exists at {_BACKEND_VENV_PYTHON}:")
        lines.append(f'  "{_BACKEND_VENV_PYTHON}" -m components.llm.context_validation.validate_long_context')
    else:
        lines.append(
            f"Or prepare the venv yourself first (no venv found yet at {_BACKEND_VENV_PYTHON}):"
        )
        lines.append(f"  {_SETUP_SCRIPT}")
        lines.append(
            "(If PowerShell blocks either script: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass)"
        )
    lines.append("(Use --dry-run to exercise the sweep/report pipeline without any of these packages.)")
    raise SystemExit("\n".join(lines))


def main() -> None:
    args = _parse_args()
    if not args.dry_run:
        _preflight_environment_check()
    settings = _load_settings(args)
    os.makedirs(settings["output_dir"], exist_ok=True)
    platform_info = _safe_platform_info()

    print(f"Long-context validation sweep starting (dry_run={args.dry_run})")
    print(f"Candidates: {settings['candidate_models']}")
    print(f"Steps: {settings['context_steps_tokens']}")
    print(f"Target: {settings['target_context_tokens']:,} tokens | Output: {settings['output_dir']}")

    model_reports = []
    for model_name in settings["candidate_models"]:
        print(f"\n=== {model_name} ===")
        model_reports.append(_sweep_model(model_name, settings, args.dry_run))

    _write_summary(settings["output_dir"], settings, model_reports, platform_info)
    print(f"\nReports written to {settings['output_dir']} (trials.csv, summary.json, summary.md)")


if __name__ == "__main__":
    main()
