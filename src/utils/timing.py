import random
import time


def sleep_ms(ms: int, jitter: float = 0.25) -> None:
    j = ms * jitter
    dur = max(0.0, (ms - j) + random.random() * (2 * j))
    time.sleep(dur / 1000.0)
