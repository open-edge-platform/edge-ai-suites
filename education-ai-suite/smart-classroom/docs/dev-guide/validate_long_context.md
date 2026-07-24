# Long-Context Capacity Validator

`components/llm/context_validation/` is a standalone diagnostic tool that answers one
question: **for a given summarizer model, how many tokens of context can this machine's
hardware (primarily the Intel iGPU) actually handle, and is that enough to meet the
customer's 160K-token requirement?**

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
  haystack_builder.py              # synthetic transcript + needle construction
  trial_runner.py                  # runs ONE (model, context length) trial, in a subprocess
  validate_long_context.py         # CLI orchestrator: stepping loop, reporting
  setup_env.ps1                    # prepares the backend venv (one-time)
  run_validate_long_context.ps1    # one-command launcher -- see §5
```

## 1. Purpose

`smart-classroom/config.yaml`'s `models.summarizer.name` lets you swap between candidate
OpenVINO models (`Qwen/Qwen3-8B`, `Qwen/Qwen3.6-35B-A3B`, `Qwen/Qwen3.5-9B`, ...), but swapping
the name alone doesn't tell you whether that model will actually survive a 160K-token classroom
transcript on the target machine. Two independent things can go wrong at long context:

1. **It runs out of resources.** OpenVINO's GPU plugin raises an error (commonly containing
   `"out of gpu resources"` / `CL_OUT_OF_RESOURCES`) once the KV-cache no longer fits in the
   memory the iGPU can allocate.
2. **It "forgets."** Even when a model loads and generates without error at a huge context
   size, it may stop reliably using facts stated far back in the transcript — the output still
   looks plausible, just wrong. A pure smoke test ("did it crash?") won't catch this.

This tool sweeps context length per model and reports the largest size that is both stable
(no crash/OOM/timeout) **and** accurate (the model still recalls a planted fact), so a
160K-token requirement can be checked against fact rather than assumption.

## 2. Quick start

```powershell
# From anywhere -- prepares the venv on first use, then runs the sweep
.\components\llm\context_validation\run_validate_long_context.ps1
```

That's the whole thing. See §5 for more commands (custom steps, `--dry-run`, etc.) and §4 if
you'd rather manage the Python environment yourself.

## 3. Design & Methodology

### 3.1 Needle-in-a-haystack accuracy probe

At each context length being tested, the tool builds a synthetic classroom transcript
(`TEACHER:` / `STUDENT_NN:` lines cycling through ~15 generic subjects, so it doesn't
degenerate into repeated text at 100K+ tokens) sized to the target token count using the
*model's own tokenizer*. One sentence — the **needle** — plants a fresh, randomly generated
6-digit access code at a controlled relative depth (10% / 50% / 90% into the transcript by
default). A closing question asks the model to recall that code. The answer is scored correct
if it contains the planted code. See
[`haystack_builder.py`](../../components/llm/context_validation/haystack_builder.py).

Three probes (one per depth) are run per context length so a single lucky/unlucky retrieval
doesn't decide the result; `accuracy_threshold` (default `0.8`) is the fraction of probes that
must succeed for that context length to count as a pass. A fresh random code is generated every
run, so a model can't "cheat" by recalling a code memorized during training. The code is
digits-only, not mixed alphanumeric — real-hardware testing showed a mixed code (e.g. `X7S89U`)
let a model locate the right spot in the transcript but sometimes reproduce it imprecisely
(quoting `46AX` for planted code `46AXE7`), registering a false "wrong" verdict that was really
a tokenization artifact. Digit runs tokenize more predictably. This mirrors standard practice in
needle-in-haystack benchmarks.

### 3.2 One subprocess per trial

Each (model, context length) trial loads the model fresh in its own `multiprocessing` child
process, runs its probes, reports a result dict over a queue, and exits. This mirrors the
existing "run conversion in a subprocess so memory is fully reclaimed on exit" pattern already
used for model conversion in
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
still alive at the deadline it's terminated and classified `timeout`.

### 3.3 Stepping strategy

For each candidate model, `context_steps_tokens` (default `[8000, 16000, 32000, 48000, 64000,
96000, 128000, 144000, 160000, 176000, 192000, 224000, 256000]`) is walked in ascending order.
The **first step that fails** (OOM, crash, timeout, or accuracy below threshold) stops the
sweep for that model — the max stable context is the last step that passed. This assumes
capability degrades monotonically with size, which holds in practice for both memory
exhaustion and needle-recall accuracy.

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

A tokenizer converted by `optimum-cli export openvino` directly (as this tool's Prerequisites
recommend) can differ from one converted by the project's own `convert_model()` helper in two
ways that trip up a plain `AutoTokenizer.from_pretrained(model_dir)` call:

- `tokenizer_config.json`'s `extra_special_tokens` is written as a list where transformers
  expects a dict (`AttributeError: 'list' object has no attribute 'keys'`) -- the same issue
  [`components/vlm/text_gen_vlm.py::VLMTextGen._load`](../../components/vlm/text_gen_vlm.py) already
  works around for production.
- `tokenizer_config.json`'s declared `tokenizer_class` can name something
  `AutoTokenizer` doesn't recognize (e.g. `TokenizersBackend`, seen on a real int8 VLM export),
  raising `ValueError: Tokenizer class ... does not exist or is not currently imported.` even
  though `tokenizer.json` is a perfectly valid fast-tokenizer file and `chat_template.jinja`
  is present alongside it.

`trial_runner.py::_load_tokenizer` tries `AutoTokenizer` and, on either failure, falls back to
loading `PreTrainedTokenizerFast` directly (which doesn't need to resolve a class name) — trying
both with and without the `extra_special_tokens` override, so whichever quirk (if any) is present
in a given export is handled without needing to know in advance which one it is. A "tokenizer
class you load ... is not the same type as the class this function is called from" warning from
transformers during this fallback is expected and harmless.

### 3.7 Answers are grammar-constrained, not free-form

This is the part that took the most real-hardware iteration to get right, so it's worth
explaining the failed attempts, not just the final answer.

**Attempt 1: free-form generation, ask nicely for a short answer.** Pure greedy decoding
(`do_sample=False`, matching production's `temperature=0.0` default) fell into a degenerate
repetition loop on this tool's synthetic, template-cycling transcript — the model repeated
"...then read the full classroom transcript, then read the full classroom transcript..."
hundreds of times instead of ever answering.

**Attempt 2: low-temperature sampling to escape the loop.** This worked for the loop, but
uncovered a second, more stubborn problem: some models are extremely verbose about "thinking
out loud" before answering, regardless of `/no_think`, `enable_thinking=False`, and explicit
"reply with ONLY the code, no preamble" instructions in the prompt. Real testing against a
35B-class multimodal candidate showed responses opening with "Here's a thinking process: 1.
Analyze the request... 2. ..." and similar, sometimes never reaching the code within
`max_new_tokens_probe` tokens at all, no matter how large that budget was set (1024+ tokens
still wasn't always enough). `repetition_penalty` / `no_repeat_ngram_size` are **not** a fix
for the loop either: both penalize or forbid reproducing any n-gram already seen in the
*input*, which actively suppresses the model from quoting the planted code back verbatim —
exactly what the probe needs it to do (observed: the model started dropping and garbling words
from the transcript it was supposed to quote).

**Attempt 3: grammar-constrained structured output, small preamble budget.**
`ov_genai.GenerationConfig` supports `structured_output_config`, which constrains every
generated token to keep the output consistent with a regex — this makes "narrate indefinitely
instead of answering" structurally impossible, not just discouraged by instructions.
`regex=r"[\s\S]{0,N}\d{6}"` (a bounded free-text lead-in, then the answer must end in the
6-digit code) guarantees the generation always ends in a clean, parseable digit sequence
instead of rambling indefinitely or being cut off mid-thought with no answer at all. But at a
small bound (200-400 chars, a few seconds to a minute per probe), two different candidate
models — a 35B-class multimodal one and a 9B one, ruling out this being specific to either —
both reliably produced the *same* shape of wrong answer: the entire budget spent on a numbered
"1. Analyze the Request: ... 2. Scan the Transcript for Keywords: ..." reasoning scaffold that
never got past its own setup, cut off before reaching the transcript content at all, followed by
a generic, unconditioned-looking guess (`100000`, `123456`, `202405`).

**Attempt 4 (current): a much larger preamble budget.** The failure above looks like being cut
off mid-scaffold, not a capability ceiling, so the natural next test was simply giving it room
to finish. Testing `answer_preamble_chars` at 800 and 1500 on the same 9B model, same context
size: 800 chars still wasn't enough (cut off during step "3. Locate the Information"); 1500
chars reliably worked, three probes in a row, with checkable, transcript-grounded reasoning in
the output ("*This appears near the end of the provided text, specifically after the line*
`TEACHER: Let's continue our discussion on photosynthesis...` *and before* `STUDENT_01: Could
you explain again why...`" then correctly extracting the code that actually followed those
lines) — not a guess. `answer_preamble_chars` now defaults to `1500`, `max_new_tokens_probe` to
`700` (must comfortably cover `answer_preamble_chars` in tokens, roughly 2-2.5 chars/token for
this reasoning style, plus the digits plus margin).

This costs real time — roughly 1-2 minutes per probe in testing, versus a few seconds at the
small-budget setting — but that time is the tool being honest about what these models actually
need to produce a checkable answer, not overhead to optimize away: at the smaller budget the
tool would have reported a confident-looking FAIL that was actually an artifact of the probe
cutting the model off before it could answer at all, which is worse than a slow but correct
result. If your run needs to be faster and you're willing to trade off recall quality for
speed, lower `answer_preamble_chars` back down — just verify against `trials.csv`'s `answer`
field (below) that failures are genuine wrong answers, not truncated reasoning, before trusting
a FAIL verdict at a smaller budget.

Every probe's actual answer text (preamble + digits, not just the extracted code) is recorded
in `trials.csv` specifically so a FAIL can be told apart: genuinely engaging with the transcript
but landing on the wrong digits (a real accuracy finding) vs. an obviously generic/unconditioned
guess or reasoning that never reached the transcript content (raise `answer_preamble_chars`) vs.
truncated before the digits were ever produced (raise `max_new_tokens_probe` to cover the
existing `answer_preamble_chars`).

**What confirmed this was the right fix, not just a plausible-sounding one:** re-running both
candidate models at the *same* `answer_preamble_chars=1500` / `max_new_tokens_probe=700`, same
context sizes, produced two clearly different, both self-consistent results — exactly what a
working validator should do:

- The 9B model passed cleanly at both 8K and 16K tokens, 3/3 probes each, with fully
  verifiable reasoning every time (`"Found near the end of the transcript: TEACHER: ... today's
  classroom access code is 994112 ..."` → answers `994112`, matching the planted code exactly).
- The 35B-class multimodal model still failed at 8K tokens — but for a *visibly different*
  reason than the earlier truncation artifact: given the same 1500-char room, it fell into a
  content loop, re-quoting the same handful of transcript lines over and over
  (`"...Cold War... cell division... French Revolution... Renaissance... Cold War... cell
  division..."`) without ever converging on the actual planted line, before being cut off
  mid-word by the budget. That's a real, reproducible property of that specific model at this
  quantization — visible and diagnosable in `trials.csv`, not a validator bug hiding behind a
  vague "FAIL".

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
    accuracy_threshold: 0.8
    needle_probe_depths: [0.1, 0.5, 0.9]
    answer_preamble_chars: 1500
    max_new_tokens_probe: 700
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
| `accuracy_threshold` | Fraction of needle probes that must be correct to pass a step. |
| `needle_probe_depths` | Relative positions (0-1) in the transcript to plant the needle. |
| `answer_preamble_chars` | Free-text reasoning room allowed before the grammar-constrained digit answer, see §3.7. Real-hardware testing found these models need ~1500 chars to reliably finish their reasoning chain and land on a checked, not guessed, answer. |
| `max_new_tokens_probe` | Generation budget per probe — must cover `answer_preamble_chars` in tokens (roughly 2-2.5 chars/token for this reasoning style) plus the digits plus margin (default 700 comfortably covers the default 1500-char preamble). |
| `trial_timeout_sec` | Per-trial wall-clock budget before the subprocess is killed. |
| `output_dir` | Where `trials.csv` / `summary.json` / `summary.md` are written (relative to `smart-classroom/`). |

## 5. Prerequisites & setup

Everything below is handled automatically by
[`run_validate_long_context.ps1`](../../components/llm/context_validation/run_validate_long_context.ps1)
(§6) — read this section if you want to understand what it's doing, run the tool without the
launcher, or troubleshoot.

1. **A Python environment with the project's `requirements.txt` installed** (OpenVINO GenAI,
   optimum-intel, transformers, torch) — **not** whatever `python` resolves to on `PATH`, which
   is the single most common way to hit "it doesn't run". This tool reuses the exact same
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

# Point at a different config file entirely (e.g. a scratch copy for one-off experiments)
.\components\llm\context_validation\run_validate_long_context.ps1 --config C:\path\to\other.yaml
```

**If you already have the right interpreter active** (see §5), the launcher is just a
convenience wrapper around, run from `smart-classroom/`:

```bash
python -m components.llm.context_validation.validate_long_context [same arguments as above]
```

Console output streams one line per trial as it happens:

```
=== Qwen/Qwen3-8B ===
[Qwen/Qwen3-8B]     8,000 tokens -> PASS (accuracy=0.95, error=None)
...
[Qwen/Qwen3-8B]   160,000 tokens -> PASS (accuracy=0.95, error=None)
[Qwen/Qwen3-8B]   176,000 tokens -> FAIL (accuracy=0.30, error=None)
```

## 7. Interpreting the report

Three files land in `output_dir`:

- **`trials.csv`** — one row per trial, written immediately after each trial completes (so a
  crash mid-sweep doesn't lose earlier results): model, tokens requested, device,
  weight_format, load/generate success, accuracy, error, and a JSON blob of the per-depth probe
  results (`depth`, `tokens_actual`, `correct`, `generate_time_s`, `expected_code`, and `answer`
  — the model's actual output text, see §3.7 for how to read it).
- **`summary.json`** — machine-readable rollup per model: `max_stable_context`,
  `meets_target` (bool, compared against `target_context_tokens`), `failure_reason`, and the
  hardware fingerprint the sweep ran on (from `utils/platform_info.py`).
- **`summary.md`** — the same rollup as a table, e.g.:

  | Model | Device | Weight | Max stable context | Meets target | Notes |
  |---|---|---|---|---|---|
  | Qwen/Qwen3-8B | GPU | int4 | 160,000 | PASS | capped by accuracy_below_threshold |
  | Qwen/Qwen3.6-35B-A3B | GPU | int4 | 128,000 | FAIL | capped by oom |

`failure_reason` values: `oom`, `timeout`, `crashed`, `load_error`, `generate_error`,
`accuracy_below_threshold`. A model whose max stable context still meets the target can show a
failure reason too — it just means the sweep found the *next* configured step above the
target failed for that reason, which is still useful context for headroom planning.

## 8. Hardware caveats

- **Windows iGPU shares system memory.** Unlike a discrete GPU with dedicated VRAM, the Intel
  iGPU's usable memory is bounded by how much the OS/driver lets it allocate. If a model that
  should plausibly fit still hits an OOM-classified failure, first try increasing the dedicated
  GPU memory allocation in **Intel® Graphics Software → Graphics tab**, per the existing
  troubleshooting note for `CL_OUT_OF_RESOURCES` in
  [`advance-setup-guide.md`](../user-guide/advance-setup-guide.md#troubleshooting), before
  concluding the model can't reach the target.
- **`weight_format` trades memory for accuracy.** `int4` leaves the most headroom for a large
  KV-cache (longer max context) but can degrade needle-recall accuracy sooner than `int8` or
  `fp16` at the same context length. If a model fails the accuracy bar (not OOM) at a size
  below target, re-run with a higher-precision `weight_format` before ruling it out.
- **Large candidates cost real disk/RAM even to attempt.** `Qwen/Qwen3.6-35B-A3B`-class models
  need substantial disk space for the IR and host RAM just to load, independent of how far the
  context sweep gets.
- **Each step reloads the model from scratch, on purpose (§3.2), and probes are slow by
  design.** For a 30B+-class model, loading is roughly a minute per step on real hardware,
  before any generation; each probe's generation is roughly 1-2 minutes on top of that with the
  default `answer_preamble_chars=1500` (§3.7) — real testing showed a smaller budget is faster
  but produces falsely-confident FAILs (the model cut off mid-reasoning, not actually wrong). A
  full 13-step sweep is therefore a real commitment of time for large candidates, not a
  five-minute check; pass a shorter custom `--steps` list while iterating on other settings, and
  save the full step schedule for the run you intend to keep. Lowering `answer_preamble_chars`
  trades this accuracy guarantee for speed — only do that once you've confirmed via `trials.csv`
  that the smaller budget still reaches real answers instead of getting cut off.

## 9. Limitations

- The needle-in-haystack probe is a proxy for "does the model still use distant context," not
  a guarantee that full classroom-summary quality holds at that size — validate the winning
  model/size combination against a couple of real long transcripts before shipping it.
- These models reason in a fairly rigid, verbose "1. Analyze the request 2. Scan for keywords
  3. Locate 4. Extract" scaffold before answering, regardless of `/no_think`,
  `enable_thinking=False`, or explicit "no preamble" instructions — `answer_preamble_chars` has
  to be generous enough to let that scaffold complete (§3.7), or every probe looks like a
  confident FAIL that's actually just a truncated reasoning chain. Always check `trials.csv`'s
  `answer` field before trusting a FAIL: genuine wrong answers reference specific (if incorrect)
  transcript content; truncated ones just stop mid-scaffold with no digits at all; a third shape
  — re-quoting the same few transcript lines on a loop without ever converging, seen on one
  35B-class candidate at the default budget — is a real, reproducible property of that model at
  this quantization, not a truncation artifact, and raising the budget further is unlikely to
  resolve a genuine loop.
- The stepping strategy assumes monotonic degradation (pass at N tokens implies nothing
  conclusive about N+1, but a fail at N is assumed to persist for all sizes above N). If a
  model's behavior is non-monotonic, re-run with a denser custom `--steps` list around the
  suspect region.
- `--refine` adds at most 3 extra trials per model — it narrows the reported boundary, it
  doesn't binary-search to token-level precision.
