import time
import logging
from queue import Queue
from threading import Thread, Timer
from datetime import datetime, timedelta
import pytz
import requests
import json

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.errors import FloodWait

from NetflixRefer import (
    get_required_points,
    get_referral_info,
    get_top_referrers
)

from NetflixRefer import register_refer_handlers

from FileID_module import register_fileid_handlers # FileID Module

import random # refer for REF-ID
import string # refer for REF-ID
from pyrogram.enums import ParseMode # For HTML styling
import asyncio # for Wait to send REF-ID

# Auto Verify QR
import os
import json
import uuid
import random
import base64
import time
import asyncio
import urllib.parse
from io import BytesIO
from uuid import uuid4
import string, secrets

import aiohttp
import requests
from PIL import Image, ImageOps, ImageDraw
from pyrogram import Client, filters
from qrcode_styled import QRCodeStyled, ERROR_CORRECT_H
from qrcode_styled.pil.image import PilStyledImage
from decimal import Decimal, InvalidOperation
from pyrogram import idle

# --------------------- Bot Configuration ---------------------
API_ID = "25270711"
API_HASH = "6bf18f3d9519a2de12ac1e2e0f5c383e"
BOT_TOKEN = "7140092976:AAHsqcw-hfs-Kb0aAgMof631fJ7DL1-NY_w"

# (My Test Bot)
#API_ID = "25270711"
#API_HASH = "6bf18f3d9519a2de12ac1e2e0f5c383e"
#BOT_TOKEN = "7140092976:AAHsqcw-hfs-Kb0aAgMof631fJ7DL1-NY_w"

#API_ID = "27708983"
#API_HASH = "d0c88b417406f93aa913ecb5f1b58ba6"
#BOT_TOKEN = "7516682635:AAFMspWzwgqrmUgjVXSbNl6VggvtDIGowek"


# --------------------- DB CONFIG ---------------------
# Replace with your actual Firebase Realtime Database URL (include trailing slash)
# Define your real DB URL
REAL_DB_URL = "https://testing-6de54-default-rtdb.firebaseio.com/"

UPI_ID           = "paytm.s1a23xv@pty"
MERCHANT_NAME    = "OTT ON RENT"
MID              = "RZUqNv45112793295319"
INTERNAL_API_KEY = "OTTONRENT"  # for your html2image service
TEMPLATE_URL     = "https://cdn.jsdelivr.net/gh/OTTONRENT01/FOR-PHOTOS@main/QRTemplate.png"
LOGO_URL         = "https://cdn.jsdelivr.net/gh/OTTONRENT01/FOR-PHOTOS@main/QRLogo.png"

app = Client("NetflixMultiSlotBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

logger = logging.getLogger(__name__)


# ── GLOBAL aiohttp SESSION ─────────────────────────────────────────────────
aiohttp_session: aiohttp.ClientSession = None
ui_cache = None

async def init_aiohttp_session():
    """
    Call this exactly once, before app.run(), to create a shared aiohttp session.
    """
    global aiohttp_session
    if aiohttp_session is None:
        aiohttp_session = aiohttp.ClientSession()

async def close_aiohttp_session():
    """
    Call this right after app.run() returns, to close the aiohttp session.
    """
    global aiohttp_session
    if aiohttp_session:
        await aiohttp_session.close()
        aiohttp_session = None

# ── ASYNC HELPERS FOR PARTIAL‐NODE DB OPERATIONS ────────────────────────────

async def read_node(path: str) -> dict:
    """
    Async GET for any /<path>.json (returns {} if missing).
    Example: read_node("users") fetches REAL_DB_URL/users.json.
    """
    url = REAL_DB_URL.rstrip("/") + f"/{path}.json"
    try:
        async with aiohttp_session.get(url) as resp:
            if resp.status == 200:
                return await resp.json() or {}
            else:
                text = await resp.text()
                logging.error(f"read_node('{path}') HTTP {resp.status}: {text}")
                return {}
    except Exception as e:
        logging.error(f"read_node('{path}') exception: {e}")
        return {}

async def patch_node(path: str, payload: dict) -> None:
    """
    Async PATCH for /<path>.json with the given payload.
    Example: patch_node("users", {"12345": True}) → PATCH /users.json
    """
    url = REAL_DB_URL.rstrip("/") + f"/{path}.json"
    try:
        async with aiohttp_session.patch(url, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                logging.error(f"patch_node('{path}') HTTP {resp.status}: {text}")
    except Exception as e:
        logging.error(f"patch_node('{path}') exception: {e}")

async def get_shallow_keys() -> list:
    """
    Async GET with ?shallow=true to fetch only the top‐level keys.
    Example: GET REAL_DB_URL/.json?shallow=true → { "users": true, "referrals": true, ... }
    Returns a list of those keys.
    """
    url = REAL_DB_URL.rstrip("/") + "/.json?shallow=true"
    try:
        async with aiohttp_session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json() or {}
                return list(data.keys())
            else:
                logging.error(f"get_shallow_keys HTTP {resp.status}")
                return []
    except Exception as e:
        logging.error(f"get_shallow_keys exception: {e}")
        return []

async def read_users_node() -> dict:
    """Fetch /users.json (one level)."""
    return await read_node("users")

async def read_ui_config(section: str) -> dict:
    """Fetch /ui_config/<section>.json (one level)."""
    return await read_node(f"ui_config/{section}")

# ── SYNCHRONOUS STUB FOR LEGACY get_ui_config() ────────────────────────────
def get_ui_config(section: str) -> dict:
    """
    Synchronous stub for code paths that still call get_ui_config() directly.
    In async handlers you should use await read_ui_config(section) instead.
    """
    return {}

# ── HELPER: Check if a node is a valid “credential” object ──────────────────
def is_credential(node):
    """
    We require belongs_to_slot so each credential is assigned to a slot.
    """
    if not isinstance(node, dict):
        return False
    required = [
        "email","password","expiry_date",
        "locked","usage_count","max_usage",
        "belongs_to_slot"
    ]
    return all(r in node for r in required)

# Store each user's chosen slot in memory:
user_slot_choice = {}  # e.g. { user_id: "slot_1" }

# In-memory store of order_id → amount
order_store = {}

# --------------------- Logging Setup ---------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Register any FileID or referral handlers
register_fileid_handlers(app)

try:
    register_refer_handlers(app)
    print("refer.py handlers registered successfully in bot.py!")
except Exception as e:
    print("Error registering refer.py handlers:", e)
    
# --------------------- Message Queue Setup ---------------------
message_queue = Queue()

def message_sender():
    while True:
        task = message_queue.get()
        try:
            func, args, kwargs = task
            func(*args, **kwargs)
            logging.info(f"Message sent to {args[0] if args else 'unknown'}")
        except FloodWait as e:
            logging.warning(f"FloodWait: waiting {e.value} seconds")
            time.sleep(e.value)
            message_queue.put(task)
        finally:
            message_queue.task_done()

Thread(target=message_sender, daemon=True).start()

# ── DATABASE READ/WRITE FOR CREDENTIAL UPDATES (UNCHANGED) ─────────────────

def update_credential_usage(cred_key, new_usage):
    logging.info(f"Updating usage_count for {cred_key} => {new_usage}")
    try:
        url = REAL_DB_URL.rstrip("/") + f"/{cred_key}/usage_count.json"
        requests.patch(url, json=new_usage, timeout=10)
    except Exception:
        pass

def update_credential_locked(cred_key, new_locked):
    logging.info(f"Updating locked for {cred_key} => {new_locked}")
    try:
        url = REAL_DB_URL.rstrip("/") + f"/{cred_key}/locked.json"
        requests.patch(url, json=new_locked, timeout=10)
    except Exception:
        pass

# ── ORDERID CHECK / MARK (UNCHANGED) ────────────────────────────────────────

def is_orderid_used(order_id) -> bool:
    try:
        url = REAL_DB_URL.rstrip("/") + f"/used_orderids/{order_id}.json"
        resp = requests.get(url, timeout=10)
        return resp.status_code == 200 and resp.json() is True
    except Exception:
        return False

def mark_orderid_used(order_id):
    try:
        url = REAL_DB_URL.rstrip("/") + "/used_orderids.json"
        requests.patch(url, json={ str(order_id): True }, timeout=10)
    except Exception:
        pass

# ── GET A VALID CREDENTIAL FOR A GIVEN SLOT (UNCHANGED) ─────────────────────

def get_valid_credential_for_slot(slot_id):
    """
    Priority: return (cred_key, cred_data) from 'all' credentials first.
    If none valid, then fallback to credentials for the specific slot_id.
    """
    locked_found = False
    found_in_all = None
    found_in_slot = None

    try:
        r = requests.get(REAL_DB_URL.rstrip("/") + "/.json?shallow=true", timeout=10)
        top_keys = list(r.json().keys()) if r.status_code == 200 else []
    except Exception:
        top_keys = []

    for key in top_keys:
        try:
            r2 = requests.get(REAL_DB_URL.rstrip("/") + f"/{key}.json", timeout=10)
            node = r2.json() if r2.status_code == 200 else {}
        except Exception:
            continue

        if not is_credential(node):
            continue

        owns = node.get("belongs_to_slot")
        if isinstance(owns, str):
            owns = [owns]
        elif not isinstance(owns, list):
            continue

        if int(node.get("locked", 0)) == 1:
            locked_found = True
            continue

        usage_count = int(node.get("usage_count", 0))
        max_usage   = int(node.get("max_usage", 0))
        try:
            expiry_dt = datetime.strptime(node["expiry_date"], "%Y-%m-%d")
        except Exception:
            continue

        if usage_count >= max_usage or expiry_dt <= datetime.now():
            continue

        if "all" in owns and not found_in_all:
            found_in_all = (key, node)
        elif slot_id in owns and not found_in_slot:
            found_in_slot = (key, node)

    if found_in_all:
        logging.info(f"[SELECTED] {found_in_all[0]} for slot {slot_id} (global)")
        return found_in_all
    if found_in_slot:
        logging.info(f"[SELECTED] {found_in_slot[0]} for slot {slot_id}")
        return found_in_slot

    if locked_found:
        return None, "locked"
    return None, None

def handle_action_with_gif(client, callback_query, gif_url, next_action):
    if gif_url:
        message_queue.put_nowait((
            client.send_animation,
            [callback_query.message.chat.id],
            {"animation": gif_url}
        ))
    def delayed():
        message_queue.put_nowait((next_action, (client, callback_query), {}))
    Timer(4.0, delayed).start()

# ── REFER / REFERRAL LOGIC (ASYNC) ──────────────────────────────────────────

def generate_referral_code(user) -> str:
    return str(user.id)

async def get_referral_points_setting() -> int:
    """
    GET /referral_settings.json → extract "points_per_referral"
    """
    url = REAL_DB_URL.rstrip("/") + "/referral_settings.json"
    try:
        async with aiohttp_session.get(url) as resp:
            if resp.status == 200:
                settings = await resp.json() or {}
                try:
                    return int(settings.get("points_per_referral", 17))
                except:
                    return 17
            else:
                return 17
    except:
        return 17

async def register_user(user) -> str:
    """
    1) Ensure /users/<user_id>.json = true (no need to GET /users.json first)
    2) Read /referrals/<user_id>.json:
       • If exists, return its referral_code.
       • If not, create it and return new code.
    """
    user_id = str(user.id)
    logging.info(f"Registering user ID: {user_id}")

    # 1) Write user record
    await patch_node("users", { user_id: True })

    # 2) Fetch referral record
    rec = await read_node(f"referrals/{user_id}")
    if rec and "referral_code" in rec:
        # Already existed; rewrite to ensure consistency
        await patch_node(f"referrals/{user_id}", rec)
        return rec["referral_code"]
    else:
        code = generate_referral_code(user)
        new_data = {
            "referral_code": code,
            "referral_points": 0,
            "referred_users": []
        }
        await patch_node(f"referrals/{user_id}", new_data)
        return code

async def add_referral(referrer_code: str, new_user_id: str) -> bool:
    """
    1) Shallow GET /referrals.json?shallow=true → get keys only
    2) For each key → GET /referrals/<key>.json → check referral_code
    3) If found and valid, modify that record and PATCH it back.
    """
    shallow_url = REAL_DB_URL.rstrip("/") + "/referrals.json?shallow=true"
    try:
        async with aiohttp_session.get(shallow_url) as resp:
            if resp.status == 200:
                keys_only = await resp.json() or {}
            else:
                text = await resp.text()
                logging.error(f"add_referral shallow HTTP {resp.status}: {text}")
                return False
    except Exception as e:
        logging.error(f"add_referral shallow exception: {e}")
        return False

    referrer_id = None
    for candidate in keys_only.keys():
        try:
            async with aiohttp_session.get(REAL_DB_URL.rstrip("/") + f"/referrals/{candidate}.json") as r2:
                if r2.status == 200:
                    rec = await r2.json() or {}
                    if rec.get("referral_code") == referrer_code:
                        referrer_id = candidate
                        break
        except:
            continue

    if not referrer_id or new_user_id == referrer_id:
        return False

    record = await read_node(f"referrals/{referrer_id}")
    if not record:
        return False

    referred = record.get("referred_users", [])
    if new_user_id in referred:
        return False

    referred.append(new_user_id)
    record["referred_users"] = referred

    pts = record.get("points_per_referral")
    if pts is None:
        pts = await get_referral_points_setting()
    record["referral_points"] = record.get("referral_points", 0) + pts

    await patch_node(f"referrals/{referrer_id}", record)
    return True

# --------------------- Button Buy With Points On/Off Refer.py below ----------------------

async def get_buy_with_points_setting() -> bool:
    """
    Async: Returns the boolean value of /referral_settings/buy_with_points_enabled.
    Defaults to True if missing or on error.
    """
    data = await read_node("referral_settings")
    if not isinstance(data, dict):
        return True
    # If key missing, default to True:
    return bool(data.get("buy_with_points_enabled", True))

# --------------------- Button Free Trial On/Off below ----------------------

async def get_free_trial_enabled() -> bool:
    """
    Async: Returns True if /referral_settings/free_trial_enabled is True.
    Defaults to False if missing or error.
    """
    data = await read_node("referral_settings")
    if not isinstance(data, dict):
        # If no data at all, default to False
        return False
    return bool(data.get("free_trial_enabled", False))
    
# --------------------- Out-of-Stock Helper ---------------------
async def handle_out_of_stock(client, callback_query):
    logging.info("No credentials => out_of_stock => user: %s", callback_query.from_user.id)

    # Async fetch of /ui_config/out_of_stock
    ui = await read_ui_config("out_of_stock")
    gif_url = ui.get("gif_url", "").replace("\\n", "\n")
    messages = ui.get("messages", [])
    if not messages:
        messages = ["Out of stock!", "Please wait..."]

    # Enqueue the GIF first
    message_queue.put_nowait((
        client.send_animation,
        [callback_query.message.chat.id],
        {"animation": gif_url}
    ))

    # Schedule each line with a 2s interval
    def send_line(i):
        message_queue.put_nowait((
            client.send_message,
            [callback_query.message.chat.id],
            {"text": messages[i]}
        ))

    for i in range(len(messages)):
        Timer(2.0 * (i + 1), send_line, args=[i]).start()

    await callback_query.answer()

def check_paytm_server():
    return True

# aiohttp

def get_admin_config():
    try:
        url = REAL_DB_URL + "admin_config.json"
        resp = requests.get(url)
        return resp.json() or {}
    except Exception:
        return {}

admin_config = get_admin_config()

superior_admins = admin_config.get("superior_admins", [])
if not isinstance(superior_admins, list):
    superior_admins = [superior_admins]
superior_admins = [str(x) for x in superior_admins]

inferior_admins = admin_config.get("inferior_admins", [])
if not isinstance(inferior_admins, list):
    inferior_admins = [inferior_admins]
inferior_admins = [str(x) for x in inferior_admins]

def format_slot_time(dt_str):
    """
    Convert a datetime string in the format '%Y-%m-%d %H:%M:%S'
    to a string formatted as '3 PM 12 MARCH'.
    If parsing fails, returns the original string.
    """
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%-I %p %d %B").upper()
    except Exception:
        return dt_str  # fallback if parsing fails

# --------------------- htmltocss api ---------------------

def html_to_png_url(html: str, timings: dict) -> str:
    DEMO_URL = "https://api-html2image.onrender.com/convert"
    headers = {
        "Accept":       "*/*",
        "Content-Type": "application/json",
        "X-API-KEY":    INTERNAL_API_KEY,
    }
    payload = {
        "html":              html,
        "selector":          "#qr-container",
        "css":               "",
        "url":               "",
        "console_mode":      "",
        "ms_delay":          "",
        "render_when_ready": "false",
        "viewport_width":    "",
        "viewport_height":   "",
        "google_fonts":      "",
        "device_scale":      ""
    }

    t0 = time.perf_counter()
    resp = requests.post(DEMO_URL, headers=headers, json=payload)
    resp.raise_for_status()
    timings['post_ms'] = int((time.perf_counter() - t0) * 1000)

    data = resp.json()
    img_url = data.get("url") or data.get("data", {}).get("url")
    if not img_url:
        raise RuntimeError("No image URL returned: " + str(data))

    return img_url + ".png"

# --------------------- BOT Handlers ---------------------
@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = str(message.from_user.id)
    user = message.from_user

    # ── 1) Only fetch /users.json and add this user ───────────────────────────
    users_node = await read_users_node()  # async call to fetch users (one level)
    if not isinstance(users_node, dict):
        users_node = {}
    if user_id not in users_node:  # if they aren’t already present
        await patch_node("users", { user_id: True })  # PATCH /users.json → { user_id: true }

    # ── 2) Referral logic (calls optimized helpers below) ─────────────────────
    args = message.text.split()
    referral = args[1].strip().upper() if len(args) > 1 else None
    my_code = await register_user(user)       # no change inside register_user()
    if referral:
        await add_referral(referral, user_id) # use async version of add_referral()

    # ── 3) UI config: fetch only /ui_config/start_command.json ──────────────
    ui = await read_ui_config("start_command")        # async GET
    welcome_text = ui.get("welcome_text", "🎟 Welcome!").replace("\\n", "\n")
    photo_url    = ui.get("welcome_photo") \
                   or "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcScpM1VdgS6eOpxhlnB0d7tR6KVTUBm5DW_1wQthTtS33QOT3ksJsU4yZU&s=10"

    buttons = ui.get("buttons", [])
    if buttons:
        kb = []
        for b in buttons:
            txt = b.get("text", "Button").replace("\\n", "\n")
            cb  = b.get("callback_data", "no_callback")
            if cb == "crunchyroll":
                cb = "book_slot"
            kb.append([InlineKeyboardButton(txt, callback_data=cb)])
        markup = InlineKeyboardMarkup(kb)
    else:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("᪤ Crunchyroll", callback_data="book_slot")],
            [InlineKeyboardButton("🆘 Help",           callback_data="help")]
        ])

    message_queue.put_nowait((
        client.send_photo,
        [message.chat.id],
        {
            "photo": photo_url,
            "caption": welcome_text,
            "reply_markup": markup
        }
    ))


@app.on_callback_query(filters.regex("^start$"))
async def buy_again_handler(client, callback_query):
    # 1) Acknowledge the button so Telegram doesn’t complain “QUERY_ID_INVALID”
    await callback_query.answer()

    # 2) Create a tiny fake Message whose .text == "/start"
    class _FakeMsg:
        def __init__(self, chat, from_user):
            self.chat = chat
            self.from_user = from_user
            self.text = "/start"

    fake_message = _FakeMsg(
        chat=callback_query.message.chat,
        from_user=callback_query.from_user
    )

    # 3) Call your existing /start logic
    await start_command(client, fake_message)
    
    
    
@app.on_message(filters.command("myreferral"))
async def my_referral(client, message):
    user_id = message.from_user.id
    info = await get_referral_info(user_id)
    if info is None:
        await message.reply_text("No referral info found. Please register using /start.")
        return

    referral_code = info.get("referral_code", "N/A")
    points = info.get("referral_points", 0)
    referred = info.get("referred_users", [])
    me = await client.get_me()
    bot_username = me.username
    referral_link = f"https://t.me/{bot_username}?start={referral_code}"
    required_points = await get_required_points()   # ← directly await the async function

    text = (
       f"𝘞𝘦𝘭𝘤𝘰𝘮𝘦 𝘵𝘰 𝘵𝘩𝘦 𝙊𝙊𝙍𝙫𝙧𝙚𝙧𝙨𝙚!\n\n"
       f"🌟 𝗢𝗢𝗥𝗯𝗶𝘁𝘀 𝗖𝗼𝗹𝗹𝗲𝘤𝘁𝗲𝗱: {points}\n"
       f"🚀 𝗡𝗲𝘅𝘁 𝗨𝗻𝗹𝗼𝗰𝗸 𝗶𝗻: {required_points} 𝖮𝖮𝖱𝖻𝗂𝗍𝗌\n"
       f"👥 𝗖𝗿𝗲𝘄 𝗠𝗲𝗺𝗯𝗲𝗿𝘀: {len(referred)}\n"
       f"🪪 𝗬𝗼𝘂𝗿 𝗢𝗢𝗥𝘃𝗲𝗿𝘀𝗲 𝗖𝗢𝗗𝗘: {referral_code}\n\n"
       f"Ready to expand Your 𝗢𝗢𝗥𝘃𝗲𝗿𝘀𝗲 ?\n\n"
       f"𝘐𝘯𝘷𝘪𝘵𝘦 𝘺𝘰𝘶𝘳 𝘊𝘳𝘦𝘸 𝘶𝘴𝘪𝘯𝘨 𝘠𝘰𝘶𝘳 𝘓𝘪𝘯𝘬:\n"
       f"<a href='{referral_link}'>https://oorverse.com/join/{referral_code}</a>"
    )

    ui_ref_info = await read_ui_config("referral_info")
    photo_url = ui_ref_info.get(
        "photo_url",
        "https://raw.githubusercontent.com/OTTONRENT01/FOR-PHOTOS/refs/heads/main/Netflix-Refer.jpg"
    )

    await message.reply_photo(photo=photo_url, caption=text)

@app.on_message(filters.command("verify"))
def verify_handler(client, message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        message.reply_text("Usage: /verify <TXN-ID>")
        return

    txn_id = parts[1].strip()
    db_data = read_data()  # existing blocking read_data()

    transactions = db_data.get("transactions", {})
    txn_data = transactions.get(txn_id)

    if not txn_data:
        if txn_id.startswith("REF-"):
            ref_transactions = transactions.get("REF-ID", {})
            txn_data = ref_transactions.get(txn_id)
        elif txn_id.startswith("FTRIAL-"):
            ftrial_transactions = transactions.get("FTRIAL-ID", {})
            txn_data = ftrial_transactions.get(txn_id)

    if not txn_data:
        message.reply_text(f"𝗧𝗿𝗮𝗻𝘀𝗮𝗰𝘁𝗶𝗼𝗻 𝗜𝗗 :\n{txn_id}\n\n𝖤𝗋𝗋𝗈𝗋 : 🤖 𝗇𝗈𝗍 𝖿𝗈𝗎𝗇𝖽")
        return

    slot_id = txn_data.get("slot_id", "N/A")
    start_time_raw = txn_data.get("start_time", "N/A")
    end_time_raw = txn_data.get("end_time", "N/A")

    start_time_formatted = format_slot_time(start_time_raw)
    end_time_formatted = format_slot_time(end_time_raw)

    reply_text = (
        f"𝗧𝗫𝗡-𝗜𝗗 :\n{txn_id}\n\n"
        f"𝗦𝗟𝗢𝗧 :\n{slot_id}\n\n"
        f"𝗧𝗜𝗠𝗜𝗡𝗚 :\n{start_time_formatted} - {end_time_formatted}"
    )
    message.reply_text(reply_text)
    
    
    
@app.on_message(filters.command("stats"))
def stats(client, message):
    db_data = read_data()
    total_users = len(db_data.get("users", {}))
    stats_text = f"👤 𝙏𝙤𝙩𝙖𝙡 𝙐𝙨𝙚𝙧𝙨: {total_users}\n\n"
    stats_text += "📊 𝙎𝙡𝙤𝙩 𝙎𝙩𝙖𝙩𝙞𝙨𝙩𝙞𝙘𝙨:\n\n"

    # Define which slots to show:
    slots_to_show = ["slot_1"]  # Always show slot 1
    # Check if slot_2 is enabled in settings:
    settings = db_data.get("settings", {}).get("slots", {})
    slot2_info = settings.get("slot_2", {})
    if isinstance(slot2_info, dict) and slot2_info.get("enabled", False):
        slots_to_show.append("slot_2")

    # Loop over each slot in our list and build stats:
    for slot in slots_to_show:
        total = used = stock = 0
        for key, node in db_data.items():
            if is_credential(node) and node.get("belongs_to_slot") == slot:
                total += 1
                usage = int(node.get("usage_count", 0))
                max_usage = int(node.get("max_usage", 0))
                used += usage
                stock += (max_usage - usage)
        stats_text += f" ▸ 𝖲𝗅𝗈𝗍 {slot[-1]}:\n"
        stats_text += f"    • 𝘛𝘰𝘵𝘢𝘭 𝘊𝘳𝘦𝘥𝘦𝘯𝘵𝘪𝘢𝘭𝘴: {total}\n"
        stats_text += f"    • 𝘛𝘰𝘵𝘢𝘭 𝘜𝘴𝘦𝘥: {used}\n"
        stats_text += f"    • 𝘚𝘵𝘰𝘤𝘬 𝘓𝘦𝘧𝘵: {stock}\n\n"

    message.reply(stats_text)
    

ADMIN_USER_ID = 5300690945 # notified when someone request their /id

@app.on_message(filters.command("id"))
def show_user_id(client, message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or ""
    text = f"Your User ID is: `{user_id}`"
    client.send_message(ADMIN_USER_ID, f"{user_name} `{user_id}` requested their ID.")
    message.reply(text)

@app.on_message(filters.command("users"))
async def process_users_command(client, message):
    """
    Expected command format:
    /users <user_id> send <slot> credentials and used_orderids <order_id>

    Example:
      /users 20315957xx send slot_1 credentials and used_orderids T25030308080632745129xx
    """
    requester_id = message.from_user.id

    # 1) Fetch admin_config from Firebase (async)
    admin_conf = await read_node("admin_config")
    inferior_admins = admin_conf.get("inferior_admins", [])
    if not isinstance(inferior_admins, list):
        inferior_admins = [inferior_admins]
    superior_admins = admin_conf.get("superior_admins", [])
    if not isinstance(superior_admins, list):
        superior_admins = [superior_admins]

    uid_str = str(requester_id)
    if uid_str not in [str(x) for x in inferior_admins] and uid_str not in [str(x) for x in superior_admins]:
        await message.reply_text(
            "𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱 🚫\n"
            "𝘠𝘰𝘶 𝘥𝘰𝘯'𝘵 𝘩𝘢𝘷𝘦 𝘱𝘦𝘳𝘮𝘪𝘴𝘴𝘪𝘰𝘯 𝘵𝘰 𝘶𝘴𝘦 𝘵𝘩𝘪𝘴 𝘤𝘰𝘮𝘮𝘢𝘯𝘥."
        )
        return

    text = message.text

    # 2) Extract order_id: alphanumeric token of length ≥12
    order_ids = re.findall(r'\b[A-Za-z0-9]{12,}\b', text)
    if not order_ids:
        await message.reply_text("No valid order ID found in the command.")
        return
    order_id = order_ids[0]

    # 3) Extract target_user_id: 8–10 digit numeric token
    user_ids = re.findall(r'\b\d{8,10}\b', text)
    if not user_ids:
        await message.reply_text("No valid user ID found in the command.")
        return
    target_user_id = user_ids[0]

    # 4) Extract slot: token like "slot_1", default to "slot_1"
    slot_match = re.search(r'\bslot_\w+\b', text, re.IGNORECASE)
    slot_id = slot_match.group(0) if slot_match else "slot_1"

    try:
        target_user_id_int = int(target_user_id)
    except ValueError:
        await message.reply_text("𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝘁𝗮𝗿𝗴𝗲𝘁 𝘂𝘀𝗲𝗿 𝗜𝗗 𝗳𝗼𝗿𝗺𝗮𝘁.")
        return

    # 5) Mark <target_user_id> under /users node (async PATCH)
    await patch_node("users", { str(target_user_id_int): True })

    # 6) Check if order_id already used (sync)
    used = await asyncio.to_thread(is_orderid_used, order_id)
    if used:
        await message.reply_text("𝗧𝗿𝗮𝗻𝘀𝗮𝗰𝘁𝗶𝗼𝗻 𝗜𝗗 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝘂𝘀𝗲𝗱")
        return

    # 7) Validate transaction via Paytm API (sync inside to_thread)
    async def fetch_paytm_status(mid, oid):
        url = f"https://paytm.udayscriptsx.workers.dev/?mid={mid}&id={oid}"
        try:
            resp = requests.get(url, timeout=10)
            return resp.json() if resp.status_code == 200 else None
        except:
            return None

    paytm_data = await asyncio.to_thread(fetch_paytm_status, "RZUqNv45112793295319", order_id)
    if not paytm_data or paytm_data.get("STATUS") != "TXN_SUCCESS":
        await message.reply_text("𝗧𝗿𝗮𝗻𝘀𝗮𝗰𝘁𝗶𝗼𝗻 𝗻𝗼𝘁 𝘀𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹 🙁")
        return

    txn_amount_str = str(paytm_data.get("TXNAMOUNT", "0"))
    try:
        paid_amount = round(float(txn_amount_str), 2)
    except ValueError:
        paid_amount = 0.0

    # 8) Retrieve required_amount from /settings/slots/<slot_id> (async)
    slot_info = await read_node(f"settings/slots/{slot_id}")
    required_amount = float(slot_info.get("required_amount", 12))

    if abs(paid_amount - required_amount) > 0.001:
        await message.reply_text("𝗔𝗺𝗼𝘂𝗻𝘁 𝗺𝗶𝘀𝗺𝗮𝘁𝗰𝗵 ⚠️")
        return

    # 9) Validate target_user_id is a valid Telegram user (non-blocking)
    try:
        await client.get_users(target_user_id_int)
    except PeerIdInvalid:
        await message.reply_text("𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗨𝘀𝗲𝗿 𝗜𝗗 ❌")
        return

    # 10) Mark order_id as used (sync)
    await asyncio.to_thread(mark_orderid_used, order_id)

    # 11) Get a valid credential for this slot (sync)
    cred_key, cred_data = await asyncio.to_thread(get_valid_credential_for_slot, slot_id)
    if cred_data == "locked":
        await message.reply_text("Credentials for this slot are locked.")
        return
    if not cred_data:
        await message.reply_text("No available credentials for this slot.")
        return

    # 12) Fetch approve_flow UI config (async)
    ui = await read_node("ui_config/approve_flow")
    gif_url   = ui.get("gif_url", "").replace("\\n", "\n")
    succ_text = ui.get("success_text", "Payment Success ✅").replace("\\n", "\n")
    acct_fmt  = ui.get("account_format", "Email: {email}\nPassword: {password}").replace("\\n", "\n")

    # 13) Optionally send animation to the target user (via background queue)
    if gif_url:
        message_queue.put((
            client.send_animation,
            [target_user_id_int],
            {"animation": gif_url}
        ))
        # give time for animation to show
        await asyncio.sleep(2)

    # 14) Send credentials to <target_user_id>
    email       = cred_data["email"]
    password    = cred_data["password"]
    final_text  = f"{succ_text}\n\n{acct_fmt.format(email=email, password=password)}"

    message_queue.put((
        client.send_message,
        [target_user_id_int],
        {"text": final_text}
    ))

    # 15) Increment usage_count if below max_usage (sync)
    usage = int(cred_data.get("usage_count", 0))
    max_u = int(cred_data.get("max_usage", 0))
    if usage < max_u:
        new_usage = usage + 1
        # Async-invoke the sync updater
        await asyncio.to_thread(update_credential_usage, cred_key, new_usage)

    # 16) Confirm back to requester
    await message.reply_text("𝗖𝗿𝗲𝗱𝗲𝗻𝘁𝗶𝗮𝗹𝘀 𝘀𝗲𝗻𝘁 𝘀𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆! ✅")


COMMANDS = {
    "/cmd": "List all commands",
    "/verify": "Usage: /𝗏𝖾𝗋𝗂𝖿𝗒 [TXN-ID]",
    "/stats": "Show total users and slots",
    "/id": "To know userid and notify admin",
    "/users": "Usage: /𝗎𝗌𝖾𝗋𝗌 [orderid] [userid] and vice-versa if no specific slot_2 provide it will take by default send slot_1",
    "/givepoints": "Usage: /𝗀𝗂𝗏𝖾𝗉𝗈𝗂𝗇𝗍𝗌 [OORbits] to all users",
    "/setreferral and /cancel": "to set self or others OORverse code and OORbits value",
    "/top10": "To list down All Top 10 Crew members of OORverse",
    "/fileid and /cancel": "For extracting file ID from photo"
    # Add additional commands here.
}

@app.on_message(filters.command("cmd"))
def list_commands_handler(client, message):
    reply = "Available commands:\n\n"
    for cmd, desc in COMMANDS.items():
        reply += f"{cmd} - {desc}\n\n"
    message.reply_text(reply)

    
# aiohttp
    
@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = str(message.from_user.id)
    user = message.from_user

    # ── 1) Only fetch /users.json and add this user ───────────────────────────
    users_node = await read_users_node()  # async call to fetch users (one level)
    if not isinstance(users_node, dict):
        users_node = {}
    if user_id not in users_node:  # if they aren’t already present
        await patch_node("users", { user_id: True })  # PATCH /users.json → { user_id: true }

    # ── 2) Referral logic (calls optimized helpers below) ─────────────────────
    args = message.text.split()
    referral = args[1].strip().upper() if len(args) > 1 else None
    my_code = await register_user(user)       # no change inside register_user()
    if referral:
        await add_referral(referral, user_id) # use async version of add_referral()

    # ── 3) UI config: fetch only /ui_config/start_command.json ──────────────
    ui = await read_ui_config("start_command")        # async GET
    welcome_text = ui.get("welcome_text", "🎟 Welcome!").replace("\\n", "\n")
    photo_url    = ui.get("welcome_photo") \
                   or "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcScpM1VdgS6eOpxhlnB0d7tR6KVTUBm5DW_1wQthTtS33QOT3ksJsU4yZU&s=10"

    # build inline keyboard from UI config if present,
    # otherwise default to “᪤ Crunchyroll” → book_slot and “🆘 Help”
    buttons = ui.get("buttons", [])
    if buttons:
        kb = []
        for b in buttons:
            txt = b.get("text", "Button").replace("\\n", "\n")
            cb  = b.get("callback_data", "no_callback")
            # override legacy "crunchyroll" callback to "book_slot"
            if cb == "crunchyroll":
                cb = "book_slot"
            kb.append([InlineKeyboardButton(txt, callback_data=cb)])
    else:
        kb = [
            [InlineKeyboardButton("᪤ Crunchyroll", callback_data="book_slot")],
            [InlineKeyboardButton("🆘 Help",           callback_data="help")]
        ]

    # enqueue send_photo without awaiting
    message_queue.put_nowait((
        client.send_photo,
        [message.chat.id],
        {
            "photo": photo_url,
            "caption": welcome_text,
            "reply_markup": InlineKeyboardMarkup(kb)
        }
    ))
    
async def buy_again_handler(client, callback_query):

    await callback_query.answer()

    class _FakeMsg:
        def __init__(self, chat, from_user):
            self.chat = chat
            self.from_user = from_user
            self.text = "/start"

    fake_message = _FakeMsg(
        chat=callback_query.message.chat,
        from_user=callback_query.from_user
    )


    await start_command(client, fake_message)
    
    

@app.on_callback_query(filters.regex("^help$"))
async def help_callback(client, callback_query):
    ui = get_ui_config("help")
    help_text = ui.get("help_text", "Contact support @letmebeunknownn").replace("\\n", "\n")
    message_queue.put_nowait((
        client.send_message,
        [callback_query.message.chat.id],
        {"text": help_text}
    ))
    await callback_query.answer()

@app.on_callback_query(filters.regex("^book_slot$"))
async def book_slot_handler(client, callback_query):
    # Immediately schedule the booking action as a coroutine
    asyncio.create_task(book_slot_action(client, callback_query))
    await callback_query.answer()


async def book_slot_action(client, callback_query):
    # Async fetch of /settings/slots.json
    settings = await read_node("settings")
    all_slots = settings.get("slots", {})

    # Async fetch of /ui_config/slot_booking.json
    ui = await read_ui_config("slot_booking")
    photo_url = ui.get("photo_url", "")
    caption = ui.get("caption", "").replace("\\n", "\n")
    kb = []

    for slot_id, slot_info in all_slots.items():
        if not isinstance(slot_info, dict):
            continue
        if not slot_info.get("enabled", False):
            continue

        label = slot_info.get("name", slot_id)
        cb_data = f"choose_slot_{slot_id}"
        kb.append([InlineKeyboardButton(label, callback_data=cb_data)])

    if not kb:
        default_cb = ui.get("callback_data", "confirm_slot")
        kb.append([InlineKeyboardButton("No Slots Available", callback_data=default_cb)])

    message_queue.put_nowait((
        client.send_photo,
        [callback_query.message.chat.id],
        {
            "photo": photo_url,
            "caption": caption,
            "reply_markup": InlineKeyboardMarkup(kb)
        }
    ))


async def show_locked_message(client, chat_id):
    ui = await read_ui_config("locked_flow")
    locked_text = ui.get("locked_text", "⚠️ No available credentials at the moment.\nPlease contact support.").replace("\\n", "\n")

    message_queue.put_nowait((
        client.send_message,
        [chat_id],
        {"text": locked_text}
    ))

# --- In your global scope, add a simple cache dict ---
ui_cache: dict[str, tuple[dict, float]] = {}  # e.g. { "confirmation_flow": (data, last_fetch_ts) }

async def get_cached_confirmation_ui() -> dict:
    # If cached recently, return it
    if "confirmation_flow" in ui_cache:
        data, ts = ui_cache["confirmation_flow"]
        if time.time() - ts < 60:  # 60 seconds TTL
            return data

    # Otherwise, hit Firebase once:
    data = await read_node("ui_config/confirmation_flow")
    ui_cache["confirmation_flow"] = (data, time.time())
    return data

# @app.on_callback_query(filters.regex("^choose_slot_"))
# async def choose_slot(client, callback_query):
    # await callback_query.answer()
    # user_id = callback_query.from_user.id
    # slot_id = callback_query.data.replace("choose_slot_", "")

    # # Credential (off‐path or cached if you implement slot‐credential cache)
    # cred_key, cred_data = await asyncio.to_thread(get_valid_credential_for_slot, slot_id)
    # if cred_data == "locked":
        # await show_locked_message(client, callback_query.message.chat.id)
        # return
    # if not cred_data:
        # await handle_out_of_stock(client, callback_query)
        # return

    # user_slot_choice[user_id] = slot_id
    # logger.info(f"User {user_id} chose slot: {slot_id}")

    # await confirm_slot_action(client, callback_query)


# async def confirm_slot_action(client, callback_query):
    # user_id = str(callback_query.from_user.id)

    # # 1. Use the cache instead of fresh GET every time
    # ui = await get_cached_confirmation_ui()
    # photo_url = ui.get("photo_url", "").replace("\\n", "\n")
    # caption   = ui.get("caption", "💸 Choose Payment Method:").replace("\\n", "\n")

    # # 2. Build the keyboard
    # phonepe_btn_text = ui.get("button_text", "𝗣𝗁𝗈𝗇𝗲𝗣𝗲").replace("\\n", "\n")
    # phonepe_cb       = ui.get("callback_data", "phonepe")
    # keyboard_rows    = [[InlineKeyboardButton(phonepe_btn_text, callback_data=phonepe_cb)]]

    # # 3. Buy with Points: now correctly awaited instead of async→thread
    # if await get_buy_with_points_setting():
        # keyboard_rows.append([
            # InlineKeyboardButton("Buy 𝗐𝗂𝗍𝗁 𝖮𝖮𝖱𝖻𝗂𝗍𝗌", callback_data="buy_with_points")
        # ])

    # # 4. Free Trial & free_trial_claims combined in one call
    # referral_task    = asyncio.create_task(read_node("referral_settings"))
    # free_trials_task = asyncio.create_task(read_node("free_trial_claims"))
    # referral_data, free_trials_node = await asyncio.gather(referral_task, free_trials_task)

    # if referral_data.get("free_trial_enabled", False):
        # if not isinstance(free_trials_node, dict):
            # free_trials_node = {}
        # if user_id not in free_trials_node:
            # keyboard_rows.append([
                # InlineKeyboardButton("𝖦𝖾𝗍 𝖥𝗋𝖾𝖾 𝖳𝗋𝗂𝖺𝗅", callback_data="free_trial")
            # ])

    # kb = InlineKeyboardMarkup(keyboard_rows)

    # # 5. Send the photo or fallback message immediately
    # if photo_url:
        # await client.send_photo(
            # chat_id=callback_query.message.chat.id,
            # photo=photo_url,
            # caption=caption,
            # reply_markup=kb
        # )
    # else:
        # await client.send_message(
            # chat_id=callback_query.message.chat.id,
            # text=caption,
            # reply_markup=kb
        # )

# ── Global cache for UI, storing (data, timestamp, version_str) ─────────────
# Global cache: maps slot name to (data, timestamp, version)
# ── In-memory caches ─────────────────────────────────
# ref_cache: dict[str, tuple[dict, float, str]]  = {}
# free_cache: dict[str, tuple[dict, float, str]] = {}

# async def get_versioned_referral_settings() -> tuple[dict, bool]:
    # raw_ver = await read_node("referral_settings/version")
    # db_v    = str(raw_ver) if isinstance(raw_ver, str) else ""
    # data, ts, cv = ref_cache.get("referral_settings", ({},0.0,""))
    # age = time.time()-ts
    # if db_v and db_v==cv and age<3600:
        # return data, True
    # # otherwise reload
    # fresh = await read_node("referral_settings") or {}
    # ref_cache["referral_settings"] = (fresh, time.time(), db_v)
    # return fresh, False

# async def get_versioned_free_trial_claims() -> tuple[dict, bool]:
    # raw_ver = await read_node("free_trial_claims/version")
    # db_v    = str(raw_ver) if isinstance(raw_ver, str) else ""
    # data, ts, cv = free_cache.get("free_trial_claims", ({},0.0,""))
    # age = time.time()-ts
    # if db_v and db_v==cv and age<3600:
        # return data, True
    # fresh = await read_node("free_trial_claims") or {}
    # free_cache["free_trial_claims"] = (fresh, time.time(), db_v)
    # return fresh, False
    
# Caches for referral and free-trial
ref_cache: dict[str, tuple[dict, float, str]]  = {}
free_cache: dict[str, tuple[dict, float, str]] = {}

# ── Versioned cache helper for referral_settings ────────────────────────────
async def get_versioned_referral_settings() -> tuple[dict, bool]:
    """
    Returns (data, from_cache):
      • from_cache=True if version==cached_version AND age<60 min
      • from_cache=False otherwise
    """
    # 1) Fetch version
    raw_ver = await read_node("referral_settings/version")
    db_v    = str(raw_ver) if isinstance(raw_ver, str) else ""
    logger.debug(f"[RefCache] db_version={db_v!r}")

    # 2) Unpack cache
    data, ts, cv = ref_cache.get("referral_settings", ({}, 0.0, ""))
    age = time.time() - ts
    logger.debug(f"[RefCache] cache_version={cv!r}, age={int(age)}s")

    # 3) Cache hit?
    if db_v and db_v == cv and age < 3600:
        logger.info(f"[RefCache] HIT (version={db_v!r}, age={int(age)}s)")
        return data, True

    # 4) Cache miss → reload
    reason = []
    if not cv:
        reason.append("no cached_version")
    elif db_v != cv:
        reason.append("version changed")
    elif age >= 3600:
        reason.append("TTL expired")
    logger.info(f"[RefCache] RELOAD because {', '.join(reason)}")

    # 5) Fetch full node
    fresh = await read_node("referral_settings") or {}
    # 6) Update cache
    ref_cache["referral_settings"] = (fresh, time.time(), db_v)
    return fresh, False


# ── Versioned cache helper for free_trial_claims ────────────────────────────
async def get_versioned_free_trial_claims() -> tuple[dict, bool]:
    """
    Returns (data, from_cache):
      • from_cache=True if version==cached_version AND age<60 min
      • from_cache=False otherwise
    """
    raw_ver = await read_node("free_trial_claims/version")
    db_v    = str(raw_ver) if isinstance(raw_ver, str) else ""
    logger.debug(f"[FreeCache] db_version={db_v!r}")

    data, ts, cv = free_cache.get("free_trial_claims", ({}, 0.0, ""))
    age = time.time() - ts
    logger.debug(f"[FreeCache] cache_version={cv!r}, age={int(age)}s")

    if db_v and db_v == cv and age < 3600:
        logger.info(f"[FreeCache] HIT (version={db_v!r}, age={int(age)}s)")
        return data, True

    reason = []
    if not cv:
        reason.append("no cached_version")
    elif db_v != cv:
        reason.append("version changed")
    elif age >= 3600:
        reason.append("TTL expired")
    logger.info(f"[FreeCache] RELOAD because {', '.join(reason)}")

    fresh = await read_node("free_trial_claims") or {}
    free_cache["free_trial_claims"] = (fresh, time.time(), db_v)
    return fresh, False   
    


ui_cache: dict[str, tuple[dict, float, str]] = {}

async def get_versioned_confirmation_ui() -> tuple[dict, bool]:
    """
    Checks version and returns either:
    - (cached UI, True) if version unchanged and cache age < 60min
    - (fresh UI, False) if version changed or TTL expired
    """
    # 1) Read latest version from DB
    raw_ver = await read_node("ui_config/confirmation_flow/version")
    db_version = str(raw_ver) if isinstance(raw_ver, str) else ""

    # 2) Pull current cached version
    data, ts, cached_version = ui_cache.get("confirmation_flow", ({}, 0.0, ""))
    age = time.time() - ts

    # 3) If version matches + TTL OK, return from cache
    if db_version and db_version == cached_version and age < 3600:
        logger.info(f"[Cache] HIT (version={db_version!r}, age={int(age)}s)")
        return data, True

    # 4) Log reason for reload
    reason = []
    if not cached_version:
        reason.append("no cached_version")
    elif db_version != cached_version:
        reason.append("version changed")
    elif age >= 3600:
        reason.append("TTL expired")

    logger.info(f"[Cache] RELOAD because {', '.join(reason)}")

    # 5) Fetch full confirmation UI config
    fresh = await read_node("ui_config/confirmation_flow")
    if not isinstance(fresh, dict):
        fresh = {}

    # 6) Update in-memory cache
    ui_cache["confirmation_flow"] = (fresh, time.time(), db_version)
    return fresh, False
    
    
# ── Handlers ────────────────────────────────────────────────────────────────

@app.on_callback_query(filters.regex("^choose_slot_"))
async def choose_slot(client, callback_query):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    slot_id = callback_query.data.replace("choose_slot_", "")

    # ── 1) Check credential ───────────────────────────────────────────────────
    cred_key, cred_data = await asyncio.to_thread(get_valid_credential_for_slot, slot_id)
    if cred_data == "locked":
        await show_locked_message(client, callback_query.message.chat.id)
        return
    if not cred_data:
        await handle_out_of_stock(client, callback_query)
        return

    user_slot_choice[user_id] = slot_id
    logger.info(f"User {user_id} chose slot: {slot_id}")

    await confirm_slot_action(client, callback_query)
    
    
async def confirm_slot_action(client, callback_query):
    """
    1) Load UI, referral_settings & free_trial_claims in parallel (all versioned)
    2) Build & send the “Choose Payment Method” screen
    """
    user_id   = str(callback_query.from_user.id)
    start_all = time.time()

    # ── 1) Kick off all three versioned‐cache helpers in parallel ─────────────
    t0 = time.time()
    ui_task    = asyncio.create_task(get_versioned_confirmation_ui())
    ref_task   = asyncio.create_task(get_versioned_referral_settings())
    free_task  = asyncio.create_task(get_versioned_free_trial_claims())

    (ui,   is_ui_cache), \
    (ref,  is_ref_cache), \
    (free, is_free_cache) = await asyncio.gather(ui_task, ref_task, free_task)

    t1 = time.time()
    total_fetch = int((t1 - t0) * 1000)
    logger.info(
        f"⏱[ConfirmSlot] Parallel fetch: {total_fetch} ms "
        f"(UI_cached={is_ui_cache}, Ref_cached={is_ref_cache}, Free_cached={is_free_cache})"
    )

    # ── 2) Build keyboard rows ─────────────────────────────────────────────────
    photo_url = ui.get("photo_url", "").replace("\\n", "\n")
    caption   = ui.get("caption",    "💸 Choose Payment Method:").replace("\\n", "\n")

    # PhonePe button
    keyboard_rows = [[
        InlineKeyboardButton(
            ui.get("button_text", "𝗣𝗁𝗈𝗇𝗲𝗣𝗲").replace("\\n", "\n"),
            callback_data=ui.get("callback_data", "phonepe")
        )
    ]]

    # Buy with points?
    if ref.get("buy_with_points_enabled", True):
        keyboard_rows.append([
            InlineKeyboardButton("Buy 𝗐𝗂𝗍𝗁 𝖮𝖮𝖱𝖻𝗂𝗍𝗌", callback_data="buy_with_points")
        ])

    # Free trial?
    if ref.get("free_trial_enabled", False) and user_id not in free:
        keyboard_rows.append([
            InlineKeyboardButton("𝖦𝖾𝗍 𝖥𝗋𝖾𝖾 𝖳𝗋𝖎𝖺𝗅", callback_data="free_trial")
        ])

    # ── 3) Send the screen ────────────────────────────────────────────────────
    kb  = InlineKeyboardMarkup(keyboard_rows)
    t2  = time.time()
    if photo_url:
        await client.send_photo(
            chat_id=callback_query.message.chat.id,
            photo=photo_url,
            caption=caption,
            reply_markup=kb
        )
    else:
        await client.send_message(
            chat_id=callback_query.message.chat.id,
            text=caption,
            reply_markup=kb
        )
    t3 = time.time()

    logger.info(f"⏱[ConfirmSlot] Send:    {int((t3 - t2)*1000)} ms")
    logger.info(f"⏱[ConfirmSlot] Total:   {int((t3 - start_all)*1000)} ms")
    
# async def confirm_slot_action(client, callback_query):
    # """
    # 1) Load UI via versioned cache
    # 2) Load referral_settings once
    # 3) Conditionally load free_trial_claims
    # 4) Build & send the “Choose Payment Method” screen
    # """
    # user_id   = str(callback_query.from_user.id)
    # # Start full timing from user click
    # start_all = time.time()

# # ── 1) Fetch UI via versioned cache ──────────────────────────────────────
    # t0 = time.time()
    # ui, is_cache = await get_versioned_confirmation_ui()
    # t1 = time.time()
    # fetch_ui_ms = int((t1 - t0) * 1000)

    # if is_cache:
      # logger.info(f"⏱[ConfirmSlot] UI   fetch: 0 ms (from memory cache)")
    # else:
      # logger.info(f"⏱[ConfirmSlot] UI   fetch: {fetch_ui_ms} ms (from Firebase)")

    # photo_url = ui.get("photo_url", "").replace("\\n", "\n")
    # caption   = ui.get("caption", "💸 Choose Payment Method:").replace("\\n", "\n")

    # # ── Build the PhonePe button ─────────────────────────────────────────────
    # phonepe_btn_text = ui.get("button_text", "𝗣𝗁𝗈𝗇𝗲𝗣𝗲").replace("\\n", "\n")
    # phonepe_cb       = ui.get("callback_data", "phonepe")
    # keyboard_rows    = [[InlineKeyboardButton(phonepe_btn_text, callback_data=phonepe_cb)]]

    # # ── 2) Fetch referral_settings once ─────────────────────────────────────
    # t2 = time.time()
    # referral_data, _ = await get_versioned_referral_settings()
    # t3 = time.time()
    # if not isinstance(referral_data, dict):
        # referral_data = {}
    # logger.info(f"⏱[ConfirmSlot] Ref  fetch: {int((t3 - t2)*1000)} ms")

    # # 2a) “Buy with Points” if enabled (default True)
    # if bool(referral_data.get("buy_with_points_enabled", True)):
        # keyboard_rows.append([
            # InlineKeyboardButton("Buy 𝗐𝗂𝗍𝗁 𝖮𝖮𝖱𝖻𝗂𝗍𝗌", callback_data="buy_with_points")
        # ])

    # # 2b) “Free Trial” only if enabled
    # needs_free = bool(referral_data.get("free_trial_enabled", False))
    # if needs_free:
        # t4 = time.time()
        # free_trials_node, _ = await get_versioned_free_trial_claims()
        # t5 = time.time()
        # if not isinstance(free_trials_node, dict):
            # free_trials_node = {}
        # logger.info(f"⏱[ConfirmSlot] Free fetch: {int((t5 - t4)*1000)} ms")

        # if user_id not in free_trials_node:
            # keyboard_rows.append([
                # InlineKeyboardButton("𝖦𝖾𝗍 𝖥𝗋𝖾𝖾 𝖳𝗋𝖎𝖺𝗅", callback_data="free_trial")
            # ])
    # else:
        # logger.info("⏱[ConfirmSlot] Free fetch: 0 ms (skipped)")

    # # ── 3) Send the screen ───────────────────────────────────────────────────
    # kb = InlineKeyboardMarkup(keyboard_rows)
    # t6 = time.time()

    # if photo_url:
        # await client.send_photo(
            # chat_id=callback_query.message.chat.id,
            # photo=photo_url,
            # caption=caption,
            # reply_markup=kb
        # )
    # else:
        # await client.send_message(
            # chat_id=callback_query.message.chat.id,
            # text=caption,
            # reply_markup=kb
        # )
    # t7 = time.time()
    # logger.info(f"⏱[ConfirmSlot] Send:    {int((t7 - t6)*1000)} ms")
    # logger.info(f"⏱[ConfirmSlot] Total:   {int((t7 - start_all)*1000)} ms")
# refer.py Logic
  

@app.on_callback_query(filters.regex("^buy_with_points$"))
async def buy_with_points_handler(client, callback_query):
    # 1) Check if the feature is enabled (correctly awaited)
    if not await get_buy_with_points_setting():
        await callback_query.answer(
            "OORverse feature is currently unavailable 🚀 Coming Soon..", show_alert=True
        )
        return

    # 2) Fetch user referral info using async DB
    user_id = str(callback_query.from_user.id)
    info = await get_referral_info(user_id)
    if info is None:
        await callback_query.answer(
            "No referral info found. Please register using /start.", show_alert=True
        )
        return

    # 3) Compose message content
    referral_code = info.get("referral_code", "N/A")
    points        = info.get("referral_points", 0)
    referred      = info.get("referred_users", [])

    me           = await client.get_me()
    bot_username = me.username
    referral_link = f"https://t.me/{bot_username}?start={referral_code}"

    # 4) Required points: if still sync, offload it. Otherwise convert get_required_points to async.
    required_points = await get_required_points()   # ← directly await the async function

    text = (
       f"𝘞𝘦𝘭𝘤𝘰𝘮𝘦 𝘵𝘰 𝘵𝘩𝘦 𝙊𝙊𝙍𝙫𝙚𝙧𝙨𝙚!\n\n"
       f"🌟 𝗢𝗢𝗥𝗯𝗶𝘁𝘀 𝗖𝗼𝗹𝗹𝗲𝗰𝘁𝗲𝗱: {points}\n"
       f"🚀 𝗡𝗲𝘅𝘁 𝗨𝗻𝗹𝗼𝗰𝗸 𝗶𝗻: {required_points} 𝖮𝖮𝖱𝖻𝗂𝗍𝗌\n"
       f"👥 𝗖𝗿𝗲𝘄 𝗠𝗲𝗺𝗯𝗲𝗿𝘀: {len(referred)}\n"
       f"🪪 𝗬𝗼𝘂𝗿 𝗢𝗢𝗥𝘃𝗲𝗿𝘀𝗲 𝗖𝗢𝗗𝗘: {referral_code}\n\n"
       f"Ready to expand Your 𝗢𝗢𝗥𝘃𝗲𝗿𝘀𝗲 ?\n\n"
       f"𝘐𝘯𝘷𝘪𝘵𝘦 𝘺𝘰𝘶𝘳 𝘊𝘳𝘦𝘸 𝘶𝘴𝘪𝘯𝘨 𝘠𝘰𝘶𝘳 𝘓𝘪𝘯𝘬:\n"
       f"<a href='{referral_link}'>https://oorverse.com/join/{referral_code}</a>"
    )

    # 5) Async UI fetch
    ui_ref_info = await read_ui_config("referral_info")
    photo_url   = ui_ref_info.get(
        "photo_url",
        "https://raw.githubusercontent.com/OTTONRENT01/FOR-PHOTOS/refs/heads/main/Netflix-Refer.jpg"
    )

    # 6) Reply buttons
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Get 𝖭𝖾𝗍𝖿𝗅𝗂𝗑 Account", callback_data="get_account")],
        [InlineKeyboardButton("Back", callback_data="back_to_confirmation")]
    ])

    # 7) Update media & buttons in place
    await callback_query.edit_message_media(
        media=InputMediaPhoto(media=photo_url, caption=text)
    )
    await callback_query.edit_message_reply_markup(reply_markup=keyboard)
    

@app.on_callback_query(filters.regex("^get_account$"))
async def get_account_handler(client, callback_query):
    # 1. Feature flag check (buy_with_points)
    if not await get_buy_with_points_setting():
        await callback_query.answer(
            "OORverse feature is currently unavailable 🚀 Coming Soon..", show_alert=True
        )
        return

    # 2. Referral info fetch
    user_id = str(callback_query.from_user.id)
    info = await get_referral_info(user_id)
    if info is None:
        await callback_query.answer(
            "𝖭𝗈 𝗋𝖾𝖿𝖾𝗋𝗋𝖺𝗅 𝗂𝗇𝖿𝗈 𝖿𝗈𝗎𝗇𝖽.\n𝖯𝗅𝖾𝖺𝗌𝖾 𝖽𝗈 /𝗌𝗍𝖺𝗋𝗍 𝖺𝗀𝖺𝗂𝗇 𝗍𝗈 𝗋𝖾𝗀𝗂𝗌𝗍𝖾𝗋 𝗂𝗇 𝖮𝖮𝖱𝗏𝖾𝗋𝗌𝖾",
            show_alert=True
        )
        return

    current_points = info.get("referral_points", 0)
    required_points = await get_required_points()   # ← directly await the async function

    if current_points < required_points:
        needed = required_points - current_points
        await callback_query.answer(
            f"𝖸𝗈𝗎 𝗇𝖾𝖾𝖽 {needed} 𝗆𝗈𝗋𝖾 𝗢𝗢𝗥𝗯𝗶𝘁𝘀 𝗍𝗈 𝗀𝖾𝗍 𝖺 𝖭𝖾𝗍𝖿𝗅𝗂𝗑 𝖠𝖼𝖼𝗈𝗎𝗇𝗍",
            show_alert=True
        )
        return

    # 3. Slot ID from in-memory user slot choice
    slot_id = user_slot_choice.get(callback_query.from_user.id, "slot_1")

    # 4. Check if user already claimed this slot today
    db_data     = await read_node("")  # root node
    account_claims = db_data.get("account_claims", {})
    user_claims    = account_claims.get(user_id, {})
    if user_claims.get(slot_id):
        await callback_query.answer(
            "𝖸𝗈𝗎 𝗁𝖺𝗏𝖾 𝖺𝗅𝗋𝖾𝖺𝖽𝗒 𝖼𝗅𝖺𝗂𝗆𝖾𝖽 𝖺 𝖭𝖾𝗍𝖿𝗅𝗂𝗑 𝖺𝖼𝖼𝗈𝗎𝗇𝗍 𝖿𝗈𝗋 𝗍𝗈𝖽𝖺𝗒'𝗌 𝗌𝗅𝗈𝗍 ! 😊 comeback 𝗍𝗈𝗆𝗈𝗋𝗋𝗈𝗐 𝖽𝗎𝗋𝗂𝗇𝗀 𝗈𝗎𝗋 𝗇𝖾𝗑𝗍 𝗍𝗂𝗆𝖾 𝗌𝗅𝗈𝗍.",
            show_alert=True
        )
        return

    # 5. Check for valid credential (sync)
    cred_key, cred_data = get_valid_credential_for_slot(slot_id)
    if cred_data == "locked":
        await show_locked_message(client, callback_query.message.chat.id)
        await callback_query.answer("Credentials locked.", show_alert=True)
        return
    if not cred_data:
        await handle_out_of_stock(client, callback_query)
        return

    # 6. Deduct referral points in async DB
    await patch_node(f"referrals/{user_id}", {
        "referral_points": current_points - required_points
    })

    # 7. Generate dummy ORDER ID
    rand_str = ''.join(random.choices(string.ascii_letters, k=5))
    dummy_order_id = f"REF-{user_id}-{datetime.now().strftime('%d-%m-%y')}-{rand_str}"
    payment_data = {"ORDERID": dummy_order_id}

    # 8. Run approval flow immediately
    do_approve_flow_immediate(client, callback_query.message, slot_id, payment_data)
    await asyncio.sleep(2)

    # 9. Record claim in DB
    await patch_node(f"account_claims/{user_id}", {
        slot_id: True
    })

    # 10. Send REF-ID
    await client.send_message(
        callback_query.message.chat.id,
        f"𝗬𝗼𝘂𝗿 𝗥𝗘𝗙-𝗜𝗗 𝗶𝘀:\n<code>{dummy_order_id}</code>\n\n"
        "(𝗉𝗅𝖾𝖺𝗌𝖾 𝗌𝗁𝖺𝗋𝖾 𝗍𝗁𝗂𝗌 𝖨𝖣 𝗐𝗂𝗍𝗁 𝗈𝗎𝗋 𝗌𝗎𝗉𝗉𝗈𝗋𝗍 𝗍𝖾𝖺𝗆 𝖿𝗈𝗋 𝗉𝗋𝗈𝗆𝗉𝗍 𝖺𝗌𝗌𝗂𝗌𝗍𝖺𝗇𝖼𝖾)",
        parse_mode=ParseMode.HTML
    )
  
  
  
@app.on_callback_query(filters.regex("^back_to_confirmation$"))
async def back_to_confirmation_handler(client, callback_query):
    # Load confirmation UI config (async)
    ui = await read_ui_config("confirmation_flow")
    photo_url = ui.get("photo_url", "")
    caption   = ui.get("caption", "💸 Choose Payment Method:").replace("\\n", "\n")
    phonepe_btn_text = ui.get("button_text", "𝗣𝗵𝗼𝗻𝗲𝗣𝗲").replace("\\n", "\n")
    phonepe_cb       = ui.get("callback_data", "phonepe")

    # Prepare keyboard rows dynamically
    keyboard_rows = [
        [InlineKeyboardButton(phonepe_btn_text, callback_data=phonepe_cb)]
    ]

    # Load DB-based toggle values via threadsafe sync
    if await get_buy_with_points_setting():
        keyboard_rows.append([
            InlineKeyboardButton("Buy 𝗐𝗂𝗍𝗁 𝖮𝖮𝖱𝖻𝗂𝗍𝗌", callback_data="buy_with_points")
        ])

    if await asyncio.to_thread(get_free_trial_enabled):
        keyboard_rows.append([
            InlineKeyboardButton("𝖦𝖾𝗍 𝖥𝗋𝖾𝖾 𝖳𝗋𝗂𝖺𝗅", callback_data="free_trial")
        ])

    # Build the InlineKeyboard
    keyboard = InlineKeyboardMarkup(keyboard_rows)

    # Replace the media and keyboard in the original message
    await callback_query.edit_message_media(
        media=InputMediaPhoto(media=photo_url, caption=caption)
    )
    await callback_query.edit_message_reply_markup(reply_markup=keyboard)
    
# refer.py End


# Free Trial
# ─── free_trial_handler ─────────────────────────────────────────────────────

@app.on_callback_query(filters.regex("^free_trial$"))
async def free_trial_handler(client, callback_query):
    # 1) “free_trial_enabled” is in /referral_settings
    settings = await read_node("referral_settings")
    enabled = bool(settings.get("free_trial_enabled", False))
    if not enabled:
        await callback_query.answer(
            "OORverse is currently unavailable 🚀 Coming Soon..", show_alert=True
        )
        return

    user_id = str(callback_query.from_user.id)

    # 2) “claim status” is at /free_trial_claims/<user_id>
    claimed = await read_node(f"free_trial_claims/{user_id}")
    if claimed:  # if that node exists & truthy, user already claimed
        await callback_query.answer("You have already claimed your free trial.", show_alert=True)
        return

    # 3) Only now that we know they haven't claimed,
    #    we might need slot_end info → that’s in /settings/slots/<slot_id>
    #    (fetch that small subtree, not the entire DB)
    slot_id   = user_slot_choice.get(int(user_id), "slot_1")
    slot_info = await read_node(f"settings/slots/{slot_id}")  # JSON: { "name": ..., "slot_end": "…" }
    slot_end_str = slot_info.get("slot_end", "N/A")
    end_label    = format_slot_time(slot_end_str)

    # 4) Build your new media/text/buttons exactly as before…
    new_caption = (
        f"𝘞𝘦𝘭𝘤𝘰𝘮𝘦 𝘵𝘰 𝘵𝘩𝘦 𝙊𝙊𝙍𝙫𝙚𝙧𝙨𝙚!\n\n"
        "𝖳𝗈 continue enjoying our service beyond your trial, simply select 𝖯𝗁𝗈𝗇𝖾𝖯𝖾 as your preferred option.\n\n"
        f"𝗬𝗈𝘂𝗋 𝘁𝗋𝗂𝖺𝗅 𝗎𝗍𝗈-𝗅𝖾𝗇𝖽: {end_label}"
    )

    ui_trial_info = await read_ui_config("freetrial_info")
    photo_url     = ui_trial_info.get(
        "photo_url",
        "https://raw.githubusercontent.com/OTTONRENT01/FOR-PHOTOS/refs/heads/main/Netflix-FreeTrial.jpg"
    )
    new_keyboard  = InlineKeyboardMarkup([
        [InlineKeyboardButton("Get 𝖭𝖾𝗍𝖿𝗅𝗂𝗑 Account", callback_data="get_trial")],
        [InlineKeyboardButton("Back",              callback_data="back_to_confirmation")]
    ])

    await callback_query.edit_message_media(
        media=InputMediaPhoto(media=photo_url, caption=new_caption)
    )
    await callback_query.edit_message_reply_markup(reply_markup=new_keyboard)


# Free trial
# get trial code
# ─── get_trial_handler ───────────────────────────────────────────────────────

@app.on_callback_query(filters.regex("^get_trial$"))
async def get_trial_handler(client, callback_query):
    # 1) Feature‐flag check
    if not await get_free_trial_enabled():
        await callback_query.answer(
            "OORverse feature is currently unavailable 🚀 Coming Soon..", show_alert=True
        )
        return

    user_id = str(callback_query.from_user.id)
    slot_id = user_slot_choice.get(int(user_id), "slot_1")

    # 2) “Have they already claimed free trial?” → fetch only /free_trial_claims/<user_id>
    claimed_node = await read_node(f"free_trial_claims/{user_id}")
    if claimed_node:  # if truthy, they already claimed
        await callback_query.answer("You have already claimed your free trial.", show_alert=True)
        return

    # 3) Check credential availability (same synchronous call)
    cred_key, cred_data = get_valid_credential_for_slot(slot_id)
    if cred_data == "locked":
        show_locked_message(client, callback_query.message.chat.id)
        await callback_query.answer("Credentials locked.", show_alert=True)
        return
    if not cred_data:
        await handle_out_of_stock(client, callback_query)
        return

    # 4) Generate dummy ORDERID + do approval flow
    rand_str     = ''.join(random.choices(string.ascii_letters, k=5))
    dummy_order  = f"FTRIAL-{user_id}-{datetime.now().strftime('%d-%m-%y')}-{rand_str}"
    payment_data = {"ORDERID": dummy_order}

    await do_approve_flow_immediate(client, callback_query.message, slot_id, payment_data)
    await asyncio.sleep(2)

    # 5) Mark “/free_trial_claims/<user_id> = true”
    await patch_node("free_trial_claims", { user_id: True })

    # 6) Send the user their dummy ORDERID
    await client.send_message(
        callback_query.message.chat.id,
        f"𝗬𝗈𝘂𝗋 𝗙𝗧𝗥𝗜𝗔𝗅-𝗜𝗗 𝗂𝗌:\n<code>{dummy_order}</code>\n\n"
        "(𝗉𝗅𝖾𝖺𝗌𝖾 𝗌𝗁𝖺𝗋𝖾 𝗍𝗁𝗂𝗌 𝖨𝖣 𝗐𝗂𝗍𝗁 𝗈𝗎𝗋 𝗌𝗎𝗉𝗉𝗈𝗋𝗍 𝗍𝖾𝖺𝗆 𝖿𝗈𝗋 𝗉𝗋𝗈𝗆𝗉𝗍 𝖺𝗌𝗌𝗂𝗌𝗍𝖺𝗇𝖼𝖾)",
        parse_mode=ParseMode.HTML
    )
# Free Trial end


# Global dictionary to store the timestamp when a user is asked for a txn ID.
pending_txn = {}  # Format: { user_id: datetime }

# In-memory
order_store = {}

async def auto_verify_payment(client, message, order_id: str):
    """
    Poll Paytm up to 60× (5 s apart), then:
      - on TXN_SUCCESS → approve/reject
      - on timeout → notify “could not confirm”
    """
    # 1) initial 8 s buffer
    await asyncio.sleep(8)

    for _ in range(60):
        info = order_store.get(order_id)
        if not info:
            # Order was cancelled or removed, stop polling.
            return

        # Paytm status call
        paytm_url = (
            f'https://securegw.paytm.in/order/status'
            f'?JsonData={{"MID":"{MID}","ORDERID":"{order_id}"}}'
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(paytm_url) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(5)
                        continue
                    data = await resp.json()
        except Exception as e:
            print(f"[auto_verify_payment] HTTP error: {e}")
            await asyncio.sleep(5)
            continue

        status     = data.get("STATUS", "")
        txn_amount = data.get("TXNAMOUNT", "0")

        # load admin bypass list from “/admin_config/superior_admins”
        admin_conf = await read_node("admin_config")
        admins = admin_conf.get("superior_admins", [])
        if not isinstance(admins, list):
            admins = [admins]
        admins = [str(x) for x in admins]
        bypass = str(info["user_id"]) in admins

        if status == "TXN_SUCCESS":
            # ── 2a) pull slot_id out of in‐memory order_store
            slot_id = info["slot_id"]

            # ── 2b) fetch exactly that slot’s settings
            slot_node = await read_node(f"settings/slots/{slot_id}")
            required  = float(slot_node.get("required_amount", 12))

            try:
                paid = round(float(txn_amount), 2)
            except:
                paid = 0.0

            if abs(paid - required) > 0.001 and not bypass:
                # amount mismatch → reject
                await do_reject_flow_immediate(client, message, "Amount mismatch.")
            else:
                # check if already used
                already_used = await asyncio.to_thread(is_orderid_used, order_id)
                if not already_used or bypass:
                    await asyncio.to_thread(mark_orderid_used, order_id)
                    # → approve payment
                    await do_approve_flow_immediate(client, message, slot_id, data)
                else:
                    await do_reject_flow_immediate(client, message, "Transaction already used.")

            # remove from in‐memory store and stop polling
            order_store.pop(order_id, None)
            return

        # still pending, wait 5 s and retry
        await asyncio.sleep(5)

    # ── 3) timeout (after ~5 minutes)
    if order_id in order_store:
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                f"⌛ Could not confirm payment automatically for order {order_id}.\n"
                "Please try again."
            )
        )
        order_store.pop(order_id, None)

# Keep track of active timers/polls so we can cancel them on refresh/cancel
countdown_tasks: dict[str, asyncio.Task] = {}

@app.on_callback_query(filters.regex(r"^phonepe$"))
async def show_phonepe(client, callback_query):
    user_id = callback_query.from_user.id
    slot_id = user_slot_choice.get(user_id, "slot_1")

    # ── 1) Async‐fetch just the required_amount for this slot ───────────────────
    # We call read_node("settings/slots/<slot_id>") to get only that slot’s dict.
    slot_info = await read_node(f"settings/slots/{slot_id}")
    # Fallback to 12 if something is missing
    try:
        amount = float(slot_info.get("required_amount", 12))
    except Exception:
        amount = 12.0

    # ── 2) Reserve an order_id (same as before) ─────────────────────────────────
    alphabet = string.ascii_uppercase + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(13))
    order_id = f"OOR{random_part}"
    order_store[order_id] = {
        "user_id":         user_id,
        "slot_id":         slot_id,
        "required_amount": amount,
        "timestamp":       time.time(),
    }

    # ── 3) Build UPI URL and styled QR (unchanged) ──────────────────────────────
    upi_url = (
        f"upi://pay?pa={UPI_ID}&am={amount}&pn={MERCHANT_NAME}"
        f"&tn={order_id}&tr={order_id}&tid={order_id}"
    )
    timings = {}
    t0 = time.perf_counter()
    qr = QRCodeStyled(
        version=None,
        error_correction=ERROR_CORRECT_H,
        border=0,
        box_size=20,
        image_factory=PilStyledImage,
        mask_pattern=None
    )
    buf = BytesIO()
    qr.get_image(data=upi_url, image=None, optimize=20).save(buf, kind="PNG")
    buf.seek(0)
    qr_img = Image.open(buf).convert("RGB")
    timings['qr_ms'] = int((time.perf_counter() - t0) * 1000)

    # invert + mask
    t1 = time.perf_counter()
    inv = ImageOps.invert(qr_img).convert("RGBA")
    inv.putdata([
        (0,0,0,0) if (r,g,b)==(0,0,0) else (r,g,b,255)
        for (r,g,b,_) in inv.getdata()
    ])
    timings['invert_ms'] = int((time.perf_counter() - t1) * 1000)

    # crop + logo
    t2 = time.perf_counter()
    w, h = inv.size
    cropped = inv.crop((2,2,w-2,h-2))
    resp_logo = requests.get(LOGO_URL)
    resp_logo.raise_for_status()
    logo = Image.open(BytesIO(resp_logo.content)).convert("RGBA")
    logo.thumbnail((int(cropped.width*0.33),)*2, Image.LANCZOS)
    x = (cropped.width - logo.width)//2
    y = (cropped.height - logo.height)//2
    hole = Image.new("L", cropped.size, 0)
    draw = ImageDraw.Draw(hole)
    draw.rounded_rectangle(
        (x,y,x+logo.width,y+logo.height),
        radius=min(logo.width,logo.height)//4,
        fill=255
    )
    empty   = Image.new("RGBA", cropped.size, (0,0,0,0))
    qr_hole = Image.composite(empty, cropped, hole)
    qr_hole.paste(logo, (x,y), logo)
    timings['compose_ms'] = int((time.perf_counter() - t2) * 1000)

    # wrap in HTML → PNG
    t3 = time.perf_counter()
    out = BytesIO()
    qr_hole.save(out, format="PNG")
    out.seek(0)
    data_uri = "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/>
    <style>html,body{{margin:0;padding:0;background:transparent}}
    #qr-container{{position:relative;display:inline-block}}
    .bg{{display:block;width:100%}}
    .qr{{position:absolute;left:50%;top:50%;
         transform:translate(-50%,-50%);width:30%}}
    </style></head><body>
    <div id="qr-container">
      <img class="bg" src="{TEMPLATE_URL}"/>
      <img class="qr" src="{data_uri}"/>
    </div></body></html>"""
    timings['html_ms'] = int((time.perf_counter() - t3) * 1000)

    # ── 4) Send the QR with Cancel button ───────────────────────────────────────
    try:
        img_url = html_to_png_url(html, timings)
    except Exception as e:
        return await callback_query.message.edit_text(f"❌ Failed: {e}")

    caption = (
        f"🛒 Order: {order_id}\n"
        f"💰 Amount: ₹{amount}\n\n"
        "✅ Styled PhonePe QR ready!\n"
        f"⏱ Total: {sum(timings.values())} ms"
    )

    kb = InlineKeyboardMarkup([
        [ InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}") ],
    ])

    await callback_query.message.reply_photo(
        photo=img_url,
        caption=caption,
        reply_markup=kb
    )
    await callback_query.answer()

    # ── 5) Start the auto-verify loop (unchanged) ──────────────────────────────
    asyncio.create_task(auto_verify_payment(
        client,
        callback_query.message,
        order_id
    ))
    
   

# ─── Cancel handler ──────────────────────────────────────────────────────────
@app.on_callback_query(filters.regex(r"^cancel_(.+)$"))
async def cancel_phonepe(client, callback_query):
    order_id = callback_query.data.split("_", 1)[1]

    # 1) Cancel poll/timer
    task = countdown_tasks.pop(order_id, None)
    if task and not task.done():
        task.cancel()
    order_store.pop(order_id, None)

    # 2) Acknowledge the button tap so QUERY_ID_INVALID doesn’t fire
    await callback_query.answer()

    # 3) Try deleting the QR message
    try:
        await callback_query.message.delete()
    except Exception as e:
        # log but don’t crash if delete fails
        logger.warning(f"Failed to delete QR message: {e!r}")



async def do_approve_flow_immediate(client, message, slot_id, data):
    """
    Immediately approve a successful payment:
      • Read /settings/slots/<slot_id> to get duration_hours
      • Insert a transaction record under /transactions (only the needed nodes)
      • Assign a free credential and record it
      • Send the user a “payment successful” UI
      • Increment that credential’s usage counter via patch_node(...)
    """
    txn_id = data.get("ORDERID")
    if not txn_id:
        logger.error("No ORDERID found in payment response.")
        return

    # ── 1) Compute start/end timestamps ───────────────────────────────────────
    tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(tz)

    # ── 1a) fetch that slot’s settings, so we know its “duration_hours”
    slot_node    = await read_node(f"settings/slots/{slot_id}")
    duration_hrs = int(slot_node.get("duration_hours", 6))
    start_time   = now
    end_time     = now + timedelta(hours=duration_hrs)

    # ── 2) build the basic transaction record (no credential yet)
    txn_record = {
        "slot_id":      slot_id,
        "start_time":   start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time":     end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "approved_at":  now.isoformat(),
        "assign_to":    None,              # will fill in below
        "user_id":      message.chat.id,   # who paid
        "last_email":   None,              # to detect future changes
        "last_password": None,
        "hidden":       False,
    }

    # ── 3) Insert into /transactions:
    if txn_id.startswith("REF-"):
        await patch_node(f"transactions/REF-ID/{txn_id}", txn_record)
    elif txn_id.startswith("FTRIAL-"):
        await patch_node(f"transactions/FTRIAL-ID/{txn_id}", txn_record)
    else:
        await patch_node(f"transactions/{txn_id}", txn_record)

    # ── 4) Assign a free credential (sync logic) ─────────────────────────────
    cred_key, cred_data = get_valid_credential_for_slot(slot_id)
    if cred_data == "locked":
        await client.send_message(
            chat_id=message.chat.id,
            text="⚠️ Credentials for this slot are locked."
        )
        return

    if not cred_data:
        await client.send_message(
            chat_id=message.chat.id,
            text="No available credentials for this slot."
        )
        return

    # ── 5) record which credential they got and its email/password
    txn_record["assign_to"]     = cred_key
    txn_record["last_email"]    = cred_data["email"]
    txn_record["last_password"] = cred_data["password"]

    # Persist just those two fields onto the same transaction node
    if txn_id.startswith("REF-"):
        await patch_node(f"transactions/REF-ID/{txn_id}", {
            "assign_to":     cred_key,
            "last_email":    cred_data["email"],
            "last_password": cred_data["password"]
        })
    elif txn_id.startswith("FTRIAL-"):
        await patch_node(f"transactions/FTRIAL-ID/{txn_id}", {
            "assign_to":     cred_key,
            "last_email":    cred_data["email"],
            "last_password": cred_data["password"]
        })
    else:
        await patch_node(f"transactions/{txn_id}", {
            "assign_to":     cred_key,
            "last_email":    cred_data["email"],
            "last_password": cred_data["password"]
        })

    # ── 6) Pull “approve_flow” UI via a small async read_node ───────────────
    ui        = await read_node("ui_config/approve_flow")
    photo_url = ui.get("photo_url", "").replace("\\n", "\n")
    succ_text = ui.get("success_text", "Payment Success ✅").replace("\\n", "\n")
    acct_fmt  = ui.get("account_format", "Email: {email}\nPassword: {password}")\
                     .replace("\\n", "\n")

    # Build the caption
    email    = cred_data["email"]
    password = cred_data["password"]
    caption  = f"{succ_text}\n\n{acct_fmt.format(email=email, password=password)}"

    # ── 7) Inline keyboard: Refresh + Buy Again ──────────────────────────────
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Refresh Password", callback_data=f"refresh_{txn_id}")],
        [InlineKeyboardButton("Buy Again",       callback_data="start")]
    ])

    # ── 8) send photo+caption (or fallback to text) ──────────────────────────
    if photo_url:
        await client.send_photo(
            chat_id=message.chat.id,
            photo=photo_url,
            caption=caption,
            reply_markup=kb
        )
    else:
        await client.send_message(
            chat_id=message.chat.id,
            text=caption,
            reply_markup=kb
        )

    # ── 9) Increment this credential’s usage counter via patch_node(...) ─────
    usage_count = int(cred_data.get("usage_count", 0))
    max_usage   = int(cred_data.get("max_usage",   0))
    if usage_count < max_usage:
        # Patch only /<cred_key>/usage_count.json
        await patch_node(f"{cred_key}", { "usage_count": usage_count + 1 })



# ── Helper: locate a transaction without fetching the whole DB ──────────────
async def _fetch_transaction_node(order_id: str) -> tuple[str, dict] | tuple[None, None]:
    """
    Try to read the transaction under these possible paths (in order):
      1) /transactions/<order_id>.json
      2) /transactions/REF-ID/<order_id>.json
      3) /transactions/FTRIAL-ID/<order_id>.json
    
    Returns (parent_path, txndata) if found, e.g. ("transactions/REF-ID", { ... }), 
    or (None, None) if not found at any location.
    """
    # 1) Top‐level
    node = await read_node(f"transactions/{order_id}")
    if node and isinstance(node, dict):
        return "transactions", node

    # 2) Under REF‐ID
    node = await read_node(f"transactions/REF-ID/{order_id}")
    if node and isinstance(node, dict):
        return "transactions/REF-ID", node

    # 3) Under FTRIAL‐ID
    node = await read_node(f"transactions/FTRIAL-ID/{order_id}")
    if node and isinstance(node, dict):
        return "transactions/FTRIAL-ID", node

    return None, None


@app.on_callback_query(filters.regex(r"^refresh_(.+)$"))
async def refresh_cred(client, callback_query):
    order_id = callback_query.data.split("_", 1)[1]

    # ── 1) Fetch exactly the transaction record ────────────────────────────────
    parent_path, txn = await _fetch_transaction_node(order_id)
    if not parent_path:
        # Transaction not found at any of the expected paths
        return await callback_query.answer("Invalid request", show_alert=True)

    # 2) Validate ownership
    if not txn or txn.get("user_id") != callback_query.from_user.id:
        return await callback_query.answer("Invalid request", show_alert=True)

    # ── 3) Expiry check (Asia/Kolkata) ────────────────────────────────────────
    tz = pytz.timezone("Asia/Kolkata")
    try:
        end_time_naive = datetime.strptime(txn["end_time"], "%Y-%m-%d %H:%M:%S")
        end_time = tz.localize(end_time_naive)
    except Exception:
        end_time = tz.localize(datetime.now(tz) - timedelta(seconds=1))  # force “expired” if parse fails

    if datetime.now(tz) > end_time:
        return await callback_query.answer("⏳ Your access has expired.", show_alert=True)

    # ── 4) Load exactly the credential node (no full DB) ───────────────────────
    cred_key = txn.get("assign_to")
    if not cred_key:
        return await callback_query.answer("No credential assigned.", show_alert=True)

    cred = await read_node(cred_key)
    if not isinstance(cred, dict):
        return await callback_query.answer("Credential not found.", show_alert=True)

    new_email    = cred.get("email", "")
    new_password = cred.get("password", "")

    # ── 5) Compare with what we last sent in txn ──────────────────────────────
    last_email    = txn.get("last_email", "")
    last_password = txn.get("last_password", "")

    if new_email == last_email and new_password == last_password:
        return await callback_query.answer("No change in credentials", show_alert=True)

    # ── 6) Build updated caption + buttons (exactly as before) ────────────────
    ui = await read_node("ui_config/approve_flow")
    succ_text = ui.get("success_text", "Payment Success ✅").replace("\\n", "\n")
    acct_fmt  = (
        ui.get("account_format", "Email: {email}\nPassword: {password}")
          .replace("\\n", "\n")
    )
    quote_text = "“𝖨𝖿 𝗅𝗈𝗀𝗀𝖾𝖽 𝗈𝗎𝗍, 𝖳𝖺𝗉 “𝖱𝖾𝖿𝗋𝖾𝗌𝗁” 𝗍𝗈 𝗀𝖾𝗍 𝗒𝗈𝗎𝗋 𝗇𝖾𝗐 𝗉𝖺𝗌𝗌𝗐𝗈𝗋𝖽!”"

    updated_caption = (
        f"{succ_text}\n\n"
        f"{acct_fmt.format(email=new_email, password=new_password)}\n\n"
        f"{quote_text}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Refresh Password", callback_data=f"refresh_{order_id}")],
        [InlineKeyboardButton("Buy Again",       callback_data="start")]
    ])

    # 7) Edit only the caption and markup (exact same UI logic) ───────────────
    try:
        await callback_query.message.edit_caption(
            caption=updated_caption,
            reply_markup=keyboard
        )
    except Exception:
        # Perhaps the original message had no 'caption' (e.g. it was a photo). In that rare case,
        # you could fall back to sending a fresh message, but usually edit_caption will work.
        pass

    # ── 8) Persist the new values via a targeted PATCH (no full write) ─────────
    patch_payload = {
        "last_email":    new_email,
        "last_password": new_password
    }
    await patch_node(f"{parent_path}/{order_id}", patch_payload)

    # 9) Confirm with a “toast”
    await callback_query.answer("Refreshed ✅", show_alert=True)


# ── The reject flow stays exactly the same (no database I/O changes needed) ──

async def do_reject_flow_immediate(client, message, reason: str = None):
    ui = await read_node("ui_config/reject_flow")
    photo_url = ui.get("photo_url", "").replace("\\n", "\n")
    err_txt   = ui.get("error_text", "Transaction Rejected.").replace("\\n", "\n")

    if reason:
        err_txt = f"{err_txt}\n\nReason: {reason}"

    if photo_url:
        await client.send_photo(
            chat_id=message.chat.id,
            photo=photo_url,
            caption=err_txt
        )
    else:
        await client.send_message(
            chat_id=message.chat.id,
            text=err_txt
        )
    

# ── BOTTOM ENTRY POINT (INIT & CLOSE aiohttp AROUND app.run) ──────────────
if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()

    # 1) Initialize the shared aiohttp session before starting the bot
    loop.run_until_complete(init_aiohttp_session())

    try:
        # 2) Run your Pyrogram bot
        app.run()
    finally:
        # 3) Close the shared aiohttp session after the bot stops
        loop.run_until_complete(close_aiohttp_session())