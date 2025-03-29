import os.path
import logging

from pyrogram import Client, filters

# Gmail API Imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gmail API scope (readonly access)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_gmail_service():
    """
    Authenticates and returns a Gmail API service instance.
    """
    creds = None
    # token.json stores the user's access and refresh tokens.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    try:
        service = build("gmail", "v1", credentials=creds)
        return service
    except HttpError as error:
        logger.error(f"Gmail API error: {error}")
        return None

def get_latest_email():
    """
    Fetches the latest email from the Gmail inbox.
    Returns a formatted string with email details.
    """
    service = get_gmail_service()
    if not service:
        return "Failed to connect to Gmail."

    try:
        # List the most recent email (maxResults=1) with label "INBOX"
        results = service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=1).execute()
        messages = results.get("messages", [])

        if not messages:
            return "No emails found in your inbox."

        msg_id = messages[0]["id"]
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()

        # Extract email headers
        headers = msg.get("payload", {}).get("headers", [])
        subject = "No subject"
        sender = "Unknown sender"
        for header in headers:
            if header["name"] == "Subject":
                subject = header["value"]
            elif header["name"] == "From":
                sender = header["value"]

        snippet = msg.get("snippet", "No snippet available")
        email_content = f"Subject: {subject}\nFrom: {sender}\n\n{snippet}"
        return email_content

    except HttpError as error:
        logger.error(f"Error fetching email: {error}")
        return "An error occurred while fetching your email."

# Replace the following with your actual Telegram API credentials and bot token.
 api_id = 25270711
 api_hash = "6bf18f3d9519a2de12ac1e2e0f5c383e"
 bot_token = "7140092976:AAFtmOBKi-mIoVighcf4XXassHimU2CtlR8"


# Create a Pyrogram Client instance using the bot token
app = Client("gmail_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

@app.on_message(filters.command("latest"))
def latest_email_handler(client, message):
    """
    When the /latest command is received, fetch and send the latest email.
    """
    message.reply_text("Fetching your latest email...")
    email_text = get_latest_email()
    message.reply_text(email_text)

if __name__ == "__main__":
    app.run()
