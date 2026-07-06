#!/usr/bin/env bash
set -euo pipefail

# Learn Something CLI — thin wrapper around learn.py
# Usage: learn.sh <command> <subject> [module]
# Commands: init, start, create-module, create-cloze, quiz, cloze, cumulative-quiz, explain, review, blurting, stats, analytics, forecast, study-plan, fsrs-predict, rate, flag, feedback, export, epub, epub-regen, epub-verify, epub-list-themes, pdf, pdf-regen, sync, sync-pull, validate [module], validate-content (deprecated → validate), mindmap, balance-quiz, checksyntax
# Run from the subjects dir (e.g. ~/.coursereader/subjects).

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$SKILL_DIR/scripts/learn.py" "$@"
