# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import time
from typing import Dict, Optional, Tuple

from src.schemas.monitor import (
    AlertConfig,
    AlertRuntimeState,
)

logger = logging.getLogger(__name__)


class AlertStateManager:
    """
    Tracks runtime alert state for all streams and all alerts.

    State dictionary layout::

        _state[stream_id][alert_name] = AlertRuntimeState(...)
    """

    def __init__(self):
        self._state: Dict[str, Dict[str, AlertRuntimeState]] = {}
    def register_stream(self, stream_id: str):
        if stream_id not in self._state:
            self._state[stream_id] = {}

    def unregister_stream(self, stream_id: str):
        self._state.pop(stream_id, None)

    def reset_all(self):
        """Clear all runtime state (e.g. after alert config changes)."""
        self._state.clear()

    def reset_alert(self, alert_name: str):
        """Clear runtime state for a specific alert across all streams."""
        for stream_state in self._state.values():
            stream_state.pop(alert_name, None)

    # ------------------------------------------------------------------ #
    # Core processing
    # ------------------------------------------------------------------ #

    def process(
        self,
        stream_id: str,
        alert_cfg: AlertConfig,
        answer: str,        # "YES" or "NO"
        reason: str,
    ) -> Tuple[bool, bool, bool]:
        """
        Update state for one (stream, alert) pair and determine what actions
        should be taken.

        Returns
        -------
        (should_act, is_escalation, is_transition)
            should_act   : True if tools should be invoked
            is_escalation: True if the escalation threshold was just reached
            is_transition: True if the answer changed from the previous cycle
                           (useful for dashboard "state change" events)
        """
        if stream_id not in self._state:
            self._state[stream_id] = {}

        state = self._state[stream_id].get(alert_cfg.name)
        if state is None:
            state = AlertRuntimeState()
            self._state[stream_id][alert_cfg.name] = state

        now = time.monotonic()

        _NO_CONFIRM_LIMIT = 2  # consecutive NOs required to clear an alert

        if answer == "YES":
            state.consecutive_yes += 1
            state.consecutive_no = 0
            is_transition = state.last_answer != "YES"
            if is_transition:
                state.last_transition_ts = now
            state.last_answer = "YES"  # type: ignore[assignment]
        else:
            # Only track consecutive NOs while in an active (YES) alert state
            if state.last_answer == "YES":
                state.consecutive_no += 1
            else:
                state.consecutive_no = 0
            if state.consecutive_no >= _NO_CONFIRM_LIMIT:
                # Confirmed clear: require N consecutive NOs before flipping
                state.consecutive_yes = 0
                is_transition = state.last_answer != "NO"
                if is_transition:
                    state.last_transition_ts = now
                    logger.info(
                        f"CLEARED [{stream_id}][{alert_cfg.name}] "
                        f"— {state.consecutive_no} consecutive NOs"
                    )
                state.last_answer = "NO"  # type: ignore[assignment]
            else:
                # Grace period: not enough NOs yet, keep last_answer unchanged
                is_transition = False

            return False, False, is_transition

        should_act = True

        # --- escalation check ---
        is_escalation = False
        if (
            should_act
            and alert_cfg.escalation
            and state.consecutive_yes >= alert_cfg.escalation.threshold_consecutive
        ):
            is_escalation = True
            logger.warning(
                f"ESCALATION [{stream_id}][{alert_cfg.name}] "
                f"— {state.consecutive_yes} consecutive detections"
            )

        if should_act:
            state.last_action_ts = now

        return should_act, is_escalation, is_transition

    def get_consecutive_count(self, stream_id: str, alert_name: str) -> int:
        return self._state.get(stream_id, {}).get(alert_name, AlertRuntimeState()).consecutive_yes

    def get_consecutive_no(self, stream_id: str, alert_name: str) -> int:
        return self._state.get(stream_id, {}).get(alert_name, AlertRuntimeState()).consecutive_no

    def get_last_answer(self, stream_id: str, alert_name: str) -> str:
        return self._state.get(stream_id, {}).get(alert_name, AlertRuntimeState()).last_answer

    def get_runtime_states(self, stream_id: str) -> Dict[str, dict]:
        """Return serialisable runtime state for all alerts on a stream."""
        states = self._state.get(stream_id, {})
        return {
            name: {
                "last_answer": s.last_answer,
                "consecutive_yes": s.consecutive_yes,
                "consecutive_no": s.consecutive_no,
            }
            for name, s in states.items()
        }
