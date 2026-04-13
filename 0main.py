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
from getinfo_module import register_getinfo_handlers



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
from pyrogram.errors import MessageNotModified, QueryIdInvalid

import hashlib
from typing import List

import psutil

import traceback # PROMO CODE
import re
from pyrogram.types import ForceReply

# --------------------- Bot Configuration ---------------------
API_ID = "27708983"
API_HASH = "d0c88b417406f93aa913ecb5f1b58ba6"
BOT_TOKEN = "7516682635:AAEQElYLeWEN3_oAjyoF4kVmtH5Vr6ni8Mo"

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
REAL_DB_URL = "https://oor-netflix-default-rtdb.firebaseio.com/"

# Shivam
#UPI_ID           = "paytmqr2810050501013202t473pymf@paytm"
MERCHANT_NAME    = "OTT ON RENT"
#MID              = "OtWRkM00455638249469"

# Me
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

pending_code_requests = {} # PROMO CODE

# The dictionary for storing gateway status (on or off)
gateway_status = {"is_on": True}  # Default to on # GATEWAY


# --------------------- Logging Setup ---------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# logging.getLogger().setLevel(logging.ERROR) ## For Logging ERROR only

logging.getLogger().setLevel(logging.CRITICAL) # Disable All Logging

# Register any FileID or referral handlers


try:
    register_refer_handlers(app)
    logging.info(f"refer.py handlers registered successfully in bot.py!")
except Exception as e:
    logging.info(f"Error registering refer.py handlers:", e)

try:    
    register_getinfo_handlers(app)
    logging.info("getinfo_module handlers registered successfully!")
except Exception as e:
    logging.info("Error registering getinfo_module handlers:", e)
    
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

 # ── 1) Async update usage_count ─────────────────────────────────────────────
async def update_usage_count_async(cred_key: str, new_usage: int):
    """
    Atomically PATCH /<cred_key>/usage_count.json to new_usage.
    """
    logging.info(f"Updating usage_count for {cred_key} => {new_usage}")
    url = REAL_DB_URL.rstrip("/") + f"/{cred_key}/usage_count.json"
    try:
        async with aiohttp_session.patch(url, json=new_usage, timeout=10) as resp:
            if resp.status != 200:
                text = await resp.text()
                logging.warning(f"update_usage_count failed {resp.status}: {text}")
    except Exception as e:
        logging.warning(f"update_usage_count exception: {e}")

# ── 2) Async update locked flag ──────────────────────────────────────────────
async def update_credential_locked_async(cred_key: str, new_locked: int):
    """
    Atomically PATCH /<cred_key>/locked.json to new_locked.
    """
    logging.info(f"Updating locked for {cred_key} => {new_locked}")
    url = REAL_DB_URL.rstrip("/") + f"/{cred_key}/locked.json"
    try:
        async with aiohttp_session.patch(url, json=new_locked, timeout=10) as resp:
            if resp.status != 200:
                text = await resp.text()
                logging.warning(f"update_locked failed {resp.status}: {text}")
    except Exception as e:
        logging.warning(f"update_locked exception: {e}")

# ── 3) Async check if ORDERID used ───────────────────────────────────────────
async def is_orderid_used_async(order_id: str) -> bool:
    """
    GET /used_orderids/<order_id>.json and return True if that node exists &== true.
    """
    url = REAL_DB_URL.rstrip("/") + f"/used_orderids/{order_id}.json"
    try:
        async with aiohttp_session.get(url, timeout=10) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data is True
    except Exception as e:
        logging.warning(f"is_orderid_used exception: {e}")
    return False

# ── 4) Async mark ORDERID used ───────────────────────────────────────────────
async def mark_orderid_used_async(order_id: str):
    """
    PATCH /used_orderids.json with { order_id: true }.
    """
    url = REAL_DB_URL.rstrip("/") + "/used_orderids.json"
    try:
        async with aiohttp_session.patch(url, json={order_id: True}, timeout=10) as resp:
            if resp.status != 200:
                text = await resp.text()
                logging.warning(f"mark_orderid_used failed {resp.status}: {text}")
    except Exception as e:
        logging.warning(f"mark_orderid_used exception: {e}")   

# ── GET A VALID CREDENTIAL FOR A GIVEN SLOT (UNCHANGED) ─────────────────────

async def get_valid_credential_for_slot_async(slot_id: str):
    """
    The same logic as your sync version, but:
      • Uses get_shallow_keys() + read_node() in parallel
      • Preserves locked_found, found_global, found_slot, and logging
    Returns (cred_key, cred_data) or (None, "locked") or (None, None).
    """
    locked_found = False
    found_global = None
    found_slot   = None
    now = datetime.now()

    # 1) shallow fetch top‐level keys
    top_keys = await get_shallow_keys()

    # 2) fetch all credential nodes in parallel
    tasks = {key: asyncio.create_task(read_node(key)) for key in top_keys}
    await asyncio.gather(*tasks.values(), return_exceptions=True)

    for key, task in tasks.items():
        node = task.result()
        if not is_credential(node):
            continue

        owns = node.get("belongs_to_slot", [])
        if isinstance(owns, str):
            owns = [owns]
        if not isinstance(owns, list):
            continue

        in_all  = "all" in owns
        in_slot = slot_id in owns
        if not (in_all or in_slot):
            continue

        locked_val   = int(node.get("locked", 0))
        usage_count  = int(node.get("usage_count", 0))
        max_usage    = int(node.get("max_usage",   0))
        try:
            expiry_dt = datetime.strptime(node.get("expiry_date", ""), "%Y-%m-%d")
        except Exception:
            continue

        if locked_val == 1:
            locked_found = True
            logger.info(f"[LOCKED] {key} is locked.")
            continue
        if usage_count >= max_usage:
            logger.info(f"[USED-UP] {key} reached max usage.")
            continue
        if expiry_dt <= now:
            logger.info(f"[EXPIRED] {key} is expired.")
            continue

        logger.info(
            f"[MATCH] Key: {key} | Owns: {owns} | Usage: {usage_count}/{max_usage} "
            f"| Locked: {locked_val} | Exp: {node.get('expiry_date')}"
        )

        if in_all and found_global is None:
            found_global = (key, node)
        elif in_slot and found_slot is None:
            found_slot = (key, node)

        if found_global:
            break

    if found_global:
        logger.info(f"[SELECTED] {found_global[0]} for slot {slot_id} (global)")
        return found_global
    if found_slot:
        logger.info(f"[SELECTED] {found_slot[0]} for slot {slot_id}")
        return found_slot
    if locked_found:
        logger.info(f"[RETURN] No available creds, but locked found. Returning 'locked'")
        return None, "locked"

    logger.info(f"[RETURN] No creds at all. Returning None, None")
    return None, None


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
async def handle_out_of_stock(client, chat_id, user_id, slot_id):
    # Log for troubleshooting
    logging.info("No credentials => out_of_stock => user: %s", user_id)

    # Load config
    ui = await read_ui_config("out_of_stock")
    photo_url = ui.get("photo_url", "")
    raw_text = ui.get("stock_text", "🚫 Sold Out!\nSorry for the inconvenience.")

    # Convert any literal “\n” into a real newline
    caption = raw_text.replace("\\n", "\n")

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔔 Notify me", callback_data=f"notify:{slot_id}")]]
    )

    await client.send_photo(
        chat_id,
        photo=photo_url,
        caption=caption,
        reply_markup=keyboard
    )

async def stock_watcher(poll_interval: float = 5.0):
    # Step 1: Load previous stock from Firebase (or empty)
    prev_stock = await read_node("notify/prev_stock") or {}

    while True:
        # A) Full DB snapshot
        db_data = await read_node("")  # root

        # B) Get enabled slots
        settings = db_data.get("settings", {}).get("slots", {})
        slots = [
            slot_id
            for slot_id, info in settings.items()
            if isinstance(info, dict) and info.get("enabled", False)
        ]

        # C) Compute current stock per slot
        curr_stock = {}
        for slot in slots:
            stock_left = 0
            for node in db_data.values():
                if not is_credential(node):
                    continue

                owns = node.get("belongs_to_slot", [])
                if isinstance(owns, str):
                    owns = [owns]
                elif not isinstance(owns, list):
                    continue

                if slot not in owns and "all" not in owns:
                    continue

                # ✅ Skip if locked
                if int(node.get("locked", 0)) == 1:
                    continue

                usage = int(node.get("usage_count", 0))
                max_usage = int(node.get("max_usage", 0))
                stock_left += max(0, max_usage - usage)

            curr_stock[slot] = stock_left

        # D) Compare and notify on 0 → positive
        for slot, stock_left in curr_stock.items():
            old = prev_stock.get(slot, 0)
            if old <= 0 < stock_left:
                slot_name = settings.get(slot, {}).get("name", slot)
                waiters = await read_node(f"notify/{slot}") or {}

                for user_id in waiters.keys():
                    try:
                        await app.send_message(
                            int(user_id),
                            f"🔥𝗪𝗲'𝗿𝗲 𝗕𝗮𝗰𝗸 𝗶𝗻 𝗦𝘁𝗼𝗰𝗸!! 😉\n𝖳𝗁𝖾 {slot_name} 𝗂𝗌 𝖺𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾 𝖺𝗀𝖺𝗂𝗇!! 🎉",
                            reply_markup=InlineKeyboardMarkup(
                                [[InlineKeyboardButton("Buy Now", callback_data="start")]]
                            )
                        )
                    except Exception as e:
                        logging.error(f"Failed to notify {user_id}: {e}")

                if waiters:
                    await patch_node(f"notify/{slot}", {uid: None for uid in waiters})

        # E) Save current stock to Firebase as prev_stock
        await patch_node("notify/prev_stock", curr_stock)

        # F) Sleep
        prev_stock = curr_stock
        await asyncio.sleep(poll_interval)
        
        
def check_paytm_server():
    return True

# aiohttp

# GATEWAY
async def get_admin_config():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(REAL_DB_URL + "admin_config.json") as resp:
                return await resp.json() or {}
    except Exception:
        return {}

# Asynchronously fetch the admin config when needed
async def load_admin_config():
    admin_config = await get_admin_config()

    superior_admins = admin_config.get("superior_admins", [])
    if not isinstance(superior_admins, list):
        superior_admins = [superior_admins]
    superior_admins = [str(x) for x in superior_admins]

    inferior_admins = admin_config.get("inferior_admins", [])
    if not isinstance(inferior_admins, list):
        inferior_admins = [inferior_admins]
    inferior_admins = [str(x) for x in inferior_admins]

    return superior_admins, inferior_admins

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
    """
    POST HTML to your convert API and return a png URL (string) or a local file path
    to a saved PNG if the upstream returned binary image bytes.

    - timings: dictionary where 'post_ms' and 'get_ms' will be written (ms).
    - Raises RuntimeError on failures with diagnostic info.
    """
    DEMO_URL = "http://194.242.56.38:6969/convert"
    headers = {
        "Accept":       "*/*",
        "Content-Type": "application/json",
        "X-API-KEY":    INTERNAL_API_KEY,
    }
    payload = {
        "html": html,
        "selector": "#qr-container"
        # keep the extra keys your upstream might expect:
    }

    t0 = time.perf_counter()
    try:
        resp = requests.post(DEMO_URL, headers=headers, json=payload, stream=True)
    except Exception as e:
        tb = traceback.format_exc()
        raise RuntimeError(f"POST to {DEMO_URL} failed: {e}\nTraceback:\n{tb}") from e

    timings['post_ms'] = int((time.perf_counter() - t0) * 1000)

    status = resp.status_code
    ctype = resp.headers.get("Content-Type", "")

    # Non-200 -> include snippet for debugging
    if status != 200:
        try:
            body = resp.text[:_MAX_BODY_SNIPPET]
        except Exception:
            body = "<unable to read body>"
        raise RuntimeError(f"Upstream returned status {status}. Content-Type: {ctype}\nHeaders: {dict(resp.headers)}\nBody snippet: {body}")

    # If JSON / text -> parse for url
    if ctype.startswith("application/json") or ctype.startswith("text/"):
        try:
            data = resp.json()
        except Exception as e:
            try:
                body = resp.text[:_MAX_BODY_SNIPPET]
            except Exception:
                body = "<unable to read body>"
            raise RuntimeError(f"Failed to parse JSON from upstream: {e}\nBody snippet: {body}") from e

        img_url = data.get("url") or (data.get("data") or {}).get("url")
        if not img_url:
            raise RuntimeError(f"JSON response did not contain an image URL. JSON: {data}")
        timings['get_ms'] = 0
        return img_url + ".png"  # keep previous behaviour

    # If binary image returned -> save to temp file and return path (compatible with reply_photo)
    if ctype.startswith("image/"):
        t1 = time.perf_counter()
        try:
            content = resp.content
        except Exception as e:
            raise RuntimeError(f"Failed to read image bytes from upstream: {e}") from e
        timings['get_ms'] = int((time.perf_counter() - t1) * 1000)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        try:
            tmp.write(content)
            tmp.flush()
            tmp.close()
            return tmp.name  # local file path string — reply_photo accepts this
        except Exception as e:
            raise RuntimeError(f"Failed to write temporary image file: {e}") from e

    # Unknown content-type — include a snippet
    try:
        body = resp.text[:_MAX_BODY_SNIPPET]
    except Exception:
        body = "<unable to read body>"
    raise RuntimeError(f"Unexpected Content-Type: {ctype}. Body snippet: {body}")


custom_font_map = {
    "A": "𝗔", "B": "𝗕", "C": "𝗖", "D": "𝗗", "E": "𝗘", "F": "𝗙", "G": "𝗚",
    "H": "𝗛", "I": "𝗜", "J": "𝗝", "K": "𝗞", "L": "𝗟", "M": "𝗠", "N": "𝗡",
    "O": "𝗢", "P": "𝗣", "Q": "𝗤", "R": "𝗥", "S": "𝗦", "T": "𝗧", "U": "𝗨",
    "V": "𝗩", "W": "𝗪", "X": "𝗫", "Y": "𝗬", "Z": "𝗭",
    "a": "𝗮", "b": "𝗯", "c": "𝗰", "d": "𝗱", "e": "𝗲", "f": "𝗳", "g": "𝗴",
    "h": "𝗵", "i": "𝗶", "j": "𝗷", "k": "𝗸", "l": "𝗹", "m": "𝗺", "n": "𝗻",
    "o": "𝗼", "p": "𝗽", "q": "𝗾", "r": "𝗿", "s": "𝘀", "t": "𝘁", "u": "𝘂",
    "v": "𝘃", "w": "𝘄", "x": "𝘅", "y": "𝘆", "z": "𝘇"
}

def stylize(text: str, font_map: dict) -> str:
    return ''.join(font_map.get(c, c) for c in text)
    
    
def compute_hash_of(obj: dict) -> str:
    """MD5 of JSON dump (sorted keys) to detect data changes."""
    b = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.md5(b).hexdigest()

async def bump_version(path: str):
    """
    Async PATCH /<path>.json → { version: "<IST time>" }
    """
    ist = datetime.now(pytz.timezone("Asia/Kolkata"))
    version_str = ist.strftime("%H:%M:%S-%d-%B")
    try:
        await patch_node(path, {"version": version_str})
        logger.info(f"[ConfigWatcher] Bumped version for {path} → {version_str}")
    except Exception as e:
        logger.error(f"[ConfigWatcher] Failed to bump version for {path}: {e}")

async def config_version_watcher(paths: list[str], interval: float = 5.0):
    """
    Watch the given DB paths. Whenever their content (ignoring 'version')
    changes, PATCH a new `version` timestamp.
    """
    last_hash: dict[str,str] = {p: None for p in paths}
    logger.info(f"[ConfigWatcher] Monitoring: {paths}")

    while True:
        for path in paths:
            node = await read_node(path) or {}
            clean = {k: v for k, v in node.items() if k != "version"}
            h = compute_hash_of(clean)

            if last_hash[path] is None:
                logger.info(f"[ConfigWatcher] Initializing version for {path}")
                await bump_version(path)
                last_hash[path] = h

            elif h != last_hash[path]:
                logger.info(f"[ConfigWatcher] Change detected in {path}; bumping version")
                await bump_version(path)
                last_hash[path] = h

        await asyncio.sleep(interval)
        
                
# --------------------- BOT Handlers ---------------------


# Remove/Delete Later 

from pyrogram.types import Message, CallbackQuery

## FOR BLOCKING ACCESS TO BOT

# ALLOWED_USER_IDS = [7506651658, 2031595742]  # your allowed IDs here

# # ── 0) DENY UNAUTHORIZED USERS ────────────────────────────────────────────────
# @app.on_message(~filters.user(ALLOWED_USER_IDS), group=0)
# async def _deny_message(client: Client, message: Message):
    # logging.warning(f"Blocked unauthorized user: {message.from_user.id}")
    # await message.reply_text("🚫 You are not authorized to use this bot.")
    # message.stop_propagation()

# @app.on_callback_query(~filters.user(ALLOWED_USER_IDS), group=0)
# async def _deny_callback(client: Client, cq: CallbackQuery):
    # logging.warning(f"Blocked unauthorized callback from: {cq.from_user.id}")
    # await cq.answer("🚫 You are not authorized.", show_alert=True)
    # cq.stop_propagation()
    
    
   

# ── MAINTENANCE MESSAGE GUARD (runs before everything else) ────────────────
@app.on_message(
    filters.private & filters.text & filters.regex(r"^/"), 
    group=-1
)
async def maintenance_message_guard(client: Client, message: Message):
    # Skip the /maintenance command itself (with or without bot username)
    cmd = message.text.split()[0].lower().split("@", 1)[0]  # e.g. "/maintenance" or "/maintenance@YourBot"
    if cmd == "/maintenance":
        return

    mnode = await read_node("maintenance")
    if not mnode.get("enabled"):
        return

    ui   = await read_ui_config("maintenance")
    mode = ui.get("mode", "text").lower()

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔔 Notify me", callback_data="maintenance_notify")]
    ])

    if mode == "photo" and ui.get("photo_url"):
        raw_caption = ui.get("caption") or ui.get("message") or "🚧 Under maintenance."
        caption     = raw_caption.replace("\\n", "\n")
        await message.reply_photo(
            photo=ui["photo_url"],
            caption=caption,
            reply_markup=kb
        )
    else:
        raw_text = ui.get("message") or ui.get("caption") or "🚧 Under maintenance."
        text     = raw_text.replace("\\n", "\n")
        await message.reply(text, reply_markup=kb)

    message.stop_propagation()


# ── 2) MAINTENANCE CALLBACK GUARD (runs before other callbacks) ──────────────
@app.on_callback_query(group=-1)
async def maintenance_callback_guard(client: Client, cq: CallbackQuery):
    # Allow the toggle command callback (if any) to pass
    if cq.data and cq.data.startswith("maintenance"):
        return

    mnode = await read_node("maintenance")
    if not mnode.get("enabled"):
        return

    ui          = await read_ui_config("maintenance")
    raw_alert   = ui.get("alert") or ui.get("message") or "🚧 Under maintenance."
    alert_text  = raw_alert.replace("\\n", "\n")
    await cq.answer(alert_text, show_alert=True)
    cq.stop_propagation()


# ── 3) “Notify Me” button handler ────────────────────────────────────────────
@app.on_callback_query(filters.regex(r"^maintenance_notify$"), group=0)
async def maintenance_notify_register(client: Client, cq: CallbackQuery):
    uid = cq.from_user.id
    # record under /maintenance/notify/{uid} = true
    await patch_node("maintenance/notify", { str(uid): True })

    ui               = await read_ui_config("maintenance")
    raw_alert_notify = ui.get("alert_notify") or "🔔 Got it! We’ll notify you when we’re back."
    alert_notify     = raw_alert_notify.replace("\\n", "\n")
    await cq.answer(alert_notify, show_alert=True)
    cq.stop_propagation()


# ── 4) /maintenance TOGGLE (no notify logic here) ────────────────────────────
@app.on_message(filters.command("maintenance"), group=1)
async def toggle_maintenance(client: Client, message: Message):
    if message.edit_date:
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or parts[1].lower() not in ("on", "off"):
        return await message.reply("Usage: /maintenance on|off")

    desired = parts[1].lower() == "on"
    uid     = message.from_user.id

    cfg = await read_node("admin_config")
    if uid not in cfg.get("inferior_admins", []) + cfg.get("superior_admins", []):
        return await message.reply("𝖸𝗈𝗎’𝗋𝖾 𝗇𝗈𝗍 𝖺𝗎𝗍𝗁𝗈𝗋𝗂𝗓𝖾𝖽 🚫")

    try:
        await patch_node("maintenance", {"enabled": desired})
    except Exception as e:
        logger.error(f"Failed to set maintenance: {e}")
        return await message.reply("⚠️ Could not update flag.")

    await message.reply(f"⚠️ [ 𝖬𝖺𝗂𝗇𝗍𝖾𝗇𝖺𝗇𝖼𝖾 ] {'𝗘𝗡𝗔𝗕𝗟𝗘𝗗 ✅' if desired else '𝗗𝗜𝗦𝗔𝗕𝗟𝗘𝗗 ❎'}")


# ── 5) BACKGROUND WATCHER to notify & clear on ANY disable ──────────────────
async def maintenance_watcher(poll_interval: float = 5.0):
    last = (await read_node("maintenance")).get("enabled", False)
    while True:
        await asyncio.sleep(poll_interval)
        node = await read_node("maintenance")
        now  = node.get("enabled", False)

        # just turned OFF?
        if last and not now:
            notify_list = await read_node("maintenance/notify") or {}
            ui           = await read_ui_config("maintenance")
            raw_back     = ui.get("back_message") or "🚀 We’re back online! You can now start."
            back_text    = raw_back.replace("\\n", "\n")
            buy_kb       = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Buy Now", callback_data="start")]]
            )
            # DM each and remove them one by one
            for uid_str in list(notify_list.keys()):
                try:
                    await app.send_message(int(uid_str), back_text, reply_markup=buy_kb)
                except Exception:
                    pass
                # delete that uid only
                await patch_node("maintenance/notify", { uid_str: None })

        last = now


# ── 6) ENSURE maintenance & notify nodes exist ───────────────────────────────
async def ensure_maintenance_node():
    m = await read_node("maintenance")
    if "enabled" not in m:
        await patch_node("maintenance", {"enabled": False})
    nl = await read_node("maintenance/notify")
    if not isinstance(nl, dict):
        await patch_node("maintenance/notify", {})

      
        
            


    
@app.on_callback_query(filters.regex(r"^notify:(.+)$"))
async def notify_register(client, callback_query):
    slot    = callback_query.data.split(":", 1)[1]
    user_id = callback_query.from_user.id

    # Save the user under /notify/{slot}/{user_id} = true
    await patch_node(f"notify/{slot}", { str(user_id): True })

    # Try to fetch the slot's friendly name from settings
    db_data   = await read_node("settings/slots")
    slot_name = db_data.get(slot, {}).get("name", slot)

    # Stylize it
    fancy_name = stylize(slot_name, custom_font_map)
    
    
    # Confirm registration with plain-text alert
    await callback_query.answer(
        f"✅ 𝖦𝗈𝗍 𝗂𝗍. 𝗪𝗲’𝗹𝗹 𝗮𝗹𝗲𝗿𝘁 𝘆𝗼𝘂 𝘁𝗵𝗲 𝗺𝗼𝗺𝗲𝗻𝘁 𝘁𝗵𝗲 {fancy_name} 𝗱𝗿𝗼𝗽𝘀 ⚡",
        show_alert=True
    )
      
    
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
async def stats(client, message):
    # 1) Total users
    users_node = await read_users_node()
    total_users = len(users_node)

    stats_text = f"👤 𝙏𝙤𝙩𝙖𝙡 𝙐𝙨𝙚𝙧𝙨: {total_users}\n\n"
    stats_text += "📊 𝙎𝙡𝙤𝙩 𝙎𝙩𝙖𝙩𝙞𝙨𝙩𝙞𝙘𝙨:\n\n"

    # 2) Which slots to show
    settings_slots = (await read_node("settings/slots")) or {}
    slots_to_show = ["slot_1"]
    slot2 = settings_slots.get("slot_2", {})
    if isinstance(slot2, dict) and slot2.get("enabled", False):
        slots_to_show.append("slot_2")

    # 3) Fetch full DB once
    db_root = await read_node("")

    for slot in slots_to_show:
        total = used = stock = 0

        for key, node in db_root.items():
            if not is_credential(node):
                continue

            owns = node.get("belongs_to_slot", [])
            if isinstance(owns, str):
                owns = [owns]

            # **include if credential is global ("all") or belongs to this slot**
            if slot not in owns and "all" not in owns:
                continue

            usage     = int(node.get("usage_count", 0))
            max_usage = int(node.get("max_usage",   0))
            total += 1
            used  += usage
            stock += (max_usage - usage)

        stats_text += (
            f" ▸ 𝖲𝗅𝗈𝗍 {slot[-1]}:\n"
            f"    • 𝘛𝘰𝘵𝘢𝘭 𝘊𝘳𝘦𝘥𝘦𝘯𝘵𝘪𝘢𝘭𝘴: {total}\n"
            f"    • 𝘛𝘰𝘵𝘢𝘭 𝘜𝘴𝘦𝘥: {used}\n"
            f"    • 𝘚𝘵𝘰𝘤𝘬 𝘓𝘦𝘧𝘵: {stock}\n\n"
        )

    await message.reply(stats_text)
    

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
    used = await is_orderid_used_async(order_id)
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
    await mark_orderid_used_async(order_id)

    # 11) Get a valid credential for this slot (sync)
    cred_key, cred_data = await get_valid_credential_for_slot_async(slot_id)
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
        await update_usage_count_async(cred_key, new_usage)

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
    
@app.on_message(filters.command("core") & filters.private)
async def core_handler(_, msg: Message):
    proc   = psutil.Process(os.getpid())
    cpu_sys = psutil.cpu_percent(interval=None)
    vm      = psutil.virtual_memory()
    cpu_bot = proc.cpu_percent(interval=None)
    rss     = proc.memory_info().rss / (1024 * 1024)
    vms     = proc.memory_info().vms / (1024 * 1024)

    reply = (
        "**System**\n"
        f" • CPU: {cpu_sys:.1f}%\n"
        f" • RAM: {vm.percent:.1f}% ({vm.used//(1024*1024)}MB/{vm.total//(1024*1024)}MB)\n\n"
        "**Bot Process**\n"
        f" • CPU: {cpu_bot:.1f}%\n"
        f" • RSS: {rss:.1f} MB\n"
        f" • VMS: {vms:.1f} MB"
    )
    await msg.reply_text(reply)    
    
    

# GATEWAY
gateway_status = {"is_on": True}  # Default to on # GATEWAY

# Command for turning the gateway off
@app.on_message(filters.command("gateway off"))
async def gateway_off(client, message):
    user_id = message.from_user.id
    superior_admins, _ = await load_admin_config()

    if str(user_id) not in superior_admins:
        return await message.reply_text("⚠️ You are not authorized to perform this action.")

    # Log that the command was triggered
    logger.info(f"Received /gateway off command from {user_id}")

    # Turn off the gateway
    gateway_status["is_on"] = False
    await message.reply_text("⚠️ [ 𝖯𝖺𝗒𝗆𝖾𝗇𝗍 𝖦𝖺𝗍𝖾𝗐𝖺𝗒 ] 𝗂𝗌 𝗇𝗈𝗐 𝗢𝗙𝗙 ❎")

@app.on_message(filters.command("gateway on"))
async def gateway_on(client, message):
    user_id = message.from_user.id
    superior_admins, _ = await load_admin_config()

    if str(user_id) not in superior_admins:
        return await message.reply_text("⚠️ You are not authorized to perform this action.")

    # Log that the command was triggered
    logger.info(f"Received /gateway on command from {user_id}")

    # Turn on the gateway
    gateway_status["is_on"] = True
    await message.reply_text("🔥 [ 𝖯𝖺𝗒𝗆𝖾𝗇𝗍 𝖦𝖺𝗍𝖾𝗐𝖺𝗒 ] 𝗂𝗌 𝗇𝗈𝗐 𝗢𝗡 ✅")    
    
    
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
    


@app.on_message(filters.command("help"))
async def help_command(client, message):
    ui = get_ui_config("help")
    help_text = ui.get("help_text", "Contact support @oor_agent").replace("\\n", "\n")
    message_queue.put_nowait((
        client.send_message,
        [message.chat.id],
        {"text": help_text}
    ))
        

@app.on_callback_query(filters.regex("^help$"))
async def help_callback(client, callback_query):
    ui = get_ui_config("help")
    help_text = ui.get("help_text", "Contact support @oor_agent").replace("\\n", "\n")
    message_queue.put_nowait((
        client.send_message,
        [callback_query.message.chat.id],
        {"text": help_text}
    ))
    await callback_query.answer()


from pyrogram.errors import UserNotParticipant, ChatAdminRequired
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus


# Your channel username
CHANNEL_USERNAME = "@ott_on_rent"

# Track users who clicked “Book Slot” but aren’t joined yet
pending_bookings: dict[int, tuple[CallbackQuery, int]] = {}

@app.on_callback_query(filters.regex(r"^book_slot$"))
async def gated_book_slot_handler(client, callback_query):
    user_id = callback_query.from_user.id
    action  = callback_query.data  # "book_slot" or "joined_confirm"
    logger.info(f"[Gate] callback {action!r} from user {user_id}")

    # 1) ACK immediately
    await callback_query.answer()

    # 2) Check channel membership
    is_member = False
    try:
        m = await client.get_chat_member(CHANNEL_USERNAME, user_id)
        if m.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            is_member = True

    except UserNotParticipant:
        pass
    except ChatAdminRequired:
        logger.warning("[Gate] Bot must be admin to check channel membership")
    except RPCError as e:
        logger.error(f"[Gate] RPCError checking membership: {e}")

    # 3) If not a member yet…
    if not is_member:

        # record that they want to book once they join
        text = (
            "🎬 𝗥𝗲𝗮𝗱𝘆 𝘁𝗼 𝘂𝗻𝗹𝗼𝗰𝗸 𝘁𝗵𝗲 𝘀𝗵𝗼𝘄?\n"
            "👉🏻 𝖩𝗎𝗌𝗍 𝗁𝗈𝗉 𝗂𝗇𝗍𝗈 𝗈𝗎𝗋 𝖼𝗁𝖺𝗇𝗇𝖾𝗅 𝖿𝗈𝗋 𝗆𝗈𝗋𝖾..‎ ‎ \n\n"
            "𝗝𝗼𝗶𝗻 𝗡𝗼𝘄 🚀\n"
            "𝗍𝗁𝖾𝗇 𝗍𝖺𝗉 “𝖩𝗈𝗂𝗇” 𝗍𝗈 𝗋𝗈𝗅𝗅 𝗍𝗁𝖾 𝗋𝖾𝖾𝗅! 🍿"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🎬 𝗝𝗼𝗶𝗻 𝗖𝗵𝗮𝗻𝗻𝗲𝗹",
                    url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
                )
            ]
        ])

        sent = await client.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=keyboard
        )

        pending_bookings[user_id] = (callback_query, sent.id)
        return

    # 4) Finally hand off to your booking logic
    logger.info("[Gate] user is a channel member → proceeding")
    asyncio.create_task(book_slot_action(client, callback_query))


# ── 2) React to Telegram “user joined channel” events ─────────
@app.on_chat_member_updated()
async def on_channel_member_update(client, update: ChatMemberUpdated):
    user_id = update.from_user.id
    old = update.old_chat_member.status if update.old_chat_member else None
    new = update.new_chat_member.status

    if (
        new in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
        and old not in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    ):
        # pop out the original query and message_id
        pair = pending_bookings.pop(user_id, None)
        if pair:
            callback_query, prompt_msg_id = pair
            try:
                await client.delete_messages(chat_id=user_id, message_ids=[prompt_msg_id])
            except:
                pass
            logger.info(f"[Gate→JOIN] launching booked slot for {user_id}")
            asyncio.create_task(book_slot_action(client, callback_query))
           
                  
                                
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

@app.on_callback_query(filters.regex(r"^choose_slot_"))
async def choose_slot(client, callback_query):
    # 1) unblock UI
    await callback_query.answer()

    user_id = callback_query.from_user.id
    slot_id = callback_query.data.replace("choose_slot_", "")

    # 2) run the async credential lookup
    cred_key, cred_data = await get_valid_credential_for_slot_async(slot_id)

    # 3a) locked path
    if cred_data == "locked":
        await show_locked_message(client, callback_query.message.chat.id)
        return

    # 3b) out of stock path
    if cred_key is None and cred_data is None:
        await handle_out_of_stock(
            client, callback_query.message.chat.id, user_id, slot_id
        )
        return

    # 4) success path → remember & hand off
    user_slot_choice[user_id] = slot_id
    logger.info(f"User {user_id} chose slot: {slot_id} with cred {cred_key}")

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
            InlineKeyboardButton("𝖦𝖾𝗍 𝖥𝗋𝖾𝖾 𝖳𝗋𝗂𝖺𝗅", callback_data="free_trial")
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
        try:
            await callback_query.answer(
                "OORverse feature is currently unavailable 🚀 Coming Soon..",
                show_alert=True
            )
        except:
            pass
        return

    # 2. Referral info fetch
    user_id = str(callback_query.from_user.id)
    info = await get_referral_info(user_id)
    if info is None:
        try:
            await callback_query.answer(
                "𝖭𝗈 𝗋𝖾𝖿𝖾𝗋𝗋𝖺𝗅 𝗂𝗇𝖿𝗈 𝖿𝗈𝗎𝗇𝖽.\n"
                "𝖯𝗅𝖾𝖺𝗌𝖾 𝖽𝗈 /𝗌𝗍𝖺𝗋𝗍 𝖺𝗀𝖺𝗂𝗇 𝗍𝗈 𝗋𝖾𝗀𝗂𝗌𝗍𝖾𝗋 𝗂𝗇 𝖮𝖮𝖱𝗏𝖾𝗋𝗌𝖾",
                show_alert=True
            )
        except:
            pass
        return

    current_points = info.get("referral_points", 0)
    required_points = await get_required_points()

    if current_points < required_points:
        needed = required_points - current_points
        try:
            await callback_query.answer(
                f"𝖸𝗈𝗎 𝗇𝖾𝖾𝖽 {needed} 𝗆𝗈𝗋𝖾 𝗢𝗢𝗥𝗯𝗶𝘁𝘀 𝗍𝗈 𝗀𝖾𝗍 𝖺 a 𝖭𝖾𝗍𝖿𝗅𝗂𝗑 𝖠𝖼𝖼𝗈𝗎𝗇𝗍",
                show_alert=True
            )
        except:
            pass
        return

    # 3. Slot ID from in-memory user slot choice
    slot_id = user_slot_choice.get(callback_query.from_user.id, "slot_1")

    # 4. Check if user already claimed this slot today
    user_claims = await read_node(f"account_claims/{user_id}")
    if user_claims.get(slot_id):
        try:
            await callback_query.answer(
                "𝖸𝗈𝗎 𝗁𝖺𝗏𝖾 𝖺𝗅𝗋𝖾𝖺𝗅𝗒 𝖼𝗅𝖺𝗂𝗆𝖾𝖽 𝖺 𝖭𝖾𝗍𝖿𝗅𝗂𝗑 𝖺𝖼𝖼𝗈𝗎𝗇𝗍 𝖿𝗈𝗋 𝗍𝗈𝖽𝖺𝗒! 😊 comeback 𝗍𝗈𝗆𝗈𝗋𝗋𝗈𝗐",
                show_alert=True
            )
        except:
            pass
        return

    # 5. Check for valid credential (sync)
    cred_key, cred_data = await get_valid_credential_for_slot_async(slot_id)
    if cred_data == "locked":
        # first, send locked-style message
        await show_locked_message(client, callback_query.message.chat.id)
        # then answer alert, wrapped to ignore invalid-ID
        try:
            await callback_query.answer("Credentials locked.", show_alert=True)
        except:
            pass
        return

    if not cred_data:
        # handle out-of-stock internally (should answer there)
        return await handle_out_of_stock(
            client, callback_query.message.chat.id, user_id, slot_id
        )

    # 6. Deduct referral points in async DB
    await patch_node(f"referrals/{user_id}", {
        "referral_points": current_points - required_points
    })

    # 7. Generate dummy ORDER ID
    rand_str = ''.join(random.choices(string.ascii_letters, k=5))
    dummy_order_id = f"REF-{user_id}-{datetime.now().strftime('%d-%m-%y')}-{rand_str}"
    payment_data = {"ORDERID": dummy_order_id}

    # 8. Run approval flow immediately
    await do_approve_flow_immediate(client, callback_query.message, slot_id, payment_data)
    await asyncio.sleep(2)

    # 9. Record claim in DB
    await patch_node(f"account_claims/{user_id}", {
        slot_id: True
    })

    # 10. Send REF-ID
    await client.send_message(
        callback_query.message.chat.id,
        f"𝗬𝗼𝘂𝗋 𝗥𝗘𝗙-𝗜𝗗 𝗶𝘀:\n<code>{dummy_order_id}</code>\n\n"
        "(𝗉𝗅𝖾𝖺𝗌𝖾 𝗌𝗁𝖺𝗋𝖾 𝗍𝗁𝗂𝗌 𝖨𝖣 𝗐𝗂𝗍𝗁 𝗈𝗎𝗋 𝗌𝗎𝗉𝗉𝗈𝗋𝗍 𝗍𝖾𝖺𝗆 𝖿𝗈𝗋 𝗉𝗋𝗈𝗆𝗉𝗍 𝖺𝗌𝗌𝗂𝗌𝗍𝖺𝗇𝖼𝖾)",
        parse_mode=ParseMode.HTML
    )

    # final answer to clear the callback
    try:
        await callback_query.answer()
    except:
        pass
  
  
  
@app.on_callback_query(filters.regex("^back_to_confirmation$"))
async def back_to_confirmation_handler(client, callback_query):
    ui = await read_ui_config("confirmation_flow")
    photo_url = ui.get("photo_url", "")
    caption   = ui.get("caption", "💸 Choose Payment Method:").replace("\\n", "\n")
    phonepe_btn_text = ui.get("button_text", "𝗣𝗁𝗈𝗇𝗲𝗣𝗲").replace("\\n", "\n")
    phonepe_cb       = ui.get("callback_data", "phonepe")

    # 1) Build the first row
    keyboard_rows = [
        [InlineKeyboardButton(phonepe_btn_text, callback_data=phonepe_cb)]
    ]

    # 2) Buy-with-points
    if await get_buy_with_points_setting():
        keyboard_rows.append([
            InlineKeyboardButton("Buy 𝗐𝗂𝗍𝗁 𝖮𝖮𝖱𝖻𝗂𝗍𝗌", callback_data="buy_with_points")
        ])

    # 3) Free trial—but only if feature on *and* user hasn’t claimed
    free = await read_node("free_trial_claims") or {}
    user_id = str(callback_query.from_user.id)
    if await get_free_trial_enabled() and user_id not in free:
        keyboard_rows.append([
            InlineKeyboardButton("𝖦𝖾𝗍 𝖥𝗋𝖾𝖾 𝖳𝗋𝗂𝖺𝗅", callback_data="free_trial")
        ])

    # 4) Send it back
    keyboard = InlineKeyboardMarkup(keyboard_rows)

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
        "𝖳𝗈 continue enjoying our service beyond your trial, simply select 𝖮𝖮𝖱 𝖯𝖺𝗒 as your preferred option.\n\n"
        f"𝖸𝗈𝗎𝗋 𝗍𝗋𝗂𝖺𝗅 𝖺𝗎𝗍𝗈-𝖾𝗇𝖽𝗌 𝖺𝖼𝖼𝗈𝗋𝖽𝗂𝗇𝗀𝗅𝗒 𝖺𝗌 𝗉𝖾𝗋 𝗍𝗁𝖾 𝗉𝗅𝖺𝗇 𝗒𝗈𝗎'𝗏𝖾 𝗌𝖾𝗅𝖾𝖼𝗍𝖾𝖽!"
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
        return await callback_query.answer(
            "OORverse feature is currently unavailable 🚀 Coming Soon..",
            show_alert=True
        )

    user_id = str(callback_query.from_user.id)
    slot_id = user_slot_choice.get(int(user_id), "slot_1")

    # 2) Already claimed?
    claimed_node = await read_node(f"free_trial_claims/{user_id}")
    if claimed_node:
        return await callback_query.answer(
            "You have already claimed your free trial.",
            show_alert=True
        )

    # 3) Check credential availability
    cred_key, cred_data = await get_valid_credential_for_slot_async(slot_id)
    if cred_data == "locked":
        # answer *first*, then show the locked message
        try:
            await callback_query.answer("Credentials locked.", show_alert=True)
        except:
            pass
        await show_locked_message(client, callback_query.message.chat.id)
        return

    if not cred_data:
        # handle_out_of_stock itself calls .answer()
        return await handle_out_of_stock(
            client, callback_query.message.chat.id, user_id, slot_id
        )

    # 4) Generate ORDERID + approval flow
    rand_str    = ''.join(random.choices(string.ascii_letters, k=5))
    dummy_order = f"FTRIAL-{user_id}-{datetime.now():%d-%m-%y}-{rand_str}"
    await do_approve_flow_immediate(client, callback_query.message, slot_id, {"ORDERID": dummy_order})
    await asyncio.sleep(2)

    # 5) Mark claimed
    await patch_node("free_trial_claims", { user_id: True })

    # 6) Send the dummy ORDERID
    await client.send_message(
        callback_query.message.chat.id,
        f"𝗬𝗼𝘂𝗿 𝗙𝗧𝗥𝗜𝗔𝗟-𝗜𝗗 𝗶𝘀:\n<code>{dummy_order}</code>\n\n"
        "(𝗉𝗅𝖾𝖺𝗌𝖾 𝗌𝗁𝖺𝗋𝖾 𝗍𝗁𝗂𝗌 𝖨𝖣 𝗐𝗂𝗍𝗁 𝗈𝗎𝗋 𝗌𝗎𝗉𝗉𝗈𝗋𝗍 𝗍𝖾𝖺𝗆 𝖿𝗈𝗋 𝗉𝗋𝗈𝗆𝗉𝗍 𝖺𝗌𝗌𝗂𝗌𝗍𝖺𝗇𝖼𝖾)",
        parse_mode=ParseMode.HTML
    )

    # final acknowledge
    try:
        await callback_query.answer()
    except:
        pass
# Free Trial end


# Global dictionary to store the timestamp when a user is asked for a txn ID.
pending_txn = {}  # Format: { user_id: datetime }

# In-memory
order_store = {}

pending_code_requests = {} # PROMO CODE


# ---------- Promo/Code helpers & handlers ----------

# ---------------- Helpers -----------------
async def is_superior_admin(user_id: int) -> bool:
    admin_conf = await read_node("admin_config") or {}
    admins = admin_conf.get("superior_admins", []) or []
    if not isinstance(admins, list):
        admins = [admins]
    admins = [str(x) for x in admins]
    return str(user_id) in admins

def gen_oor_id(nchars: int = 13) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "OOR" + "".join(secrets.choice(alphabet) for _ in range(nchars))

async def create_promo_code(code: str, slot_id: str, slot_name: str, amount: float,
                            created_by: int, max_uses: int = 1, expires_at: str = None,
                            custom: bool = False):
    payload = {
        "slot_id":      slot_id,
        "slot_name":    slot_name,
        "amount":       float(amount),
        "created_by":   created_by,
        "created_at":   datetime.now(pytz.timezone("Asia/Kolkata")).isoformat(),
        "custom":       bool(custom),
        "expires_at":   expires_at,
        "used_count":   0,
        "max_uses":     int(max_uses),
        "revoked":      False
    }
    await patch_node(f"promo_codes/{code}", payload)
    return payload

async def claim_promo_code_atomic(code: str, user_id: int, max_retries: int = 4):
    """
    Optimistic claim: read -> check -> patch -> verify.
    Returns (True, promo_obj) on success, (False, reason_str) on failure.
    NOTE: Replace with a DB transaction if available for perfect atomicity.
    """
    for attempt in range(max_retries):
        promo = await read_node(f"promo_codes/{code}")
        if not promo:
            return False, "CODE_NOT_FOUND"

        if promo.get("revoked"):
            return False, "CODE_REVOKED"

        # expiry
        expires_at = promo.get("expires_at")
        if expires_at:
            try:
                exp = datetime.fromisoformat(expires_at)
                if datetime.now(pytz.timezone("Asia/Kolkata")) > exp:
                    return False, "CODE_EXPIRED"
            except Exception:
                # ignore parse error
                pass

        try:
            used_count = int(promo.get("used_count", 0))
        except Exception:
            used_count = 0
        try:
            max_uses = int(promo.get("max_uses", 1))
        except Exception:
            max_uses = 1

        if used_count >= max_uses:
            return False, "CODE_ALREADY_USED_UP"

        # prepare update
        new_used_count = used_count + 1
        now_iso = datetime.now(pytz.timezone("Asia/Kolkata")).isoformat()
        used_by_list = promo.get("used_by", [])
        if not isinstance(used_by_list, list):
            used_by_list = []
        used_by_list.append({"user_id": user_id, "used_at": now_iso})

        patch_payload = {
            "used_count": new_used_count,
            "last_used_by": user_id,
            "last_used_at": now_iso,
            "used_by": used_by_list
        }

        # attempt patch
        try:
            await patch_node(f"promo_codes/{code}", patch_payload)
        except Exception:
            logger.exception("patch failed during claim attempt")
            await asyncio.sleep(0.1)
            continue

        # read back and verify
        promo_after = await read_node(f"promo_codes/{code}") or {}
        try:
            if int(promo_after.get("used_count", 0)) == new_used_count:
                return True, promo_after
        except Exception:
            pass

        # race — retry
        await asyncio.sleep(0.08)

    return False, "RACE_FAILED"

async def clear_pending_by_order(client, order_id: str):
    """
    Remove any pending_code_requests referencing this order and delete the prompt message(s).
    """
    for uid, p in list(pending_code_requests.items()):
        if p.get("order_id") == order_id:
            ctx = pending_code_requests.pop(uid, None)
            if not ctx:
                continue
            try:
                cmsg_id = ctx.get("context_msg_id")
                cchat = ctx.get("context_chat_id")
                if cmsg_id and cchat:
                    await client.delete_messages(chat_id=cchat, message_ids=cmsg_id)
            except Exception:
                logger.exception("Failed clearing pending prompt for order %s", order_id)

# ---------------- Admin UI: format helpers ----------------
def format_dt_short(iso_str: str) -> str:
    """Format ISO datetime to '10:47 AM 24 SEP' style (returns original on error)."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        tz = pytz.timezone("Asia/Kolkata")
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        else:
            dt = dt.astimezone(tz)
        s = dt.strftime("%I:%M %p %d %b")
        s = s.replace(" 0", " ")
        parts = s.split()
        if len(parts) >= 4:
            parts[3] = parts[3].upper()
        return " ".join(parts)
    except Exception:
        return iso_str


# Helper to check expiry given an ISO string
def _is_expired_iso(iso_str: str) -> bool:
    if not iso_str:
        return False
    try:
        dt = datetime.fromisoformat(iso_str)
        tz = pytz.timezone("Asia/Kolkata")
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        else:
            dt = dt.astimezone(tz)
        return datetime.now(tz) > dt
    except Exception:
        return False
        
        
# ---------------- UI builder ----------------
async def build_gen_ui():
    """
    Build the main /gen_code UI text and keyboard. Returns (text, keyboard).
    Caller must enforce admin check.
    """
    slots = await read_node("settings/slots") or {}
    rows = []
    any_enabled = False
    for sid, sdata in (slots.items() if isinstance(slots, dict) else []):
        if not isinstance(sdata, dict):
            continue
        if not sdata.get("enabled", False):
            continue
        any_enabled = True
        name = sdata.get("name", sid)
        amount = sdata.get("required_amount", 0)
        rows.append([InlineKeyboardButton(f"{name}", callback_data=f"slot_menu|{sid}")])

    if not any_enabled:
        txt = "<b>Generate promo codes</b>\n\nNo enabled slots found in settings/slots."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Close", callback_data="gen_close")]])
        return txt, kb

    # Add global cleanup button before Close
    rows.append([
    InlineKeyboardButton("🗑 Erase All", callback_data="promo_clear_request"),
    InlineKeyboardButton("Cancel", callback_data="gen_close")
    ])

    kb = InlineKeyboardMarkup(rows)
    txt = "<b>🎬 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲 𝗖𝗼𝗱𝗲𝘀</b>\n\n𝖲𝖾𝗅𝖾𝖼𝗍 𝖺 𝗉𝗅𝖺𝗇 𝗍𝗈 𝗆𝖺𝗇𝖺𝗀𝖾/𝗀𝖾𝗇𝖾𝗋𝖺𝗍𝖾 𝖼𝗈𝖽𝖾𝗌:"
    return txt, kb
    
    
    
@app.on_message(filters.private & filters.command("use_code"))
async def cmd_use_code(client, message):
    """
    Minimal /use_code: send a ForceReply and register a pending redeem context.
    No ORDERID required — user will paste the promo code and the existing
    on_private_text handler will process it (orderless redemption).
    """
    uid = message.from_user.id

    # remove any previous prompt for tidiness
    old = pending_code_requests.get(uid)
    if old:
        try:
            cmsg_id = old.get("context_msg_id")
            cchat = old.get("context_chat_id")
            if cmsg_id and cchat:
                await client.delete_messages(chat_id=cchat, message_ids=cmsg_id)
        except Exception:
            pass
        pending_code_requests.pop(uid, None)

    # send ForceReply only (clean UX)
    prompt_msg = await message.reply_text(
        "⌲ 𝖯𝖺𝗌𝗍𝖾 𝗍𝗁𝖾 𝖼𝗈𝖽𝖾 𝗇𝗈𝗐",
        reply_markup=ForceReply(True)
    )

    # store pending context (orderless)
    pending_code_requests[uid] = {
        "mode": "await_redeem_code",
        "order_id": None,               # indicates orderless flow
        "expires": time.time() + 60,
        "context_msg_id": prompt_msg.id,
        "context_chat_id": prompt_msg.chat.id
    }
    # no extra message — prompt alone is enough
        
    
# ---------- Unified promo manage callback (revoke / expiry / stats) ----------
@app.on_callback_query(filters.regex(r"^(revoke|expiry|stats)_[A-Z0-9]+"))
async def cb_promo_manage(client, callback_query):
    await callback_query.answer()
    data = callback_query.data
    try:
        mtype, code = data.split("_", 1)
    except Exception:
        return await callback_query.answer("Invalid callback.", show_alert=True)

    admin_id = callback_query.from_user.id
    if not await is_superior_admin(admin_id):
        return await callback_query.answer("𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱 🚫", show_alert=True)

    promo = await read_node(f"promo_codes/{code}")
    if not promo:
        return await callback_query.answer("Code not found.", show_alert=True)

    # REVOKE
    if mtype == "revoke":
        try:
            await patch_node(f"promo_codes/{code}", {"revoked": True})
        except Exception:
            logger.exception("Failed to revoke %s", code)
            return await callback_query.answer("Failed to revoke.", show_alert=True)
        try:
            await callback_query.message.edit_text(f"✅ 𝗖𝗼𝗱𝗲 {code} 𝗿𝗲𝘃𝗼𝗸𝗲𝗱", reply_markup=None)
        except Exception:
            pass
        return await callback_query.answer("Revoked.")

    # STATS
    if mtype == "stats":
        used_count = int(promo.get("used_count", 0))
        max_uses = int(promo.get("max_uses", 1))
        created_at = promo.get("created_at", "")
        created_by = str(promo.get("created_by", ""))
        last_used_at = promo.get("last_used_at", "")
        last_used_by = str(promo.get("last_used_by", ""))
        expires_at = promo.get("expires_at", "")
        revoked = bool(promo.get("revoked", False))
        slot_name = str(promo.get("slot_name", ""))
        slot_id = str(promo.get("slot_id", ""))
        amount = str(promo.get("amount", ""))

        SYM = '<a href="https://t.me/">⌘</a>'   # blank clickable symbol
        BSYM = f'[{SYM}]'                       # [⌘] 
        
        txt = (
            f"{BSYM} <b>Code:</b> <code>{code}</code>\n"
            f"{BSYM} <b>Slot:</b> {slot_name}\n"
            f"{BSYM} <b>Amount:</b> ₹{amount}\n"
            f"{BSYM} <b>Usage:</b> {used_count}/{max_uses}\n"
            f"{BSYM} <b>Created:</b> {format_dt_short(created_at)} by {created_by}\n"
            f"{BSYM} <b>Last used:</b> {format_dt_short(last_used_at)} by {last_used_by}\n"
            f"{BSYM} <b>Expires:</b> {format_dt_short(expires_at)}\n"
            f"{BSYM} <b>Revoked:</b> {str(revoked)}\n"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Revoke", callback_data=f"revoke_{code}"),
             InlineKeyboardButton("Set expiry", callback_data=f"expiry_{code}")],
            [InlineKeyboardButton("Back", callback_data="gen_close")]
        ])
        try:
            await callback_query.message.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        except Exception:
            await callback_query.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    # EXPIRY -> ask admin for minutes only
    if mtype == "expiry":
        try:
            msg = await callback_query.message.reply_text(
                "➡️ 𝖱𝖾𝗉𝗅𝗒 𝗐𝗂𝗍𝗁 𝖾𝗑𝗉𝗂𝗋𝗒 𝗂𝗇 <b>𝗺𝗶𝗻𝘂𝘁𝗲𝘀</b> (𝖾.𝗀. <code>30</code>) 𝖮𝗇𝗅𝗒 𝗆𝗂𝗇𝗎𝗍𝖾𝗌 𝖺𝗋𝖾 𝖺𝖼𝖼𝖾𝗉𝗍𝖾𝖽.",
                parse_mode=ParseMode.HTML,
                reply_markup=ForceReply(True)
            )
        except Exception:
            return await callback_query.answer("Could not open prompt.", show_alert=True)

        pending_code_requests[admin_id] = {
            "mode": "set_expiry",
            "code": code,
            "expires": time.time() + 60,            # 2 minutes to reply
            "context_msg_id": msg.id,
            "context_chat_id": msg.chat.id
        }
        return await callback_query.answer("𝖱𝖾𝗉𝗅𝗒 𝗍𝗈 𝗌𝖾𝗍 𝖾𝗑𝗉𝗂𝗋𝗒 (𝗺𝗶𝗻𝘂𝘁𝗲𝘀)")

# ---------- Clear (cleanup) flow ----------

# Add Clear button to the main UI: callback_data "promo_clear_request"
# We'll implement two callbacks: request -> confirm, then confirm -> do cleanup.

@app.on_callback_query(filters.regex(r"^promo_clear_request$"))
async def cb_promo_clear_request(client, callback_query):
    await callback_query.answer()
    admin_id = callback_query.from_user.id
    if not await is_superior_admin(admin_id):
        return await callback_query.answer("𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱 🚫", show_alert=True)

    # Confirm UI
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Confirm", callback_data="promo_clear_confirm")],
        [InlineKeyboardButton("Cancel", callback_data="gen_close")]
    ])
    txt = (
        "<b>🗑️ 𝗖𝗹𝗲𝗮𝗻𝘂𝗽 𝗣𝗿𝗼𝗺𝗼 𝗖𝗼𝗱𝗲𝘀</b>\n\n"
        "This will permanently Delete promo code nodes which are:\n"
        " • fully used\n"
        " • expired\n"
        " • revoked\n\n"
        "<i>⚠️ Press Confirm to proceed:</i>"
    )
    try:
        await callback_query.message.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception:
        await callback_query.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
    return

@app.on_callback_query(filters.regex(r"^promo_clear_confirm$"))
async def cb_promo_clear_confirm(client, callback_query):
    await callback_query.answer()
    admin_id = callback_query.from_user.id
    if not await is_superior_admin(admin_id):
        return await callback_query.answer("𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱 🚫", show_alert=True)

    # fetch all promos
    all_promos = await read_node("promo_codes") or {}
    if not isinstance(all_promos, dict):
        return await callback_query.message.edit_text("No promo codes found.", reply_markup=None)

    to_delete = {}
    deleted = []
    kept = []
    now_dt = datetime.now(pytz.timezone("Asia/Kolkata"))

    for code, p in all_promos.items():
        try:
            revoked = bool(p.get("revoked", False))
            used = int(p.get("used_count", 0)) if p.get("used_count") is not None else 0
            maxu = int(p.get("max_uses", 1)) if p.get("max_uses") is not None else 1
            exp = p.get("expires_at")
            is_expired = False
            if exp:
                try:
                    if datetime.fromisoformat(exp) < now_dt:
                        is_expired = True
                except Exception:
                    is_expired = False
            # decide
            if revoked or (used >= maxu) or is_expired:
                to_delete[code] = None   # PATCH { code: None } will delete
                deleted.append(code)
            else:
                kept.append(code)
        except Exception:
            kept.append(code)

    if not to_delete:
        return await callback_query.message.edit_text("😕 𝗡𝗼𝘁𝗵𝗶𝗻𝗴 𝘁𝗼 𝗱𝗲𝗹𝗲𝘁𝗲 — 𝗇𝗈 𝗎𝗌𝖾𝖽/𝖾𝗑𝗉𝗂𝗋𝖾𝖽/𝗋𝖾𝗏𝗈𝗄𝖾𝖽 𝖼𝗈𝖽𝖾𝗌 𝖿𝗈𝗎𝗇𝖽", reply_markup=None)

    # perform single PATCH to delete keys under promo_codes
    try:
        await patch_node("promo_codes", to_delete)
    except Exception:
        logger.exception("promo_clear_confirm: failed PATCH")
        # attempt per-code deletion fallback
        failed = []
        for c in deleted:
            try:
                await patch_node(f"promo_codes/{c}", None)
            except Exception:
                failed.append(c)
        success_count = len(deleted) - len(failed)
        return await callback_query.message.edit_text(
            f"Cleanup finished with partial failure.\nDeleted: {success_count}\nFailed: {len(failed)}",
            parse_mode=ParseMode.HTML
        )

    # success
    success_count = len(deleted)
    sample_list = "\n".join(deleted[:50])
    txt = (
        f"<b>✅ 𝗖𝗹𝗲𝗮𝗻𝘂𝗽 𝗰𝗼𝗺𝗽𝗹𝗲𝘁𝗲</b>\n\n"
        f"Deleted codes: {success_count}\n"
        f"Kept codes: {len(kept)}\n\n"
        f"Sample deleted:\n<code>{sample_list}</code>"
    )
    await callback_query.message.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=None)
    return
    
        
    
                            

# ---------------- Admin command ----------------
@app.on_message(filters.command("gen_code") & filters.private)
async def cmd_gen_code(client, message):
    user_id = message.from_user.id
    if not await is_superior_admin(user_id):
        return await message.reply_text("𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱 🚫")
    txt, kb = await build_gen_ui()
    await message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

# ---------------- Slot menu ----------------
@app.on_callback_query(filters.regex(r"^slot_menu\|"))
async def cb_slot_menu(client, callback_query):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    if not await is_superior_admin(user_id):
        return await callback_query.answer("𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱 🚫", show_alert=True)

    sid = callback_query.data.split("|", 1)[1]
    slot = await read_node(f"settings/slots/{sid}") or {}
    name = slot.get("name", sid)
    amount = slot.get("required_amount", 0)
    enabled = slot.get("enabled", False)

    txt = (
        f"<b>Slot:</b> {name}\n"
        f"<b>Price:</b> ₹{amount}\n"
        f"<b>Enabled:</b> {enabled}\n\n"
        f"𝖢𝗁𝗈𝗈𝗌𝖾 𝗐𝗁𝖺𝗍 𝗒𝗈𝗎 𝗐𝖺𝗇𝗍 𝗍𝗈 𝖽𝗈 𝖿𝗈𝗋 <b>{name}</b>:"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 Random", callback_data=f"slot_gen_random|{sid}"),
            InlineKeyboardButton("🔥 Custom", callback_data=f"slot_custom|{sid}")
        ],
        [InlineKeyboardButton("🎬 Active Codes", callback_data=f"slot_active|{sid}")],
        [InlineKeyboardButton("Close", callback_data="gen_close"),
         InlineKeyboardButton("Back", callback_data="gen_code_back")]
    ])

    await callback_query.message.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

# ---------------- Generate random (confirm + create) ----------------
@app.on_callback_query(filters.regex(r"^slot_gen_random\|"))
async def cb_slot_gen_random(client, callback_query):
    await callback_query.answer()
    admin_id = callback_query.from_user.id
    if not await is_superior_admin(admin_id):
        return await callback_query.answer("𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱 🚫", show_alert=True)

    sid = callback_query.data.split("|", 1)[1]
    slot_node = await read_node(f"settings/slots/{sid}") or {}
    slot_name = slot_node.get("name", sid)
    amount = float(slot_node.get("required_amount", 0))

    conf_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Confirm", callback_data=f"slot_gen_confirm|{sid}")],
        [InlineKeyboardButton("Cancel", callback_data=f"slot_menu|{sid}")]
    ])
    return await callback_query.message.edit_text(
        f"<b>🎲 𝗖𝗿𝗲𝗮𝘁𝗲 𝗥𝗮𝗻𝗱𝗼𝗺 𝗖𝗼𝗱𝗲</b>\n\n⚠️ 𝘈𝘳𝘦 𝘺𝘰𝘶 𝘴𝘶𝘳𝘦 𝘺𝘰𝘶 𝘸𝘢𝘯𝘵 𝘵𝘰 𝘤𝘳𝘦𝘢𝘵𝘦 𝘢 𝘤𝘰𝘥𝘦 𝘧𝘰𝘳 <b><i>{slot_name}</i></b> ( ₹{amount} ) ?",
        parse_mode=ParseMode.HTML,
        reply_markup=conf_kb
    )

@app.on_callback_query(filters.regex(r"^slot_gen_confirm\|"))
async def cb_slot_gen_confirm(client, callback_query):
    await callback_query.answer()
    admin_id = callback_query.from_user.id
    if not await is_superior_admin(admin_id):
        return await callback_query.answer("𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱 🚫", show_alert=True)

    sid = callback_query.data.split("|", 1)[1]
    slot_node = await read_node(f"settings/slots/{sid}") or {}
    slot_name = slot_node.get("name", sid)
    amount = float(slot_node.get("required_amount", 0))

    code = None
    for _ in range(8):
        cand = gen_oor_id()
        if not await read_node(f"promo_codes/{cand}"):
            code = cand
            break
    if not code:
        return await callback_query.message.edit_text("Failed to generate unique code. Try again.", parse_mode=ParseMode.HTML)

    await create_promo_code(code=code, slot_id=sid, slot_name=slot_name,
                            amount=amount, created_by=admin_id, max_uses=1, custom=False)
                            
    # use a "blank" hyperlink target for the symbol — goes to t.me root (acts as a clickable symbol)
    SYM = '<a href="https://t.me/">⌘</a>'   # blank clickable symbol
    BSYM = f'[{SYM}]'                       # [⌘]                             

    txt = (
        "✅ <b>𝗖𝗼𝗱𝗲 𝗰𝗿𝗲𝗮𝘁𝗲𝗱!</b>\n\n"
        f"{BSYM} <b>Code:</b> <code>{code}</code>\n"
        f"{BSYM} <b>Slot:</b> {slot_name}\n"
        f"{BSYM} <b>Amount:</b> ₹{amount}\n"
        f"{BSYM} <b>Created at:</b> {format_dt_short(datetime.now(pytz.timezone('Asia/Kolkata')).isoformat())}\n\n"
        "<i>One-time use by default:</i>"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Revoke", callback_data=f"revoke_{code}"),
         InlineKeyboardButton("🕑 Set Expiry", callback_data=f"expiry_{code}")],
        [InlineKeyboardButton("Get stats", callback_data=f"stats_{code}")],
        [InlineKeyboardButton("Back to Slot", callback_data=f"slot_menu|{sid}")]
    ])

    await callback_query.message.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

# ---------------- Custom generation (admin reply) ----------------
@app.on_callback_query(filters.regex(r"^slot_custom\|"))
async def cb_slot_custom(client, callback_query):
    await callback_query.answer()
    admin_id = callback_query.from_user.id
    if not await is_superior_admin(admin_id):
        return await callback_query.answer("𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱 🚫", show_alert=True)

    sid = callback_query.data.split("|", 1)[1]
    slot_node = await read_node(f"settings/slots/{sid}") or {}
    slot_name = slot_node.get("name", sid)
    amount = float(slot_node.get("required_amount", 0))

    msg = await callback_query.message.reply_text(
        f"Send the custom code string you want for <b>{slot_name}</b> (₹{amount}).\n\n"
        "Example: <code>OORABC12345DEF</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=ForceReply(True)
    )

    pending_code_requests[admin_id] = {
        "mode": "custom_code_gen",
        "slot_id": sid,
        "slot_name": slot_name,
        "amount": amount,
        "expires": time.time() + 60,
        "context_msg_id": msg.id,
        "context_chat_id": msg.chat.id
    }

# ---------------- Active codes listing ----------------
@app.on_callback_query(filters.regex(r"^slot_active\|"))
async def cb_slot_active(client, callback_query):
    await callback_query.answer()
    admin_id = callback_query.from_user.id
    if not await is_superior_admin(admin_id):
        return await callback_query.answer("𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱 🚫", show_alert=True)

    sid = callback_query.data.split("|", 1)[1]
    slot_node = await read_node(f"settings/slots/{sid}") or {}
    slot_name = slot_node.get("name", sid)

    all_promos = await read_node("promo_codes") or {}
    active = []
    now_dt = datetime.now(pytz.timezone("Asia/Kolkata"))
    for code, p in (all_promos.items() if isinstance(all_promos, dict) else []):
        try:
            if p.get("slot_id") != sid:
                continue
            if p.get("revoked"):
                continue
            used = int(p.get("used_count", 0))
            maxu = int(p.get("max_uses", 1))
            if used >= maxu:
                continue
            exp = p.get("expires_at")
            if exp:
                try:
                    if datetime.fromisoformat(exp) < now_dt:
                        continue
                except Exception:
                    pass
            active.append((code, p))
        except Exception:
            continue

    if not active:
        txt = f"<b>🎬 𝗔𝗰𝘁𝗶𝘃𝗲 𝗰𝗼𝗱𝗲𝘀</b>\n\n🤖 𝖭𝗈 𝖺𝖼𝗍𝗂𝗏𝖾 (𝗎𝗇𝗎𝗌𝖾𝖽) 𝖼𝗈𝖽𝖾𝗌 𝖿𝗈𝗎𝗇𝖽 𝖿𝗈𝗋 <b>{slot_name}</b>."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data=f"slot_menu|{sid}")]])
        return await callback_query.message.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

    active = sorted(active, key=lambda x: x[1].get("created_at", ""), reverse=True)[:20]
    rows = []
    for code, p in active:
        used = int(p.get("used_count", 0))
        maxu = int(p.get("max_uses", 1))
        rows.append([InlineKeyboardButton(f"{code} ({used}/{maxu})", callback_data=f"view_code|{code}")])

    kb = InlineKeyboardMarkup(rows + [[InlineKeyboardButton("Back", callback_data=f"slot_menu|{sid}")]])
    txt = f"<b>🎬 𝗔𝗰𝘁𝗶𝘃𝗲 𝗰𝗼𝗱𝗲𝘀 𝗳𝗼𝗿 {slot_name}</b>\n\n𝖲𝖾𝗅𝖾𝖼𝗍 𝖺 𝖼𝗈𝖽𝖾 𝗍𝗈 𝗏𝗂𝖾𝗐 𝖽𝖾𝗍𝖺𝗂𝗅𝗌:"
    await callback_query.message.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

# ---------------- View code details ----------------
@app.on_callback_query(filters.regex(r"^view_code\|"))
async def cb_view_code(client, callback_query):
    await callback_query.answer()
    admin_id = callback_query.from_user.id
    if not await is_superior_admin(admin_id):
        return await callback_query.answer("𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱 🚫", show_alert=True)

    code = callback_query.data.split("|", 1)[1]
    promo = await read_node(f"promo_codes/{code}")
    if not promo:
        return await callback_query.answer("Code not found.", show_alert=True)

    used = int(promo.get("used_count", 0))
    maxu = int(promo.get("max_uses", 1))
    created_at = format_dt_short(promo.get("created_at", ""))
    expires_at_raw = promo.get("expires_at", "")
    expires_at = format_dt_short(expires_at_raw) if expires_at_raw else "Nil"
    revoked = str(promo.get("revoked", False))
    slot_name = str(promo.get("slot_name", ""))
    amount = str(promo.get("amount", ""))

    # use a "blank" hyperlink target for the symbol — goes to t.me root (acts as a clickable symbol)
    SYM = '<a href="https://t.me/">⌘</a>'   # blank clickable symbol
    BSYM = f'[{SYM}]'                       # [⌘] 

    txt = (
        f"{BSYM} <b>Code:</b> <code>{code}</code>\n"
        f"{BSYM} <b>Slot:</b> {slot_name}\n"
        f"{BSYM} <b>Amount:</b> ₹{amount}\n"
        f"{BSYM} <b>Usage:</b> {used}/{maxu}\n"
        f"{BSYM} <b>Created:</b> {created_at}\n"
        f"{BSYM} <b>Expires:</b> {expires_at}\n"
        f"{BSYM} <b>Revoked:</b> {revoked}\n"
    )

    # Buttons: Revoke / Set expiry side-by-side, Back below
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Revoke", callback_data=f"revoke_{code}"),
         InlineKeyboardButton("🕑 Set Expiry", callback_data=f"expiry_{code}")],
        [InlineKeyboardButton("Back", callback_data=f"slot_active|{promo.get('slot_id', '')}")]
    ])

    await callback_query.message.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

# ---------------- Use Code callback (user) ----------------
@app.on_callback_query(filters.regex(r"^usecode_"))
async def cb_use_code(client, callback_query):
    """
    When user taps Use Code on the QR message.
    Minimal robust version: make sure pending_code_requests stores the exact keys
    your on_private_text expects (context_msg_id/context_chat_id), and log them.
    """
    try:
        # stop spinner immediately
        await callback_query.answer()
    except Exception:
        pass

    user_id = callback_query.from_user.id
    # callback_data format: usecode_<order_id>
    order_id = callback_query.data.split("_", 1)[1]

    # Verify order exists and belongs to the tapping user
    order_info = order_store.get(order_id)
    if not order_info:
        # order missing or expired
        return await callback_query.message.reply_text("No active payment session found for you (session expired).")

    if order_info.get("user_id") != user_id:
        # it exists but belongs to someone else
        return await callback_query.answer("This payment session belongs to someone else.", show_alert=True)

    # Now send ForceReply prompt reliably
    try:
        prompt_msg = await callback_query.message.reply_text(
            "⌲ 𝖯𝖺𝗌𝗍𝖾 𝗍𝗁𝖾 𝖼𝗈𝖽𝖾 𝗇𝗈𝗐",
            reply_markup=ForceReply(True)
        )
    except Exception as e:
        logger.exception("Failed to send ForceReply in cb_use_code: %r", e)
        return await callback_query.message.reply_text("Could not open code prompt. Try again.")

    # get message id robustly (pyrogram versions differ)
    try:
        pm_id = getattr(prompt_msg, "message_id", None) or getattr(prompt_msg, "id", None)
    except Exception:
        pm_id = None

    try:
        pm_chat = getattr(prompt_msg.chat, "id", None)
    except Exception:
        pm_chat = None

    # store pending context (include context_chat_id for reliable deletions)
    pending_code_requests[user_id] = {
        "mode": "await_redeem_code",
        "order_id": order_id,
        "expires": time.time() + 60,
        "context_msg_id": pm_id,
        "context_chat_id": pm_chat
    }

    logger.info(f"[UseCode] pending set uid={user_id} order={order_id} prompt_msg={pm_id} chat={pm_chat}")

    # give a small ephemeral feedback to the user (non-alert)
    try:
        await callback_query.answer("Paste the code in the prompt I just sent.")
    except Exception:
        pass

# ---------------- Back/Close handlers ----------------
@app.on_callback_query(filters.regex(r"^gen_code_back$"))
async def cb_gen_back(client, callback_query):
    # use callback_query.from_user for auth (the user who pressed the button)
    admin_id = callback_query.from_user.id
    await callback_query.answer()
    if not await is_superior_admin(admin_id):
        return await callback_query.answer("𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱 🚫", show_alert=True)

    txt, kb = await build_gen_ui()
    # edit the existing message to show the main UI again
    try:
        await callback_query.message.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception:
        # fallback: send a new message if edit fails
        try:
            await callback_query.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        except Exception as e:
            logger.exception("Failed to show gen UI on back: %r", e)

@app.on_callback_query(filters.regex(r"^gen_close$"))
async def cb_gen_close(client, callback_query):
    await callback_query.answer()
    try:
        await callback_query.message.delete()
    except Exception:
        pass

# ---------------- ForceReply private text handler ----------------
@app.on_message(filters.private & filters.text)
async def on_private_text(client, message):
    uid = message.from_user.id
    text = (message.text or "").strip()
    ctx = pending_code_requests.get(uid)
    
    logger.info(f"[on_private_text] uid={uid} ctx_exists={bool(ctx)} ctx_keys={list(ctx.keys()) if isinstance(ctx, dict) else ctx}")

    # nothing pending for this user — let other handlers process the message
    if not ctx:
        return

    mode = ctx.get("mode")

    # ---------- custom code generation (admin) ----------
    if mode == "custom_code_gen":
        # timeout
        if time.time() > ctx.get("expires", 0):
            try:
                cmsg_id = ctx.get("context_msg_id")
                cchat = ctx.get("context_chat_id", message.chat.id)
                if cmsg_id and cchat:
                    await client.delete_messages(chat_id=cchat, message_ids=cmsg_id)
            except Exception:
                pass
            pending_code_requests.pop(uid, None)
            return await message.reply_text("⏱️ 𝗧𝗶𝗺𝗲𝗱 𝗼𝘂𝘁 !!\n𝖲𝗍𝖺𝗋𝗍 𝖼𝗎𝗌𝗍𝗈𝗆 𝖼𝗈𝖽𝖾 𝗀𝖾𝗇𝖾𝗋𝖺𝗍𝗂𝗈𝗇 𝖺𝗀𝖺𝗂𝗇")

        # validate code format
        if not re.fullmatch(r"OOR[A-Z0-9]{6,20}", text):
            return await message.reply_text("⚠️ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗳𝗼𝗿𝗺𝗮𝘁 !!\n𝖴𝗌𝖾 𝖮𝖮𝖱 + 𝗎𝗉𝗉𝖾𝗋𝖼𝖺𝗌𝖾 𝗅𝖾𝗍𝗍𝖾𝗋𝗌/𝖽𝗂𝗀𝗂𝗍𝗌 (6-20 𝖼𝗁𝖺𝗋𝗌)")

        # uniqueness
        existing = await read_node(f"promo_codes/{text}")
        if existing:
            return await message.reply_text("⚠️ 𝗧𝗵𝗮𝘁 𝗰𝗼𝗱𝗲 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗲𝘅𝗶𝘀𝘁𝘀. 𝗖𝗵𝗼𝗼𝘀𝗲 𝗮𝗻𝗼𝘁𝗵𝗲𝗿 𝘀𝘁𝗿𝗶𝗻𝗴.")

        # create promo
        await create_promo_code(code=text,
                                slot_id=ctx["slot_id"],
                                slot_name=ctx["slot_name"],
                                amount=ctx["amount"],
                                created_by=uid,
                                max_uses=1,
                                custom=True)

        # delete prompt
        try:
            cmsg_id = ctx.get("context_msg_id")
            cchat = ctx.get("context_chat_id", message.chat.id)
            if cmsg_id and cchat:
                await client.delete_messages(chat_id=cchat, message_ids=cmsg_id)
        except Exception:
            pass

        pending_code_requests.pop(uid, None)

        # show Revoke/Set expiry side-by-side + Get Stats button below + Back to slot
        mgmt_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚫 Revoke", callback_data=f"revoke_{text}"),
             InlineKeyboardButton("🕑 Set Expiry", callback_data=f"expiry_{text}")],
            [InlineKeyboardButton("Get stats", callback_data=f"stats_{text}")],
            [InlineKeyboardButton("Back to slot", callback_data=f"slot_menu|{ctx['slot_id']}")]
        ])
        return await message.reply_text(f"✅ 𝗖𝘂𝘀𝘁𝗼𝗺 𝗽𝗿𝗼𝗺𝗼 𝗰𝗿𝗲𝗮𝘁𝗲𝗱: <code>{text}</code>", parse_mode=ParseMode.HTML, reply_markup=mgmt_kb)

# ---------- redeem code flow (user) ----------
    if mode == "await_redeem_code":
        try:
            logger.info(f"[Redeem] entering redeem branch uid={uid} ctx_keys={list(ctx.keys()) if isinstance(ctx, dict) else ctx}")

            # timeout: delete prompt and clear pending
            if time.time() > ctx.get("expires", 0):
                try:
                    cmsg_id = ctx.get("context_msg_id")
                    cchat = ctx.get("context_chat_id", message.chat.id)
                    if cmsg_id and cchat:
                        await client.delete_messages(chat_id=cchat, message_ids=cmsg_id)
                except Exception:
                    logger.exception("[Redeem] error deleting expired prompt")
                pending_code_requests.pop(uid, None)
                logger.info("[Redeem] timed out -> returning")
                return await message.reply_text("⏱️ 𝗧𝗶𝗺𝗲𝗱 𝗼𝘂𝘁 !!\n𝖯𝗋𝖾𝗌𝗌 𝖴𝗌𝖾 𝖢𝗈𝖽𝖾 𝖺𝗀𝖺𝗂𝗇")

            code_text = text.strip().upper()
            logger.info(f"[Redeem] code_text='{code_text}'")

            if not re.fullmatch(r"OOR[A-Z0-9]{6,20}", code_text):
                logger.info("[Redeem] invalid code format")
                return await message.reply_text("⚠️ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗰𝗼𝗱𝗲 𝗳𝗼𝗿𝗺𝗮𝘁\n𝖬𝖺𝗄𝖾 𝗌𝗎𝗋𝖾 𝗒𝗈𝗎 𝗉𝖺𝗌𝗍𝖾𝖽 𝗍𝗁𝖾 𝖾𝗑𝖺𝖼𝗍 𝖼𝗈𝖽𝖾")

            order_id = ctx.get("order_id")
            logger.info(f"[Redeem] order_id in ctx = {order_id!r}")

            # If order_id is present → QR flow; otherwise orderless (/use_code)
            if not order_id:
                logger.info("[Redeem] orderless flow (no QR order_id)")

                promo = await read_node(f"promo_codes/{code_text}")
                logger.info(f"[Redeem] promo fetched: exists={bool(promo)}")
                if not promo:
                    logger.info("[Redeem] promo not found")
                    return await message.reply_text("⚠️ 𝗧𝗵𝗶𝘀 𝗰𝗼𝗱𝗲 𝗱𝗼𝗲𝘀 𝗻𝗼𝘁 𝗲𝘅𝗶𝘀𝘁 !!")

                if promo.get("revoked"):
                    logger.info("[Redeem] promo revoked")
                    return await message.reply_text("⚠️ 𝗧𝗵𝗶𝘀 𝗰𝗼𝗱𝗲 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗿𝗲𝘃𝗼𝗸𝗲𝗱 !!")

                # Attempt atomic claim
                logger.info("[Redeem] attempting claim_promo_code_atomic")
                success, result = await claim_promo_code_atomic(code_text, uid)
                logger.info(f"[Redeem] claim result: success={success} result={result}")
                if not success:
                    if result == "CODE_ALREADY_USED_UP":
                        return await message.reply_text("⚠️ 𝗧𝗵𝗶𝘀 𝗰𝗼𝗱𝗲 𝗵𝗮𝘀 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗯𝗲𝗲𝗻 𝘂𝘀𝗲𝗱 !!")
                    if result == "CODE_EXPIRED":
                        return await message.reply_text("⚠️ 𝗧𝗵𝗶𝘀 𝗰𝗼𝗱𝗲 𝗵𝗮𝘀 𝗲𝘅𝗽𝗶𝗿𝗲𝗱 !!")
                    if result == "CODE_REVOKED":
                        return await message.reply_text("⚠️ 𝗧𝗵𝗶𝘀 𝗰𝗼𝗱𝗲 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗿𝗲𝘃𝗼𝗸𝗲𝗱 !!")
                    if result == "RACE_FAILED":
                        return await message.reply_text("Could not claim the code (race). Try again.")
                    return await message.reply_text("Failed to claim code: " + str(result))

                # success: claimed — delete prompt and clear pending
                try:
                    cmsg_id = ctx.get("context_msg_id")
                    cchat = ctx.get("context_chat_id", message.chat.id)
                    if cmsg_id and cchat:
                        await client.delete_messages(chat_id=cchat, message_ids=cmsg_id)
                except Exception:
                    logger.exception("[Redeem] failed deleting prompt after successful orderless claim")

                pending_code_requests.pop(uid, None)
                logger.info("[Redeem] orderless claim succeeded; calling approve flow")

                slot_id = promo.get("slot_id")
                data = {
                    "ORDERID": code_text,
                    "TXNAMOUNT": str(promo.get("amount", "0")),
                    "STATUS": "TXN_SUCCESS"
                }
                try:
                    await do_approve_flow_immediate(client, message, slot_id, data)
                except Exception:
                    logger.exception("approve flow failed for orderless promo redemption")
                    return await message.reply_text("Approval flow failed. Contact admin.")

                # notify admins (kept as before)...
                txn_node = await read_node(f"transactions/{code_text}") or {}
                start_time = txn_node.get("start_time")
                end_time = txn_node.get("end_time")

                def _format_range(s, e):
                    if not s or not e:
                        return "Nil"
                    def _parse(dt_str):
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
                            try:
                                return datetime.strptime(dt_str, fmt)
                            except Exception:
                                continue
                        try:
                            return datetime.fromisoformat(dt_str)
                        except Exception:
                            return None
                    sdt = _parse(s)
                    edt = _parse(e)
                    if not sdt or not edt:
                        return "Nil"
                    tz = pytz.timezone("Asia/Kolkata")
                    if sdt.tzinfo is None:
                        sdt = tz.localize(sdt)
                    else:
                        sdt = sdt.astimezone(tz)
                    if edt.tzinfo is None:
                        edt = tz.localize(edt)
                    else:
                        edt = edt.astimezone(tz)
                    time_part = f"{sdt.strftime('%I:%M %p').lstrip('0')} - {edt.strftime('%I:%M %p').lstrip('0')}"
                    date_part = edt.strftime("%d %b").upper()
                    return f"{time_part} {date_part}"

                details_str = _format_range(start_time, end_time)
                SYM = '<a href="https://t.me/">⌘</a>'
                BSYM = f'[{SYM}]'
                redeemer_name = (message.from_user.first_name or message.from_user.username or "User")
                redeemer_link = f'<a href="tg://user?id={uid}">{redeemer_name}</a>'
                admin_txt = (
                    "✅ <b>𝗣𝗿𝗼𝗺𝗼 𝗖𝗼𝗱𝗲 𝗥𝗲𝗱𝗲𝗲𝗺𝗲𝗱!</b>\n\n"
                    f"{BSYM} <b>Slot :</b> {promo.get('slot_name')}\n"
                    f"{BSYM} <b>Details :</b> {details_str}\n"
                    f"{BSYM} <b>Code :</b> <code>{code_text}</code>\n"
                    f"{BSYM} <b>Amount :</b> ₹{promo.get('amount')}\n\n"
                    f"{BSYM} <b>Redeemed by :</b> {redeemer_link} <code>[{uid}]</code>"
                )

                admin_conf = await read_node("admin_config") or {}
                admins = admin_conf.get("superior_admins", []) or []
                if not isinstance(admins, list):
                    admins = [admins]
                for adm in admins:
                    try:
                        adm_id = int(adm)
                        await client.send_message(chat_id=adm_id, text=admin_txt, parse_mode=ParseMode.HTML)
                    except Exception:
                        logger.exception("failed sending admin notify for orderless")

                return

            # ---------- QR-based flow (original behavior) ----------
            logger.info(f"[Redeem] QR-based flow for order {order_id}")
            order_info = order_store.get(order_id)
            logger.info(f"[Redeem] order_info found: {order_info!r}")
            if not order_info or order_info.get("user_id") != uid:
                try:
                    cmsg_id = ctx.get("context_msg_id")
                    cchat = ctx.get("context_chat_id", message.chat.id)
                    if cmsg_id and cchat:
                        await client.delete_messages(chat_id=cchat, message_ids=cmsg_id)
                except Exception:
                    logger.exception("[Redeem] failed deleting prompt for invalid order")
                pending_code_requests.pop(uid, None)
                return await message.reply_text("No active payment session found for you. Open the QR and press Use Code again.")

            slot_id = order_info["slot_id"]
            slot_node = await read_node(f"settings/slots/{slot_id}") or {}
            try:
                required = float(slot_node.get("required_amount", 0))
            except Exception:
                required = 0.0
            logger.info(f"[Redeem] required amount for slot {slot_id} = {required}")

            promo = await read_node(f"promo_codes/{code_text}")
            logger.info(f"[Redeem] promo lookup: {bool(promo)}")
            if not promo:
                return await message.reply_text("⚠️ 𝗧𝗵𝗶𝘀 𝗰𝗼𝗱𝗲 𝗱𝗼𝗲𝘀 𝗻𝗼𝘁 𝗲𝘅𝗶𝘀𝘁")

            if promo.get("revoked"):
                return await message.reply_text("⚠️ 𝗧𝗵𝗶𝘀 𝗰𝗼𝗱𝗲 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗿𝗲𝘃𝗼𝗸𝗲𝗱")
            try:
                promo_amount = float(promo.get("amount", 0))
            except Exception:
                promo_amount = 0.0
            logger.info(f"[Redeem] promo_amount={promo_amount}")

            if abs(promo_amount - required) > 0.001:
                logger.info("[Redeem] amount mismatch")
                return await message.reply_text(f"😕 𝖳𝗁𝗂𝗌 𝖼𝗈𝖽𝖾 𝗂𝗌 𝘄𝗼𝗿𝘁𝗵 ₹{promo.get('amount')} 𝖺𝗇𝖽 𝗇𝗈𝗍 𝗏𝖺𝗅𝗂𝖽 𝖿𝗈𝗋 𝘆𝗼𝘂𝗿 𝘀𝗲𝗹𝗲𝗰𝘁𝗲𝗱 𝗽𝗹𝗮𝗻 (₹{required})")
            if promo.get("slot_id") != slot_id:
                logger.info("[Redeem] slot mismatch: promo_slot={promo.get('slot_id')} expected={slot_id}")
                return await message.reply_text(f"😕 𝖳𝗁𝗂𝗌 𝖼𝗈𝖽𝖾 𝗂𝗌 𝘁𝗶𝗲𝗱 𝘁𝗼 {promo.get('slot_name')} 𝗇𝗈𝗍 𝘆𝗼𝘂𝗿 𝗰𝘂𝗿𝗿𝗲𝗻𝘁 𝗽𝗹𝗮𝗻")

            # claim atomically
            logger.info("[Redeem] attempting claim_promo_code_atomic for QR flow")
            success, result = await claim_promo_code_atomic(code_text, uid)
            logger.info(f"[Redeem] claim result: success={success} result={result}")
            if not success:
                if result == "CODE_ALREADY_USED_UP":
                    return await message.reply_text("⚠️ 𝗧𝗵𝗶𝘀 𝗰𝗼𝗱𝗲 𝗵𝗮𝘀 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗯𝗲𝗲𝗻 𝘂𝘀𝗲𝗱")
                if result == "CODE_EXPIRED":
                    return await message.reply_text("⚠️ 𝗧𝗵𝗶𝘀 𝗰𝗼𝗱𝗲 𝗵𝗮𝘀 𝗲𝘅𝗽𝗶𝗿𝗲𝗱")
                if result == "CODE_REVOKED":
                    return await message.reply_text("⚠️ 𝗧𝗵𝗶𝘀 𝗰𝗼𝗱𝗲 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗿𝗲𝘃𝗼𝗸𝗲𝗱")
                if result == "RACE_FAILED":
                    return await message.reply_text("Could not claim the code (race). Try again.")
                return await message.reply_text("Failed to claim code: " + str(result))

            # success: claimed
            order_store.pop(order_id, None)
            logger.info(f"[Redeem] claimed promo {code_text} and removed order {order_id} from store")

            # delete the prompt
            try:
                cmsg_id = ctx.get("context_msg_id")
                cchat = ctx.get("context_chat_id", message.chat.id)
                if cmsg_id and cchat:
                    await client.delete_messages(chat_id=cchat, message_ids=cmsg_id)
            except Exception:
                logger.exception("[Redeem] failed deleting prompt after claim")

            # Also clear any other pending prompts for this order (just in case)
            try:
                await clear_pending_by_order(client, order_id)
            except Exception:
                logger.exception("[Redeem] clear_pending_by_order failed")

            # craft synthetic paytm-like data & call approve flow
            data = {
                "ORDERID": code_text,
                "TXNAMOUNT": str(promo.get("amount", required)),
                "STATUS": "TXN_SUCCESS"
            }

            try:
                await do_approve_flow_immediate(client, message, slot_id, data)
            except Exception:
                logger.exception("approve flow failed for promo redemption")
                return await message.reply_text("Approval flow failed. Contact admin.")

            # Read transaction node for the code to show start/end times (if available)
            txn_node = await read_node(f"transactions/{code_text}") or {}
            start_time = txn_node.get("start_time")  # likely "YYYY-MM-DD HH:MM:SS"
            end_time = txn_node.get("end_time")

            def _format_range(s, e):
                # attempt several parse formats and return "h:mm AM - h:mm PM DD MON"
                if not s or not e:
                    return "Nil"
                def _parse(dt_str):
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
                        try:
                            return datetime.strptime(dt_str, fmt)
                        except Exception:
                            continue
                    try:
                        return datetime.fromisoformat(dt_str)
                    except Exception:
                        return None
                sdt = _parse(s)
                edt = _parse(e)
                if not sdt or not edt:
                    return "Nil"
                tz = pytz.timezone("Asia/Kolkata")
                if sdt.tzinfo is None:
                    sdt = tz.localize(sdt)
                else:
                    sdt = sdt.astimezone(tz)
                if edt.tzinfo is None:
                    edt = tz.localize(edt)
                else:
                    edt = edt.astimezone(tz)
                # times and date
                time_part = f"{sdt.strftime('%I:%M %p').lstrip('0')} - {edt.strftime('%I:%M %p').lstrip('0')}"
                date_part = edt.strftime("%d %b").upper()
                return f"{time_part} {date_part}"

            details_str = _format_range(start_time, end_time)

            # Build admin notification text (pretty)
            SYM = '<a href="https://t.me/">⌘</a>'   # blank clickable symbol
            BSYM = f'[{SYM}]'                       # [⌘] 
            
            # Redeemer link text
            redeemer_name = (message.from_user.first_name or message.from_user.username or "User")
            redeemer_link = f'<a href="tg://user?id={uid}">{redeemer_name}</a>'
            admin_txt = (
                "✅ <b>𝗣𝗿𝗼𝗺𝗼 𝗖𝗼𝗱𝗲 𝗥𝗲𝗱𝗲𝗲𝗺𝗲𝗱!</b>\n\n"
                f"{BSYM} <b>Slot :</b> {promo.get('slot_name')}\n"
                f"{BSYM} <b>Details :</b> {details_str}\n"
                f"{BSYM} <b>Code :</b> <code>{code_text}</code>\n"
                f"{BSYM} <b>Amount :</b> ₹{promo.get('amount')}\n\n"
                f"{BSYM} <b>Redeemed by :</b> {redeemer_link} <code>[{uid}]</code>"
            )

            # Notify superior admins
            admin_conf = await read_node("admin_config") or {}
            admins = admin_conf.get("superior_admins", []) or []
            if not isinstance(admins, list):
                admins = [admins]
            for adm in admins:
                try:
                    adm_id = int(adm)
                    await client.send_message(chat_id=adm_id, text=admin_txt, parse_mode=ParseMode.HTML)
                except Exception:
                    logger.exception("failed sending admin notify")

            pending_code_requests.pop(uid, None)
            return

        except Exception:
            logger.exception("[Redeem] unexpected error in await_redeem_code")
            # ensure we clean up pending so user can retry
            try:
                pending_code_requests.pop(uid, None)
            except Exception:
                pass
            return await message.reply_text("An unexpected error occurred. Try again.")

    # ---------- admin set_expiry handling ----------
    if mode == "set_expiry":
        # only accept minutes (digits)
        if time.time() > ctx.get("expires", 0):
            try:
                cmsg_id = ctx.get("context_msg_id")
                cchat = ctx.get("context_chat_id", message.chat.id)
                if cmsg_id and cchat:
                    await client.delete_messages(chat_id=cchat, message_ids=cmsg_id)
            except Exception:
                pass
            pending_code_requests.pop(uid, None)
            return await message.reply_text("⏱️ 𝗧𝗶𝗺𝗲𝗱 𝗼𝘂𝘁 !! 𝖲𝗍𝖺𝗋𝗍 '𝖲𝖾𝗍 𝖾𝗑𝗉𝗂𝗋𝗒' 𝖺𝗀𝖺𝗂𝗇")

        code = ctx.get("code")
        val = text.strip()
        if not re.fullmatch(r"\d+", val):
            return await message.reply_text("⚠️ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗳𝗼𝗿𝗺𝗮𝘁 !! 𝖱𝖾𝗉𝗅𝗒 𝗐𝗂𝗍𝗁 𝗺𝗶𝗻𝘂𝘁𝗲𝘀 𝗈𝗇𝗅𝗒 (e.g. 30).")
        mins = int(val)
        exp_dt = datetime.now(pytz.timezone("Asia/Kolkata")) + timedelta(minutes=mins)
        exp_iso = exp_dt.isoformat()
        await patch_node(f"promo_codes/{code}", {"expires_at": exp_iso})

        # delete prompt (tidy)
        try:
            cmsg_id = ctx.get("context_msg_id")
            cchat = ctx.get("context_chat_id", message.chat.id)
            if cmsg_id and cchat:
                await client.delete_messages(chat_id=cchat, message_ids=cmsg_id)
        except Exception:
            pass

        pending_code_requests.pop(uid, None)
        pretty = format_dt_short(exp_iso)
        return await message.reply_text(f"✅ 𝗘𝘅𝗽𝗶𝗿𝘆 𝘀𝗲𝘁 𝗳𝗼𝗿 <code>{code}</code>\n𝗮𝘁 {pretty}", parse_mode=ParseMode.HTML)

    # unknown mode
    pending_code_requests.pop(uid, None)
    return
# ---------------- End module ----------------

  

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
                await do_reject_flow_immediate(client, message, "𝖠𝗆𝗈𝗎𝗇𝗍 𝗆𝗂𝗌𝗆𝖺𝗍𝖼𝗁")
            else:
                # check if already used
                already_used = await is_orderid_used_async(order_id)
                if not already_used or bypass:
                    await mark_orderid_used_async(order_id)
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



async def unified_loop(client, msg, order_id, start_ts):
    chat_id, msg_id = msg.chat.id, msg.id
    logger.info(f"[Unified] started for message {msg_id}, order {order_id}")

    phase_step = 0
    caption_state = "phase"
    last_caption = CAP1_PHASES[0]
    last_caption_change = time.monotonic()
    countdown_seconds = 300

    try:
        while True:
        
                    # if the order was removed (either by cancel or by successful/failed auto_verify), bail out
            if order_id not in order_store:
                logger.info(f"[Unified] order {order_id} gone → deleting message {msg_id}")
                # delete the QR message
                try:
                    await client.delete_messages(chat_id, msg_id)
                except Exception as e:
                    logger.warning(f"[Unified] failed to delete msg {msg_id}: {e!r}")
                return
                
                
            now = time.monotonic()
            wall_elapsed = int(time.time() - start_ts)
            countdown_seconds = max(0, 300 - wall_elapsed)

            mm, ss = divmod(countdown_seconds, 60)
            timer_text = f"{mm//10} {mm%10} : {ss//10} {ss%10}"

            # Rotate caption
            caption_due = (
                (caption_state == "phase" and now - last_caption_change >= 1.5) or
                (caption_state == "cap2" and now - last_caption_change >= 2.5)
            )

            if caption_due:
                if caption_state == "phase":
                    last_caption = CAP1_PHASES[phase_step % len(CAP1_PHASES)]
                    phase_step += 1
                    if phase_step == len(CAP1_PHASES):
                        caption_state = "cap2"
                        phase_step = 0
                else:
                    last_caption = CAPTION2
                    caption_state = "phase"

                last_caption_change = now

            # Send combined update (caption + timer button)
            kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(timer_text, callback_data="noop")],  # Timer on one row
            [InlineKeyboardButton("Use Code", callback_data=f"usecode_{order_id}"),  # PROMO CODE
            InlineKeyboardButton("Cancel", callback_data=f"cancel_{order_id}")]
            ])

            try:
                await client.edit_message_caption(
                    chat_id=chat_id,
                    message_id=msg_id,
                    caption=last_caption,
                    reply_markup=kb
                )
                logger.debug(f"[Unified] caption updated: {last_caption!r}")
            except MessageNotModified:
                pass
            except MessageIdInvalid:
                logger.info(f"[Unified] Message {msg_id} invalid, stopping loop")
                return
            except Exception as e:
                logger.error(f"[Unified] Caption update failed: {e!r}")
                return

            if countdown_seconds <= 0:
                logger.info(f"[Unified] time up for order {order_id}")
                try:
                    await client.delete_messages(chat_id, msg_id)
                except Exception:
                    pass
                order_store.pop(order_id, None)

                class _FakeMsg:
                    def __init__(self, cid, u):
                        self.chat = type("C", (), {"id": cid})()
                        self.from_user = u
                        self.text = "/start"
                await start_command(client, _FakeMsg(chat_id, msg.chat))
                return

            # Align sleep to exact next wall clock second
            await asyncio.sleep(1 - (time.time() % 1))

    except asyncio.CancelledError:
        logger.info(f"[Unified] cancelled for message {msg_id}")
        return
        

# Keep track of active timers/polls so we can cancel them on refresh/cancel
countdown_tasks: dict[str, asyncio.Task] = {}

CAP1_PHASES = [
    "⚡️𝗦𝗲𝗮𝗺𝗹𝗲𝘀𝘀!",
    "🔐 𝗘𝗻𝗰𝗿𝘆𝗽𝘁𝗲𝗱!",
    "🔥 𝗔𝘂𝘁𝗼-𝘃𝗲𝗿𝗶𝗳𝗶𝗲𝗱 𝖯𝖺𝗒𝗆𝖾𝗇𝗍𝗌..",
    "❤️ 𝖮𝗇𝗅𝗒 𝗐𝗂𝗍𝗁 𝗢𝗢𝗥 𝖯𝖺𝗒 🚀"
]

CAPTION2 = "𝗖𝗼𝗺𝗶𝗻𝗴 𝘀𝗼𝗼𝗻..."

active_tasks: dict[int, asyncio.Task] = {}

from pyrogram.errors import MessageNotModified, MessageIdInvalid

# async def animate_caption_loop(client, msg):
    # chat_id, msg_id = msg.chat.id, msg.id
    # logger.info(f"[Animate] starting caption loop for message {msg_id}")

    # try:
        # while True:
            # # 1) Primary phases
            # for phase in CAP1_PHASES:
                # try:
                    # await client.edit_message_caption(
                        # chat_id=chat_id,
                        # message_id=msg_id,
                        # caption=phase
                    # )
                    # logger.debug(f"[Animate] set caption phase: {phase!r}")
                # except MessageNotModified:
                    # # caption already exactly this phase
                    # logger.debug("[Animate] caption identical, skipping")
                # except MessageIdInvalid:
                    # # message no longer exists → stop animation silently
                    # logger.info(f"[Animate] message {msg_id} gone, stopping")
                    # return
                # except Exception as e:
                    # logger.error(f"[Animate] unexpected error setting caption {phase!r}: {e!r}")
                    # return

                # await asyncio.sleep(1.5)

            # # 2) Secondary caption
            # try:
                # await client.edit_message_caption(
                    # chat_id=chat_id,
                    # message_id=msg_id,
                    # caption=CAPTION2
                # )
                # logger.debug(f"[Animate] set caption phase: {CAPTION2!r}")
            # except MessageNotModified:
                # logger.debug("[Animate] caption identical for CAPTION2, skipping")
            # except MessageIdInvalid:
                # logger.info(f"[Animate] message {msg_id} gone on CAPTION2, stopping")
                # return
            # except Exception as e:
                # logger.error(f"[Animate] unexpected error setting caption {CAPTION2!r}: {e!r}")
                # return

            # await asyncio.sleep(2.5)

    # except asyncio.CancelledError:
        # logger.info(f"[Animate] cancelled caption loop for message {msg_id}")
        # return
        

@app.on_callback_query(filters.regex(r"^phonepe$"))
async def show_phonepe(client, callback_query):
    # Check if the gateway is on or off
    if not gateway_status.get("is_on", False):
        # If the gateway is off, send a message and stop further action
        return await callback_query.message.reply_text(
            "⚠️ 𝗣𝗮𝘆𝗺𝗲𝗻𝘁 𝗚𝗮𝘁𝗲𝘄𝗮𝘆 𝗶𝘀 𝗗𝗼𝘄𝗻\n\n𝖸𝗈𝗎 𝖼𝖺𝗇 𝖺𝗅𝗐𝖺𝗒𝗌 𝖻𝗎𝗒 𝗍𝗁𝖾 𝖺𝖼𝖼𝗈𝗎𝗇𝗍 𝗈𝖿𝖿𝗅𝗂𝗇𝖾\n𝖢𝗈𝗇𝗍𝖺𝖼𝗍 𝗎𝗌 𝖺𝗍 @oor_agent"
        )

    # 1) ACK
    try:
        await callback_query.answer()
        logger.info("[PhonePe] CallbackQuery answered")
    except QueryIdInvalid:
        pass

    user_id = callback_query.from_user.id
    slot_id = user_slot_choice.get(user_id, "slot_1")
    logger.info(f"[PhonePe] User ID: {user_id}, Slot ID: {slot_id}")

    # ── 2) Send initial loader message ─────────────────────────────
    loader_msg = await callback_query.message.reply_text("⚡ 𝘊𝘰𝘯𝘯𝘦𝘤𝘵𝘪𝘯𝘨 ●○○○○")
    logger.info("[PhonePe] Loader message sent")

    loader_phases = [
        ("⚡ 𝘊𝘰𝘯𝘯𝘦𝘤𝘵𝘪𝘯𝘨",            5),
        ("🚀 𝘊𝘰𝘯𝘯𝘦𝘤𝘵𝘦𝘥 𝘵𝘰 𝙊𝙊𝙍 𝘗𝘢𝘺",  5),
        ("⚙️ 𝘗𝘳𝘰𝘤𝘦𝘴𝘴𝘪𝘯𝘨 𝘺𝘰𝘶𝘳 𝘳𝘦𝘲𝘶𝘦𝘴𝘵",    5),
        ("❤️ 𝘼𝙡𝙢𝙤𝙨𝙩 𝙩𝙝𝙚𝙧𝙚",          5),
        ("✨ 𝘼𝙡𝙡 𝙨𝙚𝙩! 𝘴𝘤𝘢𝘯 𝘺𝘰𝘶𝘳 𝘘𝘙", 5),
    ]

    async def loader_animation():
        """
        For each phase, slide a single "●" across a background of "○",
        doing two full left→right passes before moving to the next label.
        """
        for label, length in loader_phases:
            # do two passes of the sliding dot
            for _pass in range(2):
                for pos in range(length):
                    bar = ["○"] * length
                    bar[pos] = "●"
                    text = f"{label} {''.join(bar)}"
                    try:
                        await client.edit_message_text(
                            chat_id=loader_msg.chat.id,
                            message_id=loader_msg.id,
                            text=text
                        )
                    except MessageNotModified:
                        pass
                    except Exception as e:
                        logger.warning(f"[Loader] edit failed: {e!r}")
                        return
                    await asyncio.sleep(0.2)
        # leave the final frame on-screen

    loader_task = asyncio.create_task(loader_animation())

    # ── 2) Start QR generation in parallel ────────────────────
    timings = {}
    slot_info = await read_node(f"settings/slots/{slot_id}")
    logger.info(f"[PhonePe] Slot info fetched: {slot_info!r}")
    try:
        amount = float(slot_info.get("required_amount", 12))
    except:
        amount = 12.0

    alphabet = string.ascii_uppercase + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(13))
    order_id = f"OOR{random_part}"
    order_store[order_id] = {
        "user_id":         user_id,
        "slot_id":         slot_id,
        "required_amount": amount,
        "timestamp":       time.time(),
    }
    logger.info(f"[PhonePe] Reserved order_id: {order_id}")

    upi_url = (
        f"upi://pay?pa={UPI_ID}&am={amount}&pn={MERCHANT_NAME}"
        f"&tn={order_id}&tr={order_id}&tid={order_id}"
    )

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
    logger.info(f"[PhonePe] QR generated in {timings['qr_ms']}ms")

    # invert + logo mask
    t1 = time.perf_counter()
    inv = ImageOps.invert(qr_img).convert("RGBA")
    inv.putdata([
        (0,0,0,0) if (r,g,b)==(0,0,0) else (r,g,b,255)
        for (r,g,b,_) in inv.getdata()
    ])
    timings['invert_ms'] = int((time.perf_counter() - t1) * 1000)

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
    empty = Image.new("RGBA", cropped.size, (0,0,0,0))
    qr_hole = Image.composite(empty, cropped, hole)
    qr_hole.paste(logo, (x,y), logo)
    timings['compose_ms'] = int((time.perf_counter() - t2) * 1000)

    # render HTML preview
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

    try:
        img_url = await asyncio.to_thread(html_to_png_url, html, timings)
    except Exception as e:
        return await callback_query.message.edit_text(f"❌ Failed: {e}")

# ── 3) Wait for loader animation to complete ──────────────
    await loader_task
    try:
        await loader_msg.delete()
        logger.info("[PhonePe] Loader message deleted")
    except Exception as e:
        logger.warning(f"[PhonePe] Failed to delete loader message: {e!r}")

    # ── 5) Send the actual QR + initial caption & buttons ───────────
    initial_kb = InlineKeyboardMarkup([
    [InlineKeyboardButton("0 5 : 0 0", callback_data="noop")],  # Timer on one row
    [InlineKeyboardButton("Use Code", callback_data=f"usecode_{order_id}"),  # PROMO CODE
     InlineKeyboardButton("Cancel", callback_data=f"cancel_{order_id}")]
    ])
    qr_msg = await callback_query.message.reply_photo(
        photo=img_url,
        caption=CAP1_PHASES[0],
        reply_markup=initial_kb
    )
    logger.info(f"[PhonePe] sent QR message (id={qr_msg.id}), order_id={order_id}")  # ← use .id

    # ── 6) Start caption animation ─────────────────────
    cid = qr_msg.chat.id
    if cid in active_tasks:
        active_tasks[cid].cancel()
        active_tasks.pop(cid, None)

    active_tasks[cid] = asyncio.create_task(
        unified_loop(client, qr_msg, order_id, time.time())
    )
    logger.info(f"[Unified] launched combined caption+timer loop for chat {cid}")

    # ── 7) Auto‐verify logic remains separate ───────────────────────
    asyncio.create_task(auto_verify_payment(client, qr_msg, order_id))
    
   

# ─── Cancel handler ──────────────────────────────────────────────────────────
@app.on_callback_query(filters.regex(r"^cancel_(.+)$"))
async def cancel_phonepe(client, callback_query):
    order_id = callback_query.data.split("_", 1)[1]

    # 1) Cancel the countdown updater task (if running)
    task = countdown_tasks.pop(order_id, None)
    if task and not task.done():
        task.cancel()

    # 2) Remove from in-memory store so auto_verify stops
    order_store.pop(order_id, None)

    # 3) Acknowledge button tap (avoids QUERY_ID_INVALID)
    await callback_query.answer()

    # 4) Delete the QR message
    try:
        await callback_query.message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete QR message: {e!r}")


    try: # PROMO CODE
        owner_uid = None
        info = order_store.get(order_id)
        if info:
            owner_uid = info.get("user_id")
        # If the order was already popped/stopped, attempt to find any pending entries referencing this order
        if not owner_uid:
            # search pending requests for a matching order_id
            for uid, p in list(pending_code_requests.items()):
                if p.get("order_id") == order_id:
                    owner_uid = uid
                    break

        if owner_uid:
            ctx = pending_code_requests.pop(owner_uid, None)
            if ctx:
                # delete the ForceReply prompt message if present
                try:
                    cmsg_id = ctx.get("context_msg_id")
                    if cmsg_id:
                        await client.delete_messages(chat_id=owner_uid, message_ids=cmsg_id)
                except Exception:
                    pass
    except Exception:
        logger.exception("Error cleaning pending code on cancel")



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
    cred_key, cred_data = await get_valid_credential_for_slot_async(slot_id)
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

    # ── Your custom quote text ───────────────────────────────────────────────
    quote_text = (
        "𝖨𝖿 𝗅𝗈𝗀𝗀𝖾𝖽 𝗈𝗎𝗍, 𝖳𝖺𝗉 “𝖱𝖾𝖿𝗋𝖾𝗌𝗁” 𝗍𝗈 𝗀𝖾𝗍 𝗒𝗈𝗎𝗋 𝗇𝖾𝗐 𝗉𝖺𝗌𝗌𝗐𝗈𝗋𝖽!"
    )

    # ── Build the caption ────────────────────────────────────────────────────
    email    = cred_data["email"]
    password = cred_data["password"]
    caption  = (
        f"{succ_text}\n\n"
        f"{acct_fmt.format(email=email, password=password)}\n\n"
        f"{quote_text}"
    )


    # ── 7) Inline keyboard: Refresh + Buy Again ──────────────────────────────
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("𝖱𝖾𝖿𝗋𝖾𝗌𝗁 𝖯𝖺𝗌𝗌𝗐𝗈𝗋𝖽", callback_data=f"refresh_{txn_id}")],
        [InlineKeyboardButton("𝖡𝗎𝗒 𝖠𝗀𝖺𝗂𝗇",       callback_data="start")]
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
        return await callback_query.answer("🚫 𝖸𝗈𝗎𝗋 𝖠𝖼𝖼𝖾𝗌𝗌 𝖧𝖺𝗌 𝖤𝗑𝗉𝗂𝗋𝖾𝖽", show_alert=True)

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
        return await callback_query.answer("😊 𝖭𝗈 𝖢𝗁𝖺𝗇𝗀𝖾 𝖨𝗇 𝖢𝗋𝖾𝖽𝖾𝗇𝗍𝗂𝖺𝗅𝗌", show_alert=True)

    # ── 6) Build updated caption + buttons (exactly as before) ────────────────
    ui = await read_node("ui_config/approve_flow")
    succ_text = ui.get("success_text", "Payment Success ✅").replace("\\n", "\n")
    acct_fmt  = (
        ui.get("account_format", "Email: {email}\nPassword: {password}")
          .replace("\\n", "\n")
    )
    quote_text = "𝖨𝖿 𝗅𝗈𝗀𝗀𝖾𝖽 𝗈𝗎𝗍, 𝖳𝖺𝗉 “𝖱𝖾𝖿𝗋𝖾𝗌𝗁” 𝗍𝗈 𝗀𝖾𝗍 𝗒𝗈𝗎𝗋 𝗇𝖾𝗐 𝗉𝖺𝗌𝗌𝗐𝗈𝗋𝖽!"

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
    await callback_query.answer("𝖢𝗋𝖾𝖽𝖾𝗇𝗍𝗂𝖺𝗅𝗌 𝖱𝖾𝖿𝗋𝖾𝗌𝗁𝖾𝖽 ✅", show_alert=True)


# ── The reject flow stays exactly the same (no database I/O changes needed) ──

async def do_reject_flow_immediate(client, message, reason: str = None):
    ui = await read_node("ui_config/reject_flow")
    photo_url = ui.get("photo_url", "").replace("\\n", "\n")
    err_txt   = ui.get("error_text", "Transaction Rejected.").replace("\\n", "\n")

    if reason:
        err_txt = f"{err_txt}\n\n𝗥𝗲𝗮𝘀𝗼𝗻: {reason}"

    # Build the inline button
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                "I’m Sorry, I’ll Buy Now",
                callback_data="start"
            )
        ]]
    )

    if photo_url:
        await client.send_photo(
            chat_id=message.chat.id,
            photo=photo_url,
            caption=err_txt,
            reply_markup=keyboard
        )
    else:
        await client.send_message(
            chat_id=message.chat.id,
            text=err_txt,
            reply_markup=keyboard
        )
    

# ── BOTTOM ENTRY POINT (INIT & CLOSE aiohttp AROUND app.run) ──────────────
if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()

    print("🚀 Netflix NextGen has Started...")    # <-- this will appear    

    # 1) start the watcher in the background
    app.loop.create_task(stock_watcher(poll_interval=5.0))
    
    
    # 1) Initialize the shared aiohttp session before starting the bot
    loop.run_until_complete(init_aiohttp_session())
    
    loop.run_until_complete(ensure_maintenance_node()) # for maintenance code
    app.loop.create_task(maintenance_watcher(poll_interval=5.0))
    
            # new config‐version watcher
    ui_paths = [
        "ui_config/confirmation_flow",
        "referral_settings",
        "free_trial_claims",
    ]
    app.loop.create_task(config_version_watcher(ui_paths, interval=5.0))

    try:
        # 2) Run your Pyrogram bot
        app.run()
    finally:
        # 3) Close the shared aiohttp session after the bot stops
        loop.run_until_complete(close_aiohttp_session())
        
     
