# `evaluate_rules.py` Templates (custom rule path only)

Needed **only** on the custom rule path (Q2 = yes / schema extended, or custom
alert behavior beyond warn/critical). Every extended schema requires this file;
the consistency gate rejects an extension with no rule before any side effect.
On the base path no rule file exists — the built-in `defaultRuleEvaluator`
fires on parsed `severity=warn|critical`.

Contract:

- The script reads the parsed fields as a JSON object on `argv[1]` and prints
  an AlertOutcome JSON object, or `null` when no alert should fire.
  **The function returns alerts only. No alert ⇒ print `null`.**
- It may read **only** fields declared in the Final Schema (base +
  extensions). The register consistency gate rejects rule files that read
  undeclared fields (`rule_fields_not_in_schema`).
- Generate it from the LOCAL_PROMPT output fields and the Final Schema.
- Define how every extension is handled by the alert policy, alert description,
  or a documented non-alerting/default branch. The static gate verifies field
  ownership but cannot prove that every extension changes the decision.
- Pass its path as `evaluate_rules_path` to step 1 (`action=generate_task`).
  The file may live anywhere — the server stages it to
  `<data_dir>/use-cases/<use_case>/evaluate_rules.py` (`<data_dir>` is the
  server's data dir: `$SMART_COMMUNITY_DATA_DIR` or `~/.mcp-smart-community` by
  default), smoke-tests the staged
  copy, and persists that path into config.

## Severity/event template (with an extension zone field)

```python
import json, sys

SEVERITY_ORDER = {"info": 0, "warn": 1, "critical": 2}

def main():
    fields = json.loads(sys.argv[1])
    event = fields.get("event", "")
    severity = fields.get("severity", "info").lower()
    desc = fields.get("desc", "")
    zone = fields.get("zone_id", "unknown")
    excluded = {"no_incident", "normal_event"}
    should_alert = event not in excluded and SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER["warn"]
    outcome = {
        "alertType": event or "alert",
        "severity": severity,
        "description": f"{desc} (zone={zone})",
    } if should_alert else None
    print(json.dumps(outcome))

if __name__ == "__main__":
    main()
```

Adjust `excluded` to the use case's safe/no-incident events, and the extension
field reads (`zone_id` above) to the declared extensions.

## Boolean-valued template (only when explicitly requested)

The schema supports `text`, `integer`, and `real`, not a native boolean type.
Use this parser only when the user explicitly requested a boolean-valued
text/integer extension and LOCAL_PROMPT declares it. Never choose this shape
from behavior names alone.

```python
import json, sys

def truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

def main():
    fields = json.loads(sys.argv[1])
    should_alert = truthy(fields.get("<risk_field>"))
    outcome = {
        "alertType": "<event_name>",
        "severity": "warn",
        "description": "<human-readable alert>",
    } if should_alert else None
    print(json.dumps(outcome))

if __name__ == "__main__":
    main()
```
