#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SUBJECTS_DIR="$SKILL_DIR/subjects"
TEST_SUBJECT="test-subject-$$"

cleanup() {
    rm -rf "$SUBJECTS_DIR/$TEST_SUBJECT"
}
trap cleanup EXIT

echo "=== EPUB CLI Integration Tests ==="

# --- test: learn.sh init ---
echo -n "  init subject ... "
"$SKILL_DIR/scripts/learn.sh" init "$TEST_SUBJECT" > /dev/null 2>&1
[ -d "$SUBJECTS_DIR/$TEST_SUBJECT" ] || { echo "FAIL: subject dir missing"; exit 1; }
[ -f "$SUBJECTS_DIR/$TEST_SUBJECT/syllabus.yaml" ] || { echo "FAIL: syllabus missing"; exit 1; }
[ -d "$SUBJECTS_DIR/$TEST_SUBJECT/modules" ] || { echo "FAIL: modules dir missing"; exit 1; }
echo "OK"

# --- create a test module with content ---
echo -n "  create test module ... "
mkdir -p "$SUBJECTS_DIR/$TEST_SUBJECT/modules/01-test-module"
cat > "$SUBJECTS_DIR/$TEST_SUBJECT/modules/01-test-module/lesson.md" << 'EOF'
# Test Module

## Introduction

This is a test module.

### Setup

Run the setup script.

## Advanced

Deep dive into advanced topics.
EOF
echo "OK"

# --- test: learn.sh epub build ---
echo -n "  epub build ... "
EPUB_OUT="$SUBJECTS_DIR/$TEST_SUBJECT/$TEST_SUBJECT.epub"
"$SKILL_DIR/scripts/learn.sh" epub "$TEST_SUBJECT" > /dev/null 2>&1
[ -f "$EPUB_OUT" ] || { echo "FAIL: epub not created"; exit 1; }
echo "OK"

# --- test: epub.py verify ---
echo -n "  epub verify ... "
VERIFY_OUTPUT=$(python3 "$SKILL_DIR/scripts/epub.py" verify "$EPUB_OUT" 2>&1)
echo "$VERIFY_OUTPUT" | grep -q "VALID" || { echo "FAIL: verify failed"; echo "$VERIFY_OUTPUT"; exit 1; }
echo "OK"

# --- test: hierarchical ToC in nav ---
echo -n "  epub ToC structure ... "
python3 -c "
import zipfile, sys
path = '$EPUB_OUT'
with zipfile.ZipFile(path, 'r') as zf:
    nav = zf.read('EPUB/nav.xhtml').decode('utf-8')
    checks = [
        'Test Module' in nav,         # chapter title
        'Introduction' in nav,        # h2 in ToC
        'Setup' in nav,               # h3 in ToC
        'Advanced' in nav,            # h2 in ToC
        'href=\"ch001.xhtml#introduction\"' in nav,
        'href=\"ch001.xhtml#setup\"' in nav,
        'href=\"ch001.xhtml#advanced\"' in nav,
        'href=\"ch001.xhtml\"' in nav,
        '<ol>' in nav,
    ]
    if not all(checks):
        print('FAIL: nav missing entries')
        print(nav[:2000])
        sys.exit(1)
    # verify h1 has id
    ch1 = zf.read('EPUB/ch001.xhtml').decode('utf-8')
    if 'id=\"test-module\"' not in ch1:
        print('FAIL: chapter h1 missing id')
        print(ch1[:500])
        sys.exit(1)
print('OK')
"
echo "  epub ToC structure: OK"

# --- test: epub size ---
echo -n "  epub non-empty ... "
SIZE=$(stat -f%z "$EPUB_OUT" 2>/dev/null || stat -c%s "$EPUB_OUT" 2>/dev/null)
[ "$SIZE" -gt 500 ] || { echo "FAIL: epub too small ($SIZE bytes)"; exit 1; }
echo "OK"

# --- test: epub-regen from cached md ---
echo -n "  epub-regen ... "
"$SKILL_DIR/scripts/learn.sh" epub-regen "$TEST_SUBJECT" > /dev/null 2>&1
[ -f "$EPUB_OUT" ] || { echo "FAIL: epub-regen failed"; exit 1; }
python3 "$SKILL_DIR/scripts/epub.py" verify "$EPUB_OUT" 2>&1 | grep -q "VALID" || { echo "FAIL: regen verify failed"; exit 1; }
echo "OK"

# --- test: explicit --title via epub.py ---
echo -n "  title formatting ... "
python3 -c "
import sys
sys.path.insert(0, '$SKILL_DIR/scripts')
import epub
assert epub._format_title('advanced-react-19') == 'Advanced React 19'
assert epub._format_title('python-basics') == 'Python Basics'
print('OK')
"
echo "  title formatting: OK"

# --- test: epub from-md with kebab title ---
echo -n "  epub from-md title formatting ... "
TMP_MD=$(mktemp)
TMP_EPUB=$(mktemp).epub
echo '# Chapter' > "$TMP_MD"
python3 "$SKILL_DIR/scripts/epub.py" from-md "$TMP_MD" "$TMP_EPUB" 2>&1 | grep -q "1 chapter"
python3 -c "
import zipfile
with zipfile.ZipFile('$TMP_EPUB', 'r') as zf:
    opf = zf.read('EPUB/content.opf').decode('utf-8')
    assert '<dc:title>Tmp</dc:title>' in opf, f'title not formatted: {opf[:500]}'
print('OK')
"
rm -f "$TMP_MD" "$TMP_EPUB"
echo "  epub from-md title formatting: OK"

echo -e "\n=== All CLI tests passed ==="
