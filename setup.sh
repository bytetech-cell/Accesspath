#!/usr/bin/env bash
# ACCESSPATH one-time setup for macOS / Linux (uses venv, no Docker)
set -e
cd "$(dirname "$0")/backend"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
[ -f .env ] || cp .env.example .env
echo "Setup done! Put your TINYFISH_API_KEY in backend/.env, then run ./run.sh"
