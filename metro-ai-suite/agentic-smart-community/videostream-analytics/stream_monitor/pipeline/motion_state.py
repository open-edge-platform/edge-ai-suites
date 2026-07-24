"""Motion event enter/exit state machine."""


class MotionStateMachine:
    """Encapsulates motion event enter/exit logic.

    Entry: motion detector transitions from static -> motion.
    Exit:  cascaded conditions depending on prefilter state:
      - prefilter disabled: motion detector says static
      - prefilter enabled, before decision: static + min_dur + pf decided
      - prefilter enabled, after pass: pf.exit_decided (person left scene)
      - segment interval is the hard ceiling (handled externally by extractor)
    """

    def __init__(self, min_duration_s: float = 0.0, prefilter=None):
        self._min_dur = min_duration_s
        self._pf = prefilter
        self._in_motion = False
        self._motion_start_vs = 0.0

    @property
    def in_motion(self) -> bool:
        return self._in_motion

    @property
    def motion_start_vs(self) -> float:
        return self._motion_start_vs

    def should_enter(self, detector) -> bool:
        return not self._in_motion and not detector.is_static

    def enter(self, video_s: float):
        self._in_motion = True
        self._motion_start_vs = video_s

    def should_exit(self, detector, video_s: float) -> bool:
        if not self._in_motion:
            return False
        if self._pf is None:
            return detector.is_static
        if not self._pf.decided:
            collected_s = video_s - self._motion_start_vs
            min_dur_ok = (self._min_dur <= 0 or collected_s >= self._min_dur)
            return detector.is_static and min_dur_ok and self._pf.is_decided
        return self._pf.exit_decided

    def exit(self):
        self._in_motion = False
