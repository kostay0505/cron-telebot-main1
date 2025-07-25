from os import getenv
from dotenv import load_dotenv

load_dotenv()

""" General config """
# Set ENV to any value to use webhook instead of polling for bot. Must be set in prod environment.
ENV = getenv("ENV")
TZ_OFFSET = 8.0  # (UTC+08:00)
JOB_LIMIT_PER_PERSON = 10
BATCH_SIZE = 100  # Max number of messages to send at any given time
RETRIES = 1  # Number of retries if message fails to send
BOT_NAME = "@cron_telebot"

""" Telegram config """
TELEGRAM_BOT_TOKEN = getenv("TELEGRAM_BOT_TOKEN")
BOTHOST = getenv("BOTHOST")  # only required in prod environment, used to set webhook


""" DB config """
MONGODB_CONNECTION_STRING = getenv("MONGODB_CONNECTION_STRING")
MONGODB_DB = "rm_bot"
MONGODB_JOB_DATA_COLLECTION = "job_data"
MONGODB_CHAT_DATA_COLLECTION = "chat_data"
MONGODB_USER_DATA_COLLECTION = "user_data"
MONGODB_BOT_DATA_COLLECTION = "bot_data"
MONGODB_USER_WHITELIST_COLLECTION = "whitelist"

INFLUXDB_TOKEN = getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = "main"
INFLUXDB_BUCKET = "prod"
INFLUXDB_HOST = "https://eu-central-1-1.aws.cloud2.influxdata.com"
ALLOWED_USERS = {
    429466372,      # @metamodernismus
    1731120809,     # @gaslightingdesign
}
# --- keep-alive -------------------------------------------------
KEEP_ALIVE_URL      = "https://cron-telebot-main1.onrender.com/"
PING_INTERVAL       = 5 * 60           # секунд (5 мин)
OWNER_ID            = 429466372        # кому слать «ping», если SEND_PING_MESSAGE=True
SEND_PING_MESSAGE   = False            # True → придёт тихое сообщение, False → лишь HTTP-запрос
# ----------------------------------------------------------------
