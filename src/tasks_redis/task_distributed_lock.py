import datetime
import random
import threading
import time
import uuid
from functools import wraps

import redis
from config import redis_obj


class AlreadyRunning(Exception):
    pass


thread_local = threading.local()


def get_thread_maps():
    if not hasattr(thread_local, "held_counts"):
        thread_local.held_counts = {}
        thread_local.tokens = {}
    return thread_local.held_counts, thread_local.tokens


def release_lock(r: redis.Redis, key: str, token: str, retries: int = 5) -> bool:
    for _ in range(retries):
        pipe = r.pipeline()
        try:
            pipe.watch(key)
            val = pipe.get(key)
            if val is None or val.decode() != token:
                pipe.unwatch()
                return False
            pipe.multi()
            pipe.delete(key)
            pipe.execute()
            return True
        except redis.WatchError:
            continue
        finally:
            pipe.reset()
    return False


def single(
    max_processing_time: datetime.timedelta,
    redis_client: redis.Redis | None = None,
    wait_timeout: float | None = None,
    retry_interval: float = 0.1,
):
    if max_processing_time <= datetime.timedelta(0):
        raise ValueError("max_processing_time must be > 0")
    ttl_ms = int(max_processing_time.total_seconds() * 1000)

    def decorator(func):
        lock_key = f"single:{func.__module__}.{func.__qualname__}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            if redis_client is None:
                raise RuntimeError("Redis client is not configured")

            held, tokens = get_thread_maps()
            reentrant = held.get(lock_key, 0) > 0

            if not reentrant:
                token = uuid.uuid4().hex
                deadline = (
                    None if wait_timeout is None else time.monotonic() + wait_timeout
                )

                while True:
                    if redis_client.set(lock_key, token, nx=True, px=ttl_ms):
                        tokens[lock_key] = token
                        break

                    if wait_timeout == 0:
                        raise AlreadyRunning(
                            f"Function is already running (lock={lock_key})"
                        )

                    if deadline is not None and time.monotonic() >= deadline:
                        raise TimeoutError(f"Timed out waiting for lock {lock_key}")

                    time.sleep(retry_interval + random.random() * retry_interval)

            held[lock_key] = held.get(lock_key, 0) + 1
            try:
                return func(*args, **kwargs)
            finally:
                held[lock_key] -= 1
                if held[lock_key] == 0:
                    del held[lock_key]
                    tok = tokens.pop(lock_key, None)
                    if tok is not None:
                        release_lock(redis_client, lock_key, tok)

        return wrapper

    return decorator


@single(max_processing_time=datetime.timedelta(minutes=2), redis_client=redis_obj)
def process_transaction():
    print("Current time:", datetime.datetime.now())
    time.sleep(2)
    print("function process_transaction completed")


@single(
    max_processing_time=datetime.timedelta(minutes=2),
    redis_client=redis_obj,
    wait_timeout=0,
)
def process_transaction_2():
    print("Current time:", datetime.datetime.now())
    time.sleep(2)
    print("function process_transaction_2 completed")


if __name__ == "__main__":
    process_transaction()
    process_transaction()
    process_transaction()

    print("\nНесколько потоков\n")

    threads = []
    for _ in range(3):
        t = threading.Thread(target=process_transaction_2)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
