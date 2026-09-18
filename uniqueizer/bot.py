from __future__ import annotations

import logging
import re
import time
from pathlib import Path

import telebot
from telebot import types

from .config import get_settings
from .queue import active_for_user, enqueue, new_job, redis_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("uniqueizer.bot")

settings = get_settings()
if not settings.bot_token:
    raise SystemExit("BOT_TOKEN is required")

bot = telebot.TeleBot(settings.bot_token, threaded=True, parse_mode="HTML")
r = redis_client(settings.redis_url)
MODE_PREFIX = "uniqueizer:user_mode:"


def allowed(user_id: int) -> bool:
    return settings.allow_all_users or user_id in settings.allowed_user_ids


def safe_filename(name: str) -> str:
    name = Path(name or "video.mp4").name
    name = re.sub(r"[^A-Za-z0-9а-яА-ЯёЁ._-]+", "_", name)
    return name[:120] or "video.mp4"


def mode_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("СТАНДАРТНАЯ", callback_data="mode:standard"),
        types.InlineKeyboardButton("ЗАЛИПАТЕЛЬНАЯ", callback_data="mode:satisfying"),
    )
    return keyboard


def selected_mode(user_id: int) -> str | None:
    value = r.get(MODE_PREFIX + str(user_id))
    return value if value in {"standard", "satisfying"} else None


@bot.message_handler(commands=["start", "help"])
def start(message):
    r.delete(MODE_PREFIX + str(message.from_user.id))
    bot.send_message(
        message.chat.id,
        "🎬 Выберите тип уникализации, затем отправьте видео.",
        reply_markup=mode_keyboard(),
    )


@bot.callback_query_handler(func=lambda call: call.data in {"mode:standard", "mode:satisfying"})
def choose_mode(call):
    mode = call.data.split(":", 1)[1]
    r.setex(MODE_PREFIX + str(call.from_user.id), 7 * 24 * 3600, mode)
    label = "СТАНДАРТНАЯ" if mode == "standard" else "ЗАЛИПАТЕЛЬНАЯ"
    bot.answer_callback_query(call.id, f"Выбрана: {label}")
    bot.edit_message_text(
        f"Выбрана <b>{label}</b>. Теперь отправьте видео.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=mode_keyboard(),
    )


@bot.message_handler(commands=["status"])
def status(message):
    queue_len = r.llen("uniqueizer:jobs")
    active = active_for_user(r, message.from_user.id)
    bot.send_message(message.chat.id, f"Очередь: {queue_len}\nВаших активных задач: {active}")


@bot.message_handler(content_types=["video", "document"])
def handle_video(message):
    user_id = message.from_user.id
    if not allowed(user_id):
        bot.send_message(message.chat.id, "Доступ пока не открыт для вашего аккаунта.")
        return

    active = active_for_user(r, user_id)
    if active >= settings.max_active_jobs_per_user:
        bot.send_message(message.chat.id, f"У вас уже {active} активных задач. Дождитесь завершения.")
        return

    mode = selected_mode(user_id)
    if mode is None:
        bot.send_message(
            message.chat.id,
            "Сначала выберите режим обработки кнопкой ниже, затем отправьте видео.",
            reply_markup=mode_keyboard(),
        )
        return

    if message.content_type == "video":
        file_obj = message.video
        file_name = safe_filename(message.video.file_name or f"video_{message.video.file_unique_id}.mp4")
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("video/"):
        file_obj = message.document
        file_name = safe_filename(message.document.file_name or f"video_{message.document.file_unique_id}.mp4")
    else:
        bot.send_message(message.chat.id, "Отправьте именно видеофайл.")
        return

    if file_obj.file_size and file_obj.file_size > settings.max_video_mb * 1024 * 1024:
        bot.send_message(message.chat.id, f"Файл слишком большой. Лимит: {settings.max_video_mb} МБ.")
        return

    day_dir = settings.data_dir / "incoming" / time.strftime("%Y%m%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    local_path = day_dir / f"{int(time.time())}_{user_id}_{file_name}"

    msg = bot.send_message(message.chat.id, "Скачиваю видео и ставлю в очередь...")
    try:
        info = bot.get_file(file_obj.file_id)
        downloaded = bot.download_file(info.file_path)
        local_path.write_bytes(downloaded)
        label = "стандартная" if mode == "standard" else "залипательная"
        job = new_job(message.chat.id, user_id, file_name, str(local_path), settings.copies_count, mode)
        position = enqueue(r, job)
        r.delete(MODE_PREFIX + str(user_id))
        bot.edit_message_text(
            f"✅ Задача принята: <b>{label}</b> обработка.\nID: <code>{job.id[:8]}</code>\nПозиция в очереди: {position}",
            chat_id=message.chat.id,
            message_id=msg.message_id,
            reply_markup=mode_keyboard(),
        )
    except Exception as exc:
        log.exception("failed to enqueue")
        bot.edit_message_text(f"Ошибка при постановке в очередь: {str(exc)[:300]}", message.chat.id, msg.message_id)


def main() -> None:
    log.info("bot started")
    bot.infinity_polling(timeout=120, long_polling_timeout=60)


if __name__ == "__main__":
    main()
