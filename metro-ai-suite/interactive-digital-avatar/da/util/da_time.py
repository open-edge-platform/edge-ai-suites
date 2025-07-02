from time import perf_counter, sleep


def precise_sleep(duration):
    """
    :param duration: time in seconds
    :return:
    """
    start = perf_counter()
    while perf_counter() - start < duration:
        sleep(0.000)
        pass


def get_now_time():
    return perf_counter()


class RateLimiter:
    def __init__(self, frequency_per_sec: int):
        # Interval in seconds for each call based on frequency
        self.interval = 1.0 / frequency_per_sec
        self.last_time = perf_counter() - self.interval

    def wait(self):
        # Calculate the time we need to wait to meet the frequency limit
        elapsed_time = perf_counter() - self.last_time
        remaining_time = self.interval - elapsed_time

        # If we're too early, wait until the next allowed time
        if remaining_time > 0:
            precise_sleep(remaining_time)

        # Update the last run time to the current time
        self.last_time = perf_counter()
