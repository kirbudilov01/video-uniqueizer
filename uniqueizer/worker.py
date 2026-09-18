from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import telebot

from .config import get_settings
from .processing import cleanup_path, make_copy
from .queue import QUEUE_KEY, finish_user_job, mark_status, redis_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("uniqueizer.worker")

settings = get_settings()
if not settings.bot_token:
    raise SystemExit("BOT_TOKEN is required")

bot = telebot.TeleBot(settings.bot_token, threaded=True, parse_mode="HTML")
r = redis_client(settings.redis_url)


def send_file(chat_id: int, path: Path, caption: str) -> None:
    with path.open("rb") as fh:
        if settings.send_results_as_document:
            bot.send_document(chat_id, fh, caption=caption, visible_file_name=path.name, timeout=300)
        else:
            bot.send_video(chat_id, fh, caption=caption, supports_streaming=True, timeout=300)


def process_job(job: dict) -> None:
    job_id = job["id"]
    chat_id = int(job["chat_id"])
    user_id = int(job["user_id"])
    input_path = job["input_path"]
    out_dir = settings.data_dir / "jobs" / job_id
    started_at = time.time()
    mark_status(r, job_id, "processing")
    log.info("job %s started user=%s mode=%s copies=%s input=%s", job_id, user_id, job.get("mode", "standard"), job["copies_count"], input_path)
    bot.send_message(chat_id, f"🔧 Начал обработку задачи <code>{job_id[:8]}</code>.")

    completed = 0
    errors = 0
    try:
        with ThreadPoolExecutor(max_workers=max(1, settings.worker_count)) as pool:
            futures = [
                pool.submit(make_copy, input_path, out_dir, idx, settings.ffmpeg_threads, settings.use_gpu, job.get("mode", "standard"))
                for idx in range(int(job["copies_count"]))
            ]
            for idx, future in enumerate(as_completed(futures), start=1):
                try:
                    path = future.result()
                    completed += 1
                    log.info("job %s copy sent %s/%s path=%s", job_id, completed, job["copies_count"], path)
                    send_file(chat_id, path, f"✅ Копия {completed}/{job['copies_count']}")
                except Exception as exc:
                    errors += 1
                    log.exception("copy failed")
                    bot.send_message(chat_id, f"❌ Ошибка копии {idx}: {str(exc)[:300]}")
        elapsed = time.time() - started_at
        mark_status(r, job_id, "done", f"completed={completed}; errors={errors}; elapsed_sec={elapsed:.1f}")
        log.info("job %s done completed=%s errors=%s elapsed_sec=%.1f", job_id, completed, errors, elapsed)
        bot.send_message(chat_id, f"✅ Готово. Успешно: {completed}, ошибок: {errors}. Время: {elapsed:.1f} сек.")
    except Exception as exc:
        elapsed = time.time() - started_at
        mark_status(r, job_id, "failed", f"{str(exc)[:400]}; elapsed_sec={elapsed:.1f}")
        log.exception("job %s failed elapsed_sec=%.1f", job_id, elapsed)
        bot.send_message(chat_id, f"❌ Задача упала: {str(exc)[:500]}")
    finally:
        finish_user_job(r, user_id)
        cleanup_path(out_dir)
        try:
            os.remove(input_path)
        except OSError:
            pass


def main() -> None:
    log.info("worker started")
    while True:
        item = r.blpop(QUEUE_KEY, timeout=10)
        if not item:
            continue
        _, payload = item
        try:
            process_job(json.loads(payload))
        except Exception:
            log.exception("worker failed to process payload")


if __name__ == "__main__":
    main()
