#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
VERSION_FILE="$REPO_DIR/VERSION"

usage() {
  cat <<EOF
Usage: $(basename "$0") <major|minor|patch|X.Y.Z>

Bump version, commit, tag, and push.

  major     0.2.0 → 1.0.0
  minor     0.2.0 → 0.3.0
  patch     0.2.0 → 0.2.1
  X.Y.Z     set explicit version

Examples:
  $(basename "$0") minor
  $(basename "$0") 1.0.0
EOF
  exit 1
}

[ $# -eq 0 ] && usage

CURRENT=$(cat "$VERSION_FILE" | tr -d '[:space:]')
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

case "$1" in
  major) NEW_VERSION="$((MAJOR + 1)).0.0" ;;
  minor) NEW_VERSION="$MAJOR.$((MINOR + 1)).0" ;;
  patch) NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))" ;;
  *.*.*) NEW_VERSION="$1" ;;
  *) usage ;;
esac

echo "Bumping $CURRENT → $NEW_VERSION"

echo "$NEW_VERSION" > "$VERSION_FILE"

cd "$REPO_DIR"
git add VERSION
git commit -m "chore: bump version to $NEW_VERSION"
git tag "v$NEW_VERSION"
git push origin main --tags

echo "Released v$NEW_VERSION"
echo "GitHub Actions will create the release automatically."
