#!/usr/bin/env python3
import os
import random
import subprocess
import tempfile
from io import BytesIO
from pyrogram import Client, filters

# ─── CONFIG ───────────────────────────────────────────────────────────────────
# Replace these with your own or set via environment variables
API_ID    = int(os.getenv("API_ID", "25270711"))
API_HASH  = os.getenv("API_HASH",  "6bf18f3d9519a2de12ac1e2e0f5c383e")
BOT_TOKEN = os.getenv("BOT_TOKEN", "7140092976:AAFtmOBKi-mIoVighcf4XXassHimU2CtlR8")

# The image URL to embed
IMAGE_URL = (
    "https://res.cloudinary.com/djzfoukhz/image/upload/"
    "v1746022425/Untitled_design_20250430_011630_0000_icacxu.png"
)
# ──────────────────────────────────────────────────────────────────────────────

# This is the JS code for qr-code-styling (no shebang line)
QR_JS = r"""const fs        = require("fs");
const nodeCanvas= require("canvas");
const { JSDOM } = require("jsdom");
const { QRCodeStyling } = require(
  "qr-code-styling/lib/qr-code-styling.common.js"
);

async function main() {
  const [,, dataUrl, imageUrl, outPath] = process.argv;
  const qr = new QRCodeStyling({
    type:        "canvas",
    width:       300,
    height:      300,
    data:        dataUrl,
    image:       imageUrl,
    margin:      0,
    qrOptions:   { typeNumber: 0, mode: "Byte", errorCorrectionLevel: "H" },
    imageOptions:{ saveAsBlob: true, hideBackgroundDots: true, imageSize: 0.4, margin: 0 },
    dotsOptions: { type: "extra-rounded", color: "#ffffff", roundSize: true },
    backgroundOptions:      { round: 0, color: "#000000" },
    cornersSquareOptions:   { type: "extra-rounded", color: "#ffffff" },
    cornersDotOptions:      { type: "dot",          color: "#ffffff" }
  }, {
    canvas: nodeCanvas,
    jsdom:  new JSDOM().window
  });

  const buffer = await qr.getRawData("png");
  fs.writeFileSync(outPath, buffer);
}

main().catch(e=>{ console.error(e); process.exit(1); });
"""

app = Client("styled_qr_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("qr") & filters.private)
async def qr_handler(_, message):
    if len(message.command) < 2:
        return await message.reply_text(
            "Usage:\n"
            "`/qr https://example.com`\n\n"
            "Generates a 300×300 styled QR (H-level) with your image embedded.",
            quote=True
        )

    # 1) Build a unique URL so each QR differs
    raw_url = message.command[1].strip()
    suffix = random.randint(10_000, 1_000_000)
    data_url = f"{raw_url}?r={suffix}"

    await message.reply_text("🔧 Generating your QR…", quote=True)

    # 2) Write out the JS helper to a temp file
    js_fd, js_path = tempfile.mkstemp(suffix=".js")
    os.write(js_fd, QR_JS.lstrip("\n").encode("utf-8"))
    os.close(js_fd)

    # 3) Prepare a temp output PNG path
    _, out_png = tempfile.mkstemp(suffix=".png")

    try:
        # 4) Invoke Node.js to generate the QR
        subprocess.run(
            ["node", js_path, data_url, IMAGE_URL, out_png],
            check=True, capture_output=True
        )

        # 5) Send the resulting PNG
        with open(out_png, "rb") as f:
            await message.reply_photo(f, caption="✅ Here’s your styled QR code!")
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode().strip()
        await message.reply_text(f"❌ Error generating QR:\n{err}", quote=True)
    finally:
        # 6) Clean up temp files
        for path in (js_path, out_png):
            try:
                os.remove(path)
            except OSError:
                pass

app.run()
