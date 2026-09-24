# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Keep the overload conditions the prompt budget detects but must not act on.

The budget is sized from what the device can address rather than from what is
free, so that the same lesson always splits the same way. That reproducibility
is exactly why it cannot see a machine that got busier, an answer cap too large
for the device, or notes two fold rounds could not compress. Each of those was
already detected and written to a log file; this module keeps them as
structured records instead, so a client can show them and a finished run can be
audited from its own artifacts.

Recording is observability: it never changes a plan. A caller that records a
warning carries straight on with the call it was about to make.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

from utils.session_paths import SessionPaths

logger = logging.getLogger(__name__)

# What each code means, and what the user can do about it.
MEMORY_SHORT = "memory_short"        # less free RAM now than this call needs
RESERVE_CAPPED = "reserve_capped"    # instructions + answer alone exceed half the budget
FOLD_INCOMPLETE = "fold_incomplete"  # notes still over budget after the fold rounds
LINE_OVERSIZE = "line_oversize"      # one transcript line is longer than a chunk may be

CODES = (MEMORY_SHORT, RESERVE_CAPPED, FOLD_INCOMPLETE, LINE_OVERSIZE)


def warnings_path(session_id: str):
    return SessionPaths.logs_dir(session_id) / "warnings.jsonl"


class OverloadWarnings:
    """Records one session's overload warnings, in memory and on disk.

    Bound to a session rather than global: two sessions in the same process
    must not read each other's warnings, and the summary and the segmentation
    of one session should.
    """

    def __init__(self, session_id: Optional[str], stage: str):
        self.session_id = session_id
        self.stage = stage
        self.records: List[dict] = []

    def record(self, code: str, detail: str, **numbers) -> dict:
        """Append one warning and return it, ready to be yielded to a client.

        The numbers that caused the warning are top-level fields, not prose in
        ``detail``, so the UI and the analysis read the same values.

        Repeats are collapsed: one planning pass asks ``usable_tokens`` both
        whether one call fits and how large a chunk may be, and the same
        shortfall answered twice is still one thing to tell the user. Different
        numbers under the same code are different warnings and both survive.
        """
        entry = {
            "event": "warning",
            "code": code,
            "stage": self.stage,
            "detail": detail,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **numbers,
        }
        if any(self._same(entry, seen) for seen in self.records):
            return entry

        self.records.append(entry)
        self._append(entry)
        return entry

    @staticmethod
    def _same(a: dict, b: dict) -> bool:
        """Two records of the same condition. ``at`` is when, not what."""
        return {k: v for k, v in a.items() if k != "at"} == \
               {k: v for k, v in b.items() if k != "at"}

    def _append(self, entry: dict) -> None:
        """Write one JSON line. A warning must never break the run it describes."""
        if not self.session_id:
            return
        try:
            path = warnings_path(self.session_id)
            os.makedirs(path.parent, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except (OSError, ValueError) as e:  # ValueError: unsafe session id
            logger.warning("[overload] could not record %s for %s: %s",
                           entry.get("code"), self.session_id, e)

    # ---- callbacks for text_chunker, which knows the numbers but not the session ----

    def on_short(self, tokens: int, need_bytes: int, free_bytes: int, what: str) -> None:
        gb = 1024 ** 3
        self.record(
            MEMORY_SHORT,
            f"This {what} needs {need_bytes / gb:.2f} GB of KV cache but only "
            f"{free_bytes / gb:.2f} GB is free right now. The plan was not changed -- "
            f"it is sized from what the device can address, so that the same lesson "
            f"always splits the same way. Close what else is running if it fails.",
            tokens=tokens,
            need_gb=round(need_bytes / gb, 2),
            free_gb=round(free_bytes / gb, 2),
            what=what,
        )

    def on_cap(self, budget: int, reserve: int, cap: int) -> None:
        self.record(
            RESERVE_CAPPED,
            f"Instructions and the answer alone want {reserve} of a {budget}-token "
            f"budget; the reserve was capped at {cap}. The answer may be cut short. "
            f"Lower max_new_tokens for this device, or shorten the board text.",
            budget=budget, reserve=reserve, cap=cap,
        )

    def on_oversize(self, largest: int, ceiling: int, label: str) -> None:
        self.record(
            LINE_OVERSIZE,
            f"The largest {label} is {largest} tokens against the {ceiling} that "
            f"fit: one transcript line could not be packed any tighter.",
            largest=largest, ceiling=ceiling, label=label,
        )


def read(session_id: str) -> List[dict]:
    """Return a session's recorded warnings; an unreadable file yields none."""
    try:
        path = warnings_path(session_id)
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except (OSError, ValueError):
        return []

    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            logger.debug("Skipping malformed warning line in %s: %r", session_id, line)
    return out
