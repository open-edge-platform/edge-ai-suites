from unittest.mock import patch

import pytest

from utils.stage_tracker import stage_tracker


def test_success_writes_done_event():
    with patch("utils.stage_tracker.StageEventWriter.write") as mw:
        with stage_tracker("s1", "summarize"):
            pass
    assert mw.called
    args, kwargs = mw.call_args
    # positional: session_id, stage, status, started_at, ended_at, duration
    assert args[0] == "s1"
    assert args[1] == "summarize"
    assert args[2] == "done"
    assert args[5] >= 0  # duration
    assert kwargs.get("error_class") is None


def test_failure_writes_failed_event_and_reraises():
    raised = False
    with patch("utils.stage_tracker.StageEventWriter.write") as mw:
        try:
            with stage_tracker("s1", "mindmap"):
                raise ValueError("boom")
        except ValueError:
            raised = True
    assert raised  # exception propagated
    args, kwargs = mw.call_args
    assert args[2] == "failed"
    assert kwargs.get("error_class") == "ValueError"
    assert kwargs.get("error_detail") == "boom"


def test_generator_exit_is_recorded_as_interrupted():
    """A client hanging up mid-stream closes the generator, raising GeneratorExit
    at the yield. It is not an Exception, so without its own branch the stage
    would be left at 'running'."""
    def streamer():
        with stage_tracker("s1", "transcribe"):
            yield "chunk"
            yield "never reached"

    with patch("utils.stage_tracker.StageEventWriter.write") as mw:
        gen = streamer()
        assert next(gen) == "chunk"
        gen.close()

    args, kwargs = mw.call_args
    assert args[2] == "interrupted"
    assert kwargs.get("error_class") == "GeneratorExit"


def test_keyboard_interrupt_is_recorded_and_reraised():
    with patch("utils.stage_tracker.StageEventWriter.write") as mw:
        with pytest.raises(KeyboardInterrupt):
            with stage_tracker("s1", "report"):
                raise KeyboardInterrupt
    assert mw.call_args[0][2] == "interrupted"


def test_handle_fail_records_failure_without_raising():
    """Streaming endpoints turn their errors into a payload rather than raising;
    StageHandle.fail() is how the tracker still hears about it."""
    with patch("utils.stage_tracker.StageEventWriter.write") as mw:
        with stage_tracker("s1", "report") as stage:
            stage.fail(RuntimeError("[ERROR]: no transcript"))

    args, kwargs = mw.call_args
    assert args[2] == "failed"
    assert kwargs.get("error_class") == "RuntimeError"
    assert kwargs.get("error_detail") == "[ERROR]: no transcript"


def test_stage_transitions_reach_the_session_store():
    with patch("utils.stage_tracker.StageEventWriter.write"), patch(
        "utils.stage_tracker.SessionStore.set_stage"
    ) as mset:
        with stage_tracker("s1", "summarize"):
            pass
    assert [c.args for c in mset.call_args_list] == [
        ("s1", "summarize", "running"),
        ("s1", "summarize", "done"),
    ]


def test_store_failure_does_not_break_the_stage():
    """Bookkeeping must never be able to fail a stage that actually succeeded."""
    with patch("utils.stage_tracker.StageEventWriter.write"), patch(
        "utils.stage_tracker.SessionStore.set_stage", side_effect=RuntimeError("db gone")
    ):
        with stage_tracker("s1", "summarize"):
            pass  # no exception escapes
