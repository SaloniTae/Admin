# broadcaster_with_web.py
import os
import asyncio
import random
import string
import time
import datetime
import logging
import aiofiles
import aiohttp
import json
import re
from aiohttp import web
from pyrogram import idle

from pyrogram import Client, filters, types
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid

# Import your TMDB module (keep the file name tmdb_module.py beside this script)
import tmdb_module

# ---------------- USER CONFIG (patched as you requested) ----------------
BOTS = [
    {
        "api_id": 25270711,
        "api_hash": "6bf18f3d9519a2de12ac1e2e0f5c383e",
        "bot_token": "7140092976:AAEbBq9_XJYuAYjr58zYKbywMxqozEEKNT0",
        "db_url": "https://shivam-testingdb-default-rtdb.firebaseio.com/",
        "name": "Test Bot"
    },
]

ADMIN_ID = [8104243004, 2031595742, 1785564615, 5300690945, 7067405716]
BROADCAST_AS_COPY = True
BATCH_SIZE = 1000
# ------------------------------------------------------------------------

# In-memory original state (preserved)
pending_broadcast = {}
cancel_broadcast_flag = {}   # (bot_key, admin_id) -> bool

# New global structures for web control + mapping + DB helpers
CLIENTS = {}                 # bot_suffix -> pyrogram Client
DB_HELPERS = {}              # bot_suffix -> (read_node, patch_node, get_shallow_keys, read_users_node)
progress_queues = {}         # broadcast_id -> asyncio.Queue
cancel_broadcast_by_id = {}  # broadcast_id -> bool
broadcast_task_map = {}      # broadcast_id -> asyncio.Task
broadcast_id_to_key = {}     # broadcast_id -> (bot_key, admin_id)

# ---------------- DB helpers (unchanged) ----------------
def make_db_helpers(db_url: str, session: aiohttp.ClientSession):
    async def read_node(path: str) -> dict:
        url = db_url.rstrip("/") + f"/{path}.json"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json() or {}
                return {}
        except:
            return {}
    async def patch_node(path: str, payload: dict) -> None:
        url = db_url.rstrip("/") + f"/{path}.json"
        try:
            async with session.patch(url, json=payload):
                pass
        except:
            pass
    async def get_shallow_keys() -> list:
        url = db_url.rstrip("/") + "/.json?shallow=true"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json() or {}
                    return list(data.keys())
                return []
        except:
            return []
    async def read_users_node() -> dict:
        return await read_node("users")
    return read_node, patch_node, get_shallow_keys, read_users_node

# ---------------- TMDB helpers (wrap blocking module functions) ----------------
async def fetch_verified_suggestion(provider_name: str | None = None, media_type: str | None = None):
    """
    Uses tmdb_module.get_verified_suggestion/get_backdrop_url in a thread.
    Returns dict or None.
    """
    def blocking_task():
        providers = tmdb_module.PLATFORM_PROVIDERS
        if provider_name and provider_name in providers:
            prov_id = providers[provider_name]
            prov_name = provider_name
            mt = media_type or random.choice(['tv', 'movie'])
            candidate = tmdb_module.get_verified_suggestion(prov_id, mt, prov_name)
        else:
            prov_name, prov_id = random.choice(list(providers.items()))
            mt = media_type or random.choice(['tv', 'movie'])
            candidate = tmdb_module.get_verified_suggestion(prov_id, mt, prov_name)

        if not candidate:
            return None

        backdrop = tmdb_module.get_backdrop_url(mt, candidate['id'])
        title = candidate.get('title') or candidate.get('name')
        year = (candidate.get('release_date') or candidate.get('first_air_date', ''))[:4]
        rating = candidate.get('vote_average')
        return {
            "platform": prov_name,
            "title": title,
            "year": year,
            "rating": rating,
            "backdrop": backdrop,
            "tmdb_id": candidate['id'],
            "media_type": mt,
            "raw": candidate
        }

    return await asyncio.to_thread(blocking_task)


async def tmdb_search(query: str, limit: int = 10):
    """
    Lightweight TMDB search for autocomplete (runs blocking requests in a thread).
    """
    def blocking_search():
        url = "https://api.themoviedb.org/3/search/multi"
        params = {
            "api_key": tmdb_module.TMDB_API_KEY,
            "query": query,
            "language": "en-US",
            "page": 1,
            "include_adult": False
        }
        import requests
        try:
            r = requests.get(url, params=params, timeout=6)
            r.raise_for_status()
            data = r.json().get("results", [])[:limit]
            results = []
            for item in data:
                results.append({
                    "id": item.get("id"),
                    "media_type": item.get("media_type"),
                    "title": item.get("title") or item.get("name"),
                    "release_date": item.get("release_date") or item.get("first_air_date"),
                    "vote_average": item.get("vote_average")
                })
            return results
        except Exception:
            return []
    return await asyncio.to_thread(blocking_search)

# ----------------- BROADCAST RUNNER (callable) -----------------
async def run_broadcast(client: Client, broadcast_id: str, broadcast_info: dict, recipients: list, admin_id: int, progress_message=None):
    """
    Runs the broadcast and publishes progress to both:
     - the admin Telegram progress message (edited)
     - websocket listeners via progress_queues[broadcast_id]
    broadcast_info:
      - if composed in Telegram, content_msg is a pyrogram.Message object (the original flow)
      - if triggered from web, content_msg is a dict with keys: text, caption, media_file_id, media_type
    """
    bot_key = client.bot_token
    key = (bot_key, admin_id)
    broadcast_id_to_key[broadcast_id] = key

    # queue for websocket listeners
    q = asyncio.Queue()
    progress_queues[broadcast_id] = q
    cancel_broadcast_by_id[broadcast_id] = False

    start_time = time.time()
    total_users = len(recipients)
    done = 0
    success = 0
    failed = 0

    # If no progress_message provided, send initial progress message to admin
    if progress_message is None:
        try:
            progress_message = await client.send_message(admin_id, "Broadcast started...")
        except:
            progress_message = None

    # helper to build inline keyboard
    def build_keyboard(info):
        if info.get("button_option"):
            if info.get("extra_button_option"):
                return types.InlineKeyboardMarkup([
                    [types.InlineKeyboardButton(info["button_text"], url=info["button_url"])],
                    [types.InlineKeyboardButton(info["extra_button_text"], url=info["extra_button_url"])]
                ])
            else:
                return types.InlineKeyboardMarkup([
                    [types.InlineKeyboardButton(info["button_text"], url=info["button_url"])]
                ])
        return None

    custom_keyboard = build_keyboard(broadcast_info)

    # append logs (keeps original broadcast.txt behavior)
    async with aiofiles.open("broadcast.txt", "a") as log_file:
        try:
            for batch_start in range(0, total_users, BATCH_SIZE):
                # check both cancel mechanisms
                if cancel_broadcast_flag.get(key) or cancel_broadcast_by_id.get(broadcast_id):
                    break

                batch = recipients[batch_start: batch_start + BATCH_SIZE]
                for user in batch:
                    if cancel_broadcast_flag.get(key) or cancel_broadcast_by_id.get(broadcast_id):
                        break

                    try:
                        content = broadcast_info.get("content_msg")
                        # If it's a pyrogram Message object (composed in Telegram)
                        if hasattr(content, "media") or hasattr(content, "text") or hasattr(content, "caption"):
                            if getattr(content, "media", False):
                                if hasattr(content, "photo") and content.photo:
                                    await client.send_photo(chat_id=user, photo=content.photo.file_id, caption=content.caption or "", reply_markup=custom_keyboard)
                                elif hasattr(content, "video") and content.video:
                                    await client.send_video(chat_id=user, video=content.video.file_id, caption=content.caption or "", reply_markup=custom_keyboard)
                                else:
                                    await client.send_message(chat_id=user, text=content.caption or "", reply_markup=custom_keyboard)
                            else:
                                await client.send_message(chat_id=user, text=content.text or "", reply_markup=custom_keyboard)
                        else:
                            # content from web (dict)
                            if isinstance(content, dict):
                                if content.get("media_file_id"):
                                    mtype = content.get("media_type", "photo")
                                    if mtype == "photo":
                                        await client.send_photo(chat_id=user, photo=content["media_file_id"], caption=content.get("caption", ""), reply_markup=custom_keyboard)
                                    elif mtype == "video":
                                        await client.send_video(chat_id=user, video=content["media_file_id"], caption=content.get("caption", ""), reply_markup=custom_keyboard)
                                    else:
                                        await client.send_message(chat_id=user, text=content.get("caption","") or content.get("text",""), reply_markup=custom_keyboard)
                                else:
                                    await client.send_message(chat_id=user, text=content.get("text","") or content.get("caption",""), reply_markup=custom_keyboard)
                            else:
                                # fallback
                                await client.send_message(chat_id=user, text=str(content), reply_markup=custom_keyboard)

                        success += 1
                    except Exception as e:
                        await log_file.write(f"{user} : {str(e)}\n")
                        failed += 1
                    done += 1

                    # publish progress at same cadence as original (every 10)
                    if done % 10 == 0 or done == total_users:
                        elapsed = time.time() - start_time
                        avg_time = elapsed / done if done else 0
                        remaining = int((total_users - done) * avg_time) if total_users - done > 0 else 0
                        percent = (done / total_users) * 100 if total_users else 0.0
                        # edit admin message (best-effort)
                        text = (
                            f"𝗕𝗿𝗼𝗮𝗱𝗰𝗮𝘀𝘁 𝗣𝗿𝗼𝗴𝗿𝗲𝘀𝘀 ⚡ (ID: {broadcast_id}):\n\n"
                            f"🚀 𝙎𝙚𝙣𝙩: {done}/{total_users} ({percent:.1f}%)\n\n"
                            f"✅ 𝖲𝗎𝖼𝖼𝖾𝗌𝗌: {success} | ❎ 𝖥𝖺𝗂𝗅𝖾𝖽: {failed}\n\n"
                            f"⏱️ 𝖤𝗅𝖺𝗉𝗌𝖾𝖽:  {datetime.timedelta(seconds=int(elapsed))}\n"
                            f"⏱️ 𝖱𝖾𝗆𝖺𝗂𝗇𝗂𝗇𝗀: {datetime.timedelta(seconds=int(remaining))}"
                        )
                        # push to websocket queue
                        await q.put({
                            "broadcast_id": broadcast_id,
                            "done": done, "total": total_users,
                            "success": success, "failed": failed,
                            "percent": round(percent,1),
                            "elapsed_seconds": int(elapsed),
                            "remaining_seconds": remaining,
                        })
                        if progress_message:
                            try:
                                await progress_message.edit_text(text)
                            except:
                                await asyncio.sleep(0.2)

                await asyncio.sleep(3)
        finally:
            total_time = datetime.timedelta(seconds=int(time.time() - start_time))
            status = "cancelled" if (cancel_broadcast_flag.get(key) or cancel_broadcast_by_id.get(broadcast_id)) else "completed"
            final_summary = {
                "broadcast_id": broadcast_id,
                "done": done, "total": total_users,
                "success": success, "failed": failed,
                "status": status,
                "total_time": str(total_time),
            }
            await q.put(final_summary)
            await q.put(None)
            # cleanup
            await asyncio.sleep(0.05)
            cancel_broadcast_by_id.pop(broadcast_id, None)
            progress_queues.pop(broadcast_id, None)
            broadcast_task_map.pop(broadcast_id, None)
            broadcast_id_to_key.pop(broadcast_id, None)
            # send admin summary message (same UX)
            try:
                summary_text = (
                    f"Broadcast {'CANCELLED' if final_summary['status']=='cancelled' else 'COMPLETED'} (ID: {broadcast_id})\n\n"
                    f"👥 𝗧𝗼𝘁𝗮𝗹: {total_users}\n"
                    f"🚀 𝗦𝗲𝗻𝘁: {done}/{total_users}\n\n"
                    f"✅ 𝖲𝗎𝖼𝖼𝖾𝗌𝗌: {success} | ❎ 𝖥𝖺𝗂𝗅𝖾𝖽: {failed}\n\n"
                    f"⏱️ 𝗙𝗶𝗻𝗶𝘀𝗵𝗲𝗱 𝗶𝗻: {total_time}"
                )
                await client.send_message(admin_id, summary_text)
            except:
                pass

# ----------------- REGISTER BROADCAST HANDLERS (original logic preserved) -----------------
def register_broadcast_handlers(app, read_node, patch_node, get_shallow_keys, read_users_node):
    bot_key = app.bot_token
    
    @app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
    async def broadcast_command(client, message):
        admin_id = message.from_user.id
        pending_broadcast[(bot_key, admin_id)] = {}
        cancel_broadcast_flag[(bot_key, admin_id)] = False
        await message.reply_text("Please send me the content (text or media) that you want to broadcast.")

    @app.on_message(
        filters.user(ADMIN_ID)
        & ~filters.command(["broadcast", "cancelbroadcast"]),
        group=1
    )
    async def capture_broadcast_content(client, message):
        admin_id = message.from_user.id
        if (bot_key, admin_id) not in pending_broadcast:
            return

        info = pending_broadcast[(bot_key, admin_id)]
        if "content_msg" not in info:
            info["content_msg"] = message
            await message.reply_text("Do you want to include an inline button? Reply with 'yes' or 'no'.")

    @app.on_message(
        filters.user(ADMIN_ID)
        & filters.regex("^(yes|no)$", flags=re.IGNORECASE)
        & ~filters.command(["broadcast", "cancelbroadcast"]),
        group=2
    )
    async def capture_inline_button_option(client, message):
        admin_id = message.from_user.id
        if (bot_key, admin_id) not in pending_broadcast:
            return
                
        option = message.text.strip().lower()
        broadcast_info = pending_broadcast[(bot_key, admin_id)]
        if "content_msg" in broadcast_info and "button_option" not in broadcast_info:
            if option == "yes":
                broadcast_info["button_option"] = True
                await message.reply_text("Please send me the inline button text you want to include in the broadcast.")
            elif option == "no":
                broadcast_info["button_option"] = False
                confirm_kb = types.InlineKeyboardMarkup([
                    [
                        types.InlineKeyboardButton("Confirm", callback_data="confirm_broadcast"),
                        types.InlineKeyboardButton("Cancel",  callback_data="cancel_broadcast"),
                    ]
                ])
                await message.reply_text("Do you want to broadcast the content without an inline button?", reply_markup=confirm_kb)
            else:
                await message.reply_text("Invalid response. Please reply with 'yes' or 'no'.")

    @app.on_message(
        filters.user(ADMIN_ID)
        & ~filters.regex("^(yes|no)$", flags=re.IGNORECASE)
        & ~filters.command(["broadcast", "cancelbroadcast"]),
        group=3
    )
    async def capture_button_text(client, message):
        admin_id = message.from_user.id
        if (bot_key, admin_id) not in pending_broadcast:
            return
        broadcast_info = pending_broadcast[(bot_key, admin_id)]
        if broadcast_info.get("button_option") and "button_text" not in broadcast_info:
            if message.text:
                broadcast_info["button_text"] = message.text.strip()
                await message.reply_text("Please send me the inline button URL for the button.")
            else:
                await message.reply_text("Please send a valid button text.")

    @app.on_message(
        filters.user(ADMIN_ID)
        & ~filters.command(["broadcast", "cancelbroadcast"]),
        group=4
    )
    async def capture_button_url(client, message):
        admin_id = message.from_user.id
        if (bot_key, admin_id) not in pending_broadcast:
            return
                
        info = pending_broadcast[(bot_key, admin_id)]
        if info.get("button_option") and "button_text" in info and "button_url" not in info:
            text = message.text.strip()
            if not (text.startswith("http://") or text.startswith("https://")):
                return await message.reply_text("Invalid URL provided. Please send a valid URL starting with http:// or https://")
            info["button_url"] = text
            preview_kb = types.InlineKeyboardMarkup([[types.InlineKeyboardButton(info["button_text"], url=info["button_url"])]])
            await message.reply_text("Here is a preview of your inline button:", reply_markup=preview_kb)
            await message.reply_text("Do you want to add an extra inline button? Reply with 'yes' or 'no'.")

    @app.on_message(
        filters.user(ADMIN_ID)
        & filters.regex("^(yes|no)$", flags=re.IGNORECASE)
        & ~filters.command(["broadcast", "cancelbroadcast"]),
        group=5
    )
    async def capture_extra_button_option(client, message):
        admin_id = message.from_user.id
        if (bot_key, admin_id) not in pending_broadcast:
            return
                
        info = pending_broadcast[(bot_key, admin_id)]
        if info.get("button_option") and "button_url" in info and "extra_button_option" not in info:
            option = message.text.strip().lower()
            if option == "yes":
                info["extra_button_option"] = True
                await message.reply_text("Please send me the extra inline button text.")
            elif option == "no":
                info["extra_button_option"] = False
                confirm_kb = types.InlineKeyboardMarkup([
                    [
                        types.InlineKeyboardButton("Confirm", callback_data="confirm_broadcast"),
                        types.InlineKeyboardButton("Cancel",  callback_data="cancel_broadcast"),
                    ]
                ])
                await message.reply_text("Do you want to broadcast the content with the inline button?", reply_markup=confirm_kb)
            else:
                await message.reply_text("Invalid response. Please reply with 'yes' or 'no'.")

    @app.on_message(
        filters.user(ADMIN_ID)
        & ~filters.regex("^(yes|no)$", flags=re.IGNORECASE)
        & ~filters.command(["broadcast", "cancelbroadcast"]),
        group=6
    )
    async def capture_extra_button_text(client, message):
        admin_id = message.from_user.id
        if (bot_key, admin_id) not in pending_broadcast:
            return
                
        info = pending_broadcast[(bot_key, admin_id)]
        if info.get("extra_button_option") and "extra_button_text" not in info:
            text = message.text.strip()
            if text:
                info["extra_button_text"] = text
                await message.reply_text("Please send me the extra inline button URL.")
            else:
                await message.reply_text("Please send a valid extra button text.")

    @app.on_message(
        filters.user(ADMIN_ID)
        & ~filters.command(["broadcast", "cancelbroadcast"]),
        group=7
    )
    async def capture_extra_button_url(client, message):
        admin_id = message.from_user.id
        if (bot_key, admin_id) not in pending_broadcast:
            return
                
        info = pending_broadcast[(bot_key, admin_id)]
        if info.get("extra_button_option") and "extra_button_text" in info and "extra_button_url" not in info:
            text = message.text.strip()
            if not (text.startswith("http://") or text.startswith("https://")):
                return await message.reply_text("Invalid URL provided for the extra button. Please send a valid URL starting with http:// or https://")
            info["extra_button_url"] = text
            preview_kb = types.InlineKeyboardMarkup([
                [ types.InlineKeyboardButton(info["button_text"], url=info["button_url"]) ],
                [ types.InlineKeyboardButton(info["extra_button_text"], url=info["extra_button_url"]) ]
            ])
            await message.reply_text("Here is a preview of your inline buttons:", reply_markup=preview_kb)
            confirm_kb = types.InlineKeyboardMarkup([
                [
                    types.InlineKeyboardButton("Confirm", callback_data="confirm_broadcast"),
                    types.InlineKeyboardButton("Cancel",  callback_data="cancel_broadcast")
                ]
            ])
            await message.reply_text("Do you want to broadcast the content with the inline buttons?", reply_markup=confirm_kb)

    @app.on_message(filters.command("cancelbroadcast") & filters.user(ADMIN_ID))
    async def cancel_broadcast_command(client, message):
      admin_id = message.from_user.id
      cancel_broadcast_flag[(bot_key, admin_id)] = True
      pending_broadcast.pop((bot_key, admin_id), None)
      await message.reply_text("✅ Broadcast cancelled. All pending broadcasts have been cleared.")

    @app.on_callback_query(filters.user(ADMIN_ID))
    async def broadcast_confirmation(client, callback_query):
        admin_id = callback_query.from_user.id
        key = (bot_key, admin_id)

        if callback_query.data not in ("confirm_broadcast", "cancel_broadcast"):
            return

        if callback_query.data == "cancel_broadcast":
            cancel_broadcast_flag[key] = True
            await callback_query.answer("Broadcast cancelled.", show_alert=True)
            await callback_query.message.edit_text("Broadcast cancelled.")
            pending_broadcast.pop(key, None)
            return

        if key not in pending_broadcast or "content_msg" not in pending_broadcast[key]:
            await callback_query.answer("No broadcast content found.", show_alert=True)
            return

        cancel_broadcast_flag[key] = False
        broadcast_info = pending_broadcast[key]
        content_msg = broadcast_info["content_msg"]

        # fetch recipients from Firebase (same as your original flow)
        users_dict = await read_users_node()
        recipients = [int(uid) for uid in users_dict.keys()] if users_dict else []

        if not recipients:
            await callback_query.answer("No recipients found.", show_alert=True)
            return

        try:
            progress_msg = await callback_query.message.edit_text("Broadcast started...")
        except:
            progress_msg = None

        broadcast_id = "".join(random.choice(string.ascii_letters) for _ in range(6))
        task = asyncio.create_task(run_broadcast(client, broadcast_id, broadcast_info, recipients, admin_id, progress_message=progress_msg))
        broadcast_task_map[broadcast_id] = task

        await callback_query.answer(f"Broadcast started (ID: {broadcast_id})", show_alert=True)
        pending_broadcast.pop(key, None)

# ----------------- AIOHTTP control panel: start/cancel/ws/health -----------------
routes = web.RouteTableDef()

@routes.get("/health")
async def health(request):
    return web.json_response({"status": "ok"})

@routes.get("/broadcasts/active")
async def list_active(request):
    # return list of active broadcast ids
    return web.json_response({"active_broadcasts": list(broadcast_task_map.keys())})

@routes.post("/broadcasts/{bot_suffix}/start")
async def http_start_broadcast(request):
    bot_suffix = request.match_info["bot_suffix"]
    client = CLIENTS.get(bot_suffix)
    if client is None:
        return web.json_response({"error": "unknown bot"}, status=404)

    try:
        data = await request.json()
    except:
        return web.json_response({"error": "invalid json"}, status=400)

    admin_id = data.get("admin_id")
    recipients = data.get("recipients")   # optional
    broadcast_info = data.get("broadcast_info")

    if not admin_id or not broadcast_info:
        return web.json_response({"error": "admin_id and broadcast_info required"}, status=400)

    # if recipients not provided, read from firebase users node for that bot
    if not recipients:
        helpers = DB_HELPERS.get(bot_suffix)
        if not helpers:
            return web.json_response({"error": "no db helpers for this bot"}, status=500)
        read_node, patch_node, get_shallow_keys, read_users_node = helpers
        users_dict = await read_users_node()
        if not users_dict:
            return web.json_response({"error": "no recipients found in DB/users"}, status=400)
        try:
            recipients = [int(uid) for uid in users_dict.keys()]
        except:
            recipients = [int(k) for k in list(users_dict.keys())]

    if not recipients:
        return web.json_response({"error": "recipients list is empty"}, status=400)

    # start broadcast
    broadcast_id = "".join(random.choice(string.ascii_letters) for _ in range(6))
    task = asyncio.create_task(run_broadcast(client, broadcast_id, broadcast_info, recipients, admin_id, progress_message=None))
    broadcast_task_map[broadcast_id] = task

    return web.json_response({"status": "started", "broadcast_id": broadcast_id})

@routes.post("/broadcasts/{broadcast_id}/cancel")
async def http_cancel_broadcast(request):
    broadcast_id = request.match_info["broadcast_id"]
    cancel_broadcast_by_id[broadcast_id] = True
    # try to cancel the asyncio task (best-effort)
    task = broadcast_task_map.get(broadcast_id)
    if task and not task.done():
        try:
            task.cancel()
        except:
            pass
    return web.json_response({"status": "cancelling", "broadcast_id": broadcast_id})

# ----------------- TMDB API endpoints (imported module, clean) -----------------
@routes.get("/api/suggest")
async def api_suggest(request):
    """
    GET /api/suggest?provider=Netflix&media_type=tv
    provider optional (Netflix | Prime Video | Crunchyroll)
    media_type optional (tv | movie)
    """
    provider = request.rel_url.query.get("provider")
    media_type = request.rel_url.query.get("media_type")
    suggestion = await fetch_verified_suggestion(provider_name=provider, media_type=media_type)
    if not suggestion:
        return web.json_response({"error":"no_suggestion"}, status=404)
    return web.json_response({"suggestion": suggestion})

@routes.get("/api/search")
async def api_search(request):
    q = request.rel_url.query.get("q","").strip()
    if not q:
        return web.json_response({"results": []})
    limit = int(request.rel_url.query.get("limit", "10"))
    results = await tmdb_search(q, limit=limit)
    return web.json_response({"results": results})

@routes.post("/api/start_suggestion")
async def api_start_suggestion(request):
    """
    POST:
    {
      "bot_suffix": "<bot_suffix>",
      "admin_id": 8104243004,
      "recipients": [....],     # optional
      "broadcast_info": { ... } # can include use_suggestion: true
    }
    """
    try:
        data = await request.json()
    except:
        return web.json_response({"error":"invalid json"}, status=400)

    bot_suffix = data.get("bot_suffix")
    if not bot_suffix:
        return web.json_response({"error":"bot_suffix required"}, status=400)
    client = CLIENTS.get(bot_suffix)
    if client is None:
        return web.json_response({"error":"unknown bot"}, status=404)

    admin_id = data.get("admin_id")
    if not admin_id:
        return web.json_response({"error":"admin_id required"}, status=400)

    broadcast_info = data.get("broadcast_info") or {}
    recipients = data.get("recipients")   # optional

    # If use_suggestion requested, fetch one and populate content_msg if missing
    if broadcast_info.get("use_suggestion") and "content_msg" not in broadcast_info:
        provider = broadcast_info.get("provider")
        media_type = broadcast_info.get("media_type")
        suggestion = await fetch_verified_suggestion(provider_name=provider, media_type=media_type)
        if suggestion:
            caption = f"**{suggestion['title']} ({suggestion['year']})**\n⭐ {suggestion['rating']}/10\nPlatform: {suggestion['platform']}"
            broadcast_info["content_msg"] = {
                "media_file_id": suggestion["backdrop"],
                "media_type": "photo" if suggestion["backdrop"] else None,
                "caption": caption,
                "text": caption
            }
            # default button to TMDB page
            broadcast_info["button_option"] = True
            broadcast_info["button_text"] = "More info"
            broadcast_info["button_url"] = f"https://www.themoviedb.org/{suggestion['media_type']}/{suggestion['tmdb_id']}"
        else:
            broadcast_info["content_msg"] = {"text": "Couldn't get verified suggestion now."}

    # if recipients not provided, read from firebase users node for that bot
    if not recipients:
        helpers = DB_HELPERS.get(bot_suffix)
        if not helpers:
            return web.json_response({"error": "no db helpers for this bot"}, status=500)
        read_node, patch_node, get_shallow_keys, read_users_node = helpers
        users_dict = await read_users_node()
        if not users_dict:
            return web.json_response({"error": "no recipients found in DB/users"}, status=400)
        try:
            recipients = [int(uid) for uid in users_dict.keys()]
        except:
            recipients = [int(k) for k in list(users_dict.keys())]

    if not recipients:
        return web.json_response({"error": "recipients list is empty"}, status=400)

    # start broadcast
    broadcast_id = "".join(random.choice(string.ascii_letters) for _ in range(6))
    task = asyncio.create_task(run_broadcast(client, broadcast_id, broadcast_info, recipients, admin_id, progress_message=None))
    broadcast_task_map[broadcast_id] = task

    return web.json_response({"status": "started", "broadcast_id": broadcast_id})

# add this route (place it with your other aiohttp routes)
@routes.get("/sse/{broadcast_id}")
async def sse_progress(request):
    """
    Server-Sent Events endpoint that streams JSON progress updates.
    Usage:
      curl -N https://<host>/sse/<broadcast_id>
    Browser: use EventSource("https://<host>/sse/<broadcast_id>")
    """
    broadcast_id = request.match_info["broadcast_id"]

    resp = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # allow cross-origin so you can open this from a static page anywhere
            "Access-Control-Allow-Origin": "*",
        },
    )
    await resp.prepare(request)

    # wait a little for the broadcast to start (same as websocket waiter)
    waited = 0.0
    while broadcast_id not in progress_queues and waited < 5.0:
        await asyncio.sleep(0.1)
        waited += 0.1

    q = progress_queues.get(broadcast_id)
    if q is None:
        # send an error event then close
        err = json.dumps({"error": "no such broadcast or not started yet"})
        await resp.write(f"data: {err}\n\n".encode())
        try:
            await resp.write_eof()
        except:
            pass
        return resp

    try:
        while True:
            payload = await q.get()
            if payload is None:
                # final sentinel
                final_payload = json.dumps({"final": True})
                await resp.write(f"data: {final_payload}\n\n".encode())
                break

            # send JSON as an SSE "data:" event
            data = json.dumps(payload)
            await resp.write(f"data: {data}\n\n".encode())
            # flush
            try:
                await resp.drain()
            except:
                # client likely disconnected, break out
                break

    except asyncio.CancelledError:
        pass
    finally:
        try:
            await resp.write_eof()
        except:
            pass
        return resp

# ----------------- BOOTSTRAP / MAIN -----------------
# Simple CORS middleware for aiohttp
@web.middleware
async def cors_middleware(request, handler):
    # Handle preflight
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Allow-Credentials": "true",
        }
        return web.Response(status=204, headers=headers)

    # Normal request -> call handler then attach CORS headers to response
    resp = await handler(request)
    # if the handler returned a plain value, wrap it
    if not isinstance(resp, web.StreamResponse):
        resp = web.json_response(resp)

    # Set CORS headers for all responses (including SSE)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Allow-Credentials"] = "true"
    return resp

async def start_aiohttp_app(port: int = 8080):
    # Attach the CORS middleware so every route gets the required headers
    app = web.Application(middlewares=[cors_middleware])
    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 aiohttp control panel started on port {port} (CORS enabled)")
    return runner

async def main():
    bots = []
    sessions = []

    # instantiate each bot + its aiohttp session + register handlers
    for cfg in BOTS:
        session = aiohttp.ClientSession()
        sessions.append(session)

        rd, pd, gs, ru = make_db_helpers(cfg["db_url"], session)
        # store helpers for web endpoint usage
        DB_HELPERS[cfg['bot_token'][-5:]] = (rd, pd, gs, ru)

        app = Client(
            name=f"bot_{cfg['bot_token'][-5:]}",
            api_id=cfg["api_id"],
            api_hash=cfg["api_hash"],
            bot_token=cfg["bot_token"]
        )

        CLIENTS[cfg['bot_token'][-5:]] = app
        register_broadcast_handlers(app, rd, pd, gs, ru)
        bots.append((cfg, app))

    # start clients
    for cfg, app in bots:
        bot_name = cfg["name"]
        try:
            await app.start()
            print(f"✅ {bot_name} Bot has started")
        except Exception as e:
            print(f"❌ {bot_name} Bot failed to start: {e}")

    # start aiohttp on configured PORT or 8080
    port = int(os.environ.get("PORT", "8080"))
    aio_runner = None
    try:
        aio_runner = await start_aiohttp_app(port)
    except Exception as e:
        print(f"❌ Failed to start aiohttp server: {e}")

    print("🚀 All valid bots started. Press Ctrl+C to stop.")
    try:
        await idle()
    except KeyboardInterrupt:
        print("🛑 KeyboardInterrupt received, shutting down...")
    finally:
        # Clean up aiohttp runner
        if aio_runner is not None:
            try:
                await aio_runner.cleanup()
                print("🛑 aiohttp server stopped")
            except Exception as e:
                print(f"⚠️ Error stopping aiohttp runner: {e}")

        # Stop each pyrogram client (best-effort)
        for cfg, app in bots:
            bot_name = cfg["name"]
            try:
                # attempt to stop regardless of client attributes
                await app.stop()
                print(f"🛑 {bot_name} Bot stopped")
            except Exception as e:
                # print and continue
                print(f"⚠️ Error stopping {bot_name} Bot (best-effort): {e}")

        # Close each aiohttp session (best-effort)
        for session in sessions:
            try:
                await session.close()
            except Exception as e:
                print(f"⚠️ Error closing aiohttp session: {e}")

        print("🔒 Closed aiohttp sessions and cleaned up")

if __name__ == "__main__":
    asyncio.run(main())
