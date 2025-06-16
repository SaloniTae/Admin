import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_ID = 25270711
API_HASH = "6bf18f3d9519a2de12ac1e2e0f5c383e"
BOT_TOKEN = "7140092976:AAHsqcw-hfs-Kb0aAgMof631fJ7DL1-NY_w"

app = Client("oor_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Your image path (Termux users: ensure this path exists!)
IMAGE_PATH = "/storage/emulated/0/Pictures/Telegram/IMG_20250616_130429_596.jpg"

# Caption texts
CAPTIONS = [
    "⚡️𝖲𝖾𝖺𝗆𝗅𝖾𝗌𝗌, 𝖺𝗎𝗍𝗈-𝗏𝖾𝗋𝗂𝖿𝗂𝖾𝖽 𝗉𝖺𝗒𝗆𝖾𝗇𝗍𝗌 𝗐𝗂𝗍𝗁 𝗢𝗢𝗥 𝖯𝖠𝖸! 🚀",
    "𝖱𝖾𝖺𝖼𝗁 𝗈𝗎𝗍 𝗍𝗈 @oor_agent for instant access 🔒"
]

# Dummy inline keyboard
keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔘 0 4 : 5 9", callback_data="noop")],
    [InlineKeyboardButton("❌ Cancel", callback_data="noop")]
])

# Track running animations
active_animations = {}

async def animate_caption(message, chat_id):
    try:
        last_caption = ""
        while True:
            for caption in CAPTIONS:
                words = caption.split()
                new_caption = ""
                for word in words:
                    new_caption += word + " "
                    if new_caption.strip() != last_caption:
                        try:
                            await message.edit_caption(new_caption.strip(), reply_markup=keyboard)
                            last_caption = new_caption.strip()
                        except Exception as e:
                            if "MESSAGE_NOT_MODIFIED" not in str(e):
                                print(f"Edit failed: {e}")
                    await asyncio.sleep(0.3)
                await asyncio.sleep(1.5)
    except asyncio.CancelledError:
        print(f"Animation stopped for {chat_id}")

@app.on_message(filters.command("start"))
async def start(client, message):
    chat_id = message.chat.id

    # Cancel previous animation if running
    if chat_id in active_animations:
        active_animations[chat_id].cancel()

    # Send image
    sent = await message.reply_photo(IMAGE_PATH, caption="⚡️𝖲𝖾𝖺𝗆𝗅𝖾𝗌𝗌...", reply_markup=keyboard)

    # Start animation loop
    task = asyncio.create_task(animate_caption(sent, chat_id))
    active_animations[chat_id] = task

app.run()
