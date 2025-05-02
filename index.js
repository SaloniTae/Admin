import express from 'express';
import nodeHtmlToImage from 'node-html-to-image';
import fs from 'fs';
import path from 'path';
import { Octokit } from '@octokit/rest';
import { v4 as uuidv4 } from 'uuid';
import puppeteer from 'puppeteer-core';

// ── 1) CONFIG ────────────────────────────────────────────────────────────────
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
if (!GITHUB_TOKEN) {
  console.error('❌ Missing GITHUB_TOKEN in environment');
  process.exit(1);
}

const API_KEY = 'OTTONRENT';
const REPO_OWNER  = 'SaloniTae';
const REPO_NAME   = 'Admin';
const REPO_BRANCH = 'main';
const REPO_PATH   = 'media/html_to_image';

const PUPPETEER_ARGS = [
  '--no-sandbox',
  '--disable-setuid-sandbox',
  '--disable-dev-shm-usage',
];

// ── 2) SETUP ─────────────────────────────────────────────────────────────────
const app = express();
const PORT = process.env.PORT || 10000;

app.use(express.json());

const MEDIA_FOLDER = path.join(process.cwd(), 'media');
fs.mkdirSync(MEDIA_FOLDER, { recursive: true });

// ── Shared browser instance ───────────────────────────────────────────────────
// ── Shared browser instance ───────────────────────────────────────────────────
let browser;
(async () => {
  console.log('⏳ Launching headless browser...');
  browser = await puppeteer.launch({
    executablePath: '/usr/bin/chromium-browser',
    args: PUPPETEER_ARGS
  });
  console.log('🚀 Browser launched');
})();

// ── 3) /generate ROUTE ──────────────────────────────────────────────────────
app.post('/generate', async (req, res) => {
  try {
    if (req.header('x-api-key') !== API_KEY) {
      return res.status(401).json({ error: 'Invalid API key' });
    }

    const {
      html, type, quality, content, waitUntil,
      transparent, encoding, selector,
      beforeScreenshot, handlebarsHelpers, timeout
    } = req.body;

    if (!html || typeof html !== 'string') {
      return res.status(400).json({ error: '"html" (string) is required' });
    }

    const ext = type === 'jpeg' ? 'jpg' : 'png';
    const imageName = `${uuidv4()}.${ext}`;
    const localPath = path.join(MEDIA_FOLDER, imageName);

    // ── Timing: render phase ─────────────────────────────────────────────────
    console.time('render');
    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: waitUntil || 'networkidle0', timeout });
    if (beforeScreenshot) await beforeScreenshot(page);
    const screenshotOpts = {
      path: localPath,
      type: type || 'png',
      quality: quality,
      omitBackground: transparent === true
    };
    if (selector) {
      const el = await page.$(selector);
      await el.screenshot({ ...screenshotOpts });
    } else {
      await page.screenshot(screenshotOpts);
    }
    await page.close();
    console.timeEnd('render');

    // ── Read & cleanup ───────────────────────────────────────────────────────
    const buffer = fs.readFileSync(localPath);
    const base64 = buffer.toString('base64');
    fs.unlinkSync(localPath);

    // ── Timing: GitHub upload ────────────────────────────────────────────────
    console.time('upload');
    const octokit = new Octokit({ auth: GITHUB_TOKEN });
    const repoFilePath = `${REPO_PATH}/${imageName}`;
    const commitMsg    = `Add generated image ${imageName}`;

    let sha;
    try {
      const { data: existing } = await octokit.repos.getContent({
        owner: REPO_OWNER, repo: REPO_NAME,
        path: repoFilePath, ref: REPO_BRANCH
      });
      sha = existing.sha;
    } catch {}

    await octokit.repos.createOrUpdateFileContents({
      owner:   REPO_OWNER,
      repo:    REPO_NAME,
      path:    repoFilePath,
      message: commitMsg,
      content: base64,
      branch:  REPO_BRANCH,
      ...(sha && { sha })
    });
    console.timeEnd('upload');

    const rawUrl = `https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${REPO_BRANCH}/${repoFilePath}`;
    return res.json({ image_url: rawUrl });
  }
  catch (error) {
    console.error('❌ Error in /generate:', error);
    return res.status(500).json({ error: error.message });
  }
});

// ── 4) /ping for healthcheck ─────────────────────────────────────────────────
app.get('/ping', (req, res) => res.sendStatus(200));

// ── 5) START SERVER ───────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`🚀 Listening on http://localhost:${PORT}/generate`);
});
