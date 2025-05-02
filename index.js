import express from 'express';
import { render } from 'node-html-to-image';
import fs from 'fs';
import path from 'path';
import { Octokit } from '@octokit/rest';
import { v4 as uuidv4 } from 'uuid';

// ── 1) HARD-CODED CONFIG ─────────────────────────────────────────────────────

const GITHUB_TOKEN = process.env.GITHUB_TOKEN;    // ← Only this one stays in env

const REPO_OWNER   = 'SaloniTae';
const REPO_NAME    = 'Admin';
const REPO_BRANCH  = 'main';
const REPO_PATH    = 'media/html_to_image';

// Puppeteer flags for Render free plan
const PUPPETEER_ARGS = [
  '--no-sandbox',
  '--disable-setuid-sandbox',
  '--disable-dev-shm-usage',
];

// ── 2) BOILERPLATE ───────────────────────────────────────────────────────────

if (!GITHUB_TOKEN) {
  console.error('❌ Missing GITHUB_TOKEN in environment');
  process.exit(1);
}

const MEDIA_FOLDER = path.join(process.cwd(), 'media');
fs.mkdirSync(MEDIA_FOLDER, { recursive: true });

const app  = express();
const PORT = process.env.PORT || 10000;

// ── 3) ROUTE ─────────────────────────────────────────────────────────────────

app.get('/generate', async (req, res) => {
  try {
    // a) Define your HTML template
    const html = `
      <html>
        <head>
          <style>
            body { margin:0; padding:40px; font-family:sans-serif; }
            .card {
              padding:20px;
              border-radius:8px;
              box-shadow:0 2px 8px rgba(0,0,0,0.1);
              background:#fff;
            }
            h1 { font-size:32px; margin:0 0 10px; }
            p  { font-size:16px; color:#555; }
          </style>
        </head>
        <body>
          <div class="card">
            <h1>Hello, world!</h1>
            <p>Rendered via node-html-to-image on Node 22.</p>
          </div>
        </body>
      </html>
    `;

    // b) Render to a local file
    const imageName = `${uuidv4()}.png`;
    const localPath = path.join(MEDIA_FOLDER, imageName);

    await render({
      html,
      output: localPath,
      puppeteerArgs: PUPPETEER_ARGS,
      quality: 100,
    });
    console.log(`✅ Rendered image to ${localPath}`);

    // c) Read & Base64-encode the file
    const buffer  = fs.readFileSync(localPath);
    const content = buffer.toString('base64');

    // d) Initialize GitHub client
    const octokit = new Octokit({ auth: GITHUB_TOKEN });
    const repoFilePath = `${REPO_PATH}/${imageName}`;
    const commitMsg    = `Add generated image ${imageName}`;

    // e) Try to fetch existing file SHA (for update vs. create)
    let sha;
    try {
      const { data: existing } = await octokit.repos.getContent({
        owner: REPO_OWNER,
        repo:  REPO_NAME,
        path:  repoFilePath,
        ref:   REPO_BRANCH,
      });
      sha = existing.sha;
    } catch { /* not found → will create */ }

    // f) Create or update the file in GitHub
    await octokit.repos.createOrUpdateFileContents({
      owner:   REPO_OWNER,
      repo:    REPO_NAME,
      path:    repoFilePath,
      message: commitMsg,
      content,
      branch:  REPO_BRANCH,
      ...(sha && { sha }),
    });

    // g) Clean up & return the raw URL
    fs.unlinkSync(localPath);
    const rawUrl = `https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${REPO_BRANCH}/${repoFilePath}`;
    return res.json({ image_url: rawUrl });
  }
  catch (error) {
    console.error('❌ Error in /generate:', error);
    return res.status(500).json({ error: error.message });
  }
});

// ── 4) START SERVER ───────────────────────────────────────────────────────────

app.listen(PORT, () => {
  console.log(`🚀 Service listening on http://localhost:${PORT}/generate`);
});
