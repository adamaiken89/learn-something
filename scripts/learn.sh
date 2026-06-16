#!/usr/bin/env bash
set -euo pipefail

# Learn Anything CLI
# Usage: learn.sh <command> <subject> [module]
# Commands: init, start, quiz, review, stats, export, epub

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUBJECTS_DIR="$SKILL_DIR/../../subjects"

# Ensure subjects dir exists relative to cwd too
if [ ! -d "$SUBJECTS_DIR" ]; then
  SUBJECTS_DIR="./subjects"
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

check_subject() {
  local subject="$1"
  if [ ! -d "$SUBJECTS_DIR/$subject" ]; then
    echo "Subject '$subject' not found at $SUBJECTS_DIR/$subject"
    echo "Available:"
    ls "$SUBJECTS_DIR" 2>/dev/null || echo "  (no subjects yet)"
    exit 1
  fi
}

cmd_init() {
  local subject="$1"
  local lang="${2:-en}"
  local dir="$SUBJECTS_DIR/$subject"
  if [ -d "$dir" ]; then
    echo "Subject '$subject' already exists"
    exit 1
  fi
  mkdir -p "$dir/modules" "$dir/srs"
  # Copy template, set subject name + language
  sed "s/\"\[Subject\]\"/\"$subject\"/" "$SKILL_DIR/templates/syllabus.yaml" > "$dir/syllabus.yaml"
  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i '' "s/^language: .*/language: $lang/" "$dir/syllabus.yaml"
  else
    sed -i "s/^language: .*/language: $lang/" "$dir/syllabus.yaml"
  fi
  echo "Created $dir (language: $lang)"
  echo "Edit syllabus.yaml, then create modules with: learn.sh create-module <subject> <id>"
}

cmd_start() {
  local subject="$1"
  check_subject "$subject"

  # Show syllabus summary
  local syllabus="$SUBJECTS_DIR/$subject/syllabus.yaml"
  if [ -f "$syllabus" ]; then
    echo -e "${CYAN}=== $subject ===${NC}"
    head -20 "$syllabus" 2>/dev/null || true
    # Show language
    local lang=$(grep "^language:" "$syllabus" 2>/dev/null | awk '{print $2}')
    if [ -n "$lang" ]; then
      echo -e "${GREEN} Language: $lang${NC}"
    fi
    echo ""
  fi

  # List modules
  echo -e "${YELLOW}Modules:${NC}"
  for mod in "$SUBJECTS_DIR/$subject/modules/"*/; do
    local name=$(basename "$mod")
    local lesson="$mod/lesson.md"
    if [ -f "$lesson" ]; then
      echo "  ${CYAN}$name${NC}"
    else
      echo "  ${YELLOW}$name${NC} (no lesson yet)"
    fi
  done
  echo ""
  echo "Open lesson: learn.sh open <subject> <module-id>"
  echo "Take quiz:  learn.sh quiz <subject> <module-id>"
  echo "Review:     learn.sh review <subject>"
}

cmd_quiz() {
  local subject="$1"
  local module="$2"
  local quiz="$SUBJECTS_DIR/$subject/modules/$module/quiz.yaml"

  if [ ! -f "$quiz" ]; then
    echo "No quiz found at $quiz"
    exit 1
  fi

  echo -e "${CYAN}=== $subject / $module Quiz ===${NC}"
  echo ""

  # Parse quiz using python3 (most portable)
  python3 -c "
import yaml, sys, random, json

with open('$quiz') as f:
    questions = yaml.safe_load(f)

random.shuffle(questions)
correct = 0
total = len(questions)

for i, q in enumerate(questions, 1):
    print(f'\\n--- Question {i}/{total} ---')
    print(q[\"question\"])
    opts = list(q[\"options\"].items())
    random.shuffle(opts)
    keymap = {}
    for j, (letter, text) in enumerate(opts):
        key = chr(ord(\"a\") + j)
        keymap[key] = letter
        print(f'  {key}) {text}')

    while True:
        ans = input('\\nYour answer: ').strip().lower()
        if ans in keymap:
            break
        print('Invalid. Choose a-e.')

    if keymap[ans] == q[\"answer\"]:
        print(f'{GREEN}✓ Correct!${NC}')
        correct += 1
    else:
        print(f'{RED}✗ Wrong. Correct: {q[\"answer\"]}{NC}')

    print(f'  {q[\"explanation\"]}')
    print()

print(f'\\nScore: {correct}/{total} ({correct*100//total}%)')

# Update SRS deck
deck_path = '$SUBJECTS_DIR/$subject/srs/deck.json'
try:
    with open(deck_path) as f:
        deck = json.load(f)
except:
    deck = []

from datetime import datetime, timedelta
today = datetime.now().strftime('%Y-%m-%d')

for q in questions:
    cid = q['id']
    existing = None
    for card in deck:
        if card['id'] == cid:
            existing = card
            break

    # Find if user got this right
    was_correct = False
    # Simplified: we only track from deck state, not per-question
    # For now just ensure all MCQs are in deck
    if not existing:
        deck.append({
            'id': cid,
            'question': q['question'],
            'options': q['options'],
            'answer': q['answer'],
            'explanation': q['explanation'],
            'tags': q.get('tags', []),
            'ease_factor': 2.5,
            'interval': 0,
            'repetitions': 0,
            'next_review': today,
            'last_review': None
        })

with open(deck_path, 'w') as f:
    json.dump(deck, f, indent=2)
" 2>&1 | sed "s/{GREEN}/$(printf $GREEN)/g; s/{RED}/$(printf $RED)/g; s/{NC}/$(printf $NC)/g" || {
    echo "Python3 or pyyaml not available."
    echo "Falling back to raw display:"
    cat "$quiz" | head -50
  }
}

cmd_review() {
  local subject="$1"
  local deck="$SUBJECTS_DIR/$subject/srs/deck.json"

  if [ ! -f "$deck" ]; then
    echo "No SRS deck yet. Take a quiz first: learn.sh quiz <subject> <module>"
    exit 1
  fi

  python3 -c "
import json, sys
from datetime import datetime, timedelta

with open('$deck') as f:
    deck = json.load(f)

today = datetime.now().strftime('%Y-%m-%d')
due = [c for c in deck if c.get('next_review', '2000-01-01') <= today]

if not due:
    print('No cards due for review!')
    sys.exit(0)

random.shuffle(due)
correct = 0
total = len(due)

print(f'=== Review: {total} card(s) due ===')
print()

for card in due:
    print(f'Q: {card[\"question\"]}')
    opts = list(card['options'].items())
    import random
    random.shuffle(opts)
    keymap = {}
    for j, (letter, text) in enumerate(opts):
        key = chr(ord('a') + j)
        keymap[key] = letter
        print(f'  {key}) {text}')

    while True:
        ans = input('\\nYour answer: ').strip().lower()
        if ans in keymap:
            break
        print('Invalid.')

    if keymap[ans] == card['answer']:
        print('✓ Correct!')
        quality = 4
        correct += 1
    else:
        print(f'✗ Wrong. Correct: {card[\"answer\"]}')
        quality = 1

    print(f'  {card[\"explanation\"]}')
    print()

    # SM-2 algorithm
    ef = card.get('ease_factor', 2.5)
    rep = card.get('repetitions', 0)
    interval = card.get('interval', 0)

    if quality >= 3:
        if rep == 0:
            interval = 1
        elif rep == 1:
            interval = 6
        else:
            interval = round(interval * ef)
        rep += 1
    else:
        rep = 0
        interval = 1

    ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if ef < 1.3:
        ef = 1.3

    card['ease_factor'] = ef
    card['repetitions'] = rep
    card['interval'] = interval
    card['next_review'] = (datetime.now() + timedelta(days=interval)).strftime('%Y-%m-%d')
    card['last_review'] = today

print(f'\\nScore: {correct}/{total} ({correct*100//total}%)')

with open('$deck', 'w') as f:
    json.dump(deck, f, indent=2)
" 2>&1
}

cmd_stats() {
  local subject="$1"
  check_subject "$subject"

  local deck="$SUBJECTS_DIR/$subject/srs/deck.json"
  if [ ! -f "$deck" ]; then
    echo "No stats yet. Take a quiz first."
    return
  fi

  python3 -c "
import json, sys
from datetime import datetime

with open('$deck') as f:
    deck = json.load(f)

total = len(deck)
if total == 0:
    print('No cards in deck')
    sys.exit(0)

reviewed = [c for c in deck if c.get('last_review')]
due_today = [c for c in deck if c.get('next_review', '2000-01-01') <= datetime.now().strftime('%Y-%m-%d')]
avg_ef = sum(c.get('ease_factor', 2.5) for c in deck) / total

print(f'Cards: {total}')
print(f'Reviewed: {len(reviewed)}')
print(f'Due today: {len(due_today)}')
print(f'Mastered (interval >= 21d): {len([c for c in deck if c.get(\"interval\", 0) >= 21])}')
print(f'Avg ease factor: {avg_ef:.2f}')

# Module breakdown
from collections import Counter
module_counts = Counter(c['id'].split('.')[0] for c in deck)
print()
print('By module:')
for mod in sorted(module_counts):
    print(f'  Module {mod}: {module_counts[mod]} cards')
" 2>&1
}

cmd_explain() {
  local subject="$1"
  local module="$2"
  check_subject "$subject"

  local lesson="$SUBJECTS_DIR/$subject/modules/$module/lesson.md"
  if [ ! -f "$lesson" ]; then
    echo "No lesson found at $lesson"
    exit 1
  fi

  echo -e "${CYAN}=== Feynman Explain: $subject / $module ===${NC}"
  echo ""
  echo "Step 1: Explain the core concept as if teaching a child."
  echo "  - Simplest words. No jargon."
  echo "  - Give concrete example from your daily work."
  echo ""
  echo "Step 2: Self-check your explanation for:"
  echo "  - Vague words: 'stuff', 'things', 'basically', 'kind of'"
  echo "  - Circular reasoning: 'it works because that's how it works'"
  echo "  - Missing steps: did you skip a causal link?"
  echo "  - Unnecessary complexity: can you shorten it?"
  echo ""
  echo "Step 3: Run this command again after refining."
  echo "  For deeper probing, say explanation in opencode chat."
  echo "  AI will find gaps you missed."
  echo ""
  echo -e "${YELLOW}Concept to explain:${NC}"
  grep -A 3 "^## Core Concept\|^## The Core\|Feynman" "$lesson" 2>/dev/null | head -10 || echo "(Read lesson.md for core concept)"
  echo ""
  echo "Lesson: $lesson"
}

cmd_export() {
  local subject="$1"
  local deck="$SUBJECTS_DIR/$subject/srs/deck.json"

  if [ ! -f "$deck" ]; then
    echo "No deck to export."
    exit 1
  fi

  local out="$SUBJECTS_DIR/$subject/srs/deck.csv"
  python3 -c "
import json, csv

with open('$deck') as f:
    deck = json.load(f)

with open('$out', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Question', 'Answer', 'Explanation', 'Tags'])
    for card in deck:
        w.writerow([
            card['question'],
            card['options'][card['answer']],
            card.get('explanation', ''),
            ' '.join(card.get('tags', []))
        ])

print(f'Exported {len(deck)} cards to $out')
print('Import into Anki via: File > Import')
" 2>&1
}

cmd_epub() {
  local subject="$1"
  local out="${2:-$SUBJECTS_DIR/$subject/$subject.epub}"
  check_subject "$subject"

  local dir="$SUBJECTS_DIR/$subject"
  local tmp_dir=$(mktemp -d)
  local md_file="$tmp_dir/book.md"

  echo -e "${CYAN}Building EPUB: $subject${NC}"

  > "$md_file"
  echo "# $subject" >> "$md_file"
  echo "" >> "$md_file"

  local mod_count=0
  for mod in "$dir/modules/"*/; do
    [ -d "$mod" ] || continue
    local name=$(basename "$mod")
    local lesson="$mod/lesson.md"
    local quiz="$mod/quiz.yaml"

    echo "" >> "$md_file"
    echo "---" >> "$md_file"
    echo "" >> "$md_file"

    if [ -f "$lesson" ]; then
      cat "$lesson" >> "$md_file"
      echo "" >> "$md_file"
    fi

    if [ -f "$quiz" ]; then
      echo "## Quiz: $name" >> "$md_file"
      echo "" >> "$md_file"
      # Parse quiz YAML into markdown Q&A
      python3 -c "
import yaml, sys, os
quiz_path = os.environ.get('QUIZ_PATH', '$quiz')
with open(quiz_path) as f:
    questions = yaml.safe_load(f)
for q in questions:
    ans = q['answer']
    print(f'### {q[\"question\"]}')
    for k, v in q['options'].items():
        mark = '✓' if k == ans else ' '
        print(f'- [{mark}] {k}: {v}')
    print()
    print(f'**Answer:** {ans}')
    print(f'**Explanation:** {q[\"explanation\"]}')
    print()
" >> "$md_file" 2>/dev/null || echo "(quiz questions unavailable)" >> "$md_file"
    fi

    ((mod_count++))
  done

  if [ "$mod_count" -eq 0 ]; then
    echo -e "${YELLOW}No modules found in $dir/modules/${NC}"
    rm -rf "$tmp_dir"
    return
  fi

  mkdir -p "$(dirname "$out")"
  rm -f "$out"

  if command -v pandoc &>/dev/null; then
    pandoc "$md_file" -o "$out" --metadata title="$subject" --metadata author="Learn Anything" --toc --toc-depth=2 2>/dev/null || true
  fi

  if [ ! -f "$out" ] && command -v python3 &>/dev/null; then
    python3 "$SKILL_DIR/scripts/epubgen.py" "$md_file" "$out" "$subject" || true
  fi

  if [ -f "$out" ]; then
    local size=$(du -h "$out" | cut -f1)
    echo -e "${GREEN}EPUB: $out ($size)${NC}"
  else
    echo -e "${RED}Failed. Need pandoc or Python 3.${NC}"
    echo "  Install pandoc: brew install pandoc"
  fi

  rm -rf "$tmp_dir"
}

# Main
cmd="${1:-help}"
subject="${2:-}"
module="${3:-}"
lang="${4:-}"

case "$cmd" in
  init)    cmd_init "$subject" "$module" ;;
  start)   cmd_start "$subject" ;;
  quiz)    cmd_quiz "$subject" "$module" ;;
  explain|feynman) cmd_explain "$subject" "$module" ;;
  review)  cmd_review "$subject" ;;
  stats)   cmd_stats "$subject" ;;
  export)  cmd_export "$subject" ;;
  epub)    cmd_epub "$subject" "$module" ;;
  help|*)
    echo "Usage: learn.sh <command> <subject> [module]"
    echo ""
    echo "Commands:"
    echo "  init <subject> [lang]       Create new subject (lang: en|zh|yue, default en)"
    echo "  start <subject>            Show subject overview and modules"
    echo "  quiz <subject> <mod>       Take MCQ quiz"
    echo "  explain <subject> <mod>    Feynman Technique prompt"
    echo "  feynman <subject> <mod>    Alias for explain"
    echo "  review <subject>           Spaced repetition review"
    echo "  stats <subject>            Study statistics"
    echo "  export <subject>           Export to Anki CSV"
  echo "  epub <subject> [file]      Export course to EPUB book"
    ;;
esac
