# `evaluate_rules.py` Templates (custom rule path only)

Needed **only** on the custom rule path (Q2 = yes / schema extended, or custom
alert behavior beyond warn/critical). On the default path no rule file exists
— the built-in `defaultRuleEvaluator` fires on parsed `severity=warn|critical`.

Contract:

- The script reads the parsed fields as a JSON object on `argv[1]` and prints
  an AlertOutcome JSON object, or `null` when no alert should fire.
- It may read **only** fields declared in the Final Schema (base +
  extensions). The register consistency gate rejects rule files that read
  undeclared fields (`rule_fields_not_in_schema`).
- Generate it from the LOCAL_PROMPT output fields and the Final Schema.
- Pass its path as `evaluate_rules_path` to step 1 (`action=register_task`).
  The file may live anywhere — the server stages it to
  `use-cases/<use_case>/evaluate_rules.py` in its repo, smoke-tests the staged
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

## Boolean template (only when boolean extensions were explicitly requested)

Use a boolean parser ONLY when the user explicitly requested boolean schema
extensions and LOCAL_PROMPT declares exactly those boolean fields. Never
choose this shape from behavior names alone.

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
