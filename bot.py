#!/usr/bin/env python3
import os
import random
import base64
from io import BytesIO
import subprocess
import tempfile
import requests
from PIL import Image
from pyrogram import Client, filters
from qrcode_styled import QRCodeStyled, ERROR_CORRECT_H
from qrcode_styled.pil.image import PilStyledImage

API_ID    = int(os.getenv("API_ID", "25270711"))
API_HASH  = os.getenv("API_HASH", "6bf18f3d9519a2de12ac1e2e0f5c383e")
BOT_TOKEN = os.getenv("BOT_TOKEN", "7140092976:AAFtmOBKi-mIoVighcf4XXassHimU2CtlR8")

TEMPLATE_URL = "https://i.postimg.cc/4y0GJPXN/QRTemplate.png"
app = Client("styled_qr_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def html_to_png_wkhtmltoimage(html: str, width: int, height: int) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode='w', encoding='utf-8') as html_file:
        html_file.write(html)
        html_path = html_file.name

    png_path = html_path.replace(".html", ".png")

    cmd = [
        "wkhtmltoimage",
        "--width", str(width),
        "--height", str(height),
        "--disable-smart-width",
        html_path,
        png_path
    ]
    subprocess.run(cmd, check=True)

    with open(png_path, "rb") as img_file:
        result = img_file.read()

    os.remove(html_path)
    os.remove(png_path)

    return result

@app.on_message(filters.command("qr") & filters.private)
async def qr_handler(_, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /qr https://example.com", quote=True)

    raw_url = message.command[1].strip()
    data_url = f"{raw_url}?r={random.randint(0,999999)}"
    await message.reply_text("🔧 Generating your QR + template…", quote=True)
    print("[INFO] Data URL:", data_url)

    qr = QRCodeStyled(
        version=None,
        error_correction=ERROR_CORRECT_H,
        border=1,
        box_size=32,
        image_factory=PilStyledImage,
        mask_pattern=None
    )
    buf = BytesIO()
    qr_img = qr.get_image(data=data_url, image=None, optimize=20)
    qr_img.save(buf, format="PNG")
    buf.seek(0)

    b64 = base64.b64encode(buf.getvalue()).decode()
    qr_data_uri = f"data:image/png;base64,{b64}"
    print("[INFO] QR data URI length:", len(qr_data_uri))

    tpl_resp = requests.get(TEMPLATE_URL)
    tpl_resp.raise_for_status()
    tpl_img = Image.open(BytesIO(tpl_resp.content))
    tpl_w, tpl_h = tpl_img.size
    print(f"[INFO] Template size: {tpl_w}×{tpl_h}")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>QR on Template</title>
  <style>
    .container {{
      position: relative;
      width: {tpl_w}px;
      height: {tpl_h}px;
      overflow: hidden;
    }}
    .container img.bg {{
      position: absolute;
      top:0; left:0;
      width:100%; height:100%;
    }}
    .container img.qr {{
      position: absolute;
      left: 50%; top: 50%;
      transform: translate(-50%, -50%);
      width: 30%;
      height: auto;
    }}
  </style>
</head>
<body>
  <div class="container">
    <img class="bg" src="{TEMPLATE_URL}" alt="Template"/>
    <img class="qr" src="{qr_data_uri}" alt="QR Code"/>
  </div>
</body>
</html>"""

    final_png = html_to_png_wkhtmltoimage(html, tpl_w, tpl_h)
    print("[INFO] HTML rendered to PNG using wkhtmltoimage")
    await message.reply_photo(final_png, caption="✅ Here’s your styled QR on the template!")

if __name__ == "__main__":
    app.run()
