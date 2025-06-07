import logging
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

logger = logging.getLogger(__name__)
pending_fileid = {}  # Dictionary to track users awaiting file ID extraction

def register_fileid_handlers(client):
    async def fileid_command(client, message):
        user_id = message.from_user.id
        logger.info(f"/fileid command received from user {user_id}")
        pending_fileid[user_id] = True  # Mark that this user is waiting for a photo
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Cancel", callback_data="cancel_fileid")]
        ])
        await message.reply_text("Please send a photo to extract its file ID.", reply_markup=keyboard)

    async def get_file_id(client, message):
        user_id = message.from_user.id
        if user_id not in pending_fileid:
            logger.info(f"Photo received from user {user_id} but not pending; ignoring.")
            return  # Do nothing if the user is not waiting for file ID extraction
        try:
            file_id = message.photo.file_id  # Get the file ID directly from the Photo 
            logger.info(f"Extracted file ID for user {user_id}: {file_id}")
            await message.reply_text(f"File ID is:\n<code>{file_id}</code>", parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error extracting file ID for user {user_id}: {e}")
        pending_fileid.pop(user_id, None)  # Clear the pending state

    async def cancel_fileid_handler(client, callback_query):
        user_id = callback_query.from_user.id
        if user_id in pending_fileid:
            pending_fileid.pop(user_id, None)
            await callback_query.edit_message_text("File ID extraction cancelled.")
        await callback_query.answer("Cancelled", show_alert=True)

    client.add_handler(MessageHandler(fileid_command, filters.command("fileid")))
    client.add_handler(MessageHandler(get_file_id, filters.photo))
    client.add_handler(CallbackQueryHandler(cancel_fileid_handler, filters.regex("^cancel_fileid$")))
    
    logger.info("FileID handlers registered.")