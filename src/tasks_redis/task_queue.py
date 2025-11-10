import json

import redis
from config import redis_obj


class RedisQueue:
    def __init__(self, redis_ins: redis.Redis):
        self.redis_ins = redis_ins
        self.key = "queue1"

    def publish(self, msg: dict):
        self.redis_ins.rpush(self.key, json.dumps(msg))

    def consume(self) -> dict:
        msg = self.redis_ins.lpop(self.key)
        return json.loads(msg)


if __name__ == "__main__":
    q = RedisQueue(redis_obj)
    q.publish({"a": 1})
    q.publish({"b": 2})
    q.publish({"c": 3})

    assert q.consume() == {"a": 1}
    assert q.consume() == {"b": 2}
    assert q.consume() == {"c": 3}
