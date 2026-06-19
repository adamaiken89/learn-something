#!/usr/bin/env bash
set -euo pipefail

# Learn Anything CLI — thin wrapper around learn.py
# Usage: learn.sh <command> <subject> [module]
# Commands: init, start, create-module, quiz, explain, feynman, review, stats, export, epub, epub-regen, epub-verify

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$SKILL_DIR/scripts/learn.py" "$@"
