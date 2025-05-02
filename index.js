import express from 'express';
import { render } from 'node-html-to-image';
import fs from 'fs';
import path from 'path';
import { Octokit } from '@octokit/rest';
import { v4 as uuidv4 } from 'uuid';
import dotenv from 'dotenv';

dotenv.config();

const {
  GITHUB_TOKEN,
  REPO_OWNER = 'SaloniTae',
  REPO_NAME  = 'Admin',
  REPO_BRANCH= 'main',
  REPO_PATH  = 'media/html_to_image',
  PUPPETEER_ARGS,
} = process.env;

if (!GITHUB_TOKEN) {
  console.error('❌ Missing GITHUB_TOKEN');
  process.exit(1);
}

const MEDIA_FOLDER = path.join(process.cwd(), 'media');
fs.mkdirSync(MEDIA_FOLDER, { recursive: true });

const puppeteerArgs = PUPPETEER_ARGS
  ? PUPPETEER_ARGS.split(',').map(s => s.trim())
  : ['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'];

const app = express();
const PORT = process.env.PORT || 10000;

app.get('/generate', async (req, res) => {
  try {
    // 1) Define HTML
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

    // 2) Render to local file
    const imageName = `${uuidv4()}.png`;
    const localPath = path.join(MEDIA_FOLDER, imageName);
    await render({
      html,
      output: localPath,
      puppeteerArgs,
      quality: 100,
    });

    // 3) Read & encode
    const buffer = fs.readFileSync(localPath);
    const content = buffer.toString('base64');

    // 4) GitHub API
    const octokit = new Octokit({ auth: GITHUB_TOKEN });
    const repoFilePath = `${REPO_PATH}/${imageName}`;
    const commitMsg = `Add generated image ${imageName}`;

    let sha;
    try {
      const { data: existing } = await octokit.repos.getContent({
        owner: REPO_OWNER, repo: REPO_NAME,
        path: repoFilePath, ref: REPO_BRANCH
      });
      sha = existing.sha;
    } catch (err) {
      // file does not exist → create new
    }

    await octokit.repos.createOrUpdateFileContents({
      owner:   REPO_OWNER,
      repo:    REPO_NAME,
      path:    repoFilePath,
      message: commitMsg,
      content,
      branch:  REPO_BRANCH,
      ...(sha && { sha })
    });

    // 5) Respond with raw URL
    const rawUrl = `https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${REPO_BRANCH}/${repoFilePath}`;
    fs.unlinkSync(localPath);
    return res.json({ image_url: rawUrl });
  }
  catch (e) {
    console.error(e);
    return res.status(500).json({ error: e.message });
  }
});

app.listen(PORT, () => {
  console.log(`🚀 Listening on http://localhost:${PORT}/generate`);
});
