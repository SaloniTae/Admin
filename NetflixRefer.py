import logging
import random
import string
import requests
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode


# ---------------- Logging Setup ----------------
logging.getLogger("httpx").setLevel(logging.INFO)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------- Proxy DB Configuration ----------------
REAL_DB_URL = "https://testing-6de54-default-rtdb.firebaseio.com/"

def read_data():
    try:
        resp = requests.get(REAL_DB_URL + ".json")
        if resp.status_code == 200:
            return resp.json() or {}
        else:
            logging.error("DB read error: " + resp.text)
            return {}
    except Exception as e:
        logging.error("read_data exception: " + str(e))
        return {}

def write_data(data):
    try:
        resp = requests.put(REAL_DB_URL + ".json", json=data)
        if resp.status_code == 200:
            return resp.json()
        else:
            logging.error("DB write error: " + resp.text)
            return {}
    except Exception as e:
        logging.error("write_data exception: " + str(e))
        return {}

# ---------------- Telegram Bot Configuration ----------------
API_ID = 25270711  # Your App ID
API_HASH = "6bf18f3d9519a2de12ac1e2e0f5c383e"  # Your API Hash
BOT_TOKEN = "7140092976:AAFtmOBKi-mIoVighcf4XXassHimU2CtlR8"  # Replace with your bot token


# NOTE: The following line is commented out because we now register handlers via a function.
# app = Client("ReferEarnBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ---------------- Utility Functions ----------------
def get_required_points():
    """
    Retrieves the required points (for superior status) from the "referral_settings" node.
    Defaults to 100 if not set.
    """
    db_data = read_data()
    if not db_data:
        logger.info("DB data empty; using default required points: 100")
        return 100
    settings = db_data.get("referral_settings", {})
    try:
        req = int(settings.get("required_point", 100))
        logger.info(f"Required points set to: {req}")
        return req
    except Exception as e:
        logger.error(f"Error converting required points to int: {e}")
        return 100

async def get_referral_info(user_id):
    db_data = read_data()
    if not db_data:
        logger.error("No DB data in get_referral_info.")
        return None
    referrals = db_data.get("referrals", {})
    return referrals.get(str(user_id))

def get_top_referrers(n=10):
    db_data = read_data()
    if not db_data:
        logger.error("No DB data in get_top_referrers.")
        return []
    referrals = db_data.get("referrals", {})
    ref_list = []
    for uid, record in referrals.items():
        points = record.get("referral_points", 0)
        code = record.get("referral_code", "N/A")
        total_referred = len(record.get("referred_users", []))
        ref_list.append((uid, points, code, total_referred))
    ref_list.sort(key=lambda x: x[1], reverse=True)
    return ref_list[:n]

async def register_user(user):
    # Implement the user registration logic here.
    # For demonstration, we'll assume it writes an empty record for the user.
    db_data = read_data() or {}
    referrals = db_data.get("referrals", {})
    if str(user.id) not in referrals:
        referrals[str(user.id)] = {"referral_code": "", "referral_points": 0, "referred_users": []}
        db_data["referrals"] = referrals
        write_data(db_data)
        logger.info(f"Registered new user: {user.id}")
    else:
        logger.info(f"User {user.id} is already registered.")


def register_refer_handlers(app):
    @app.on_message(filters.command("top10"))
    async def top10_handler(client, message):
        db_data = read_data()
        if not db_data:
            await message.reply_text("Failed to retrieve data from the database.")
            return

        # Get the referrals node and count total registered referral users.
        referrals = db_data.get("referrals", {})
        total_users = len(referrals)

        # Build the report using HTML formatting.
        report_lines = []
        report_lines.append("<b>📊 𝗢𝗢𝗥𝘃𝗲𝗿𝘀𝗲 𝖲𝗍𝖺𝗍𝗂𝗌𝗍𝗂𝖼𝗌 📊</b>")
        report_lines.append("")
        report_lines.append(f"<b>𝗧𝗼𝘁𝗮𝗹 𝗖𝗿𝗲𝘄 𝗠𝗲𝗺𝗯𝗲𝗿𝘀:</b> {total_users}")
        report_lines.append("")
        report_lines.append("<b>𝗧𝗼𝗽 10 𝖬𝖾𝗆𝖻𝖾𝗋𝗌:</b>")

        top_referrers = get_top_referrers(10)
        if top_referrers:
            for idx, (uid, points, code, total_referred) in enumerate(top_referrers, start=1):
                report_lines.append(f"{idx}. <b>𝖮𝖮𝖱𝖻𝗂𝗍𝗌:</b> {points}")
                report_lines.append(f"    <b>𝖢𝗋𝖾𝗐:</b> {total_referred}")
                report_lines.append(f"    <b>𝖴𝗌𝖾𝗋𝖨𝖣:</b> <code>{uid}</code>")
                report_lines.append(f"    <b>𝖢𝖮𝖣𝖤:</b> <code>{code}</code>")
                report_lines.append("")  # Blank line between entries
        else:
            report_lines.append("No referral data available.")

        report_text = "\n".join(report_lines)
        await message.reply_text(report_text, parse_mode=ParseMode.HTML)



    @app.on_message(filters.command("ping"))
    async def ping_handler(client, message):
        db_data = read_data()
        if db_data:
            await message.reply_text("pong - DB connected.")
        else:
            await message.reply_text("pong - DB connection failed.")


    # NEW CODE: Log a message indicating successful registration of refer.py handlers.
    logger.info("Refer.py handlers registered successfully.")

# ---------------- Optional: Standalone Testing ----------------
if __name__ == "__main__":
    # NEW CODE: Allow running refer.py independently for testing.
    from pyrogram import Client
    print("Starting refer.py in standalone mode for testing...")
    app = Client("NetflixReferEarnBot", api_id=API_ID, api_hash="API_HASH", bot_token="BOT_TOKEN")
    register_refer_handlers(app)
    print("Refer.py handlers registered. Running the client...")
    app.run()
