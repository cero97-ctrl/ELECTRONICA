#!/usr/bin/env bash
set -euo pipefail

# update_repo.sh
# Usage:
#   ./update_repo.sh [-d DIR] [-r REMOTE] [-b BRANCH] [-m "commit message"] [--push] [--no-pull] [--dry-run]
# Examples:
#   ./update_repo.sh                    # pull current branch, add/commit changes with default message and push
#   ./update_repo.sh -d /path/to/repo -m "Fix docs" --push
#   ./update_repo.sh --no-pull --push  # don't pull, just commit and push local changes

REMOTE="origin"
BRANCH=""
DIR="$(pwd)"
COMMIT_MSG="Update from update_repo.sh"
DO_PUSH=false
DO_PULL=true
DRY_RUN=false
CONFIRM=false

show_help(){
  sed -n '1,120p' "$0" | sed -n '1,40p'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--dir)
      DIR="$2"; shift 2;;
    -r|--remote)
      REMOTE="$2"; shift 2;;
    -b|--branch)
      BRANCH="$2"; shift 2;;
    -m|--message)
      COMMIT_MSG="$2"; shift 2;;
    --push)
      DO_PUSH=true; shift;;
    --no-pull)
      DO_PULL=false; shift;;
    --dry-run)
      DRY_RUN=true; shift;;
    --confirm)
      CONFIRM=true; shift;;
    -h|--help)
      show_help; exit 0;;
    *)
      echo "Unknown argument: $1"; show_help; exit 1;;
  esac
done

echo "Dir: $DIR"
echo "Remote: $REMOTE"

cd "$DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: $DIR is not a git repository." >&2
  exit 2
fi

CURRENT_BRANCH=$(git symbolic-ref --quiet --short HEAD || git rev-parse --short HEAD)
if [ -z "$BRANCH" ]; then
  BRANCH="$CURRENT_BRANCH"
fi

echo "Branch: $BRANCH"

if [ "$DRY_RUN" = true ]; then
  echo "DRY RUN: no changes will be made. Showing planned actions..."
  echo "Would run: git fetch $REMOTE"
  if [ "$DO_PULL" = true ]; then
    echo "Would run: git pull --rebase $REMOTE $BRANCH"
  fi
  echo "Would run: git add -A"
  echo "Would run: git commit -m \"$COMMIT_MSG\" (if there are changes)"
  if [ "$DO_PUSH" = true ]; then
    echo "Would run: git push $REMOTE $BRANCH"
  fi
  exit 0
fi

# Check if remote exists to avoid fetch failure
if ! git remote | grep -q "^$REMOTE$"; then
  echo "Error: Remote '$REMOTE' not found. Please add it using 'git remote add $REMOTE <url>'." >&2
  exit 5
fi

# Fetch and pull
echo "Fetching from $REMOTE..."
git fetch "$REMOTE"

if [ "$DO_PULL" = true ]; then
  if git rev-parse --verify "$REMOTE/$BRANCH" >/dev/null 2>&1; then
    echo "Pulling latest from $REMOTE/$BRANCH (rebase)..."
    git pull --rebase "$REMOTE" "$BRANCH" || {
      echo "Pull failed: you may need to resolve conflicts manually." >&2
      exit 3
    }
  else
    echo "Remote branch '$REMOTE/$BRANCH' not found. Skipping pull (likely first push)."
  fi
fi

# Stage changes
if git status --porcelain | grep -q .; then
  echo "Local changes detected."
  if [ "$CONFIRM" = true ]; then
    echo "Working tree status:"
    git status --short
    read -r -p "Stage and commit these changes? [y/N]: " REPLY
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
      echo "Staging changes..."
      git add -A
    else
      echo "Skipping commit as requested."
      SKIP_COMMIT=true
    fi
  else
    echo "Staging changes..."
    git add -A
  fi

  if [ "${SKIP_COMMIT:-false}" != "true" ]; then
    # commit if there are staged changes
    if ! git diff --cached --quiet; then
      # If confirm mode and a default message, allow editing the commit message
      if [ "$CONFIRM" = true ]; then
        if [ "$COMMIT_MSG" = "Update from update_repo.sh" ] || [ -z "$COMMIT_MSG" ]; then
          echo "Default commit message: '$COMMIT_MSG'"
          read -r -p "Enter commit message (leave empty to use default): " USER_MSG
          if [ -n "$USER_MSG" ]; then
            COMMIT_MSG="$USER_MSG"
          fi
        else
          read -r -p "Commit message '$COMMIT_MSG'. Edit? (leave empty to keep) : " USER_MSG2
          if [ -n "$USER_MSG2" ]; then
            COMMIT_MSG="$USER_MSG2"
          fi
        fi
      fi
      echo "Committing with message: $COMMIT_MSG"
      git commit -m "$COMMIT_MSG" || {
        echo "Commit failed." >&2
        exit 4
      }
    else
      echo "No staged changes to commit."
    fi
  fi
else
  echo "No local changes detected."
fi

if [ "$DO_PUSH" = true ]; then
  if [ "$CONFIRM" = true ]; then
    echo "About to push to $REMOTE/$BRANCH"
    git --no-pager log --oneline --decorate --graph --all -n 10 || true
    read -r -p "Push to $REMOTE/$BRANCH? [y/N]: " REPLY2
    if [[ "$REPLY2" =~ ^[Yy]$ ]]; then
      echo "Pushing to $REMOTE $BRANCH..."
      git push "$REMOTE" "$BRANCH"
    else
      echo "Push skipped by user."
    fi
  else
    echo "Pushing to $REMOTE $BRANCH..."
    git push "$REMOTE" "$BRANCH"
  fi
fi

echo "Done."