#!/usr/bin/env python3
import os
import random
import base64
import time
from io import BytesIO

import requests
from PIL import Image, ImageOps, ImageDraw
from pyrogram import Client, filters
from qrcode_styled import QRCodeStyled, ERROR_CORRECT_H
from qrcode_styled.pil.image import PilStyledImage

# ─── CONFIG ───────────────────────────────────────────────────────────────────
API_ID           = int(os.getenv("API_ID",    "25270711"))
API_HASH         = os.getenv("API_HASH",      "6bf18f3d9519a2de12ac1e2e0f5c383e")
BOT_TOKEN        = os.getenv("BOT_TOKEN",     "7140092976:AAFtmOBKi-mIoVighcf4XXassHimU2CtlR8")
INTERNAL_API_KEY = "OTTONRENT"  # your hard-coded key for html2image

TEMPLATE_URL = "https://res.cloudinary.com/djzfoukhz/image/upload/v1746200521/QRTemplate_znsfef.png"
LOGO_URL     = (
    "https://res.cloudinary.com/djzfoukhz/image/upload/"
    "v1746022425/Untitled_design_20250430_011630_0000_icacxu.png"
)

# ─── HTML2Image via your own API (returns a .png URL) ─────────────────────────
def html_to_jpg_convertapi(html: str, timings: dict) -> str:
    """
    1) POST to your /convert endpoint → get JSON with .bin URL
    2) Append .png and return that URL
    Records POST duration into timings.
    """
    DEMO_URL = "https://api-html2image.onrender.com/convert"
    headers = {
        "Accept":       "*/*",
        "Content-Type": "application/json",
        "X-API-KEY":    INTERNAL_API_KEY,
    }
    payload = {
        "html":              html,
        "selector":          "#qr-container",
        "css":               "",
        "url":               "",
        "console_mode":      "",
        "ms_delay":          "",
        "render_when_ready": "false",
        "viewport_width":    "",
        "viewport_height":   "",
        "google_fonts":      "",
        "device_scale":      ""
    }

    t0 = time.perf_counter()
    resp = requests.post(DEMO_URL, headers=headers, json=payload)
    resp.raise_for_status()
    timings['post_ms'] = int((time.perf_counter() - t0) * 1000)

    data = resp.json()
    img_url = data.get("url") or data.get("data", {}).get("url")
    if not img_url:
        raise RuntimeError("No image URL returned: " + str(data))

    # we won't do a GET; let Telegram fetch the .png directly
    timings['get_ms'] = 0
    return img_url + ".png"

# ─── Bot setup ─────────────────────────────────────────────────────────────────
app = Client(
    "styled_qr_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.command("qr") & filters.private)
async def qr_handler(_, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /qr https://example.com", quote=True)

    raw_url = message.command[1].strip()
    data_url = f"{raw_url}?r={random.randint(0,999999)}"
    sent = await message.reply_text("🔧 Generating your styled QR…", quote=True)

    timings = {}

    # ─── 1) Generate base QR ───────────────────────────────────────────────────
    t0 = time.perf_counter()
    qr = QRCodeStyled(
        version=None,
        error_correction=ERROR_CORRECT_H,
        border=0,
        box_size=20,
        image_factory=PilStyledImage,
        mask_pattern=None
    )
    tmp = BytesIO()
    qr.get_image(data=data_url, image=None, optimize=20).save(tmp, kind="PNG")
    tmp.seek(0)
    qr_img = Image.open(tmp).convert("RGB")
    timings['qr_ms'] = int((time.perf_counter() - t0) * 1000)

    # ─── 2) Invert + make background transparent ───────────────────────────────
    t1 = time.perf_counter()
    inverted = ImageOps.invert(qr_img).convert("RGBA")
    pixels = inverted.getdata()
    new_pixels = [
        (0,0,0,0) if (r==0 and g==0 and b==0) else (r,g,b,255)
        for (r,g,b,_) in pixels
    ]
    inverted.putdata(new_pixels)
    timings['invert_ms'] = int((time.perf_counter() - t1) * 1000)

    # ─── 3) Crop edges, carve hole, and composite logo ─────────────────────────
    t2 = time.perf_counter()
    w, h = inverted.size
    cropped = inverted.crop((2, 2, w - 2, h - 2))

    resp_logo = requests.get(LOGO_URL); resp_logo.raise_for_status()
    logo = Image.open(BytesIO(resp_logo.content)).convert("RGBA")
    logo.thumbnail((int(cropped.width * 0.33),) * 2, Image.LANCZOS)

    x = (cropped.width - logo.width) // 2
    y = (cropped.height - logo.height) // 2

    hole_mask = Image.new("L", cropped.size, 0)
    draw = ImageDraw.Draw(hole_mask)
    draw.rounded_rectangle(
        (x, y, x + logo.width, y + logo.height),
        radius=min(logo.width, logo.height)//4,
        fill=255
    )

    transparent_bg = Image.new("RGBA", cropped.size, (0,0,0,0))
    qr_hole = Image.composite(transparent_bg, cropped, hole_mask)
    qr_hole.paste(logo, (x, y), mask=logo)
    timings['compose_ms'] = int((time.perf_counter() - t2) * 1000)

    # ─── 4) Embed into HTML as data-URI ───────────────────────────────────────
    t3 = time.perf_counter()
    out_buf = BytesIO()
    qr_hole.save(out_buf, format="PNG")
    out_buf.seek(0)
    qr_data_uri = "data:image/png;base64," + base64.b64encode(out_buf.getvalue()).decode()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>QR on Template</title>
  <style>
    html, body {{ margin:0; padding:0; background:transparent; }}
    #qr-container {{ position:relative; display:inline-block; }}
    #qr-container img.bg {{ display:block; width:100%; height:auto; }}
    #qr-container img.qr {{
      position:absolute; left:50%; top:50%;
      transform:translate(-50%, -50%);
      width:30%; height:auto;
    }}
  </style>
</head>
<body>
  <div id="qr-container">
    <img class="bg" src="{TEMPLATE_URL}" alt="Template"/>
    <img class="qr" src="{qr_data_uri}" alt="Styled QR"/>
  </div>
</body>
</html>"""
    timings['html_ms'] = int((time.perf_counter() - t3) * 1000)

    # ─── 5) Convert via YOUR API (no GET) ─────────────────────────────────────
    try:
        image_url = html_to_jpg_convertapi(html, timings)
    except Exception as e:
        return await sent.edit_text(f"❌ Failed to generate image: {e}")

    # ─── 6) Send photo by URL with timings in caption ─────────────────────────
    caption = (
        "✅ Here’s your styled QR on the template!\n\n"
        f"⏱ QR gen:    {timings['qr_ms']} ms\n"
        f"⏱ Invert:    {timings['invert_ms']} ms\n"
        f"⏱ Compose:   {timings['compose_ms']} ms\n"
        f"⏱ HTML prep: {timings['html_ms']} ms\n"
        f"⏱ POST:      {timings.get('post_ms',0)} ms\n"
        f"⏱ GET img:   {timings.get('get_ms',0)} ms\n"
        f"⏱ Total:     {sum(timings.values())} ms"
    )
    await sent.delete()
    await message.reply_photo(photo=image_url, caption=caption)

if __name__ == "__main__":
    app.run()
