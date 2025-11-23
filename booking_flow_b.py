# booking_flow_b.py
# ---------------------------------------------------------------------
# Flow-B (platform-first) module:
#  • First screen: platform picker → ui_config.flow_b.picker.{photo_url, caption}
#  • After picking a platform: ui_config.flow_b.platform_ui[Platform].{photo_url, caption}
#  • Plan buttons: show enabled slots that belong to that platform (NO amounts)
#  • Label for each plan uses your global resolve_slot_label_for_scope_global(...) if available,
#    otherwise a safe fallback honoring settings.ui_flags.slot_booking_label_mode.
#  • Sending uses your message_queue if passed, otherwise awaits client methods.
# ---------------------------------------------------------------------

from __future__ import annotations
import asyncio
from typing import Callable, Dict, Optional, Any

from pyrogram import filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ---- Resolver shim ---------------------------------------------------
# We prefer the global resolver that you already have in main:
# def resolve_slot_label_for_scope_global(slot_info, slot_id, ui_flags, scope) -> (label_text, used_platform_bool)
_RESOLVE_FN = globals().get("resolve_slot_label_for_scope_global")

if not callable(_RESOLVE_FN):
    # Fallback that respects settings.ui_flags.slot_booking_label_mode ("name"|"platform")
    def _fallback_resolve_slot_label_for_scope_global(slot_node, slot_id, ui_flags, scope: str):
        mode_key = "approve_flow_label_mode" if scope == "approve_flow" else "slot_booking_label_mode"
        mode = (ui_flags.get(mode_key) or "name").strip().lower()

        name     = (slot_node.get("name") or str(slot_id)).strip()
        platform = (slot_node.get("platform") or "").strip() or name

        if mode == "platform":
            # No stylize here (your main already stylizes platform if needed)
            return platform, True
        return name, False

    _RESOLVE_FN = _fallback_resolve_slot_label_for_scope_global
# ---------------------------------------------------------------------


def _slugify_platform(p: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in (p or "")).strip("_") or "p"


class BookingFlowB:
    """
    Platform-first (Flow-B) module. Does not auto-register handlers by default.
    Wire handlers using .register(app) or by calling:
        app.on_callback_query(filters.regex(r"^choose_platform_(.+)$"))(booking_b.choose_platform)
    """

    def __init__(
        self,
        *,
        read_node: Callable[[str], "asyncio.Future"],
        read_ui_config: Callable[[str], "asyncio.Future"],
        message_queue: Any,
        user_slot_choice: Dict[int, str],
        confirm_slot_action: Callable[..., "asyncio.Future"],
        logger: Any = None,
    ) -> None:
        self.read_node = read_node
        self.read_ui_config = read_ui_config
        self.message_queue = message_queue
        self.user_slot_choice = user_slot_choice
        self.confirm_slot_action = confirm_slot_action
        self.logger = logger

        # Optional: remember chosen platform per user (not required for flow)
        self.user_platform_choice: Dict[int, str] = {}

    # Optional one-call binder (use if you like)
    def register(self, app) -> None:
        app.on_callback_query(filters.regex(r"^book$"))(self.book_entry)
        app.on_callback_query(filters.regex(r"^choose_platform_(.+)$"))(self.choose_platform)

    # ---------- Public entry points ----------
    async def book_entry(self, client, callback_query: CallbackQuery):
        # entry point if you want a dedicated "book" callback
        try:
            await callback_query.answer()
        except Exception:
            pass
        await self._render_platform_picker(client, callback_query)

    async def start_platform_picker(self, client, callback_query: CallbackQuery) -> None:
        # called from your router when settings.ui_flags.booking_flow_mode == "platform_first"
        await self._render_platform_picker(client, callback_query)

    # ---------- Handlers ----------
    async def choose_platform(self, client, callback_query: CallbackQuery):
        """
        After user taps a platform, show that platform's header (image/caption) from ui_config.flow_b.platform_ui
        and present a list of enabled plans (slots) that belong to this platform.

        • Buttons do NOT show amounts.
        • Plan labels are resolved via your global resolver (or fallback) using scope="slot_booking".
        """
        try:
            await callback_query.answer()
        except Exception:
            pass

        user_id = callback_query.from_user.id
        plat_slug = callback_query.data.split("_", 2)[2]  # choose_platform_<slug>

        # Load settings (logic only) and Flow-B UI (media only)
        settings = await self.read_node("settings")
        slots    = settings.get("slots", {}) if isinstance(settings, dict) else {}
        ui_flags = settings.get("ui_flags", {}) if isinstance(settings, dict) else {}

        ui_flowb = (await self.read_ui_config("flow_b")) or {}
        platform_ui = ui_flowb.get("platform_ui", {}) if isinstance(ui_flowb, dict) else {}

        # Resolve slug→platform name by scanning enabled slots
        slug_to_name: Dict[str, str] = {}
        for s in (slots or {}).values():
            if not isinstance(s, dict) or not s.get("enabled", False):
                continue
            p = (s.get("platform") or "").strip()
            if p:
                slug_to_name[_slugify_platform(p)] = p

        platform_name = slug_to_name.get(plat_slug)
        if not platform_name:
            return await callback_query.answer("Invalid platform.", show_alert=True)

        self.user_platform_choice[user_id] = platform_name

        # Per-platform header strictly from ui_config.flow_b.platform_ui
        p_ui = platform_ui.get(platform_name, {}) if isinstance(platform_ui, dict) else {}
        photo_url = p_ui.get("photo_url", "")
        caption   = (p_ui.get("caption", f"Available plans for {platform_name}") or "").replace("\\n", "\n")

        # Build plan list for the chosen platform (enabled only), NO amounts
        rows = []
        for slot_id, s in (slots or {}).items():
            if not isinstance(s, dict) or not s.get("enabled", False):
                continue
            if (s.get("platform") or "").strip() != platform_name:
                continue

            label_text, _ = _RESOLVE_FN(s, slot_id, ui_flags, scope="slot_booking")
            rows.append([InlineKeyboardButton(label_text, callback_data=f"choose_slot_{slot_id}")])

        if not rows:
            rows = [[InlineKeyboardButton("No Plans Available", callback_data="noop")]]

        await self._send_photo_or_text(
            client=client,
            chat_id=callback_query.message.chat.id,
            photo_url=photo_url,
            caption=caption,
            kb=InlineKeyboardMarkup(rows),
        )

    # ---------- Internals ----------
    async def _render_platform_picker(self, client, callback_query: CallbackQuery):
        """
        First screen for Flow-B:
          • Header uses ui_config.flow_b.picker.{photo_url, caption} (one global image/caption)
          • Buttons list unique enabled platforms from settings.slots
        """
        try:
            await callback_query.answer()
        except Exception:
            pass

        settings = await self.read_node("settings")
        slots    = settings.get("slots", {}) if isinstance(settings, dict) else {}

        # Unique, enabled platforms present in slots
        present = {
            (s.get("platform") or "").strip()
            for s in (slots or {}).values()
            if isinstance(s, dict) and s.get("enabled", False) and (s.get("platform") or "").strip()
        }

        # Global picker header from ui_config.flow_b.picker
        ui_flowb = (await self.read_ui_config("flow_b")) or {}
        picker   = ui_flowb.get("picker", {}) if isinstance(ui_flowb, dict) else {}
        photo_url = picker.get("photo_url", "")
        caption   = (picker.get("caption", "🎬 Choose your platform") or "").replace("\\n", "\n")

        # Platform buttons (no amounts)
        buttons = [InlineKeyboardButton(p, callback_data=f"choose_platform_{_slugify_platform(p)}")
                   for p in sorted(present) if p]
        rows = [[b] for b in buttons] if buttons else [[InlineKeyboardButton("No Platforms Available", callback_data="noop")]]

        await self._send_photo_or_text(
            client=client,
            chat_id=callback_query.message.chat.id,
            photo_url=photo_url,
            caption=caption,
            kb=InlineKeyboardMarkup(rows),
        )

    async def _send_photo_or_text(self, *, client, chat_id: int, photo_url: str, caption: str, kb: InlineKeyboardMarkup):
        """
        Uses your message_queue if given; otherwise sends immediately.
        """
        if self.message_queue is not None:
            if photo_url:
                self.message_queue.put_nowait((
                    client.send_photo,
                    [chat_id],
                    {"photo": photo_url, "caption": caption, "reply_markup": kb}
                ))
            else:
                self.message_queue.put_nowait((
                    client.send_message,
                    [chat_id],
                    {"text": caption, "reply_markup": kb}
                ))
            return

        if photo_url:
            await client.send_photo(chat_id=chat_id, photo=photo_url, caption=caption, reply_markup=kb)
        else:
            await client.send_message(chat_id=chat_id, text=caption, reply_markup=kb)