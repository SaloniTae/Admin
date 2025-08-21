import builtins
builtins.print = lambda *args, **kwargs: None

import os
import asyncio
import json
import signal
import traceback
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Set, Any, List

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl import types as tl_types
from telethon.tl.types import User as TLUser, Message as TLMessage

# Optional HTTP libs (aiohttp preferred)
try:
    import aiohttp  # type: ignore
    _HAS_AIOHTTP = True
except Exception:
    _HAS_AIOHTTP = False
    import requests  # type: ignore




# --- tiny health server for Render (paste near top of file) ---
from aiohttp import web

HEALTH_SERVER_ENABLED = os.getenv("HEALTH_SERVER_ENABLED", "true").lower() in ("1", "true", "yes")
# Render provides PORT env var during deploy; fallback to 8080
HEALTH_BIND_HOST = os.getenv("HEALTH_BIND_HOST", "0.0.0.0")
HEALTH_BIND_PORT = int(os.getenv("PORT", os.getenv("HEALTH_BIND_PORT", "8080")))

# simple handler that reports script status if you have _status_lock/_IS_ONLINE
async def _health_handler(request):
    # include minimal info; safe to return even if status vars are missing
    status = {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
    try:
        # if your script defines these, include them
        async with _status_lock:
            is_online = _IS_ONLINE
        status["my_online"] = bool(is_online is True)
        status["my_status_known"] = (is_online is not None)
    except Exception:
        pass
    return web.json_response(status)

def start_health_server():
    """Create and return an asyncio.Task running the aiohttp health server."""
    if not HEALTH_SERVER_ENABLED:
        return None

    app = web.Application()
    app.router.add_get("/health", _health_handler)

    runner = web.AppRunner(app)

    async def _run():
        try:
            await runner.setup()
            site = web.TCPSite(runner, HEALTH_BIND_HOST, HEALTH_BIND_PORT)
            await site.start()
            if DEBUG:
                print(f"[health] started on http://{HEALTH_BIND_HOST}:{HEALTH_BIND_PORT}/health")
            while running:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            # teardown on cancel
            try:
                await runner.cleanup()
            except Exception:
                pass
            return
        except Exception:
            if DEBUG:
                import traceback as _tb
                _tb.print_exc()
            try:
                await runner.cleanup()
            except Exception:
                pass

    return asyncio.create_task(_run())
# --- end health server block ---






# -------- CONFIG (via env vars / defaults) --------
API_ID = int(os.getenv("TG_API_ID", "12344306"))               # REQUIRED
API_HASH = os.getenv("TG_API_HASH", "618183cd0189d15777dbb390a3d121e0")                 # REQUIRED
SESSION_STRING = os.getenv("TG_SESSION", "1BVtsOIMBu7CdXE4qhkQK7RpEupg1UrFIwnV73_7_dp0jrc4fUXUtjy10ctM-r_V4onGCdPaE4TNA5LsNIJ64GA7yUjWzDyTD2qKLHdbq9bFWrLEa_FOTAQxWUoRe1Kg4JYIcWbkUUu0yS0WC5w70VkPcKvOr4mTLH4O06B-N6emJ1OGBZ8JEnxXA1vBdb2J8fjIE4cTL_Emw9PPyuY3BC8kpiaTFG6MLAt8IxIrj901WxJf2o5O_DEaPZiLP06j2xi8lqmSlARt0nOxY1LqwQ8XvaXS3sfqub1AiLHXTea0cbELzNRLRemlwhe8-6plM5hon-R68eq-fqax27b_aHjf2pPzBWkE=")    
SESSION_NAME = os.getenv("SESSION_NAME", "session")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", ".")
MEDIA_DIRNAME = os.getenv("MEDIA_DIRNAME", "media")
MEDIA_DIR = os.path.join(OUTPUT_DIR, MEDIA_DIRNAME)
MESSAGES_FILE = os.path.join(OUTPUT_DIR, os.getenv("MESSAGES_FILE", "messages.json"))

WORKERS = int(os.getenv("WORKERS", "3"))
QUEUE_MAXSIZE = int(os.getenv("QUEUE_MAXSIZE", "2000"))
BURST_GUARD = float(os.getenv("BURST_GUARD", "0.01"))
MEDIA_DOWNLOAD_CONCURRENCY = int(os.getenv("MEDIA_CONCURRENCY", "2"))
MAX_MEDIA_BYTES = int(os.getenv("MAX_MEDIA_BYTES", str(50 * 1024 * 1024)))  # 50 MB
IGNORE_OUTGOING = os.getenv("IGNORE_OUTGOING", "true").lower() in ("1", "true", "yes")

# RESCAN_INTERVAL: seconds between rescans. Default 30 (run initial scan at startup if offline, then rescans).
RESCAN_INTERVAL = int(os.getenv("RESCAN_INTERVAL", "30"))

# Polling fallback for our own user status. Keep >= 3 to be safe.
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "3"))

DEBUG = os.getenv("DEBUG", "") not in ("", "0", "false", "no")
# -------------------------------------------------

# ---- Notification / Firebase configuration ----
ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID", "887203af-f02f-4a68-ad94-0214cdec4d4f")
ONESIGNAL_API_KEY = os.getenv("ONESIGNAL_API_KEY", "os_v2_app_rbzahl7qf5fgrlmuaikm33cnj6722nlzdy2u5v4wnwxc7hl5xmt7erlubtaxg3lcqrojgpcgu4md5so7p5oxeihqpsmej7bi56lprci")
ONESIGNAL_URL = os.getenv("ONESIGNAL_URL", "https://onesignal.com/api/v1/notifications")

# comma-separated player ids env var or fallback to provided id
PLAYER_IDS = [p.strip() for p in os.getenv("PLAYER_IDS", "bcf177cf-c791-47b9-a620-0ab9d9e3f1de").split(",") if p.strip()]

# Firebase Realtime DB base URL (no trailing slash), e.g. https://tg-unreadmessagesnotify-default-rtdb.firebaseio.com
FIREBASE_BASE_URL = os.getenv("FIREBASE_BASE_URL", "https://tg-unreadmessagesnotify-default-rtdb.firebaseio.com")

# How often to re-notify same unread message (seconds)
RENOTIFY_INTERVAL = int(os.getenv("RENOTIFY_INTERVAL", "300"))  # default 5 minutes

# How often notifier checks dialogs for re-notify and deletion of read entries
NOTIFY_CHECK_INTERVAL = int(os.getenv("NOTIFY_CHECK_INTERVAL", "60"))

# Max messages to include in one notification per user
MAX_MESSAGES_PER_NOTIFICATION = int(os.getenv("MAX_MESSAGES_PER_NOTIFICATION", "8"))

# -------------------------------------------------

if not API_ID or not API_HASH:
    raise SystemExit("ERROR: Set TG_API_ID and TG_API_HASH in environment or edit the script.")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

# Create Telethon client (prefer string session)
if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# runtime
queue: "asyncio.Queue[dict]" = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
file_lock = asyncio.Lock()
media_sema = asyncio.Semaphore(MEDIA_DOWNLOAD_CONCURRENCY)
running = True

# Our user id and status tracking
MY_ID: Optional[int] = None
_status_lock = asyncio.Lock()
_IS_ONLINE: Optional[bool] = None  # None = unknown, True = online, False = offline

# Per-user notify locks to serialize notifications for same user
_notify_locks: Dict[str, asyncio.Lock] = {}

def _now_iso():
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

# ----------------- existing messages.json helpers -----------------
async def load_messages_dict() -> dict:
    if not os.path.exists(MESSAGES_FILE):
        return {}
    try:
        with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        try:
            backup = MESSAGES_FILE + ".corrupt." + datetime.utcnow().strftime("%Y%m%d%H%M%S")
            os.replace(MESSAGES_FILE, backup)
            print("[!] messages.json corrupted - moved to", backup)
        except Exception:
            pass
        return {}

async def save_messages_dict(data: dict):
    tmp = MESSAGES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, MESSAGES_FILE)

# ----------------- existing media helpers -----------------
async def safe_download_media(message: TLMessage) -> Optional[str]:
    if not getattr(message, "media", None):
        return None
    size = None
    try:
        if getattr(message, "file", None) and getattr(message.file, "size", None):
            size = int(message.file.size)
    except Exception:
        size = None
    if size is not None and size > MAX_MEDIA_BYTES:
        return None
    async with media_sema:
        try:
            basename = f"{message.id}_{int(message.date.timestamp())}"
            saved = await client.download_media(message, file=os.path.join(MEDIA_DIR, basename))
            return saved
        except FloodWaitError as e:
            print("[!] FloodWait during media download — sleeping", e.seconds)
            await asyncio.sleep(e.seconds + 1)
            return None
        except Exception as e:
            print("Media download error:", repr(e))
            return None

def media_label_for_message(message: TLMessage) -> Optional[str]:
    if not getattr(message, "media", None):
        return None
    if getattr(message, "photo", None) is not None:
        return "sent a photo"
    f = getattr(message, "file", None)
    if f is not None:
        mt = getattr(f, "mime_type", "") or ""
        mt = mt.lower()
        if "image" in mt:
            return "sent a photo"
        if "video" in mt:
            return "sent a video"
    if getattr(message, "video", None) is not None:
        return "sent a video"
    return "sent a file"

def build_message_entry(message: TLMessage, media_path: Optional[str]) -> dict:
    media_label = media_label_for_message(message)
    text_val = media_label if media_label is not None else getattr(message, "message", None)
    return {
        "message_id": message.id,
        "text": text_val,
        "date": message.date.isoformat() if getattr(message, "date", None) else _now_iso(),
        "is_outgoing": bool(getattr(message, "out", False)),
        "has_media": bool(getattr(message, "media", False)),
        "media_path": media_path
    }

# ----------------- duplicate check -----------------
async def message_already_saved(sender_id: int, message_id: int) -> bool:
    async with file_lock:
        data = await load_messages_dict()
        uid = str(sender_id)
        if uid not in data:
            return False
        msgs = data[uid].get("messages", [])
        for m in msgs:
            try:
                if int(m.get("message_id")) == int(message_id):
                    return True
            except Exception:
                continue
        return False

async def load_saved_ids_map() -> Dict[str, Set[int]]:
    async with file_lock:
        data = await load_messages_dict()
    out: Dict[str, Set[int]] = {}
    for uid, info in (data.items() if isinstance(data, dict) else []):
        try:
            msg_list = info.get("messages", []) if isinstance(info, dict) else []
            s = set()
            for m in msg_list:
                try:
                    s.add(int(m.get("message_id")))
                except Exception:
                    continue
            out[str(uid)] = s
        except Exception:
            continue
    return out

# ----------------- topic detection -----------------
_TOPIC_PATTERNS = {
    "Netflix": [r"\bnetflix\b", r"\bntflix\b", r"\bflix\b"],
    "Prime Video": [r"\bprime\s*video\b", r"\bprimevideo\b", r"\bprime\b"],
    "Crunchyroll": [r"\bcrunchyroll\b", r"\bcrunchy\b"],
    "House": [r"\bfaphouse\b", r"\bfap\s*house\b"]
}
_TOPIC_REGEX = {k: [re.compile(p, re.IGNORECASE) for p in pats] for k, pats in _TOPIC_PATTERNS.items()}

def detect_topic_from_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    for topic, regexes in _TOPIC_REGEX.items():
        for rx in regexes:
            if rx.search(text):
                return topic
    return None

def aggregate_topic_for_messages(texts: List[str]) -> Optional[str]:
    for t in texts:
        topic = detect_topic_from_text(t)
        if topic:
            return topic
    return None

# ----------------- OneSignal helper -----------------
async def send_onesignal_notification_async(title: str, message_lines: List[str], player_ids: Optional[List[str]] = None):
    contents = "\n".join(message_lines)[:3000]
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "headings": {"en": title},
        "contents": {"en": contents},
        "data": {"source": "tele_safe_save_grouped_unread_rescan"}
    }
    if player_ids:
        payload["include_player_ids"] = player_ids
    else:
        payload["included_segments"] = ["Subscribed Users"]

    headers = {
        "Authorization": f"Basic {ONESIGNAL_API_KEY}",
        "Content-Type": "application/json; charset=utf-8"
    }

    if _HAS_AIOHTTP:
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(ONESIGNAL_URL, json=payload, headers=headers, timeout=15) as r:
                    txt = await r.text()
                    if r.status >= 400:
                        print(f"[onesignal] HTTP {r.status}: {txt}")
                    elif DEBUG:
                        print(f"[onesignal] sent ok: {txt}")
        except asyncio.CancelledError:
            raise
        except Exception:
            if DEBUG:
                traceback.print_exc()
    else:
        def _req():
            try:
                r = requests.post(ONESIGNAL_URL, json=payload, headers=headers, timeout=15)
                if r.status_code >= 400:
                    print(f"[onesignal] HTTP {r.status_code}: {r.text}")
                elif DEBUG:
                    print(f"[onesignal] sent ok: {r.text}")
            except Exception:
                if DEBUG:
                    traceback.print_exc()
        await asyncio.to_thread(_req)

# ----------------- Firebase helpers (REST) -----------------
def _firebase_url_for_message(uid: str, mid: int) -> str:
    return f"{FIREBASE_BASE_URL}/notifications/{uid}/{mid}.json"

def _firebase_url_for_user(uid: str) -> str:
    return f"{FIREBASE_BASE_URL}/notifications/{uid}.json"

async def firebase_set_message_notified(uid: str, mid: int, payload: Dict[str, Any]):
    url = _firebase_url_for_message(uid, mid)
    if _HAS_AIOHTTP:
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.put(url, json=payload, timeout=15) as r:
                    if r.status >= 400 and DEBUG:
                        txt = await r.text()
                        print(f"[firebase] PUT {r.status}: {txt}")
        except Exception:
            if DEBUG:
                traceback.print_exc()
    else:
        def _req():
            try:
                requests.put(url, json=payload, timeout=15)
            except Exception:
                if DEBUG:
                    traceback.print_exc()
        await asyncio.to_thread(_req)

async def firebase_get_user_notifications(uid: str) -> Dict[str, Any]:
    url = _firebase_url_for_user(uid)
    if _HAS_AIOHTTP:
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, timeout=15) as r:
                    if r.status == 200:
                        txt = await r.text()
                        try:
                            return json.loads(txt) if txt and txt != "null" else {}
                        except Exception:
                            return {}
                    else:
                        return {}
        except Exception:
            if DEBUG:
                traceback.print_exc()
            return {}
    else:
        def _req():
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    return r.json() or {}
                return {}
            except Exception:
                if DEBUG:
                    traceback.print_exc()
                return {}
        return await asyncio.to_thread(_req)

async def firebase_delete_message(uid: str, mid: int):
    url = _firebase_url_for_message(uid, mid)
    if _HAS_AIOHTTP:
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.delete(url, timeout=15) as r:
                    if r.status >= 400 and DEBUG:
                        txt = await r.text()
                        print(f"[firebase] DELETE {r.status}: {txt}")
        except Exception:
            if DEBUG:
                traceback.print_exc()
    else:
        def _req():
            try:
                requests.delete(url, timeout=15)
            except Exception:
                if DEBUG:
                    traceback.print_exc()
        await asyncio.to_thread(_req)

# ----------------- Firebase notification helpers -----------------
async def should_notify_message_firebase(uid: str, mid: int) -> bool:
    data = await firebase_get_user_notifications(uid)
    if not data:
        return True
    entry = data.get(str(mid))
    if not entry:
        return True
    try:
        last_ts = int(entry.get("last_notified", 0))
        now_ts = int(datetime.utcnow().timestamp())
        return (now_ts - last_ts) >= RENOTIFY_INTERVAL
    except Exception:
        return True

async def mark_messages_notified_firebase(uid: str, msg_ids: List[int]):
    ts = int(datetime.utcnow().timestamp())
    for mid in msg_ids:
        payload = {"last_notified": ts}
        await firebase_set_message_notified(uid, mid, payload)

# ----------------- helper: find unread ids for a user -----------------
async def get_unread_ids_for_entity(entity: TLUser) -> Set[int]:
    """
    Returns set of unread message IDs for the private dialog with 'entity'.
    Uses client.get_dialogs() to find unread_count and client.get_messages to fetch exact unread messages.
    """
    try:
        dialogs = await client.get_dialogs()
    except Exception:
        if DEBUG:
            traceback.print_exc()
        return set()

    unread_count = 0
    found = None
    for dlg in dialogs:
        try:
            ent = getattr(dlg, "entity", None)
            if ent is None:
                continue
            if getattr(ent, "id", None) == getattr(entity, "id", None):
                unread_count = getattr(dlg, "unread_count", None) or getattr(dlg, "unread", None) or 0
                found = dlg
                break
        except Exception:
            continue

    if not unread_count or unread_count <= 0:
        return set()

    try:
        msgs = await client.get_messages(entity, limit=unread_count)
    except Exception:
        if DEBUG:
            traceback.print_exc()
        return set()

    ids = set()
    for m in msgs:
        try:
            if not getattr(m, "out", False):  # only incoming
                ids.add(int(m.id))
        except Exception:
            continue
    return ids

# ----------------- notification builder (per-user aggregated) -----------------
async def notify_user_unread(uid: str, sender_name: Optional[str], entity: TLUser):
    """
    Build a single aggregated notification for 'uid' including only messages that are
    currently unread (per Telegram), which also pass the firebase re-notify test.
    This function uses a per-uid asyncio.Lock so only one notifier runs per user at a time.
    """
    lock = _notify_locks.get(uid)
    if lock is None:
        lock = asyncio.Lock()
        _notify_locks[uid] = lock

    async with lock:
        # fetch unread ids for this user now
        try:
            unread_ids = await get_unread_ids_for_entity(entity)
        except Exception:
            if DEBUG:
                traceback.print_exc()
            unread_ids = set()

        if not unread_ids:
            if DEBUG:
                print(f"[notify_user_unread] no unread ids for uid {uid}, skipping notify")
            return

        # load saved messages from messages.json
        async with file_lock:
            data = await load_messages_dict()
            saved_msgs = data.get(uid, {}).get("messages", []) if data else []

        # filter saved messages that are still unread
        unread_saved = []
        for m in saved_msgs:
            try:
                mid = int(m.get("message_id"))
            except Exception:
                continue
            if mid in unread_ids:
                unread_saved.append(m)

        if not unread_saved:
            if DEBUG:
                print(f"[notify_user_unread] no saved unread messages for uid {uid}")
            return

        # pick candidates that need notification per firebase rules (and cap)
        candidates = []
        for s in reversed(unread_saved):  # newest first
            mid = int(s.get("message_id"))
            try:
                need = await should_notify_message_firebase(uid, mid)
            except Exception:
                need = True
            if need:
                candidates.append(s)
            if len(candidates) >= MAX_MESSAGES_PER_NOTIFICATION:
                break

        if not candidates:
            if DEBUG:
                print(f"[notify_user_unread] nothing to notify for uid {uid} (all within snooze)")
            return

        to_notify = list(reversed(candidates))  # chronological order

        # build notification title and lines
        texts = [m.get("text") or "" for m in to_notify]
        topic = aggregate_topic_for_messages(texts)
        count = len(to_notify)
        if topic:
            title = f"You have {count} Unread Message{'s' if count>1 else ''} About {topic}"
        else:
            title = f"You have {count} Unread Message{'s' if count>1 else ''}"

        lines = []
        for m in to_notify:
            txt = m.get("text") or ""
            single = " ".join(str(txt).splitlines())
            lines.append(f"{sender_name or uid}: {single}")
        lines.append(f"(received {count} unread message{'s' if count>1 else ''})")

        # send via onesignal
        try:
            await send_onesignal_notification_async(title, lines, player_ids=PLAYER_IDS)
        except Exception:
            if DEBUG:
                traceback.print_exc()

        # mark in firebase
        mids = [int(m.get("message_id")) for m in to_notify]
        await mark_messages_notified_firebase(uid, mids)

# ----------------- worker (unchanged logic except notification uses unread set) -----------------
async def worker_task(worker_id: int):
    print(f"[worker-{worker_id}] started")
    while True:
        try:
            item = await queue.get()
        except asyncio.CancelledError:
            break

        try:
            await asyncio.sleep(BURST_GUARD)

            message = item.get("msg")
            sender_entity = item.get("sender")

            if IGNORE_OUTGOING and getattr(message, "out", False):
                continue

            if not isinstance(sender_entity, TLUser):
                if DEBUG:
                    print(f"[worker-{worker_id}] skipping non-user sender: {type(sender_entity)}")
                continue

            if getattr(sender_entity, "bot", False):
                if DEBUG:
                    print(f"[worker-{worker_id}] skipping bot: {getattr(sender_entity, 'username', None)}")
                continue

            if await message_already_saved(sender_entity.id, message.id):
                if DEBUG:
                    print(f"[worker-{worker_id}] message {message.id} already saved for user {sender_entity.id}")
                continue

            media_path = None
            if getattr(message, "media", None):
                media_path = await safe_download_media(message)

            entry = build_message_entry(message, media_path)

            sender_id = getattr(sender_entity, "id", None)
            sender_name = " ".join(filter(None, [getattr(sender_entity, "first_name", None), getattr(sender_entity, "last_name", None)])) or None
            sender_username = getattr(sender_entity, "username", None)

            if sender_id is None:
                print("[!] Unknown sender, skipping message id", getattr(message, "id", None))
                continue

            async with file_lock:
                data = await load_messages_dict()
                uid = str(sender_id)
                new_user = uid not in data
                if uid not in data:
                    data[uid] = {
                        "name": sender_name,
                        "username": sender_username,
                        "messages": []
                    }
                else:
                    if sender_name:
                        data[uid]["name"] = sender_name
                    if sender_username:
                        data[uid]["username"] = sender_username

                data[uid]["messages"].append(entry)
                await save_messages_dict(data)

            print(f"[worker-{worker_id}] saved message {entry['message_id']} from user {uid}")

            # Decide whether to notify (only notify when offline)
            if not entry.get("is_outgoing", False):
                async with _status_lock:
                    is_online = _IS_ONLINE
                if is_online is True:
                    if DEBUG:
                        print("[notify] currently ONLINE => skipping immediate push")
                else:
                    # Build a single aggregated notification for this user containing only currently unread messages
                    try:
                        await notify_user_unread(uid, sender_name, sender_entity)
                    except Exception:
                        if DEBUG:
                            traceback.print_exc()

        except FloodWaitError as e:
            print(f"[worker-{worker_id}] FloodWait: sleeping {e.seconds}s")
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            print(f"[worker-{worker_id}] processing error:", repr(e))
            if DEBUG:
                traceback.print_exc()
        finally:
            try:
                queue.task_done()
            except Exception:
                pass

    print(f"[worker-{worker_id}] exiting")

# ----------------- live new message handler: NO-OP (preserve original) -----------------
@client.on(events.NewMessage(incoming=True))
async def _on_new_message(event):
    if DEBUG:
        print("[handler] live message ignored (client online) id:", getattr(event.message, "id", None))
    return

# ----------------- scan unread private user dialogs (unchanged) -----------------
async def scan_unread_private_messages():
    count_enqueued = 0
    try:
        dialogs = await client.get_dialogs()
    except Exception as e:
        print("[scan] failed to get dialogs:", repr(e))
        return

    saved_map = await load_saved_ids_map()
    in_scan_added: Dict[str, Set[int]] = {}

    for dialog in dialogs:
        try:
            unread_count = getattr(dialog, "unread_count", None)
            if unread_count is None:
                unread_count = getattr(dialog, "unread", None)
            name = getattr(dialog, "name", None)
            entity = getattr(dialog, "entity", None)

            if DEBUG:
                etype = type(entity).__name__ if entity is not None else "None"
                print(f"[scan] dialog: name={name!r} type={etype} unread_count={unread_count}")

            if not unread_count or unread_count <= 0:
                continue

            if not isinstance(entity, TLUser):
                if DEBUG:
                    print(f"[scan] skipping non-user dialog {name} ({type(entity)})")
                continue
            if getattr(entity, "bot", False):
                if DEBUG:
                    print(f"[scan] skipping bot {getattr(entity,'username',None)}")
                continue

            msgs = await client.get_messages(entity, limit=unread_count)
            if not msgs:
                if DEBUG:
                    print(f"[scan] no messages fetched for {name}")
                continue

            uid = str(entity.id)
            saved_for_uid = saved_map.get(uid, set())
            added_for_uid = in_scan_added.setdefault(uid, set())

            for m in reversed(msgs):
                try:
                    if getattr(m, "out", False):
                        continue

                    if int(m.id) in saved_for_uid or int(m.id) in added_for_uid:
                        if DEBUG:
                            print(f"[scan] skipping already-saved/queued message {m.id} for user {uid}")
                        continue

                    if await message_already_saved(entity.id, m.id):
                        if DEBUG:
                            print(f"[scan] message {m.id} confirmed saved by final check, skipping")
                        saved_for_uid.add(int(m.id))
                        continue

                    added_for_uid.add(int(m.id))
                    await queue.put({"msg": m, "sender": entity})
                    count_enqueued += 1

                except Exception as e:
                    if DEBUG:
                        print("[scan] enqueue error:", repr(e))
                    continue

        except Exception as e:
            if DEBUG:
                print("[scan] error for dialog:", repr(e))
            continue

    print(f"[scan] enqueued {count_enqueued} unread private message(s) for processing")

# ----------------- rescanner task (preserve logic; only scan while offline) -----------------
async def rescanner_task():
    if RESCAN_INTERVAL <= 0:
        if DEBUG:
            print("[rescanner] disabled (RESCAN_INTERVAL <= 0)")
        return
    print(f"[rescanner] starting: interval={RESCAN_INTERVAL}s")
    while running:
        try:
            await asyncio.sleep(RESCAN_INTERVAL)
            async with _status_lock:
                is_online = _IS_ONLINE
            if is_online is None:
                if DEBUG:
                    print("[rescanner] status unknown => skipping scan")
                continue
            if is_online:
                if DEBUG:
                    print("[rescanner] currently ONLINE => skipping scan")
                continue
            await scan_unread_private_messages()
        except asyncio.CancelledError:
            break
        except Exception as e:
            if DEBUG:
                print("[rescanner] error:", repr(e))
                traceback.print_exc()
    print("[rescanner] exiting")

# ----------------- status handling: raw updates + polling fallback (preserve behavior) -----------------
def format_status_obj(status) -> str:
    if status is None:
        return "UNKNOWN"
    if isinstance(status, tl_types.UserStatusOnline):
        return "ONLINE"
    if isinstance(status, tl_types.UserStatusOffline):
        return "OFFLINE"
    if isinstance(status, tl_types.UserStatusRecently):
        return "RECENT"
    if isinstance(status, tl_types.UserStatusLastWeek):
        return "LAST_WEEK"
    if isinstance(status, tl_types.UserStatusLastMonth):
        return "LAST_MONTH"
    if isinstance(status, tl_types.UserStatusEmpty):
        return "EMPTY"
    return "OTHER"

def _is_status_online(status) -> bool:
    return isinstance(status, tl_types.UserStatusOnline)

async def _apply_status_obj(status):
    global _IS_ONLINE
    async with _status_lock:
        prev = _IS_ONLINE
        new = _is_status_online(status)
        if prev == new:
            return
        _IS_ONLINE = new

    ts = _now_iso()
    try:
        print(f"[status] {ts} -> {_IS_ONLINE and 'ONLINE' or 'OFFLINE'} (prev={prev})")
    except Exception:
        pass

    # If we just transitioned from online -> offline, run an immediate scan to save unread messages.
    if prev and not new:
        try:
            asyncio.create_task(scan_unread_private_messages())
        except Exception:
            pass

@client.on(events.Raw)
async def _raw_update_handler(update):
    try:
        if isinstance(update, tl_types.UpdateUserStatus):
            uid = getattr(update, "user_id", None)
            if uid is not None and MY_ID is not None and int(uid) == int(MY_ID):
                status = getattr(update, "status", None)
                await _apply_status_obj(status)
    except Exception:
        if DEBUG:
            traceback.print_exc()

async def polling_status_task(poll_interval: float = 3.0):
    backoff = 1.0
    max_backoff = 300.0
    while True:
        try:
            me = await client.get_me()
            status = getattr(me, "status", None)
            await _apply_status_obj(status)
            backoff = 1.0
            await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            return
        except Exception as e:
            print(f"[status_poll] error fetching status: {repr(e)}")
            if DEBUG:
                traceback.print_exc()
            sleep_for = min(max_backoff, poll_interval * backoff)
            print(f"[status_poll] backing off for {sleep_for:.1f}s")
            await asyncio.sleep(sleep_for)
            backoff = min(backoff * 2, max_backoff / max(1.0, poll_interval))

# ----------------- notifier task: re-notify & delete read (Firebase) -----------------
async def notifier_task():
    interval = NOTIFY_CHECK_INTERVAL
    if interval <= 0:
        return
    while running:
        try:
            await asyncio.sleep(interval)
            async with _status_lock:
                is_online = _IS_ONLINE
            if is_online is None:
                if DEBUG:
                    print("[notifier] status unknown - skipping")
                continue
            if is_online:
                if DEBUG:
                    print("[notifier] online - skipping")
                continue

            try:
                dialogs = await client.get_dialogs()
            except Exception:
                if DEBUG:
                    traceback.print_exc()
                continue

            async with file_lock:
                messages_data = await load_messages_dict()

            for dlg in dialogs:
                try:
                    unread_count = getattr(dlg, "unread_count", None)
                    if unread_count is None:
                        unread_count = getattr(dlg, "unread", None)
                    entity = getattr(dlg, "entity", None)
                    if not entity or not isinstance(entity, TLUser):
                        continue
                    uid = str(entity.id)

                    # if no unread messages, delete firebase entries for this user
                    if not unread_count or unread_count <= 0:
                        firebase_entries = await firebase_get_user_notifications(uid)
                        if firebase_entries:
                            for mid_s in list(firebase_entries.keys()):
                                try:
                                    mid = int(mid_s)
                                except Exception:
                                    continue
                                await firebase_delete_message(uid, mid)
                                if DEBUG:
                                    print(f"[notifier] deleted firebase entry for read message {mid} uid {uid}")
                        continue

                    # collect unread message ids from Telegram
                    try:
                        unread_msgs = await client.get_messages(entity, limit=unread_count)
                    except Exception:
                        unread_msgs = []
                    unread_ids = set()
                    for m in unread_msgs:
                        try:
                            if not getattr(m, "out", False):
                                unread_ids.add(int(m.id))
                        except Exception:
                            continue

                    # firebase entries for this user
                    firebase_entries = await firebase_get_user_notifications(uid)

                    # delete firebase entries for saved messages that are no longer unread
                    saved_msgs = messages_data.get(uid, {}).get("messages", []) if messages_data else []
                    for saved in saved_msgs:
                        try:
                            mid = int(saved.get("message_id"))
                        except Exception:
                            continue
                        if mid not in unread_ids:
                            if firebase_entries and str(mid) in firebase_entries:
                                await firebase_delete_message(uid, mid)
                                if DEBUG:
                                    print(f"[notifier] deleted firebase notif for read message {mid} uid {uid}")

                    # find unread saved messages to possibly re-notify
                    unread_saved = []
                    for saved in saved_msgs:
                        try:
                            mid = int(saved.get("message_id"))
                        except Exception:
                            continue
                        if mid in unread_ids:
                            unread_saved.append(saved)
                    if not unread_saved:
                        continue

                    # decide which unread saved messages need re-notify
                    candidates = []
                    for s in unread_saved[::-1]:  # newest first
                        mid = int(s.get("message_id"))
                        try:
                            need = await should_notify_message_firebase(uid, mid)
                        except Exception:
                            need = True
                        if need:
                            candidates.append(s)
                        if len(candidates) >= unread_count:
                            break
                    if not candidates:
                        continue
                    to_notify = list(reversed(candidates[:MAX_MESSAGES_PER_NOTIFICATION]))
                    sender_name = " ".join(filter(None, [getattr(entity, "first_name", None), getattr(entity, "last_name", None)])) or None

                    # use per-user lock to serialize notifier with worker notifications
                    try:
                        await notify_user_unread(uid, sender_name, entity)
                    except Exception:
                        if DEBUG:
                            traceback.print_exc()

                except Exception:
                    if DEBUG:
                        traceback.print_exc()
                    continue

        except asyncio.CancelledError:
            return
        except Exception:
            if DEBUG:
                traceback.print_exc()
            # continue loop

# ----------------- start/stop helpers -----------------
async def start_workers():
    tasks = []
    for i in range(WORKERS):
        t = asyncio.create_task(worker_task(i+1))
        tasks.append(t)
    return tasks

async def stop_workers(tasks):
    global running
    running = False
    try:
        await queue.join()
    except Exception:
        pass
    for t in tasks:
        t.cancel()
    await asyncio.sleep(0.1)

# ----------------- main -----------------
async def main():
    global MY_ID, _IS_ONLINE
        # start health server immediately so Render sees an open port during deploy
    health_task = None
    try:
        health_task = start_health_server()
    except Exception:
        health_task = None

    print("Starting Telethon client...")
    await client.start()
    me = await client.get_me()
    MY_ID = getattr(me, "id", None)
    who = getattr(me, "username", None) or str(getattr(me, "id", "unknown"))
    print("Client started. Logged in as:", who, f"(id={MY_ID})")

    # set initial status from get_me()
    init_status = getattr(me, "status", None)
    async with _status_lock:
        _IS_ONLINE = _is_status_online(init_status)

    print("Initial status:", format_status_obj(init_status))

    worker_tasks = await start_workers()
    rescanner = asyncio.create_task(rescanner_task())

    poll_task = None
    try:
        if POLL_INTERVAL and POLL_INTERVAL > 0:
            poll_task = asyncio.create_task(polling_status_task(POLL_INTERVAL))
    except Exception:
        poll_task = None

    notifier = asyncio.create_task(notifier_task())

    # Initial scan: run only if we start OFFLINE (if online, don't save now)
    async with _status_lock:
        starting_online = _IS_ONLINE

    if starting_online:
        print("Starting ONLINE — skipping initial scan. Messages will be saved when you go OFFLINE.")
    else:
        print("Starting OFFLINE — running initial scan for unread private DMs...")
        await scan_unread_private_messages()

    print("Rescanner will pick up unread messages every", RESCAN_INTERVAL, "seconds when you are OFFLINE.")
    try:
        await client.run_until_disconnected()
    finally:
        print("Client disconnected — stopping workers, rescanner, poller...")
        if poll_task:
            poll_task.cancel()
            try:
                await poll_task
            except Exception:
                pass
        rescanner.cancel()
        notifier.cancel()
        await stop_workers(worker_tasks)

    try:
        await client.run_until_disconnected()
    finally:
        # cancel health server cleanly
        if health_task:
            health_task.cancel()
            try:
                await health_task
            except Exception:
                pass

def _handle_exit(signame):
    print(f"Received {signame}, shutting down...")
    try:
        asyncio.create_task(client.disconnect())
    except Exception:
        pass

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    for s in ("SIGINT", "SIGTERM"):
        try:
            loop.add_signal_handler(getattr(signal, s), lambda s=s: _handle_exit(s))
        except NotImplementedError:
            pass
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
        print("Shutdown complete.")
