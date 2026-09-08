from unittest.mock import MagicMock

_STAGE_METHODS = ("run_transcription", "run_summarizer", "run_mindmap",
                  "run_content_segmentation", "run_report_generator")


def make_pipeline_mock(fail_at=None, fail_with=None, fail_mode="immediate",
                       block_at=None, block_event=None):
    """Build a MagicMock standing in for utils/orchestrator's Pipeline.

    Each stage method is a MagicMock returning an empty generator by default.
    Parametrize:
    - fail_at: which method raises (a stage name).
    - fail_mode="mid_iteration": yield once then raise, exercising _drain's
      mid-stream error path.
    - block_at: which method blocks on block_event, for hang/concurrency tests.
    Tests may override `pipeline.run_transcription.side_effect` directly.
    """
    pipeline = MagicMock(name="Pipeline")

    fail_with = fail_with or RuntimeError("boom")

    for method in _STAGE_METHODS:
        mock = MagicMock(name=method)

        def _base(*args, _m=method, **kwargs):
            if block_at is not None and block_at == _m and block_event is not None:
                block_event.wait()
            if fail_at is not None and fail_at == _m:
                if fail_mode == "mid_iteration":
                    return _mid_iter_gen(fail_with)
                raise fail_with
            return iter([])

        mock.side_effect = _base
        setattr(pipeline, method, mock)
    return pipeline


def _mid_iter_gen(error):
    def _gen():
        yield None
        raise error
    return _gen()