import sys
from pyrogram import Client, filters

# -------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------
# Get these from https://my.telegram.org
API_ID = "25270711"
API_HASH = "6bf18f3d9519a2de12ac1e2e0f5c383e"
BOT_TOKEN = "7140092976:AAEbBq9_XJYuAYjr58zYKbywMxqozEEKNT0"
# -------------------------------------------------------

print("Initializing Bot...")

# In-memory session is safer for compiled bots so it doesn't leave a 
# .session file explicitly unless you want it to save state.
app = Client(
    "my_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True # Set to True if you don't want a .session file created on customer PC
)

# --- Command 1: /start ---
@app.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text(
        "**Hello!** I am a compiled Pyrogram bot.\n"
        "I am running inside a standalone executable!"
    )
    print(f"User {message.from_user.first_name} used /start")

# --- Command 2: /help ---
@app.on_message(filters.command("help"))
async def help_command(client, message):
    await message.reply_text(
        "**Available Commands:**\n"
        "/start - Check if bot is alive\n"
        "/help - Show this menu\n"
        "/ping - Check latency"
    )

# --- Command 3: /ping ---
@app.on_message(filters.command("ping"))
async def ping_command(client, message):
    await message.reply_text("Pong! 🏓")

if __name__ == "__main__":
    print("Bot is running... Press Ctrl+C to stop.")
    try:
        app.run()
    except Exception as e:
        print(f"Error: {e}")
        input("Press Enter to exit...") # Keeps window open if it crashes
