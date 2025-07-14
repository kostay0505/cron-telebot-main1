# main.py
from http import HTTPStatus
from fastapi import Request, Response
from telegram import Update
from telegram.ext import (
    Application, ExtBot, JobQueue,
    CommandHandler, MessageHandler, CallbackQueryHandler, filters
)
from telegram.ext._contexttypes import ContextTypes
import uvicorn
import asyncio, threading, time, requests
from typing import Dict, Any

from api import app
from bot.ptb import ptb
from bot import handlers, commands
from bot.convos import handlers as convo_handlers
from common.log import logger
import config


# ──────────────────────────────────────────────────────────────
#  ⚙️  KEEP-ALIVE (чтобы Render не «засыпал»)
# ──────────────────────────────────────────────────────────────
KEEP_ALIVE_URL   = "https://cron-telebot-main1.onrender.com/"
PING_INTERVAL_S  = 5 * 60         # 5 минут
OWNER_ID         = 429466372      # ваш Telegram-id (для опц. уведомлений)
SEND_PING_MESSAGE = False         # True → бот присылает «ping», False → только curl


async def _ping_async(context: ContextTypes.DEFAULT_TYPE = None):
    try:
        requests.get(KEEP_ALIVE_URL, timeout=10)
        if SEND_PING_MESSAGE and context:
            await context.bot.send_message(OWNER_ID, "ping ✅")
    except Exception as e:
        logger.warning(f"ping failed: {e}")


def _ping_thread():
    """Fallback-пинг, если JobQueue недоступен (не установлен extra)."""
    while True:
        try:
            requests.get(KEEP_ALIVE_URL, timeout=10)
        except Exception as e:
            logger.warning(f"ping failed: {e}")
        time.sleep(PING_INTERVAL_S)


# ──────────────────────────────────────────────────────────────
#  ⛔️  Ограничение доступа к боту
# ──────────────────────────────────────────────────────────────
only_allowed = filters.User(config.ALLOWED_USERS)


async def error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def add_handlers(
    dp: Application[
        ExtBot[None],
        ContextTypes.DEFAULT_TYPE,
        Dict[Any, Any],
        Dict[Any, Any],
        Dict[Any, Any],
        JobQueue[ContextTypes.DEFAULT_TYPE],
    ]
) -> None:
    # ── Conversations (должны добавляться первыми) ────────────
    dp.add_handler(convo_handlers.edit_handler)
    dp.add_handler(convo_handlers.config_chat_handler)

    # ── Команды ───────────────────────────────────────────────
    command_map = {
        "start":        commands.start,
        "help":         commands.help,
        "add":          commands.add,
        "delete":       commands.delete,
        "list":         commands.list_jobs,
        "checkcron":    commands.checkcron,
        "options":      commands.list_options,
        "adminsonly":   commands.option_restrict_to_admins,
        "creatoronly":  commands.option_restrict_to_user,
        "changetz":     commands.change_tz,
        "reset":        commands.reset,
        "addmultiple":  commands.add_multiple,
    }
    for cmd, fn in command_map.items():
        dp.add_handler(CommandHandler(cmd, fn, filters=only_allowed))

    # ── Обычные сообщения / фото / опросы ────────────────────
    dp.add_handler(MessageHandler(filters.TEXT  & only_allowed, handlers.handle_messages))
    dp.add_handler(MessageHandler(filters.PHOTO & only_allowed, handlers.handle_photos))
    dp.add_handler(MessageHandler(filters.POLL  & only_allowed, handlers.handle_polls))

    # ── Кнопки ────────────────────────────────────────────────
    dp.add_handler(CallbackQueryHandler(handlers.handle_callback, only_allowed))

    # ── Лог ошибок ────────────────────────────────────────────
    dp.add_error_handler(error)


# добавляем все хендлеры
add_handlers(ptb)

# ──────────────────────────────────────────────────────────────
#  Планировщик keep-alive
# ──────────────────────────────────────────────────────────────
if ptb.job_queue:                 # если JobQueue доступен (установлен extra)
    ptb.job_queue.run_repeating(_ping_async, interval=PING_INTERVAL_S, first=0)
else:                             # fallback-пинг через отдельный поток
    threading.Thread(target=_ping_thread, daemon=True).start()


# ──────────────────────────────────────────────────────────────
#  Webhook (Render) / Polling (локально)
# ──────────────────────────────────────────────────────────────
if config.ENV:
    @app.post("/")
    async def process_update(request: Request):
        update = Update.de_json(await request.json(), ptb.bot)
        await ptb.process_update(update)
        return Response(status_code=HTTPStatus.OK)
else:
    # локальная отладка → polling
    if __name__ == "__main__":
        ptb.run_polling()

# запуск через uvicorn для webhook-режима (используется Gunicorn)
if __name__ == "__main__" and config.ENV:
    uvicorn.run(app, host="0.0.0.0", port=8000)
