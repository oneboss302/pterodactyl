#!/usr/bin/env bash
# Fetch Reddit sightings from this machine (Reddit blocks GitHub's servers) and push items.json.
# The GitHub workflow deploys the archive on its next scheduled run (17 minutes past every 3rd hour).
# shortcut: needs this PC on and WSL running; replace with the Reddit API once Reddit approves access.
set -euo pipefail
cd "$(dirname "$0")"

git pull --rebase -q origin main
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
python3 build.py "$out"

git add items.json
git diff --cached --quiet && { echo "$(date -Is) no new sightings"; exit 0; }
git -c user.name="pterodactyl-bot" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
    commit -q -m "Sightings from local fetch $(date -u +'%F %H:%M UTC')"
git push -q origin main
echo "$(date -Is) pushed"
