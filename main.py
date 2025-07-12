# import builtins
# builtins.print = lambda *args, **kwargs: None
""" ^^^ Turn OFF Print ^^^ """


import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Tuple, List, Optional
import logging

import requests
from flask import Flask, jsonify

# ─── ONE SIGNAL CONFIG ─────────────────────────────────────────────────────────
ONESIGNAL_APP_ID  = os.getenv("ONESIGNAL_APP_ID")
ONESIGNAL_API_KEY = os.getenv("ONESIGNAL_API_KEY")
ONESIGNAL_URL     = os.getenv("ONESIGNAL_URL", "https://onesignal.com/api/v1/notifications")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def send_push_notification(
    title: str,
    body: str,
    player_ids: List[str],
    big_picture: Optional[str] = None
):
    """
    Sends a OneSignal push notification to exactly the given player_ids,
    and optionally includes a big_picture URL.
    """
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {ONESIGNAL_API_KEY}"
    }
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "include_player_ids": player_ids,
        "headings": {"en": title},
        "contents": {"en": body},
    }
    if big_picture:
        # Android / generic
        payload["big_picture"] = big_picture
        # Chrome Web
        payload["chrome_web_image"] = big_picture
        # iOS
        payload["ios_attachments"] = {"id": big_picture}

    try:
        resp = requests.post(ONESIGNAL_URL, json=payload, headers=headers)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        logger.error("OneSignal %s: %s", resp.status_code, resp.text)

    except Exception as e:
        logger.error("OneSignal push failed: %s", e)

# ─── MONITOR FACTORY ────────────────────────────────────────────────────────────

def make_monitor(db_url: str, service: str, poll_interval: float = 1.0):
    """
    Returns a monitor_loop() that watches `db_url` and sends notifications
    only to subscribers in OneSignal/{service}, using the single photo at
    OneSignal/{service}/photo
    """
    db_url = db_url.rstrip("/")

    # ─── FIREBASE REST HELPERS ────────────────────────────────────────────────
    def firebase_get(path: str) -> dict:
        url = f"{db_url}/{path}.json"
        resp = requests.get(url); resp.raise_for_status()
        return resp.json() or {}

    def firebase_patch(path: str, data: dict):
        url = f"{db_url}/{path}.json"
        resp = requests.patch(url, json=data); resp.raise_for_status()
        return resp.json()

    def firebase_delete(path: str):
        url = f"{db_url}/{path}.json"
        resp = requests.delete(url); resp.raise_for_status()
        return resp.json()

    # ─── STATE PERSISTENCE ────────────────────────────────────────────────────
    def load_state() -> Tuple[Dict[str,bool], Dict[str,bool]]:
        base = firebase_get("notification_state")
        notified = base.get("notified_expiries", {}) or {}
        upcoming = base.get("upcoming_expiry_notices", {}) or {}
        return {k: bool(v) for k,v in notified.items()}, {k: bool(v) for k,v in upcoming.items()}

    def mark_notified_expiry(tx_id: str):
        firebase_patch("notification_state/notified_expiries", {tx_id: True})

    def unmark_notified_expiry(tx_id: str):
        firebase_delete(f"notification_state/notified_expiries/{tx_id}")

    def mark_upcoming_hour(hour_key: str):
        firebase_patch("notification_state/upcoming_expiry_notices", {hour_key: True})

    def unmark_upcoming_hour(hour_key: str):
        firebase_delete(f"notification_state/upcoming_expiry_notices/{hour_key}")

    # ─── DATE/TIME HELPERS ───────────────────────────────────────────────────────
    def parse_datetime(dt_str: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(dt_str.replace(" ", "T"))
        except Exception:
            return None

    def format_time_with_ampm(dt: datetime) -> str:
        return dt.strftime("%-I:%M %p")

    def format_date_with_time(dt: datetime) -> str:
        now = datetime.now()
        today = now.date()
        tomorrow = (now + timedelta(days=1)).date()
        if dt.date() == today:
            return f"Today at {format_time_with_ampm(dt)}"
        elif dt.date() == tomorrow:
            return f"Tomorrow at {format_time_with_ampm(dt)}"
        else:
            return dt.strftime("%b %-d") + f" at {format_time_with_ampm(dt)}"

    def group_by_hour(items: List[Tuple[str,dict]]) -> Dict[str,List[Tuple[str,dict]]]:
        grp: Dict[str,List[Tuple[str,dict]]] = {}
        for tx_id, data in items:
            end_dt = parse_datetime(data.get("end_time",""))
            if not end_dt: continue
            key = end_dt.strftime("%Y-%m-%dT%H")
            grp.setdefault(key, []).append((tx_id, data))
        return grp

    def get_next_expiry(active: List[Tuple[str,dict]]):
        now = datetime.now()
        future = [i for i in active if parse_datetime(i[1]["end_time"]) and parse_datetime(i[1]["end_time"]) > now]
        if not future: return None
        future.sort(key=lambda x: parse_datetime(x[1]["end_time"]))
        return future[0]

    # ─── CORE FILTER + NOTIFY ──────────────────────────────────────────────────
    def filter_transactions(
        all_tx: Dict[str,dict],
        notified: Dict[str,bool],
        upcoming: Dict[str,bool]
    ) -> Tuple[List[Tuple[str,dict]],List[Tuple[str,dict]]]:
        now = datetime.now()
        active_list: List[Tuple[str,dict]] = []
        expired_list: List[Tuple[str,dict]] = []
        new_exp = False

        # 1. Determine currently active IDs/hours
        active_ids, active_hours = set(), set()
        for tx_id, data in all_tx.items():
            if not isinstance(data, dict) or data.get("hidden") or not data.get("end_time"):
                continue
            d = parse_datetime(data["end_time"])
            if d and d > now:
                active_ids.add(tx_id)
                active_hours.add(d.strftime("%Y-%m-%dT%H"))

        # 2. Cleanup old state
        for tx_id in list(notified):
            if tx_id in active_ids:
                notified.pop(tx_id, None)
                unmark_notified_expiry(tx_id)
        for hour in list(upcoming):
            if hour not in active_hours:
                upcoming.pop(hour, None)
                unmark_upcoming_hour(hour)

        # 3. Split active vs expired (≤24h ago)
        for tx_id, data in all_tx.items():
            if not isinstance(data, dict) or data.get("hidden") or not data.get("end_time"):
                continue
            d = parse_datetime(data["end_time"])
            if not d:
                continue
            if d > now:
                active_list.append((tx_id, data))
            elif d > now - timedelta(hours=24):
                expired_list.append((tx_id, data))
                if not notified.get(tx_id):
                    new_exp = True
                    notified[tx_id] = True
                    mark_notified_expiry(tx_id)

        active_list.sort(key=lambda x: parse_datetime(x[1]["end_time"]))
        expired_list.sort(key=lambda x: parse_datetime(x[1]["end_time"]), reverse=True)

        # 4. Upcoming expirations (≤1h)
        one_hour = now + timedelta(hours=1)
        upcoming_items = [
            (tid,dat) for (tid,dat) in active_list
            if parse_datetime(dat["end_time"]) <= one_hour
               and not upcoming.get(parse_datetime(dat["end_time"]).strftime("%Y-%m-%dT%H"))
        ]
        grouped = group_by_hour(upcoming_items)
        for hour_key, txs in grouped.items():
            if txs and not upcoming.get(hour_key):
                _, ex = txs[0]
                ft = format_date_with_time(parse_datetime(ex["end_time"]))
                body = f"{len(txs)} account{'s' if len(txs)>1 else ''} will expire {ft}"

                # fetch ALL subscribers
                subs = firebase_get(f"OneSignal/{service}") or {}

                # fetch the one photo for upcoming
                photo_up = firebase_get(f"OneSignal/{service}/photo_upcoming") or None

                # remove both photo nodes so only real IDs remain
                subs.pop("photo_upcoming", None)
                subs.pop("photo_expired",  None)

                player_ids = list(subs.keys())
                logger.debug("[%s] upcoming player_ids = %s", service, player_ids)

                send_push_notification("Upcoming Expiration", body, player_ids, big_picture=photo_up)
                upcoming[hour_key] = True
                mark_upcoming_hour(hour_key)

        # 5. Newly expired batch
        if new_exp and expired_list:
            next_info = ""
            nxt = get_next_expiry(active_list)
            if nxt:
                nd = parse_datetime(nxt[1]["end_time"])
                next_info = f" Next expires {format_date_with_time(nd)}."
            body = f"{len(expired_list)} account{'s' if len(expired_list)>1 else ''} have expired.{next_info}"

            subs = firebase_get(f"OneSignal/{service}") or {}
            photo_exp = firebase_get(f"OneSignal/{service}/photo_expired") or None

            subs.pop("photo_upcoming", None)
            subs.pop("photo_expired",  None)

            player_ids = list(subs.keys())
            logger.info("[%s] expired player_ids = %s", service, player_ids)

            send_push_notification("Accounts Expired", body, player_ids, big_picture=photo_exp)

        return active_list, expired_list

    # ─── THE MONITOR LOOP ────────────────────────────────────────────────────────
    def monitor_loop():
        notified, upcoming = load_state()
        while True:
            try:
                txs = firebase_get("transactions")
                filter_transactions(txs, notified, upcoming)
            except Exception as e:
                logger.error("[%s] monitor error: %s", service, e)
            time.sleep(poll_interval)

    return monitor_loop

# ─── FLASK APP ─────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({"status": "OK"})

# ─── START MONITORS AT IMPORT TIME ─────────────────────────────────────────────
DBS = {
    "crunchyroll": "https://get-crunchy-credentials-default-rtdb.firebaseio.com",
    "prime":       "https://get-prime-credentials-default-rtdb.firebaseio.com",
    "netflix":     "https://get-accounts-netflix-prime-default-rtdb.firebaseio.com",
}

for svc, url in DBS.items():
    loop = make_monitor(url, svc, poll_interval=1.0)
    t = threading.Thread(target=loop, daemon=True)
    t.start()

# ─── RUN (only with `python main.py`) ───────────────────────────────────────────
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5550))
    app.run(host="0.0.0.0", port=PORT)



# import os
# import threading
# import time
# from datetime import datetime, timedelta
# from typing import Dict, Tuple, List, Optional

# import requests
# from flask import Flask, jsonify

# # ─── ONE SIGNAL CONFIG ─────────────────────────────────────────────────────────
# ONESIGNAL_APP_ID  = "887203af-f02f-4a68-ad94-0214cdec4d4f"
# ONESIGNAL_API_KEY = "os_v2_app_rbzahl7qf5fgrlmuaikm33cnj6722nlzdy2u5v4wnwxc7hl5xmt7erlubtaxg3lcqrojgpcgu4md5so7p5oxeihqpsmej7bi56lprci"
# ONESIGNAL_URL     = "https://onesignal.com/api/v1/notifications"
# POLL_INTERVAL     = 1  # seconds

# def send_push_notification(title: str, body: str):
    # """
    # Sends a OneSignal push notification to ALL subscribers.
    # """
    # headers = {
        # "Content-Type": "application/json; charset=utf-8",
        # "Authorization": f"Basic {ONESIGNAL_API_KEY}"
    # }
    # payload = {
        # "app_id": ONESIGNAL_APP_ID,
        # "included_segments": ["All"],
        # "headings":   {"en": title},
        # "contents":   {"en": body}
    # }
    # try:
        # resp = requests.post(ONESIGNAL_URL, json=payload, headers=headers)
        # resp.raise_for_status()
    # except Exception as e:
        # print(f"[ERROR] OneSignal push failed: {e}")

# def make_monitor(db_url: str):
    # """
    # Returns a monitor loop function that polls the given Firebase DB URL.
    # """

    # # ─── FIREBASE REST HELPERS ─────────────────────────────────────────────────
    # def firebase_get(path: str) -> dict:
        # url = f"{db_url.rstrip('/')}/{path}.json"
        # resp = requests.get(url)
        # resp.raise_for_status()
        # return resp.json() or {}

    # def firebase_patch(path: str, data: dict):
        # url = f"{db_url.rstrip('/')}/{path}.json"
        # resp = requests.patch(url, json=data)
        # resp.raise_for_status()
        # return resp.json()

    # def firebase_delete(path: str):
        # url = f"{db_url.rstrip('/')}/{path}.json"
        # resp = requests.delete(url)
        # resp.raise_for_status()
        # return resp.json()

    # # ─── STATE‐PERSISTENCE ───────────────────────────────────────────────────────
    # def load_state() -> Tuple[Dict[str, bool], Dict[str, bool]]:
        # base = firebase_get("notification_state")
        # notified = base.get("notified_expiries", {}) or {}
        # upcoming = base.get("upcoming_expiry_notices", {}) or {}
        # return {k: bool(v) for k, v in notified.items()}, {k: bool(v) for k, v in upcoming.items()}

    # def mark_notified_expiry(tx_id: str):
        # firebase_patch("notification_state/notified_expiries", {tx_id: True})

    # def unmark_notified_expiry(tx_id: str):
        # firebase_delete(f"notification_state/notified_expiries/{tx_id}")

    # def mark_upcoming_hour(hour_key: str):
        # firebase_patch("notification_state/upcoming_expiry_notices", {hour_key: True})

    # def unmark_upcoming_hour(hour_key: str):
        # firebase_delete(f"notification_state/upcoming_expiry_notices/{hour_key}")

    # # ─── DATE‐TIME HELPERS ───────────────────────────────────────────────────────
    # def parse_datetime(dt_str: str) -> Optional[datetime]:
        # try:
            # return datetime.fromisoformat(dt_str.replace(" ", "T"))
        # except Exception:
            # return None

    # def format_time_with_ampm(dt: datetime) -> str:
        # return dt.strftime("%-I:%M %p")

    # def format_date_with_time(dt: datetime) -> str:
        # now = datetime.now()
        # today = now.date()
        # tomorrow = (now + timedelta(days=1)).date()
        # if dt.date() == today:
            # return f"Today at {format_time_with_ampm(dt)}"
        # elif dt.date() == tomorrow:
            # return f"Tomorrow at {format_time_with_ampm(dt)}"
        # else:
            # return dt.strftime("%b %-d") + f" at {format_time_with_ampm(dt)}"

    # def group_transactions_by_expiry_hour(
        # transactions: List[Tuple[str, dict]]
    # ) -> Dict[str, List[Tuple[str, dict]]]:
        # grouped: Dict[str, List[Tuple[str, dict]]] = {}
        # for tx_id, tx_data in transactions:
            # end_dt = parse_datetime(tx_data.get("end_time", ""))
            # if not end_dt:
                # continue
            # hour_key = end_dt.strftime("%Y-%m-%dT%H")
            # grouped.setdefault(hour_key, []).append((tx_id, tx_data))
        # return grouped

    # def get_next_expiry_time(
        # transactions: List[Tuple[str, dict]]
    # ) -> Optional[Tuple[str, dict]]:
        # now = datetime.now()
        # future_list = [
            # (tx_id, tx_data)
            # for tx_id, tx_data in transactions
            # if parse_datetime(tx_data.get("end_time", "")) and parse_datetime(tx_data["end_time"]) > now
        # ]
        # if not future_list:
            # return None
        # future_list.sort(key=lambda item: parse_datetime(item[1]["end_time"]))
        # return future_list[0]

    # # ─── CORE FILTER + NOTIFICATION LOGIC ──────────────────────────────────────
    # def filter_transactions(
        # all_transactions: Dict[str, dict],
        # notified_expiries: Dict[str, bool],
        # upcoming_expiry_notices: Dict[str, bool]
    # ) -> Tuple[List[Tuple[str, dict]], List[Tuple[str, dict]]]:
        # now = datetime.now()
        # active_list: List[Tuple[str, dict]] = []
        # expired_list: List[Tuple[str, dict]] = []
        # new_expiration = False

        # # 1a. Determine current active IDs & hours
        # current_active_ids = set()
        # active_hour_keys = set()
        # for tx_id, data in all_transactions.items():
            # if not isinstance(data, dict):
                # continue
            # if data.get("hidden") or not data.get("end_time"):
                # continue
            # end_dt = parse_datetime(data["end_time"])
            # if not end_dt:
                # continue
            # if end_dt > now:
                # current_active_ids.add(tx_id)
                # active_hour_keys.add(end_dt.strftime("%Y-%m-%dT%H"))

        # # 1b. Cleanup notified_expiries
        # for old_id in list(notified_expiries.keys()):
            # if old_id in current_active_ids:
                # del notified_expiries[old_id]
                # unmark_notified_expiry(old_id)

        # # 1c. Cleanup upcoming_expiry_notices
        # for old_hour in list(upcoming_expiry_notices.keys()):
            # if old_hour not in active_hour_keys:
                # del upcoming_expiry_notices[old_hour]
                # unmark_upcoming_hour(old_hour)

        # # 2. Split into active vs expired
        # for tx_id, data in all_transactions.items():
            # if not isinstance(data, dict):
                # continue
            # if data.get("hidden") or not data.get("end_time"):
                # continue
            # end_dt = parse_datetime(data["end_time"])
            # if not end_dt:
                # continue

            # if end_dt > now:
                # active_list.append((tx_id, data))
            # else:
                # if end_dt > now - timedelta(hours=24):
                    # expired_list.append((tx_id, data))
                    # if not notified_expiries.get(tx_id, False):
                        # new_expiration = True
                        # notified_expiries[tx_id] = True
                        # mark_notified_expiry(tx_id)

        # active_list.sort(key=lambda item: parse_datetime(item[1]["end_time"]))
        # expired_list.sort(key=lambda item: parse_datetime(item[1]["end_time"]), reverse=True)

        # # 3. Upcoming expirations
        # one_hour_later = now + timedelta(hours=1)
        # upcoming = [
            # (tx_id, tx_data)
            # for tx_id, tx_data in active_list
            # if parse_datetime(tx_data["end_time"]) <= one_hour_later
               # and not upcoming_expiry_notices.get(parse_datetime(tx_data["end_time"]).strftime("%Y-%m-%dT%H"), False)
        # ]
        # grouped_upcoming = group_transactions_by_expiry_hour(upcoming)

        # for hour_key, tx_list in grouped_upcoming.items():
            # if tx_list and not upcoming_expiry_notices.get(hour_key, False):
                # _, example_data = tx_list[0]
                # expiry_dt = parse_datetime(example_data["end_time"])
                # friendly_time = format_date_with_time(expiry_dt)
                # body = f"{len(tx_list)} account{'s' if len(tx_list) > 1 else ''} will expire {friendly_time}"

                # send_push_notification("Upcoming Expiration", body)
                # upcoming_expiry_notices[hour_key] = True
                # mark_upcoming_hour(hour_key)

        # # 4. Newly expired accounts
        # if new_expiration and expired_list:
            # next_info = ""
            # next_expiry = get_next_expiry_time(active_list)
            # if next_expiry:
                # _, next_data = next_expiry
                # next_dt = parse_datetime(next_data["end_time"])
                # next_info = f" Next account expires {format_date_with_time(next_dt)}."
            # body = f"{len(expired_list)} account{'s' if len(expired_list) > 1 else ''} have expired.{next_info}"
            # send_push_notification("Accounts Expired", body)

        # return active_list, expired_list

    # # ─── CLEAR EXPIRED ACCOUNTS ─────────────────────────────────────────────────
    # def clear_expired_accounts(expired: List[Tuple[str, dict]]):
        # if not expired:
            # return
        # all_data = firebase_get("transactions")
        # for tx_id, tx_data in expired:
            # try:
                # firebase_patch(f"transactions/{tx_id}", {"hidden": True})
                # cred_key = tx_data.get("assign_to")
                # if cred_key:
                    # cred_data = firebase_get(cred_key) or {}
                    # if isinstance(cred_data.get("usage_count"), int):
                        # new_count = max(0, cred_data["usage_count"] - 1)
                        # firebase_patch(cred_key, {"usage_count": new_count})
            # except Exception as e:
                # print(f"[ERROR] Clearing {tx_id}: {e}")

    # # ─── MONITOR LOOP ────────────────────────────────────────────────────────────
    # def monitor_loop():
        # notified_expiries, upcoming_expiry_notices = load_state()
        # while True:
            # try:
                # txs = firebase_get("transactions")
                # active, expired = filter_transactions(txs, notified_expiries, upcoming_expiry_notices)
                # clear_expired_accounts(expired)
            # except Exception as e:
                # print(f"[{db_url}] monitor error: {e}")
            # time.sleep(POLL_INTERVAL)

    # return monitor_loop


# # ─── FLASK APP + THREAD SPAWNING ───────────────────────────────────────────────
# app = Flask(__name__)

# @app.route("/")
# def home():
    # return jsonify({"status": "OK"})


# if __name__ == "__main__":
    # DBS = [
        # "https://testing-6de54-default-rtdb.firebaseio.com",
        # "https://testing-6de54-default-rtdb.firebaseio.com",
        # "https://testing-6de54-default-rtdb.firebaseio.com",
    # ]

    # for url in DBS:
        # loop_fn = make_monitor(url)
        # t = threading.Thread(target=loop_fn, daemon=True)
        # t.start()

    # app.run(host="0.0.0.0", port=5000)
