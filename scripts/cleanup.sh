#!/usr/bin/env bash
# Delete old pipeline artifacts so the VPS disk does not fill up.
# Retention: inputs 7 days, working 1 day, outputs 30 days.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$PROJECT_ROOT/logs/cleanup.log"

mkdir -p "$PROJECT_ROOT/logs"

{
    echo "--- $(date -Is) cleanup run ---"
    find "$PROJECT_ROOT/inputs"  -maxdepth 1 -type f -mtime +7  -print -delete || true
    find "$PROJECT_ROOT/working" -maxdepth 1 -type f -mtime +1  -print -delete || true
    find "$PROJECT_ROOT/outputs" -maxdepth 1 -type f -mtime +30 -print -delete || true
    echo "--- done ---"
} >> "$LOG_FILE" 2>&1
