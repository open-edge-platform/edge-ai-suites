<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Component Tests

## Running

The suite is written as pytest functions, so `unittest discover` will collect
nothing. From `education-ai-suite/smart-classroom`, with the project venv
active:

```sh
python -m pytest components/tests -q
```

`test_paraformer.py` loads the real FunASR model and downloads a sample clip;
it is marked `slow`. Everything else runs against fakes — no model loaded, no
audio decoded, nothing read from or written to `storage/` — so the line for a
quick check is:

```sh
python -m pytest components/tests -q -m "not slow"
```

A `FakeTokenizer` that splits on whitespace stands in for the real one, so token
counts in the tests are readable numbers rather than model-specific ones.

`manual_media_service.py` and `manual_va_pipeline_service.py` are not tests:
they have no assertions and need a live MediaMTX server and RTSP sources. They
are run by hand — see their module docstrings — and pytest does not collect
them.

The chunking modules are documented in
[`docs/dev-guide/transcript-chunking/prompt-budget.md`](../../docs/dev-guide/transcript-chunking/prompt-budget.md).

## Adding a Test

- `conftest.py` already puts the repo root on `sys.path`; the modules import as
  `utils.x` and `components.x`.
- Mark anything that loads a model, hits the network, or needs a running service
  with `pytest.mark.slow`, so `-m "not slow"` stays fast.
- Take the budget out of the equation with
  `patch.object(text_chunker, "resolve_budget", return_value=N)` — otherwise the
  plan depends on the machine running the test.
- Restore anything mutated on the live `config` object in a `finally`; the
  config loader is a process-wide singleton.
- Say in the test name what would break if it failed. `_charged` / `_reserve` /
  `_announced` name the behaviour; `test_chunk_2` does not.
