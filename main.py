from http import HTTPStatus
from fastapi import Request, Response
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
from telegram.ext._contexttypes import ContextTypes
from telegram import Update
import uvicorn
from bot.ptb import ptb
from api import app
from bot import handlers, commands
import config
from bot.convos import handlers as convo_handlers
from common.log import logger
from telegram.ext import Application, ExtBot, JobQueue
from typing import Dict, Any


# ⛔️ Ограничить доступ к боту
only_allowed = filters.User(config.ALLOWED_USERS)


async def error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
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
    # conversations (must be declared first)
    dp.add_handler(convo_handlers.edit_handler)
    dp.add_handler(convo_handlers.config_chat_handler)

    # командные хендлеры
    dp.add_handler(CommandHandler("start", commands.start, filters=only_allowed))
    dp.add_handler(CommandHandler("help", commands.help, filters=only_allowed))
    dp.add_handler(CommandHandler("add", commands.add, filters=only_allowed))
    dp.add_handler(CommandHandler("delete", commands.delete, filters=only_allowed))
    dp.add_handler(CommandHandler("list", commands.list_jobs, filters=only_allowed))
    dp.add_handler(CommandHandler("checkcron", commands.checkcron, filters=only_allowed))
    dp.add_handler(CommandHandler("options", commands.list_options, filters=only_allowed))
    dp.add_handler(CommandHandler("adminsonly", commands.option_restrict_to_admins, filters=only_allowed))
    dp.add_handler(CommandHandler("creatoronly", commands.option_restrict_to_user, filters=only_allowed))
    dp.add_handler(CommandHandler("changetz", commands.change_tz, filters=only_allowed))
    dp.add_handler(CommandHandler("reset", commands.reset, filters=only_allowed))
    dp.add_handler(CommandHandler("addmultiple", commands.add_multiple, filters=only_allowed))

    # текст/фото/опросы
    dp.add_handler(MessageHandler(filters.TEXT & only_allowed, handlers.handle_messages))
    dp.add_handler(MessageHandler(filters.PHOTO & only_allowed, handlers.handle_photos))
    dp.add_handler(MessageHandler(filters.POLL & only_allowed, handlers.handle_polls))

    # кнопки
    dp.add_handler(CallbackQueryHandler(handlers.handle_callback, only_allowed))

    # логировать все ошибки
    dp.add_error_handler(error)


add_handlers(ptb)

# Webhook (на сервере)
if config.ENV:

    @app.post("/")
    async def process_update(request: Request):
        req = await request.json()
        update = Update.de_json(req, ptb.bot)
        await ptb.process_update(update)
        return Response(status_code=HTTPStatus.OK)

# Polling (локально)
if __name__ == "__main__":
    if not config.ENV:
        ptb.run_polling()
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)
