# fridge

Refrigerator monitoring use case. Emits narrative-style VLM summaries used by
the daily-report tool; **no realtime alert rules apply**.

## Rule handling

`evaluate_rules.py` unconditionally returns `{"should_alert": false}`. The
fridge VLM prompt produces narrative-style summaries consumed by the report
generator; opening `alerts` rows is not part of the use case. The stub is
retained rather than relying on `defaultRuleEvaluator` so operators have a
strong "fridge never alerts" invariant even if a summary happens to contain
`SEVERITY: warn`.

## Prompts

- `prompt.md` — Chinese-language task registration content (`LOCAL_PROMPT` /
  `GLOBAL_PROMPT` sections).
- `prompt_en.md` — English-language variant, selectable by the operator at
  task registration time.

Both variants target the same VLM task name (`fridge_monitor`); only one
should be registered per deployment.

## Configuration

`config.yaml`:

```yaml
use_case_dict:
  fridge:
    video_summary_task: "fridge_monitor"
    rules: {}
```

No `evaluate_rules_path` — see "Rule handling" above.
