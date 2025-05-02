#!/usr/bin/env bash
set -o errexit

export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
export PUPPETEER_EXECUTABLE_PATH=/opt/render/project/.render/chrome/opt/google/chrome


# install only your Node deps
npm install
