# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
import os
import sys

import pytest

_SC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SC_ROOT not in sys.path:
    sys.path.insert(0, _SC_ROOT)

from utils import text_chunker as tc


class FakeTokenizer:
    """One token per whitespace-delimited word."""

    def encode(self, text):
        return text.split()


def _transcript(n_lines, words_per_line=10):
    return [
        {"start": float(i * 10), "end": float(i * 10 + 10),
         "text": " ".join(f"w{i}_{j}" for j in range(words_per_line))}
        for i in range(n_lines)
    ]


def _group_count(total_tokens, budget, reserve=0, stage_reserve=None, *, weight=100):
    """How many calls ``total_tokens`` of even lines are planned into.

    Planning is weight-only, so a transcript can stand in as a flat list of
    equal lines. This is the question every caller of ``plan_line_groups``
    actually asks it, spelled once here rather than in every test below.
    """
    weights = [weight] * max(1, round(total_tokens / weight))
    return len(tc.plan_line_groups(
        weights, budget_tokens=budget, overlap_lines=0,
        reserve_tokens=reserve, stage_reserve_tokens=stage_reserve,
    ))


# ---------------------------------------------------------------- token counts

def test_estimate_does_not_underestimate_chinese():
    zh = "这是一节关于经济学原理的课程录音转写内容"
    assert tc.estimate_tokens(zh) >= len(zh)


def test_estimate_handles_mixed_and_empty():
    assert tc.estimate_tokens("") == 0
    mixed = "供给 supply 需求 demand"
    assert tc.estimate_tokens(mixed) > tc.estimate_tokens("supply demand")


def test_count_tokens_prefers_tokenizer_and_survives_failure():
    assert tc.count_tokens("a b c", FakeTokenizer()) == 3

    class Broken:
        def encode(self, text):
            raise RuntimeError("tokenizer gone")

    assert tc.count_tokens("a b c", Broken()) > 0


# ------------------------------------------------------------------- planning

def test_text_within_budget_is_not_split():
    assert _group_count(13_000, 46_000) == 1
    assert _group_count(46_000, 46_000) == 1


def test_over_budget_uses_fewest_chunks_that_fit():
    assert _group_count(56_000, 46_000) == 2
    assert _group_count(56_000, 6_000) == 10


def test_generation_reserve_comes_off_the_budget():
    # The answer shares the cache with the prompt, so a transcript that fills
    # the budget exactly no longer counts as fitting in one call.
    assert _group_count(46_000, 46_000, reserve=0) == 1
    assert _group_count(46_000, 46_000, reserve=5_120) > 1

    # Chunks are sized against what is left after the reserve, not the budget.
    assert _group_count(40_000, 10_000, reserve=0) == 4
    assert _group_count(40_000, 10_000, reserve=5_000) == 8


def test_reserve_never_drives_the_budget_to_zero():
    # An unsatisfiable reserve is capped at half the budget rather than
    # collapsing the prompt budget into a sliver.
    assert _group_count(1_000, 500, reserve=9_999) == \
        _group_count(1_000, 500, reserve=250)
    assert _group_count(1_000, 500, reserve=-5) >= 1

    # The cap must keep the chunk count proportionate to the transcript.
    assert _group_count(8_400, 2_000, reserve=5_120) < 20


def test_a_split_never_returns_a_single_group():
    """Past the one-call limit, one group would send the very call being split."""
    # Packing alone fits this in one group; the reserve is what ruled that out.
    assert _group_count(20_000, 24_000, 5_264, 1_736) == 2
    assert _group_count(1, 10, reserve=9) == 1, "but a text that does fit stays whole"


def test_reserve_reaches_the_chunking_helpers():
    # 100 rendered lines of 11 tokens, plus one separator each: 1200 tokens.
    lines = _transcript(100)
    tok = FakeTokenizer()
    without = tc.chunk_transcript_lines(
        lines, budget_tokens=2_000, overlap_lines=0, tokenizer=tok
    )
    assert len(without) == 1

    # 900 is under the half-budget cap, leaving 1100 usable for 1200 tokens.
    with_reserve = tc.chunk_transcript_lines(
        lines, budget_tokens=2_000, overlap_lines=0, tokenizer=tok,
        reserve_tokens=900,
    )
    assert len(with_reserve) > 1


# --------------------------------------------------------------- kv cache size

def _model_dir(tmp_path, name, payload):
    path = tmp_path / name
    path.mkdir()
    (path / "config.json").write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_kv_bytes_follow_the_model_architecture(tmp_path, monkeypatch):
    tc.kv_bytes_per_token.cache_clear()
    monkeypatch.setattr(tc, "_kv_dtype_bytes", lambda device: 1)

    # Qwen3-VL-8B: the language model config is nested under text_config.
    big = _model_dir(tmp_path, "big", {
        "text_config": {"num_hidden_layers": 36, "num_attention_heads": 32,
                        "num_key_value_heads": 8, "head_dim": 128, "hidden_size": 4096},
    })
    assert tc.kv_bytes_per_token(big, "GPU") == int(2 * 36 * 8 * 128 * 1.25)

    # Fewer KV heads must cost proportionally less per token.
    small = _model_dir(tmp_path, "small", {
        "text_config": {"num_hidden_layers": 36, "num_attention_heads": 16,
                        "num_key_value_heads": 2, "head_dim": 128, "hidden_size": 2048},
    })
    assert tc.kv_bytes_per_token(small, "GPU") * 4 == tc.kv_bytes_per_token(big, "GPU")


def test_kv_bytes_infer_head_dim_and_survive_a_missing_config(tmp_path, monkeypatch):
    tc.kv_bytes_per_token.cache_clear()
    monkeypatch.setattr(tc, "_kv_dtype_bytes", lambda device: 2)

    # No head_dim and no GQA: 512/8 dims cached for each of the 8 heads.
    plain = _model_dir(tmp_path, "plain", {
        "num_hidden_layers": 4, "num_attention_heads": 8, "hidden_size": 512,
    })
    assert tc.kv_bytes_per_token(plain, "CPU") == int(2 * 4 * 8 * 64 * 2 * 1.25)

    assert tc.kv_bytes_per_token(str(tmp_path / "absent"), "CPU") == tc.DEFAULT_BYTES_PER_TOKEN


# -------------------------------------------------------------- memory ceiling

def test_memory_budget_spends_capacity_minus_headroom(monkeypatch):
    monkeypatch.setattr(tc, "_capacity_bytes", lambda device, model_dir=None: 8 * 1024 ** 3)
    assert tc._memory_budget("GPU", 92_160) == \
        int(8 * 1024 ** 3 * tc.GPU_MEMORY_SAFETY_MARGIN // 92_160)

    monkeypatch.setattr(tc, "_capacity_bytes", lambda device, model_dir=None: 1024)
    with pytest.raises(ValueError):
        tc._memory_budget("GPU", 92_160)


def test_headroom_leaves_room_for_the_rest_of_the_machine():
    """The budget is sized from capacity, so the headroom is the only guard."""
    assert tc.GPU_MEMORY_SAFETY_MARGIN <= 0.7, \
        "capacity is not free memory; a busy machine has to fit under this"


def test_capacity_is_what_the_machine_holds_not_what_is_free(monkeypatch, tmp_path):
    """The same lesson must split the same way however busy the machine is."""
    import psutil

    (tmp_path / "openvino_language_model.bin").write_bytes(b"x" * 4096)

    class Mem:
        total = 32 * 1024 ** 3
        available = 3 * 1024 ** 3   # a busy machine

    monkeypatch.setattr(psutil, "virtual_memory", lambda: Mem())
    capacity = tc._capacity_bytes("CPU", tmp_path)

    Mem.available = 30 * 1024 ** 3  # an idle one
    assert tc._capacity_bytes("CPU", tmp_path) == capacity

    # Total, less the weights the pipeline already holds resident.
    assert capacity == 32 * 1024 ** 3 - 4096


def test_a_gpu_is_sized_by_what_it_can_address_not_by_system_ram(monkeypatch, tmp_path):
    """An integrated GPU reaches only part of RAM; the rest is not capacity."""
    import psutil
    import openvino as ov

    (tmp_path / "openvino_language_model.bin").write_bytes(b"x" * 4096)

    class Mem:
        total = 32 * 1024 ** 3
        available = 20 * 1024 ** 3

    class Core:
        def get_property(self, device, name):
            assert name == "GPU_DEVICE_TOTAL_MEM_SIZE"
            return 25 * 1024 ** 3   # what the driver lets the iGPU address

    monkeypatch.setattr(psutil, "virtual_memory", lambda: Mem())
    monkeypatch.setattr(ov, "Core", Core)

    # The plugin's figure, not RAM -- and the device type is never consulted,
    # so an integrated GPU is sized the same way a discrete one is.
    assert tc._capacity_bytes("GPU", tmp_path) == 25 * 1024 ** 3 - 4096


# ------------------------------------------------------------- quality ceiling

def test_quality_ceiling_caps_a_large_machine(monkeypatch):
    monkeypatch.setattr(tc, "_memory_budget", lambda *a, **k: 140_000)
    monkeypatch.setattr(tc, "kv_bytes_per_token", lambda *a, **k: 92_160)

    # Memory alone would send a whole 56k lesson in one call on this machine.
    assert tc.resolve_budget("GPU", max_content_tokens=0) == 140_000
    assert tc.resolve_budget("GPU", max_content_tokens=24_000) == 24_000


def test_memory_wins_when_it_is_the_tighter_of_the_two(monkeypatch):
    monkeypatch.setattr(tc, "_memory_budget", lambda *a, **k: 8_000)
    monkeypatch.setattr(tc, "kv_bytes_per_token", lambda *a, **k: 92_160)
    assert tc.resolve_budget("GPU", max_content_tokens=24_000) == 8_000


def test_an_explicit_budget_overrides_both_arms(monkeypatch):
    monkeypatch.setattr(tc, "_memory_budget", lambda *a, **k: 140_000)
    assert tc.resolve_budget("GPU", override=48_000, max_content_tokens=24_000) == 48_000


# ------------------------------------------------------- one plan, two reserves

def test_a_chunk_is_not_charged_for_an_answer_it_never_writes():
    """The map stage writes 1536 tokens, not the reduce stage's 5120."""
    single, stage = 5_264, 1_736

    # 40k of transcript: three chunks if each pays for a 5120-token summary,
    # two if each pays only for the 1536-token note it actually writes.
    assert _group_count(40_000, 24_000, single) == 3
    assert _group_count(40_000, 24_000, single, stage) == 2

    # The fit decision still uses the single-call reserve, not the stage one.
    assert _group_count(20_000, 24_000, single, stage) > 1
    assert _group_count(18_000, 24_000, single, stage) == 1


def test_plan_line_groups_covers_every_line_once():
    weights = [100] * 60
    groups = tc.plan_line_groups(weights, budget_tokens=2_000, reserve_tokens=200,
                                 overlap_lines=0)
    assert len(groups) > 1
    assert groups[0][0] == 0
    assert groups[-1][1] == len(weights)
    # No overlap requested, so the groups abut exactly.
    for (_, hi), (lo, _) in zip(groups, groups[1:]):
        assert lo == hi


def test_plan_line_groups_warns_when_a_line_cannot_be_packed_tighter(caplog):
    # One line alone is wider than a chunk may be, so no packing can help.
    weights = [200] * 10 + [4_000] + [200] * 10
    with caplog.at_level("WARNING"):
        tc.plan_line_groups(weights, budget_tokens=2_000, reserve_tokens=200,
                            label="segment")
    assert any("could not be packed any tighter" in r.message for r in caplog.records)


# ------------------------------------------------- the busy-machine backstop

def test_a_call_that_will_not_fit_right_now_is_reported(monkeypatch, caplog):
    """Capacity cannot see a busy machine; this is what notices."""
    monkeypatch.setattr(tc, "_free_bytes_now", lambda device: 2 * 1024 ** 3)
    monkeypatch.setattr(tc, "kv_bytes_per_token", lambda *a, **k: 92_160)

    with caplog.at_level("WARNING"):
        assert tc.warn_if_short_of_memory(40_000, "GPU") is True   # 3.4 GB
    assert any("only 2.00 GB is free" in r.message for r in caplog.records)

    caplog.clear()
    with caplog.at_level("WARNING"):
        assert tc.warn_if_short_of_memory(10_000, "GPU") is False  # 0.86 GB
    assert not caplog.records


def test_the_backstop_only_reports(monkeypatch):
    """It must not feed back into the budget, or the plan stops being stable."""
    monkeypatch.setattr(tc, "_free_bytes_now", lambda device: 1024)
    monkeypatch.setattr(tc, "_memory_budget", lambda *a, **k: 140_000)
    monkeypatch.setattr(tc, "kv_bytes_per_token", lambda *a, **k: 92_160)

    assert tc.resolve_budget("GPU", max_content_tokens=24_000) == 24_000


def test_free_memory_is_unknowable_on_a_discrete_gpu(monkeypatch):
    """No reliable free-VRAM figure, so the check is skipped rather than guessed."""
    import openvino as ov

    class Core:
        def get_property(self, device, name):
            assert name == "DEVICE_TYPE"
            return "Type.DISCRETE"

    monkeypatch.setattr(ov, "Core", Core)
    assert tc._free_bytes_now("GPU") is None
    assert tc.warn_if_short_of_memory(10 ** 9, "GPU") is False


def test_reserve_cap_is_not_silent(caplog):
    tc._CAP_WARNED.discard((1_000, 9_999))
    with caplog.at_level("WARNING"):
        assert tc.usable_tokens(1_000, 9_999) == 500
    assert any("capping the reserve" in r.message for r in caplog.records)

    # Planning one transcript asks this five times over; one warning is enough.
    caplog.clear()
    with caplog.at_level("WARNING"):
        assert tc.usable_tokens(1_000, 9_999) == 500
    assert not caplog.records


def test_weights_are_measured_from_the_ir_not_guessed(tmp_path):
    (tmp_path / "openvino_language_model.bin").write_bytes(b"x" * 1000)
    (tmp_path / "openvino_vision_embeddings_model.bin").write_bytes(b"x" * 24)
    (tmp_path / "openvino_language_model.xml").write_bytes(b"x" * 4096)  # graph, not weights
    assert tc._weights_bytes(tmp_path) == 1024
    assert tc._weights_bytes(tmp_path / "absent") == 0


# ------------------------------------------------------------------- chunking

def test_chunks_stay_under_budget_and_cover_every_line():
    lines = _transcript(200)
    chunks = tc.chunk_transcript_lines(
        lines, budget_tokens=300, overlap_lines=0, tokenizer=FakeTokenizer()
    )
    assert len(chunks) > 1
    for c in chunks:
        assert c.tokens <= 300, f"chunk {c.index} = {c.tokens} tokens"

    seen = "\n".join(c.text for c in chunks)
    for line in lines:
        assert line["text"] in seen


def test_chunks_come_out_evenly_sized():
    """A remainder stub would make one thin note and drag the reduce stage down."""
    chunks = tc.chunk_transcript_lines(
        _transcript(200), budget_tokens=300, overlap_lines=0, tokenizer=FakeTokenizer()
    )
    sizes = [c.tokens for c in chunks]
    assert max(sizes) - min(sizes) <= max(sizes) * 0.25, sizes


def test_chunks_never_split_a_line():
    lines = _transcript(120)
    chunks = tc.chunk_transcript_lines(
        lines, budget_tokens=250, overlap_lines=0, tokenizer=FakeTokenizer()
    )
    rendered = {f"[{int(l['start'])}-{int(l['end'])}] {l['text']}" for l in lines}
    for chunk in chunks:
        for line in chunk.text.split("\n"):
            assert line in rendered


def test_overlap_repeats_trailing_lines_into_the_next_chunk():
    lines = _transcript(120)
    chunks = tc.chunk_transcript_lines(
        lines, budget_tokens=250, overlap_lines=2, tokenizer=FakeTokenizer()
    )
    assert len(chunks) > 1
    for prev, nxt in zip(chunks, chunks[1:]):
        tail = prev.text.split("\n")[-2:]
        head = nxt.text.split("\n")[:2]
        assert tail == head


def test_chunks_carry_their_time_range():
    lines = _transcript(150)
    chunks = tc.chunk_transcript_lines(
        lines, budget_tokens=300, overlap_lines=0, tokenizer=FakeTokenizer()
    )
    assert chunks[0].start == lines[0]["start"]
    assert chunks[-1].end == lines[-1]["end"]
    for c in chunks:
        assert c.end > c.start


def test_single_chunk_when_transcript_fits():
    lines = _transcript(5)
    chunks = tc.chunk_transcript_lines(
        lines, budget_tokens=10_000, tokenizer=FakeTokenizer()
    )
    assert len(chunks) == 1
    assert chunks[0].total == 1


def test_untimestamped_lines_are_chunked_without_times():
    lines = [f"TEACHER: line {i} " + "word " * 20 for i in range(100)]
    chunks = tc.chunk_lines(
        lines, budget_tokens=300, overlap_lines=0, tokenizer=FakeTokenizer()
    )
    assert len(chunks) > 1
    assert all(c.start is None and c.end is None for c in chunks)


def test_empty_input_returns_no_chunks():
    assert tc.chunk_transcript_lines([], budget_tokens=100) == []
    assert tc.chunk_lines([], budget_tokens=100) == []
    assert tc.plan_line_groups([], budget_tokens=100) == []


def test_blank_lines_are_dropped_before_planning():
    """A transcript file ends in a newline; that must not become a weight."""
    chunks = tc.chunk_lines(["a b c", "", "   ", "d e f"], budget_tokens=1_000,
                            tokenizer=FakeTokenizer())
    assert chunks[0].text == "a b c\nd e f"


# ------------------------------------------- one plan, two renderings of a lesson

def test_groups_can_be_replayed_over_a_different_rendering():
    """chunks_from_groups is what lets a caller cut a twin file identically."""
    lines = _transcript(120)
    timed = tc.render_transcript_lines(lines)
    tok = FakeTokenizer()

    weights = [tc.count_tokens(l, tok) + 1 for l in timed]
    groups = tc.plan_line_groups(weights, budget_tokens=300, overlap_lines=0)
    assert len(groups) > 1

    # The same groups, applied to a speaker-labelled copy written line for line.
    speaker = [f"Teacher: {l['text']}" for l in lines]
    replayed = tc.chunks_from_groups(speaker, groups, tokenizer=tok)

    assert len(replayed) == len(groups)
    assert "Teacher:" in replayed[0].text
    assert [c.text.count("\n") for c in replayed] == \
        [hi - lo - 1 for lo, hi in groups]


def test_replayed_groups_can_borrow_the_times_they_cover():
    """A speaker transcript has no timestamps; its twin's groups lend it theirs."""
    lines = _transcript(120)
    tok = FakeTokenizer()
    weights = [tc.count_tokens(l, tok) + 1 for l in tc.render_transcript_lines(lines)]
    groups = tc.plan_line_groups(weights, budget_tokens=300, overlap_lines=0)

    times = [(l["start"], l["end"]) for l in lines]
    replayed = tc.chunks_from_groups([f"Teacher: {l['text']}" for l in lines],
                                     groups, times=times, tokenizer=tok)

    assert replayed[0].start == 0.0
    assert replayed[-1].end == float(len(lines) * 10)
    assert all(c.total == len(groups) for c in replayed)


def test_render_transcript_lines_round_trips_through_the_parser():
    from utils.transcript_parser import parse_transcript_lines

    lines = _transcript(5)
    rendered = tc.render_transcript_lines(lines)
    assert rendered[0] == "[0-10] w0_0 w0_1 w0_2 w0_3 w0_4 w0_5 w0_6 w0_7 w0_8 w0_9"
    assert parse_transcript_lines("\n".join(rendered)) == lines


# --------------------------------------------------------------- config plumbing

class _Chunking:
    """Stands in for the ``models.text_gen.chunking`` config node."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_budget_from_config_reads_the_chunking_node(monkeypatch):
    seen = {}
    monkeypatch.setattr(tc, "resolve_budget",
                        lambda device, **kw: seen.update(kw, device=device) or 1234)

    cfg = _Chunking(max_prompt_tokens=48_000, max_content_tokens=24_000,
                    gpu_memory_safety_margin=0.5)
    assert tc.budget_from_config(cfg, "CPU") == 1234
    assert seen == {"device": "CPU", "override": 48_000,
                    "max_content_tokens": 24_000, "gpu_memory_safety_margin": 0.5}


def test_budget_from_config_supplies_defaults_for_a_sparse_node(monkeypatch):
    """An operator who deleted a key must not get a zero budget."""
    seen = {}
    monkeypatch.setattr(tc, "resolve_budget",
                        lambda device, **kw: seen.update(kw) or 1)

    tc.budget_from_config(_Chunking(), "GPU")
    assert seen["override"] == "auto"
    assert seen["max_content_tokens"] == tc.DEFAULT_MAX_CONTENT_TOKENS
    assert seen["gpu_memory_safety_margin"] is None


def test_a_bad_explicit_budget_falls_back_to_auto(monkeypatch, caplog):
    monkeypatch.setattr(tc, "_memory_budget", lambda *a, **k: 140_000)
    monkeypatch.setattr(tc, "kv_bytes_per_token", lambda *a, **k: 92_160)

    with caplog.at_level("WARNING"):
        assert tc.resolve_budget("GPU", override="lots", max_content_tokens=24_000) == 24_000
    assert any("falling back to auto" in r.message for r in caplog.records)


def test_the_safety_margin_can_be_tightened_from_the_config(monkeypatch):
    monkeypatch.setattr(tc, "_capacity_bytes", lambda device, model_dir=None: 8 * 1024 ** 3)
    loose = tc._memory_budget("GPU", 92_160, gpu_memory_safety_margin=0.6)
    tight = tc._memory_budget("GPU", 92_160, gpu_memory_safety_margin=0.3)
    assert tight * 2 == loose


def test_an_unreadable_device_leaves_a_workable_budget(monkeypatch, caplog):
    """A machine whose memory cannot be sized still has to summarize."""
    monkeypatch.setattr(tc, "_memory_budget",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no device")))
    monkeypatch.setattr(tc, "kv_bytes_per_token", lambda *a, **k: 92_160)

    with caplog.at_level("WARNING"):
        assert tc.resolve_budget("GPU", max_content_tokens=0) == tc.DEFAULT_PROMPT_TOKENS
    assert any("Could not read device memory" in r.message for r in caplog.records)
