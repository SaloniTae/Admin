# file: broadcaster_with_web.py
import os
import asyncio
import random
import string
import time
import datetime
import logging
import aiofiles
import aiohttp
import re
from aiohttp import web
from pyrogram import idle

from pyrogram import Client, filters, types
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid

# ---------------- USER CONFIG ----------------
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
# ----------------------------------------------

# existing in-memory states from your original code (kept)
pending_broadcast = {}
cancel_broadcast_flag = {}   # your original key: (bot_key, admin_id) -> bool

# new structures for web control + mapping
CLIENTS = {}                 # map bot_token_suffix -> pyrogram Client
progress_queues = {}         # broadcast_id -> asyncio.Queue
cancel_broadcast_by_id = {}  # broadcast_id -> bool
broadcast_task_map = {}      # broadcast_id -> asyncio.Task
broadcast_id_to_key = {}     # broadcast_id -> (bot_key, admin_id) - for telegram cancel cross-check

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

# ----------------- BROADCAST RUNNER (callable) -----------------
async def run_broadcast(client: Client, broadcast_id: str, broadcast_info: dict, recipients: list, admin_id: int, progress_message=None):
    """
    Runs the broadcast. broadcast_info may be:
      - the same dict you stored in pending_broadcast (where content_msg is a pyrogram Message)
      - OR a dict coming from web with keys: content_msg {text, caption, media_file_id, media_type}, and button fields
    progress_message: if provided, will be edited for live updates (keeps original UX).
    """
    # Map the broadcast_id back to the key so telegram / cancel command can work
    bot_key = client.bot_token
    key = (bot_key, admin_id)
    broadcast_id_to_key[broadcast_id] = key

    # create queue for websocket listeners
    q = asyncio.Queue()
    progress_queues[broadcast_id] = q
    cancel_broadcast_by_id[broadcast_id] = False

    start_time = time.time()
    total_users = len(recipients)
    done = 0
    success = 0
    failed = 0

    # fallback: if no progress_message passed, send a new one
    if progress_message is None:
        try:
            progress_message = await client.send_message(admin_id, "Broadcast started...")
        except:
            progress_message = None

    # prepare keyboard builder helper
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

    async with aiofiles.open("broadcast.txt", "a") as log_file:
        try:
            # Iterate in batches - same logic as your original loop
            for batch_start in range(0, total_users, BATCH_SIZE):
                # Check cancel flags (from Telegram cancel command or from web cancel endpoint)
                if cancel_broadcast_flag.get(key) or cancel_broadcast_by_id.get(broadcast_id):
                    break

                batch = recipients[batch_start: batch_start + BATCH_SIZE]
                for user in batch:
                    if cancel_broadcast_flag.get(key) or cancel_broadcast_by_id.get(broadcast_id):
                        break

                    try:
                        # Support both pyrogram Message stored in broadcast_info["content_msg"]
                        # or a simplified dict coming from web control.
                        content = broadcast_info.get("content_msg")
                        # If it's a pyrogram Message object (composed in telegram), handle same as before:
                        if hasattr(content, "media") or hasattr(content, "text") or hasattr(content, "caption"):
                            # this is the original flow - use message attributes
                            if getattr(content, "media", False):
                                if hasattr(content, "photo") and content.photo:
                                    await client.send_photo(
                                        chat_id=user,
                                        photo=content.photo.file_id,
                                        caption=content.caption or "",
                                        reply_markup=custom_keyboard
                                    )
                                elif hasattr(content, "video") and content.video:
                                    await client.send_video(
                                        chat_id=user,
                                        video=content.video.file_id,
                                        caption=content.caption or "",
                                        reply_markup=custom_keyboard
                                    )
                                else:
                                    await client.send_message(
                                        chat_id=user,
                                        text=content.caption or "",
                                        reply_markup=custom_keyboard
                                    )
                            else:
                                await client.send_message(
                                    chat_id=user,
                                    text=content.text or "",
                                    reply_markup=custom_keyboard
                                )
                        else:
                            # possibility: content is a dict sent via web endpoint
                            # expected keys:
                            # content_msg: { "text": "...", "caption": "...", "media_file_id": "...", "media_type": "photo"/"video" }
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
                                # unknown content shape - fallback
                                await client.send_message(chat_id=user, text=str(content), reply_markup=custom_keyboard)

                        success += 1
                    except Exception as e:
                        # log error (append)
                        await log_file.write(f"{user} : {str(e)}\n")
                        failed += 1
                    done += 1

                    # publish progress every few messages (your original used 10)
                    if done % 10 == 0 or done == total_users:
                        elapsed = time.time() - start_time
                        avg_time = elapsed / done if done else 0
                        remaining = int((total_users - done) * avg_time) if total_users - done > 0 else 0
                        percent = (done / total_users) * 100 if total_users else 0.0
                        text = (
                            f"𝗕𝗿𝗼𝗮𝗱𝗰𝗮𝘀𝘁 𝗣𝗿𝗼𝗴𝗿𝗲𝘀𝘀 ⚡ (ID: {broadcast_id}):\n\n"
                            f"🚀 𝙎𝙚𝙣𝙩: {done}/{total_users} ({percent:.1f}%)\n\n"
                            f"✅ 𝖲𝗎𝖼𝖼𝖾𝗌𝗌: {success} | ❎ 𝖥𝖺𝗂𝗅𝖾𝖽: {failed}\n\n"
                            f"⏱️ 𝖤𝗅𝖺𝗉𝗌𝖾𝖽:  {datetime.timedelta(seconds=int(elapsed))}\n"
                            f"⏱️ 𝖱𝖾𝗆𝖺𝗂𝗇𝗂𝗇𝗀: {datetime.timedelta(seconds=int(remaining))}"
                        )
                        # push to progress queue for websocket clients
                        await q.put({
                            "broadcast_id": broadcast_id,
                            "done": done, "total": total_users,
                            "success": success, "failed": failed,
                            "percent": round(percent, 1),
                            "elapsed_seconds": int(elapsed),
                            "remaining_seconds": remaining,
                        })
                        # edit admin progress message if possible (best-effort)
                        if progress_message:
                            try:
                                await progress_message.edit_text(text)
                            except:
                                # ignore edit failures (message edited elsewhere)
                                await asyncio.sleep(0.2)

                # small batch delay like your original
                await asyncio.sleep(3)

        finally:
            # final publish & cleanup
            total_time = datetime.timedelta(seconds=int(time.time() - start_time))
            status = "cancelled" if (cancel_broadcast_flag.get(key) or cancel_broadcast_by_id.get(broadcast_id)) else "completed"
            final_summary = {
                "broadcast_id": broadcast_id,
                "done": done, "total": total_users,
                "success": success, "failed": failed,
                "status": status,
                "total_time": str(total_time),
            }
            # push final then sentinel
            await q.put(final_summary)
            await q.put(None)

            # cleanup maps after short delay
            await asyncio.sleep(0.05)
            cancel_broadcast_by_id.pop(broadcast_id, None)
            progress_queues.pop(broadcast_id, None)
            broadcast_task_map.pop(broadcast_id, None)
            broadcast_id_to_key.pop(broadcast_id, None)

            # send summary to admin (as original)
            try:
                summary_text = (
                    f"Broadcast {'CANCELLED' if final_summary['status']=='cancelled' else 'COMPLETED'} (ID: {broadcast_id})\n\n"
                    f"👥 𝗧𝗼𝘁𝗮𝗹: {total_users}\n"
                    f"🚀 𝗦𝗲𝗻𝘁: {done}/{total_users}\n\n"
                    f"✅ 𝖲𝗎𝖼𝖼𝖾𝗌𝗌: {success} | ❎ 𝖥𝖺𝗂𝗅𝖾𝖽: {failed}\n\n"
                    f"⏱️ 𝖥𝗂𝗇𝗂𝖲𝗁𝖾𝗗 𝗂𝗇: {total_time}"
                )
                await client.send_message(admin_id, summary_text)
            except:
                pass

# ----------------- REGISTER BROADCAST HANDLERS (original) -----------------
def register_broadcast_handlers(app, read_node, patch_node, get_shallow_keys, read_users_node):
    bot_key = app.bot_token
    
    # Step 1: /broadcast command
    @app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
    async def broadcast_command(client, message):
        admin_id = message.from_user.id
        pending_broadcast[(bot_key, admin_id)] = {}
        cancel_broadcast_flag[(bot_key, admin_id)] = False
        await message.reply_text(
            "Please send me the content (text or media) that you want to broadcast."
        )

    # Group 1: Capture the content
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
            await message.reply_text(
                "Do you want to include an inline button? Reply with 'yes' or 'no'."
            )

    # Group 2: Yes/No for inline button
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
                await message.reply_text(
                    "Please send me the inline button text you want to include in the broadcast."
                )
            elif option == "no":
                broadcast_info["button_option"] = False
                confirm_kb = types.InlineKeyboardMarkup([
                    [
                        types.InlineKeyboardButton("Confirm", callback_data="confirm_broadcast"),
                        types.InlineKeyboardButton("Cancel",  callback_data="cancel_broadcast"),
                    ]
                ])
                await message.reply_text(
                    "Do you want to broadcast the content without an inline button?",
                    reply_markup=confirm_kb
                )
            else:
                await message.reply_text("Invalid response. Please reply with 'yes' or 'no'.")

    # Group 3: Capture the inline button text
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
                await message.reply_text(
                    "Please send me the inline button URL for the button."
                )
            else:
                await message.reply_text("Please send a valid button text.")

    # Group 4: Capture the primary inline button URL.
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
        # Only proceed if they opted for a button, provided text but not yet URL
        if info.get("button_option") and "button_text" in info and "button_url" not in info:
            text = message.text.strip()
            if not (text.startswith("http://") or text.startswith("https://")):
                return await message.reply_text(
                    "Invalid URL provided. Please send a valid URL starting with http:// or https://"
                )
            info["button_url"] = text
            # Preview it
            preview_kb = types.InlineKeyboardMarkup([
                [types.InlineKeyboardButton(info["button_text"], url=info["button_url"])]
            ])
            await message.reply_text(
                "Here is a preview of your inline button:", 
                reply_markup=preview_kb
            )
            # Next: ask if they want an extra button
            await message.reply_text("Do you want to add an extra inline button? Reply with 'yes' or 'no'.")

    # Group 5: Capture the extra inline button option.
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
        # Only if they said yes to a primary button and haven't decided on extra yet
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
                await message.reply_text(
                    "Do you want to broadcast the content with the inline button?",
                    reply_markup=confirm_kb
                )
            else:
                await message.reply_text("Invalid response. Please reply with 'yes' or 'no'.")

    # Group 6: Capture the extra inline button text.
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
        # Only if they opted for an extra button and haven't given its text yet
        if info.get("extra_button_option") and "extra_button_text" not in info:
            text = message.text.strip()
            if text:
                info["extra_button_text"] = text
                await message.reply_text("Please send me the extra inline button URL.")
            else:
                await message.reply_text("Please send a valid extra button text.")

    # Group 7: Capture the extra inline button URL and send a preview.
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
        # Only if they said “yes” to extra and provided text but not URL
        if info.get("extra_button_option") and "extra_button_text" in info and "extra_button_url" not in info:
            text = message.text.strip()
            if not (text.startswith("http://") or text.startswith("https://")):
                return await message.reply_text(
                    "Invalid URL provided for the extra button. Please send a valid URL starting with http:// or https://"
                )
            info["extra_button_url"] = text

            # Preview both buttons
            preview_kb = types.InlineKeyboardMarkup([
                [ types.InlineKeyboardButton(info["button_text"], url=info["button_url"]) ],
                [ types.InlineKeyboardButton(info["extra_button_text"], url=info["extra_button_url"]) ]
            ])
            await message.reply_text(
                "Here is a preview of your inline buttons:",
                reply_markup=preview_kb
            )

            # Final confirm/cancel
            confirm_kb = types.InlineKeyboardMarkup([
                [
                    types.InlineKeyboardButton("Confirm", callback_data="confirm_broadcast"),
                    types.InlineKeyboardButton("Cancel",  callback_data="cancel_broadcast")
                ]
            ])
            await message.reply_text(
                "Do you want to broadcast the content with the inline buttons?",
                reply_markup=confirm_kb
            )

# ---------------- BROADCAST HANDLERS (existing cancel & confirm) ----------------
    @app.on_message(filters.command("cancelbroadcast") & filters.user(ADMIN_ID))
    async def cancel_broadcast_command(client, message):
      admin_id = message.from_user.id

      cancel_broadcast_flag[(bot_key, admin_id)] = True
      pending_broadcast.pop((bot_key, admin_id), None)
      
      await message.reply_text(
        "✅ Broadcast cancelled. All pending broadcasts have been cleared."
      )

    # Callback for confirm/cancel
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

        # callback_query.data == "confirm_broadcast"
        if key not in pending_broadcast or "content_msg" not in pending_broadcast[key]:
            await callback_query.answer("No broadcast content found.", show_alert=True)
            return

        # Instead of running inline, we launch run_broadcast as background task
        cancel_broadcast_flag[key] = False
        broadcast_info = pending_broadcast[key]
        content_msg = broadcast_info["content_msg"]

        users_dict = await read_users_node()
        recipients = [int(uid) for uid in users_dict.keys()]

        if not recipients:
            await callback_query.answer("No recipients found.", show_alert=True)
            return

        # Edit the admin message like your original flow
        try:
            progress_msg = await callback_query.message.edit_text("Broadcast started...")
        except:
            progress_msg = None

        # create a broadcast id and schedule the runner as a background task
        broadcast_id = "".join(random.choice(string.ascii_letters) for _ in range(6))
        # start the task
        task = asyncio.create_task(run_broadcast(client, broadcast_id, broadcast_info, recipients, admin_id, progress_message=progress_msg))
        broadcast_task_map[broadcast_id] = task

        # reply to admin that it's started and give the id
        await callback_query.answer(f"Broadcast started (ID: {broadcast_id})", show_alert=True)

        # clear pending_broadcast entry (like original)
        pending_broadcast.pop(key, None)

# ----------------- AIOHTTP control panel (start/cancel + websocket) -----------------
routes = web.RouteTableDef()

@routes.post("/broadcasts/{bot_suffix}/start")
async def http_start_broadcast(request):
    """
    Start a broadcast from web. Request JSON shape:
    {
      "admin_id": 7506651658,
      "recipients": [12345, 23456],
      "broadcast_info": {
         "content_msg": { "text": "...", "caption": "...", "media_file_id": "...", "media_type": "photo" },
         "button_option": false,
         ...
      }
    }
    """
    bot_suffix = request.match_info["bot_suffix"]
    client = CLIENTS.get(bot_suffix)
    if client is None:
        return web.json_response({"error": "unknown bot"}, status=404)

    try:
        data = await request.json()
    except:
        return web.json_response({"error": "invalid json"}, status=400)

    admin_id = data.get("admin_id")
    recipients = data.get("recipients", [])
    broadcast_info = data.get("broadcast_info")

    if not admin_id or not recipients or not broadcast_info:
        return web.json_response({"error": "admin_id, recipients, broadcast_info required"}, status=400)

    # generate id and start task
    broadcast_id = "".join(random.choice(string.ascii_letters) for _ in range(6))
    # run in background
    task = asyncio.create_task(run_broadcast(client, broadcast_id, broadcast_info, recipients, admin_id, progress_message=None))
    broadcast_task_map[broadcast_id] = task

    return web.json_response({"status": "started", "broadcast_id": broadcast_id})

@routes.post("/broadcasts/{broadcast_id}/cancel")
async def http_cancel_broadcast(request):
    broadcast_id = request.match_info["broadcast_id"]
    # mark cancel flag
    cancel_broadcast_by_id[broadcast_id] = True

    # also try to cancel the running asyncio task (best-effort)
    task = broadcast_task_map.get(broadcast_id)
    if task and not task.done():
        try:
            task.cancel()
        except:
            pass

    return web.json_response({"status": "cancelling", "broadcast_id": broadcast_id})

@routes.get("/ws/{broadcast_id}")
async def websocket_progress(request):
    """
    Connect via websocket to receive JSON progress updates.
    The server will send dicts and finally a None-sentinel wrapped as {"final": true, ...}
    """
    broadcast_id = request.match_info["broadcast_id"]
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # wait a short while for queue to appear
    waited = 0.0
    while broadcast_id not in progress_queues and waited < 5.0:
        await asyncio.sleep(0.1)
        waited += 0.1

    q = progress_queues.get(broadcast_id)
    if q is None:
        await ws.send_json({"error": "no such broadcast or not started yet"})
        await ws.close()
        return ws

    try:
        while True:
            payload = await q.get()
            if payload is None:
                # final sentinel - inform client then close
                await ws.send_json({"final": True})
                break
            await ws.send_json(payload)
    except asyncio.CancelledError:
        pass
    finally:
        await ws.close()
        return ws

# ----------------- BOOTSTRAP / MAIN -----------------
async def start_aiohttp_app(port: int = 8080):
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 aiohttp control panel started on port {port}")
    return runner

async def main():
    bots = []
    sessions = []

    # instantiate each bot + its aiohttp session + register handlers
    for cfg in BOTS:
        session = aiohttp.ClientSession()
        sessions.append(session)

        rd, pd, gs, ru = make_db_helpers(cfg["db_url"], session)

        app = Client(
            name=f"bot_{cfg['bot_token'][-5:]}",
            api_id=cfg["api_id"],
            api_hash=cfg["api_hash"],
            bot_token=cfg["bot_token"]
        )

        # keep mapping so web endpoints can select client by suffix
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
    aio_runner = await start_aiohttp_app(port)

    print("🚀 All valid bots started. Press Ctrl+C to stop.")
    # keep running until interrupted
    try:
        await idle()
    except KeyboardInterrupt:
        pass
    finally:
        # shutdown web server
        try:
            await aio_runner.cleanup()
            print("🛑 aiohttp server stopped")
        except:
            pass

        # stop all bots and close sessions
        for cfg, app in bots:
            bot_name = cfg["name"]
            if app.is_running:
                try:
                    await app.stop()
                    print(f"🛑 {bot_name} Bot stopped")
                except:
                    pass

        for session in sessions:
            try:
                await session.close()
            except:
                pass
        print("🔒 Closed aiohttp sessions and cleaned up")

if __name__ == "__main__":
    asyncio.run(main())
