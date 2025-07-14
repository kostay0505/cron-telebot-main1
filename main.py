"""
main.py — точка входа веб-приложения и Telegram-бота
----------------------------------------------------

* Web-hook (`/`) обрабатывают обновления от Telegram.
* Keep-alive-пинг раз в `PING_INTERVAL` сек не даёт Render «уснуть».
* Scheduler каждые 60 сек просматривает базу (`api.run`)
  и рассылает сообщения в нужное время.

‼️ Требует python-telegram-bot, установленный c extra `[job-queue]`
    pip install "python-telegram-bot[job-queue]"
"""

from http import HTTPStatus
from typing import Any, Dict

import aiohttp
import asyncio
import uvicorn
from fastapi import Request, Response
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ExtBot,
    JobQueue,
    MessageHandler,
    filters,
)

import config
from api import app
from bot import commands, handlers
from bot.convos import handlers as convo_handlers
from bot.ptb import ptb
from common.log import logger

# ---------------------------------------------------------------------------
# 🔒 Ограничиваем доступ к боту
# ---------------------------------------------------------------------------
only_allowed = filters.User(config.ALLOWED_USERS)

# ---------------------------------------------------------------------------
#  Keep-alive: чтобы Render-контейнер не «засыпал» по-прошествии 15 мин
# ---------------------------------------------------------------------------
KEEP_ALIVE_URL = "https://cron-telebot-main1.onrender.com/"
PING_INTERVAL = 5 * 60          # секунд
OWNER_ID = 429466372            # ваш Telegram-id
SEND_PING_MESSAGE = False       # True → бот шлёт сообщение; False → обычный HTTP-ping


async def _ping(_: ContextTypes.DEFAULT_TYPE) -> None:
    """Раз в PING_INTERVAL: HTTP-запрос к себе или сообщение владельцу."""
    try:
        if SEND_PING_MESSAGE:
            await ptb.bot.send_message(OWNER_ID, "ping")
        else:
            async with aiohttp.ClientSession() as sess:
                await sess.get(KEEP_ALIVE_URL, timeout=10)
        logger.info("PING ok")
    except Exception as exc:                               # noqa: BLE001
        logger.warning("PING failed: %s", exc)


# ---------------------------------------------------------------------------
#  Scheduler: вызываем «рассыльщик» (`api.run`) каждые 60 сек
# ---------------------------------------------------------------------------
async def _run_scheduler(_: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Имитация GET /api — забирает из Mongo записи с истекшим `nextrun_ts`
    и рассылает сообщения.
    """
    from api import run as process_jobs                   # локальный импорт ⬅
    await asyncio.to_thread(process_jobs)                 # не блокируем event-loop


# ---------------------------------------------------------------------------
#  Логирование ошибок
# ---------------------------------------------------------------------------
async def error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:      # noqa: ANN001
    logger.warning('Update "%s" caused error "%s"', update, context.error)


# ---------------------------------------------------------------------------
#  Регистрируем обработчики
# ---------------------------------------------------------------------------
def add_handlers(
    dp: Application[
        ExtBot[None],
        ContextTypes.DEFAULT_TYPE,
        Dict[Any, Any],
        Dict[Any, Any],
        Dict[Any, Any],
        JobQueue[ContextTypes.DEFAULT_TYPE],
    ],
) -> None:
    # conversations
    dp.add_handler(convo_handlers.edit_handler)
    dp.add_handler(convo_handlers.config_chat_handler)

    # команды
    dp.add_handler(CommandHandler("start",        commands.start,        filters=only_allowed))
    dp.add_handler(CommandHandler("help",         commands.help,         filters=only_allowed))
    dp.add_handler(CommandHandler("add",          commands.add,          filters=only_allowed))
    dp.add_handler(CommandHandler("delete",       commands.delete,       filters=only_allowed))
    dp.add_handler(CommandHandler("list",         commands.list_jobs,    filters=only_allowed))
    dp.add_handler(CommandHandler("checkcron",    commands.checkcron,    filters=only_allowed))
    dp.add_handler(CommandHandler("options",      commands.list_options, filters=only_allowed))
    dp.add_handler(CommandHandler("adminsonly",   commands.option_restrict_to_admins, filters=only_allowed))
    dp.add_handler(CommandHandler("creatoronly",  commands.option_restrict_to_user,   filters=only_allowed))
    dp.add_handler(CommandHandler("changetz",     commands.change_tz,    filters=only_allowed))
    dp.add_handler(CommandHandler("reset",        commands.reset,        filters=only_allowed))
    dp.add_handler(CommandHandler("addmultiple",  commands.add_multiple, filters=only_allowed))

    # сообщения
    dp.add_handler(MessageHandler(filters.TEXT  & only_allowed, handlers.handle_messages))
    dp.add_handler(MessageHandler(filters.PHOTO & only_allowed, handlers.handle_photos))
    dp.add_handler(MessageHandler(filters.POLL  & only_allowed, handlers.handle_polls))

    # кнопки
    dp.add_handler(CallbackQueryHandler(handlers.handle_callback, only_allowed))

    # ошибки
    dp.add_error_handler(error)


add_handlers(ptb)

# ---------------------------------------------------------------------------
#  Планируем фоновые задачи через JobQueue (если она активна)
# ---------------------------------------------------------------------------
if ptb.job_queue is not None:
    ptb.job_queue.run_repeating(_ping,          interval=PING_INTERVAL, first=30)
    ptb.job_queue.run_repeating(_run_scheduler, interval=60,            first=10)
else:
    logger.warning("JobQueue not available — keep-alive / scheduler disabled!")

# ---------------------------------------------------------------------------
#  Web-hook (Render)  / Polling (локально)
# ---------------------------------------------------------------------------
if config.ENV:
    @app.post("/")
    async def process_update(request: Request):
        req = await request.json()
        update = Update.de_json(req, ptb.bot)
        await ptb.process_update(update)
        return Response(status_code=HTTPStatus.OK)
else:
    # локальный режим (python main.py)
    if __name__ == "__main__":
        ptb.run_polling()

# Запуск через gunicorn в проде
if __name__ == "__main__" and config.ENV:
    uvicorn.run(app, host="0.0.0.0", port=8000)
