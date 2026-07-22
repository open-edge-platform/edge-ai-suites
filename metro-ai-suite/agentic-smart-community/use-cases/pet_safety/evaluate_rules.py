import sys, json

SEVERITY_ORDER = {"info": 0, "warn": 1, "critical": 2}


def evaluate_rules(parsed: dict) -> dict | None:
    event = parsed.get("event", "")
    severity = parsed.get("severity", "info").lower()
    desc = parsed.get("desc") or parsed.get("description", "")
    zone = parsed.get("pet_zone", "unknown")

    excluded_events = {"no_incident", "pet_normal"}
    threshold_level = SEVERITY_ORDER["warn"]

    if event in excluded_events:
        return None
    if SEVERITY_ORDER.get(severity, 0) < threshold_level:
        return None

    return {
        "alertType": event or "pet_safety",
        "severity": severity,
        "description": f"{desc} (zone={zone})",
    }


def main():
    parsed = json.loads(sys.argv[1])
    print(json.dumps(evaluate_rules(parsed)))

if __name__ == "__main__":
    main()
