"""Time range utilities for night pause and scheduling."""

from datetime import datetime
from typing import Optional, Tuple


def parse_time_range(spec: str) -> Optional[Tuple[int, int]]:
    """Parse 'HH:MM-HH:MM' into (start_minutes, end_minutes) from midnight.
    Supports overnight ranges like '22:00-09:00'."""
    if not spec or '-' not in spec:
        return None
    try:
        start_str, end_str = spec.split('-', 1)
        sh, sm = map(int, start_str.strip().split(':'))
        eh, em = map(int, end_str.strip().split(':'))
        return (sh * 60 + sm, eh * 60 + em)
    except (ValueError, IndexError):
        return None


def in_time_range(start_min: int, end_min: int) -> bool:
    """Check if current local time falls within [start, end). Handles overnight wrap."""
    now = datetime.now()
    cur = now.hour * 60 + now.minute
    if start_min <= end_min:
        return start_min <= cur < end_min
    else:  # overnight, e.g. 22:00-09:00
        return cur >= start_min or cur < end_min
