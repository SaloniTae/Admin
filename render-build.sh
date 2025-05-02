#!/usr/bin/env bash
set -o errexit

# 1. Install your Node dependencies (CI is faster & clean)
npm ci
