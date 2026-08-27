# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Split long transcripts into prompt-sized chunks.
    Keeps calls within quality and memory limits."""

import json
import logging
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

from utils.model_paths import text_gen_model_dir

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TOKENS = 6000
DEFAULT_BYTES_PER_TOKEN = 96 * 1024      # fallback when the model config is unreadable
DEFAULT_OVERLAP_LINES = 2
# Leave capacity for fragmentation, estimation error, and other processes.
GPU_MEMORY_SAFETY_MARGIN = 0.6
_KV_RUNTIME_OVERHEAD = 1.25              # paged-cache block padding + prefill activations
_DEFAULT_KV_DTYPE_BYTES = 1              # CPU and GPU both cache in int8 by default

# Limit content before long context degrades instruction following.
DEFAULT_MAX_CONTENT_TOKENS = 24000

_CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿぀-ヿ가-힯]")

# Avoid repeating the same reserve warning during one planning pass.
_CAP_WARNED = set()


@dataclass(frozen=True)
class Chunk:
    """One segment of a transcript, sized to fit a single model call."""

    text: str
    index: int          # 0-based
    total: int
    tokens: int
    start: Optional[float] = None   # seconds; timestamped input only
    end: Optional[float] = None


def estimate_tokens(text: str) -> int:
    """Count tokens without a tokenizer: CJK ~1/char, everything else ~1/4 chars."""
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    return cjk + math.ceil((len(text) - cjk) / 4)


def count_tokens(text: str, tokenizer=None) -> int:
    """Count tokens with ``tokenizer``, or a 15%-padded estimate without one."""
    if not text:
        return 0
    if tokenizer is not None:
        try:
            return len(tokenizer.encode(text))
        except Exception:  # noqa: BLE001
            logger.debug("tokenizer.encode failed; falling back to estimate", exc_info=True)
    return math.ceil(estimate_tokens(text) * 1.15)


@lru_cache(maxsize=None)
def _kv_dtype_bytes(device: str) -> int:
    """Return the width of one cached value from the plugin's KV cache hint."""
    try:
        import openvino as ov

        width = int(ov.Core().get_property(device, "KV_CACHE_PRECISION").size)
    except Exception:  # noqa: BLE001
        logger.debug("KV_CACHE_PRECISION unreadable on %s", device, exc_info=True)
        return _DEFAULT_KV_DTYPE_BYTES
    # A dynamic type reports size 0: the plugin picks the precision per model.
    return width or _DEFAULT_KV_DTYPE_BYTES


def _kv_geometry(model_dir: Path):
    """Return ``(layers, kv_heads, head_dim)`` from a model's ``config.json``."""
    cfg = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    cfg = cfg.get("text_config", cfg)  # VLMs nest the language model's config
    layers = int(cfg["num_hidden_layers"])
    heads = int(cfg["num_attention_heads"])
    kv_heads = int(cfg.get("num_key_value_heads") or heads)  # no GQA: one per head
    head_dim = int(cfg.get("head_dim") or int(cfg["hidden_size"]) // heads)
    return layers, kv_heads, head_dim


@lru_cache(maxsize=None)
def kv_bytes_per_token(model_dir=None, device: str = "GPU") -> int:
    """Return KV-cache bytes per token. Model geometry keeps the estimate device-aware."""
    model_dir = Path(model_dir) if model_dir else text_gen_model_dir()
    try:
        layers, kv_heads, head_dim = _kv_geometry(model_dir)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not size the KV cache from %s (%s); assuming %d bytes/token.",
                       model_dir, exc, DEFAULT_BYTES_PER_TOKEN)
        return DEFAULT_BYTES_PER_TOKEN

    width = _kv_dtype_bytes(device)
    per_token = int(2 * layers * kv_heads * head_dim * width * _KV_RUNTIME_OVERHEAD)
    logger.info("KV cache on %s: %d layers x %d kv-heads x %d dims x %dB = %d bytes/token.",
                device, layers, kv_heads, head_dim, width, per_token)
    return per_token


def _weights_bytes(model_dir) -> int:
    """Return the on-disk size of the IR weights the pipeline holds resident."""
    try:
        return sum(f.stat().st_size for f in Path(model_dir).glob("*.bin"))
    except Exception:  # noqa: BLE001
        logger.debug("Could not size the weights in %s", model_dir, exc_info=True)
        return 0


def _capacity_bytes(device: str, model_dir=None) -> int:
    """Return addressable memory less the resident weights.

    Capacity, not free memory: a split that changed with whatever else was
    running would make one recording's summary irreproducible.
    """
    if device.startswith("GPU"):
        import openvino as ov

        # GPU_MEMORY_STATISTICS cannot stand in for the resident weights, as
        # it only counts allocations made through the very Core instance that
        # asks, and the warm pipeline owns a different one.
        total = int(ov.Core().get_property(device, "GPU_DEVICE_TOTAL_MEM_SIZE"))
    else:
        import psutil

        total = int(psutil.virtual_memory().total)

    return max(0, total - _weights_bytes(model_dir))


def _free_bytes_now(device: str) -> Optional[int]:
    """Return current free memory for diagnostics. It never changes the stable budget."""
    if device.startswith("GPU"):
        try:
            import openvino as ov

            if "DISCRETE" in str(ov.Core().get_property(device, "DEVICE_TYPE")):
                return None
        except Exception:  # noqa: BLE001
            logger.debug("Could not read DEVICE_TYPE on %s", device, exc_info=True)
            return None

    # CPU and integrated GPUs draw on system RAM, which psutil reports honestly.
    try:
        import psutil

        return int(psutil.virtual_memory().available)
    except Exception:  # noqa: BLE001
        logger.debug("Could not read free memory", exc_info=True)
        return None


def warn_if_short_of_memory(tokens: int, device: str = "GPU", model_dir=None,
                            what: str = "call") -> bool:
    """Warn when a call would not fit the memory free right now.

    Reports and changes nothing: the budget is sized from capacity so the plan
    stays reproducible, which is exactly why it cannot see a busy machine.
    """
    device = (device or "GPU").upper()  # callers pass the config value verbatim
    free = _free_bytes_now(device)
    if free is None or tokens <= 0:
        return False

    need = tokens * kv_bytes_per_token(model_dir, device)
    if need <= free:
        return False

    gb = 1024 ** 3
    logger.warning(
        "This %s needs %d tokens of KV cache (%.2f GB) on %s, but only %.2f GB is "
        "free right now. The budget is sized from the memory the device can "
        "address rather than from what is free, so that the same lesson always "
        "splits the same way -- it cannot see that the machine is busy. Close "
        "what else is running, or lower max_content_tokens.",
        what, tokens, need / gb, device, free / gb,
    )
    return True


def _memory_budget(device: str, bytes_per_token: int, model_dir=None, 
                   gpu_memory_safety_margin=None) -> int:
    """Return the prompt tokens that fit in the memory on ``device``."""
    if gpu_memory_safety_margin is None:
        gpu_memory_safety_margin = GPU_MEMORY_SAFETY_MARGIN
    capacity = _capacity_bytes(device, model_dir)
    budget = int(capacity * gpu_memory_safety_margin // bytes_per_token)
    if budget <= 0:
        raise ValueError(f"{capacity} usable bytes on {device} holds no prompt")
    return budget


def resolve_budget(device: str = "GPU", override="auto", model_dir=None,
                   max_content_tokens: int = DEFAULT_MAX_CONTENT_TOKENS,
                   gpu_memory_safety_margin=None) -> int:
    """Return the smaller quality or memory limit. This avoids weak or oversized calls."""
    if override not in (None, "auto", "Auto", "AUTO"):
        try:
            budget = max(1, int(override))
            logger.info("Prompt budget: %d tokens (set explicitly).", budget)
            return budget
        except (TypeError, ValueError):
            logger.warning("Invalid max_prompt_tokens %r; falling back to auto.", override)

    device = (device or "GPU").upper()
    model_dir = Path(model_dir) if model_dir else text_gen_model_dir()
    try:
        budget = _memory_budget(device, kv_bytes_per_token(model_dir, device), model_dir,
                                gpu_memory_safety_margin)
        reason = "memory"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read device memory on %s (%s); assuming %d tokens.",
                       device, exc, DEFAULT_PROMPT_TOKENS)
        budget, reason = DEFAULT_PROMPT_TOKENS, "default"

    if max_content_tokens and 0 < int(max_content_tokens) < budget:
        budget, reason = int(max_content_tokens), "quality"

    # Shipped models have context windows well above the quality limit.

    logger.info("Prompt budget on %s: %d tokens (limited by %s).", device, budget, reason)
    return budget



def budget_from_config(chunking_cfg, device: str = "GPU") -> int:
    """Resolve the budget from a ``models.text_gen.chunking`` config node."""
    return resolve_budget(
        device,
        override=getattr(chunking_cfg, "max_prompt_tokens", "auto"),
        max_content_tokens=getattr(chunking_cfg, "max_content_tokens",
                                   DEFAULT_MAX_CONTENT_TOKENS),
        gpu_memory_safety_margin=getattr(chunking_cfg, "gpu_memory_safety_margin", None),
    )


def usable_tokens(budget: int, reserve_tokens: int) -> int:
    """Return budget left for content. Cap reserve at half budget so chunks remain usable."""
    reserve = max(0, reserve_tokens)
    cap = max(0, budget) // 2
    if reserve > cap:
        if (budget, reserve) not in _CAP_WARNED:
            _CAP_WARNED.add((budget, reserve))
            logger.warning(
                "Instructions and answer alone want %d of a %d-token budget; capping "
                "the reserve at %d (half). The answer may be truncated -- lower "
                "max_new_tokens for this device, or shorten the board text.",
                reserve, budget, cap,
            )
        reserve = cap
    return max(1, budget - reserve)


def _pack_to_ceiling(weights: List[int], ceiling: int,
                     overlap: int) -> List[Tuple[int, int]]:
    """Pack whole lines up to the ceiling, carrying overflow into the next group."""
    groups: List[Tuple[int, int]] = []
    start = 0
    while start < len(weights):
        end = start
        tokens = 0
        while end < len(weights):
            next_tokens = tokens + weights[end]
            if end > start and next_tokens > ceiling:
                break
            tokens = next_tokens
            end += 1

        groups.append((start, end))
        if end == len(weights):
            break

        # Keep as much overlap as fits alongside the next new line.
        next_start = max(start + 1, end - overlap)
        while next_start < end and sum(weights[next_start:end + 1]) > ceiling:
            next_start += 1
        start = next_start
    return groups


def _balanced_ceiling(weights: List[int], cap: int, overlap: int,
                      n_groups: int, total: int) -> int:
    """Return the smallest ceiling that still packs into ``n_groups``.

    Dividing ``total`` by the group count instead would undercount: every group
    but the first repeats ``overlap`` lines, which fill a ceiling without
    carrying new text, and greedy packing stops short of the ceiling by up to
    one line. Halving a transcript that needs two groups therefore leaves a
    remainder for a third, stub group. Searching for the ceiling measures both
    losses rather than trying to predict them.

    Group count is non-increasing in the ceiling, so a binary search finds it.
    """
    lo, hi = math.ceil(total / n_groups), cap
    while lo < hi:
        mid = (lo + hi) // 2
        if len(_pack_to_ceiling(weights, mid, overlap)) <= n_groups:
            hi = mid
        else:
            lo = mid + 1
    return lo


def plan_line_groups(weights: List[int], *, budget_tokens: int,
                     overlap_lines: int = DEFAULT_OVERLAP_LINES,
                     reserve_tokens: int = 0,
                     stage_reserve_tokens: Optional[int] = None,
                     label: str = "chunk") -> List[Tuple[int, int]]:
    """Return budget-safe line groups. Weight-only planning keeps formats aligned."""
    n_units = len(weights)
    if not n_units:
        return []

    total = sum(weights)
    # The whole-lesson reserve decides whether one call does; a chunk's own,
    # smaller reserve decides how big each chunk may then be.
    if total <= usable_tokens(budget_tokens, reserve_tokens):
        return [(0, n_units)]

    stage = reserve_tokens if stage_reserve_tokens is None else stage_reserve_tokens
    cap = usable_tokens(budget_tokens, stage)
    # The loosest packing gives the fewest calls. Two at minimum: the text is
    # already past what one whole-lesson call holds, so a single group would
    # send the very call this is splitting to avoid.
    n_groups = max(2, len(_pack_to_ceiling(weights, cap, overlap_lines)))
    ceiling = _balanced_ceiling(weights, cap, overlap_lines, n_groups, total)
    groups = _pack_to_ceiling(weights, ceiling, overlap_lines)
    if len(groups) > n_groups:
        # The search assumes the group count falls as the ceiling rises, which
        # a pathological run of line weights could break. Losing the balance is
        # better than emitting a group the search did not sanction.
        logger.debug("Balanced ceiling %d gave %d %ss, not %d; packing to the cap.",
                     ceiling, len(groups), label, n_groups)
        ceiling = cap
        groups = _pack_to_ceiling(weights, cap, overlap_lines)

    sizes = [sum(weights[lo:hi]) for lo, hi in groups]
    if max(sizes) > ceiling:
        logger.warning(
            "Largest %s is %d tokens against the %d that fit: an unusually long "
            "line could not be packed any tighter.", label, max(sizes), ceiling,
        )

    logger.info("Split %d lines (%d tokens) into %d %ss of %d-%d tokens (ceiling %d).",
                n_units, total, len(groups), label, min(sizes), max(sizes), ceiling)
    return groups


def chunks_from_groups(lines: List[str], groups: List[tuple], *,
                       times: Optional[List[tuple]] = None,
                       weights: Optional[List[int]] = None,
                       tokenizer=None, joiner: str = "\n") -> List[Chunk]:
    """Render line groups as chunks. Reusing groups keeps transcript formats aligned."""
    if weights is None:
        weights = [count_tokens(l, tokenizer) + 1 for l in lines]

    chunks = []
    for idx, (lo, hi) in enumerate(groups):
        start, end = (times[lo][0], times[hi - 1][1]) if times else (None, None)
        chunks.append(Chunk(
            text=joiner.join(lines[lo:hi]),
            index=idx,
            total=len(groups),
            tokens=sum(weights[lo:hi]),
            start=start,
            end=end,
        ))
    return chunks


def chunk_lines(lines: List[str], *, budget_tokens: int,
                overlap_lines: int = DEFAULT_OVERLAP_LINES,
                tokenizer=None,
                times: Optional[List[tuple]] = None,
                reserve_tokens: int = 0,
                stage_reserve_tokens: Optional[int] = None,
                label: str = "chunk") -> List[Chunk]:
    """Split only between lines. Optional overlap and timestamps preserve context."""
    lines = [l for l in lines if l and l.strip()]
    if not lines:
        return []

    weights = [count_tokens(l, tokenizer) + 1 for l in lines]
    groups = plan_line_groups(
        weights,
        budget_tokens=budget_tokens,
        overlap_lines=overlap_lines,
        reserve_tokens=reserve_tokens,
        stage_reserve_tokens=stage_reserve_tokens,
        label=label,
    )
    return chunks_from_groups(lines, groups, times=times, weights=weights)


def render_transcript_lines(lines: List[dict]) -> List[str]:
    """Render ``parse_transcript_lines`` output back to ``[start-end] text``."""
    return [f"[{int(l['start'])}-{int(l['end'])}] {l['text']}" for l in lines]


def chunk_transcript_lines(lines: List[dict], *, budget_tokens: int,
                           overlap_lines: int = DEFAULT_OVERLAP_LINES,
                           tokenizer=None, reserve_tokens: int = 0,
                           stage_reserve_tokens: Optional[int] = None,
                           label: str = "chunk") -> List[Chunk]:
    """Chunk ``parse_transcript_lines`` output, tagging each chunk's time range."""
    if not lines:
        return []
    return chunk_lines(
        render_transcript_lines(lines),
        budget_tokens=budget_tokens,
        overlap_lines=overlap_lines,
        tokenizer=tokenizer,
        times=[(l["start"], l["end"]) for l in lines],
        reserve_tokens=reserve_tokens,
        stage_reserve_tokens=stage_reserve_tokens,
        label=label,
    )


