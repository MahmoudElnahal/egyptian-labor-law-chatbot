#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 -m uvicorn app.server:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}" --reload
