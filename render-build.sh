#!/usr/bin/env bash
set -o errexit

# Skip any Chromium download, install your deps
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
npm install
