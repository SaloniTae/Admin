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

from NetflixRefer import get_required_points, get_referral_info, get_top_referrers
from NetflixRefer import register_refer_handlers  # NEW CODE: Import the registration function from refer.py
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

aiohttp_session = None

async def init_aiohttp_session():
    global aiohttp_session
    if aiohttp_session is None or aiohttp_session.closed:
        aiohttp_session = aiohttp.ClientSession()

async def close_aiohttp_session():
    global aiohttp_session
    if aiohttp_session and not aiohttp_session.closed:
        await aiohttp_session.close()
        aiohttp_session = None

async def firebase_get(path: str):
    global aiohttp_session, REAL_DB_URL, logger, init_aiohttp_session

    # Normalize path to avoid double slashes if REAL_DB_URL ends with / and path starts with /
    # or missing slash if neither have one.
    if REAL_DB_URL.endswith('/') and path.startswith('/'):
        url = f"{REAL_DB_URL[:-1]}{path}.json"
    elif not REAL_DB_URL.endswith('/') and not path.startswith('/'):
        url = f"{REAL_DB_URL}/{path}.json"
    else: # Handles cases where one has slash and other doesn't, correctly.
        url = f"{REAL_DB_URL}{path}.json"

    try:
        if aiohttp_session is None or aiohttp_session.closed:
            await init_aiohttp_session()
        async with aiohttp_session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            elif resp.status == 404:
                logger.info(f"Firebase GET: Path not found (404): {url}")
                return None
            else:
                logger.error(f"Firebase GET error for {url}: {resp.status} - {await resp.text()}")
                return None
    except aiohttp.ClientError as e:
        logger.error(f"Aiohttp client error during Firebase GET for {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during Firebase GET for {url}: {e}")
        return None

async def firebase_put(path: str, data):
    global aiohttp_session, REAL_DB_URL, logger, init_aiohttp_session

    if REAL_DB_URL.endswith('/') and path.startswith('/'):
        url = f"{REAL_DB_URL[:-1]}{path}.json"
    elif not REAL_DB_URL.endswith('/') and not path.startswith('/'):
        url = f"{REAL_DB_URL}/{path}.json"
    else:
        url = f"{REAL_DB_URL}{path}.json"

    try:
        if aiohttp_session is None or aiohttp_session.closed:
            await init_aiohttp_session()
        async with aiohttp_session.put(url, json=data) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                logger.error(f"Firebase PUT error for {url}: {resp.status} - {await resp.text()}")
                return None
    except aiohttp.ClientError as e:
        logger.error(f"Aiohttp client error during Firebase PUT for {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during Firebase PUT for {url}: {e}")
        return None

from pyrogram import Client, filters
from qrcode_styled import QRCodeStyled, ERROR_CORRECT_H
from qrcode_styled.pil.image import PilStyledImage
from decimal import Decimal, InvalidOperation

# --------------------- Bot Configuration ---------------------
API_ID = "25270711"
API_HASH = "6bf18f3d9519a2de12ac1e2e0f5c383e"
BOT_TOKEN = "7140092976:AAFtmOBKi-mIoVighcf4XXassHimU2CtlR8"

# (My Test Bot)
#API_ID = "25270711"
#API_HASH = "6bf18f3d9519a2de12ac1e2e0f5c383e"
#BOT_TOKEN = "7140092976:AAFtmOBKi-mIoVighcf4XXassHimU2CtlR8"

#API_ID = "27708983"
#API_HASH = "d0c88b417406f93aa913ecb5f1b58ba6"
#BOT_TOKEN = "7516682635:AAFMspWzwgqrmUgjVXSbNl6VggvtDIGowek"


# --------------------- DB CONFIG ---------------------
# Replace with your actual Firebase Realtime Database URL (include trailing slash)
# Define your real DB URL
REAL_DB_URL = "https://testing-6de54-default-rtdb.firebaseio.com/"

# UI Configuration Cache
UI_CACHE = {}
CACHE_DURATION = 30  # seconds

UPI_ID           = "paytm.s1a23xv@pty"
MERCHANT_NAME    = "OTT ON RENT"
MID              = "RZUqNv45112793295319"
INTERNAL_API_KEY = "OTTONRENT"  # for your html2image service
TEMPLATE_URL     = "https://res.cloudinary.com/djzfoukhz/image/upload/v1746200521/QRTemplate_znsfef.png"
LOGO_URL         = "https://res.cloudinary.com/djzfoukhz/image/upload/v1746022425/Untitled_design_20250430_011630_0000_icacxu.png"


def read_data():
    global logger # Ensure logger is accessible
    logger.warning("Deprecated function read_data() was called. This should be replaced with optimized Firebase calls.")
    # try:
    #     resp = requests.get(REAL_DB_URL + ".json")
    #     if resp.status_code == 200:
    #         return resp.json() or {}
    #     else:
    #         logging.error("DB read error: " + resp.text) # Should be logger.error
    #         return {}
    # except Exception as e:
    #     logging.error("read_data exception: " + str(e)) # Should be logger.error
    #     return {}
    return {}

def write_data(data):
    global logger # Ensure logger is accessible
    logger.warning("Deprecated function write_data(data) was called. This should be replaced with optimized Firebase calls.")
    # try:
    #     resp = requests.put(REAL_DB_URL + ".json", json=data)
    #     if resp.status_code == 200:
    #         return resp.json()
    #     else:
    #         logging.error("DB write error: " + resp.text) # Should be logger.error
    #         return {}
    # except Exception as e:
    #     logging.error("write_data exception: " + str(e)) # Should be logger.error
    #     return {}
    return {}

async def get_ui_config_optimized(section: str) -> dict:
    global UI_CACHE, aiohttp_session, REAL_DB_URL, logger # Ensure logger is accessible

    current_time = time.time()
    if section in UI_CACHE:
        data, timestamp = UI_CACHE[section]
        if current_time - timestamp < CACHE_DURATION:
            logger.info(f"Cache hit for UI config section: {section}")
            return data

    url = f"{REAL_DB_URL}ui_config/{section}.json" # REAL_DB_URL has trailing slash
    try:
        if aiohttp_session is None or aiohttp_session.closed: # Ensure session is active
            await init_aiohttp_session() # Initialize if not active

        async with aiohttp_session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json() or {}
                UI_CACHE[section] = (data, current_time)
                logger.info(f"Fetched and cached UI config for section: {section}")
                return data
            elif resp.status == 404: # Handle 404 specifically
                logger.warning(f"UI config section not found (404): {section} at {url}")
                UI_CACHE[section] = ({}, current_time) # Cache empty result
                return {}
            else:
                logger.error(f"Error fetching UI config section {section} from {url}: {resp.status} - {await resp.text()}")
                # Return cached data if available on error, otherwise empty
                if section in UI_CACHE:
                    return UI_CACHE[section][0]
                return {}
    except aiohttp.ClientError as e:
        logger.error(f"Aiohttp client error fetching UI config section {section} from {url}: {e}")
        if section in UI_CACHE:
            return UI_CACHE[section][0]
        return {}
    except Exception as e:
        logger.error(f"Unexpected error fetching UI config section {section} from {url}: {e}")
        if section in UI_CACHE:
            return UI_CACHE[section][0]
        return {}

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
# logging.basicConfig(
    # format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    # level=logging.INFO
# )
logger = logging.getLogger(__name__)

app = Client("NetflixMultiSlotBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

register_fileid_handlers(app) # FileID_module.py

try:
    register_refer_handlers(app) # refer.py
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
            logger.info(f"Message sent to {args[0] if args else 'unknown'}")
        except FloodWait as e:
            logger.warning(f"FloodWait: waiting {e.value} seconds")
            time.sleep(e.value)
            message_queue.put(task)
        finally:
            message_queue.task_done()

Thread(target=message_sender, daemon=True).start()

# --------------------- Updating usage / locked in DB ---------------------
def update_credential_usage(cred_key, new_usage):
    logger.info(f"Updating usage_count for {cred_key} => {new_usage}")
    db_data = read_data()
    if not db_data:
        return
    if cred_key not in db_data or not isinstance(db_data[cred_key], dict):
        return
    db_data[cred_key]["usage_count"] = new_usage
    write_data(db_data)

def update_credential_locked(cred_key, new_locked):
    logger.info(f"Updating locked for {cred_key} => {new_locked}")
    db_data = read_data()
    if not db_data:
        return
    if cred_key not in db_data or not isinstance(db_data[cred_key], dict):
        return
    db_data[cred_key]["locked"] = new_locked
    write_data(db_data)

# --------------------- Checking / Marking used ORDERIDs in DB ---------------------
def is_orderid_used(order_id):
    db_data = read_data()
    if not db_data:
        return False
    used_list = db_data.get("used_orderids", {})
    return str(order_id) in used_list

def mark_orderid_used(order_id):
    db_data = read_data()
    if not db_data:
        return
    used_list = db_data.get("used_orderids", {})
    if not isinstance(used_list, dict):
        used_list = {}
    used_list[str(order_id)] = True
    db_data["used_orderids"] = used_list
    write_data(db_data)

# --------------------- get_valid_credential_for_slot ---------------------
def get_valid_credential_for_slot(slot_id):
    """
    Priority: return (cred_key, cred_data) from 'all' credentials first.
    If none valid, then fallback to credentials for the specific slot_id.
    """
    db_data = read_data() or {}
    locked_found = False
    found_in_all = None
    found_in_slot = None

    for key, node in db_data.items():
        if not is_credential(node):
            continue

        # Normalize slot binding to list
        owns = node.get("belongs_to_slot")
        if isinstance(owns, str):
            owns = [owns]
        elif not isinstance(owns, list):
            continue

        # Skip if locked
        if int(node.get("locked", 0)) == 1:
            locked_found = True
            continue

        # Check usage and expiry
        usage_count = int(node.get("usage_count", 0))
        max_usage   = int(node.get("max_usage", 0))
        try:
            expiry_dt = datetime.strptime(node["expiry_date"], "%Y-%m-%d")
        except Exception:
            continue

        if usage_count >= max_usage or expiry_dt <= datetime.now():
            continue

        # Save the first match in 'all' or 'slot-specific'
        if "all" in owns and not found_in_all:
            found_in_all = (key, node)
        elif slot_id in owns and not found_in_slot:
            found_in_slot = (key, node)

    # Prefer 'all' first
    if found_in_all:
        logger.info(f"[SELECTED] {found_in_all[0]} for slot {slot_id} (global)")
        return found_in_all
    if found_in_slot:
        logger.info(f"[SELECTED] {found_in_slot[0]} for slot {slot_id}")
        return found_in_slot

    if locked_found:
        return None, "locked"
    return None, None

    if locked_found:
        return None, "locked"
    return None, None

def handle_action_with_gif(client, callback_query, gif_url, next_action):
    if gif_url:
        message_queue.put((
            client.send_animation,
            [callback_query.message.chat.id],
            {"animation": gif_url}
        ))
    def delayed():
        message_queue.put((next_action, (client, callback_query), {}))
    Timer(4.0, delayed).start()

    

# --------------------- Refer.py -------------------------
def generate_referral_code(user):
    """
    Generate a referral code using only the user ID.
    """
    return str(user.id) # This is fine, no async needed for generate_referral_code

# def read_data(): # Already modified above
#     try:
#         resp = requests.get(REAL_DB_URL + ".json")
#         if resp.status_code == 200:
#             return resp.json() or {}
#         else:
#             logging.error("DB read error: " + resp.text)
#             return {}
#     except Exception as e:
#         logging.error("read_data exception: " + str(e))
#         return {}

# def write_data(data): # Already modified above
#     try:
#         resp = requests.put(REAL_DB_URL + ".json", json=data)
#         if resp.status_code == 200:
#             return resp.json()
#         else:
#             logging.error("DB write error: " + resp.text)
#             return {}
#     except Exception as e:
#         logging.error("write_data exception: " + str(e))
#         return {}

async def register_user(user):
    """
    Registers the user in both the "users" node and the "referrals" node.
    Returns the referral code.
    """
    user_id_str = str(user.id)
    logger.info(f"Registering user with ID: {user_id_str}")

    await firebase_put(f"users/{user_id_str}", True)

    referral_data = await firebase_get(f"referrals/{user_id_str}")

    if referral_data and "referral_code" in referral_data:
        logger.info(f"User {user_id_str} already registered with referral code: {referral_data['referral_code']}")
        return referral_data["referral_code"]
    else:
        referral_code = generate_referral_code(user) # generate_referral_code is sync
        logger.info(f"Generated referral code for user {user_id_str}: {referral_code}")
        new_referral_record = {
            "referral_code": referral_code,
            "referral_points": 0,
            "referred_users": []  # Initialize with an empty list
        }
        await firebase_put(f"referrals/{user_id_str}", new_referral_record)
        return referral_code

async def get_referral_points_setting(): # Made async
    """
    Retrieves the global referral points from the "referral_settings" node.
    Defaults to 17 if not set.
    """
    settings = await firebase_get("referral_settings")
    if settings and settings.get("points_per_referral") is not None:
        try:
            points = int(settings["points_per_referral"])
            logger.info(f"Global referral points per referral: {points}")
            return points
        except ValueError:
            logger.error(f"Error converting referral_settings/points_per_referral to int: {settings['points_per_referral']}")
            return 17 # Default on conversion error
    else:
        logger.info("No custom points_per_referral in referral_settings, using default 17")
        return 17

async def add_referral(referrer_code, new_user_id_str): # Made async, new_user_id is str
    """
    Looks up the referrer by the provided referral code in the "referrals" node.
    If found (and not self-referral) and the new user hasn't been referred yet,
    adds new_user_id_str to the referrer's record and awards points.
    Uses the referrer's custom "points_per_referral" if set, or falls back to the global setting.
    """
    new_user_id_str = str(new_user_id_str) # Ensure it's a string

    # Get all referral user IDs first (keys only)
    all_referral_keys_data = await firebase_get("referrals?shallow=true")
    if not all_referral_keys_data:
        logger.warning("No referral data found (shallow=true failed or empty referrals node).")
        return False

    referrer_id_str = None
    referrer_record_snapshot = None

    for candidate_id_str in all_referral_keys_data.keys():
        # Fetch full record only for potential referrers
        record = await firebase_get(f"referrals/{candidate_id_str}")
        if record and record.get("referral_code") == referrer_code:
            referrer_id_str = candidate_id_str
            referrer_record_snapshot = record # Store the fetched record
            break

    if not referrer_id_str:
        logger.info(f"Referrer code {referrer_code} not found.")
        return False

    if new_user_id_str == referrer_id_str:
        logger.info("Self-referral attempt.")
        return False

    # Use the already fetched referrer_record_snapshot
    referrer_record = referrer_record_snapshot
    if not referrer_record: # Should not happen if referrer_id_str is set from loop above
        logger.error(f"Referrer record for {referrer_id_str} inexplicably missing after shallow find.")
        return False

    referred_users = referrer_record.get("referred_users", [])
    # Ensure referred_users is a list, Firebase might return dicts for array-like structures if keys are numeric strings
    if isinstance(referred_users, dict):
        referred_users = list(referred_users.values())

    if new_user_id_str in referred_users:
        logger.info(f"New user {new_user_id_str} already referred by {referrer_id_str}.")
        return False

    if not isinstance(referred_users, list): # Double check it's a list before append
        logger.warning(f"referred_users for {referrer_id_str} is not a list, re-initializing: {referred_users}")
        referred_users = []
    referred_users.append(new_user_id_str)

    # Update points
    points_to_award = referrer_record.get("points_per_referral")
    if points_to_award is None:
        points_to_award = await get_referral_points_setting() # await async call

    current_points = referrer_record.get("referral_points", 0)

    # Construct the data to update multiple fields atomically using PATCH or specific path PUTs
    # For simplicity with current firebase_put, we'll update the whole record.
    # More optimized would be:
    # await firebase_patch(f"referrals/{referrer_id_str}",
    #                      {"referred_users": referred_users,
    #                       "referral_points": current_points + points_to_award})

    update_data = {
        "referral_code": referrer_record.get("referral_code"), # Keep existing code
        "referral_points": current_points + points_to_award,
        "referred_users": referred_users
    }
    # Preserve custom points_per_referral if it exists
    if "points_per_referral" in referrer_record:
        update_data["points_per_referral"] = referrer_record["points_per_referral"]

    result = await firebase_put(f"referrals/{referrer_id_str}", update_data)

    if result is not None:
        logger.info(f"Referral processed: referrer {referrer_id_str} awarded {points_to_award} points for new user {new_user_id_str}.")
        return True
    else:
        logger.error(f"Failed to update referrer data for {referrer_id_str}.")
        return False

# Assuming these are part of NextGenTest.py or moved here for the purpose of this refactoring
async def get_referral_info(user_id):
    user_id_str = str(user_id)
    return await firebase_get(f"referrals/{user_id_str}")

async def get_required_points():
    settings = await firebase_get("referral_settings")
    if settings and settings.get("required_point") is not None:
        try:
            return int(settings["required_point"])
        except ValueError:
            logger.error(f"Error converting referral_settings/required_point to int: {settings['required_point']}")
            return 17 # Default
    logger.info("No custom required_point in referral_settings, using default 17")
    return 17 # Default

# --------------------- Button Buy With Points On/Off Refer.py below ----------------------

async def get_buy_with_points_setting(): # Made async
    """
    Returns True if the "buy_with_points_enabled" flag in the referral_settings node is True,
    otherwise returns False. Defaults to True if the value is not set.
    """
    referral_settings = await firebase_get("referral_settings")
    if referral_settings is None: # Indicates error or path not found
        logger.info("referral_settings not found or error; defaulting buy_with_points_enabled to True")
        return True # Default to True on error or if not set, maintaining previous behavior

    # The value could be boolean true/false, or string "true"/"false" from some DB setups
    value = referral_settings.get("buy_with_points_enabled")
    if isinstance(value, bool):
        return value
    if isinstance(value, str): # Handle string "true" or "false"
        return value.lower() == "true"

    logger.info("buy_with_points_enabled flag not explicitly set or not boolean/string; defaulting to True")
    return True # Default if the key exists but is not a recognized format, or if key doesn't exist
    
# --------------------- Button Free Trial On/Off below ----------------------

async def get_free_trial_enabled():  #FreeTrial & Made async
    """
    Returns True if the "free_trial_enabled" flag in the referral_settings node is True.
    Defaults to False if not set.
    """
    referral_settings = await firebase_get("referral_settings")
    if referral_settings is None:
        logger.info("referral_settings not found or error; defaulting free_trial_enabled to False")
        return False # Default to False on error or if not set

    value = referral_settings.get("free_trial_enabled")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"

    logger.info("free_trial_enabled flag not explicitly set or not boolean/string; defaulting to False")
    return False # Default if the key exists but is not a recognized format, or if key doesn't exist
    
    
# --------------------- Out-of-Stock Helper ---------------------
async def handle_out_of_stock(client, callback_query): #refer.py
    logger.info("No credentials => out_of_stock => user: %s", callback_query.from_user.id)
    ui = await get_ui_config_optimized("out_of_stock")
    gif_url  = ui.get("gif_url","").replace("\\n","\n")
    messages = ui.get("messages", [])
    if not messages:
        messages = ["Out of stock!", "Please wait..."]

    message_queue.put((
        client.send_animation,
        [callback_query.message.chat.id],
        {"animation": gif_url}
    ))

    def send_line(i):
        message_queue.put((
            client.send_message,
            [callback_query.message.chat.id],
            {"text": messages[i]}
        ))
    for i in range(len(messages)):
        Timer(2.0*(i+1), send_line, args=[i]).start()

    await callback_query.answer()    

def check_paytm_server():
    return True

def get_admin_config():
    db_data = read_data()
    return db_data.get("admin_config", {})

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
        # Use %-I for non-padded hour; adjust to %I.lstrip("0") if needed on your platform.
        return dt.strftime("%-I %p %d %B").upper()
    except Exception as e:
        return dt_str  # fallback if error occurs
        
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

    # Telegram can fetch the PNG directly
    return img_url + ".png"
                    
# --------------------- BOT Handlers ---------------------
@app.on_message(filters.command("myreferral"))
async def my_referral(client, message):
    user_id = message.from_user.id
    info = await get_referral_info(user_id) # already awaits
    if info is None:
        # Attempt to register the user if they have no referral info
        logger.info(f"No referral info for {user_id} in my_referral, attempting to register.")
        await register_user(message.from_user)
        info = await get_referral_info(user_id) # Try fetching again
        if info is None:
            await message.reply_text("Still no referral info found after attempting re-registration. Please contact support.")
            return

    referral_code = info.get("referral_code", "N/A")
    points = info.get("referral_points", 0)

    referred_users_data = info.get("referred_users", [])
    if isinstance(referred_users_data, dict):
        num_referred = len(referred_users_data.keys())
    elif isinstance(referred_users_data, list):
        num_referred = len(referred_users_data)
    else:
        num_referred = 0

    me = await client.get_me()
    bot_username = me.username
    referral_link = f"https://t.me/{bot_username}?start={referral_code}"
    required_points = await get_required_points() # await async call

    text = (
       f"𝘞𝘦𝘭𝘤𝘰𝘮𝘦 𝘵𝘰 𝘵𝘩𝘦 𝙊𝙊𝙍𝙫𝙚𝙧𝙨𝙚!\n\n" # This is the specific text block for my_referral
       f"🌟 𝗢𝗢𝗥𝗯𝗶𝘁𝘀 𝗖𝗼𝗹𝗹𝗲𝗰𝘁𝗲𝗱: {points}\n"
       f"🚀 𝗡𝗲𝘅𝘁 𝗨𝗻𝗹𝗼𝗰𝗸 𝗶𝗻: {required_points} 𝖮𝖮𝖱𝖻𝗂𝗍𝗌\n"
       f"👥 𝗖𝗿𝗲𝘄 𝗠𝗲𝗺𝗯𝗲𝗿𝘀: {num_referred}\n" # Use num_referred
       f"🪪 𝗬𝗼𝘂𝗿 𝗢𝗢𝗥𝘃𝗲𝗿𝘀𝗲 𝗖𝗢𝗗𝗘: {referral_code}\n\n"
       f"Ready to expand Your 𝗢𝗢𝗥𝘃𝗲𝗿𝘀𝗲 ?\n\n"
       f"𝘐𝘯𝘷𝘪𝘵𝘦 𝘺𝘰𝘶𝘳 𝘊𝘳𝘦𝘸 𝘶𝘴𝘪𝘯𝘨 𝘠𝘰𝘶𝘳 𝘓𝘪𝘯𝘬:\n"
       f"<a href='{referral_link}'>https://oorverse.com/join/{referral_code}</a>"
    )

    # Retrieve the photo URL from your UI config; if not set, use a default URL.
    ui_ref_info = await get_ui_config_optimized("referral_info")
    photo_url = ui_ref_info.get("photo_url", "https://raw.githubusercontent.com/OTTONRENT01/FOR-PHOTOS/refs/heads/main/Netflix-Refer.jpg")

    # Send the referral info as a photo with a caption (no inline keyboard buttons).
    await message.reply_photo(photo=photo_url, caption=text)
    
        
# Add the /verify command handler to your application.
@app.on_message(filters.command("verify")) # refer and free trial 
def verify_handler(client, message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        message.reply_text("Usage: /verify <TXN-ID>")
        return

    txn_id = parts[1].strip()
    db_data = read_data()  # your proxy function to get DB data
    
    # transactions = db_data.get("transactions", {})
    # txn_data = transactions.get(txn_id)
    # if not txn_data and txn_id.startswith("REF-"):
        # ref_transactions = transactions.get("REF-ID", {})
        # txn_data = ref_transactions.get(txn_id)
  
    transactions = db_data.get("transactions", {})
    txn_data = transactions.get(txn_id)

    # If not found, check in the appropriate sub-node.
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
    
    # Format the datetime strings
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
async def process_users_command(client, message): # Made async
    """
    Expected command format:
    /users <user_id> send <slot> credentials and used_orderids <order_id>
    
    Example:
    /users 20315957xx send slot_1 credentials and used_orderids T25030308080632745129xx
    """
    user_id = message.from_user.id
    # Fetch admin configuration from DB (admins are stored in DB, not hardcoded)
    admin_config = get_admin_config()
    inferior_admins = admin_config.get("inferior_admins", [])
    if not isinstance(inferior_admins, list):
        inferior_admins = [inferior_admins]
    superior_admins = admin_config.get("superior_admins", [])
    if not isinstance(superior_admins, list):
        superior_admins = [superior_admins]
    
    # Allow only inferior (or superior) admins to use this command.
    if str(user_id) not in [str(x) for x in inferior_admins] and str(user_id) not in [str(x) for x in superior_admins]:
        message.reply("𝗔𝗰𝗰𝗲𝘀𝘀 𝗱𝗲𝗻𝗶𝗲𝗱 🚫\n𝘠𝘰𝘶 𝘥𝘰𝘯'𝘵 𝘩𝘢𝘷𝘦 𝘱𝘦𝘳𝘮𝘪𝘴𝘴𝘪𝘰𝘯 𝘵𝘰 𝘶𝘴𝘦 𝘵𝘩𝘪𝘴 𝘤𝘰𝘮𝘮𝘢𝘯𝘥.")
        return

    # --- regex-based extraction ---
    text = message.text
    # Extract order_id: any alphanumeric token of length 12 or more.
    order_ids = re.findall(r'\b[A-Za-z0-9]{12,}\b', text)
    if not order_ids:
        message.reply("No valid order ID found in the command.")
        return
    order_id = order_ids[0]

    # Extract user_id: any numeric token of 8 to 10 digits.
    user_ids = re.findall(r'\b\d{8,10}\b', text)
    if not user_ids:
        message.reply("No valid user ID found in the command.")
        return
    target_user_id = user_ids[0]

    # Extract slot: match a token like "slot_1", default to "slot_1" if not provided.
    slot_match = re.search(r'\bslot_\w+\b', text, re.IGNORECASE)
    slot_id = slot_match.group(0) if slot_match else "slot_1"
    # --- End replacement ---

    try:
        target_user_id_int = int(target_user_id)
    except ValueError:
        message.reply("𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝘁𝗮𝗿𝗴𝗲𝘁 𝘂𝘀𝗲𝗿 𝗜𝗗 𝗳𝗼𝗿𝗺𝗮𝘁.")
        return

    # Update DB: add the target user into the "users" node
    db_data = read_data() or {}
    users_node = db_data.get("users", {})
    if not isinstance(users_node, dict):
        users_node = {}
    users_node[target_user_id] = True
    db_data["users"] = users_node
    write_data(db_data)

    # Check if the order ID has already been used
    if is_orderid_used(order_id):
        message.reply("𝗧𝗿𝗮𝗻𝘀𝗮𝗰𝘁𝗶𝗼𝗻 𝗜𝗗 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝘂𝘀𝗲𝗱")
        return

    # --- Additional Validation Logic Start ---
    # Validate the transaction by calling the external Paytm API using the provided order ID.
    merchant_key = "RZUqNv45112793295319"
    paytm_url = f"https://paytm.udayscriptsx.workers.dev/?mid={merchant_key}&id={order_id}"
    resp = requests.get(paytm_url)
    if resp.status_code != 200:
        message.reply("API request failed.")
        return
    data = resp.json()
    status = data.get("STATUS", "")
    txn_amount_str = str(data.get("TXNAMOUNT", "0"))
    if status != "TXN_SUCCESS":
        message.reply("𝗧𝗿𝗮𝗻𝘀𝗮𝗰𝘁𝗶𝗼𝗻 𝗻𝗼𝘁 𝘀𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹 🙁")
        return
    try:
        paid_amount = round(float(txn_amount_str), 2)
    except ValueError:
        paid_amount = 0.0

    # Retrieve required amount from slot settings.
    slot_info = db_data.get("settings", {}).get("slots", {}).get(slot_id, {})
    required_amount = float(slot_info.get("required_amount", 12))
    if abs(paid_amount - required_amount) > 0.001:
        message.reply("𝗔𝗺𝗼𝘂𝗻𝘁 𝗺𝗶𝘀𝗺𝗮𝘁𝗰𝗵 ⚠️")
        return
    # --- Additional Validation Logic End ---

    try:
        # This will raise an error if the user is not yet in your peer cache.
        client.get_users(target_user_id_int)
    except pyrogram.errors.PeerIdInvalid:
        message.reply("𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗨𝘀𝗲𝗿 𝗜𝗗 ❌")
        return

    # If no exception is raised, continue to mark the order id as used.
    mark_orderid_used(order_id)

    # Retrieve a valid credential for the given slot.
    cred_key, cred_data = get_valid_credential_for_slot(slot_id)
    if cred_data == "locked":
        message.reply("Credentials for this slot are locked.")
        return
    if not cred_data:
        message.reply("No available credentials for this slot.")
        return

      # ================================
    # FETCH FROM approve_flow CONFIG
    # ================================
    ui = await get_ui_config_optimized("approve_flow") # Changed to async
    gif_url   = ui.get("gif_url", "").replace("\\n", "\n")
    succ_text = ui.get("success_text", "Payment Success ✅").replace("\\n", "\n")
    acct_fmt  = ui.get("account_format", "Email: {email}\nPassword: {password}").replace("\\n", "\n")

    if gif_url:
        message_queue.put((
            client.send_animation,
            [target_user_id_int],
            {"animation": gif_url}
        ))

        time.sleep(2)
        
    email = cred_data["email"]
    password = cred_data["password"]
    usage_count = int(cred_data["usage_count"])
    max_usage = int(cred_data["max_usage"])

    final_text = f"{succ_text}\n\n{acct_fmt.format(email=email, password=password)}"
    # Send the credentials to the target user.
    client.send_message(target_user_id_int, final_text)

    # Update the usage count for the credential.
    if usage_count < max_usage:
        new_usage = usage_count + 1
        update_credential_usage(cred_key, new_usage)

    message.reply("𝗖𝗿𝗲𝗱𝗲𝗻𝘁𝗶𝗮𝗹𝘀 𝘀𝗲𝗻𝘁 𝘀𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆! ✅")


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

    
    
@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_id_str = str(message.from_user.id) # Use string version of ID
    user = message.from_user

    # -- Referral tracking --
    # register_user now handles adding to "users/{user_id_str}" node.
    my_code = await register_user(user) # This is now async

    args = message.text.split()
    referrer_code_from_start_arg = args[1].strip().upper() if len(args) > 1 else None

    # Ensure not self-referral by comparing own generated/retrieved code with the one from args
    if referrer_code_from_start_arg and my_code != referrer_code_from_start_arg:
        logger.info(f"User {user_id_str} was referred by code {referrer_code_from_start_arg}")
        # add_referral is async and takes new_user_id as string
        await add_referral(referrer_code_from_start_arg, user_id_str)
    elif referrer_code_from_start_arg and my_code == referrer_code_from_start_arg:
        logger.info(f"User {user_id_str} attempted self-referral with code {referrer_code_from_start_arg}.")

    # -- end referral logic --

    ui = await get_ui_config_optimized("start_command")
    welcome_text = ui.get("welcome_text", "🎟 Welcome!")
    welcome_text = welcome_text.replace("\\n", "\n")

    # Retrieve welcome photo URL from UI config.
    # If not present, try to retrieve it from the DB schema.
    photo_url = ui.get("welcome_photo")
    if not photo_url:
        # Schema: Retrieve the welcome photo from DB data if not provided in UI config.
        photo_url = db_data.get("welcome_photo")


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

@app.on_callback_query(filters.regex("^help$"))
async def help_callback(client, callback_query):
    ui = await get_ui_config_optimized("help")
    help_text = ui.get("help_text", "Contact support @letmebeunknownn").replace("\\n", "\n")
    message_queue.put_nowait((
        client.send_message,
        [callback_query.message.chat.id],
        {"text": help_text}
    ))
    await callback_query.answer()

@app.on_callback_query(filters.regex("^book_slot$"))
async def book_slot_handler(client, callback_query): # Was book_slot_handler, now contains logic of book_slot_action
    db_data   = read_data() # This is sync, keep for now or refactor read_data if necessary
    all_slots = db_data.get("settings", {}).get("slots", {})
    ui        = await get_ui_config_optimized("slot_booking")
    photo_url = ui.get("photo_url", "")
    caption   = ui.get("caption", "").replace("\\n", "\n")
    kb        = []

    for slot_id, slot_info in all_slots.items():
        if not isinstance(slot_info, dict):
            continue
        if not slot_info.get("enabled", False):
            continue

        label = slot_info.get("name", slot_id)
        cb_data = f"choose_slot_{slot_id}"
        kb.append([ InlineKeyboardButton(label, callback_data=cb_data) ])

    if not kb:
        default_cb = ui.get("callback_data", "confirm_slot") # Default from UI config or hardcoded
        kb.append([ InlineKeyboardButton(ui.get("no_slots_button_text", "No Slots Available"), callback_data=default_cb) ])

    # Directly send the photo, no longer using message_queue for this specific action
    # as the handler itself is async.
    # Ensure client.send_photo is awaited if it's an async operation.
    # Pyrogram's client.send_photo is indeed async.
    await client.send_photo(
        chat_id=callback_query.message.chat.id,
        photo=photo_url,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(kb)
    )
    await callback_query.answer()

# Removed book_slot_action as its logic is merged into book_slot_handler

async def show_locked_message(client, chat_id): # Made async
    locked_ui = await get_ui_config_optimized("locked_flow") # Changed to async
    locked_text = locked_ui.get("locked_text", "⚠️ No available credentials at the moment.\nPlease contact support.").replace("\\n", "\n")
    # message_queue.put might need to change if it doesn't support async message sending directly
    # For now, assuming client.send_message can be awaited or handled by an async queue if available
    # If message_queue is strictly synchronous, this needs a different approach for send_message.
    # However, client.send_message is an async Pyrogram method.
    # This function is called by choose_slot (async) and get_account_handler (async now)
    # So, this can directly await client.send_message
    await client.send_message(chat_id=chat_id, text=locked_text)

@app.on_callback_query(filters.regex("^choose_slot_"))
async def choose_slot(client, callback_query):
    user_id = callback_query.from_user.id
    slot_id = callback_query.data.replace("choose_slot_", "")

    # Check credential
    cred_key, cred_data = get_valid_credential_for_slot(slot_id) # This is sync
    if cred_data == "locked":
        await show_locked_message(client, callback_query.message.chat.id) # await here
        await callback_query.answer()
        return
        client.send_message,
        [chat_id],
        {"text": locked_text}
    ))

@app.on_callback_query(filters.regex("^choose_slot_"))
async def choose_slot(client, callback_query):
    user_id = callback_query.from_user.id
    slot_id = callback_query.data.replace("choose_slot_", "")

    # Check credential
    cred_key, cred_data = get_valid_credential_for_slot(slot_id) # This is sync
    if cred_data == "locked":
        await show_locked_message(client, callback_query.message.chat.id) # await here
        await callback_query.answer()
        return

    if not cred_data:
        await handle_out_of_stock(client, callback_query)
        return

    # Store choice
    user_slot_choice[user_id] = slot_id
    logger.info(f"User {user_id} chose slot: {slot_id}")

    # Call the async version of confirm_slot_action
    await confirm_slot_action(client, callback_query)

    await callback_query.answer()


async def confirm_slot_action(client, callback_query):
    """
    Asynchronous: build buttons & send the final photo or message.
    """
    ui = await get_ui_config_optimized("confirmation_flow")
    photo_url = ui.get("photo_url", "").replace("\\n", "\n")
    caption = ui.get("caption", "💸 Choose Payment Method:").replace("\\n", "\n")
    
    # Build buttons
    phonepe_btn_text = ui.get("button_text", "𝗣𝗁𝗈𝗇𝗲𝗣𝗲").replace("\\n", "\n")
    phonepe_cb      = ui.get("callback_data", "phonepe")
    keyboard_rows = [
        [InlineKeyboardButton(phonepe_btn_text, callback_data=phonepe_cb)]
    ]
    
    if await get_buy_with_points_setting(): # await async call
        keyboard_rows.append([
            InlineKeyboardButton("Buy 𝗐𝗂𝗍𝗁 𝖮𝖮𝖱𝖻𝗂𝗍𝗌", callback_data="buy_with_points")
        ])

    if await get_free_trial_enabled(): # await async call
        user_id = callback_query.from_user.id
        # db_data = read_data() or {} # Deprecated, free_trial_claims should be fetched via firebase_get if needed here
        # For now, this check relies on local free_trial_claims if it were populated from a full user record elsewhere
        # The current logic for free_trial_claims is still using read_data() in get_trial_handler.
        # This part might need further refactoring if free_trial_claims is strictly needed here from DB.
        # However, the button is just to show/hide, actual claim logic is in get_trial_handler.
        # For now, let's assume this check is for UI display and might not need live DB data for the button itself.
        # If it does, free_trials would need to be fetched asynchronously.
        # For this specific change, we are focusing on get_free_trial_enabled call.
        # The logic for `free_trials` itself is not part of this subtask's direct change, other than awaiting the setting.
        db_data_ft = await firebase_get(f"free_trial_claims/{user_id}") # Example if we needed to check claims here
        free_trials = db_data_ft if db_data_ft is not None else {} # Simplified; real check might be just if path exists

        # The original logic for free_trials was:
        # db_data = read_data() or {}
        # free_trials = db_data.get("free_trial_claims", {})
        # if str(user_id) not in free_trials:
        # This implies free_trial_claims is a top-level node mapping user_ids to claim status.
        # So, we would fetch specifically for that user.
        user_claim_status = await firebase_get(f"free_trial_claims/{str(user_id)}")
        if user_claim_status is None: # User has not claimed
        if str(user_id) not in free_trials:
            keyboard_rows.append([
                InlineKeyboardButton("𝖦𝖾𝗍 𝖥𝗋𝖾𝖾 𝖳𝗋𝗂𝖺𝗅", callback_data="free_trial")
            ])

    kb = InlineKeyboardMarkup(keyboard_rows)

    # Send the photo or fallback to send_message if photo_url is empty
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


# refer.py Logic
  

@app.on_callback_query(filters.regex("^buy_with_points$"))
async def buy_with_points_handler(client, callback_query):
    if not await get_buy_with_points_setting(): # Awaited
        await callback_query.answer("OORverse feature is currently unavailable 🚀 Coming Soon..", show_alert=True)
        return
        
    user_id = callback_query.from_user.id
    info = await get_referral_info(user_id) # Awaited
    if info is None:
        logger.info(f"No referral info for {user_id} in buy_with_points_handler, attempting to register.")
        await register_user(callback_query.from_user)
        info = await get_referral_info(user_id)
        if info is None:
            await callback_query.answer("Still no referral info found after attempting re-registration. Please contact support.", show_alert=True)
            return

    referral_code = info.get("referral_code", "N/A")
    points = info.get("referral_points", 0)
    referred_users_data = info.get("referred_users", [])
    if isinstance(referred_users_data, dict):
        num_referred = len(referred_users_data.keys())
    elif isinstance(referred_users_data, list):
        num_referred = len(referred_users_data)
    else:
        num_referred = 0

    me = await client.get_me()
    bot_username = me.username
    referral_link = f"https://t.me/{bot_username}?start={referral_code}"
    required_points = await get_required_points() # Awaited

    # This is the text block for buy_with_points_handler
    # Context: Inside buy_with_points_handler, after fetching info and required_points
    text = (
       f"𝘞𝘦𝘭𝘤𝘰𝘮𝘦 𝘵𝘰 𝘵𝘩𝘦 𝙊𝙊𝙍𝙫𝙚𝙧𝙨𝙚!\n\n"
       f"🌟 𝗢𝗢𝗥𝗯𝗶𝘁𝘀 𝗖𝗼𝗹𝗹𝗲𝗰𝘁𝗲𝗱: {points}\n"
       f"🚀 𝗡𝗲𝘅𝘁 𝗨𝗻𝗹𝗼𝗰𝗸 𝗶𝗻: {required_points} 𝖮𝖮𝖱𝖻𝗂𝗍𝗌\n"
       f"👥 𝗖𝗿𝗲𝘄 𝗠𝗲𝗺𝗯𝗲𝗿𝘀: {num_referred}\n"
       f"🪪 𝗬𝗼𝘂𝗿 𝗢𝗢𝗥𝘃𝗲𝗿𝘀𝗲 𝗖𝗢𝗗𝗘: {referral_code}\n\n"
       f"Ready to expand Your 𝗢𝗢𝗥𝘃𝗲𝗿𝘀𝗲 ?\n\n"
       f"𝘐𝘯𝘷𝘪𝘵𝘦 𝘺𝘰𝘶𝘳 𝘊𝘳𝘦𝘸 𝘶𝘴𝘪𝘯𝘨 𝘠𝘰𝘶𝘳 𝘓𝘪𝘯𝘬:\n"
       f"<a href='{referral_link}'>https://oorverse.com/join/{referral_code}</a>"
    )


    # Get the photo URL from your UI config; fallback if not provided.
    ui_ref_info = await get_ui_config_optimized("referral_info")
    photo_url = ui_ref_info.get("photo_url", "https://raw.githubusercontent.com/OTTONRENT01/FOR-PHOTOS/refs/heads/main/Netflix-Refer.jpg")
    
    # Build an inline keyboard with a Back button.
    keyboard = InlineKeyboardMarkup([
       [InlineKeyboardButton("Get 𝖭𝖾𝗍𝖿𝗅𝗂𝗑 Account", callback_data="get_account")],
       [InlineKeyboardButton("Back", callback_data="back_to_confirmation")]
    ])
    
    # Update the existing message's media and reply markup
    await callback_query.edit_message_media(
        media=InputMediaPhoto(media=photo_url, caption=text)
    )
    await callback_query.edit_message_reply_markup(reply_markup=keyboard)
    

@app.on_callback_query(filters.regex("^get_account$"))
async def get_account_handler(client, callback_query):
    if not await get_buy_with_points_setting(): # Awaited
        await callback_query.answer("OORverse feature is currently unavailable 🚀 Coming Soon..", show_alert=True)
        return
    user_id = callback_query.from_user.id
    user_id_str = str(user_id) # Use string ID
    info = await get_referral_info(user_id) # Awaited
    if info is None:
        logger.info(f"No referral info for {user_id_str} in get_account_handler, attempting to register.")
        await register_user(callback_query.from_user)
        info = await get_referral_info(user_id)
        if info is None:
            await callback_query.answer("𝖭𝗈 𝗋𝖾𝖿𝖾𝗋𝗋𝖺𝗅 𝗂𝗇𝖿𝗈 𝖿𝗈𝗎𝗇𝖽 𝖾𝗏𝖾𝗇 𝖺𝖿𝗍𝖾𝗋 𝗋𝖾-𝗋𝖾𝗀𝗂𝗌𝗍𝗋𝖺𝗍𝗂𝗈𝗇.\n𝖯𝗅𝖾𝖺𝗌𝖾 𝖽𝗈 /𝗌𝗍𝖺𝗋𝗍 𝖺𝗀𝖺𝗂𝗇 𝗈𝗋 𝖼𝗈𝗇𝗍𝖺𝖼𝗍 𝗌𝗎𝗉𝗉𝗈𝗋𝗍.", show_alert=True)
            return

    current_points = info.get("referral_points", 0)
    required_points = await get_required_points() # Awaited
    if current_points < required_points:
        needed = required_points - current_points
        await callback_query.answer(f"𝖸𝗈𝗎 𝗇𝖾𝖾𝖽 {needed} 𝗆𝗈𝗋𝖾 𝗢𝗢𝗥𝗯𝗶𝘁𝘀 𝗍𝗈 𝗀𝖾𝗍 𝖺 𝖭𝖾𝗍𝖿𝗅𝗂𝗑 𝖠𝖼𝖼𝗈𝗎𝗇𝗍", show_alert=True)
        return

    # Now check if at least one valid credential is available
    slot_id = user_slot_choice.get(user_id, "slot_1")
    
    # Check if user already claimed an account for this slot (using Firebase)
    account_claim_path = f"account_claims/{user_id_str}/{slot_id}"
    claim_status = await firebase_get(account_claim_path)
    if claim_status is not None: # If path exists, they've claimed
        await callback_query.answer("𝖸𝗈𝗎 𝗁𝖺𝗏𝖾 𝖺𝗅𝗋𝖾𝖺𝖽𝗒 𝖼𝗅𝖺𝗂𝗆𝖾𝖽 𝖺 𝖭𝖾𝗍𝖿𝗅𝗂𝗑 𝖺𝖼𝖼𝗈𝗎𝗇𝗍 𝖿𝗈𝗋 𝗍𝗈𝖽𝖺𝗒'𝗌 𝗌𝗅𝗈𝗍 ! 😊 comeback 𝗍𝗈𝗆𝗈𝗋𝗋𝗈𝗐 𝖽𝗎𝗋𝗂𝗇𝗀 𝗈𝗎𝗋 𝗇𝖾𝗑𝗍 𝗍𝗂𝗆𝖾 𝗌𝗅𝗈𝗍.", show_alert=True)
        return
        
    cred_key, cred_data = get_valid_credential_for_slot(slot_id) # This is sync, uses deprecated read_data
                                                                # This function needs full refactoring later.
    if cred_data == "locked":
        await show_locked_message(client, callback_query.message.chat.id)
        await callback_query.answer("Credentials locked.", show_alert=True)
        return
    if not cred_data:
        await handle_out_of_stock(client, callback_query)
        return

    # Deduct points using Firebase
    new_points = current_points - required_points
    put_result = await firebase_put(f"referrals/{user_id_str}/referral_points", new_points)
    if put_result is None:
        logger.error(f"Failed to update points for user {user_id_str} in get_account_handler.")
        # TODO: Optionally, consider how to handle failure here. If points aren't deducted, should we proceed?
        # For now, if Firebase update fails, we stop and alert user.
        await callback_query.answer("Could not update your points. Please try again or contact support.", show_alert=True)
        return
    logger.info(f"User {user_id_str} spent {required_points} points, new balance {new_points}.")

    # Generate a dummy ORDERID using the dd-mm-yy format plus a unique 5-letter string
    rand_str = ''.join(random.choices(string.ascii_letters, k=5)) # Ensure random is imported
    dummy_order_id = f"REF-{user_id_str}-{datetime.now().strftime('%d-%m-%y')}-{rand_str}" # Use user_id_str
    payment_data = {"ORDERID": dummy_order_id}

    # Now, since a valid credential is available, call your approval flow
    await do_approve_flow_immediate(client, callback_query.message, slot_id, payment_data)
    await asyncio.sleep(2)  # Wait 2 seconds for approval flow messages to be sent
    
    
    # *** Record that this user has claimed an account for this slot using Firebase ***
    await firebase_put(account_claim_path, True) # Store True to indicate claim
    
    
    
    # Now, send a message to the user with the dummy REF-ID formatted in HTML (monospaced)
    await client.send_message(
        callback_query.message.chat.id,
        f"𝗬𝗼𝘂𝗿 𝗥𝗘𝗙-𝗜𝗗 𝗶𝘀:\n<code>{dummy_order_id}</code>\n\n(𝗉𝗅𝖾𝖺𝗌𝖾 𝗌𝗁𝖺𝗋𝖾 𝗍𝗁𝗂𝗌 𝖨𝖣 𝗐𝗂𝗍𝗁 𝗈𝗎𝗋 𝗌𝗎𝗉𝗉𝗈𝗋𝗍 𝗍𝖾𝖺𝗆 𝖿𝗈𝗋 𝗉𝗋𝗈𝗆𝗉𝗍 𝖺𝗌𝗌𝗂𝗌𝗍𝖺𝗇𝖼𝖾)",
        parse_mode=ParseMode.HTML
  )
  
  
  
@app.on_callback_query(filters.regex("^back_to_confirmation$"))
async def back_to_confirmation_handler(client, callback_query):
    ui = await get_ui_config_optimized("confirmation_flow")
    photo_url = ui.get("photo_url", "")
    caption = ui.get("caption", "💸 Choose Payment Method:").replace("\\n", "\n")
    phonepe_btn_text = ui.get("button_text", "𝗣𝗵𝗼𝗻𝗲𝗣𝗲").replace("\\n", "\n")
    phonepe_cb = ui.get("callback_data", "phonepe")
    
    # Build keyboard rows conditionally:
    keyboard_rows = [
        [InlineKeyboardButton(phonepe_btn_text, callback_data=phonepe_cb)]
    ]
    # Only add Buy With Points if enabled in DB:
    if await get_buy_with_points_setting(): # await async call
        keyboard_rows.append([InlineKeyboardButton("Buy 𝗐𝗂𝗍𝗁 𝖮𝖮𝖱𝖻𝗂𝗍𝗌", callback_data="buy_with_points")])
    # Only add Free Trial if enabled in DB:
    if await get_free_trial_enabled(): # await async call
        # Similar to confirm_slot_action, this is for button display.
        # The actual check if user *can* claim is in free_trial_handler and get_trial_handler.
        keyboard_rows.append([InlineKeyboardButton("𝖦𝖾𝗍 𝖥𝗋𝖾𝖾 𝖳𝗋𝗂𝖺𝗅", callback_data="free_trial")])
    
    keyboard = InlineKeyboardMarkup(keyboard_rows)
    
    await callback_query.edit_message_media(
        media=InputMediaPhoto(media=photo_url, caption=caption)
    )
    await callback_query.edit_message_reply_markup(reply_markup=keyboard)
    
# refer.py End


# Free Trial
@app.on_callback_query(filters.regex("^free_trial$"))
async def free_trial_handler(client, callback_query):
    if not await get_free_trial_enabled(): # await async call
        await callback_query.answer("OORverse feature is currently unavailable 🚀 Coming Soon..", show_alert=True)
        return
        
    user_id = callback_query.from_user.id

    # # Check if the user has already claimed the free trial.
    db_data = read_data()
    # free_trial_claims = db_data.get("free_trial_claims", {})
    # if str(user_id) in free_trial_claims:
        # await callback_query.answer("You have already claimed your free trial.", show_alert=True)
        # return

    # # Mark the free trial as claimed.
    # if "free_trial_claims" not in db_data:
        # db_data["free_trial_claims"] = {}
    # db_data["free_trial_claims"][str(user_id)] = True
    # write_data_via_proxy(db_data)
    
    # Retrieve current slot information to get the slot end time.
    slot_id = user_slot_choice.get(user_id, "slot_1")
    slot_info = db_data.get("settings", {}).get("slots", {}).get(slot_id, {})
    slot_end_str = slot_info.get("slot_end", "N/A")
    end_label = format_slot_time(slot_end_str)  # e.g. "3 PM 12 MARCH"

    # Create a new caption for free trial activation.
    new_caption = (
        f"𝘞𝘦𝘭𝘤𝘰𝘮𝘦 𝘵𝘰 𝘵𝘩𝘦 𝙊𝙊𝙍𝙫𝙚𝙧𝙨𝙚!\n\n"
        "𝖳𝗈 continue enjoying our service beyond your trial, simply select 𝖯𝗁𝗈𝗇𝖾𝖯𝖾 as your preferred option.\n\n"
        f"𝗬𝗼𝘂𝗿 𝘁𝗿𝗶𝗮𝗹 𝗮𝘂𝘁𝗼-𝗲𝗻𝗱: {end_label}"
    )

    # Get the photo URL from your UI config for referral info (with fallback).
    ui_trial_info = await get_ui_config_optimized("freetrial_info")
    photo_url = ui_trial_info.get("photo_url", "https://raw.githubusercontent.com/OTTONRENT01/FOR-PHOTOS/refs/heads/main/Netflix-FreeTrial.jpg")

    # Build an inline keyboard with "Get 𝖭𝖾𝗍𝖿𝗅𝗂𝗑 Account" and "Back" buttons.
    new_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Get 𝖭𝖾𝗍𝖿𝗅𝗂𝗑 Account", callback_data="get_trial")],
        [InlineKeyboardButton("Back", callback_data="back_to_confirmation")]
    ])

    # Update the current message's media and reply markup.
    await callback_query.edit_message_media(
        media=InputMediaPhoto(media=photo_url, caption=new_caption)
    )
    await callback_query.edit_message_reply_markup(reply_markup=new_keyboard)


# Free trial
# get trial code
@app.on_callback_query(filters.regex("^get_trial$"))
async def get_trial_handler(client, callback_query):
    if not await get_free_trial_enabled(): # await async call
        await callback_query.answer("OORverse feature is currently unavailable 🚀 Coming Soon..", show_alert=True)
        return
    user_id = callback_query.from_user.id
    user_id_str = str(user_id)
    slot_id = user_slot_choice.get(user_id, "slot_1")

    # Check if the user has already claimed the free trial.
    # db_data = read_data() or {} # Deprecated
    # free_trial_claims = db_data.get("free_trial_claims", {}) # Deprecated
    user_claim_status = await firebase_get(f"free_trial_claims/{user_id_str}")
    if user_claim_status is not None: # If not None, means entry exists, so claimed.
        await callback_query.answer("You have already claimed your free trial.", show_alert=True)
        return

    # Check for a valid credential.
    cred_key, cred_data = get_valid_credential_for_slot(slot_id)
    if cred_data == "locked":
        show_locked_message(client, callback_query.message.chat.id)
        await callback_query.answer("Credentials locked.", show_alert=True)
        return
    if not cred_data:
        await handle_out_of_stock(client, callback_query)
        return

    # Generate a dummy free trial ORDERID using dd-mm-yy and a unique 5-letter string.
    rand_str = ''.join(random.choices(string.ascii_letters, k=5))
    dummy_order_id = f"FTRIAL-{user_id}-{datetime.now().strftime('%d-%m-%y')}-{rand_str}"
    payment_data = {"ORDERID": dummy_order_id}

    # Call your approval flow.
    # await do_approve_flow_immediate(client, callback_query.message, slot_id, payment_data) # Already awaited
    # No, do_approve_flow_immediate is already awaited by the caller get_trial_handler if it's made async
    # This call is inside get_trial_handler, which we are making async. So it should be awaited.
    await do_approve_flow_immediate(client, callback_query.message, slot_id, payment_data)
    await asyncio.sleep(2)  # Wait 2 seconds for approval messages to be sent

    # Re-read the database to pick up changes made by the approval flow. # Not needed if we PUT directly
    # db_data = read_data() or {} # Deprecated
    # Mark the free trial as claimed.
    # if "free_trial_claims" not in db_data: # Deprecated
        # db_data["free_trial_claims"] = {} # Deprecated
    # db_data["free_trial_claims"][str(user_id)] = True # Deprecated
    # write_data(db_data) # Deprecated
    await firebase_put(f"free_trial_claims/{user_id_str}", True) # Mark as claimed

    # Send a message to the user with the dummy free trial ID.
    await client.send_message(
        callback_query.message.chat.id,
        f"𝗬𝗼𝘂𝗿 𝗙𝗧𝗥𝗜𝗔𝗟-𝗜𝗗 𝗶𝘀:\n<code>{dummy_order_id}</code>\n\n(𝗉𝗅𝖾𝖺𝗌𝖾 𝗌𝗁𝖺𝗋𝖾 𝗍𝗁𝗂𝗌 𝖨𝖣 𝗐𝗂𝗍𝗁 𝗈𝗎𝗋 𝗌𝗎𝗉𝗉𝗈𝗋𝗍 𝗍𝖾𝖺𝗆 𝖿𝗈𝗋 𝗉𝗋𝗈𝗆𝗉𝗍 𝖺𝗌𝗌𝗂𝗌𝗍𝖺𝗇𝖼𝖾)",
        parse_mode=ParseMode.HTML
    )
# Free Trial end


# Global dictionary to store the timestamp when a user is asked for a txn ID.
pending_txn = {}  # Format: { user_id: datetime }

# In-memory
order_store = {}

async def auto_verify_payment(client, message, order_id: str):
    """
    Poll Paytm up to 60× (5 s apart), then:
      - on TXN_SUCCESS → approve/reject
      - on timeout → notify “could not confirm”
    """
    # ─── 1) wait initial 8 s ─────────────────────────────────────────────────────
    await asyncio.sleep(8)

    # ─── 2) poll up to 60 times, 5 s apart ─────────────────────────────────────
    for _ in range(60):
        info = order_store.get(order_id)
        if not info:
            return

        # call Paytm status endpoint using aiohttp
        paytm_url = (
            f'https://securegw.paytm.in/order/status'
            f'?JsonData={{"MID":"{MID}","ORDERID":"{order_id}"}}'
        )

        try:
            # Use the global aiohttp_session
            async with aiohttp_session.get(paytm_url) as resp:
                if resp.status != 200:
                    await asyncio.sleep(5)
                    continue
                data = await resp.json()
        except Exception as e:
            print(f"[auto_verify_payment] HTTP error: {e}")
            await asyncio.sleep(5)
            continue

        status = data.get("STATUS", "")
        txn_amount = data.get("TXNAMOUNT", "0")

        # load admin bypass list
        cfg = get_admin_config()
        admins = cfg.get("superior_admins", [])
        if not isinstance(admins, list):
            admins = [admins]
        admins = [str(x) for x in admins]
        bypass = str(info["user_id"]) in admins

        if status == "TXN_SUCCESS":
            # reload required amount
            db = read_data()
            slot = db["settings"]["slots"].get(info["slot_id"], {})
            required = float(slot.get("required_amount", 12))
            try:
                paid = round(float(txn_amount), 2)
            except:
                paid = 0.0
                

            logger.info(f"[auto_verify] status={status!r}, amount={txn_amount!r}")
            if abs(paid - required) > 0.001 and not bypass:
               logger.info("[auto_verify] amount mismatch, rejecting")
               await do_reject_flow_immediate(client, message, "Amount mismatch.")
            else:
                if not is_orderid_used(order_id) or bypass:
                    mark_orderid_used(order_id)
                    await do_approve_flow_immediate(client, message, info["slot_id"], data)
                else:
                    await do_reject_flow_immediate(client, message, "Transaction already used.")
            order_store.pop(order_id, None)
            return

        # still pending or any other status → retry after 5 s
        await asyncio.sleep(5)

# ─── 3) timeout ────────────────────────────────────────────────────────────
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
    db_data = read_data()
    amount  = db_data["settings"]["slots"][slot_id].get("required_amount", 12)

    # 1) Reserve an order_id OR OOR ID
    alphabet = string.ascii_uppercase + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(13))
    order_id = f"OOR{random_part}"
    order_store[order_id] = {
        "user_id":        user_id,
        "slot_id":        slot_id,
        "required_amount": float(amount),
        "timestamp":      time.time(),
    }

    # 2) Build UPI URL and styled QR
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

    # 3) Send the QR
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
    
      # ── 3) Build inline keyboard ──────────────────────────────────────────────
# 3) Build inline keyboard with two rows, one button each
    kb = InlineKeyboardMarkup([
        [ InlineKeyboardButton("❌ Cancel",       callback_data=f"cancel_{order_id}") ],
    ])

    # 4) Send the QR **with** reply_markup=kb
    await callback_query.message.reply_photo(
        photo=img_url,
        caption=caption,
        reply_markup=kb      # ← make sure you include this
    )
    await callback_query.answer()
    
    # 4) Start the auto‑verify loop (after QR is shown)
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
    txn_id = data.get("ORDERID")
    if not txn_id:
        logger.error("No ORDERID found in payment response.")
        return

    tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(tz)

    db_data    = read_data() or {}
    slot_info  = db_data.get("settings", {}).get("slots", {}).get(slot_id, {})

    # NEW: dynamic duration
    duration_hrs = int(slot_info.get("duration_hours", 6))
    start_time   = now
    end_time     = now + timedelta(hours=duration_hrs)

    txn_record = {
        "slot_id":     slot_id,
        "start_time":  start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time":    end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "approved_at": now.isoformat(),
        "assign_to":     None,                # ← which credential key
        "user_id":       message.chat.id,     # ← who bought it
        "last_email":    None,                # ← to detect changes
        "last_password": None,
        "hidden": False, # store hidden to false
    }

    # ── Insert into the proper namespace ───────────────────────────────────────
    txns = db_data.setdefault("transactions", {})
    if txn_id.startswith("REF-"):
        txns.setdefault("REF-ID", {})[txn_id] = txn_record
    elif txn_id.startswith("FTRIAL-"):
        txns.setdefault("FTRIAL-ID", {})[txn_id] = txn_record
    else:
        txns[txn_id] = txn_record

    write_data(db_data)

    # ── Get a free credential ──────────────────────────────────────────────────
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

    # ← NEW: record which cred they got and its initial email/password
    txn_record["assign_to"]     = cred_key
    txn_record["last_email"]    = cred_data["email"]
    txn_record["last_password"] = cred_data["password"]
    write_data(db_data)  # persist the updated txn_record

    # ── Build your UI strings ─────────────────────────────────────────────────
    ui        = await get_ui_config_optimized("approve_flow")
    photo_url = ui.get("photo_url", "").replace("\\n", "\n")
    succ_text = ui.get("success_text", "Payment Success ✅").replace("\\n", "\n")
    acct_fmt  = ui.get("account_format", "Email: {email}\nPassword: {password}")\
                     .replace("\\n", "\n")

    email       = cred_data["email"]
    password    = cred_data["password"]
    usage_count = int(cred_data["usage_count"])
    max_usage   = int(cred_data["max_usage"])

    caption = f"{succ_text}\n\n{acct_fmt.format(email=email, password=password)}"

    # ── Build inline keyboard with Refresh button ─────────────────────────────
    kb = InlineKeyboardMarkup([
        [ InlineKeyboardButton("Refresh Password", callback_data=f"refresh_{txn_id}") ],
        [InlineKeyboardButton("Buy Again", callback_data="start")]
    ])

    # ── Send photo or plain text with our new keyboard ────────────────────────
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

    # ── Increment usage counter ────────────────────────────────────────────────
    if usage_count < max_usage:
        update_credential_usage(cred_key, usage_count + 1)




@app.on_callback_query(filters.regex(r"^refresh_(.+)$"))
async def refresh_cred(client, callback_query):
    order_id = callback_query.data.split("_", 1)[1]
    db_data  = read_data() or {}
    txn      = db_data.get("transactions", {}).get(order_id)

    # 1) Validate existence & ownership
    if not txn or txn["user_id"] != callback_query.from_user.id:
        return await callback_query.answer("Invalid request", show_alert=True)

    # 2) Expiry check (Asia/Kolkata)
    tz = pytz.timezone("Asia/Kolkata")
    end_time_naive = datetime.strptime(txn["end_time"], "%Y-%m-%d %H:%M:%S")
    end_time = tz.localize(end_time_naive)
    if datetime.now(tz) > end_time:
        return await callback_query.answer("⏳ Your access has expired.", show_alert=True)

    # 3) Load current credential
    cred_key     = txn["assign_to"]
    cred         = db_data.get(cred_key, {})
    new_email    = cred.get("email", "")
    new_password = cred.get("password", "")

    # 4) Compare to what we last sent
    if new_email == txn["last_email"] and new_password == txn["last_password"]:
        return await callback_query.answer("No change in credentials", show_alert=True)

    # 5) Something changed → update the same message’s caption (with button)
    
    ui        = await get_ui_config_optimized("approve_flow")
    succ_text = ui.get("success_text", "Payment Success ✅").replace("\\n", "\n")
    acct_fmt  = ui.get("account_format", "Email: {email}\nPassword: {password}")\
               .replace("\\n", "\n")
    quote_text = "“𝖨𝖿 𝗅𝗈𝗀𝗀𝖾𝖽 𝗈𝗎𝗍, 𝖳𝖺𝗉 “𝖱𝖾𝖿𝗋𝖾𝗌𝗁” 𝗍𝗈 𝗀𝖾𝗍 𝗒𝗈𝗎𝗋 𝗇𝖾𝗐 𝗉𝖺𝗌𝗌𝗐𝗈𝗋𝖽!”"
               
               
    updated_caption = (
        f"{succ_text}\n\n"
        f"{acct_fmt.format(email=new_email, password=new_password)}\n\n"
        f"{quote_text}"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Refresh Password", callback_data=f"refresh_{order_id}")],
        [InlineKeyboardButton("Buy Again", callback_data="start")]
    ])
    await callback_query.message.edit_caption(
        caption=updated_caption,
        reply_markup=keyboard
    )

    # 6) Persist the new values
    txn["last_email"]    = new_email
    txn["last_password"] = new_password
    write_data(db_data)

    # 7) Confirm with a toast
    await callback_query.answer("Refreshed ✅", show_alert=True)
    
    
    
async def do_reject_flow_immediate(client, message, reason: str = None):
    ui        = await get_ui_config_optimized("reject_flow")
    photo_url = ui.get("photo_url", "").replace("\\n", "\n")
    err_txt   = ui.get("error_text", "Transaction Rejected.").replace("\\n", "\n")

    # Append the specific reason, if any
    if reason:
        err_txt = f"{err_txt}\n\nReason: {reason}"

    # Send as photo+caption if a photo_url is configured...
    if photo_url:
        await client.send_photo(
            chat_id=message.chat.id,
            photo=photo_url,
            caption=err_txt
        )
    # ...otherwise, just send text
    else:
        await client.send_message(
            chat_id=message.chat.id,
            text=err_txt
        )
    
if __name__ == "__main__":
    logger.info("Next Gen Testing multi-slot bot running...")
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(init_aiohttp_session())
        app.run()
    finally:
        logger.info("Shutting down bot and closing session...")
        loop.run_until_complete(close_aiohttp_session())