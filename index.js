import express from 'express';
import nodeHtmlToImage from 'node-html-to-image';
import fs from 'fs';
import path from 'path';
import { Octokit } from '@octokit/rest';
import { v4 as uuidv4 } from 'uuid';

// ── 1) CONFIG ────────────────────────────────────────────────────────────────

// GitHub token (set only this in Render's dashboard)
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
if (!GITHUB_TOKEN) {
  console.error('❌ Missing GITHUB_TOKEN in environment');
  process.exit(1);
}

// Your fixed API key – callers must send this header
const API_KEY = 'OTTONRENT';

// GitHub upload settings
const REPO_OWNER  = 'SaloniTae';
const REPO_NAME   = 'Admin';
const REPO_BRANCH = 'main';
const REPO_PATH   = 'media/html_to_image';

// Puppeteer flags for Render free plan
const PUPPETEER_ARGS = [
  '--no-sandbox',
  '--disable-setuid-sandbox',
  '--disable-dev-shm-usage',
];

// ── 2) SETUP ─────────────────────────────────────────────────────────────────

const app = express();
const PORT = process.env.PORT || 10000;

// JSON parser
app.use(express.json());

// Ensure temp folder exists
const MEDIA_FOLDER = path.join(process.cwd(), 'media');
fs.mkdirSync(MEDIA_FOLDER, { recursive: true });

// ── 3) /generate ROUTE ──────────────────────────────────────────────────────

/**
 * POST /generate
 * Headers:
 *   x-api-key: your fixed key
 * Body JSON:
 * {
 *   html:             string,        // required
 *   output?:          string,        // optional local path (ignored)
 *   type?:            'png'|'jpeg',  // default 'png'
 *   quality?:         number,        // jpg only, 0–100
 *   content?:         object|array,  // Handlebars data
 *   waitUntil?:       string|array,  // e.g. 'networkidle0'
 *   transparent?:     boolean,       // png only
 *   encoding?:        'binary'|'base64',
 *   selector?:        string,        // CSS selector
 *   beforeScreenshot?: Function,     // async (page) => {…}
 *   handlebarsHelpers?: object,
 *   timeout?:         number         // ms
 * }
 * 
 * Returns:
 *   { image_url: string }
 */
app.post('/generate', async (req, res) => {
  try {
    // 3a) Authenticate
    if (req.header('x-api-key') !== API_KEY) {
      return res.status(401).json({ error: 'Invalid API key' });
    }

    // 3b) Destructure options
    const {
      html,
      type,
      quality,
      content,
      waitUntil,
      transparent,
      encoding,
      selector,
      beforeScreenshot,
      handlebarsHelpers,
      timeout
    } = req.body;

    if (!html || typeof html !== 'string') {
      return res.status(400).json({ error: '"html" (string) is required' });
    }

    // 3c) Render to local file
    const ext = type === 'jpeg' ? 'jpg' : 'png';
    const imageName = `${uuidv4()}.${ext}`;
    const localPath = path.join(MEDIA_FOLDER, imageName);

    await nodeHtmlToImage({
      html,
      output: localPath,
      puppeteerArgs: PUPPETEER_ARGS,
      // optional overrides
      ...(type       && { type }),
      ...(quality    != null && { quality }),
      ...(content    && { content }),
      ...(waitUntil  && { waitUntil }),
      ...(transparent!= null && { transparent }),
      ...(encoding   && { encoding }),
      ...(selector   && { selector }),
      ...(beforeScreenshot && { beforeScreenshot }),
      ...(handlebarsHelpers && { handlebarsHelpers }),
      ...(timeout    != null && { timeout })
    });

    // 3d) Read & Base64-encode, then cleanup
    const buffer = fs.readFileSync(localPath);
    const base64 = buffer.toString('base64');
    fs.unlinkSync(localPath);

    // 3e) Upload to GitHub
    const octokit = new Octokit({ auth: GITHUB_TOKEN });
    const repoFilePath = `${REPO_PATH}/${imageName}`;
    const commitMsg    = `Add generated image ${imageName}`;

    // Try fetch existing SHA
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
      // not found → create new
    }

    await octokit.repos.createOrUpdateFileContents({
      owner:   REPO_OWNER,
      repo:    REPO_NAME,
      path:    repoFilePath,
      message: commitMsg,
      content: base64,
      branch:  REPO_BRANCH,
      ...(sha && { sha })
    });

    // 3f) Respond with raw URL
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
  console.log(`🚀 Listening on http://localhost:${PORT}/generate`);
});
