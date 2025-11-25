# account_actions.py
# Unified "after payment" actions:
#   • Refresh Password
#   • Get OTP
# Configured per-platform via settings/platform_actions in DB.

import aiohttp
import secrets
import string
from urllib.parse import urlencode
from datetime import datetime, timedelta
import json
import random
import urllib.parse

import aiohttp
import requests

import asyncio
import time
from typing import Callable, Dict, Any, Tuple

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message,
)
from pyrogram.errors import MessageNotModified, FloodWait


# TOTP step (seconds)
STEP = 30

        
class AccountActions:
    """
    Handles:
      • Building per-platform post-payment keyboard (Refresh / OTP / Buy Again)
      • Refresh flow (re-read credential & update caption)
      • OTP flow (confirm + loader + countdown)
    All heavy logic lives here; main file just calls build_keyboard(...)
    and registers handlers via register(app).
    """
    
        
 
    def __init__(
        self,
        *,
        read_node: Callable[[str], "asyncio.Future"],
        patch_node: Callable[[str, Dict[str, Any]], "asyncio.Future"],
        fetch_txn_node: Callable[[str], "asyncio.Future"],
        logger: Any,
        stylize: Callable[[str, Dict[str, str]], str],
        custom_font_map: Dict[str, str],
        gothic_font_map: Dict[str, str],       # ← NEW
        resolve_mode: Callable[[Dict[str, Any], str], str],
    ) -> None:
        self.read_node = read_node
        self.patch_node = patch_node
        self.fetch_txn_node = fetch_txn_node
        self.logger = logger
        self.stylize = stylize
        self.custom_font_map = custom_font_map
        self.gothic_font_map = gothic_font_map   # ← NEW
        self.resolve_mode = resolve_mode
        
        
        
    async def get_category_emoji(self, platform: str) -> str:
        """
        Returns an emoji based on settings/platform_actions/<Platform>.category.
        Defaults to 'entertainment' (🎬) if not set.
        Supported: entertainment 🎬, design 🎨, ai 🚀
        """
        conf = await self._get_actions_conf(platform)
        cat = str(conf.get("category", "")).strip().lower()

        emoji_map = {
            "entertainment": "🎬",
            "design":        "🎨",
            "ai":            "🚀",
        }
        return emoji_map.get(cat, "🎬")
        
        
    async def _get_actions_conf(self, platform: str) -> Dict[str, Any]:
        """
        Reads settings/platform_actions and returns the config for this platform,
        falling back to "default" or {}.
        """
        try:
            actions_root = await self.read_node("settings/platform_actions") or {}
        except Exception:
            actions_root = {}

        if isinstance(actions_root, dict):
            return actions_root.get(platform) or actions_root.get("default") or {}
        return {}
        
        
    def _rand_alias(self, n: int = 4) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(random.choice(alphabet) for _ in range(n))

    async def _ulvis_one_time_short(self, long_url: str) -> str:
        """
        Creates a ONE-TIME ulvis short link (uses=1, private=1).
        Async-safe: runs requests.get in a thread via asyncio.to_thread.
        Retries with small backoff to survive occasional ulvis slowness or alias collisions.
        """
        long_url = (long_url or "").strip()
        if not long_url:
            return ""

        api_url = "https://ulvis.net/API/write/get"

        # 3 attempts (shorter timeout to avoid long stalls when ulvis is slow)
        for attempt in range(1, 4):
            # Generate a new alias for each attempt, in case of collision
            alias = self._rand_alias(4)

            params = {
                "url": long_url,
                "type": "json",
                "uses": "1",       # ✅ one-time click
                "private": "1",    # ✅ unlisted
                "custom": alias,   # ✅ custom alias
            }

            def _do_request() -> dict:
                # connect timeout, read timeout
                r = requests.get(
                    api_url,
                    params=params,
                    timeout=(4, 10),
                    headers={"User-Agent": "oorbots/1.0"},
                )
                r.raise_for_status() # Raise exception for 4xx/5xx status codes
                return r.json()

            try:
                payload = await asyncio.to_thread(_do_request)
            except requests.exceptions.ReadTimeout as e:
                if self.logger:
                    self.logger.warning(f"[Invite] ulvis read timeout (attempt {attempt}/3): {e!r}")
                # Continue to next iteration after logging/backoff
                # We need to explicitly continue here if an exception occurs
                pass
            except requests.exceptions.RequestException as e:
                if self.logger:
                    self.logger.warning(f"[Invite] ulvis request failed (attempt {attempt}/3): {e!r}")
                # Continue to next iteration after logging/backoff
                pass
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"[Invite] ulvis unexpected error (attempt {attempt}/3): {e!r}")
                # Continue to next iteration after logging/backoff
                pass
            else:
                # This block runs ONLY if no exception was raised in the try block
                if payload.get("success") in (True, 1, "1"):
                    data = payload.get("data") or {}
                    short_url = (data.get("url") or "").strip()
                    if short_url:
                        return short_url

                # Collision or API-level error (status 200, but success=False)
                if self.logger:
                    self.logger.info(f"[Invite] ulvis not success (attempt {attempt}/3): {payload!r}")

            # small backoff/jitter before retry
            await asyncio.sleep(0.35 * attempt)

        return ""

    async def _isgd_short(self, long_url: str) -> str:
        """Fallback shortener when ulvis is slow/unavailable.

        is.gd provides a simple JSON API without needing authentication. We
        keep this lean and synchronous inside a thread (just like ulvis) to
        avoid blocking the event loop.
        """
        long_url = (long_url or "").strip()
        if not long_url:
            return ""

        api_url = "https://is.gd/create.php"
        params = {
            "format": "json",
            "url": long_url,
            "logstats": "0",
        }

        def _do_request() -> dict:
            r = requests.get(api_url, params=params, timeout=(4, 10))
            r.raise_for_status()
            return r.json()

        try:
            payload = await asyncio.to_thread(_do_request)
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[Invite] is.gd shortener failed: {e!r}")
            return ""

        short_url = (payload.get("shorturl") or "").strip()
        if short_url:
            return short_url

        if self.logger:
            self.logger.info(f"[Invite] is.gd returned no short url: {payload!r}")
        return ""


    async def _get_or_create_txn_invite_link(self, txn_id: str, platform: str, long_invite: str) -> str:
        """
        Ensures THIS transaction has a unique one-time invite link.
        - If txn already has invite_link_short → reuse it (stable button/caption)
        - Else mint new ulvis one-time link and store in txn
        Returns: short link if possible else the original long_invite.
        """
        long_invite = (long_invite or "").strip()
        if not long_invite:
            return ""

        # If txn already has one, reuse (no double-mint)
        parent_path, txn = await self.fetch_txn_node(txn_id)
        if isinstance(txn, dict):
            existing = (txn.get("invite_link_short") or "").strip()
            if existing:
                return existing

        # First preference: ulvis (one-time link). If it times out/fails, fall
        # back to is.gd so the user still gets a usable short link quickly.
        short = await self._ulvis_one_time_short(long_invite)
        if not short:
            short = await self._isgd_short(long_invite)
        if not short:
            return long_invite

        # Store on txn so refresh/other flows show same link for that order
        if parent_path:
            try:
                await self.patch_node(f"{parent_path}/{txn_id}", {
                    "invite_link_long": long_invite,
                    "invite_link_short": short,
                    "invite_one_time": True,
                })
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"[Invite] failed to store invite_link_short: {e!r}")

        return short

        
                

    # ------------------------------------------------------------------ #
    #  A) PUBLIC: keyboard builder (used from do_approve_flow_immediate)
    # ------------------------------------------------------------------ #

    async def build_keyboard(
        self,
        slot_node: dict,
        txn_id: str,
        cred: dict | None = None
    ) -> InlineKeyboardMarkup:
        """
        Build the action keyboard for a transaction, based ONLY on:
          settings/platform_actions and slot_node["platform"]

        Layout (dynamic):
          Row 1: [Refresh Password] [Get OTP]    (if enabled)
          Row 2: [Join Now]                      (if invite_enabled & invite_link present)
          Row 3: [Buy Again]
        """
        # 1) Determine platform name from slot
        platform = (slot_node.get("platform") or "").strip()

        # 2) Load per-platform action config
        conf = await self._get_actions_conf(platform)

        refresh_enabled = bool(conf.get("refresh_enabled", True))
        otp_enabled     = bool(conf.get("otp_enabled", False))
        invite_enabled  = bool(conf.get("invite_enabled", False))

        first_row: list[InlineKeyboardButton] = []
        if refresh_enabled:
            first_row.append(
                InlineKeyboardButton(
                    "𝖱𝖾𝖿𝗋𝖾𝗌𝗁 𝖯𝖺𝗌𝗌𝗐𝗈𝗋𝖽",
                    callback_data=f"refresh_{txn_id}",
                )
            )
        if otp_enabled:
            first_row.append(
                InlineKeyboardButton(
                    "𝖦𝖾𝗍 𝖮𝖳𝖯",
                    callback_data=f"otp_{txn_id}",
                )
            )

        rows: list[list[InlineKeyboardButton]] = []
        if first_row:
            rows.append(first_row)

        # 3) Join Now button for invite mode
        invite_long = ""
        if cred and isinstance(cred, dict):
            invite_long = (cred.get("invite_link") or "").strip()

        if invite_enabled and invite_long:
            invite_effective = await self._get_or_create_txn_invite_link(txn_id, platform, invite_long)
            if invite_effective:
                rows.append([
                    InlineKeyboardButton("𝖩𝗈𝗂𝗇 𝖭𝗈𝗐", url=invite_effective)
                ])

        # 4) Fixed Buy Again button
        rows.append(
            [InlineKeyboardButton("𝖡𝗎𝗒 𝖠𝗀𝖺𝗂𝗇", callback_data="start")]
        )

        return InlineKeyboardMarkup(rows)


    # ------------------------------------------------------------------ #
    #  B) REFRESH PASSWORD HANDLER
    # ------------------------------------------------------------------ #
    
    async def get_quote_for_slot(self, slot_node: dict) -> str:
        """
        Returns the quote line under the account details, based on
        settings/platform_actions and the slot's platform.

        Rules:
          • invite_enabled → invite quote (highest priority)
          • Only Refresh enabled → refresh quote
          • Only OTP enabled     → OTP quote
          • Both enabled         → combined quote
        """
        platform = (slot_node.get("platform") or "").strip()

        conf = await self._get_actions_conf(platform)

        refresh_enabled = bool(conf.get("refresh_enabled", True))
        otp_enabled     = bool(conf.get("otp_enabled", False))
        invite_enabled  = bool(conf.get("invite_enabled", False))

        # Invite mode: override with invite quote
        if invite_enabled:
          p = platform or "the platform"
          return (
              f'Tap the link to copy and share with a friend, or "Join Now" to enter {p} directly!'
          )

        # Only Refresh
        if refresh_enabled and not otp_enabled:
            return (
                "𝖨𝖿 𝗅𝗈𝗀𝗀𝖾𝖽 𝗈𝗎𝗍, 𝖳𝖺𝗉 “𝖱𝖾𝖿𝗋𝖾𝗌𝗁” 𝗍𝗈 𝗀𝖾𝗍 𝗒𝗈𝗎𝗋 𝗇𝖾𝗐 𝗉𝖺𝗌𝗌𝗐𝗈𝗋𝖽!"
            )

        # Only OTP
        if otp_enabled and not refresh_enabled:
            return (
                "𝖳𝗋𝗈𝗎𝖻𝗅𝖾 𝗅𝗈𝗀𝗀𝗂𝗇𝗀 𝗂𝗇? 𝖳𝖺𝗉 “𝖦𝖾𝗍 𝖮𝖳𝖯” 𝗍𝗈 𝗀𝗋𝖺𝖻 𝗈𝗇𝖾 𝗂𝗇𝗌𝗍𝖺𝗇𝗍𝗅𝗒!"
            )

        # Both Refresh + OTP
        if refresh_enabled and otp_enabled:
            return (
                "𝖨𝖿 𝗅𝗈𝗀𝗀𝖾𝖽 𝗈𝗎𝗍, 𝖴𝗌𝖾 𝖱𝖾𝖿𝗋𝖾𝗌𝗁 𝖿𝗈𝗋 𝖺 𝗇𝖾𝗐 𝗉𝖺𝗌𝗌𝗐𝗈𝗋𝖽 "
                "𝗈𝗋 𝖦𝖾𝗍 𝖮𝖳𝖯 𝖿𝗈𝗋 𝖺 𝗇𝖾𝗐 𝖼𝗈𝖽𝖾!"
            )

        # Neither (edge / misconfig)
        return ""
        
        
    async def build_caption_for_approve(self, slot_node: dict, headline: str, ui: dict, cred: dict, txn_id: str | None = None) -> str:
        """
        Build the main caption for approve_flow, supporting two modes:

          • Normal (email/password)
          • Invite mode (invite_enabled + invite_link)

        Uses:
          • headline (already computed in do_approve_flow_immediate)
          • ui_config/approve_flow.account_format for normal mode
          • special Invite Link line for invite mode
          • get_quote_for_slot(...) for the quote line
        """
        platform = (slot_node.get("platform") or "").strip()
        conf = await self._get_actions_conf(platform)

        invite_enabled = bool(conf.get("invite_enabled", False))
        invite_link = (cred or {}).get("invite_link", "").strip()

        # Invite mode
        if invite_enabled and invite_link:
            effective = invite_link
            if txn_id:
                effective = await self._get_or_create_txn_invite_link(txn_id, platform, invite_link)

            body = f"✦ 𝖨𝗇𝗏𝗂𝗍𝖾 𝖫𝗂𝗇𝗄 : `{effective}`"
            quote = await self.get_quote_for_slot(slot_node)
            return f"{headline}\n\n{body}\n\n{quote}"

        # Normal email/password mode
        acct_fmt = ui.get(
            "account_format",
            "Email: {email}\nPassword: {password}",
        ).replace("\\n", "\n")

        email = cred.get("email", "")
        password = cred.get("password", "")

        quote = await self.get_quote_for_slot(slot_node)

        return (
            f"{headline}\n\n"
            f"{acct_fmt.format(email=email, password=password)}\n\n"
            f"{quote}"
        )

            

    async def _handle_refresh(self, client: Client, callback_query: CallbackQuery):
        order_id = callback_query.data.split("_", 1)[1]

        parent_path, txn = await self.fetch_txn_node(order_id)
        if not parent_path:
            return await callback_query.answer("Invalid request", show_alert=True)
        if not txn or txn.get("user_id") != callback_query.from_user.id:
            return await callback_query.answer("Invalid request", show_alert=True)

        # Expiry check (Asia/Kolkata)
        import pytz
        from datetime import datetime, timedelta

        tz = pytz.timezone("Asia/Kolkata")
        try:
            end_time_naive = datetime.strptime(
                txn["end_time"], "%Y-%m-%d %H:%M:%S"
            )
            end_time = tz.localize(end_time_naive)
        except Exception:
            end_time = tz.localize(datetime.now(tz) - timedelta(seconds=1))

        if datetime.now(tz) > end_time:
            return await callback_query.answer(
                "🚫 𝖸𝗈𝗎𝗋 𝖠𝖼𝖼𝖾𝗌𝗌 𝖧𝖺𝗌 𝖤𝗑𝗉𝗂𝗋𝖾𝖽",
                show_alert=True,
            )

        cred_key = txn.get("assign_to")
        if not cred_key:
            return await callback_query.answer(
                "No credential assigned.", show_alert=True
            )

        cred = await self.read_node(cred_key)
        if not isinstance(cred, dict):
            return await callback_query.answer(
                "Credential not found.", show_alert=True
            )

        new_email = cred.get("email", "")
        new_password = cred.get("password", "")

        last_email = txn.get("last_email", "")
        last_password = txn.get("last_password", "")

        if new_email == last_email and new_password == last_password:
            return await callback_query.answer(
                "😊 𝖭𝗈 𝖢𝗁𝖺𝗇𝗀𝖾 𝖨𝗇 𝖢𝗋𝖾𝖽𝖾𝗇𝗍𝗂𝖺𝗅𝗌",
                show_alert=True,
            )

        # Headline: same label-mode logic as approve_flow
        ui_flags = (await self.read_node("settings/ui_flags")) or {}
        slot_id = txn.get("slot_id")
        slot_node = await self.read_node(f"settings/slots/{slot_id}") if slot_id else {}

        mode = self.resolve_mode(ui_flags, "approve_flow")
        platform = (slot_node.get("platform") or "").strip() if slot_node else ""
        slot_name = (
            (slot_node.get("name") or (slot_id or "Account")).strip()
            if slot_node
            else (slot_id or "Account")
        )

        if mode == "platform" and platform:
            cat_emoji = await self.get_category_emoji(platform)
            headline = f"{cat_emoji} {self.stylize(platform, self.custom_font_map)} 𝗔𝗰𝗰𝗼𝘂𝗻𝘁"
        else:
            headline = slot_name

        ui = await self.read_node("ui_config/approve_flow") or {}
        acct_fmt = ui.get(
            "account_format", "Email: {email}\nPassword: {password}"
        ).replace("\\n", "\n")

        # NEW: quote based on platform actions (Refresh / OTP / both)
        slot_node_for_kb = slot_node if isinstance(slot_node, dict) else {}
        quote_text = await self.get_quote_for_slot(slot_node_for_kb)

        updated_caption = (
            f"{headline}\n\n"
            f"{acct_fmt.format(email=new_email, password=new_password)}\n\n"
            f"{quote_text}"
        )

        # Rebuild buttons for this platform/slot (respect per-platform config)
        kb = await self.build_keyboard(slot_node_for_kb, order_id)

        try:
            await callback_query.message.edit_caption(
                caption=updated_caption,
                reply_markup=kb,
            )
        except Exception:
            # Fallback: ignore edit failure quietly
            pass

        # Persist new last_email / last_password
        await self.patch_node(
            f"{parent_path}/{order_id}",
            {"last_email": new_email, "last_password": new_password},
        )

        await callback_query.answer(
            "𝖢𝗋𝖾𝖽𝖾𝗇𝗍𝗂𝖺𝗅𝗌 𝖱𝖾𝖿𝗋𝖾𝗌𝗁𝖾𝖽 ✅",
            show_alert=True,
        )

    # ------------------------------------------------------------------ #
    #  C) OTP GENERATION + FLOW
    # ------------------------------------------------------------------ #

    async def _generate_totp(self, secret: str) -> str:
        """
        Uses oathtool to generate TOTP for the given secret.
        """
        proc = await asyncio.create_subprocess_exec(
            "oathtool",
            "--totp",
            "-b",
            secret,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()

    async def _execute_otp_sequence(
        self,
        client: Client,
        message: Message,
        secret: str,
        parent_path: str,
        order_id: str,
    ):
        """
        Handles:
          • OTP loader animation
          • Wait until next window
          • Show OTP + countdown
          • Mark otp_delivered in DB after showing
        """
        now = int(time.time())
        rem = STEP - (now % STEP)

        phases = [
            ("🚀 𝘍𝘦𝘵𝘤𝘩𝘪𝘯𝘨 𝙊𝙏𝙋", ["●○○○○", "●●○○○", "●●●○○", "●●●●○", "●●●●●"]),
            ("⚙️ 𝘗𝘳𝘰𝘤𝘦𝘴𝘴𝘪𝘯𝘨 𝙊𝙏𝙋", ["●○○○○", "●●○○○", "●●●○○", "●●●●○", "●●●●●"]),
        ]
        total_frames = sum(len(seq) for _, seq in phases)
        delay = rem / total_frames if rem > 0 else 0

        # 1) initial loader
        label0, seq0 = phases[0]
        msg = await message.reply(f"{label0} {seq0[0]}")
        start = time.time()

        # 2) animate until remainder time
        for label, seq in phases:
            for frame in seq:
                if time.time() - start >= rem:
                    break
                text = f"{label} {frame}"
                try:
                    await client.edit_message_text(msg.chat.id, msg.id, text)
                except MessageNotModified:
                    pass
                except Exception:
                    return
                await asyncio.sleep(delay)
            else:
                continue
            break

        elapsed = time.time() - start
        if elapsed < rem:
            await asyncio.sleep(rem - elapsed)

        # 3) generate & show OTP for current window
        code = await self._generate_totp(secret)
        window_id = int(time.time()) // STEP
        ttl = STEP

        otp_text = f"🔑 𝖸𝗈𝗎𝗋 𝖮𝖳𝖯 𝗂𝗌: `{code}`"
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"⏱ expires in {ttl}s", callback_data="ignore"
                    )
                ]
            ]
        )
        try:
            await client.edit_message_text(
                msg.chat.id, msg.id, otp_text, reply_markup=markup
            )
        except MessageNotModified:
            pass

        # 4) mark delivered
        await self.patch_node(
            f"{parent_path}/{order_id}", {"otp_delivered": True}
        )

        # 5) countdown updater (background)
        async def updater(message_obj: Message, initial_code: str, start_win: int):
            backoff_until = 0
            expired = False

            while True:
                await asyncio.sleep(1)
                now2 = int(time.time())
                cur_win = now2 // STEP
                rem2 = STEP - (now2 % STEP)

                if not expired and cur_win != start_win:
                    expired = True
                    expiry_text = (
                        f"🔑 𝗬𝗼𝘂𝗿 𝗢𝗧𝗣 𝘄𝗮𝘀: `{initial_code}`\n\n"
                        "𝖨𝖿 𝗒𝗈𝗎 𝗌𝗍𝗂𝗅𝗅 𝖼𝖺𝗇’𝗍 𝗅𝗈𝗀 𝗂𝗇, 𝗉𝗅𝖾𝖺𝗌𝖾 𝗋𝖾𝖺𝖼𝗁 𝗈𝗎𝗍 𝗍𝗈 𝗌𝗎𝗉𝗉𝗈𝗋𝗍."
                    )
                    help_btn = InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "🆘 Help",
                                    url="https://t.me/oor_agent",
                                )
                            ]
                        ]
                    )
                    try:
                        await message_obj.edit_text(
                            expiry_text, reply_markup=help_btn
                        )
                    except Exception:
                        pass
                    break

                if time.time() < backoff_until:
                    continue

                new_kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                f"⏱ expires in {rem2}s",
                                callback_data="ignore",
                            )
                        ]
                    ]
                )
                try:
                    await message_obj.edit_reply_markup(new_kb)
                except FloodWait as e:
                    backoff_until = time.time() + e.value
                except MessageNotModified:
                    pass
                except Exception:
                    break

        # run updater in background
        client.loop.create_task(updater(msg, code, window_id))

    # ------------------------------------------------------------------ #
    #  D) OTP CALLBACK HANDLERS
    # ------------------------------------------------------------------ #

    async def _otp_initial_handler(self, client: Client, cq: CallbackQuery):
        """
        First click on "Get OTP" button.
        Checks txn, ensures not already delivered,
        then asks user "Yes / Cancel".
        """
        order_id = cq.data.split("_", 1)[1]

        parent_path, txn = await self.fetch_txn_node(order_id)
        if not parent_path or not txn or txn.get("user_id") != cq.from_user.id:
            return await cq.answer("Invalid request", show_alert=True)

        if txn.get("otp_delivered"):
            return await cq.answer(
                "✅ 𝗢𝗧𝗣 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗱𝗲𝗹𝗶𝘃𝗲𝗿𝗲𝗱!",
                show_alert=True,
            )

        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Yes", callback_data=f"otp_confirm_{order_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Cancel", callback_data=f"otp_cancel_{order_id}"
                    )
                ],
            ]
        )

        # Platform name (for prompt), gothic-styled
        platform = (txn.get("platform") or "").strip()
        if not platform:
            slot_id = txn.get("slot_id")
            slot_node = await self.read_node(f"settings/slots/{slot_id}") if slot_id else {}
            if isinstance(slot_node, dict):
                platform = (slot_node.get("platform") or "").strip()

        if platform:
            styled_platform = self.stylize(platform, self.gothic_font_map)
        else:
            styled_platform = "𝖯𝗅𝖺𝗍𝖿𝗈𝗋𝗆"

        prompt_text = (
            f"⚠️ 𝖤𝗇𝗍𝖾𝗋 𝖾𝗆𝖺𝗂𝗅 & 𝗉𝖺𝗌𝗌𝗐𝗈𝗋𝖽 𝗈𝗇 {styled_platform} "
            f"𝖻𝖾𝖿𝗈𝗋𝖾 𝗋𝖾𝗊𝗎𝖾𝗌𝗍𝗂𝗇𝗀 𝖮𝖳𝖯.\n\n"
            f"𝗣𝗿𝗼𝗰𝗲𝗲𝗱 𝗻𝗼𝘄?"
        )

        await cq.answer()  # stop spinner
        await client.send_message(
            chat_id=cq.message.chat.id,
            text=prompt_text,
            reply_markup=kb,
        )

    async def _otp_confirmation_handler(self, client: Client, cq: CallbackQuery):
        """
        Second step: Yes / Cancel prompt for OTP.
        On Yes → generates OTP + loader.
        """
        action, order_id = cq.data.split("_", 2)[1:]

        if action == "cancel":
            await cq.answer("Request cancelled.", show_alert=False)
            try:
                await cq.message.delete()
            except Exception:
                pass
            return

        # action == confirm
        await cq.answer()
        try:
            await cq.message.delete()
        except Exception:
            pass

        parent_path, txn = await self.fetch_txn_node(order_id)
        if not parent_path or not txn or txn.get("user_id") != cq.from_user.id:
            return await client.send_message(
                cq.message.chat.id, "Invalid request"
            )

        if txn.get("otp_delivered"):
            return await client.send_message(
                cq.message.chat.id,
                "🔒 𝗢𝗧𝗣 𝖺𝗅𝗋𝖾𝖺𝖽𝗒 𝖽𝖾𝗅𝗂𝗏𝖾𝗋𝖾𝖽.",
            )

        cred_key = txn.get("assign_to")
        cred = await self.read_node(cred_key) if cred_key else {}
        secret = cred.get("secret")
        if not secret:
            return await client.send_message(
                cq.message.chat.id, "No OTP secret configured."
            )

        await self._execute_otp_sequence(
            client, cq.message, secret, parent_path, order_id
        )

    async def _ignore_handler(self, _client: Client, cq: CallbackQuery):
        """
        Ignore clicks on the countdown button.
        """
        await cq.answer()

    # ------------------------------------------------------------------ #
    #  E) REGISTRATION
    # ------------------------------------------------------------------ #

    def register(self, app: Client) -> None:
        """
        Wire all callback handlers to the app.
        Call this once in main after creating the instance.
        """
        app.on_callback_query(filters.regex(r"^refresh_(.+)$"))(
            self._handle_refresh
        )
        app.on_callback_query(
            filters.regex(r"^otp_(?!confirm_|cancel_)(.+)$"), group=1
        )(self._otp_initial_handler)
        app.on_callback_query(
            filters.regex(r"^otp_(confirm|cancel)_(.+)$"), group=2
        )(self._otp_confirmation_handler)
        app.on_callback_query(filters.regex(r"^ignore$"), group=3)(
            self._ignore_handler
        )

        if self.logger:
            self.logger.info("AccountActions handlers registered successfully!")