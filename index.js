import express from 'express';
// Pull in the default export; that's your render function
import nodeHtmlToImage from 'node-html-to-image';

import fs from 'fs';
import path from 'path';
import { Octokit } from '@octokit/rest';
import { v4 as uuidv4 } from 'uuid';

// ── 1) CONFIG ────────────────────────────────────────────────────────────────
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;    // ← Only this comes from env

const REPO_OWNER   = 'SaloniTae';
const REPO_NAME    = 'Admin';
const REPO_BRANCH  = 'main';
const REPO_PATH    = 'media/html_to_image';

const PUPPETEER_ARGS = [
  '--no-sandbox',
  '--disable-setuid-sandbox',
  '--disable-dev-shm-usage',
];

// ── 2) PREP ──────────────────────────────────────────────────────────────────
if (!GITHUB_TOKEN) {
  console.error('❌ Missing GITHUB_TOKEN in environment');
  process.exit(1);
}

const MEDIA_FOLDER = path.join(process.cwd(), 'media');
fs.mkdirSync(MEDIA_FOLDER, { recursive: true });

const app  = express();
const PORT = process.env.PORT || 10000;

// ── 3) /generate ROUTE ──────────────────────────────────────────────────────
app.get('/generate', async (req, res) => {
  try {
    // a) Your HTML template
    const html = `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>QR on Template</title>
  <style>
    /* 1) Remove any page margins and make background transparent */
    html, body {
      margin: 0;
      padding: 0;
      background: transparent;
    }

    /* 2) Container holds the background and the QR overlay */
    #qr-container {
      position: relative;
      display: inline-block; /* shrink-wrap to the template image */
    }

    /* 3) Background template */
    #qr-container img.bg {
      display: block;        /* remove inline-img whitespace */
      max-width: 100%;       /* responsive */
      height: auto;
    }

    /* 4) QR overlay: absolute so it sits above the bg */
    #qr-container img.qr {
      position: absolute;
      left: 50%;
      top: 50%;
      transform: translate(-50%, -50%);
      width: 30%;    /* adjust size as needed */
      height: auto;
    }
  </style>
</head>
<body>
  <div id="qr-container">
    <!-- Background template -->
    <img
      class="bg"
      src="https://i.postimg.cc/4y0GJPXN/QRTemplate.png"
      alt="Template Background"
    />

    <!-- QR overlay -->
    <img
      class="qr"
      src="https://i.postimg.cc/YqSRhyG8/IMG-20250501-103105-956.jpg"
      alt="Generated QR Code"
    />
  </div>
</body>
</html>
    `;

    // b) Render locally via default export
    const imageName = `${uuidv4()}.png`;
    const localPath = path.join(MEDIA_FOLDER, imageName);

    await nodeHtmlToImage({
      output: localPath,
      html,
      puppeteerArgs: PUPPETEER_ARGS,
      quality: 100,
    });
    console.log(`✅ Rendered image to ${localPath}`);

    // c) Read & encode
    const buffer  = fs.readFileSync(localPath);
    const content = buffer.toString('base64');

    // d) GitHub client
    const octokit = new Octokit({ auth: GITHUB_TOKEN });
    const repoFilePath = `${REPO_PATH}/${imageName}`;
    const commitMsg    = `Add generated image ${imageName}`;

    // e) Check if exists (for update vs create)
    let sha;
    try {
      const { data: existing } = await octokit.repos.getContent({
        owner: REPO_OWNER,
        repo:  REPO_NAME,
        path:  repoFilePath,
        ref:   REPO_BRANCH,
      });
      sha = existing.sha;
    } catch {
      // not found ⇒ we'll create it
    }

    // f) Create/update on GitHub
    await octokit.repos.createOrUpdateFileContents({
      owner:   REPO_OWNER,
      repo:    REPO_NAME,
      path:    repoFilePath,
      message: commitMsg,
      content,
      branch:  REPO_BRANCH,
      ...(sha && { sha }),
    });

    // g) Cleanup & respond
    fs.unlinkSync(localPath);
    const rawUrl = `https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${REPO_BRANCH}/${repoFilePath}`;
    return res.json({ image_url: rawUrl });
  }
  catch (error) {
    console.error('❌ Error in /generate:', error);
    return res.status(500).json({ error: error.message });
  }
});

// ── 4) START ─────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`🚀 Service listening on http://localhost:${PORT}/generate`);
});
