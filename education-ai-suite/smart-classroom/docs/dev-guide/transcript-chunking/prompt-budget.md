<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Prompt Budget and Transcript Chunking

A whole-lesson transcript is a bad fit for a single model call on two counts.
The model stops following its instructions well before its context window is
full, and the KV cache grows linearly until a small device runs out. This
document describes how the budget is computed, when a transcript is split, and
which knobs exist.

This document is derived from the implementation:

- `utils/text_chunker.py` — budget maths and the chunking helpers
- `utils/model_paths.py` — where the converted IR lives
- `components/summarizer_component.py` — summary map/reduce
- `components/segmentation/content_segmentation.py` — topic segmentation windows
- `prompts/segmentation/` — the two segmentation templates (`system.txt`, `user.txt`);
  the one-line fragments filled into them live in `content_segmentation.py`
- `config.yaml` (`models.text_gen.chunking`, `models.text_gen.segmentation`)

## Design Goals

- **A lesson that fits in one call is never split.** Splitting costs a little
  quality of its own, so it happens only when one call would cost more.
- **A lesson that does not fit is split into the fewest pieces that do.** There
  is deliberately no "tokens per chunk" knob; chunk size is derived.
- **The same lesson splits the same way every time.** The budget is a property
  of the machine and the model, never of what happened to be running.
- **Each consumer is sized against the text it actually sends.** The summary and
  the segmentation send different renderings of the lesson and reserve different
  amounts for their answers, so each plans its own split.
- **Changing `vlm_name` or `device` needs no retuning.** Everything that can be
  measured is measured at runtime.

## The Budget Chain

```
       ┌── quality ceiling ──┐
min ───┤                     ├──► budget ──► usable ──► chunk ceiling
       └── memory ceiling ───┘              (reserve)
             ▲
       total memory ──► bytes per token
                        (model geometry)
```

### Step 1 — The quality ceiling

`max_content_tokens` (24,000) is the length past which the model stops doing
what it was asked, as distinct from the length it can physically hold.

**Measured, on a 132-minute lesson (~56k tokens), Qwen3-VL-8B int4:**

| | One call | Split |
|---|---|---|
| Topics returned (15–25 required) | 144 | 20 |
| Lesson covered | 36% | 100% |
| Summary sections present (of 6) | 4 | 6 |

This is instruction-following decaying with context length, which is a
property of the model rather than of the machine, so it is a constant in
`utils/text_chunker.py` and not something fitted per device.

> **Why this number.** An earlier revision reached the same effect indirectly,
> through a prefill-time ceiling: `sqrt(max_prefill_seconds / prefill_coeff)`,
> which at its configured values worked out to ≈25,800 tokens. That is the
> ceiling under which the "Split" column above was measured. It was removed
> because `prefill_coeff` had to be re-fitted for every device, which is the
> wrong shape for a limit that does not actually depend on the device — but
> removing it took the quality ceiling with it, and left memory alone deciding.
> 24,000 keeps the number that was measured to work and drops the fitting.
>
> The band between 24k and 56k has not been probed. If a lesson needs to go in
> one call, raise `max_content_tokens` and check the topic count and the
> summary's section headings before trusting the result.

### Step 2 — Bytes per token

`kv_bytes_per_token(model_dir, device)` sizes one token of KV cache from the
model's own `config.json`:

```
bytes_per_token = 2 × layers × kv_heads × head_dim × kv_dtype_bytes × 1.25
```

| Term | Source |
|---|---|
| `2` | one key and one value per layer |
| `layers` | `num_hidden_layers` |
| `kv_heads` | `num_key_value_heads`, falling back to `num_attention_heads` when the model has no GQA |
| `head_dim` | `head_dim`, falling back to `hidden_size // num_attention_heads` |
| `kv_dtype_bytes` | the plugin's `KV_CACHE_PRECISION` property |
| `1.25` | `_KV_RUNTIME_OVERHEAD`: paged-cache block padding plus the activations alive during prefill |

A VLM nests its language model under `text_config`; that node is read when
present. If `config.json` cannot be read, `DEFAULT_BYTES_PER_TOKEN` (96 KB) is
used and a warning is logged.

**Measured values:**

| Model | Geometry | Bytes/token |
|---|---|---|
| Qwen3-VL-8B-Instruct int4 | 36 layers × 8 KV heads × 128 dims × 1 B | 92,160 (90 KB) |
| Qwen2.5-VL-3B-Instruct int8 | 36 layers × 2 KV heads × 128 dims × 1 B | 23,040 (22.5 KB) |

Two properties are worth stating explicitly, because both are easy to assume
wrongly:

- **`weight_format` does not appear in this formula.** Quantising the weights
  shrinks the model's constant footprint, not the per-token cost.
- **The device barely matters.** Its only influence is `KV_CACHE_PRECISION`.
  CPU reports `u8`; GPU reports `dynamic` (size 0), in which case
  `_DEFAULT_KV_DTYPE_BYTES` (1) is assumed. The worst-case spread is 2×, and it
  is queried rather than guessed.

### Step 3 — The memory ceiling

`_capacity_bytes(device, model_dir)` returns the memory a growing cache may
claim: what the device can *address*, less the resident IR weights.

| Device | Capacity |
|---|---|
| GPU — integrated or discrete | `GPU_DEVICE_TOTAL_MEM_SIZE` − size of the IR's `*.bin` files |
| CPU | `psutil.virtual_memory().total` − size of the IR's `*.bin` files |

> **Why the plugin's figure for an integrated GPU too?** An iGPU does carve its
> memory out of system RAM, but the driver caps how much of it the GPU may
> address — 25.2 GB of 32 GB on an Arc 140T — and RAM the GPU cannot reach is
> not capacity. `DEVICE_TYPE` is never consulted; both kinds of GPU are sized
> the same way.
>
> **Why capacity and not free memory?** Because the budget decides how a lesson
> is split, and a split that changes because ASR happened to still be resident
> makes the summary of one recording irreproducible from one run to the next.
> Capacity is a property of the machine; free memory is a property of the
> moment. What free memory used to absorb is now the headroom's job — see
> below.
>
> **Why not `GPU_MEMORY_STATISTICS`?** That property only counts allocations
> made through the very `ov.Core` instance that asks. The warm `VLMPipeline`
> owns a different `Core`, so a fresh `Core` always reports zero and the
> property cannot stand in for the resident weights.

```
memory_ceiling = floor(capacity_bytes × 0.6 / bytes_per_token)
```

`GPU_MEMORY_SAFETY_MARGIN` (0.6) covers what the capacity figure does not know about:
allocator fragmentation, error in the per-token estimate, and — since the
budget no longer looks at free memory — whatever else on the machine is holding
memory at the time. On an integrated GPU that last term dominates, because ASR,
OCR and the desktop all draw on the same RAM.

**Why 0.6.** On the reference machine it leaves 12.1 GB for the cache against
14.7 GB of RAM actually free mid-session. 0.7 also fits, but only by 0.6 GB,
which is a coincidence rather than a margin:

| Headroom | KV budget | vs 14.7 GB free |
|---|---|---|
| 0.8 | 16.1 GB | over |
| 0.7 | 14.1 GB | 0.6 GB spare |
| **0.6** | **12.1 GB** | **2.6 GB spare** |
| 0.5 | 10.1 GB | 4.6 GB spare |

Lowering it costs nothing where the quality ceiling binds anyway, which is
every machine with more than about 4 GB to spare. It costs real tokens only on
a device already small enough for the half-budget cap to engage.

If the device cannot be read at all, `DEFAULT_PROMPT_TOKENS` (6000) is used.

### A backstop for a busy machine

Sizing from capacity is what makes the plan reproducible, and it is also what
makes an out-of-memory crash hard to explain: the budget cannot see that
something else took the RAM. `warn_if_short_of_memory` closes that gap without
reopening the other one — it **reports and changes nothing**, so the plan stays
stable.

Once each consumer knows its plan, it checks the largest call that plan implies
against the memory free at that moment:

| Path | Largest call |
|---|---|
| One call | transcript + single-call reserve |
| Split | largest chunk + stage reserve — the reduce call carries notes, not transcript |

Free memory is read from `psutil` for CPU and integrated GPUs, both of which
draw on system RAM. On a **discrete** GPU there is no reliable free-VRAM figure
(same reason `GPU_MEMORY_STATISTICS` is unusable above), so the check is skipped
rather than guessed at. This is the one place `DEVICE_TYPE` is still consulted,
and only because the question here really is different from the capacity one.

On the reference machine the realistic peak is 19,546 tokens — 1.68 GB against
14.7 GB free — so it stays quiet. It fires when the memory arm binds on a
machine that is busier than it was when the budget was computed.

### Step 4 — Budget

```
budget = min(max_content_tokens, memory_ceiling)
```

`budget` is the capacity of the **whole call** — prompt *and* answer. An
integer `max_prompt_tokens` overrides both arms and skips all device probing.

**Which arm binds.** On anything with more than about 3 GB to spare, quality
does. That is intentional: chunking is not a small-device feature that a large
machine gets to skip, it is how a long lesson is summarised well.

| Machine | Memory ceiling | Budget | Limited by |
|---|---|---|---|
| Arc 140T iGPU, 25.2 GB addressable, Qwen3-VL-8B int4 | 140,835 | 24,000 | quality |
| 6 GB discrete GPU, same model | 6,501 | 6,501 | memory |

There is no third arm for the model's context length
(`max_position_embeddings`). 24,000 is an order of magnitude below it on every
model shipped here — 262,144 for Qwen3-VL-8B, 128,000 for Qwen2.5-VL-3B — so it
can only bind if `max_content_tokens` is raised past the context window.

### Step 5 — Two reserves, not one

Everything in a call that is not transcript is measured and subtracted:

```
usable = budget − min(reserve, budget // 2)
```

Two different calls get sized, and they do not cost the same:

| | Sizes | Reserve | Where |
|---|---|---|---|
| **Single-call reserve** | Does the whole lesson fit in one call? And the reduce call at the end. | full instructions + board text + `max_new_tokens` (5120) | each component's `_call_overhead()` |
| **Stage reserve** | How big may one chunk be? | that component's chunk-stage prompt + its own `*_max_new_tokens` | each component's `_stage_reserve()` |

Charging every chunk for an answer it will never write makes every chunk
smaller and so makes more of them — more sequential calls, for nothing.
`plan_line_groups` therefore takes both: the first decides *whether*, the
second decides *how big*.

Both reserves are **per component**. A map call sends the summariser's map
prompt and writes a note; a window call sends *both* segmentation templates and
writes a topic list. Neither figure describes the other.

**Measured overhead (`language: zh`, Qwen3-VL-8B tokenizer, the 50-minute
lesson in the worked example below):**

| Component | Tokens |
|---|---|
| Summariser map prompt | 165 |
| Segmentation `system.txt` + `user.txt` | 316 + 116 = 432 |
| Board OCR (one lesson's blackboard) | 4,661 |
| `max_new_tokens` | 5,120 |
| `map_max_new_tokens` / `window_max_new_tokens` | 1,536 / 1,024 |
| **Summary single-call reserve** (system + board + 5,120) | **9,781** |
| **Summary stage reserve** (165 + 1,536) | **1,701** |
| **Segmentation single-call reserve** (432 + prompt fragments + 5,120) | **5,551** |
| **Segmentation stage reserve** (432 + 1,024) | **1,456** |

> **Why these are per component.** An earlier revision shared one stage reserve
> across both, as `max(map, seg system, seg user) + max(1536, 1024)` = 1,852.
> Taking the *maximum* of the templates is wrong for segmentation, which sends
> `system.txt` **and** `user.txt` — 432, not 316 — and the error was masked only
> because the shared answer term (1,536) over-covered the 1,024 a window
> actually writes. Measuring each component's own prompts removes both the
> under-reserve and the over-reserve.

These are roughly **constant** costs, so they are subtracted rather than covered
by a ratio. A ratio is the wrong shape for a fixed cost: it over-reserves on a
large budget and under-reserves on a small one, and it cannot track a board text
that varies from empty to several thousand tokens.

> **Note:** Board text is included once in the final reduce call, not in each map
> call. If it is too long for the token budget, some board content or the final
> summary may be truncated.

**The half-budget cap.** A prompt and answer that alone outgrow the device are
unsatisfiable. Without the cap, `usable` collapses toward zero and produces impractically tiny
chunks. Capping the reserve at half the budget degrades gracefully instead: the
answer may be truncated, but the plan stays sane. Reaching the cap logs a
warning naming the numbers, since it means the call is already over the
device's head.

### Step 6 — Split or not

```
one group                                       if total ≤ usable(single reserve)

cap      = usable(stage)
n_chunks = max(2, len(pack(cap)))
ceiling  = min c ∈ [ceil(total / n_chunks), cap] where len(pack(c)) ≤ n_chunks
```

Packing is greedy: lines are added until the next whole line would exceed the
ceiling, and that line starts the next chunk. `overlap_lines` (2) trailing
lines are repeated for continuity and count against the next chunk's ceiling.
Only a single line wider than the entire ceiling may exceed it, because it
cannot be split; `plan_line_groups` logs a warning in that case.

The chunk count is **measured, not predicted**: packing at the cap is the
loosest legal packing, so it yields the fewest calls. Two is the floor, because
the text is already past what one whole-lesson call holds and a single group
would send the very call the split exists to avoid.

The ceiling is then tightened back down to the smallest value that still fits
that many groups, which spreads the text evenly — a stub segment yields a thin
note that drags the reduce stage down.

> **Why search for the ceiling instead of dividing.** An earlier revision used
> `ceiling = min(cap, ceil(total / n_chunks))`, which undercounts twice over:
> every group but the first repeats `overlap_lines` lines that fill a ceiling
> without carrying new text, and greedy packing stops short of the ceiling by
> up to one line. Halving a transcript that needs two groups therefore leaves a
> remainder for a third. A real 1,225-line, 23,020-token lesson came out as
> 11,500 / 11,483 / **127** — and the log line averaged the three into a
> reassuring `~7673`. Both losses depend on the line weights, so
> `_balanced_ceiling` measures them with a binary search (group count is
> non-increasing in the ceiling) rather than trying to predict them.

## Three Transcripts, Three Plans

ASR writes the same lesson three ways, in one loop, one line per speaker turn:

| File | Rendering | Lines | Read by |
|---|---|---|---|
| `content_segmentation_transcription.txt` | `[start-end] text` | all turns | topic segmentation |
| `transcription.txt` | `Teacher: text` | all turns | summary (dialog, hybrid) |
| `teacher_transcription.txt` | `[start-end] text` | teacher only | summary (teacher) |

**Each consumer plans over the file it actually sends.** The summariser calls
`_plan_chunks` on its own input; the segmentation calls `_plan_windows` on its
own. Neither knows about the other's split.

The summariser branches on whether its own input carries timestamps —
`parse_transcript_lines` returns nothing for `transcription.txt` — so `teacher`
mode gets `[SEGMENT 3/7] 12:30-25:10` and `dialog`/`hybrid` get `[SEGMENT 3/7]`.
The index is what the reduce stage needs to keep notes in order; the final
summary carries no times at all, because `reduce_instruction.txt` explicitly
forbids mentioning segments, numbers, or time ranges.

> **Why there is no shared plan.** An earlier revision decided the split **once
> per session** over the timestamped transcript and handed the `(lo, hi)` line
> groups to both consumers, so that segment *k* and window *k* covered the same
> stretch of lesson. It was removed for two reasons.
>
> Nothing downstream cross-referenced a summary segment against a topic window,
> so the alignment bought nothing; and the plan measured the wrong text. On a
> real 50-minute lesson the timestamped rendering came to 23,020 tokens while
> the `transcription.txt` the summary actually sent came to 14,064 — a 39% gap.
> The plan therefore answered "split into 3" for a call that comfortably fitted
> in one, and the two consumers disagreed in the logs while each was internally
> correct. A single boolean cannot be right for two callers sending different
> text against different reserves.
>
> The shared plan also lent `transcription.txt` the timestamps it does not
> carry. That is the one capability lost, and it cost nothing: those times never
> reached the summary, which is forbidden from printing them.

Each consumer plans once per run, when it needs it. Nothing is cached between
them, and removing the shared layer removed duplicated work rather than adding
it: the plan used to tokenise the timestamped transcript before the summariser
tokenised its own copy anyway.

## Memory Safety Margin

`GPU_MEMORY_SAFETY_MARGIN` (0.6) converts device capacity bytes into the KV
cache memory ceiling. It protects against allocator fragmentation, estimation
error, and other processes using memory. Chunk packing has no separate margin:
it uses 100% of the usable token ceiling and moves whole lines that do not fit
into the next chunk.

## Configuration

`models.text_gen.chunking`:

| Key | Default | Description |
|---|---|---|
| `enabled` | `true` | `false` restores the exact pre-chunking behaviour: one call, no splitting |
| `max_content_tokens` | `24000` | Quality ceiling. `0` disables it, leaving the memory ceiling alone — which is the behaviour that produced 144 topics |
| `max_prompt_tokens` | `auto` | `auto` computes `min(quality, memory)`. An integer overrides both and skips all device probing |
| `gpu_memory_safety_margin` | `0.6` | Memory headroom for allocator fragmentation and concurrent processes |
| `map_max_new_tokens` | `1536` | Length cap for each per-segment note; also the answer half of the stage reserve |

`overlap_lines` is not a knob: it is `DEFAULT_OVERLAP_LINES` (2) in
`utils/text_chunker.py`. Two lines of continuity is not a per-deployment
decision, and the seam handling downstream (`topic_merge._collapse_seams`) is
tuned against it.

`models.text_gen.segmentation`:

| Key | Default | Description |
|---|---|---|
| `window_max_new_tokens` | `1024` | Length cap for each window's topic list |
| `topics_target` | `20` | Topics to aim for across the whole lesson, split into per-window quotas |
| `topics_min` / `topics_max` | `15` / `25` | Accepted band for the merged result |

There is intentionally **no** `bytes_per_token` knob, no prefill-time knob, and
no longer a separate `window_ratio`. The first is computed from the model; the
second was a per-device fit standing in for a per-model limit, and is now
`max_content_tokens`; the third set a window size by hand, which the stage
reserve now derives.

## Worked Examples

**Arc 140T iGPU, 32 GB RAM, Qwen3-VL-8B int4, 56k-token lesson, summary path,
no board text**

```
bytes/token      = 92,160
GPU addressable                                = 25.22 GB   (not the 32 GB of RAM)
capacity         = 25.22 GB − 5.07 GB weights  = 20.15 GB
memory ceiling   = 20.15 GB × 0.6 / 92,160     = 140,835 tokens
budget           = min(24,000, 140,835)        =  24,000 tokens   ← quality
single reserve   = 209 + 0 board + 5,120       =   5,329 tokens
usable (fit)                                   =  18,671 tokens
  56,000 > 18,671                              → split
stage reserve    = 165 + 1,536                 =   1,701 tokens
cap = usable (stage)                           =  22,299 tokens
n_chunks         = pack at 22,299              =       3
chunk ceiling    = smallest that still fits 3  =  18,688 tokens
  → 18,676 / 18,685 / 18,688
```

The segmentation would size the same lesson with its own pair — 5,551 and
1,456 — and can land on a different number of windows. That is expected: it
sends a different rendering of the lesson.

The ceiling lands 21 tokens above `⌈56,000/3⌉`; that difference is the two
seams' repeated lines plus the greedy shortfall. Dividing instead would pack
this lesson into **four** groups, the last of them 95 tokens.

The same lesson under the memory ceiling alone comes out as one call. The
42,797-token longest recording in the corpus below comes out as 2.

**Discrete GPU, 6 GB VRAM, same model**

```
weights on disk                                =  5.07 GB
capacity         = 6 GB − 5.07 GB              =  0.93 GB
memory ceiling   = 0.93 GB × 0.6 / 92,160      =   6,501 tokens
budget           = min(24,000, 6,501)          =   6,501 tokens   ← memory
single reserve   = 5,386, capped at 6,501 // 2 =   3,250 tokens
usable (fit)                                   =   3,251 tokens
```

Here the cap engages and logs, which is the signal that `max_new_tokens: 5120`
is too large for this device. Long answers may be truncated.

**What that means for real lessons.** Measured across 57 recorded transcripts in
`storage/smart-classroom`:

| | Tokens |
|---|---|
| Shortest | 245 |
| Median | 1,622 |
| Longest | 42,797 |

Under the memory ceiling alone the 16 GB machine split **none** of these — the
42,797-token lesson went in one call, which is the failure this feature exists
to prevent. With the quality ceiling it splits the ones that need it on every
machine, and still leaves the median 1,622-token lesson in a single call.

## Reading the Logs

Three INFO lines trace the chain, and each consumer emits its own:

```
KV cache on GPU: 36 layers x 8 kv-heads x 128 dims x 1B = 92160 bytes/token.
Prompt budget on GPU: 24000 tokens (limited by quality).
Split 4210 lines (38122 tokens) into 2 segments of 19068-19069 tokens (ceiling 19069).
```

The bracketed reason on the budget line is `quality`, `memory`, `set
explicitly`, or `default` when the device could not be read — in which case a
warning naming the failure precedes it.

The split line reports the **smallest and largest** piece, not an average, so a
stub is visible as a low first number. Expect the two to sit within a line's
width of the ceiling. The label is `segment` for the summary and `window` for
the segmentation, so the two are told apart by that word alone.

The split line appears **only when that consumer splits**. Its absence after a
budget line means the lesson fit in one call — and because the two consumers
size themselves independently, one may split while the other does not.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Could not size the KV cache from ...` | The IR directory has no readable `config.json`; the 96 KB fallback is in use. Re-export the model |
| Budget line says `limited by default` | The device could not be probed; 6000 tokens assumed. Check the preceding warning |
| A long lesson is *not* split | `max_content_tokens` is `0` or set high, or `enabled: false`. Check the budget line's bracketed reason |
| A short transcript is split anyway | The reserve dominates a small budget. Check the board OCR size and `max_new_tokens`; a `capping the reserve` warning confirms it |
| `Largest segment is N tokens against the M that fit` | One transcript line is longer than a chunk may be. Usually an ASR turn that never got a boundary; shorten that source line if it recurs |
| `Notes still hold N tokens ... after 2 fold round(s)` | Too many segments for two rounds of folding to compress. Lower `map_max_new_tokens` |
| The summary splits but the segmentation does not, or vice versa | Expected. Each is sized against the text it sends and the answer it writes; the summary's board OCR alone can be several thousand tokens the segmentation never pays for |
| Summary segment headers have no `mm:ss` | Expected in `dialog` and `hybrid` mode: `transcription.txt` carries no timestamps. `teacher` mode reads a timestamped file and keeps them |
| `Transcript carries no timestamps; segmenting in one call.` | The segmentation's input lost its `[start-end]` prefixes, so it cannot be windowed. Check the ASR writer |
| `... needs N tokens of KV cache (X GB) ... but only Y GB is free right now` | The backstop. The machine got busier than it was when the budget was computed. Nothing was changed; the call may still succeed. If it does not, lower `GPU_MEMORY_SAFETY_MARGIN` or close what else is running |
| Out of memory despite the budget | As above, but with no warning first — so either the device is discrete (where free VRAM cannot be read) or the shortfall is in something other than KV cache. Check the budget line's bracketed reason: if it says `quality`, memory was never the constraint |
