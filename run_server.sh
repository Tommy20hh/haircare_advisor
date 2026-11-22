#!/usr/bin/env bash
cd "$(dirname "$0")" && python -m uvicorn service.main:app --host 127.0.0.1 --port 8000
