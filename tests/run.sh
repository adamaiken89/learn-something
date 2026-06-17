#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FAILED=0

echo "========================================="
echo " Learn Anything — Test Suite"
echo "========================================="

# --- Python unit tests ---
echo ""
echo "--- Python unit tests (test_epub.py) ---"
if python3 "$SKILL_DIR/tests/test_epub.py"; then
    echo "Python tests: PASS"
else
    echo "Python tests: FAIL"
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
