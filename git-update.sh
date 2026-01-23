#!/usr/bin/env bash
set -euo pipefail

# Get the directory where the script is located
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR"

# Ensure update_repo.sh exists and is executable
if [ ! -f "./update_repo.sh" ]; then
  echo "Error: update_repo.sh not found in $SCRIPT_DIR"
  exit 1
fi
chmod +x ./update_repo.sh

# Detect current branch (defaults to main if detection fails)
CURRENT_BRANCH=$(git symbolic-ref --quiet --short HEAD || echo "main")

echo "Starting update for branch: $CURRENT_BRANCH"

# Commit local changes before pulling (WIP)
git add -A
if ! git diff --staged --quiet; then
  git commit -m "WIP: guardar cambios antes de pull" || true
else
  echo "No local changes to commit (pre-check)."
fi

# Call update_repo.sh
./update_repo.sh --remote origin --branch "$CURRENT_BRANCH" --push
