from unittest.mock import MagicMock


def make_va_service_mock(launch_results=True, launch_raises=None,
                         final_status=None, stop_raises=None):
    """Build a MagicMock standing in for VideoAnalyticsPipelineService.

    launch_results: True        -> every launch_pipeline call returns True
                    False       -> every launch returns False
                    dict        -> per-pipeline-name result, e.g. {"front": True}
    final_status:   dict merged into service.pipeline_final_status.  Omitted
                    pipelines that launched are marked "eos" (success).
    stop_raises:    exception raised by stop_all_pipelines.
    """
    service = MagicMock(name="VideoAnalyticsPipelineService")
    service.pipeline_final_status = {}
    final_status = final_status or {}

    def _launch(name, source, options):
        if launch_raises is not None:
            raise launch_raises
        if isinstance(launch_results, dict):
            ok = launch_results.get(name, True)
        else:
            ok = launch_results
        if ok and name not in service.pipeline_final_status:
            service.pipeline_final_status[name] = final_status.get(name, "eos")
        return ok

    service.launch_pipeline.side_effect = _launch

    def _stop(timeout=None):
        if stop_raises is not None:
            raise stop_raises

    service.stop_all_pipelines.side_effect = _stop
    return service


def make_wait_completion_mock(result=True, block_event=None):
    """Return a MagicMock for utils.orchestrator.wait_for_va_completion.

    result: True  -> VA considered complete; populates `final_status` arg from
                     the service's pipeline_final_status (mirrors the real
                     function so _any_success sees "eos").
            False -> never completes within timeout (timeout path).
    block_event: if set, block until the event fires before returning result.
    """
    from unittest.mock import MagicMock as _M
    mock = _M(name="wait_for_va_completion")

    def _wait(service, wanted, done, final_status, timeout, *args, **kwargs):
        if block_event is not None:
            block_event.wait()
        if result:
            final_status.update(service.pipeline_final_status)
        return result

    mock.side_effect = _wait
    return mock