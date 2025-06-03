import time
import logging
import asyncio
import aiohttp

from pyrogram import Client, filters, errors
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ── Your credentials ───────────────────────────────────────────────────────
api_id = 25270711
api_hash = "6bf18f3d9519a2de12ac1e2e0f5c383e"
bot_token = "7140092976:AAFtmOBKi-mIoVighcf4XXassHimU2CtlR8"
# ────────────────────────────────────────────────────────────────────────────

app = Client("start_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
REAL_DB_URL = "https://testing-6de54-default-rtdb.firebaseio.com"

# ── GLOBAL aiohttp SESSION & UI CACHE ───────────────────────────────────────
aiohttp_session: aiohttp.ClientSession = None
ui_cache = None

async def init_aiohttp_session():
    global aiohttp_session
    if aiohttp_session is None:
        aiohttp_session = aiohttp.ClientSession()

async def close_aiohttp_session():
    global aiohttp_session
    if aiohttp_session:
        await aiohttp_session.close()
        aiohttp_session = None

# ── ASYNC HELPERS FOR ONE‐NODE OPERATIONS ──────────────────────────────────

async def write_user_record(user_id: str):
    """
    PUT /users/<user_id>.json  = true
    (No need to GET first.)
    """
    url = f"{REAL_DB_URL}/users/{user_id}.json"
    try:
        async with aiohttp_session.put(url, json=True) as resp:
            if resp.status != 200:
                logging.error("write_user_record error: %s", await resp.text())
    except Exception as e:
        logging.error("write_user_record exception: %s", e)


async def read_referral_record(user_id: str) -> dict:
    """
    GET /referrals/<user_id>.json
    Returns {} if not found.
    """
    url = f"{REAL_DB_URL}/referrals/{user_id}.json"
    try:
        async with aiohttp_session.get(url) as resp:
            if resp.status == 200:
                return await resp.json() or {}
            elif resp.status == 404:
                return {}
            else:
                logging.error("read_referral_record error: %s", await resp.text())
                return {}
    except Exception as e:
        logging.error("read_referral_record exception: %s", e)
        return {}


async def write_referral_record(user_id: str, data: dict):
    """
    PUT /referrals/<user_id>.json  = data
    """
    url = f"{REAL_DB_URL}/referrals/{user_id}.json"
    try:
        async with aiohttp_session.put(url, json=data) as resp:
            if resp.status != 200:
                logging.error("write_referral_record error: %s", await resp.text())
    except Exception as e:
        logging.error("write_referral_record exception: %s", e)


async def read_start_ui() -> dict:
    """
    GET /ui_config/start_command.json  
    Cached for 30 seconds.
    """
    global ui_cache
    if ui_cache:
        data, ts = ui_cache
        if time.time() - ts < 30:
            return data

    url = f"{REAL_DB_URL}/ui_config/start_command.json"
    try:
        async with aiohttp_session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json() or {}
            else:
                logging.error("read_start_ui error: %s", await resp.text())
                data = {}
    except Exception as e:
        logging.error("read_start_ui exception: %s", e)
        data = {}

    ui_cache = (data, time.time())
    return data


async def get_referral_points_setting() -> int:
    """
    GET /referral_settings.json → extract "points_per_referral"
    """
    url = f"{REAL_DB_URL}/referral_settings.json"
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

# ────────────────────────────────────────────────────────────────────────────

def generate_referral_code(user) -> str:
    return str(user.id)


async def register_user(user) -> str:
    """
    1) Ensure /users/<user_id>.json = true
    2) Read /referrals/<user_id>.json
       • If exists, return its referral_code.
       • If not, create a new record and return new code.
    """
    user_id = str(user.id)
    logging.info("Registering user ID: %s", user_id)

    # 1) Write user flag
    await write_user_record(user_id)

    # 2) Fetch referral record
    rec = await read_referral_record(user_id)
    if rec and "referral_code" in rec:
        # Already has a referral entry
        # (Still rewrite it to keep DB synced in case of incidental changes.)
        await write_referral_record(user_id, rec)
        return rec["referral_code"]
    else:
        # Create new referral entry
        code = generate_referral_code(user)
        new_data = {
            "referral_code": code,
            "referral_points": 0,
            "referred_users": []
        }
        await write_referral_record(user_id, new_data)
        return code


async def add_referral(referrer_code: str, new_user_id: str) -> bool:
    """
    1) Find referrer_id by scanning /referrals (only keys in server)
       Actually, we can directly do a query: GET /referrals.json?orderBy="referral_code"&equalTo="X"
       But REST filtering is cumbersome. So:
         • We will do a GET /referrals.json?shallow=true  → get keys only (small payload)
         • Then for each candidate key → GET /referrals/<candidate>.json to check if code matches.
       Because ~3 000 keys is still manageable in shallow listing.
    2) Once referrer_id found and new_user_id ≠ referrer_id, fetch /referrals/<referrer_id>.json
    3) Append new_user_id, increment points, PUT back.
    """

    # 1a) Shallow fetch to get all referral keys only
    shallow_url = f"{REAL_DB_URL}/referrals.json?shallow=true"
    try:
        async with aiohttp_session.get(shallow_url) as resp:
            if resp.status == 200:
                keys_only = await resp.json() or {}
            else:
                logging.error("add_referral shallow error: %s", await resp.text())
                return False
    except Exception as e:
        logging.error("add_referral shallow exception: %s", e)
        return False

    referrer_id = None
    # 1b) For each key, check /referrals/<key>.json.referral_code
    for candidate in keys_only.keys():
        try:
            async with aiohttp_session.get(f"{REAL_DB_URL}/referrals/{candidate}.json") as r2:
                if r2.status == 200:
                    rec = await r2.json() or {}
                    if rec.get("referral_code") == referrer_code:
                        referrer_id = candidate
                        break
        except:
            continue

    if not referrer_id or new_user_id == referrer_id:
        return False

    # 2) Fetch the referrer’s full record
    record = await read_referral_record(referrer_id)
    if not record:
        return False

    # 3) If new_user_id already in referred_users, skip
    referred = record.get("referred_users", [])
    if new_user_id in referred:
        return False

    referred.append(new_user_id)
    record["referred_users"] = referred

    # 4) Update points
    pts = record.get("points_per_referral")
    if pts is None:
        pts = await get_referral_points_setting()
    record["referral_points"] = record.get("referral_points", 0) + pts

    # 5) Write back /referrals/<referrer_id>.json
    await write_referral_record(referrer_id, record)
    return True

# ────────────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("start"))
async def start_command(client, message):
    """
    1) Referral tracking (calls register_user + maybe add_referral)
    2) Load only UI config at /ui_config/start_command
    3) Send photo (or fallback text) with caption/buttons
    4) Send a timing report (ms)
    """
    t_start = time.time()

    # ── 1) REFERRAL LOGIC ────────────────────────────────────────────────────
    t1 = time.time()
    user = message.from_user
    user_id = str(user.id)

    # Register user (writes /users/<user_id> and /referrals/<user_id> if new)
    my_code = await register_user(user)

    # If they passed a referral code as an argument, process it:
    args = message.text.split()
    referral = args[1].strip().upper() if len(args) > 1 else None
    if referral:
        await add_referral(referral, user_id)
    t2 = time.time()

    # ── 2) LOAD UI CONFIG ───────────────────────────────────────────────────
    t3 = time.time()
    ui = await read_start_ui()
    photo_url = ui.get("photo_url") or "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcScpM1VdgS6eOpxhlnB0d7tR6KVTUBm5DW_1wQthTtS33QOT3ksJsU4yZU&s=10"

    buttons = ui.get("buttons", [])
    if buttons:
        kb = []
        for b in buttons:
            txt = b.get("text", "Button").replace("\\n", "\n")
            cb  = b.get("callback_data", "no_callback")
            if cb == "crunchyroll":
                cb = "book_slot"
            kb.append([InlineKeyboardButton(txt, callback_data=cb)])
    else:
        kb = [
            [InlineKeyboardButton("᪤ Crunchyroll", callback_data="book_slot")],
            [InlineKeyboardButton("🆘 Help",           callback_data="help")]
        ]
    inline_markup = InlineKeyboardMarkup(kb)
    t4 = time.time()

    # ── 3) SEND PHOTO WITH CAPTION AND BUTTONS ──────────────────────────────
    t5 = time.time()
    final_caption = "👋🏻 𝙒𝙚𝙡𝙘𝙤𝙢𝙚! 𝘊𝘩𝘰𝘰𝘴𝘦 𝘢𝘯 𝘰𝘱𝘵𝘪𝘰𝘯:"
    try:
        await client.send_photo(
            chat_id=message.chat.id,
            photo=photo_url,
            caption=final_caption,
            reply_markup=inline_markup
        )
    except errors.WebpageCurlFailed:
        logging.error(f"Failed to fetch image at {photo_url}, sending text only.")
        await client.send_message(
            chat_id=message.chat.id,
            text=final_caption,
            reply_markup=inline_markup
        )
    t6 = time.time()

    # ── 4) SEND TIMING REPORT ────────────────────────────────────────────────
    dur_referral = int((t2 - t1) * 1000)
    dur_ui_load  = int((t4 - t3) * 1000)
    dur_send     = int((t6 - t5) * 1000)
    dur_total    = int((t6 - t_start) * 1000)

    timing_text = (
        f"⏱ Timing (ms):\n"
        f"- Referral & DB writes: {dur_referral} ms\n"
        f"- UI config load:      {dur_ui_load} ms\n"
        f"- Send photo/text:     {dur_send} ms\n"
        f"- Total:               {dur_total} ms"
    )
    await client.send_message(chat_id=message.chat.id, text=timing_text)

# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    # 1) Initialize global aiohttp session once
    loop.run_until_complete(init_aiohttp_session())
    try:
        app.run()
    finally:
        # 2) Close session when bot stops
        loop.run_until_complete(close_aiohttp_session())