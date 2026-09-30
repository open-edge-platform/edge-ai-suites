import time


def wait_for_va_completion(service, wanted, done, final_status, timeout,
                           interval=2.0, grace_polls=3) -> bool:
    deadline = time.monotonic() + timeout
    down_count = 0
    while time.monotonic() < deadline:
        if done.is_set():
            final_status.update(service.pipeline_final_status)
            return True
        statuses = service.pipeline_final_status
        if statuses and all(statuses.get(n) in ("eos", "failed") for n in wanted):
            final_status.update(statuses)
            return True
        all_down = all(not service.is_pipeline_running(n) for n in wanted)
        if all_down:
            down_count += 1
            if down_count >= grace_polls:
                final_status.update(service.pipeline_final_status)
                return True
        else:
            down_count = 0
        time.sleep(interval)
    return False
