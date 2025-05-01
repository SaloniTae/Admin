import os
import uuid
import tempfile
import subprocess
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup

# === Configuration ===
API_KEY = os.environ.get("API_KEY", "abcd")
MEDIA_FOLDER = os.environ.get(
    "MEDIA_FOLDER",
    "/home/htmltoimage/mysite/media/html_to_image"
)
os.makedirs(MEDIA_FOLDER, exist_ok=True)

# === App initialization ===
app = Flask(__name__)

@app.route("/convert", methods=["POST"])
def convert_html():
    # 1) API-key check
    api_key = request.headers.get("x-api-key", "abcd")
    if api_key != API_KEY:
        return jsonify({"error": "Invalid API key"}), 403

    # 2) JSON + html sanity
    data = request.get_json(force=True, silent=True) or {}
    html = data.get("html")
    if not html:
        return jsonify({"error": "Missing HTML in request"}), 400

    # 3) Parse & extract only <div id="qr-container">
    soup = BeautifulSoup(html, "html5lib")
    target_div = soup.find("div", id="qr-container")
    if not target_div:
        return jsonify({"error": "Div with id='qr-container' not found"}), 400

    # 4) Build minimal standalone HTML
    standalone = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>QR Snapshot</title></head>
<body>
{target_div.prettify()}
</body>
</html>"""

    # 5) Write temp file
    tmp = tempfile.NamedTemporaryFile(
        mode="w+", suffix=".html", delete=False, encoding="utf-8"
    )
    tmp.write(standalone)
    tmp.flush()
    tmp_path = tmp.name
    tmp.close()

    # 6) Prepare output path
    image_name = f"{uuid.uuid4().hex}.png"
    image_path = os.path.join(MEDIA_FOLDER, image_name)

    # 7) Run wkhtmltoimage
    try:
        subprocess.run(
            ["wkhtmltoimage", tmp_path, image_path],
            check=True,
            stderr=subprocess.PIPE
        )
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="ignore")
        return jsonify({
            "error": "Failed to convert HTML to image",
            "details": err
        }), 500
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    # 8) Return JSON
    return jsonify({
        "image_url": f"/media/html_to_image/{image_name}"
    }), 200


@app.route("/media/html_to_image/<path:filename>", methods=["GET"])
def serve_image(filename):
    return send_from_directory(MEDIA_FOLDER, filename)


if __name__ == "__main__":
    # Run on 0.0.0.0:5000 (or $PORT)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
