// index.js

require('dotenv').config();
const express        = require('express');
const bodyParser     = require('body-parser');
// swap in puppeteer-core so it won't look for its own Chromium download
const puppeteer      = require('puppeteer-core');
const { Octokit }    = require('@octokit/rest');
const { v4: uuidv4 } = require('uuid');
const fs             = require('fs-extra');
const path           = require('path');

const app = express();
app.use(bodyParser.json({ limit: '10mb' }));

// ── REQUIRED ENV VARS ──────────────────────────────────────────────────────
const API_KEY      = process.env.API_KEY     || 'abcd';
const MEDIA_FOLDER = process.env.MEDIA_FOLDER
  || path.join(process.cwd(), 'media', 'html_to_image');
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const REPO_OWNER   = process.env.REPO_OWNER   || 'SaloniTae';
const REPO_NAME    = process.env.REPO_NAME    || 'Admin';
const BRANCH       = process.env.REPO_BRANCH  || 'main';
const PATH_PREFIX  = process.env.REPO_PATH    || 'media/html_to_image';
// Puppeteer executable path: either explicitly set or fallback to Render's Chrome
const CHROME_PATH  = process.env.PUPPETEER_EXECUTABLE_PATH
                   || process.env.CHROME_PATH
                   || '/opt/render/project/.render/chrome/opt/google/chrome';
// ──────────────────────────────────────────────────────────────────────────

// ensure local media folder exists
fs.ensureDirSync(MEDIA_FOLDER);

// initialize GitHub client
const octokit = new Octokit({ auth: GITHUB_TOKEN });

app.post('/convert', async (req, res) => {
  try {
    // 1) API key check
    if (req.headers['x-api-key'] !== API_KEY) {
      return res.status(403).json({ error: 'Invalid API key' });
    }

    // 2) Validate payload
    const html      = req.body.html;
    const elementId = req.body.elementId;
    if (!html) {
      return res.status(400).json({ error: "Missing 'html'" });
    }

    // 3) Build standalone HTML if element-only
    let standalone = html;
    if (elementId) {
      const styleMatches = [...html.matchAll(/<style[\s\S]*?<\/style>/gi)]
        .map(m => m[0])
        .join('\n');
      const inject = `
        <style>
          html, body { margin: 0; padding: 0; }
          #${elementId} { display: inline-block; }
        </style>
      `;
      standalone = `
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          ${styleMatches}
          ${inject}
        </head>
        <body>
          ${html}
        </body>
        </html>
      `;
    }

    // 4) Launch Puppeteer against Render’s Chrome
    const browser = await puppeteer.launch({
      executablePath: CHROME_PATH,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();
    await page.setContent(standalone, { waitUntil: 'networkidle0' });

    // 5) Screenshot logic
    const imageName = uuidv4() + '.png';
    const imagePath = path.join(MEDIA_FOLDER, imageName);

    if (elementId) {
      const el = await page.$(`#${elementId}`);
      if (!el) {
        await browser.close();
        return res.status(400).json({ error: `No element with id='${elementId}' found` });
      }
      const rect = await el.boundingBox();
      await page.screenshot({
        path: imagePath,
        clip: {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height)
        }
      });
    } else {
      await page.screenshot({ path: imagePath, fullPage: true });
    }
    await browser.close();

    // 6) Commit to GitHub
    const fileContent = await fs.readFile(imagePath);
    const repoPath    = `${PATH_PREFIX}/${imageName}`;

    let sha;
    try {
      const existing = await octokit.repos.getContent({
        owner: REPO_OWNER,
        repo:  REPO_NAME,
        path:  repoPath,
        ref:   BRANCH
      });
      sha = existing.data.sha;
    } catch (_) {
      sha = undefined;
    }

    const params = {
      owner:   REPO_OWNER,
      repo:    REPO_NAME,
      path:    repoPath,
      message: `Add generated image ${imageName}`,
      content: fileContent.toString('base64'),
      branch:  BRANCH
    };
    if (sha) params.sha = sha;
    await octokit.repos.createOrUpdateFileContents(params);

    // 7) Build raw URL and clean up
    const rawUrl = `https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${BRANCH}/${repoPath}`;
    await fs.remove(imagePath);

    return res.json({ image_url: rawUrl });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: 'Conversion failed', details: err.message });
  }
});

// start server
const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
  console.log(`⚡️ Puppeteer service listening on port ${PORT}`);
});
