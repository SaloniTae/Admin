#!/usr/bin/env bash
set -o errexit

# tell Puppeteer to skip its own download
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
# point to Render’s Chrome
export PUPPETEER_EXECUTABLE_PATH=/opt/render/project/.render/chrome/opt/google/chrome

# install only your Node deps
npm install
