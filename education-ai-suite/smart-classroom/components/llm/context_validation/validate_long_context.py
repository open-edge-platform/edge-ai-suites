# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Sweep candidate summarizer models across context lengths to find the maximum
context each one can reliably prefill and decode on this hardware, versus the
customer's target (default 160K tokens).

What it measures is deliberately narrow (mirroring refer/long_context): whether
*this machine* can load the model and prefill + decode a prompt of a given token
size without running out of GPU/host memory (or hanging). It does NOT judge
answer quality -- content is irrelevant to a capacity check, only whether the
box survives the token volume. Each trial reports where its memory went: the
weight footprint (measured just after load) versus the KV-cache footprint (the
extra memory prefill+decode adds on top). See
docs/dev-guide/validate_long_context.md.

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
import contextlib
import gc
import importlib.util
import json
import multiprocessing
import os
import re
import sys
import threading
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

# Measured kv_gpu_gb / expected_kv_gpu_gb at or above this is called out in the summary notes as a
# scope mismatch between the two numbers (persistent-cache-only estimate vs. all post-load growth)
# rather than a plain capacity limit -- see _theoretical_kv_bytes_per_token()'s docstring and the
# note built in _write_summary() for what this can and cannot be blamed on.
_KV_OVERHEAD_RATIO_NOTE_THRESHOLD = 3.0

TRIAL_CSV_FIELDS = [
    "model",
    "tokens_requested",
    "device",
    "weight_format",
    "load_ok",
    "load_time_s",
    "generate_ok",
    "prompt_tokens",
    "generated_tokens",
    "generate_time_s",
    "tokens_per_second",
    "max_generate_time_sec",
    "latency_limit_exceeded",
    "gpu_memory_pressure_pct",
    "peak_gpu_pct",
    "gpu_memory_at_limit",
    "weight_disk_gb",
    "weight_ram_gb",
    "kv_ram_gb",
    "peak_ram_gb",
    "peak_ram_pct",
    "weight_gpu_gb",
    "kv_gpu_gb",
    "expected_kv_gpu_gb",
    "kv_overhead_ratio",
    "peak_gpu_gb",
    "status",
    "error",
]


# ---------------------------------------------------------------------------
# Memory sampling (parent side)
#
# System RAM / GPU counters are process-wide, so sampling from the orchestrator
# captures the trial subprocess's footprint -- and, unlike sampling inside the
# child, these readings survive even when the child is killed on a timeout
# (exactly the case where memory matters most: the box was thrashing, not idle).
# ---------------------------------------------------------------------------
def _read_mem() -> dict:
    ram_used = ram_total = ram_pct = 0.0
    try:
        import psutil

        vm = psutil.virtual_memory()
        ram_used, ram_total, ram_pct = vm.used / (1024 ** 3), vm.total / (1024 ** 3), vm.percent
    except Exception:
        pass
    gpu_gb = 0.0
    try:
        from monitoring.scripts.windows.collect_gpu import get_gpu_memory_total

        used_mb, _dedicated, _shared = get_gpu_memory_total()
        if used_mb is not None:
            gpu_gb = used_mb / 1024
    except Exception:
        pass
    return {"ram_gb": ram_used, "ram_total_gb": ram_total, "ram_pct": ram_pct, "gpu_gb": gpu_gb}


class _MemorySampler(threading.Thread):
    """Tracks peak (and latest) system RAM / GPU usage while a trial runs."""

    def __init__(self, interval: float = 0.5):
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        self.interval = interval
        self.peak_ram = 0.0
        self.peak_ram_pct = 0.0
        self.peak_gpu = 0.0
        self.latest = _read_mem()

    def run(self):
        while not self._stop_event.is_set():
            m = _read_mem()
            self.latest = m
            self.peak_ram = max(self.peak_ram, m["ram_gb"])
            self.peak_ram_pct = max(self.peak_ram_pct, m["ram_pct"])
            self.peak_gpu = max(self.peak_gpu, m["gpu_gb"])
            self._stop_event.wait(self.interval)

    def stop(self):
        self._stop_event.set()


def _delta(higher: float, lower: float) -> float:
    return round(max(0.0, higher - lower), 2)


def _weight_disk_gb(model_dir: str) -> float:
    """Approximate weight footprint from the on-disk IR weights (.bin). For an
    int8/int4 export this closely tracks the resident weight memory, and it's a
    deterministic reference that's available even if a trial OOMs before we can
    measure the loaded footprint."""
    total = 0
    for root, _dirs, files in os.walk(model_dir):
        for f in files:
            if f.endswith(".bin"):
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    return round(total / (1024 ** 3), 2)


def _load_model_config(model_dir: str) -> dict | None:
    """Best-effort read of the exported IR's config.json (present for every
    optimum-cli export). Returns None if missing/unreadable so callers can
    degrade to "no theoretical estimate" instead of failing the trial."""
    path = os.path.join(model_dir, "config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _theoretical_kv_bytes_per_token(config: dict, kv_cache_dtype_bytes: int = 2) -> float | None:
    """Expected KV-cache growth per token from the model's own declared
    architecture, treating hybrid linear-attention layers correctly.

    VLM exports nest the causal-LM config under `text_config` (confirmed on
    the Qwen3.5-9B / Qwen3.6-35B-A3B IR exports this tool targets); plain LLM
    configs have these keys top-level, so this reads from
    ``config.get("text_config", config)`` to handle both.

    Only layers whose `layer_types` entry is "full_attention" hold a KV cache
    that grows with sequence length; entries like "linear_attention" are
    Mamba/GatedDeltaNet-style recurrent-state layers with an O(1) state that
    does NOT grow with context length. This split is not just a config.json
    label -- it is confirmed directly against the exported IR
    (openvino_language_model.xml / openvino_model.xml): only the
    full_attention layers' `cache_params.past.{key,value}.N` state variables
    carry a dynamic sequence-length axis; the linear_attention layers'
    `cache_params.past.{conv,ssm}.N` variables have a fixed shape regardless
    of context length.

    This function returns a *persistent-cache-only* estimate, which is
    deliberately narrower than what trial_runner's kv_gpu_gb/kv_ram_gb
    measure (see the `kv_overhead_ratio` note in `_write_summary()`): those
    also include prefill/decode working memory (Q/K/V projections, MLP
    activations, ...) for *every* layer, including the linear-attention ones
    -- a hybrid model still runs all its layers on every prompt token during
    prefill even though only the full_attention layers keep a cache
    afterwards. A large kv_overhead_ratio for a hybrid model is therefore
    expected from this scope mismatch alone; it is not, by itself, evidence
    of a specific OpenVINO defect (an earlier version of this comment cited
    a known OpenVINO Model Server issue where continuous-batching prefix
    caching over-allocates memory for linear-attention models -- that issue
    is real, but its precondition isn't met here: trial_runner's
    `_load_pipeline()` never sets `scheduler_config`/`ATTENTION_BACKEND=PA`,
    so OpenVINO GenAI's own backend-selection logic keeps this tool on the
    plain stateful single-sequence backend, not continuous batching, so that
    specific issue cannot be what's being observed in this tool's trials).
    If `layer_types` is absent, every layer is assumed to be a standard
    growing-KV-cache attention layer (ordinary dense transformer).

    Returns None if the config doesn't expose enough info to compute this
    (num_hidden_layers / num_key_value_heads / head_dim), so callers can
    degrade gracefully for architectures/exports this doesn't understand yet.

    kv_cache_dtype_bytes defaults to 2 (fp16), OpenVINO GenAI's default KV
    cache precision when not otherwise configured -- this is a stated
    assumption, not something measured, since the tool has no way to read
    back the runtime's actual KV precision.
    """
    text_cfg = config.get("text_config", config)
    num_layers = text_cfg.get("num_hidden_layers")
    num_kv_heads = text_cfg.get("num_key_value_heads")
    head_dim = text_cfg.get("head_dim")
    if not num_layers or not num_kv_heads or not head_dim:
        return None
    layer_types = text_cfg.get("layer_types")
    growing_layers = (
        sum(1 for t in layer_types if t == "full_attention") if layer_types else num_layers
    )
    if not growing_layers:
        return None
    return 2 * growing_layers * num_kv_heads * head_dim * kv_cache_dtype_bytes


@contextlib.contextmanager
def _suppress_native_stderr():
    """Silence C-level stderr for the duration of the block.

    The WMI/COM hardware probe in utils/platform_info.py emits benign
    "Win32 exception occurred releasing IUnknown" teardown noise from the native
    COM layer (not via Python's logging/warnings), so only an fd-level redirect
    can hide it. Used solely around the best-effort platform-info call, which
    already falls back to defaults on any failure.
    """
    try:
        stderr_fd = sys.stderr.fileno()
    except (AttributeError, OSError, ValueError):
        yield
        return
    saved = os.dup(stderr_fd)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        sys.stderr.flush()
        os.dup2(devnull, stderr_fd)
        yield
    finally:
        sys.stderr.flush()
        os.dup2(saved, stderr_fd)
        os.close(saved)
        os.close(devnull)


def _parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Find the max context length each candidate summarizer model can "
            "prefill and decode on this hardware, against the configured target (default 160K)."
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
    parser.add_argument("--probe-tokens", type=int, help="Override probe_tokens (decode length per trial)")
    parser.add_argument(
        "--max-generate-time-sec",
        type=float,
        help="Override the maximum acceptable prefill + probe generation time",
    )
    parser.add_argument(
        "--gpu-memory-pressure-pct",
        type=float,
        help="Override the GPU-used/system-RAM percentage treated as the practical iGPU limit",
    )
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
        "target_context_tokens": (
            args.target_tokens if args.target_tokens is not None else lcv.target_context_tokens
        ),
        "context_steps_tokens": sorted(args.steps or lcv.context_steps_tokens),
        "probe_tokens": (
            args.probe_tokens if args.probe_tokens is not None else getattr(lcv, "probe_tokens", 64)
        ),
        "max_generate_time_sec": (
            args.max_generate_time_sec
            if args.max_generate_time_sec is not None
            else getattr(lcv, "max_generate_time_sec", 600)
        ),
        "gpu_memory_pressure_pct": (
            args.gpu_memory_pressure_pct
            if args.gpu_memory_pressure_pct is not None
            else getattr(lcv, "gpu_memory_pressure_pct", 90)
        ),
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

        with _suppress_native_stderr():
            info = get_platform_and_model_info()
            gc.collect()  # force COM release inside the suppressed window
        return info
    except Exception:
        return {}


def _passed(result: dict) -> bool:
    return (
        bool(result.get("load_ok"))
        and bool(result.get("generate_ok"))
        and result.get("generated_tokens", 0) > 0
        and not _resource_limit_reached(result)
    )


def _resource_limit_reached(result: dict) -> bool:
    """A soft latency breach is a capacity failure only with GPU memory pressure."""
    generate_time = result.get("generate_time_s")
    max_generate_time = result.get("max_generate_time_sec")
    return bool(
        max_generate_time is not None
        and generate_time is not None
        and generate_time > max_generate_time
        and result.get("gpu_memory_at_limit") is True
    )


def _error_classification(error: str) -> str:
    """Middle field of a run_trial "stage:classification:detail" error string (e.g.
    "oom" or "exception"), or "" if the error isn't in that format -- an output-
    validation reason like "no_output" has no colons at all, and the raw exception
    text in the detail field can itself contain arbitrary colons, so this must read
    only the classification field rather than search the whole string."""
    parts = error.split(":", 2)
    return parts[1] if len(parts) >= 2 else ""


def _classify_failure(result: dict) -> str:
    error = str(result.get("error") or "")
    if error == "timeout" or error.startswith("crashed"):
        return error.split(":")[0]
    is_oom = _error_classification(error) == "oom"
    if not result.get("load_ok"):
        return "oom" if is_oom else "load_error"
    if not result.get("generate_ok"):
        if is_oom:
            return "oom"
        if error == "no_output":
            return "no_output"
        return "generate_error"
    if not result.get("generated_tokens", 0):
        return "no_output"
    if _resource_limit_reached(result):
        return "too_slow"
    return "unknown"


def _status_label(result: dict) -> str:
    return "PASS" if _passed(result) else _classify_failure(result)


def _append_trial_row(output_dir: str, row: dict) -> None:
    path = os.path.join(output_dir, "trials.csv")
    flat = {field: row.get(field) for field in TRIAL_CSV_FIELDS}
    flat["model"] = row["model"]
    flat["device"] = row["device"]
    flat["weight_format"] = row["weight_format"]
    flat["status"] = _status_label(row)
    StorageManager.save_csv(path, flat, headers=TRIAL_CSV_FIELDS, append=True)


def _fmt_gb(value) -> str:
    return f"{value:.1f} GB" if isinstance(value, (int, float)) else "--"


def _format_trial_line(model_name: str, tokens: int, result: dict) -> str:
    passed = _passed(result)
    status = "PASS" if passed else f"FAIL ({_classify_failure(result)})"
    parts = [f"[{model_name}] {tokens:>9,} tok -> {status}"]

    timing = []
    if result.get("load_time_s") is not None:
        timing.append(f"load {result['load_time_s']:.1f}s")
    if result.get("generate_time_s") is not None:
        timing.append(
            f"gen {result['generate_time_s']:.1f}s ({result.get('generated_tokens', 0)} tok, "
            f"{result.get('tokens_per_second', 0):.2f} tok/s)"
        )
    if timing:
        parts.append(", ".join(timing))

    if result.get("peak_ram_gb") is not None:
        seg = f"peak RAM {_fmt_gb(result.get('peak_ram_gb'))}"
        if result.get("weight_ram_gb") is not None and result.get("kv_ram_gb") is not None:
            seg += f" (weights +{result['weight_ram_gb']:.1f}, kv +{result['kv_ram_gb']:.1f})"
        parts.append(seg)
    if result.get("peak_gpu_gb") is not None:
        seg = f"peak GPU {_fmt_gb(result.get('peak_gpu_gb'))}"
        if result.get("peak_gpu_pct") is not None:
            seg += f" ({result['peak_gpu_pct']:.1f}% of system RAM)"
        if result.get("weight_gpu_gb") is not None and result.get("kv_gpu_gb") is not None:
            seg += f" (weights +{result['weight_gpu_gb']:.1f}, kv +{result['kv_gpu_gb']:.1f}"
            if result.get("kv_overhead_ratio") is not None:
                seg += f", expected {result['expected_kv_gpu_gb']:.2f}, {result['kv_overhead_ratio']:.1f}x"
            seg += ")"
        parts.append(seg)

    if result.get("latency_limit_exceeded") and not result.get("gpu_memory_at_limit"):
        parts.append("latency budget exceeded without GPU memory saturation")

    if not passed and result.get("error"):
        parts.append(f"error={result.get('error')}")
    return "  |  ".join(parts)


def _fake_ceiling_tokens(model_name: str, steps: list) -> int:
    """Deterministic per-model fake ceiling so --dry-run exercises a mix of
    pass/fail across the configured steps without touching any hardware."""
    digest = sum(ord(c) for c in model_name)
    return steps[digest % len(steps)]


def _run_trial_dry_run(model_name: str, tokens: int, probe_tokens: int, fake_ceiling: int) -> dict:
    ok = tokens <= fake_ceiling
    weight_ram = 4.0  # pretend a small fixed weight footprint
    weight_gpu = 3.5
    kv_ram = round(tokens / 8000.0, 2)  # KV grows with context
    kv_gpu = round(tokens / 10000.0, 2)
    peak_gpu = round(1.0 + weight_gpu + kv_gpu, 2)
    return {
        "tokens_requested": tokens,
        "load_ok": True,
        "load_time_s": 0.01,
        "generate_ok": ok,
        "prompt_tokens": tokens,
        "generated_tokens": probe_tokens if ok else 0,
        "generate_time_s": 0.01,
        "weight_ram_gb": weight_ram,
        "weight_gpu_gb": weight_gpu,
        "kv_ram_gb": kv_ram,
        "kv_gpu_gb": kv_gpu,
        "peak_ram_gb": round(2.0 + weight_ram + kv_ram, 2),
        "peak_ram_pct": 50.0,
        "peak_gpu_gb": peak_gpu,
        "ram_total_gb": 64.0,
        "error": None if ok else "generate:oom:allocation failed (dry-run)",
    }


def _run_trial_subprocess(
    model_name: str,
    model_dir: str,
    device: str,
    tokens: int,
    probe_tokens: int,
    timeout_sec: int,
    sample_interval: float = 0.5,
    poll_interval: float = 2.0,
) -> dict:
    baseline = _read_mem()
    sampler = _MemorySampler(interval=sample_interval)
    sampler.start()

    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=trial_runner.run_trial,
        args=(model_dir, model_name, device, tokens, probe_tokens, result_queue),
    )
    process.start()

    loaded_mem = None
    result = None
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            msg = result_queue.get(timeout=poll_interval)
        except Empty:
            if not process.is_alive():
                break  # child exited without a "done" message -> crash
            continue
        if msg.get("event") == "loaded":
            loaded_mem = _read_mem()  # snapshot the weight footprint before prefill grows it
        elif msg.get("event") == "done":
            result = msg
            break

    timed_out = result is None and time.monotonic() >= deadline
    if process.is_alive():
        process.terminate()
    process.join(10)
    sampler.stop()
    sampler.join(2 * sample_interval + 1)

    mem = {
        "peak_ram_gb": round(sampler.peak_ram, 2),
        "peak_ram_pct": round(sampler.peak_ram_pct, 1),
        "peak_gpu_gb": round(sampler.peak_gpu, 2),
        "weight_ram_gb": _delta(loaded_mem["ram_gb"], baseline["ram_gb"]) if loaded_mem else None,
        "weight_gpu_gb": _delta(loaded_mem["gpu_gb"], baseline["gpu_gb"]) if loaded_mem else None,
        "kv_ram_gb": _delta(sampler.peak_ram, loaded_mem["ram_gb"]) if loaded_mem else None,
        "kv_gpu_gb": _delta(sampler.peak_gpu, loaded_mem["gpu_gb"]) if loaded_mem else None,
        "ram_total_gb": round(baseline["ram_total_gb"], 2),
    }

    if result is not None:
        result.pop("event", None)
        result.update(mem)
        return result

    reason = "timeout" if timed_out else f"crashed:exitcode={process.exitcode}"
    return {
        "tokens_requested": tokens,
        "load_ok": loaded_mem is not None,  # crashed/hung during generate, not load
        "load_time_s": None,
        "generate_ok": False,
        "prompt_tokens": 0,
        "generated_tokens": 0,
        "generate_time_s": None,
        "error": reason,
        **mem,
    }


def _run_one(model_name, model_dir, device, tokens, settings, dry_run, fake_ceiling, kv_bytes_per_token=None):
    if dry_run:
        result = _run_trial_dry_run(model_name, tokens, settings["probe_tokens"], fake_ceiling)
    else:
        result = _run_trial_subprocess(
            model_name,
            model_dir,
            device,
            tokens,
            settings["probe_tokens"],
            settings["trial_timeout_sec"],
        )
    generate_time = result.get("generate_time_s")
    generated_tokens = result.get("generated_tokens", 0)
    result["tokens_per_second"] = (
        round(generated_tokens / generate_time, 3) if generate_time and generated_tokens else 0.0
    )
    result["max_generate_time_sec"] = settings["max_generate_time_sec"]
    result["latency_limit_exceeded"] = bool(
        generate_time is not None and generate_time > settings["max_generate_time_sec"]
    )
    ram_total_gb = result.pop("ram_total_gb", 0.0)
    peak_gpu_gb = result.get("peak_gpu_gb", 0.0)
    result["gpu_memory_pressure_pct"] = settings["gpu_memory_pressure_pct"]
    result["peak_gpu_pct"] = (
        round(peak_gpu_gb / ram_total_gb * 100, 1) if peak_gpu_gb and ram_total_gb else None
    )
    result["gpu_memory_at_limit"] = bool(
        result["peak_gpu_pct"] is not None
        and result["peak_gpu_pct"] >= settings["gpu_memory_pressure_pct"]
    )
    if kv_bytes_per_token and result.get("prompt_tokens"):
        expected_kv_gb = kv_bytes_per_token * result["prompt_tokens"] / (1024 ** 3)
        result["expected_kv_gpu_gb"] = round(expected_kv_gb, 2)
        kv_gpu = result.get("kv_gpu_gb")
        result["kv_overhead_ratio"] = round(kv_gpu / expected_kv_gb, 2) if kv_gpu else None
    else:
        result["expected_kv_gpu_gb"] = None
        result["kv_overhead_ratio"] = None
    return result


def _refine_boundary(
    model_name, model_dir, device, settings, low, high, dry_run, fake_ceiling, weight_disk,
    kv_bytes_per_token=None, max_extra=3,
):
    lo, hi = low, high
    smallest_step = settings["context_steps_tokens"][0]
    best_result = None
    for _ in range(max_extra):
        if hi - lo <= max(1, smallest_step // 8):
            break
        mid = (lo + hi) // 2
        result = _run_one(model_name, model_dir, device, mid, settings, dry_run, fake_ceiling, kv_bytes_per_token)
        _append_trial_row(
            settings["output_dir"],
            {
                "model": model_name,
                "device": device,
                "weight_format": settings["weight_format"],
                "weight_disk_gb": weight_disk,
                **result,
            },
        )
        passed = _passed(result)
        print("  " + _format_trial_line(model_name, mid, result))
        if passed:
            best_result = result
        lo, hi = (mid, hi) if passed else (lo, mid)
    return lo, best_result


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

    weight_disk = 0.0 if dry_run else _weight_disk_gb(model_dir)
    print(f"\n=== {model_name} ===  weights on disk: {_fmt_gb(weight_disk)} ({weight_format})")

    model_config = None if dry_run else _load_model_config(model_dir)
    kv_bytes_per_token = _theoretical_kv_bytes_per_token(model_config) if model_config else None

    fake_ceiling = _fake_ceiling_tokens(model_name, settings["context_steps_tokens"]) if dry_run else None

    max_stable = 0
    max_stable_result = None
    fail_reason = None
    completed_all_steps = True
    last_tokens = settings["context_steps_tokens"][0]

    for tokens in settings["context_steps_tokens"]:
        last_tokens = tokens
        result = _run_one(model_name, model_dir, device, tokens, settings, dry_run, fake_ceiling, kv_bytes_per_token)
        _append_trial_row(
            settings["output_dir"],
            {
                "model": model_name,
                "device": device,
                "weight_format": weight_format,
                "weight_disk_gb": weight_disk,
                **result,
            },
        )

        passed = _passed(result)
        print(_format_trial_line(model_name, tokens, result))
        if not passed:
            fail_reason = _classify_failure(result)
            completed_all_steps = False
            break
        max_stable = tokens
        max_stable_result = result

    if completed_all_steps:
        fail_reason = None
    elif settings["refine"] and max_stable:
        max_stable, refined_result = _refine_boundary(
            model_name, model_dir, device, settings, max_stable, last_tokens, dry_run, fake_ceiling, weight_disk,
            kv_bytes_per_token=kv_bytes_per_token,
        )
        if refined_result is not None:
            max_stable_result = refined_result

    peak = max_stable_result or {}
    return {
        "model": model_name,
        "status": "ok",
        "max_stable_context": max_stable,
        "meets_target": max_stable >= settings["target_context_tokens"],
        "device": device,
        "weight_format": weight_format,
        "weight_disk_gb": weight_disk,
        "weight_ram_gb": peak.get("weight_ram_gb"),
        "weight_gpu_gb": peak.get("weight_gpu_gb"),
        "kv_ram_gb": peak.get("kv_ram_gb"),
        "kv_gpu_gb": peak.get("kv_gpu_gb"),
        "expected_kv_gpu_gb": peak.get("expected_kv_gpu_gb"),
        "kv_overhead_ratio": peak.get("kv_overhead_ratio"),
        "peak_ram_gb": peak.get("peak_ram_gb"),
        "peak_gpu_gb": peak.get("peak_gpu_gb"),
        "failure_reason": fail_reason,
    }


def _write_summary(output_dir: str, settings: dict, model_reports: list, platform_info: dict) -> None:
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_context_tokens": settings["target_context_tokens"],
        "probe_tokens": settings["probe_tokens"],
        "max_generate_time_sec": settings["max_generate_time_sec"],
        "hardware": platform_info,
        "models": model_reports,
    }
    with open(os.path.join(output_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    lines = [
        "# Long-Context Capacity Validation Summary",
        "",
        f"Generated: {summary['generated_at']}",
        f"Target context: {settings['target_context_tokens']:,} tokens | "
        f"Probe decode: {settings['probe_tokens']} tokens/trial | "
        f"Max prefill + generation: {settings['max_generate_time_sec']:g}s | "
        f"GPU memory pressure: {settings['gpu_memory_pressure_pct']:g}% of system RAM",
        "",
        f"Hardware: {platform_info.get('Processor', '--')}, {platform_info.get('Memory', '--')} RAM, "
        f"{platform_info.get('iGPU', '--')}",
        "",
        "Memory columns are measured at the max stable context: weights = footprint just after "
        "load; KV = additional memory prefill+decode added on top; peak = total high-water mark.",
        "",
        "| Model | Device | Weight | Max stable context | Meets target | Weights (disk) | "
        "Peak RAM | KV RAM | Peak GPU | KV GPU | Expected KV | KV Ratio | Notes |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in model_reports:
        if r["status"] == "missing_ir":
            lines.append(
                f"| {r['model']} | {r['device']} | {r['weight_format']} | - | - | - | - | - | - | - | - | - | "
                f"IR not found; run: `{r['prep_command']}` |"
            )
            continue
        max_ctx = f"{r['max_stable_context']:,}" if r["max_stable_context"] else "0"
        meets = "PASS" if r["meets_target"] else "FAIL"
        ratio = r.get("kv_overhead_ratio")
        if ratio is not None and ratio >= _KV_OVERHEAD_RATIO_NOTE_THRESHOLD:
            note = (
                f"kv {ratio:g}x the persistent-cache-only estimate -- expected_kv_gpu_gb counts "
                "only growing-KV-cache layers, kv_gpu_gb also includes prefill/decode working "
                "memory across all layers, so a large ratio here is not a capacity problem with "
                "this box by itself, and not proof of a specific OpenVINO defect either"
            )
        elif r.get("failure_reason"):
            note = f"capped by {r['failure_reason']}"
        else:
            note = "reached top configured step without failing"
        lines.append(
            f"| {r['model']} | {r['device']} | {r['weight_format']} | {max_ctx} | {meets} | "
            f"{_fmt_gb(r.get('weight_disk_gb'))} | {_fmt_gb(r.get('peak_ram_gb'))} | "
            f"{_fmt_gb(r.get('kv_ram_gb'))} | {_fmt_gb(r.get('peak_gpu_gb'))} | "
            f"{_fmt_gb(r.get('kv_gpu_gb'))} | {_fmt_gb(r.get('expected_kv_gpu_gb'))} | "
            f"{f'{ratio:g}x' if ratio is not None else '--'} | {note} |"
        )

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

    print(f"Long-context capacity validation sweep starting (dry_run={args.dry_run})")
    print(f"Candidates: {settings['candidate_models']}")
    print(f"Steps: {settings['context_steps_tokens']}")
    print(
        f"Target: {settings['target_context_tokens']:,} tokens | "
        f"Probe decode: {settings['probe_tokens']} tok | "
        f"Max generation: {settings['max_generate_time_sec']:g}s | Output: {settings['output_dir']}"
    )

    model_reports = []
    for model_name in settings["candidate_models"]:
        model_reports.append(_sweep_model(model_name, settings, args.dry_run))

    _write_summary(settings["output_dir"], settings, model_reports, platform_info)
    print(f"\nReports written to {settings['output_dir']} (trials.csv, summary.json, summary.md)")


if __name__ == "__main__":
    main()
