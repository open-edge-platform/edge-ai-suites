"""elder_wakeup evaluate_rules override.

Receives parsed VLM fields on argv[1]. Prints an AlertOutcome JSON object or null.

Fires a `late_wakeup` alert when:
  1. VLM-reported event is `get_up`, and
  2. current local time is later than `expectedWakeupLocal + graceMinutes`.
"""

import json
import os
import sys
from datetime import datetime


DEFAULT_EXPECTED_WAKEUP_LOCAL = "07:00"
DEFAULT_GRACE_MINUTES = 30


def hhmm_to_minutes(s: str) -> int | None:
    """Parse 'HH:MM' to total minutes since midnight."""
    if not s:
        return None
    parts = s.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h * 60 + m


def current_minutes() -> int:
    """Current local time as minutes since midnight."""
    now = datetime.now()
    return now.hour * 60 + now.minute


def evaluate_rules(parsed: dict) -> dict | None:
    event = parsed.get("event", "")

    if event != "get_up":
        return None

    expected_str = os.environ.get(
        "ELDER_WAKEUP_EXPECTED_WAKEUP_LOCAL",
        DEFAULT_EXPECTED_WAKEUP_LOCAL,
    )
    expected = hhmm_to_minutes(expected_str)
    if expected is None:
        return None

    grace = int(os.environ.get(
        "ELDER_WAKEUP_GRACE_MINUTES",
        str(DEFAULT_GRACE_MINUTES),
    ))

    observed = current_minutes()

    if observed <= expected + grace:
        return None

    wakeup_time = parsed.get("wakeup_time")
    extra = {}
    if wakeup_time:
        try:
            extra["wakeupTime"] = float(wakeup_time)
        except (ValueError, TypeError):
            pass

    return {
        "alertType": "late_wakeup",
        "severity": "warn",
        "description": parsed.get("desc") or parsed.get("description", ""),
        **extra,
    }


def main() -> None:
    parsed = json.loads(sys.argv[1])
    print(json.dumps(evaluate_rules(parsed)))


if __name__ == "__main__":
    main()
