#!/usr/bin/env bash
# Start the React frontend dev server
set -e
cd "$(dirname "$0")/frontend"
PORT=3010 npm start
