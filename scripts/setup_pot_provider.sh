#!/usr/bin/env bash
# Set up the BgUtils PO token provider (script-node variant) under vendor/.
# Required when yt-dlp hits "Sign in to confirm you're not a bot". Uses the
# currently-installed bgutil-ytdlp-pot-provider plugin version from the venv.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/vendor/bgutil-ytdlp-pot-provider"
PLUGIN_VERSION="$("$ROOT/.venv/bin/python" -m pip show bgutil-ytdlp-pot-provider \
  | awk '/^Version:/ {print $2}')"

if [[ -z "$PLUGIN_VERSION" ]]; then
  echo "bgutil-ytdlp-pot-provider not installed in .venv; run: .venv/bin/python -m pip install bgutil-ytdlp-pot-provider" >&2
  exit 1
fi

mkdir -p "$ROOT/vendor"
if [[ ! -d "$VENDOR/.git" ]]; then
  git clone --single-branch --branch "$PLUGIN_VERSION" \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git "$VENDOR"
else
  git -C "$VENDOR" fetch --tags
  git -C "$VENDOR" checkout "$PLUGIN_VERSION"
fi

cd "$VENDOR/server"
npm ci
npx tsc

echo
echo "Provider ready at: $VENDOR/server"
echo "Pass to yt-dlp: --js-runtimes node --extractor-args 'youtubepot-bgutilscript:server_home=$VENDOR/server'"
