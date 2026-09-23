#!/usr/bin/env bash
set -u
exec python3 "$(dirname "$0")/video-session.py" "$@"
