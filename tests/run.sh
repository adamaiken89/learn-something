#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FAILED=0

# ── Install Python deps if missing ──────────────────────────────
if ! python3 -c "import typer" 2>/dev/null; then
    echo "Installing Python dependencies (typer, click, pyyaml)..."
    pip3 install --break-system-packages --quiet -r "$SKILL_DIR/requirements.txt" \
        2>&1 | tail -5 || {
        echo "WARNING: pip install failed — some tests may be skipped"
    }
fi

echo "========================================="
echo " Learn Something — Test Suite"
echo "========================================="

# --- Python unit tests ---
echo ""
echo "--- Python unit tests (test_epub.py) ---"
if python3 "$SKILL_DIR/tests/test_epub.py"; then
    echo "EPUB tests: PASS"
else
    echo "EPUB tests: FAIL"
    FAILED=1
fi

echo ""
echo "--- Learn.py tests (test_learn.py) ---"
if python3 "$SKILL_DIR/tests/test_learn.py"; then
    echo "Learn.py tests: PASS"
else
    echo "Learn.py tests: FAIL"
    FAILED=1
fi

# --- Bash integration tests ---
echo ""
echo "--- Bash integration tests (test_epub.sh) ---"
if bash "$SKILL_DIR/tests/test_epub.sh"; then
    echo "Integration tests: PASS"
else
    echo "Integration tests: FAIL"
    FAILED=1
fi

echo ""
echo "========================================="
if [ "$FAILED" -eq 0 ]; then
    echo " All tests passed"
else
    echo " Some tests failed"
fi
echo "========================================="
exit "$FAILED"
