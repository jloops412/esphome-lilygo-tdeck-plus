#!/usr/bin/with-contenv bashio
set -euo pipefail

export ADDON_GITHUB_REF="$(bashio::config 'github_ref')"
export ADDON_GITHUB_REPO_URL="$(bashio::config 'github_repo_url')"

python3 /app/main.py
