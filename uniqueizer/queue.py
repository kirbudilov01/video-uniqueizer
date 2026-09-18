from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass

import redis

QUEUE_KEY = "uniqueizer:jobs"
JOB_PREFIX = "uniqueizer:job:"
USER_ACTIVE_PREFIX = "uniqueizer:user_active:"


@dataclass
class Job:
    id: str
    chat_id: int
    user_id: int
    original_name: str
    input_path: str
    copies_count: int
    mode: str
    created_at: float


def new_job(chat_id: int, user_id: int, original_name: str, input_path: str, copies_count: int, mode: str = "standard") -> Job:
    return Job(
        id=uuid.uuid4().hex,
        chat_id=chat_id,
        user_id=user_id,
        original_name=original_name,
        input_path=input_path,
        copies_count=copies_count,
        mode=mode,
        created_at=time.time(),
    )


def redis_client(redis_url: str) -> redis.Redis:
    return redis.from_url(redis_url, decode_responses=True)


def enqueue(r: redis.Redis, job: Job) -> int:
    payload = json.dumps(asdict(job), ensure_ascii=False)
    pipe = r.pipeline()
    pipe.hset(JOB_PREFIX + job.id, mapping={"status": "queued", "payload": payload, "updated_at": str(time.time())})
    pipe.incr(USER_ACTIVE_PREFIX + str(job.user_id))
    pipe.expire(USER_ACTIVE_PREFIX + str(job.user_id), 24 * 3600)
    pipe.rpush(QUEUE_KEY, payload)
    pipe.llen(QUEUE_KEY)
    return int(pipe.execute()[-1])


def active_for_user(r: redis.Redis, user_id: int) -> int:
    value = r.get(USER_ACTIVE_PREFIX + str(user_id))
    return int(value or 0)


def mark_status(r: redis.Redis, job_id: str, status: str, detail: str = "") -> None:
    r.hset(JOB_PREFIX + job_id, mapping={"status": status, "detail": detail, "updated_at": str(time.time())})


def finish_user_job(r: redis.Redis, user_id: int) -> None:
    key = USER_ACTIVE_PREFIX + str(user_id)
    try:
        if int(r.get(key) or 0) > 0:
            r.decr(key)
    except Exception:
        pass
