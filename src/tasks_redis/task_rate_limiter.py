import random
import time

import redis
from config import redis_obj


class RateLimitExceed(Exception):
    pass


class RateLimiter:
    def __init__(
        self,
        redis_client: redis.Redis,
        key: str = "ratelimit:global",
        window_seconds: float = 3.0,
        limit: int = 5,
    ):
        self.redis_client = redis_client
        self.key = key
        self.window_ms = int(window_seconds * 1000)
        self.limit = int(limit)
        self.ttl_ms = int(self.window_ms * 2)

    def test(self) -> bool:
        now = int(time.time() * 1000)
        pipe = self.redis_client.pipeline()
        while True:
            try:
                pipe.watch(self.key)
                pipe.zremrangebyscore(self.key, "-inf", now - self.window_ms)
                count = pipe.zcard(self.key)
                if count >= self.limit:
                    pipe.unwatch()
                    return False
                member = f"{now}-{random.getrandbits(32)}"
                pipe.multi()
                pipe.zadd(self.key, {member: now})
                pipe.pexpire(self.key, self.window_ms * 2)
                pipe.execute()
                return True
            except redis.WatchError:
                now = int(time.time() * 1000)
                continue
            finally:
                pipe.reset()


def make_api_request(rate_limiter: RateLimiter):
    if not rate_limiter.test():
        raise RateLimitExceed
    else:
        # какая-то бизнес логика
        pass


if __name__ == "__main__":
    rate_limiter = RateLimiter(redis_obj)

    for _ in range(50):
        time.sleep(random.randint(1, 2))

        try:
            make_api_request(rate_limiter)
        except RateLimitExceed:
            print("Rate limit exceed!")
        else:
            print("All good")
