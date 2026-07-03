#!/bin/sh
set -e

DATA_DIR="${DOPAMINE_DATA_DIR:-/app/data}"
mkdir -p "$DATA_DIR"

if ! touch "$DATA_DIR/.write_probe" 2>/dev/null; then
  echo "WARN: data dir not writable: $DATA_DIR" >&2
else
  rm -f "$DATA_DIR/.write_probe"
  echo "data dir ok: $DATA_DIR" >&2
fi

exec uvicorn server.main:app --host 0.0.0.0 --port "${PORT:-8080}"
