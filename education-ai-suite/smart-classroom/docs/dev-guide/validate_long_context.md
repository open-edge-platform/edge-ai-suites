# Long-Context Capacity Validator

`components/llm/context_validation/` is a standalone diagnostic tool that answers one
question: **for a given summarizer model, how many tokens of context can this machine's
hardware (primarily the Intel iGPU) prefill and decode within an explicit latency SLA,
and is that enough to meet the customer's 160K-token requirement?**

It is **not** part of the runtime pipeline. `pipeline.py` / `SummarizerComponent` never import
it, and it reads its own bundled
[`config.yaml`](../../components/llm/context_validation/config.yaml) next to the script —
never `smart-classroom/config.yaml`. Editing either file has no effect on the other: this is a
capacity-planning script you run manually before committing to a model choice, or whenever you
change device / weight format / hardware, and it can't drift the production config or be
affected by changes to it.

```
components/llm/context_validation/
  config.yaml                      # this tool's own config -- see §3
  context_builder.py               # synthetic transcript construction (exact token size)
  trial_runner.py                  # runs ONE (model, context length) trial, in a subprocess
  validate_long_context.py         # CLI orchestrator: stepping loop, reporting
  setup_env.ps1                    # prepares the backend venv (one-time)
  run_validate_long_context.ps1    # one-command launcher -- see §5
```

## 1. Purpose

`smart-classroom/config.yaml`'s `models.summarizer.name` lets you swap between candidate
OpenVINO models (`Qwen/Qwen3-8B`, `Qwen/Qwen3.6-35B-A3B`, `Qwen/Qwen3.5-9B`, ...), but swapping
the name alone doesn't tell you whether that model will actually survive a 160K-token classroom
transcript on the target machine. The model advertises a long context (160K); whether *this box*
can load it and prefill + decode a prompt that large **without exhausting the memory the iGPU can
allocate** is a property of the hardware, not the model — and that is exactly what this tool
measures.

This mirrors the reference harness in `refer/long_context`: the transcript content is irrelevant
to the check, only the token *volume* matters. The tool sweeps context length per model and
reports the largest size the hardware can sustain (load + prefill + decode a few tokens) before
it runs out of resources, hangs, or becomes too slow to be operationally useful. This matters on
shared-memory iGPUs: memory pressure can cause severe paging/thrashing without producing a clean
OOM, so "eventually returned one token" is not a meaningful capacity result.

> **Scope — capacity, not answer quality.** This tool deliberately does **not** score whether the
> model *understood* the long context (e.g. a needle-in-a-haystack recall test). Earlier revisions
> tried that with grammar-constrained decoding, but on some models the constrained decoder
> collapsed into garbage output (`!!!!`) and produced a *false* FAIL for a context the hardware
> had actually handled fine. A capacity check is simple, robust, and answers the question that
> actually blocks deployment ("does it fit on this box?"). Validate answer quality separately
> against a couple of real long transcripts before shipping (§8).

## 2. Quick start

```powershell
# From anywhere -- prepares the venv on first use, then runs the sweep
.\components\llm\context_validation\run_validate_long_context.ps1
```

That's the whole thing. See §5 for more commands (custom steps, `--dry-run`, etc.) and §4 if
you'd rather manage the Python environment yourself.

## 3. Design & Methodology

### 3.1 What one trial does

At each context length being tested, the tool builds a synthetic classroom transcript
(`TEACHER:` / `STUDENT_NN:` dialog lines) sized to the target token count using the *model's own
tokenizer*, wraps it in the chat template (system prompt + transcript as the user turn), then:

1. **Loads** the model fresh (records load time, or a load failure / OOM).
2. **Prefills** the full prompt and **decodes** up to `probe_tokens` tokens (default 64) with
  plain greedy decoding. The transcript and final task are explicitly delimited so truncated
  synthetic input still gives the model a meaningful instruction.
3. **Validates** that decoded output is non-empty natural-language content, rejecting output
  made only of special tokens, control characters, punctuation, or one repeated character.
4. **Passes** unless generation fails or both capacity-pressure signals occur together: the
  complete `generate()` call exceeds `max_generate_time_sec` (default 600s) **and** sampled GPU
  memory reaches `gpu_memory_pressure_pct` (default 90% of system RAM). OOM, crash, hard trial
  timeout, and invalid output remain unconditional failures.

The console and CSV also report `tokens_per_second = generated_tokens / generate_time_s`. This is
an **effective end-to-end output rate that includes prefill**, not pure decode throughput. Models
may stop before `probe_tokens` when they emit EOS; the wall-clock SLA is therefore the stable
policy signal, while tok/s is diagnostic context.

`probe_tokens` is small on purpose: proving the box can hold a context size only needs a few
decode steps, not a full summary — generating thousands of tokens at 128K+ context would add
many minutes per step for no extra capacity signal. See
[`context_builder.py`](../../components/llm/context_validation/context_builder.py) and
[`trial_runner.py`](../../components/llm/context_validation/trial_runner.py).

### 3.1.1 Memory breakdown: weights vs. KV-cache

The core signal on hardware where the iGPU shares system RAM is *where the memory went*, so each
trial reports it split three ways:

- **Weights** — the RAM/GPU footprint measured the instant the model finishes loading, before any
  prefill. This is roughly constant across context sizes for a given model/weight-format, and is
  cross-checked against the on-disk IR weight size (`weights on disk`, the summed `.bin` bytes).
- **KV-cache** — the *additional* memory the peak reaches during prefill+decode, on top of the
  loaded weights. This is what grows with context length and is what eventually exhausts the box.
- **Peak** — the total high-water mark (weights + KV + everything else), i.e. how close the trial
  came to the hardware limit.

The child subprocess signals two milestones over its result queue — `loaded` (weights resident)
and `done` (trial finished) — and the orchestrator snapshots system memory at the `loaded`
milestone and tracks the running peak throughout, so weights (post-load delta from a pre-spawn
baseline) and KV-cache (peak minus post-load) fall straight out of those two snapshots. Sampling
in the *parent* rather than the child is deliberate: system RAM/GPU counters are process-wide, so
the parent sees the child's footprint just as well, and — crucially — its readings **survive even
when the child is killed on a timeout**, which is exactly the case where memory matters most (the
box was thrashing on a context it couldn't hold, not sitting idle). RAM comes from `psutil`; GPU
is best-effort and Windows-only via the repo's perf-counter collector (reads `0.0` elsewhere).

### 3.2 One subprocess per trial

Each (model, context length) trial loads the model fresh in its own `multiprocessing` child
process, runs its probe, reports a result dict over a queue, and exits. This mirrors the existing
"run conversion in a subprocess so memory is fully reclaimed on exit" pattern already used for
model conversion in
[`components/vlm/vlm_openvino_serving/utils/utils.py::_convert_model_worker`](../../components/vlm/vlm_openvino_serving/utils/utils.py).
It matters here for two reasons:

- **Clean memory state.** iGPU memory on this hardware is shared with system RAM; a leak or
  fragmentation carried over from one trial could make the *next* trial fail for reasons
  unrelated to that model/size.
- **Crash containment.** A hard OOM/driver crash at, say, 224K tokens kills only that trial's
  process — the orchestrator (`validate_long_context.py`) detects the dead process, records the
  failure, and moves on instead of taking down the whole sweep.

The orchestrator polls the result queue every 2 seconds up to `trial_timeout_sec` (default
1200s); if the process dies without reporting a result it's classified `crashed`, and if it's
still alive at the deadline it's terminated and classified `timeout`. This hard timeout protects
the sweep from a hung process. It is intentionally separate from `max_generate_time_sec`: a
trial that completes after the operational SLA is recorded as `too_slow`, with its real timing
and memory high-water marks intact.

### 3.3 Stepping strategy

For each candidate model, `context_steps_tokens` (default `[8000, 16000, 32000, 48000, 64000,
96000, 128000, 144000, 160000, 176000, 192000, 224000, 256000]`) is walked in ascending order.
The **first step that fails** (OOM, crash, timeout, or no output) stops the sweep for that model —
the max stable context is the last step that passed. This assumes capacity degrades monotonically
with size, which holds in practice for memory exhaustion.

Pass `--refine` to bisect up to 3 extra points between the last pass and the first failure,
tightening the reported ceiling instead of only reporting one of the configured step values.

### 3.4 Model preparation is explicit, not automatic

The tool requires each candidate model to already be converted to OpenVINO IR on disk. If the
IR is missing it fails fast for that model and prints the exact `optimum-cli` command to
prepare it, rather than auto-downloading/converting mid-sweep. Given `Qwen/Qwen3.6-35B-A3B`-class
models can mean tens of GB and a long export time, silently kicking that off in the middle of a
context sweep would make run time unpredictable. Prepare all candidates up front instead.

### 3.5 Plain LLM vs. multimodal (VLM) export auto-detection

`optimum-cli export openvino` picks the export layout from the model's own architecture, not
from anything this tool tells it: a plain causal LM exports as a single
`openvino_model.xml`/`.bin` pair, while a multimodal/VLM model (as all three default candidates
are) exports as several components — `openvino_language_model.xml`, `openvino_text_embeddings_model.xml`,
`openvino_vision_embeddings_model.xml`, etc. — the same layout
[`components/vlm/text_gen_vlm.py`](../../components/vlm/text_gen_vlm.py) loads for the production
warm VLM. `trial_runner.py` checks which layout is on disk and loads it with the matching
`ov_genai.LLMPipeline` or `ov_genai.VLMPipeline` accordingly (both expose the same
`.generate(prompt, generation_config=...)` call used for probing here); `_ir_ready()` in
`validate_long_context.py` recognizes either layout too (mirroring
[`content_search/providers/utils/model_utils.py::is_model_ready`](../../content_search/providers/utils/model_utils.py)),
so a converted multimodal model is never misreported as a missing IR.

### 3.6 Tokenizer-loading quirks in raw `optimum-cli` exports

The tokenizer is used only to size the prompt and count tokens; the model's own
`openvino_tokenizer.xml` handles real inference. A tokenizer converted by `optimum-cli export
openvino` directly (as this tool's Prerequisites recommend) can differ from one converted by the
project's own `convert_model()` helper in two ways that trip up a plain
`AutoTokenizer.from_pretrained(model_dir)` call:

- `tokenizer_config.json`'s `extra_special_tokens` is written as a list where transformers
  expects a dict (`AttributeError: 'list' object has no attribute 'keys'`) -- the same issue
  [`components/vlm/text_gen_vlm.py::VLMTextGen._load`](../../components/vlm/text_gen_vlm.py) already
  works around for production.
- `tokenizer_config.json`'s declared `tokenizer_class` can name something
  `AutoTokenizer` doesn't recognize (e.g. `TokenizersBackend`, seen on a real int8 VLM export),
  raising `ValueError: Tokenizer class ... does not exist or is not currently imported.` even
  though `tokenizer.json` is a perfectly valid fast-tokenizer file.

`trial_runner.py::_load_tokenizer` tries `AutoTokenizer` and, on either failure, falls back to
loading `PreTrainedTokenizerFast` directly (which doesn't need to resolve a class name) — trying
both with and without the `extra_special_tokens` override, so whichever quirk (if any) is present
in a given export is handled without needing to know in advance which one it is. This fallback
makes transformers log a "tokenizer class you load ... is not the same type as the class this
function is called from" warning; it is harmless here (the tokenizer is only used for prompt
sizing, not inference), so `_load_tokenizer` sets transformers' log level to error to silence it —
otherwise it would repeat three lines for **every** trial's fresh subprocess and bury the actual
results.

### 3.7 Keeping the console log clean

Two sources of benign native noise are suppressed so the sweep log shows just the per-trial
results:

- **The tokenizer fallback warning** (above) — silenced via transformers' log level in
  `_load_tokenizer`, once per subprocess.
- `Win32 exception occurred releasing IUnknown at 0x...` — COM-teardown noise emitted by the
  Windows WMI/`pythoncom` layer in [`utils/platform_info.py`](../../utils/platform_info.py) while
  it collects the hardware fingerprint. It comes from the native COM layer, not Python's
  logging/warnings, so `validate_long_context.py` wraps only that best-effort call in an fd-level
  stderr redirect (`_suppress_native_stderr`) to hide it. It never affected the sweep; this just
  removes the distraction.

## 4. Configuration reference

The tool has its own config file,
[`components/llm/context_validation/config.yaml`](../../components/llm/context_validation/config.yaml),
loaded by default (resolved relative to the script's own location, not the current directory).
It is a standalone copy — `provider` / `device` / `weight_format` / `models_base_path` start out
matching `smart-classroom/config.yaml`'s `models.summarizer` section, but the two are not linked:
changing one does not change the other. If you update the production summarizer's device or
weight format, update this file's copies too if you want the sweep to stay representative of
what's actually deployed. Any key can also be overridden per-run via CLI flags without editing
either file.

```yaml
summarizer:
  provider: openvino
  device: GPU
  weight_format: int8
  models_base_path: "models"
  long_context_validation:
    candidate_models:
      - Qwen/Qwen3-8B
      - Qwen/Qwen3.6-35B-A3B
      - Qwen/Qwen3.5-9B
    target_context_tokens: 160000
    context_steps_tokens: [8000, 16000, 32000, 48000, 64000, 96000, 128000, 144000, 160000, 176000, 192000, 224000, 256000]
    probe_tokens: 64
    max_generate_time_sec: 600
    gpu_memory_pressure_pct: 90
    trial_timeout_sec: 1200
    output_dir: monitoring/executionlogs/long_context_validation
```

| Key | Meaning |
|---|---|
| `provider` / `device` / `weight_format` | How to load each candidate model — mirrors `models.summarizer` in the main config, but is an independent copy. |
| `models_base_path` | Where converted model IRs live, resolved relative to the `smart-classroom/` working directory (same convention as production). |
| `candidate_models` | Model names to sweep (HuggingFace repo id form). |
| `target_context_tokens` | The customer requirement to check the ceiling against (160K). |
| `context_steps_tokens` | Ascending token sizes to probe. |
| `probe_tokens` | Tokens to decode per trial. Small on purpose — a capacity check only needs a few decode steps (default 64). |
| `max_generate_time_sec` | Soft time limit for the full prefill + probe `generate()` call (default 600s). It produces `too_slow` only together with GPU memory pressure. |
| `gpu_memory_pressure_pct` | Practical shared-iGPU memory pressure line, measured as peak GPU usage divided by total system RAM (default 90%). It is combined with the soft time limit rather than treated as an independent failure. |
| `trial_timeout_sec` | Hard per-trial wall-clock budget before the subprocess is killed. Keep this above `max_generate_time_sec` so slow trials can return diagnostics. |
| `output_dir` | Where `trials.csv` / `summary.json` / `summary.md` are written (relative to `smart-classroom/`). |

## 5. Prerequisites & setup

Everything below is handled automatically by
[`run_validate_long_context.ps1`](../../components/llm/context_validation/run_validate_long_context.ps1)
(§6) — read this section if you want to understand what it's doing, run the tool without the
launcher, or troubleshoot.

1. **A Python environment with the project's `requirements.txt` installed** (OpenVINO GenAI,
   optimum-intel, transformers, torch, psutil) — **not** whatever `python` resolves to on `PATH`,
   which is the single most common way to hit "it doesn't run". This tool reuses the exact same
   backend venv `setup-smart-classroom.ps1` / `start-smart-classroom.ps1` use: created at
   `../smartclassroom` (sibling of `smart-classroom/`, no hyphen), activated with
   `Scripts\Activate.ps1` before launching `python`.
   - **Already ran `setup-smart-classroom.ps1`?** That venv already exists; nothing more to do.
   - **Haven't, or just want this tool working on its own?** Run this tool's own
     [`setup_env.ps1`](../../components/llm/context_validation/setup_env.ps1) once — it
     creates/reuses that exact same venv and `pip install`s `requirements.txt` into it, without
     running the full interactive `setup-smart-classroom.ps1` (which also sets up the frontend
     and content_search, unrelated to this tool) and without touching
     `smart-classroom/config.yaml`. Safe to re-run any time — it detects an existing venv and
     just verifies/updates packages.
     ```powershell
     .\components\llm\context_validation\setup_env.ps1
     ```
   - Either way, the tool also checks for this itself before starting a real sweep (not under
     `--dry-run`) and prints the exact venv path / setup command to fix it with if
     `openvino_genai` / `transformers` aren't importable in whatever interpreter you used,
     rather than letting every trial in the sweep fail on the same missing import.
2. **Each candidate model converted to OpenVINO IR** under
   `<models_base_path>/<provider>/<model_name_with_slashes_replaced>_<weight_format>/` — the
   same layout `utils/ensure_model.py::get_model_path()` uses for the production summarizer
   model. For example:
   ```bash
   optimum-cli export openvino --model "Qwen/Qwen3-8B" --trust-remote-code --weight-format int4 "models/openvino/Qwen_Qwen3-8B_int4"
   ```
   Repeat per candidate model / weight format you want to test. The tool prints this exact
   command (with the right path filled in) whenever it detects a missing IR, so you don't have
   to compute the path by hand.

If PowerShell blocks either `.ps1` script with an UnauthorizedAccess/SecurityError:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

## 6. Usage

**Simplest path** — run from anywhere; it finds `smart-classroom/` and the backend venv
relative to its own location, preparing the venv on first use if needed:

```powershell
.\components\llm\context_validation\run_validate_long_context.ps1
```

Any extra arguments are forwarded to `validate_long_context.py` as-is:

```powershell
# Exercise the sweep/report pipeline itself with no OpenVINO/GPU required
.\components\llm\context_validation\run_validate_long_context.ps1 --dry-run

# Tighten the reported ceiling with a bounded bisection near the pass/fail boundary
.\components\llm\context_validation\run_validate_long_context.ps1 --refine

# Test one model only, with a custom step list
.\components\llm\context_validation\run_validate_long_context.ps1 --models Qwen/Qwen3-8B --steps 32000 64000 128000 160000 192000

# Test the same model at a different device/weight_format without editing any config file
.\components\llm\context_validation\run_validate_long_context.ps1 --models Qwen/Qwen3-8B --weight-format int8 --device GPU

# Adjust either half of the combined time + GPU-memory pressure policy
.\components\llm\context_validation\run_validate_long_context.ps1 --max-generate-time-sec 900 --gpu-memory-pressure-pct 92

# Point at a different config file entirely (e.g. a scratch copy for one-off experiments)
.\components\llm\context_validation\run_validate_long_context.ps1 --config C:\path\to\other.yaml
```

**If you already have the right interpreter active** (see §5), the launcher is just a
convenience wrapper around, run from `smart-classroom/`:

```bash
python -m components.llm.context_validation.validate_long_context [same arguments as above]
```

Console output streams one line per trial as it happens, with the memory split into weights vs.
KV-cache (§3.1.1):

```
=== Qwen/Qwen3-8B ===  weights on disk: 8.5 GB (int8)
[Qwen/Qwen3-8B]     8,000 tok -> PASS  |  load 12.3s, gen 3.1s (64 tok, 20.65 tok/s)  |  peak RAM 12.4 GB (weights +8.6, kv +1.8)  |  peak GPU 10.1 GB (weights +8.5, kv +1.6)
...
[Qwen/Qwen3-8B]   160,000 tok -> PASS  |  load 12.1s, gen 9.4s (64 tok, 6.81 tok/s)  |  peak RAM 58.1 GB (weights +8.6, kv +47.5)  |  peak GPU 21.4 GB (weights +8.5, kv +12.9)
[Qwen/Qwen3-8B]   176,000 tok -> FAIL (timeout)  |  load 12.4s  |  peak RAM 63.9 GB (weights +8.6, kv +53.3)  |  peak GPU 22.1 GB  |  error=timeout
```

Because memory is sampled by the orchestrator, the failing row still reports the peak the box
reached (here ~64 GB RAM — the machine was thrashing, which is why it timed out rather than
raising a clean OOM), instead of dropping to zeros when the trial subprocess is killed.

## 7. Interpreting the report

Three files land in `output_dir`:

- **`trials.csv`** — one row per trial, written immediately after each trial completes (so a
  crash mid-sweep doesn't lose earlier results): model, tokens requested, device, weight_format,
  load/generate success, prompt/generated tokens, load & generate time, effective
  `tokens_per_second`, the configured `max_generate_time_sec`, and the memory breakdown
  (`weight_disk_gb`, `weight_ram_gb`/`weight_gpu_gb`, `kv_ram_gb`/`kv_gpu_gb`,
  `peak_ram_gb`/`peak_ram_pct`/`peak_gpu_gb`), a `status` (`PASS` or the failure reason), and the
  raw `error` string.
- **`summary.json`** — machine-readable rollup per model: `max_stable_context`,
  `meets_target` (bool, compared against `target_context_tokens`), the memory breakdown at that
  max stable size (`weight_disk_gb`, `weight_ram_gb`/`weight_gpu_gb`, `kv_ram_gb`/`kv_gpu_gb`,
  `peak_ram_gb`/`peak_gpu_gb`), `failure_reason`, and the hardware fingerprint the sweep ran on
  (from `utils/platform_info.py`).
- **`summary.md`** — the same rollup as a table (memory measured at the max stable context;
  weights = footprint just after load, KV = extra memory prefill+decode added on top), e.g.:

  | Model | Device | Weight | Max stable context | Meets target | Weights (disk) | Peak RAM | KV RAM | Peak GPU | KV GPU | Notes |
  |---|---|---|---|---|---|---|---|---|---|---|
  | Qwen/Qwen3-8B | GPU | int4 | 160,000 | PASS | 4.6 GB | 58.1 GB | 47.5 GB | 21.4 GB | 12.9 GB | reached top configured step without failing |
  | Qwen/Qwen3.6-35B-A3B | GPU | int4 | 64,000 | FAIL | 18.2 GB | 63.6 GB | 20.1 GB | 58.4 GB | 21.4 GB | capped by timeout |

`failure_reason` values: `oom`, `timeout`, `crashed`, `load_error`, `generate_error`,
`no_output`, `too_slow`. A model whose max stable context still meets the target can show a failure reason
too — it just means the sweep found the *next* configured step above the target failed for that
reason, which is still useful context for headroom planning.

### 7.1 Conclusion for the supplied int8 / iGPU / 64 GB run

The earlier 120-second-only policy established **48,000 tokens as the maximum supported context
among the completed steps** for `Qwen/Qwen3.6-35B-A3B` int8 on one measured platform:

| Context | Generate time | Output | Result under 120s SLA |
|---:|---:|---:|---|
| 32,000 | 31.7s | 64 tokens | PASS |
| 48,000 | 50.7s | 64 tokens | PASS |
| 64,000 | 254.4s | 10 tokens | FAIL (`too_slow`) |
| 68,000 | 288.7s | 10 tokens | FAIL (`too_slow`) |
| 72,000 | 328.3s | 10 tokens | FAIL (`too_slow`) |
| 80,000 | 405.2s | 10 tokens | FAIL (`too_slow`) |

Under the current combined policy these historical timings must be re-run: a trial is capped by
`too_slow` only when its measured GPU peak also crosses the configured pressure line. The sharp
timing jump remains useful evidence of paging/thrashing, but old rows do not contain the new
`peak_gpu_pct` / `gpu_memory_at_limit` decision fields. Conclusions remain specific to the model,
weight format, device, driver, system memory, time budget, and pressure threshold used in a run.

## 8. Hardware caveats

- **Windows iGPU shares system memory.** Unlike a discrete GPU with dedicated VRAM, the Intel
  iGPU's usable memory is bounded by how much the OS/driver lets it allocate. If a model that
  should plausibly fit still hits an OOM-classified failure, first try increasing the dedicated
  GPU memory allocation in **Intel® Graphics Software → Graphics tab**, per the existing
  troubleshooting note for `CL_OUT_OF_RESOURCES` in
  [`advance-setup-guide.md`](../user-guide/advance-setup-guide.md#troubleshooting), before
  concluding the model can't reach the target.
- **`weight_format` trades memory for capacity.** `int4` leaves the most headroom for a large
  KV-cache (longer max context) than `int8` or `fp16` at the same context length. If a model OOMs
  below the target, re-run with a lower-precision `weight_format` before ruling it out.
- **Large candidates cost real disk/RAM even to attempt.** `Qwen/Qwen3.6-35B-A3B`-class models
  need substantial disk space for the IR and host RAM just to load, independent of how far the
  context sweep gets.
- **Each step reloads the model from scratch, on purpose (§3.2).** For a 30B+-class model,
  loading is roughly a minute per step on real hardware. Prefill at 128K+ tokens is itself slow,
  so a full 13-step sweep is a real commitment of time for large candidates, not a five-minute
  check; pass a shorter custom `--steps` list while iterating.
- **Capacity is not answer quality.** A PASS means the hardware can hold and decode that context
  size within the configured latency SLA — not that the model produces a good summary of it. Validate the winning model/size
  combination against a couple of real long transcripts before shipping.

## 9. Limitations

- This is a hardware-capacity probe, not a comprehension test: it confirms the box can prefill and
  decode a context of size N, not that the model still *uses* facts stated far back in it. If you
  need to check long-range recall quality, do it separately against real transcripts.
- The stepping strategy assumes monotonic degradation (a fail at N is assumed to persist for all
  sizes above N). If a model's behavior is non-monotonic, re-run with a denser custom `--steps`
  list around the suspect region.
- `--refine` adds at most 3 extra trials per model — it narrows the reported boundary, it
  doesn't binary-search to token-level precision.
- Peak GPU memory sampling is best-effort and Windows-only (via the repo's perf-counter
  collector); on other platforms, or if the counter is unavailable, the GPU column reads `0.0`
  and only RAM is reported.
```
