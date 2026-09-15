import logging

# Endpoints the UI polls on a short interval. Their access-log lines would
# otherwise flood the console with one entry per second, per endpoint.
POLLED_PATHS = ("/metrics", "/health")


class SuppressPolledAccessLogs(logging.Filter):
    """Drop successful uvicorn access-log records for high-frequency poll endpoints.

    Errors (>= 400) are always kept so real failures stay visible.
    """

    def filter(self, record):
        args = record.args
        # uvicorn.access args: (client_addr, method, full_path, http_version, status_code)
        if not isinstance(args, tuple) or len(args) < 5:
            return True
        path = str(args[2]).split("?")[0]
        try:
            status_code = int(args[4])
        except (TypeError, ValueError):
            return True
        return not (path in POLLED_PATHS and status_code < 400)


def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # main.py is imported twice (as __main__ and again by uvicorn.run("main:app")),
    # so guard against attaching the filter more than once.
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, SuppressPolledAccessLogs) for f in access_logger.filters):
        access_logger.addFilter(SuppressPolledAccessLogs())
