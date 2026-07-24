# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Runs ONE (model, context length) trial for the long-context validator.

Executed as a fresh subprocess per trial (see validate_long_context.py) so that
GPU/host memory from a crashed or OOM'd attempt can never bleed into the next
trial -- the same "convert in a subprocess so memory is fully reclaimed on exit"
rationale already used for model conversion in
components/vlm/vlm_openvino_serving/utils/utils.py::_convert_model_worker.

OpenVINO / transformers are imported lazily inside run_trial() rather than at
module scope, so this module -- and therefore validate_long_context.py, which
imports it -- can be imported (e.g. for --dry-run) on a machine that doesn't
have the OpenVINO stack installed.
"""

from __future__ import annotations

import gc
import os
import random
import sys
import time
import traceback

from components.llm.context_validation.haystack_builder import build_probe

_OOM_MARKERS = ("out of gpu resources", "out of memory", "allocation failed", "bad_alloc")


def _classify_error(exc: Exception) -> str:
    text = str(exc).lower()
    if any(marker in text for marker in _OOM_MARKERS):
        return "oom"
    return "exception"


def _apply_qwen3_no_think(model_name: str, messages: list) -> list:
    """Mirrors components/summarizer_component.py::_get_message's /no_think prefix."""
    if "qwen3" not in model_name.lower():
        return messages
    user_msg = messages[-1]
    if user_msg.get("role") == "user" and not user_msg["content"].lstrip().startswith("/no_think"):
        user_msg = dict(user_msg, content="/no_think\n" + user_msg["content"])
        return messages[:-1] + [user_msg]
    return messages


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
    """
    from transformers import AutoTokenizer, PreTrainedTokenizerFast

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
    probe_depths: list,
    max_new_tokens_probe: int,
    result_queue,
    answer_preamble_chars: int = 200,
) -> None:
    """Load the model once, run one needle probe per depth, report a result dict.

    Always puts exactly one dict on result_queue before returning, even on
    failure, so the orchestrator never blocks indefinitely on a trial that
    errors out cleanly (a hard crash/segfault is instead caught by the
    orchestrator's process-liveness check).
    """
    result = {
        "tokens_requested": tokens,
        "load_ok": False,
        "load_time_s": None,
        "generate_ok": False,
        "accuracy": 0.0,
        "probes": [],
        "error": None,
    }

    try:
        t0 = time.perf_counter()
        tokenizer = _load_tokenizer(model_dir)
        ov_config = (
            {"GPU_ENABLE_LARGE_ALLOCATIONS": "YES"} if device.upper().startswith("GPU") else {}
        )
        pipe = _load_pipeline(model_dir, device, ov_config)
        result["load_ok"] = True
        result["load_time_s"] = round(time.perf_counter() - t0, 3)
    except Exception as exc:  # noqa: BLE001 - reported to orchestrator, not re-raised
        print(f"[trial_runner] load failed: {traceback.format_exc()}", file=sys.stderr)
        result["error"] = f"load:{_classify_error(exc)}:{exc}"
        result_queue.put(result)
        return

    import openvino_genai as ov_genai

    # Fresh entropy per trial so the planted fact can't be answered from memorized
    # training data instead of from the context actually supplied, and so repeated
    # sweeps don't keep re-testing the exact same code.
    seed_base = random.SystemRandom().randrange(1, 2**31 - 1)
    correct = 0
    attempted = 0

    try:
        for i, depth in enumerate(probe_depths):
            probe = build_probe(tokenizer, tokens, depth, seed=seed_base + i)
            messages = _apply_qwen3_no_think(model_name, probe.messages)
            prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
            )
            # Constrain the answer via structured output (grammar-constrained
            # decoding) rather than trusting free-form generation + a "please
            # answer briefly" instruction to behave. Real-hardware testing
            # showed two failure modes with plain free-form generation on this
            # synthetic transcript: (a) some models narrate "Let me analyze
            # this jumbled request..." for hundreds of tokens regardless of
            # /no_think, enable_thinking=False, and explicit "no preamble"
            # instructions -- max_new_tokens_probe alone can't fix a model
            # that won't stop explaining itself; (b) constraining the FIRST
            # token to a digit (regex=r"\d{N}", no preamble allowed at all)
            # reliably got a clean answer fast, but a noticeably *wrong* one
            # (generic-looking guesses like "100000"/"123456") -- with zero
            # room to engage with the transcript before committing, the model
            # had nothing to condition the answer on. Allowing a bounded
            # free-text lead-in before requiring the digits is the middle
            # ground: real reasoning room, but the generation is still
            # guaranteed to end in a clean, parseable answer instead of
            # rambling indefinitely or being truncated mid-thought with no
            # answer at all.
            structured_output_config = ov_genai.StructuredOutputConfig(
                regex=rf"[\s\S]{{0,{answer_preamble_chars}}}\d{{{len(probe.expected_code)}}}"
            )
            gen_config = ov_genai.GenerationConfig(
                max_new_tokens=max_new_tokens_probe,
                do_sample=False,
                structured_output_config=structured_output_config,
            )
            t1 = time.perf_counter()
            output = str(pipe.generate(prompt, generation_config=gen_config))
            elapsed = time.perf_counter() - t1
            attempted += 1
            is_correct = probe.expected_code.lower() in output.lower()
            correct += int(is_correct)
            result["probes"].append(
                {
                    "depth": depth,
                    "tokens_actual": probe.tokens_actual,
                    "correct": is_correct,
                    "generate_time_s": round(elapsed, 3),
                    "expected_code": probe.expected_code,
                    # Sized to answer_preamble_chars + margin so this captures
                    # the FULL answer (reasoning scaffold and concluding
                    # digits), not just the opening -- with a large preamble
                    # budget, a small fixed cap here would only ever show the
                    # boilerplate "1. Analyze the Request..." opening and cut
                    # off exactly the part (the conclusion) needed to tell a
                    # genuine wrong answer apart from truncated reasoning. See
                    # docs/dev-guide/validate_long_context.md §3.7.
                    "answer": output[: answer_preamble_chars + 100],
                }
            )
        result["generate_ok"] = True
    except Exception as exc:  # noqa: BLE001
        print(f"[trial_runner] generate failed: {traceback.format_exc()}", file=sys.stderr)
        result["error"] = f"generate:{_classify_error(exc)}:{exc}"
        result["generate_ok"] = False
    finally:
        result["accuracy"] = (correct / attempted) if attempted else 0.0
        try:
            del pipe
            gc.collect()
        except Exception:
            pass

    result_queue.put(result)
