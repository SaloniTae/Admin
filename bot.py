import os
import random
import subprocess
import tempfile
from io import BytesIO
from pyrogram import Client, filters

# ─── CONFIG ───────────────────────────────────────────────────────────────────
API_ID    = 25270711
API_HASH  = "6bf18f3d9519a2de12ac1e2e0f5c383e"
BOT_TOKEN = "7140092976:AAFtmOBKi-mIoVighcf4XXassHimU2CtlR8"

# fixed image to embed
IMAGE_URL = (
  "https://res.cloudinary.com/djzfoukhz/image/upload/"
  "v1746022425/Untitled_design_20250430_011630_0000_icacxu.png"
)
# ──────────────────────────────────────────────────────────────────────────────

# JS stub: exact qr-code-styling config you gave
QR_JS = r"""
#!/usr/bin/env node
const fs        = require("fs");
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
            "Usage:\n`/qr https://example.com`\n\n"
            "I’ll return a 300×300 styled QR with your image embedded.",
            quote=True
        )

    # unique-ify to force new QR each time
    url = message.command[1].strip() + f"?r={random.randint(1e4,1e6)}"
    await message.reply_text("🔧 Generating your QR…", quote=True)

    # write out the JS helper once to a temp file
    js_fd, js_path = tempfile.mkstemp(suffix=".js")
    os.write(js_fd, QR_JS.encode("utf-8"))
    os.close(js_fd)
    os.chmod(js_path, 0o755)

    # temp output path
    out_fd, out_png = tempfile.mkstemp(suffix=".png")
    os.close(out_fd)

    try:
        subprocess.run([
          "node", js_path, url, IMAGE_URL, out_png
        ], check=True)

        # send back
        with open(out_png, "rb") as image:
            await message.reply_photo(image, caption="✅ Here’s your styled QR!")
    except Exception as e:
        await message.reply_text(f"❌ Failed to generate QR:\n{e}", quote=True)
    finally:
        # cleanup
        for p in (js_path, out_png):
            try: os.remove(p)
            except: pass

app.run()
