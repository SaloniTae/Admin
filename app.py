import os
import uuid
import tempfile
import subprocess
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from github import Github
from PIL import Image, ImageChops

app = Flask(__name__)

# ── REQUIRED ENV VARS ──────────────────────────────────────────────────────
API_KEY      = os.getenv("API_KEY", "abcd")
MEDIA_FOLDER = os.environ.get(
    "MEDIA_FOLDER",
    os.path.join(os.getcwd(), "media/html_to_image")
)
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO_OWNER   = os.getenv("REPO_OWNER", "SaloniTae")
REPO_NAME    = os.getenv("REPO_NAME", "Admin")
BRANCH       = os.getenv("REPO_BRANCH", "main")
PATH_PREFIX  = os.getenv("REPO_PATH", "media/html_to_image")
# ─────────────────────────────────────────────────────────────────────────

# ensure local media folder exists
os.makedirs(MEDIA_FOLDER, exist_ok=True)

# initialize GitHub client
gh   = Github(GITHUB_TOKEN)
repo = gh.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

# ── Helper: Crop whitespace ───────────────────────────────────────────────
def trim_whitespace(image_path):
    img = Image.open(image_path).convert("RGB")
    bg = Image.new("RGB", img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    if bbox:
        img_cropped = img.crop(bbox)
        img_cropped.save(image_path)

# ── Endpoint ──────────────────────────────────────────────────────────────
@app.route("/convert", methods=["POST"])
def convert_html():
    # 1) API key check
    if request.headers.get("x-api-key") != API_KEY:
        return jsonify({"error": "Invalid API key"}), 403

    # 2) Validate payload
    data = request.get_json(force=True, silent=True) or {}
    html = data.get("html")
    if not html:
        return jsonify({"error": "Missing 'html'"}), 400

    # 3) Determine render mode: full or element-only
    element_id = data.get("elementId")  # optional
    if element_id:
        soup = BeautifulSoup(html, "html5lib")
        # extract any <style> tags you already have
        existing_styles = "".join(str(tag) for tag in soup.find_all("style"))

        # build print-css to hide everything except the element
        inject = f"""
        <style>
          @media print {{
            /* hide all */
            body * {{
              visibility: hidden !important;
              margin: 0; padding: 0;
            }}
            /* show only our element */
            #{element_id} {{
              visibility: visible !important;
              position: absolute;
              top: 0; left: 0;
              /* optional: force exact size */
              /* width: 300px; height: 300px; */
            }}
          }}
        </style>
        """

        target = soup.find(id=element_id)
        if not target:
            return jsonify({"error": f"No element with id='{element_id}' found"}), 400

        standalone = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  {existing_styles}
  {inject}
</head>
<body>
  {target.prettify()}
</body>
</html>"""
    else:
        # full-page pass-through
        standalone = html

    # 4) Write HTML to temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8")
    tmp.write(standalone)
    tmp.flush()
    tmp_path = tmp.name
    tmp.close()

    # 5) Convert to PNG locally (with print CSS + viewport sizing)
    image_name = f"{uuid.uuid4().hex}.png"
    image_path = os.path.join(MEDIA_FOLDER, image_name)
    try:
        subprocess.run([
            "wkhtmltoimage",
            "--print-media-type",      # use @media print rules
            "--width",  "400",         # OPTIONAL: match your element’s width in px
            "--height", "400",         # OPTIONAL: match your element’s height in px
            tmp_path,
            image_path
        ], check=True, stderr=subprocess.PIPE)
        trim_whitespace(image_path)  # crop any excess whitespace
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="ignore")
        return jsonify({"error": "Conversion failed", "details": err}), 500
    finally:
        os.remove(tmp_path)

    # 6) Read PNG bytes
    with open(image_path, "rb") as f:
        img_data = f.read()

    # 7) Commit to GitHub
    repo_filepath = f"{PATH_PREFIX}/{image_name}"
    commit_msg    = f"Add generated image {image_name}"
    try:
        existing = repo.get_contents(repo_filepath, ref=BRANCH)
        repo.update_file(repo_filepath, commit_msg, img_data, existing.sha, branch=BRANCH)
    except Exception:
        repo.create_file(repo_filepath, commit_msg, img_data, branch=BRANCH)

    # 8) Build raw URL and clean up
    raw_url = (
        f"https://raw.githubusercontent.com/"
        f"{REPO_OWNER}/{REPO_NAME}/{BRANCH}/{repo_filepath}"
    )
    os.remove(image_path)

    return jsonify({"image_url": raw_url}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
