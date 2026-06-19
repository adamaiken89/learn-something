#!/usr/bin/env python3
"""Learn Anything CLI — study with spaced repetition (SM-2).

Usage:
  learn.py init <subject> [lang]
  learn.py start <subject>
  learn.py create-module <subject> <module-id> [--name NAME]
  learn.py quiz <subject> <module>
  learn.py explain <subject> <module>
  learn.py feynman <subject> <module>
  learn.py review <subject>
  learn.py stats <subject>
  learn.py export <subject>
   learn.py epub <subject> [output] [--mermaid api|local|off]
   learn.py epub-regen <subject> [output] [--mermaid api|local|off]
   learn.py epub-verify <subject> [output]
   learn.py pdf <subject> [output] [--engine auto|weasyprint|pandoc|raw]
   learn.py pdf-regen <subject> [output] [--engine auto|weasyprint|pandoc|raw]
"""

import argparse
import csv
import json
import os
import random
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).resolve().parent.parent


def _get_subjects_dir():
    candidates = [
        SKILL_DIR / '..' / '..' / 'subjects',
        Path.cwd() / 'subjects',
    ]
    for d in candidates:
        if d.resolve().exists():
            return d.resolve()
    return (Path.cwd() / 'subjects').resolve()


SUBJECTS_DIR = _get_subjects_dir()

# ── Colors ─────────────────────────────────────────────────────


class C:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'


def cval(val):
    """Return ANSI color code, stripping escapes if output not a TTY."""
    return val if sys.stdout.isatty() else ''


RED = cval(C.RED)
GREEN = cval(C.GREEN)
YELLOW = cval(C.YELLOW)
CYAN = cval(C.CYAN)
BOLD = cval(C.BOLD)
NC = cval(C.NC)

# ── SM-2 Algorithm ─────────────────────────────────────────────


def sm2_update(card, quality):
    """Update card's SM-2 fields given quality (0-5). Returns updated card."""
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

    card['ease_factor'] = round(ef, 2)
    card['repetitions'] = rep
    card['interval'] = interval
    card['next_review'] = (datetime.now() + timedelta(days=interval)).strftime('%Y-%m-%d')
    card['last_review'] = datetime.now().strftime('%Y-%m-%d')
    return card


# ── Subject helpers ─────────────────────────────────────────────


def _subject_path(subject):
    return SUBJECTS_DIR / subject


def _check_subject(subject):
    path = _subject_path(subject)
    if not path.exists():
        print(f"{RED}Subject '{subject}' not found at {path}{NC}")
        print('Available:')
        _list_subjects()
        sys.exit(1)
    return path


def _list_subjects():
    if SUBJECTS_DIR.exists():
        for d in sorted(SUBJECTS_DIR.iterdir()):
            if d.is_dir():
                print(f'  {d.name}')
    else:
        print('  (no subjects yet)')


def _module_path(subject, module):
    return _subject_path(subject) / 'modules' / module


def _check_module(subject, module):
    path = _module_path(subject, module)
    if not path.exists():
        print(f"{RED}Module '{module}' not found in '{subject}'{NC}")
        sys.exit(1)
    return path


def _list_modules(subject):
    path = _subject_path(subject) / 'modules'
    if not path.exists():
        return []
    return sorted(d.name for d in path.iterdir() if d.is_dir() and (d / 'lesson.md').exists())


def _load_deck(subject):
    deck_path = _subject_path(subject) / 'srs' / 'deck.json'
    if deck_path.exists():
        with open(deck_path) as f:
            return json.load(f)
    return []


def _save_deck(subject, deck):
    path = _subject_path(subject) / 'srs' / 'deck.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(deck, f, indent=2)


def _load_stats(subject):
    path = _subject_path(subject) / 'srs' / 'stats.json'
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {'sessions': []}


def _save_stats(subject, stats):
    path = _subject_path(subject) / 'srs' / 'stats.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(stats, f, indent=2)


def _record_session(subject, session_type, module=None, score=None, total=None):
    stats = _load_stats(subject)
    record = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'type': session_type,
        'subject': subject,
    }
    if module:
        record['module'] = module
    if score is not None:
        record['score'] = score
    if total is not None:
        record['total'] = total
    stats['sessions'].append(record)
    _save_stats(subject, stats)


# ── Commands ────────────────────────────────────────────────────


def cmd_init(args):
    subject = args.subject
    lang = args.lang or 'en'
    path = _subject_path(subject)
    if path.exists():
        print(f"{RED}Subject '{subject}' already exists{NC}")
        sys.exit(1)

    (path / 'modules').mkdir(parents=True, exist_ok=True)
    (path / 'srs').mkdir(parents=True, exist_ok=True)

    syllabus_template = SKILL_DIR / 'templates' / 'syllabus.yaml'
    if syllabus_template.exists():
        with open(syllabus_template) as f:
            content = f.read()
        content = content.replace('"[Subject]"', f'"{subject}"')
        content = re.sub(r'^language: .*', f'language: {lang}', content, flags=re.MULTILINE)
        with open(path / 'syllabus.yaml', 'w') as f:
            f.write(content)
    else:
        print(f'{YELLOW}Warning: syllabus template not found{NC}')

    print(f'{GREEN}Created {path} (language: {lang}){NC}')
    print(
        f'Edit syllabus.yaml, then create modules with: learn.py create-module {subject} <module-id>'
    )


def cmd_start(args):
    subject = args.subject
    spath = _check_subject(subject)

    syllabus = spath / 'syllabus.yaml'
    if syllabus.exists():
        lines = syllabus.read_text().splitlines()
        for line in lines[:20]:
            print(line)
        lang_match = None
        for line in lines:
            m = re.match(r'^language:\s*(\S+)', line)
            if m:
                lang_match = m.group(1)
                break
        if lang_match:
            print(f'{GREEN} Language: {lang_match}{NC}')
        print()

    print(f'{YELLOW}Modules:{NC}')
    mods_dir = spath / 'modules'
    if mods_dir.exists():
        for mod in sorted(mods_dir.iterdir()):
            if mod.is_dir():
                lesson = mod / 'lesson.md'
                if lesson.exists():
                    print(f'  {CYAN}{mod.name}{NC}')
                else:
                    print(f'  {YELLOW}{mod.name}{NC} (no lesson yet)')

    print()
    print(f'Open lesson: learn.py open {subject} <module-id>')
    print(f'Take quiz:  learn.py quiz {subject} <module-id>')
    print(f'Review:     learn.py review {subject}')


def cmd_create_module(args):
    subject = args.subject
    module_id = args.module_id
    name = args.name or module_id
    _check_subject(subject)

    mod_path = _module_path(subject, module_id)
    if mod_path.exists():
        print(f"{RED}Module '{module_id}' already exists in '{subject}'{NC}")
        sys.exit(1)

    mod_path.mkdir(parents=True, exist_ok=True)

    # Copy lesson template
    lesson_tpl = SKILL_DIR / 'templates' / 'module.md'
    if lesson_tpl.exists():
        with open(lesson_tpl) as f:
            content = f.read()
        content = content.replace('[Title]', name)
        content = content.replace('Module N:', f'Module {module_id}:')
        with open(mod_path / 'lesson.md', 'w') as f:
            f.write(content)

    # Copy quiz template
    quiz_tpl = SKILL_DIR / 'templates' / 'quiz.yaml'
    if quiz_tpl.exists():
        shutil.copy2(quiz_tpl, mod_path / 'quiz.yaml')

    print(f'{GREEN}Created module: {mod_path}{NC}')
    print('  lesson.md — edit content')
    print('  quiz.yaml — add 8-10 MCQs')


def cmd_quiz(args):
    subject = args.subject
    module = args.module
    _check_subject(subject)
    _check_module(subject, module)

    quiz_path = _module_path(subject, module) / 'quiz.yaml'
    if not quiz_path.exists():
        print(f'{RED}No quiz found at {quiz_path}{NC}')
        sys.exit(1)

    try:
        import yaml
    except ImportError:
        print(f'{RED}Python yaml library required. Install: pip install pyyaml{NC}')
        print(f'{YELLOW}Raw quiz content:{NC}')
        with open(quiz_path) as f:
            print(f.read())
        sys.exit(1)

    with open(quiz_path) as f:
        questions = yaml.safe_load(f)

    if not questions:
        print(f'{YELLOW}No questions in quiz{NC}')
        return

    random.shuffle(questions)
    correct = 0
    total = len(questions)

    deck = _load_deck(subject)

    print(f'{CYAN}=== {subject} / {module} Quiz ==={NC}\n')

    for i, q in enumerate(questions, 1):
        print(f'--- Question {i}/{total} ---')
        print(q['question'])
        opts = list(q.get('options', {}).items())
        random.shuffle(opts)
        keymap = {}
        for j, (letter, text) in enumerate(opts):
            key = chr(ord('a') + j)
            keymap[key] = letter
            print(f'  {key}) {text}')

        while True:
            try:
                ans = input('\nYour answer: ').strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if ans in keymap:
                break
            valid_range = f'{min(keymap)}-{max(keymap)}'
            print(f'Invalid. Choose {valid_range}.')

        is_correct = keymap[ans] == q.get('answer', '')
        if is_correct:
            print(f'{GREEN}✓ Correct!{NC}')
            quality = 4
            correct += 1
        else:
            print(f'{RED}✗ Wrong. Correct: {q.get("answer", "?")}{NC}')
            quality = 1

        explanation = q.get('explanation', '')
        if explanation:
            print(f'  {explanation}')
        print()

        # ── SRS update: create or update card with SM-2 ──
        cid = q.get('id', f'{module}.{i}')
        existing = None
        for card in deck:
            if card['id'] == cid:
                existing = card
                break

        if existing:
            sm2_update(existing, quality)
        else:
            card = {
                'id': cid,
                'question': q['question'],
                'options': q['options'],
                'answer': q['answer'],
                'explanation': q.get('explanation', ''),
                'tags': q.get('tags', []),
                'ease_factor': 2.5,
                'interval': 0,
                'repetitions': 0,
                'next_review': datetime.now().strftime('%Y-%m-%d'),
                'last_review': None,
            }
            sm2_update(card, quality)
            deck.append(card)

    _save_deck(subject, deck)

    pct = correct * 100 // total if total else 0
    print(f'\nScore: {correct}/{total} ({pct}%)')
    _record_session(subject, 'quiz', module=module, score=correct, total=total)


def cmd_explain(args):
    subject = args.subject
    module = args.module
    _check_subject(subject)
    _check_module(subject, module)

    lesson_path = _module_path(subject, module) / 'lesson.md'
    if not lesson_path.exists():
        print(f'{RED}No lesson found at {lesson_path}{NC}')
        sys.exit(1)

    print(f'{CYAN}=== Feynman Explain: {subject} / {module} ==={NC}')
    print()
    print('Step 1: Explain the core concept as if teaching a child.')
    print('  - Simplest words. No jargon.')
    print('  - Give concrete example from your daily work.')
    print()
    print('Step 2: Self-check your explanation for:')
    print("  - Vague words: 'stuff', 'things', 'basically', 'kind of'")
    print("  - Circular reasoning: 'it works because that's how it works'")
    print('  - Missing steps: did you skip a causal link?')
    print('  - Unnecessary complexity: can you shorten it?')
    print()
    print('Step 3: Run this command again after refining.')
    print('  For deeper probing, say explanation in opencode chat.')
    print('  AI will find gaps you missed.')
    print()
    print(f'{YELLOW}Concept to explain:{NC}')
    lines = lesson_path.read_text().splitlines()
    found = False
    for i, line in enumerate(lines):
        if re.match(r'^## (Core Concept|The Core|Feynman)', line):
            print(line)
            for extra in lines[i + 1 : i + 4]:
                print(extra)
            found = True
            break
    if not found:
        print('(no core concept heading found)')
    print()
    print(f'Lesson: {lesson_path}')


def cmd_review(args):
    subject = args.subject
    _check_subject(subject)

    deck = _load_deck(subject)
    if not deck:
        print(f'{YELLOW}No SRS deck yet. Take a quiz first: learn.py quiz {subject} <module>{NC}')
        return

    today = datetime.now().strftime('%Y-%m-%d')
    due = [c for c in deck if c.get('next_review', '2000-01-01') <= today]

    if not due:
        print(f'{GREEN}No cards due for review!{NC}')
        return

    random.shuffle(due)
    correct = 0
    total = len(due)

    print(f'{CYAN}=== Review: {total} card(s) due ==={NC}\n')

    for card in due:
        print(f'Q: {card["question"]}')
        opts = list(card.get('options', {}).items())
        random.shuffle(opts)
        keymap = {}
        for j, (letter, text) in enumerate(opts):
            key = chr(ord('a') + j)
            keymap[key] = letter
            print(f'  {key}) {text}')

        answered = False
        while True:
            try:
                ans = input('\nYour answer: ').strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if ans in keymap:
                answered = True
                break
            valid_range = f'{min(keymap)}-{max(keymap)}'
            print(f'Invalid. Choose {valid_range}.')

        if not answered:
            break
        is_correct = keymap[ans] == card['answer']

        if is_correct:
            print(f'{GREEN}✓ Correct!{NC}')
            quality = 4
            correct += 1
        else:
            print(f'{RED}✗ Wrong. Correct: {card["answer"]}{NC}')
            quality = 1

        explanation = card.get('explanation', '')
        if explanation:
            print(f'  {explanation}')
        print()

        sm2_update(card, quality)

    _save_deck(subject, deck)

    if total > 0:
        pct = correct * 100 // total
        print(f'\nScore: {correct}/{total} ({pct}%)')
        _record_session(subject, 'review', score=correct, total=total)


def cmd_stats(args):
    subject = args.subject
    _check_subject(subject)

    deck = _load_deck(subject)
    if not deck:
        print(f'{YELLOW}No stats yet. Take a quiz first.{NC}')
        return

    total = len(deck)
    reviewed = [c for c in deck if c.get('last_review')]
    today = datetime.now().strftime('%Y-%m-%d')
    due_today = [c for c in deck if c.get('next_review', '2000-01-01') <= today]
    mastered = [c for c in deck if c.get('interval', 0) >= 21]
    avg_ef = sum(c.get('ease_factor', 2.5) for c in deck) / total

    print(f'Cards: {total}')
    print(f'Reviewed: {len(reviewed)}')
    print(f'Due today: {len(due_today)}')
    print(f'Mastered (interval >= 21d): {len(mastered)}')
    print(f'Avg ease factor: {avg_ef:.2f}')
    print()

    # Module breakdown
    module_counts = Counter()
    for c in deck:
        mod = c['id'].split('.')[0] if '.' in c['id'] else '?'
        module_counts[mod] += 1
    print('By module:')
    for mod in sorted(module_counts):
        print(f'  Module {mod}: {module_counts[mod]} cards')

    # Session history
    stats = _load_stats(subject)
    if stats.get('sessions'):
        print()
        print('Recent sessions:')
        for s in stats['sessions'][-5:]:
            parts = [s['date'], s['type']]
            if s.get('module'):
                parts.append(s['module'])
            if s.get('score') is not None and s.get('total') is not None:
                parts.append(f'{s["score"]}/{s["total"]}')
            print(f'  {" | ".join(parts)}')


def cmd_export(args):
    subject = args.subject
    _check_subject(subject)

    deck = _load_deck(subject)
    if not deck:
        print(f'{YELLOW}No deck to export.{NC}')
        return

    out_path = _subject_path(subject) / 'srs' / 'deck.csv'
    with open(out_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Question', 'Answer', 'Explanation', 'Tags'])
        for card in deck:
            w.writerow(
                [
                    card.get('question', ''),
                    card.get('options', {}).get(card.get('answer', ''), ''),
                    card.get('explanation', ''),
                    ' '.join(card.get('tags', [])),
                ]
            )

    print(f'{GREEN}Exported {len(deck)} cards to {out_path}{NC}')
    print('Import into Anki via: File > Import')


def cmd_epub(args):
    subject = args.subject
    output = args.output
    mermaid = args.mermaid
    description = args.description

    _check_subject(subject)
    spath = _subject_path(subject)

    if not output:
        output = str(spath / f'{subject}.epub')

    epub_script = SKILL_DIR / 'scripts' / 'epub.py'
    if not epub_script.exists():
        print(f'{RED}epub.py not found at {epub_script}{NC}')
        sys.exit(1)

    cmd = [sys.executable, str(epub_script), 'build', str(spath), output, '--mermaid', mermaid]
    if description:
        cmd.extend(['--description', description])

    print(f'{CYAN}Building EPUB: {subject}{NC}')
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, file=sys.stderr, end='')

    if os.path.exists(output):
        size_kb = os.path.getsize(output) / 1024
        print(f'{GREEN}EPUB: {output} ({size_kb:.1f} KB){NC}')
    else:
        print(f'{RED}Failed{NC}')
        sys.exit(1)


def _pdf_extra_args(args):
    cmd = []
    if args.title:
        cmd.extend(['--title', args.title])
    if args.author:
        cmd.extend(['--author', args.author])
    cmd.extend(['--engine', args.engine])
    return cmd


def cmd_pdf(args):
    subject = args.subject
    output = args.output

    _check_subject(subject)
    spath = _subject_path(subject)

    if not output:
        output = str(spath / f'{subject}.pdf')

    pdf_script = SKILL_DIR / 'scripts' / 'pdf.py'
    if not pdf_script.exists():
        print(f'{RED}pdf.py not found at {pdf_script}{NC}')
        sys.exit(1)

    print(f'{CYAN}Building PDF: {subject}{NC}')
    cmd = [sys.executable, str(pdf_script), 'build', str(spath), output] + _pdf_extra_args(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, file=sys.stderr, end='')

    if os.path.exists(output):
        size_kb = os.path.getsize(output) / 1024
        print(f'{GREEN}PDF: {output} ({size_kb:.1f} KB){NC}')
    else:
        print(f'{RED}Failed{NC}')
        sys.exit(1)


def cmd_pdf_regen(args):
    subject = args.subject
    output = args.output

    _check_subject(subject)
    spath = _subject_path(subject)
    book_md = spath / 'book.md'

    if not book_md.exists():
        print(f"{YELLOW}No book.md. Run 'pdf' first.{NC}")
        return

    if not output:
        output = str(spath / f'{subject}.pdf')

    pdf_script = SKILL_DIR / 'scripts' / 'pdf.py'
    if not pdf_script.exists():
        print(f'{RED}pdf.py not found at {pdf_script}{NC}')
        sys.exit(1)

    print(f'{CYAN}Regenerating PDF from cached markdown: {subject}{NC}')
    cmd = [sys.executable, str(pdf_script), 'from-md', str(book_md), output] + _pdf_extra_args(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, file=sys.stderr, end='')

    if os.path.exists(output):
        size_kb = os.path.getsize(output) / 1024
        print(f'{GREEN}PDF: {output} ({size_kb:.1f} KB){NC}')
    else:
        print(f'{RED}Failed{NC}')
        sys.exit(1)


def cmd_epub_regen(args):
    subject = args.subject
    output = args.output
    mermaid = args.mermaid
    description = args.description

    _check_subject(subject)
    spath = _subject_path(subject)
    book_md = spath / 'book.md'

    if not book_md.exists():
        print(f"{YELLOW}No book.md. Run 'epub' first.{NC}")
        return

    if not output:
        output = str(spath / f'{subject}.epub')

    epub_script = SKILL_DIR / 'scripts' / 'epub.py'
    if not epub_script.exists():
        print(f'{RED}epub.py not found at {epub_script}{NC}')
        sys.exit(1)

    cmd = [sys.executable, str(epub_script), 'from-md', str(book_md), output, '--mermaid', mermaid]
    if description:
        cmd.extend(['--description', description])

    print(f'{CYAN}Regenerating EPUB from cached markdown: {subject}{NC}')
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, file=sys.stderr, end='')

    if os.path.exists(output):
        size_kb = os.path.getsize(output) / 1024
        print(f'{GREEN}EPUB: {output} ({size_kb:.1f} KB){NC}')
    else:
        print(f'{RED}Failed{NC}')
        sys.exit(1)


def cmd_epub_verify(args):
    subject = args.subject
    output = args.output

    _check_subject(subject)
    spath = _subject_path(subject)

    if not output:
        epub_path = spath / f'{subject}.epub'
    else:
        epub_path = Path(output)

    if not epub_path.exists():
        print(f'{RED}EPUB not found: {epub_path}{NC}')
        return

    epub_script = SKILL_DIR / 'scripts' / 'epub.py'
    if not epub_script.exists():
        print(f'{RED}epub.py not found at {epub_script}{NC}')
        sys.exit(1)

    print(f'{CYAN}Verifying EPUB: {subject}{NC}')
    result = subprocess.run(
        [sys.executable, str(epub_script), 'verify', str(epub_path)],
        capture_output=True,
        text=True,
    )
    print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, file=sys.stderr, end='')


# ── CLI Parser ──────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description='Learn Anything — study with spaced repetition (SM-2)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  init <subject> [lang]        Create new subject (lang: en|zh|yue, default en)
  start <subject>              Show subject overview and modules
  create-module <sub> <mod>    Create new module from template
  quiz <subject> <mod>         Take MCQ quiz
  explain <subject> <mod>      Feynman Technique prompt
  feynman <subject> <mod>      Alias for explain
  review <subject>             Spaced repetition review
  stats <subject>              Study statistics
  export <subject>             Export to Anki CSV
  epub <subject> [file]        Export course to EPUB book
  epub-regen <subject> [file]  Regenerate EPUB from cached markdown
  epub-verify <subject> [file] Validate EPUB structure
  pdf <subject> [file]         Export course to PDF
  pdf-regen <subject> [file]   Regenerate PDF from cached book.md
        """,
    )
    sub = parser.add_subparsers(dest='command')
    sub.required = True

    p = sub.add_parser('init', help='Create new subject')
    p.add_argument('subject')
    p.add_argument('lang', nargs='?', default='en')

    p = sub.add_parser('start', help='Show subject overview')
    p.add_argument('subject')

    p = sub.add_parser('create-module', help='Create new module from template')
    p.add_argument('subject')
    p.add_argument('module_id')
    p.add_argument('--name', default=None, help='Human-readable module name')

    p = sub.add_parser('quiz', help='Take MCQ quiz')
    p.add_argument('subject')
    p.add_argument('module')

    p = sub.add_parser('explain', help='Feynman Technique prompt')
    p.add_argument('subject')
    p.add_argument('module')

    p = sub.add_parser('feynman', help='Feynman Technique prompt (alias)')
    p.add_argument('subject')
    p.add_argument('module')

    p = sub.add_parser('review', help='Spaced repetition review')
    p.add_argument('subject')

    p = sub.add_parser('stats', help='Study statistics')
    p.add_argument('subject')

    p = sub.add_parser('export', help='Export to Anki CSV')
    p.add_argument('subject')

    p = sub.add_parser('epub', help='Export course to EPUB')
    p.add_argument('subject')
    p.add_argument('output', nargs='?', default=None)
    p.add_argument('--description', default='', help='Cover page description')
    p.add_argument(
        '--mermaid',
        default='api',
        choices=['api', 'local', 'off'],
        help='Mermaid rendering mode: api (default), local (mmdc CLI), off (skip)',
    )

    p = sub.add_parser('epub-regen', help='Regenerate EPUB from cached book.md')
    p.add_argument('subject')
    p.add_argument('output', nargs='?', default=None)
    p.add_argument('--description', default='', help='Cover page description')
    p.add_argument(
        '--mermaid',
        default='api',
        choices=['api', 'local', 'off'],
        help='Mermaid rendering mode: api (default), local (mmdc CLI), off (skip)',
    )

    p = sub.add_parser('epub-verify', help='Validate EPUB structure')
    p.add_argument('subject')
    p.add_argument('output', nargs='?', default=None)

    p = sub.add_parser('pdf', help='Export course to PDF')
    p.add_argument('subject')
    p.add_argument('output', nargs='?', default=None)
    p.add_argument('--title', default=None, help='PDF title (default: subject dir name)')
    p.add_argument('--author', default='Learn Anything', help='PDF author')
    p.add_argument(
        '--engine',
        default='auto',
        choices=['auto', 'weasyprint', 'pandoc', 'raw'],
        help='PDF engine: auto (default), weasyprint, pandoc, raw (stdlib)',
    )

    p = sub.add_parser('pdf-regen', help='Regenerate PDF from cached book.md')
    p.add_argument('subject')
    p.add_argument('output', nargs='?', default=None)
    p.add_argument('--title', default=None, help='PDF title (default: subject dir name)')
    p.add_argument('--author', default='Learn Anything', help='PDF author')
    p.add_argument(
        '--engine',
        default='auto',
        choices=['auto', 'weasyprint', 'pandoc', 'raw'],
        help='PDF engine: auto (default), weasyprint, pandoc, raw (stdlib)',
    )

    sub.add_parser('help', help='Show this help message')

    args = parser.parse_args()

    if args.command == 'help':
        parser.print_help()
        return

    # Dispatch
    dispatch = {
        'init': cmd_init,
        'start': cmd_start,
        'create-module': cmd_create_module,
        'quiz': cmd_quiz,
        'explain': cmd_explain,
        'feynman': cmd_explain,
        'review': cmd_review,
        'stats': cmd_stats,
        'export': cmd_export,
        'epub': cmd_epub,
        'epub-regen': cmd_epub_regen,
        'epub-verify': cmd_epub_verify,
        'pdf': cmd_pdf,
        'pdf-regen': cmd_pdf_regen,
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
