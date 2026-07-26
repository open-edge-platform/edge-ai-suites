# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Runs ONE (model, context length) capacity trial for the long-context validator.

The question a trial answers is deliberately narrow, mirroring
refer/long_context/validate_long_context.py: *can this hardware load the model,
prefill a prompt of the requested token size, and decode a few tokens without
running out of memory (or hanging)?* It does NOT judge answer quality -- content
is irrelevant, only whether the box survives the token volume.

Executed as a fresh subprocess per trial (see validate_long_context.py) so that
GPU/host memory from a crashed or OOM'd attempt can never bleed into the next
trial -- the same "convert in a subprocess so memory is fully reclaimed on exit"
rationale already used for model conversion in
components/vlm/vlm_openvino_serving/utils/utils.py::_convert_model_worker.

Memory is sampled by the *orchestrator* (parent), not here: system RAM / GPU
counters are process-wide, so the parent sees this child's footprint just as
well, and -- crucially -- its readings survive even when this child is killed on
a timeout. This child only signals two milestones over the queue so the parent
can time its snapshots: an "loaded" event once the weights are resident (so the
parent can separate weight memory from KV-cache memory), then a "done" event
with the trial outcome.

OpenVINO / transformers are imported lazily inside run_trial() rather than at
module scope, so this module -- and therefore validate_long_context.py, which
imports it -- can be imported (e.g. for --dry-run) on a machine that doesn't
have the OpenVINO stack installed.
"""

from __future__ import annotations

import gc
import os
import sys
import time
import traceback
import unicodedata

from components.llm.context_validation.context_builder import build_context_prompt

_OOM_MARKERS = (
    "out of gpu resources",
    "out of memory",
    "allocation failed",
    "bad_alloc",
    "cannot allocate",
    "insufficient memory",
    "memoryerror",
)


def _classify_error(exc: Exception) -> str:
    text = str(exc).lower()
    if any(marker in text for marker in _OOM_MARKERS):
        return "oom"
    return "exception"


def _validate_generated_output(output: str, tokenizer) -> tuple[bool, int, str | None]:
    """Reject empty, undecodable, control-only, and low-information output."""
    if not output or not output.strip():
        return False, 0, "no_output"

    token_ids = tokenizer.encode(output, add_special_tokens=False)
    if not token_ids:
        return False, 0, "no_output_tokens"

    decoded = tokenizer.decode(token_ids, skip_special_tokens=True).strip()
    if not decoded:
        return False, len(token_ids), "special_tokens_only"
    if "\ufffd" in decoded or any(
        unicodedata.category(char) == "Cc" and char not in "\n\r\t" for char in decoded
    ):
        return False, len(token_ids), "invalid_characters"

    semantic_chars = [char.casefold() for char in decoded if char.isalnum()]
    if len(semantic_chars) < 3:
        return False, len(token_ids), "no_semantic_output"
    if len(set(semantic_chars)) == 1:
        return False, len(token_ids), "repetitive_output"
    return True, len(token_ids), None


def _load_tokenizer(model_dir: str, trust_remote_code: bool = True):
    """Load the tokenizer, working around two OpenVINO-export quirks seen on
    real `optimum-cli export openvino` output (neither is specific to one
    candidate model, so try progressively more permissive loaders rather than
    assuming which quirk, if any, is present):

    1. `extra_special_tokens` written as a list where transformers expects a
       dict -- same workaround as components/vlm/text_gen_vlm.py::VLMTextGen._load.
    2. `tokenizer_config.json`'s declared `tokenizer_class` (e.g.
       "TokenizersBackend") isn't a class AutoTokenizer can resolve, even
       though `tokenizer.json` is a perfectly valid fast-tokenizer file --
       load it directly via PreTrainedTokenizerFast, which doesn't need to
       resolve a class name.

    The tokenizer is used only to size the prompt and count tokens; the model's
    own openvino_tokenizer.xml handles real inference. transformers' "tokenizer
    class you load ... is not the same type as the class this function is called
    from" warning during the PreTrainedTokenizerFast fallback is therefore
    expected and harmless, so it's silenced here to keep the sweep log readable
    (it would otherwise repeat for every trial's fresh subprocess).
    """
    from transformers import AutoTokenizer, PreTrainedTokenizerFast
    from transformers.utils import logging as hf_logging

    hf_logging.set_verbosity_error()

    attempts = [
        (AutoTokenizer, {}),
        (AutoTokenizer, {"extra_special_tokens": {}}),
        (PreTrainedTokenizerFast, {}),
        (PreTrainedTokenizerFast, {"extra_special_tokens": {}}),
    ]
    last_exc = None
    for tokenizer_cls, extra_kwargs in attempts:
        try:
            return tokenizer_cls.from_pretrained(
                model_dir, trust_remote_code=trust_remote_code, **extra_kwargs
            )
        except (ValueError, AttributeError) as exc:
            last_exc = exc
    raise last_exc


def _load_pipeline(model_dir: str, device: str, ov_config: dict):
    """Pick LLMPipeline or VLMPipeline based on which IR layout is on disk.

    A candidate model can convert to a plain causal-LM export
    (openvino_model.xml) or a multimodal/VLM export (openvino_language_model.xml
    plus vision-embedding components) depending on the model's own architecture
    -- optimum-cli decides this, not us. Both pipeline classes expose the same
    .generate(prompt, generation_config=...) surface used below, so the rest of
    run_trial doesn't need to know which one it got.
    """
    import openvino_genai as ov_genai

    if os.path.exists(os.path.join(model_dir, "openvino_language_model.xml")):
        return ov_genai.VLMPipeline(model_dir, device=device, **ov_config)
    if os.path.exists(os.path.join(model_dir, "openvino_model.xml")):
        return ov_genai.LLMPipeline(model_dir, device=device, **ov_config)
    raise RuntimeError(
        f"Unrecognized OpenVINO IR layout in {model_dir}: expected openvino_model.xml "
        "(plain LLM) or openvino_language_model.xml (multimodal/VLM export)"
    )


def run_trial(
    model_dir: str,
    model_name: str,
    device: str,
    tokens: int,
    probe_tokens: int,
    result_queue,
) -> None:
    """Load the model, prefill a ~`tokens`-token prompt, decode up to
    `probe_tokens` tokens, and report the outcome over `result_queue`.

    Posts up to two messages: `{"event": "loaded", ...}` once the weights are
    resident (skipped if loading fails), then `{"event": "done", ...}` with the
    result. Finding the memory ceiling only needs a few decode steps, not a full
    summary, so `probe_tokens` is small on purpose -- generating thousands of
    tokens at 128K+ context would add many minutes per step for no extra signal.
    """
    done = {
        "event": "done",
        "tokens_requested": tokens,
        "load_ok": False,
        "load_time_s": None,
        "generate_ok": False,
        "prompt_tokens": 0,
        "generated_tokens": 0,
        "generate_time_s": None,
        "error": None,
    }

    try:
        t0 = time.perf_counter()
        tokenizer = _load_tokenizer(model_dir)
        ov_config = (
            {"GPU_ENABLE_LARGE_ALLOCATIONS": "YES"} if device.upper().startswith("GPU") else {}
        )
        pipe = _load_pipeline(model_dir, device, ov_config)
        done["load_ok"] = True
        done["load_time_s"] = round(time.perf_counter() - t0, 3)
        # Tell the parent the weights are resident so it can snapshot post-load
        # memory (weight footprint) before prefill grows it (KV-cache footprint).
        result_queue.put({"event": "loaded", "load_time_s": done["load_time_s"]})
    except Exception as exc:  # noqa: BLE001 - reported to orchestrator, not re-raised
        print(f"[trial_runner] load failed: {traceback.format_exc()}", file=sys.stderr)
        done["error"] = f"load:{_classify_error(exc)}:{exc}"
        result_queue.put(done)
        return

    import openvino_genai as ov_genai

    try:
        prompt, prompt_tokens = build_context_prompt(tokenizer, tokens)
        done["prompt_tokens"] = prompt_tokens

        # Plain greedy decoding, no structured output: proving the hardware can
        # prefill + decode this context is the only goal, and grammar-constrained
        # decoding was observed to collapse into garbage output ("!!!!") on some
        # models, which would score a false FAIL for a context the box handled.
        gen_config = ov_genai.GenerationConfig(max_new_tokens=probe_tokens, do_sample=False)
        t1 = time.perf_counter()
        output = str(pipe.generate(prompt, generation_config=gen_config))
        done["generate_time_s"] = round(time.perf_counter() - t1, 3)
        output_ok, generated_tokens, output_error = _validate_generated_output(output, tokenizer)
        done["generated_tokens"] = generated_tokens
        done["generate_ok"] = output_ok
        done["error"] = output_error
    except Exception as exc:  # noqa: BLE001
        print(f"[trial_runner] generate failed: {traceback.format_exc()}", file=sys.stderr)
        done["error"] = f"generate:{_classify_error(exc)}:{exc}"
        done["generate_ok"] = False
    finally:
        try:
            del pipe
            gc.collect()
        except Exception:
            pass

    result_queue.put(done)
