from http import HTTPStatus
from datetime import datetime

import requests
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

from api import app
from bot import commands, handlers
from bot.convos import handlers as convo_handlers
from bot.ptb import ptb
from common.log import logger
import config

# 🔒 Ограничиваем пользователей
only_allowed = filters.User(config.ALLOWED_USERS)

# ------------------------------------------------------------------
# Keep-alive job ----------------------------------------------------
def keep_alive_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Периодически «тыкает» Render, чтобы контейнер не засыпал."""
    try:
        # HTTP-пинг
        requests.get(config.KEEP_ALIVE_URL, timeout=10)
        # Опционально – тихое сообщение владельцу
        if config.SEND_PING_MESSAGE:
            context.bot.send_message(
                chat_id=config.OWNER_ID,
                text=f"🔄 ping {datetime.utcnow().strftime('%H:%M:%S')}",
                disable_notification=True,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Keep-alive failed: %s", exc)
# ------------------------------------------------------------------


async def error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логируем все необработанные ошибки."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def add_handlers(
    dp: Application[
        ExtBot[None],
        ContextTypes.DEFAULT_TYPE,
        dict,
        dict,
        dict,
        JobQueue[ContextTypes.DEFAULT_TYPE],
    ]
) -> None:
    # --- беседы (должны идти первыми) -----------------------------
    dp.add_handler(convo_handlers.edit_handler)
    dp.add_handler(convo_handlers.config_chat_handler)

    # --- командные обработчики ------------------------------------
    dp.add_handler(CommandHandler("start",         commands.start,                filters=only_allowed))
    dp.add_handler(CommandHandler("help",          commands.help,                 filters=only_allowed))
    dp.add_handler(CommandHandler("add",           commands.add,                  filters=only_allowed))
    dp.add_handler(CommandHandler("delete",        commands.delete,               filters=only_allowed))
    dp.add_handler(CommandHandler("list",          commands.list_jobs,            filters=only_allowed))
    dp.add_handler(CommandHandler("checkcron",     commands.checkcron,            filters=only_allowed))
    dp.add_handler(CommandHandler("options",       commands.list_options,         filters=only_allowed))
    dp.add_handler(CommandHandler("adminsonly",    commands.option_restrict_to_admins, filters=only_allowed))
    dp.add_handler(CommandHandler("creatoronly",   commands.option_restrict_to_user,   filters=only_allowed))
    dp.add_handler(CommandHandler("changetz",      commands.change_tz,            filters=only_allowed))
    dp.add_handler(CommandHandler("reset",         commands.reset,                filters=only_allowed))
    dp.add_handler(CommandHandler("addmultiple",   commands.add_multiple,         filters=only_allowed))

    # --- обычные сообщения ----------------------------------------
    dp.add_handler(MessageHandler(filters.TEXT  & only_allowed, handlers.handle_messages))
    dp.add_handler(MessageHandler(filters.PHOTO & only_allowed, handlers.handle_photos))
    dp.add_handler(MessageHandler(filters.POLL  & only_allowed, handlers.handle_polls))

    # --- кнопки ----------------------------------------------------
    dp.add_handler(CallbackQueryHandler(handlers.handle_callback, only_allowed))

    # --- ошибки ----------------------------------------------------
    dp.add_error_handler(error)


# Регистрируем всё вышеописанное
add_handlers(ptb)

# Добавляем keep-alive задачу
ptb.job_queue.run_repeating(
    keep_alive_job,
    interval=config.PING_INTERVAL,
    first=0,
    name="keep_alive",
)

# ------------------------------------------------------------------
# Web-hook (сервер)  -----------------------------------------------
if config.ENV:

    @app.post("/")
    async def process_update(request: Request):
        req = await request.json()
        update = Update.de_json(req, ptb.bot)
        await ptb.process_update(update)
        return Response(status_code=HTTPStatus.OK)

# Polling (локально) ----------------------------------------------
if __name__ == "__main__":
    if not config.ENV:
        ptb.run_polling()
    else:
        # Локальная проверка веб-хука (если нужно)
        uvicorn.run(app, host="0.0.0.0", port=8000)
