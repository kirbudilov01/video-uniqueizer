from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    bot_token: str
    redis_url: str
    data_dir: Path
    copies_count: int
    worker_count: int
    max_video_mb: int
    max_active_jobs_per_user: int
    allow_all_users: bool
    allowed_user_ids: set[int]
    use_gpu: bool
    ffmpeg_threads: int
    send_results_as_document: bool


def get_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    allowed_raw = os.getenv("ALLOWED_USER_IDS", "").replace(" ", "")
    allowed: set[int] = set()
    for item in allowed_raw.split(","):
        if item:
            try:
                allowed.add(int(item))
            except ValueError:
                pass
    return Settings(
        bot_token=token,
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        data_dir=Path(os.getenv("DATA_DIR", "/data")),
        copies_count=_int_env("COPIES_COUNT", 10),
        worker_count=_int_env("WORKER_COUNT", 4),
        max_video_mb=_int_env("MAX_VIDEO_MB", 200),
        max_active_jobs_per_user=_int_env("MAX_ACTIVE_JOBS_PER_USER", 3),
        allow_all_users=_bool_env("ALLOW_ALL_USERS", True),
        allowed_user_ids=allowed,
        use_gpu=_bool_env("USE_GPU", False),
        ffmpeg_threads=_int_env("FFMPEG_THREADS", 2),
        send_results_as_document=_bool_env("SEND_RESULTS_AS_DOCUMENT", True),
    )
