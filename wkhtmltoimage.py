#!/usr/bin/env python3
import tempfile, subprocess, os

# ← set this to your actual wkhtmltoimage executable
WKHTMLTOIMAGE_PATH = "/usr/bin/wkhtmtoimage"  

def html_to_png_wkhtmltoimage(html: str, width: int, height: int) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode='w', encoding='utf-8') as html_file:
        html_file.write(html)
        html_path = html_file.name

    png_path = html_path.replace(".html", ".png")
    # call your explicit path here
    subprocess.run([
        WKHTMLTOIMAGE_PATH,
        "--width",  str(width),
        "--height", str(height),
        "--disable-smart-width",
        html_path,
        png_path
    ], check=True)

    with open(png_path, "rb") as img_file:
        result = img_file.read()

    os.remove(html_path)
    os.remove(png_path)
    return result

if __name__ == "__main__":
    html = """
    <html><head><meta charset="utf-8"/></head><body style="margin:0">
      <div style="position:relative;width:600px;height:400px">
        <img src="https://via.placeholder.com/600x400.png?text=TEST+TEMPLATE"
             style="width:100%;height:100%;object-fit:cover"/>
        <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
                    font-family:sans-serif;color:#fff;
                    font-size:48px;text-shadow:0 0 5px rgba(0,0,0,.8)">
          WKHTMLTOIMAGE OK!
        </div>
      </div>
    </body></html>
    """
    png_bytes = html_to_png_wkhtmltoimage(html, 600, 400)
    with open("test.png", "wb") as f:
        f.write(png_bytes)
    print("✅ test.png written – open it to confirm wkhtmltoimage is working")
