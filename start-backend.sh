#!/usr/bin/env bash
# Start the Python FastAPI backend
set -e
cd "$(dirname "$0")/backend"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8010
