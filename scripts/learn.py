#!/usr/bin/env python3
"""Learn Something CLI — study with spaced repetition (FSRS-5).

Usage:
  learn.py init <topic> [lang] [--depth survey|standard|deep] [--pretest]
  learn.py start <topic>
  learn.py create-module <topic> <module-id> [--name NAME]
  learn.py quiz <topic> <module> [--weak-only] [--adaptive]
  learn.py explain <topic> <module>
  learn.py feynman <topic> <module>
  learn.py review <topic>
  learn.py stats <topic>
  learn.py export <topic>
  learn.py rate <topic> <module> <score> [--comment TEXT]
  learn.py flag <topic> <module> <type> [--detail TEXT]
  learn.py feedback <topic>
  learn.py analytics <topic>
  learn.py forecast <topic>
  learn.py study-plan <topic>
   learn.py epub <topic> [output] [--mermaid api|local|off]
   learn.py epub-regen <topic> [output] [--mermaid api|local|off]
   learn.py epub-verify <topic> [output]
   learn.py pdf <topic> [output] [--engine auto|weasyprint|pandoc|raw]
   learn.py pdf-regen <topic> [output] [--engine auto|weasyprint|pandoc|raw]
   learn.py validate-content <topic> [module]
"""

import csv
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

import sm2 as _sm2
import typer

try:
    import yaml
except ImportError:
    yaml = None

# ── Paths ──────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).resolve().parent.parent
SUBJECTS_DIR = Path.cwd()

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

# ── SRS Algorithm ──────────────────────────────────────────────

sm2_update = _sm2.update


# ── Topic helpers ───────────────────────────────────────────────


def _topic_path(topic):
    return SUBJECTS_DIR / topic


def _check_topic(topic):
    path = _topic_path(topic)
    if not path.exists():
        print(f'{RED}Topic "{topic}" not found. Run: learn.py init {topic}{NC}')
        sys.exit(1)
    return path


MODULE_ID_RE = re.compile(r'^\d{2}-[a-z0-9]+(-[a-z0-9]+)*$')


def _module_path(topic, module):
    return _topic_path(topic) / 'modules' / module


def _check_module(topic, module):
    path = _module_path(topic, module)
    if not path.exists():
        print(f"{RED}Module '{module}' not found in '{topic}'{NC}")
        sys.exit(1)
    if not MODULE_ID_RE.match(module):
        print(f"{YELLOW}Warning: '{module}' doesn't follow NN-name convention (e.g., 01-intro){NC}")
    return path


# ── Syllabus Generation ────────────────────────────────────────


# Depth presets: (module_count, time_per_module_range, time_budget)
_DEPTH_PRESETS = {
    'survey': {'modules': 6, 'time_min': 1.5, 'time_max': 2.0, 'budget': 12},
    'standard': {'modules': 18, 'time_min': 1.5, 'time_max': 2.5, 'budget': 40},
    'deep': {'modules': 28, 'time_min': 2.0, 'time_max': 3.0, 'budget': 75},
}


def _pretty_title(topic):
    """Derive a human-readable title from a kebab/snake topic slug."""
    return topic.replace('_', ' ').replace('-', ' ').title()


def _generate_syllabus(topic, lang, depth):
    """Generate a skeleton syllabus YAML with the given depth."""
    preset = _DEPTH_PRESETS.get(depth, _DEPTH_PRESETS['standard'])
    n = preset['modules']
    t_min, t_max = preset['time_min'], preset['time_max']
    budget = preset['budget']
    title = _pretty_title(topic)

    lines = []
    lines.append(f'subject: "{title}"')
    lines.append(f'language: {lang}')
    lines.append(f'time_budget_hours: {budget}')
    lines.append('target_level: intermediate')
    lines.append(f'domain: "{topic}"')
    lines.append('prerequisites: []')
    lines.append('learning_objectives:')
    for i in range(1, min(4, n // 3 + 1)):
        lines.append(f'  - "[Objective {i}]"')
    lines.append(f'# Depth: {depth} ({n} modules, ~{budget}h)')
    lines.append('')
    lines.append('modules:')

    # Generate meaningful module names based on position
    def _module_name(idx, total):
        if idx == 1:
            return f'Introduction to {title}'
        elif idx == total:
            return f'{title}: Review and Practice'
        elif idx == 2:
            return f'{title}: Core Concepts'
        elif idx <= total // 3:
            return f'{title}: Fundamentals {idx}'
        elif idx <= 2 * total // 3:
            return f'{title}: Intermediate Topics'
        else:
            return f'{title}: Advanced Topics'

    for i in range(1, n + 1):
        t = round(random.uniform(t_min, t_max), 1)
        # Build prerequisites: depends on earlier modules
        prereqs = []
        if i > 1:
            candidates = list(range(1, i))
            if len(candidates) > 2:
                candidates = candidates[-2:]
            prereqs = random.sample(candidates, min(len(candidates), 2))
            prereqs.sort()

        name = _module_name(i, n)
        lines.append(f'  - id: {i}')
        lines.append(f'    name: "{name}"')
        lines.append(f'    time_hours: {t}')
        lines.append(f'    prerequisites: {prereqs}')
        lines.append('    topics: [topic1, topic2]')

    return '\n'.join(lines) + '\n'


def _run_pretest(topic):
    """Quick pre-test: ask 1 question per syllabus module, skip known ones."""
    path = _topic_path(topic)
    syllabus_path = path / 'syllabus.yaml'
    if not syllabus_path.exists():
        return

    # Parse syllabus to get module count
    with open(syllabus_path) as f:
        content = f.read()

    module_names = re.findall(r'name:\s*"(.+?)"', content)
    if not module_names:
        return

    print(f'  {len(module_names)} modules found. Testing 1 question each.\n')
    print('  Rate your knowledge for each module: y = I know this well, n = keep in plan\n')

    skip_count = 0
    skip_modules = []
    for i, name in enumerate(module_names, 1):
        print(f'  [{i}/{len(module_names)}] Module: {name}')
        print('    Are you comfortable with the basics of this topic? (y/n): ', end='')

        try:
            answer = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if answer in ('y', 'yes', 's', 'skip'):
            skip_count += 1
            skip_modules.append(name)
            print(f'    -> Will skip "{name}"\n')
        else:
            print('    -> Kept in plan\n')

    if skip_modules:
        print(
            f'{GREEN}Pre-test complete: {skip_count}/{len(module_names)} modules marked as known.{NC}'
        )
        print(f'Known modules: {", ".join(skip_modules)}')
        print('\nTip: Edit syllabus.yaml to remove known modules before creating content.')
    else:
        print(f'{YELLOW}Pre-test complete: no modules skipped.{NC}')


def _list_modules(topic):
    path = _topic_path(topic) / 'modules'
    if not path.exists():
        return []
    return sorted(d.name for d in path.iterdir() if d.is_dir() and (d / 'lesson.md').exists())


def _load_deck(topic):
    """Load deck in Reader format: {"cards": {"id": card}}."""
    deck_path = _topic_path(topic) / 'srs' / 'deck.json'
    if deck_path.exists():
        with open(deck_path) as f:
            data = json.load(f)
        # Auto-migrate old array format to new dict format
        if isinstance(data, list):
            return _migrate_deck_array(data, topic)
        if 'cards' in data:
            return data
        return {'cards': {}}
    return {'cards': {}}


def _migrate_deck_array(old_deck, topic):
    """Convert old array-format deck to Reader-compatible dict format."""
    new_cards = {}
    for card in old_deck:
        cid = card.get('id', '')
        if '.' in cid:
            parts = cid.split('.', 1)
            module_id = parts[0]
        else:
            module_id = 'unknown'
        new_card = {
            'id': f'{topic}-{module_id}-{cid}',
            'questionId': cid,
            'moduleId': module_id,
            'courseId': topic,
            'question': card.get('question', ''),
            'answer': f'{card.get("answer", "a")}. {card.get("options", {}).get(card.get("answer", "a"), "")}',
            'explanation': card.get('explanation', ''),
            'easeFactor': card.get('ease_factor', 2.5),
            'interval': card.get('interval', 0),
            'repetitions': card.get('repetitions', 0),
            'nextReviewDate': card.get('next_review', datetime.now().strftime('%Y-%m-%d')),
            'lastReviewed': card.get('last_review'),
            'isStarred': False,
        }
        new_cards[new_card['id']] = new_card
    migrated = {'cards': new_cards}
    _save_deck(topic, migrated)
    return migrated


def _save_deck(topic, deck):
    """Save deck in Reader format: {"cards": {"id": card}}."""
    path = _topic_path(topic) / 'srs' / 'deck.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(deck, f, indent=2)


def _load_stats(topic):
    path = _topic_path(topic) / 'srs' / 'stats.json'
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {'sessions': []}


def _save_stats(topic, stats):
    path = _topic_path(topic) / 'srs' / 'stats.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(stats, f, indent=2)


def _record_session(topic, session_type, module=None, score=None, total=None):
    stats = _load_stats(topic)
    record = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'type': session_type,
        'topic': topic,
    }
    if module:
        record['module'] = module
    if score is not None:
        record['score'] = score
    if total is not None:
        record['total'] = total
    stats['sessions'].append(record)
    _save_stats(topic, stats)


# ── Feedback helpers ────────────────────────────────────────────


def _load_feedback(topic):
    path = _topic_path(topic) / 'srs' / 'feedback.json'
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {'ratings': [], 'flags': []}


def _save_feedback(topic, feedback):
    path = _topic_path(topic) / 'srs' / 'feedback.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(feedback, f, indent=2)


# ── Schema validation helpers ────────────────────────────────────

SCHEMA_DIR = SKILL_DIR / 'learn-something-schema' / 'schemas'


def _try_validate(data, schema_name):
    """Validate data against JSON schema. Returns errors list, empty if valid.
    Warns (does not skip silently) if jsonschema not installed."""
    try:
        import jsonschema
    except ImportError:
        print(f'{YELLOW}WARNING: jsonschema not installed. Install: pip install jsonschema{NC}')
        print(f'{YELLOW}Schema validation skipped.{NC}')
        return []
    schema_path = SCHEMA_DIR / f'{schema_name}.schema.json'
    if not schema_path.exists():
        return [f'Schema not found: {schema_path}']
    with open(schema_path) as f:
        schema = json.load(f)
    validator = jsonschema.Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = '.'.join(str(p) for p in error.absolute_path)
        prefix = f'{path}: ' if path else ''
        errors.append(f'{prefix}{error.message}')
    return errors


# ── Adaptive quiz helpers ───────────────────────────────────────


def _find_card(cards, qid, topic, module):
    """Find a card in the dict by question ID, trying various ID formats."""
    # O(1) direct key lookup — card key is {topic}-{module}-{questionId}
    direct_key = f'{topic}-{module}-{qid}'
    if direct_key in cards:
        return cards[direct_key]
    # O(n) fallback: scan for questionId match (legacy/alternate formats)
    for card in cards.values():
        if card.get('questionId') == qid:
            return card
    return {}


def _adaptive_sort(questions, cards, topic, module):
    """Sort questions by priority: weak cards first, then by difficulty."""

    def priority(q):
        card = _find_card(cards, q.get('id', ''), topic, module)
        if card:
            ef = card.get('easeFactor', 2.5)
            reps = card.get('repetitions', 0)
            return (ef, reps, q.get('difficulty', 1))
        return (2.5, 0, q.get('difficulty', 1))

    return sorted(questions, key=priority)


# ── Commands ────────────────────────────────────────────────────


def cmd_init(topic: str, lang: str = 'en', depth: str = 'standard', pretest: bool = False):
    lang = lang or 'en'
    path = _topic_path(topic)
    if path.exists():
        print(f'{RED}Topic "{topic}" already exists. Pick a different name.{NC}')
        sys.exit(1)

    (path / 'modules').mkdir(parents=True, exist_ok=True)
    (path / 'srs').mkdir(parents=True, exist_ok=True)

    # Generate syllabus based on depth
    syllabus = _generate_syllabus(topic, lang, depth)
    with open(path / 'syllabus.yaml', 'w') as f:
        f.write(syllabus)

    depth_info = {
        'survey': ('survey', '~8-12 hours', '5-8 modules'),
        'standard': ('standard', '~30-40 hours', '15-20 modules'),
        'deep': ('deep', '~50+ hours', '25+ modules'),
    }
    label, hours, mods = depth_info.get(depth, depth_info['standard'])

    print(f'{GREEN}Created {path} (language: {lang}, depth: {label}){NC}')
    print(f'  {mods}, {hours}')
    print(
        f'Edit syllabus.yaml, then create modules with: learn.py create-module {topic} <module-id>'
    )

    if pretest:
        print(f'\n{CYAN}Pre-test: answering a few questions to skip what you know...{NC}')
        _run_pretest(topic)


def cmd_start(topic: str):
    spath = _check_topic(topic)

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
    print(f'Explain:    learn.py explain {topic} <module-id>')
    print(f'Take quiz:  learn.py quiz {topic} <module-id>')
    print(f'Review:     learn.py review {topic}')


def cmd_create_module(topic: str, module_id: str, name: Optional[str] = None):
    name = name or module_id
    _check_topic(topic)

    mod_path = _module_path(topic, module_id)
    if mod_path.exists():
        print(f"{RED}Module '{module_id}' already exists in '{topic}'{NC}")
        sys.exit(1)

    if not MODULE_ID_RE.match(module_id):
        print(
            f"{RED}Invalid module ID '{module_id}'. Must be: NN-name (e.g., 01-intro, 02-core-concepts){NC}"
        )
        sys.exit(1)

    mod_path.mkdir(parents=True, exist_ok=True)

    # Copy lesson template
    lesson_tpl = SKILL_DIR / 'templates' / 'module.md'
    if lesson_tpl.exists():
        with open(lesson_tpl) as f:
            content = f.read()
        content = content.replace('[Title]', name)
        # H1 must carry the plain number, never the directory slug (rule 17)
        module_num = module_id.split('-', 1)[0]
        content = content.replace('Module N:', f'Module {module_num}:')
        with open(mod_path / 'lesson.md', 'w') as f:
            f.write(content)

    # Copy quiz template
    quiz_tpl = SKILL_DIR / 'templates' / 'quiz.yaml'
    if quiz_tpl.exists():
        shutil.copy2(quiz_tpl, mod_path / 'quiz.yaml')

    # Copy cloze template
    cloze_tpl = SKILL_DIR / 'templates' / 'cloze.yaml'
    if cloze_tpl.exists():
        shutil.copy2(cloze_tpl, mod_path / 'cloze.yaml')

    print(f'{GREEN}Created module: {mod_path}{NC}')
    print('  lesson.md — edit content')
    print('  quiz.yaml — add 8-10 MCQs')
    print('  cloze.yaml — add 8-10 cloze questions')


def cmd_create_cloze(topic: str, module: str):
    """Create cloze.yaml from template for a module."""
    _check_topic(topic)
    _check_module(topic, module)

    cloze_path = _module_path(topic, module) / 'cloze.yaml'
    if cloze_path.exists():
        print(f'{YELLOW}cloze.yaml already exists at {cloze_path}{NC}')
        sys.exit(1)

    cloze_tpl = SKILL_DIR / 'templates' / 'cloze.yaml'
    if cloze_tpl.exists():
        shutil.copy2(cloze_tpl, cloze_path)
        print(f'{GREEN}Created: {cloze_path}{NC}')
        print('  Edit to add 8-10 cloze questions')
    else:
        print(f'{RED}Template not found at {cloze_tpl}{NC}')
        sys.exit(1)


def cmd_quiz(topic: str, module: str, adaptive: bool = False, weak_only: bool = False):
    _check_topic(topic)
    _check_module(topic, module)

    quiz_path = _module_path(topic, module) / 'quiz.yaml'
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

    if isinstance(questions, dict):
        print(
            f'{RED}Invalid quiz.yaml shape: expected top-level list, got dict with {list(questions.keys())}{NC}'
        )
        print(f'{YELLOW}Run: python {SKILL_DIR}/scripts/migrate_courses.py {topic} --apply{NC}')
        sys.exit(1)

    if not questions:
        print(f'{YELLOW}No questions in quiz{NC}')
        return

    deck = _load_deck(topic)
    cards = deck.get('cards', {})

    # Filter to weak cards only if requested
    if weak_only:
        questions = [
            q
            for q in questions
            if _find_card(cards, q.get('id', ''), topic, module).get('easeFactor', 2.5) < 2.0
        ]
        if not questions:
            print(f'{GREEN}No weak cards found. All cards have easeFactor >= 2.0{NC}')
            return

    # Sort questions
    if adaptive:
        questions = _adaptive_sort(questions, cards, topic, module)
        print(f'{CYAN}=== {topic} / {module} Adaptive Quiz ==={NC}\n')
    else:
        random.shuffle(questions)
        print(f'{CYAN}=== {topic} / {module} Quiz ==={NC}\n')

    correct = 0
    streak = 0
    current_difficulty = 1
    seen_ids = set()

    shown = 0
    total_to_show = 0
    for q in questions:
        qid = q.get('id', '')
        if qid in seen_ids:
            continue
        if adaptive and q.get('difficulty', 1) > current_difficulty + 1:
            continue
        total_to_show += 1

    for i, q in enumerate(questions, 1):
        qid = q.get('id', f'{module}.{i}')

        # Anti-repeat: skip if already seen this session
        if qid in seen_ids:
            continue
        seen_ids.add(qid)

        # Adaptive: skip if difficulty too high for current streak
        if adaptive:
            q_diff = q.get('difficulty', 1)
            if q_diff > current_difficulty + 1:
                continue

        shown += 1
        print(f'--- Question {shown}/{total_to_show} ---')
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
            streak += 1
            # Adaptive: advance difficulty after 3 correct streak
            if adaptive and streak >= 3 and current_difficulty < 3:
                current_difficulty += 1
                streak = 0
                print(f'  {CYAN}难度提升 → Level {current_difficulty}{NC}')
        else:
            print(f'{RED}✗ Wrong. Correct: {q.get("answer", "?")}{NC}')
            quality = 1
            streak = 0
            # Adaptive: drop difficulty on wrong
            if adaptive and current_difficulty > 1:
                current_difficulty -= 1

        explanation = q.get('explanation', '')
        if explanation:
            print(f'  {explanation}')
        print()

        # ── SRS update: create or update card with FSRS-5 ──
        card_id = f'{topic}-{module}-{qid}'
        existing = cards.get(card_id) or _find_card(cards, qid, topic, module)

        if existing:
            sm2_update(existing, quality)
        else:
            answer_opt = q.get('answer', 'a')
            card = {
                'id': card_id,
                'questionId': qid,
                'moduleId': module,
                'courseId': topic,
                'question': q['question'],
                'answer': f'{answer_opt}. {q.get("options", {}).get(answer_opt, "")}',
                'explanation': q.get('explanation', ''),
                'tags': q.get('tags', []),
                'easeFactor': 2.5,
                'interval': 0,
                'repetitions': 0,
                'nextReviewDate': datetime.now().strftime('%Y-%m-%d'),
                'lastReviewed': None,
                'isStarred': False,
            }
            sm2_update(card, quality)
            cards[card_id] = card

    deck['cards'] = cards
    _save_deck(topic, deck)

    pct = correct * 100 // shown if shown else 0
    print(f'\nScore: {correct}/{shown} ({pct}%)')
    _record_session(topic, 'quiz', module=module, score=correct, total=shown)


def cmd_cloze(topic: str, module: str, adaptive: bool = False, weak_only: bool = False):
    """Run cloze (fill-in-blank) quiz for a module."""
    _check_topic(topic)
    _check_module(topic, module)

    cloze_path = _module_path(topic, module) / 'cloze.yaml'
    if not cloze_path.exists():
        print(f'{RED}No cloze.yaml found at {cloze_path}{NC}')
        print(f'{YELLOW}Run: learn.py create-cloze {topic} {module}{NC}')
        sys.exit(1)

    try:
        import yaml
    except ImportError:
        print(f'{RED}Python yaml library required. Install: pip install pyyaml{NC}')
        print(f'{YELLOW}Raw cloze content:{NC}')
        with open(cloze_path) as f:
            print(f.read())
        sys.exit(1)

    with open(cloze_path) as f:
        questions = yaml.safe_load(f)

    if not questions:
        print(f'{YELLOW}No cloze questions found{NC}')
        return

    deck = _load_deck(topic)
    cards = deck.get('cards', {})

    # Filter to weak cards only if requested
    if weak_only:
        questions = [
            q
            for q in questions
            if _find_card(cards, q.get('id', ''), topic, module).get('easeFactor', 2.5) < 2.0
        ]
        if not questions:
            print(f'{GREEN}No weak cloze cards found. All cards have easeFactor >= 2.0{NC}')
            return

    # Sort questions
    if adaptive:
        questions = _adaptive_sort(questions, cards, topic, module)
        print(f'{CYAN}=== {topic} / {module} Adaptive Cloze Quiz ==={NC}\n')
    else:
        random.shuffle(questions)
        print(f'{CYAN}=== {topic} / {module} Cloze Quiz ==={NC}\n')

    correct = 0
    streak = 0
    current_difficulty = 1
    seen_ids = set()

    shown = 0
    total_to_show = len(questions)

    for i, q in enumerate(questions, 1):
        qid = q.get('id', f'{module}.c.{i}')

        # Anti-repeat: skip if already seen this session
        if qid in seen_ids:
            continue
        seen_ids.add(qid)

        # Adaptive: skip if difficulty too high for current streak
        if adaptive:
            q_diff = q.get('difficulty', 1)
            if q_diff > current_difficulty + 1:
                continue

        shown += 1
        print(f'--- Question {shown}/{total_to_show} ---')
        print(q['question'])

        try:
            ans = input('\nYour answer: ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        is_correct = ans.lower() == q.get('answer', '').lower()
        if is_correct:
            print(f'{GREEN}✓ Correct!{NC}')
            quality = 4
            correct += 1
            streak += 1
            # Adaptive: advance difficulty after 3 correct streak
            if adaptive and streak >= 3 and current_difficulty < 3:
                current_difficulty += 1
                streak = 0
                print(f'  {CYAN}难度提升 → Level {current_difficulty}{NC}')
        else:
            print(f'{RED}✗ Wrong. Correct: {q.get("answer", "?")}{NC}')
            quality = 1
            streak = 0
            # Adaptive: drop difficulty on wrong
            if adaptive and current_difficulty > 1:
                current_difficulty -= 1

        explanation = q.get('explanation', '')
        if explanation:
            print(f'  {explanation}')
        print()

        # ── SRS update: create or update card with FSRS-5 ──
        card_id = f'{topic}-{module}-{qid}'
        existing = cards.get(card_id) or _find_card(cards, qid, topic, module)

        if existing:
            sm2_update(existing, quality)
        else:
            card = {
                'id': card_id,
                'questionId': qid,
                'moduleId': module,
                'courseId': topic,
                'question': q['question'],
                'answer': q.get('answer', ''),
                'explanation': q.get('explanation', ''),
                'tags': q.get('tags', []),
                'easeFactor': 2.5,
                'interval': 0,
                'repetitions': 0,
                'nextReviewDate': datetime.now().strftime('%Y-%m-%d'),
                'lastReviewed': None,
                'isStarred': False,
            }
            sm2_update(card, quality)
            cards[card_id] = card

    deck['cards'] = cards
    _save_deck(topic, deck)

    pct = correct * 100 // shown if shown else 0
    print(f'\nScore: {correct}/{shown} ({pct}%)')
    _record_session(topic, 'cloze', module=module, score=correct, total=shown)


def cmd_cumulative_quiz(topic: str, modules: Optional[str] = None):
    """Cross-module quiz: 8-10 questions mixing MCQ, cloze, T/F."""
    _check_topic(topic)

    quiz_paths = sorted((SUBJECTS_DIR / topic).glob('cumulative_quiz*.yaml'))
    if not quiz_paths:
        print(f'{RED}No cumulative_quiz*.yaml found at {SUBJECTS_DIR / topic}{NC}')
        print(f'{YELLOW}Generate one after completing 3-5 modules.{NC}')
        sys.exit(1)

    try:
        import yaml
    except ImportError:
        print(f'{RED}Python yaml library required. Install: pip install pyyaml{NC}')
        sys.exit(1)

    questions = []
    for qp in quiz_paths:
        with open(qp) as f:
            chunk = yaml.safe_load(f)
        if chunk:
            questions.extend(chunk)

    if not questions:
        print(f'{YELLOW}No questions in cumulative quiz{NC}')
        return
    if len(quiz_paths) > 1:
        print(
            f'{YELLOW}Loaded {len(quiz_paths)} cumulative quizzes ({len(questions)} questions). '
            f'Use --modules X-Y to target one range.{NC}'
        )

    # Filter by module range if specified
    if modules:
        parts = modules.split('-')
        try:
            lo, hi = int(parts[0]), int(parts[-1])
        except ValueError:
            print(f'{RED}Invalid module range: {modules}. Use X-Y format.{NC}')
            sys.exit(1)
        questions = [
            q for q in questions if any(lo <= m <= hi for m in q.get('source_modules', []))
        ]
        if not questions:
            print(f'{YELLOW}No questions matching modules {modules}{NC}')
            return

    deck = _load_deck(topic)
    cards = deck.get('cards', {})
    random.shuffle(questions)

    print(f'{CYAN}=== {topic} Cumulative Quiz ==={NC}')
    if modules:
        print(f'{CYAN}Modules: {modules}{NC}')
    print()

    correct = 0
    shown = 0

    for i, q in enumerate(questions, 1):
        qid = q.get('id', f'cum.{i}')
        qtype = q.get('type', 'mcq')
        source = q.get('source_modules', [])
        source_str = ', '.join(str(s) for s in source)

        print(f'--- Question {i}/{len(questions)} [{qtype.upper()}] (modules: {source_str}) ---')

        if qtype == 'mcq':
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
                print(f'Invalid. Choose {min(keymap)}-{max(keymap)}.')

            is_correct = keymap[ans] == q.get('answer', '')
            # Add to SRS deck
            card_id = f'{topic}-cum-{qid}'
            card = _find_card(cards, qid, topic, 'cumulative')
            card['question'] = q['question']
            card['answer'] = (
                f'{q.get("answer", "").lower()}. {q["options"].get(q.get("answer", ""), "")}'
            )
            cards[card_id] = card

        elif qtype == 'cloze':
            print(q['question'])
            try:
                ans = input('\nYour answer: ').strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            is_correct = ans.lower() == q.get('answer', '').lower()
            card_id = f'{topic}-cum-{qid}'
            card = _find_card(cards, qid, topic, 'cumulative')
            card['question'] = q['question']
            card['answer'] = q.get('answer', '')
            cards[card_id] = card

        elif qtype == 'tf':
            print(q['statement'])
            while True:
                try:
                    ans = input('\nTrue or False: ').strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print()
                    return
                if ans in ('t', 'true', 'f', 'false'):
                    break
                print('Invalid. Enter t/true or f/false.')
            user_answer = ans in ('t', 'true')
            is_correct = user_answer == q.get('answer', True)
            card_id = f'{topic}-cum-{qid}'
            card = _find_card(cards, qid, topic, 'cumulative')
            card['question'] = q.get('statement', '')
            card['answer'] = 'True' if q.get('answer', True) else 'False'
            cards[card_id] = card
        else:
            print(f'{YELLOW}Unknown type: {qtype}{NC}')
            continue

        if is_correct:
            print(f'{GREEN}✓ Correct!{NC}')
            quality = 4
            correct += 1
        else:
            print(f'{RED}✗ Wrong.{NC}')
            quality = 1

        explanation = q.get('explanation', '')
        if explanation:
            print(f'  {explanation}')

        # Update SRS
        if card_id in cards:
            cards[card_id] = _sm2.sm2_update(cards[card_id], quality)

        shown += 1
        print()

    deck['cards'] = cards
    _save_deck(topic, deck)

    pct = correct * 100 // shown if shown else 0
    print(f'\nScore: {correct}/{shown} ({pct}%)')
    _record_session(topic, 'cumulative-quiz', module='cumulative', score=correct, total=shown)


def cmd_explain(topic: str, module: str):
    _check_topic(topic)
    _check_module(topic, module)

    lesson_path = _module_path(topic, module) / 'lesson.md'
    if not lesson_path.exists():
        print(f'{RED}No lesson found at {lesson_path}{NC}')
        sys.exit(1)

    print(f'{CYAN}=== Feynman Explain: {topic} / {module} ==={NC}')
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


def cmd_review(topic: str):
    _check_topic(topic)

    deck = _load_deck(topic)
    cards = deck.get('cards', {})
    if not cards:
        print(f'{YELLOW}No SRS deck yet. Take a quiz first: learn.py quiz {topic} <module>{NC}')
        return

    today = datetime.now().strftime('%Y-%m-%d')
    due = [c for c in cards.values() if c.get('nextReviewDate', '2000-01-01') <= today]

    if not due:
        print(f'{GREEN}No cards due for review!{NC}')
        return

    random.shuffle(due)
    correct = 0
    total = len(due)

    print(f'{CYAN}=== Review: {total} card(s) due ==={NC}\n')

    for card in due:
        print(f'Q: {card["question"]}')
        # Parse answer from "a. option text" format
        answer_key = card.get('answer', 'a. ')[0]
        print(f'  Answer key: {answer_key}')
        explanation = card.get('explanation', '')

        while True:
            try:
                ans = input('\nYour answer (a/b/c/d or s=show): ').strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if ans in ('a', 'b', 'c', 'd'):
                break
            if ans == 's':
                print(f'  {GREEN}Answer: {card.get("answer", "?")}{NC}')
                if explanation:
                    print(f'  {explanation}')
                ans = None
                break
            print('Invalid. Choose a, b, c, d, or s to show.')

        if ans is None:
            # Showed answer — mark as review for re-attempt later
            quality = 2
        elif ans == answer_key.lower():
            print(f'{GREEN}✓ Correct!{NC}')
            quality = 4
            correct += 1
        else:
            print(f'{RED}✗ Wrong. Correct: {card.get("answer", "?")}{NC}')
            quality = 1

        if ans is not None and explanation:
            print(f'  {explanation}')
        print()

        sm2_update(card, quality)

    deck['cards'] = cards
    _save_deck(topic, deck)

    if total > 0:
        pct = correct * 100 // total
        print(f'\nScore: {correct}/{total} ({pct}%)')
        _record_session(topic, 'review', score=correct, total=total)


def cmd_stats(topic: str):
    _check_topic(topic)

    deck = _load_deck(topic)
    cards = deck.get('cards', {})
    if not cards:
        print(f'{YELLOW}No stats yet. Take a quiz first.{NC}')
        return

    total = len(cards)
    reviewed = [c for c in cards.values() if c.get('lastReviewed')]
    today = datetime.now().strftime('%Y-%m-%d')
    due_today = [c for c in cards.values() if c.get('nextReviewDate', '2000-01-01') <= today]
    mastered = [c for c in cards.values() if c.get('interval', 0) >= 21]
    avg_ef = sum(c.get('easeFactor', 2.5) for c in cards.values()) / total

    print(f'Cards: {total}')
    print(f'Reviewed: {len(reviewed)}')
    print(f'Due today: {len(due_today)}')
    print(f'Mastered (interval >= 21d): {len(mastered)}')
    print(f'Avg ease factor: {avg_ef:.2f}')
    print()

    # Module breakdown
    module_counts = Counter()
    for c in cards.values():
        mod = c.get('moduleId', '?')
        module_counts[mod] += 1
    print('By module:')
    for mod in sorted(module_counts):
        print(f'  Module {mod}: {module_counts[mod]} cards')

    # Session history
    stats = _load_stats(topic)
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


def cmd_export(topic: str):
    _check_topic(topic)

    deck = _load_deck(topic)
    cards = deck.get('cards', {})
    if not cards:
        print(f'{YELLOW}No deck to export.{NC}')
        return

    out_path = _topic_path(topic) / 'srs' / 'deck.csv'
    with open(out_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Question', 'Answer', 'Explanation', 'Tags'])
        for card in cards.values():
            w.writerow(
                [
                    card.get('question', ''),
                    card.get('answer', ''),
                    card.get('explanation', ''),
                    ' '.join(card.get('tags', [])),
                ]
            )

    print(f'{GREEN}Exported {len(cards)} cards to {out_path}{NC}')
    print('Import into Anki via: File > Import')


def cmd_rate(topic: str, module: str, score: int, comment: str = ''):
    comment = comment or ''
    _check_topic(topic)
    _check_module(topic, module)

    if not 1 <= score <= 5:
        print(f'{RED}Score must be 1-5{NC}')
        sys.exit(1)

    feedback = _load_feedback(topic)
    feedback['ratings'].append(
        {
            'module': module,
            'score': score,
            'date': datetime.now().isoformat(),
            'comment': comment,
        }
    )
    _save_feedback(topic, feedback)
    print(f'{GREEN}Rated {module}: {score}/5{NC}')


def cmd_flag(topic: str, module: str, flag_type: str = 'wrong', detail: str = ''):
    detail = detail or ''
    _check_topic(topic)
    _check_module(topic, module)

    valid_types = ['wrong', 'outdated', 'confusing']
    if flag_type not in valid_types:
        print(f'{RED}Flag type must be one of: {", ".join(valid_types)}{NC}')
        sys.exit(1)

    feedback = _load_feedback(topic)
    feedback['flags'].append(
        {
            'module': module,
            'type': flag_type,
            'detail': detail,
            'date': datetime.now().isoformat(),
        }
    )
    _save_feedback(topic, feedback)
    print(f'{GREEN}Flagged {module}: {flag_type}{NC}')


def cmd_feedback(topic: str):
    _check_topic(topic)

    feedback = _load_feedback(topic)
    ratings = feedback.get('ratings', [])
    flags = feedback.get('flags', [])

    if not ratings and not flags:
        print(f'{YELLOW}No feedback yet.{NC}')
        return

    print(f'{CYAN}=== Feedback: {topic} ==={NC}\n')

    mod_ratings = {}
    mod_flags = {}

    if ratings:
        print(f'{YELLOW}Ratings:{NC}')
        for r in ratings:
            mod = r['module']
            mod_ratings.setdefault(mod, []).append(r['score'])
        for mod in sorted(mod_ratings):
            scores = mod_ratings[mod]
            avg = sum(scores) / len(scores)
            bar = '★' * int(round(avg)) + '☆' * (5 - int(round(avg)))
            print(f'  {mod}: {bar} {avg:.1f}/5 ({len(scores)} ratings)')
        print()

    if flags:
        print(f'{YELLOW}Flags:{NC}')
        for f in flags:
            mod = f['module']
            mod_flags.setdefault(mod, []).append(f['type'])
        for mod in sorted(mod_flags):
            types = mod_flags[mod]
            counts = Counter(types)
            parts = [f'{t}: {c}' for t, c in counts.most_common()]
            print(f'  {mod}: {", ".join(parts)}')
        print()

    # Suggest modules to revisit
    low_rated = [mod for mod, scores in mod_ratings.items() if sum(scores) / len(scores) < 3.0]
    flagged = list(mod_flags.keys())
    revisit = sorted(set(low_rated + flagged))
    if revisit:
        print(f'{YELLOW}Suggest revisiting:{NC}')
        for mod in revisit:
            print(f'  - {mod}')


def cmd_analytics(topic: str):
    _check_topic(topic)

    deck = _load_deck(topic)
    cards = deck.get('cards', {})
    stats = _load_stats(topic)

    if not cards:
        print(f'{YELLOW}No data yet. Take a quiz first.{NC}')
        return

    total_cards = len(cards)
    mastered = [c for c in cards.values() if c.get('interval', 0) >= 21]
    learning = [c for c in cards.values() if 0 < c.get('interval', 0) < 21]
    new_cards = [c for c in cards.values() if not c.get('lastReviewed')]

    print(f'{CYAN}=== Analytics: {topic} ==={NC}\n')

    print(f'Total cards: {total_cards}')
    print(f'  New (never reviewed): {len(new_cards)}')
    print(f'  Learning (interval < 21d): {len(learning)}')
    print(f'  Mastered (interval >= 21d): {len(mastered)}')
    if total_cards > 0:
        mastery_pct = len(mastered) * 100 // total_cards
        bar_len = 30
        filled = mastery_pct * bar_len // 100
        bar = '█' * filled + '░' * (bar_len - filled)
        print(f'  Mastery: [{bar}] {mastery_pct}%')
    print()

    # Session retention over time
    sessions = stats.get('sessions', [])
    if sessions:
        print(f'{YELLOW}Session history:{NC}')
        daily = {}
        for s in sessions:
            date = s['date']
            daily.setdefault(date, {'quiz': [], 'review': []})
            if s['type'] == 'quiz' and s.get('score') is not None and s.get('total') is not None:
                daily[date]['quiz'].append((s['score'], s['total']))
            elif (
                s['type'] == 'review' and s.get('score') is not None and s.get('total') is not None
            ):
                daily[date]['review'].append((s['score'], s['total']))

        for date in sorted(daily.keys())[-10:]:
            parts = [date]
            if daily[date]['quiz']:
                q_correct = sum(s[0] for s in daily[date]['quiz'])
                q_total = sum(s[1] for s in daily[date]['quiz'])
                parts.append(f'quiz {q_correct}/{q_total}')
            if daily[date]['review']:
                r_correct = sum(s[0] for s in daily[date]['review'])
                r_total = sum(s[1] for s in daily[date]['review'])
                parts.append(f'review {r_correct}/{r_total}')
            print(f'  {" | ".join(parts)}')
    print()

    # Weak modules (by ease factor)
    mod_ef = {}
    for c in cards.values():
        mod = c.get('moduleId', '?')
        mod_ef.setdefault(mod, []).append(c.get('easeFactor', 2.5))

    if mod_ef:
        print(f'{YELLOW}Module difficulty (avg ease factor):{NC}')
        mod_avg = [(mod, sum(efs) / len(efs)) for mod, efs in mod_ef.items()]
        mod_avg.sort(key=lambda x: x[1])
        for mod, avg in mod_avg:
            indicator = f'{RED}⚠{NC}' if avg < 2.0 else ''
            print(f'  {mod}: {avg:.2f} {indicator}')


def cmd_forecast(topic: str):
    _check_topic(topic)

    deck = _load_deck(topic)
    cards = deck.get('cards', {})
    if not cards:
        print(f'{YELLOW}No deck yet.{NC}')
        return

    today = datetime.now()
    today_str = today.strftime('%Y-%m-%d')

    due_now = []
    due_week = []
    due_month = []
    later = []

    for card in cards.values():
        nr = card.get('nextReviewDate', '2000-01-01')
        if nr <= today_str:
            due_now.append(card)
        else:
            try:
                due_date = datetime.strptime(nr, '%Y-%m-%d')
                days = (due_date - today).days
                if days <= 7:
                    due_week.append((days, card))
                elif days <= 30:
                    due_month.append((days, card))
                else:
                    later.append((days, card))
            except ValueError:
                later.append((999, card))

    print(f'{CYAN}=== Forgetting Forecast: {topic} ==={NC}\n')

    print(f'{RED}Due now: {len(due_now)} cards{NC}')
    if due_now:
        mods = Counter(c.get('moduleId', '?') for c in due_now)
        for mod, count in mods.most_common():
            print(f'  {mod}: {count} cards')

    print(f'\nDue this week: {len(due_week)} cards')
    due_week.sort()
    for days, card in due_week[:5]:
        mod = card.get('moduleId', '?')
        print(f'  In {days}d: {mod} — {card["question"][:50]}...')
    if len(due_week) > 5:
        print(f'  ... and {len(due_week) - 5} more')

    print(f'\nDue this month: {len(due_month)} cards')
    print(f'  Later: {len(later)} cards')


def cmd_study_plan(topic: str):
    _check_topic(topic)

    deck = _load_deck(topic)
    cards = deck.get('cards', {})
    if not cards:
        print(f'{YELLOW}No deck yet. Take a quiz first.{NC}')
        return

    today_str = datetime.now().strftime('%Y-%m-%d')

    due_now = [c for c in cards.values() if c.get('nextReviewDate', '2000-01-01') <= today_str]
    weak = [
        c
        for c in cards.values()
        if c.get('easeFactor', 2.5) < 2.0 and c.get('nextReviewDate', '2000-01-01') > today_str
    ]
    mastered = [c for c in cards.values() if c.get('interval', 0) >= 21]

    print(f'{CYAN}=== Study Plan: {topic} ==={NC}\n')

    total_suggested = 0

    if due_now:
        print(f'{RED}Priority: {len(due_now)} cards due now{NC}')
        mods = Counter(c.get('moduleId', '?') for c in due_now)
        for mod, count in mods.most_common(5):
            print(f'  {mod}: {count} cards')
        total_suggested += len(due_now)

    if weak:
        print(f'\n{YELLOW}Weak cards (easeFactor < 2.0): {len(weak)}{NC}')
        mods = Counter(c.get('moduleId', '?') for c in weak)
        for mod, count in mods.most_common(5):
            print(f'  {mod}: {count} cards')
        total_suggested += len(weak)

    if mastered:
        print(f'\n{GREEN}Mastered: {len(mastered)} cards (review less frequently){NC}')

    target = 20
    print(f'\n{CYAN}Suggested session: {min(total_suggested, target)} cards{NC}')
    if total_suggested > target:
        print('  (Focus on due + weak. Skip mastered.)')
    elif total_suggested == 0:
        print('  All caught up! Next review based on FSRS-5 schedule.')


def cmd_epub(
    topic: str,
    output: Optional[str] = None,
    description: str = '',
    theme: str = 'notebook',
    mermaid: str = 'api',
):
    _check_topic(topic)
    spath = _topic_path(topic)

    if not output:
        output = str(spath / f'{topic}.epub')

    epub_script = SKILL_DIR / 'scripts' / 'epub.py'
    if not epub_script.exists():
        print(f'{RED}epub.py not found at {epub_script}{NC}')
        sys.exit(1)

    cmd = [
        sys.executable,
        str(epub_script),
        'build',
        str(spath),
        output,
        '--mermaid',
        mermaid,
        '--theme',
        theme,
    ]
    if description:
        cmd.extend(['--description', description])

    print(f'{CYAN}Building EPUB: {topic}{NC}')
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


def _pdf_extra_args(title=None, author='Learn Something', engine='auto'):
    cmd = []
    if title:
        cmd.extend(['--title', title])
    if author:
        cmd.extend(['--author', author])
    cmd.extend(['--engine', engine])
    return cmd


def cmd_pdf(
    topic: str,
    output: Optional[str] = None,
    title: Optional[str] = None,
    author: str = 'Learn Something',
    engine: str = 'auto',
):
    _check_topic(topic)
    spath = _topic_path(topic)

    if not output:
        output = str(spath / f'{topic}.pdf')

    pdf_script = SKILL_DIR / 'scripts' / 'pdf.py'
    if not pdf_script.exists():
        print(f'{RED}pdf.py not found at {pdf_script}{NC}')
        sys.exit(1)

    print(f'{CYAN}Building PDF: {topic}{NC}')
    cmd = [sys.executable, str(pdf_script), 'build', str(spath), output] + _pdf_extra_args(
        title, author, engine
    )
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


def cmd_pdf_regen(
    topic: str,
    output: Optional[str] = None,
    title: Optional[str] = None,
    author: str = 'Learn Something',
    engine: str = 'auto',
):
    _check_topic(topic)
    spath = _topic_path(topic)
    book_md = spath / 'book.md'

    if not book_md.exists():
        print(f"{YELLOW}No book.md. Run 'pdf' first.{NC}")
        return

    if not output:
        output = str(spath / f'{topic}.pdf')

    pdf_script = SKILL_DIR / 'scripts' / 'pdf.py'
    if not pdf_script.exists():
        print(f'{RED}pdf.py not found at {pdf_script}{NC}')
        sys.exit(1)

    print(f'{CYAN}Regenerating PDF from cached markdown: {topic}{NC}')
    cmd = [sys.executable, str(pdf_script), 'from-md', str(book_md), output] + _pdf_extra_args(
        title, author, engine
    )
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


def cmd_epub_regen(
    topic: str,
    output: Optional[str] = None,
    description: str = '',
    theme: str = 'notebook',
    mermaid: str = 'api',
):
    _check_topic(topic)
    spath = _topic_path(topic)
    book_md = spath / 'book.md'

    if not book_md.exists():
        print(f"{YELLOW}No book.md. Run 'epub' first.{NC}")
        return

    if not output:
        output = str(spath / f'{topic}.epub')

    epub_script = SKILL_DIR / 'scripts' / 'epub.py'
    if not epub_script.exists():
        print(f'{RED}epub.py not found at {epub_script}{NC}')
        sys.exit(1)

    cmd = [
        sys.executable,
        str(epub_script),
        'from-md',
        str(book_md),
        output,
        '--mermaid',
        mermaid,
        '--theme',
        theme,
    ]
    if description:
        cmd.extend(['--description', description])

    print(f'{CYAN}Regenerating EPUB from cached markdown: {topic}{NC}')
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


def cmd_epub_list_themes():
    epub_script = SKILL_DIR / 'scripts' / 'epub.py'
    if not epub_script.exists():
        print(f'{RED}epub.py not found at {epub_script}{NC}')
        sys.exit(1)
    result = subprocess.run(
        [sys.executable, str(epub_script), 'list-themes'], capture_output=True, text=True
    )
    if result.stdout:
        print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, file=sys.stderr, end='')
    sys.exit(result.returncode)


def cmd_epub_verify(topic: str, output: Optional[str] = None):
    _check_topic(topic)
    spath = _topic_path(topic)

    if not output:
        epub_path = spath / f'{topic}.epub'
    else:
        epub_path = Path(output)

    if not epub_path.exists():
        print(f'{RED}EPUB not found: {epub_path}{NC}')
        return

    epub_script = SKILL_DIR / 'scripts' / 'epub.py'
    if not epub_script.exists():
        print(f'{RED}epub.py not found at {epub_script}{NC}')
        sys.exit(1)

    print(f'{CYAN}Verifying EPUB: {topic}{NC}')
    result = subprocess.run(
        [sys.executable, str(epub_script), 'verify', str(epub_path)],
        capture_output=True,
        text=True,
    )
    print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, file=sys.stderr, end='')


def cmd_sync(topic: str, reader_path: Optional[str] = None):
    """Export CLI deck to Reader-compatible directory."""
    _check_topic(topic)

    reader_subjects = _reader_subjects_path(reader_path)
    reader_topic = reader_subjects / topic

    # Create Reader directory structure
    reader_srs = reader_topic / 'srs'
    reader_srs.mkdir(parents=True, exist_ok=True)

    # Load and save deck (already in Reader format)
    deck = _load_deck(topic)
    cards = deck.get('cards', {})
    if not cards:
        print(f'{YELLOW}No cards to sync.{NC}')
        return

    # Save deck
    with open(reader_srs / 'deck.json', 'w') as f:
        json.dump(deck, f, indent=2)

    # Copy modules (lesson.md + quiz.yaml)
    reader_modules = reader_topic / 'modules'
    reader_modules.mkdir(parents=True, exist_ok=True)

    cli_modules = _topic_path(topic) / 'modules'
    copied = 0
    for mod_dir in sorted(cli_modules.iterdir()):
        if not mod_dir.is_dir():
            continue
        reader_mod = reader_modules / mod_dir.name
        reader_mod.mkdir(exist_ok=True)
        for fname in ['lesson.md', 'quiz.yaml', 'cloze.yaml']:
            src = mod_dir / fname
            if src.exists():
                shutil.copy2(src, reader_mod / fname)
                copied += 1

    # Copy syllabus
    syllabus_src = _topic_path(topic) / 'syllabus.yaml'
    if syllabus_src.exists():
        shutil.copy2(syllabus_src, reader_topic / 'syllabus.yaml')

    # Copy cumulative quizzes
    for cum_src in sorted(_topic_path(topic).glob('cumulative_quiz*.yaml')):
        shutil.copy2(cum_src, reader_topic / cum_src.name)

    print(f'{GREEN}Synced to Reader: {reader_topic}{NC}')
    print(f'  Deck: {len(cards)} cards')
    print(f'  Modules: {copied} files copied')


def cmd_sync_pull(topic: str, reader_path: Optional[str] = None):
    """Import deck from Reader directory to CLI."""
    reader_subjects = _reader_subjects_path(reader_path)
    reader_topic = reader_subjects / topic

    if not reader_topic.exists():
        print(f'{RED}Reader topic not found: {reader_topic}{NC}')
        sys.exit(1)

    reader_deck = reader_topic / 'srs' / 'deck.json'
    if not reader_deck.exists():
        print(f'{RED}No deck found at {reader_deck}{NC}')
        sys.exit(1)

    # Ensure CLI topic exists
    cli_topic = _topic_path(topic)
    cli_topic.mkdir(parents=True, exist_ok=True)
    cli_srs = cli_topic / 'srs'
    cli_srs.mkdir(exist_ok=True)

    # Load Reader deck and save to CLI
    with open(reader_deck) as f:
        deck = json.load(f)

    # Ensure it's in dict format
    if isinstance(deck, list):
        deck = _migrate_deck_array(deck, topic)

    with open(cli_srs / 'deck.json', 'w') as f:
        json.dump(deck, f, indent=2)

    cards = deck.get('cards', {})
    print(f'{GREEN}Imported from Reader: {reader_topic}{NC}')
    print(f'  Deck: {len(cards)} cards')


def cmd_validate(
    topic: Optional[str] = typer.Argument(None),
    module: Optional[str] = typer.Argument(None),
    max_chars: Optional[int] = None,
    offline: bool = False,
    fast: bool = False,
    all_topics: bool = typer.Option(False, '--all', '--all-topics', help='Validate every topic.'),
    json_out: bool = typer.Option(False, '--json', help='JSON output.'),
):
    """Full quality gate: schema + content syntax + quality checks. All checks ERR (rule 16 is WARN).

    With --all: validate every topic under the subjects directory.
    With --json: machine-readable output.
    """
    if all_topics:
        topics = sorted(
            d.name for d in SUBJECTS_DIR.iterdir()
            if d.is_dir() and (d / 'syllabus.yaml').exists()
        )
        if not topics:
            print(f'{RED}No topics found in {SUBJECTS_DIR}{NC}')
            sys.exit(1)
        all_results = {}
        any_errors = False
        for tname in topics:
            t = SUBJECTS_DIR / tname
            try:
                old = sys.stdout
                if json_out:
                    sys.stdout = io.StringIO()
                try:
                    results = (
                        _schema_errors(t, yaml_available())
                        + _content_syntax_errors(t, None, offline=offline or fast)
                        + _quality_checks(t, None, max_chars or 12000)
                    )
                finally:
                    if json_out:
                        sys.stdout = old
            except SystemExit:
                raise
            except Exception as e:
                results = [('validate', [f'internal error: {e}'])]
            files = {}
            for name, errors in results:
                files[name] = errors
                if errors:
                    any_errors = True
            all_results[tname] = {'files': files, 'passed': all(not e for e in files.values())}
        if json_out:
            print(json.dumps({'results': all_results, 'all_passed': not any_errors}, indent=2))
        else:
            for tname, data in all_results.items():
                if data['passed']:
                    print(f'{GREEN}{tname}: OK{NC}')
                    continue
                n = sum(len(e) for e in data['files'].values())
                print(f'{RED}{tname}: {n} error(s){NC}')
                for name, errors in data['files'].items():
                    if errors:
                        print(f'  {name}:')
                        for err in errors:
                            print(f'    - {err}')
            print(f"\n{'All topics passed.' if not any_errors else 'FAILURES PRESENT.'}")
        sys.exit(1 if any_errors else 0)

    if topic is None:
        print(f'{RED}Provide TOPIC or use --all{NC}')
        sys.exit(1)
    t = _topic_path(topic)
    if not t.exists():
        print(f'{RED}Subject not found: {topic}{NC}')
        sys.exit(1)

    results = []
    old = sys.stdout
    if json_out:
        sys.stdout = io.StringIO()
    try:
        results += _schema_errors(t, yaml_available())
        results += _content_syntax_errors(t, module, offline=offline or fast)
        results += _quality_checks(t, module, max_chars or 12000)
    finally:
        if json_out:
            sys.stdout = old

    if json_out:
        files = {name: errors for name, errors in results}
        passed = all(not errors for _, errors in results)
        print(json.dumps({'topic': topic, 'files': files, 'passed': passed}, indent=2))
        sys.exit(0 if passed else 1)

    # Report
    any_errors = False
    for name, errors in results:
        if errors:
            any_errors = True
            print(f'{RED}{name}: {len(errors)} error(s){NC}')
            for err in errors:
                print(f'  - {err}')
        else:
            print(f'{GREEN}{name}: OK{NC}')

    if not any_errors:
        print(f'\n{GREEN}All checks passed.{NC}')
    sys.exit(1 if any_errors else 0)


def yaml_available():
    return yaml is not None


def _schema_errors(t, has_yaml):
    """Pass 1: validate all files against JSON schemas + module dir naming."""
    results = []

    # Validate deck
    deck_path = t / 'srs' / 'deck.json'
    if deck_path.exists():
        try:
            with open(deck_path) as f:
                deck_data = json.load(f)
            errors = _try_validate(deck_data, 'deck')
            results.append(('deck.json', errors))
        except Exception as e:
            results.append(('deck.json', [str(e)]))
    else:
        print(
            f'{YELLOW}deck.json: not found — no SRS cards yet (OK for new/unstudied subjects){NC}'
        )
        results.append(('deck.json', []))

    # Validate quiz files
    for mf in sorted(t.glob('modules/*/quiz.yaml')):
        try:
            if not has_yaml:
                results.append((str(mf.relative_to(t)), ['PyYAML not installed']))
                continue
            with open(mf) as f:
                quiz_data = yaml.safe_load(f)
            errors = _try_validate(quiz_data, 'quiz')
            results.append((str(mf.relative_to(t)), errors))
        except Exception as e:
            results.append((str(mf.relative_to(t)), [str(e)]))

    # Validate cloze files
    for cf in sorted(t.glob('modules/*/cloze.yaml')):
        try:
            if not has_yaml:
                results.append((str(cf.relative_to(t)), ['PyYAML not installed']))
                continue
            with open(cf) as f:
                cloze_data = yaml.safe_load(f)
            errors = _try_validate(cloze_data, 'cloze_quiz')
            results.append((str(cf.relative_to(t)), errors))
        except Exception as e:
            results.append((str(cf.relative_to(t)), [str(e)]))

    # Validate cumulative quizzes
    for cuf in sorted(t.glob('cumulative_quiz*.yaml')):
        try:
            if not has_yaml:
                results.append((str(cuf.relative_to(t)), ['PyYAML not installed']))
                continue
            with open(cuf) as f:
                cum_data = yaml.safe_load(f)
            errors = _try_validate(cum_data, 'cumulative_quiz')
            results.append((str(cuf.relative_to(t)), errors))
        except Exception as e:
            results.append((str(cuf.relative_to(t)), [str(e)]))

    # Validate module dir naming (NN-kebab-case)
    for md in sorted(t.glob('modules/*')):
        if not md.is_dir():
            results.append((f'modules/{md.name}', ['not a directory; remove junk files']))
            continue
        if not MODULE_ID_RE.match(md.name):
            results.append((f'modules/{md.name}', ['invalid name; expected NN-kebab-case']))

    # Validate syllabus
    syll_path = t / 'syllabus.yaml'
    if syll_path.exists():
        try:
            if not has_yaml:
                results.append(('syllabus.yaml', ['PyYAML not installed']))
            else:
                with open(syll_path) as f:
                    syll_data = yaml.safe_load(f)
                errors = _try_validate(syll_data, 'syllabus')
                results.append(('syllabus.yaml', errors))
        except Exception as e:
            results.append(('syllabus.yaml', [str(e)]))

    # Validate feedback
    fb_path = t / 'srs' / 'feedback.json'
    if fb_path.exists():
        try:
            with open(fb_path) as f:
                fb_data = json.load(f)
            errors = _try_validate(fb_data, 'feedback')
            results.append(('srs/feedback.json', errors))
        except Exception as e:
            results.append(('srs/feedback.json', [str(e)]))

    return results


# ── Content syntax validation ──────────────────────────────────


def _check_pymarkdownlnt():
    """Check if pymarkdownlnt is available."""
    try:
        result = subprocess.run(
            ['pymarkdown', 'version'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _check_mmdc():
    """Check if mermaid CLI (mmdc) is available."""
    try:
        result = subprocess.run(
            ['mmdc', '--version'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ── Linter resolution chains ────────────────────────────────────
#
# Ground truth is the real linter; naive basic checkers are last resort
# and known to produce false positives (e.g. sequenceDiagram alt/end read
# as subgraph/end mismatch, globs in code spans read as unclosed italics).
#
# Resolution order:
#   markdown: global `pymarkdown` → `uvx --from pymarkdownlnt pymarkdown`
#             → `pipx run --spec pymarkdownlnt pymarkdown` → basic
#   mermaid:  global `mmdc` → `npx -y @mermaid-js/mermaid-cli` → basic
#
# Network-backed fallbacks are skipped under offline/fast mode, so basic
# false positives can only surface when explicitly opted out.


def _resolve_md_linter(offline=False):
    """Return (argv_prefix or None, via_network).

    argv_prefix runs the pymarkdown CLI: <prefix> scan <file>.
    """
    if _check_pymarkdownlnt():
        return ['pymarkdown'], False
    if not offline:
        if shutil.which('uvx'):
            # package console-script is `pymarkdown`, not `pymarkdownlnt`
            return ['uvx', '--from', 'pymarkdownlnt', 'pymarkdown'], True
        if shutil.which('pipx'):
            return ['pipx', 'run', '--spec', 'pymarkdownlnt', 'pymarkdown'], True
    return None, False


def _resolve_mmdc(offline=False):
    """Return (argv_prefix or None, via_network).

    argv_prefix renders a diagram: <prefix> -i tmp.mmd -t neutral --quiet.
    """
    if _check_mmdc():
        return ['mmdc'], False
    if not offline and shutil.which('npx'):
        return ['npx', '-y', '@mermaid-js/mermaid-cli'], True
    return None, False


def _validate_markdown_basic(filepath):
    """Basic markdown validation without external tools.
    Returns list of (line, message) tuples."""
    errors = []
    content = filepath.read_text()
    lines = content.split('\n')

    # Check code block closure
    in_code_block = False
    code_block_start = 0
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('```'):
            if in_code_block:
                in_code_block = False
            else:
                in_code_block = True
                code_block_start = i
    if in_code_block:
        errors.append((code_block_start, 'Code block not closed (opened here)'))

    # Check heading hierarchy
    prev_level = 0
    in_code_block = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        m = re.match(r'^(#{1,6})\s', line)
        if m:
            level = len(m.group(1))
            if prev_level > 0 and level > prev_level + 1:
                errors.append((i, f'Heading level skipped (h{prev_level} → h{level})'))
            prev_level = level

    # Check link syntax
    for i, line in enumerate(lines, 1):
        # Find [text](url) patterns - basic check
        for m in re.finditer(r'\[([^\]]*)\]\(([^)]*)\)', line):
            pass  # Valid link syntax
        # Find broken links: [text] without (url)
        for m in re.finditer(r'\[([^\]]+)\](?!\()', line):
            text = m.group(1)
            # Skip if it's inside a code block or is an image
            if text and not text.startswith('!'):
                # Could be a reference link, but flag if it looks like a broken inline link
                pass  # Reference links are valid, skip

    # Check bold/italic closure
    in_code_block = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        # Count unescaped ** pairs (ignore inline code spans: globs like
        # `*.module.css` or `dist/**` are not emphasis markers)
        line_prose = re.sub(r'`[^`]*`', '``', line)
        double_stars = len(re.findall(r'(?<!\*)\*\*(?!\*)', line_prose))
        if double_stars % 2 != 0:
            errors.append((i, 'Unclosed ** (bold) marker'))
        # Count emphasis-capable * only: CommonMark requires a non-space
        # neighbor (opener `*x`, closer `x*`). A spaced star as in
        # `select * from` is literal text, never emphasis.
        single_stars = len(re.findall(r'\*(?=\S)|(?<=\S)\*', line_prose)) - double_stars * 2
        if single_stars < 0:
            single_stars = 0
        if single_stars % 2 != 0:
            # Could be valid if it's a list item marker, check context
            stripped = line.strip()
            if not stripped.startswith('* ') and not stripped.startswith('- '):
                errors.append((i, 'Unclosed * (italic) marker'))

    # Check table structure
    in_table = False
    header_cols = 0
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            if not in_table:
                in_table = True
                header_cols = stripped.count('|') - 1
            else:
                # Check separator row
                if re.match(r'^\|[\s\-:|]+\|$', stripped):
                    sep_cols = stripped.count('|') - 1
                    if sep_cols != header_cols:
                        errors.append(
                            (i, f'Table separator has {sep_cols} columns, header has {header_cols}')
                        )
        else:
            in_table = False

    return errors


def _validate_mermaid_basic(content):
    """Basic mermaid syntax validation without external tools.
    Returns list of (block_num, message) tuples."""
    try:
        import mermaidcheck
    except ImportError:
        return []
    return mermaidcheck.validate_mermaid(content)


def _content_syntax_errors(t, module=None, offline=False):
    """Pass 2: markdown + mermaid syntax validation of lesson.md files."""
    results = []

    md_cmd, md_net = _resolve_md_linter(offline)
    mmdc_cmd, mmdc_net = _resolve_mmdc(offline)

    if md_cmd is None:
        print(f'{YELLOW}no markdown linter available — using basic checks (false positives possible){NC}')
        print(f'{YELLOW}Install: pip install pymarkdownlnt{NC}')
    elif md_net:
        print(f'{YELLOW}pymarkdownlnt not installed — using {"uvx" if md_cmd[0] == "uvx" else "pipx"} fallback (downloads on first use; --offline skips){NC}')
    if mmdc_cmd is None:
        print(f'{YELLOW}mmdc not installed — using basic mermaid checks (false positives possible){NC}')
        print(f'{YELLOW}Install: npm install -g @mermaid-js/mermaid-cli{NC}')
    elif mmdc_net:
        print(f'{YELLOW}mmdc not installed — using npx fallback (cached after first use; --offline skips){NC}')

    if module:
        mods = [module]
    else:
        mods = sorted(d.name for d in t.glob('modules/*') if d.is_dir())

    for m in mods:
        mod_path = t / 'modules' / m
        lesson_path = mod_path / 'lesson.md'
        if not lesson_path.exists():
            continue

        md_errors = []
        mermaid_errors = []

        # Markdown validation
        if md_cmd:
            try:
                result = subprocess.run(
                    [*md_cmd, 'scan', str(lesson_path)],
                    capture_output=True,
                    text=True,
                    timeout=60 if len(md_cmd) > 1 else 30,
                )
                for line in result.stdout.splitlines():
                    if line.startswith('MD'):
                        m2 = re.match(r'(?:Line (\d+), Column \d+: )?(MD\d+)', line)
                        if m2:
                            lineno = int(m2.group(1)) if m2.group(1) else 0
                            code = m2.group(2)
                            md_errors.append((lineno, code))
            except subprocess.TimeoutExpired:
                md_errors.append((0, 'pymarkdown timed out'))
        else:
            md_errors = _validate_markdown_basic(lesson_path)

        # Mermaid validation
        content = lesson_path.read_text()
        if mmdc_cmd:
            blocks = re.findall(r'```mermaid\s*\n(.*?)```', content, re.DOTALL)
            for idx, block in enumerate(blocks, 1):
                if not block.strip():
                    mermaid_errors.append((idx, 'Empty mermaid block'))
                    continue
                import tempfile

                with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
                    f.write(block)
                    tmp_path = f.name
                try:
                    result = subprocess.run(
                        [*mmdc_cmd, '-i', tmp_path, '-t', 'neutral', '--quiet'],
                        capture_output=True,
                        text=True,
                        timeout=120 if len(mmdc_cmd) > 1 else 30,
                    )
                    if result.returncode != 0:
                        err_msg = (
                            result.stderr.strip().split('\n')[0]
                            if result.stderr
                            else 'invalid syntax'
                        )
                        mermaid_errors.append((idx, err_msg))
                except subprocess.TimeoutExpired:
                    mermaid_errors.append((idx, 'mmdc timed out'))
                finally:
                    os.unlink(tmp_path)
        else:
            mermaid_errors = _validate_mermaid_basic(content)

        errors = [
            f'[markdown] line {ln}: {msg}' if ln else f'[markdown] {msg}' for ln, msg in md_errors
        ]
        errors += [f'[mermaid] block {b}: {msg}' for b, msg in mermaid_errors]
        results.append((f'{m}/lesson.md', errors))

    return results


def _quality_checks(t, module=None, max_chars=12000):
    """Pass 3+4: quality gate — delegates to shared quality.py rule engine."""
    try:
        import quality
    except ImportError:
        return []
    return quality.quality_checks(t, module=module, max_chars=max_chars)

def cmd_validate_content(topic: str, module: Optional[str] = None):
    """Deprecated alias → validate (full quality gate)."""
    print(
        f'{YELLOW}validate-content is deprecated — use validate (now includes content syntax){NC}'
    )
    cmd_validate(topic, module)


def cmd_enrich(
    topic: str,
    module: Optional[str] = None,
    types: str = 'cloze,predict,error,diagram',
    dry_run: bool = False,
    render_mode: str = 'api',
):
    """Add cloze/predict/error/diagram enrichments to lesson(s).

    Args:
        render_mode: Diagram render mode ('api', 'local', or 'off')
    """
    _check_topic(topic)

    from enrich import enrich_lesson

    type_list = [t.strip() for t in types.split(',')]

    if module:
        mods = [module]
    else:
        mods = _list_modules(topic)

    if not mods:
        print(f'{YELLOW}No modules found.{NC}')
        return

    for m in mods:
        lesson_path = _module_path(topic, m) / 'lesson.md'
        if not lesson_path.exists():
            print(f'{YELLOW}No lesson.md in module {m}, skipping{NC}')
            continue
        print(f'{CYAN}Enriching: {topic}/{m}{NC}')
        enrich_lesson(str(lesson_path), types=type_list, dry_run=dry_run, render_mode=render_mode)


def cmd_blurting(topic: str, module: str):
    """Brain-dump before review. Type everything you remember. AI compares to lesson."""
    _check_topic(topic)
    path = _check_module(topic, module)
    lesson = path / 'lesson.md'
    if not lesson.exists():
        print(f'{RED}No lesson.md at {lesson}{NC}')
        sys.exit(1)

    content = lesson.read_text()

    # Extract key terms: headings, **bold** text, Think answers, Mermaid captions
    key_terms = set()
    for m in re.finditer(r'\*\*(.+?)\*\*', content):
        t = m.group(1).strip()
        if t and t not in ('Think', 'Predict', 'Cloze', 'Spot the Mistake', 'Answer'):
            key_terms.add(t)
    for m in re.finditer(r'^## (.+)$', content, re.MULTILINE):
        key_terms.add(m.group(1).strip())
    for m in re.finditer(r'> \*\*Answer\*\*: (.+)', content):
        for word in re.findall(r'[A-Za-z][A-Za-z-]+', m.group(1)):
            if len(word) > 3:
                key_terms.add(word)

    key_terms = sorted(key_terms)
    print(f'{CYAN}=== Blurting: {topic}/{module} ==={NC}')
    print(f'{YELLOW}Type everything you remember about this module.{NC}')
    print(f'{YELLOW}Type "DONE" on its own line when finished.{NC}\n')

    lines = []
    while True:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.strip().upper() == 'DONE':
            break
        lines.append(line)

    user_text = ' '.join(lines).lower()

    # Compare
    covered = []
    missing = []
    fuzzy = []
    for term in key_terms:
        tl = term.lower()
        if tl in user_text:
            covered.append(term)
        else:
            # Check if any word from term appears
            term_words = set(tl.split())
            user_words = set(user_text.split())
            overlap = term_words & user_words
            if overlap and len(overlap) >= len(term_words) * 0.5:
                fuzzy.append(term)
            else:
                missing.append(term)

    print(f'\n{GREEN}✓ Covered: {len(covered)}{NC}')
    if covered:
        for c in covered[:10]:
            print(f'  ✓ {c}')
        if len(covered) > 10:
            print(f'  ... and {len(covered) - 10} more')

    print(f'\n{YELLOW}? Fuzzy: {len(fuzzy)}{NC}')
    if fuzzy:
        for f in fuzzy[:5]:
            print(f'  ? {f}')

    print(f'\n{RED}✗ Missing: {len(missing)}{NC}')
    if missing:
        for m in missing[:10]:
            print(f'  ✗ {m}')
        if len(missing) > 10:
            print(f'  ... and {len(missing) - 10} more')

    pct = len(covered) * 100 // len(key_terms) if key_terms else 100
    print(f'\n{CYAN}Recall: {pct}% ({len(covered)}/{len(key_terms)} terms){NC}')
    if pct < 50:
        print(f'{YELLOW}Review before quiz. Key gaps above.{NC}')
    elif pct < 80:
        print(f'{GREEN}Good recall. Review fuzzy terms then quiz.{NC}')
    else:
        print(f'{GREEN}Strong recall. Ready for quiz.{NC}')

    # Save blurt session
    blurt_dir = _topic_path(topic) / 'srs' / 'blurting'
    blurt_dir.mkdir(parents=True, exist_ok=True)
    record = {
        'module': module,
        'date': datetime.now().isoformat(),
        'covered': len(covered),
        'total': len(key_terms),
        'pct': pct,
        'missing': missing,
    }
    with open(blurt_dir / f'{module}-{datetime.now().strftime("%Y%m%d-%H%M%S")}.json', 'w') as f:
        json.dump(record, f, indent=2)
    _record_session(topic, 'blurting', module=module, score=len(covered), total=len(key_terms))


def cmd_fsrs_predict(topic: str):
    """Show FSRS memory model predictions for all cards."""
    _check_topic(topic)
    deck = _load_deck(topic)
    cards = deck.get('cards', {})
    if not cards:
        print(f'{YELLOW}No deck yet. Take a quiz first.{NC}')
        return

    from sm2 import predict_retention

    today = datetime.now()
    total = len(cards)
    avg_stability = 0
    avg_difficulty = 0
    now_retained = 0
    due_retained = 0
    due_count = 0
    card_estimates = []

    for c in cards.values():
        s = c.get('stability', c.get('interval', 1))
        d = c.get('difficulty', 5.0)
        nr = c.get('nextReviewDate', today.strftime('%Y-%m-%d'))

        avg_stability += s
        avg_difficulty += d

        # Current retention
        lr = c.get('lastReviewed')
        if lr:
            try:
                lrd = datetime.strptime(lr, '%Y-%m-%d')
                elapsed = max(0, (today - lrd).days)
                r_now = predict_retention(s, elapsed)
            except ValueError:
                r_now = 0
        else:
            r_now = 0

        next_due = datetime.strptime(nr, '%Y-%m-%d')
        elapsed_at_due = max(0, (next_due - today).days)
        if lr:
            elapsed_at_due = max(0, (next_due - datetime.strptime(lr, '%Y-%m-%d')).days)
        r_due = predict_retention(s, elapsed_at_due) if lr else 0

        now_retained += r_now
        if nr <= today.strftime('%Y-%m-%d'):
            due_count += 1
            due_retained += r_now

        card_estimates.append(
            (c.get('questionId', '?'), s, d, r_now, r_due, nr <= today.strftime('%Y-%m-%d'))
        )

    avg_stability /= total
    avg_difficulty /= total
    avg_retention = now_retained / total * 100
    avg_due_retention = due_retained / max(1, due_count) * 100

    print(f'{CYAN}=== FSRS Memory Model: {topic} ==={NC}\n')
    print(f'Cards: {total}')
    print(f'Avg stability: {avg_stability:.1f} days')
    print(f'Avg difficulty: {avg_difficulty:.1f}/10')
    print(f'Avg retention (now): {avg_retention:.0f}%')
    print(f'Due cards: {due_count} (avg retention: {avg_due_retention:.0f}%)')
    print(f'Stable (S >= 21d): {sum(1 for c in cards.values() if c.get("stability", 0) >= 21)}')
    print(f'Mature (S >= 90d): {sum(1 for c in cards.values() if c.get("stability", 0) >= 90)}')
    print()

    # Cards with lowest predicted retention
    card_estimates.sort(key=lambda x: x[3])
    print(f'{YELLOW}Weakest cards (lowest current retention):{NC}')
    for qid, s, d, r_now, r_due, is_due in card_estimates[:5]:
        due_tag = f'{RED}DUE{NC}' if is_due else ''
        print(f'  {qid}: S={s:.0f}d, D={d:.1f}, retention={r_now:.0f}% {due_tag}')


def cmd_render_diagrams(
    topic: str,
    module: Optional[str] = None,
    render_mode: str = 'api',
    scale: int = 2,
):
    """Render ```mermaid blocks in lesson.md to PNG.

    Args:
        render_mode: 'api' (mermaid.ink) or 'local' (mmdc CLI)
        scale: PNG scale factor (2 = 300dpi)
    """
    _check_topic(topic)

    try:
        from render_diagrams import render_lesson_diagrams
    except ImportError:
        print(f'{RED}render_diagrams.py not found in scripts directory.{NC}')
        sys.exit(1)

    if module:
        mods = [module]
    else:
        mods = _list_modules(topic)

    if not mods:
        print(f'{YELLOW}No modules found.{NC}')
        return

    total = 0
    for m in mods:
        lesson_path = _module_path(topic, m) / 'lesson.md'
        if not lesson_path.exists():
            print(f'{YELLOW}No lesson.md in module {m}, skipping{NC}')
            continue
        print(f'{CYAN}Rendering diagrams: {topic}/{m}{NC}')
        count = render_lesson_diagrams(str(lesson_path), mode=render_mode, scale=scale)
        if count:
            print(f'  Rendered {count} diagram(s) to PNG')
            total += count

    if total:
        print(f'{GREEN}Total: {total} diagram(s) rendered.{NC}')
    else:
        print(f'{YELLOW}No diagrams rendered.{NC}')


def cmd_mindmap(topic: str, module: str):
    """Generate/regenerate Mermaid mindmap for a module via LLM."""
    _check_topic(topic)
    path = _check_module(topic, module)
    lesson = path / 'lesson.md'
    if not lesson.exists():
        print(f'{RED}No lesson.md at {lesson}{NC}')
        sys.exit(1)

    try:
        from enrich import _call_llm
    except ImportError:
        print(f'{RED}enrich.py not found in scripts directory.{NC}')
        sys.exit(1)

    content = lesson.read_text()

    # Check if mindmap already exists
    has_mindmap = '```mermaid\nmindmap' in content

    prompt = (
        f'Current lesson content:\n\n{content}\n\n'
        'Task: Add a Mermaid mindmap at the top of this lesson (after metadata, before Learning Objectives). '
        "Show the module's knowledge hierarchy: central concept → key topics → sub-concepts. "
        'Use `mindmap` syntax. Max 3 levels deep. Keep concise.\n'
        'Format: ```mermaid\nmindmap\n  root((Title))\n    Topic\n      Sub\n```\n'
    )

    if has_mindmap:
        prompt += 'Replace the existing mindmap section with an updated one.\n'
    else:
        prompt += 'Insert the mindmap after the diagrams HTML comment and before ## Learning Objectives.\n'

    prompt += 'Return the full lesson with mindmap inserted/replaced at top.'

    system = (
        'You are a learning science expert. Generate Mermaid mindmaps that show '
        'knowledge hierarchy for a module. Output only the enhanced markdown, no explanation.'
    )

    print(f'{CYAN}Generating mindmap for {topic}/{module}...{NC}', end=' ', flush=True)
    result = _call_llm(prompt, system)

    # Backup and write
    bak = lesson.with_suffix('.md.bak')
    shutil.copy2(lesson, bak)
    lesson.write_text(result)
    print('done')
    print(f'  Backup: {bak}')
    print(f'  Written: {lesson}')

    # Auto-run basic mermaid check (generation-stage guard)
    try:
        import mermaidcheck

        errs = mermaidcheck.validate_mermaid(lesson.read_text())
        if errs:
            print(f'{YELLOW}Mermaid warnings after write:{NC}')
            for idx, msg in errs:
                print(f'  mermaid block {idx}: {msg}')
            print(f'  Run: learn.py checksyntax {topic} {module} --render api')
        else:
            print(f'{GREEN}Mermaid check: OK{NC}')
    except ImportError:
        pass


def cmd_balance_quiz(topic: str, module: str):
    """Re-letter quiz.yaml answers for balance (no 3-run, even spread).

    Deterministic per (topic, module): option text untouched, only letter
    positions move so the correct option lands on a balanced sequence.
    Original file backed up to quiz.yaml.bak.
    """
    _check_topic(topic)
    path = _check_module(topic, module)
    quiz_path = path / 'quiz.yaml'
    if not quiz_path.exists():
        print(f'{RED}No quiz.yaml at {quiz_path}. Create it first (create-cloze is for cloze).{NC}')
        sys.exit(1)
    if yaml is None:
        print(f'{RED}PyYAML not available. Install: pip install --break-system-packages pyyaml{NC}')
        sys.exit(1)

    try:
        import quizbalance
    except ImportError:
        print(f'{RED}quizbalance.py not found in scripts directory.{NC}')
        sys.exit(1)

    data = yaml.safe_load(quiz_path.read_text())
    if not isinstance(data, list):
        print(f'{RED}quiz.yaml must be a list of questions (got {type(data).__name__}).{NC}')
        sys.exit(1)

    new_qs, stats = quizbalance.balance_quiz(data, f'{topic}-{module}')

    bak = quiz_path.with_suffix('.yaml.bak')
    shutil.copy2(quiz_path, bak)
    quiz_path.write_text(
        yaml.dump(new_qs, default_flow_style=False, sort_keys=False, allow_unicode=True)
        + '\n'
    )

    print(f'{CYAN}Balanced quiz: {topic}/{module}{NC}')
    print(f'  Before: {dict(stats["before"])}')
    print(f'  After:  {dict(stats["after"])}')
    print(f'  Questions re-lettered: {stats["mutated"]}, skipped: {stats["skipped"]}')
    print(f'  Backup: {bak}')
    seq = stats['after']
    seq_sorted = sorted(seq.items(), key=lambda kv: (-kv[1], kv[0]))
    top_share = (seq_sorted[0][1] / max(1, sum(seq.values()))) * 100 if seq else 0
    if top_share > 50 or any(seq[a] > (sum(seq.values()) // 4) + 1 for a in seq):
        print(f'{YELLOW}Warning: balance constraint violated (share {top_share:.0f}%){NC}')
        sys.exit(1)
    print(f'{GREEN}Answer spread OK (max share {top_share:.0f}%){NC}')


def _cum_range_validate(topic, lo, hi):
    """Validate a cumulative range; returns (t_path, mods) or exits."""
    t = _check_topic(topic)
    mods = sorted(d.name for d in (t / 'modules').iterdir() if d.is_dir())
    if not mods:
        print(f'{RED}No modules in {topic}.{NC}')
        sys.exit(1)
    course_max = max(int(m.split('-', 1)[0]) for m in mods)
    if lo < 1 or hi < lo:
        print(f'{RED}Invalid range {lo}-{hi} (need 1 <= lo <= hi).{NC}')
        sys.exit(1)
    if hi - lo + 1 > 4:
        print(f'{RED}Range {lo}-{hi} spans {hi - lo + 1} modules — max 4 per cumulative quiz.{NC}')
        sys.exit(1)
    if hi > course_max:
        print(f'{RED}Range ends at module {hi}, beyond course max ({course_max}).{NC}')
        sys.exit(1)
    return t, mods


def cmd_gen_cumulative(topic: str, rng: str, force: bool = False):
    """Generate cumulative_quiz_XX-YY.yaml from existing module question banks.

    Assembles >=8 items covering the given <=4-module window: MCQs and cloze
    are pulled verbatim from the modules' banks (ids rewritten to cum.N),
    true/false items synthesized from cloze pairs when needed. The result is
    re-lettered via quizbalance so rotation/spread rules pass.
    """
    m = re.match(r'^(\d+)-(\d+)$', rng)
    if not m:
        print(f'{RED}Range must look like 01-04 (got "{rng}").{NC}')
        sys.exit(1)
    lo, hi = int(m.group(1)), int(m.group(2))
    t, mods = _cum_range_validate(topic, lo, hi)

    if yaml is None:
        print(f'{RED}PyYAML not available. Install: pip install --break-system-packages pyyaml{NC}')
        sys.exit(1)
    try:
        import quizbalance
    except ImportError:
        print(f'{RED}quizbalance.py not found in scripts directory.{NC}')
        sys.exit(1)

    out_path = t / f'cumulative_quiz_{lo:02d}-{hi:02d}.yaml'
    if out_path.exists() and not force:
        print(f'{RED}{out_path.name} already exists. Use --force to overwrite.{NC}')
        sys.exit(1)

    in_range = [d for d in mods if lo <= int(d.split('-', 1)[0]) <= hi]
    mcq_bank, cloze_bank = [], []
    for mod_name in in_range:
        num = int(mod_name.split('-', 1)[0])
        qp = t / 'modules' / mod_name / 'quiz.yaml'
        cp = t / 'modules' / mod_name / 'cloze.yaml'
        if qp.exists():
            qs = yaml.safe_load(qp.read_text()) or []
            for q in qs:
                if isinstance(q, dict) and isinstance(q.get('options'), dict):
                    q = dict(q)
                    q['source_modules'] = [num]
                    mcq_bank.append(q)
        if cp.exists():
            cs = yaml.safe_load(cp.read_text()) or []
            for c in cs:
                if isinstance(c, dict) and c.get('answer'):
                    c = dict(c)
                    c['source_modules'] = [num]
                    cloze_bank.append(c)

    if len(mcq_bank) < 3 or len(cloze_bank) < 2:
        print(f'{RED}Banks too thin in modules {lo}-{hi}: {len(mcq_bank)} MCQs, {len(cloze_bank)} cloze. '
              f'Need >=3 MCQs and >=2 cloze to build a valid file.{NC}')
        sys.exit(1)

    items, n = [], 0
    def take(bank, k):
        nonlocal n
        got = bank[:k]
        del bank[:k]
        return got

    # 4 MCQ + 3 cloze + 3 tf target (10 items), min floor enforced by quality gate
    for src in take(mcq_bank, 4):
        n += 1
        items.append({
            'id': f'cum.{n}', 'type': 'mcq',
            'question': src.get('question', ''),
            'source_modules': src['source_modules'],
            'options': {k: str(v) for k, v in src['options'].items()},
            'answer': str(src.get('answer', 'a')).lower(),
            'explanation': src.get('explanation', ''),
            'difficulty': int(src.get('difficulty', 2)),
            'tags': ['cross-module'] + list(src.get('tags') or []),
        })
    for src in take(cloze_bank, 3):
        n += 1
        items.append({
            'id': f'cum.{n}', 'type': 'cloze',
            'question': src.get('question', ''),
            'source_modules': src['source_modules'],
            'answer': src.get('answer', ''),
            'explanation': src.get('explanation', ''),
            'difficulty': int(src.get('difficulty', 2)),
            'tags': ['cross-module'] + list(src.get('tags') or []),
        })

    # synthesize T/F statements from remaining cloze until we have >=3 tf
    tf_made = 0
    while len([i for i in items if i['type'] == 'tf']) < 3 and cloze_bank:
        src = cloze_bank.pop(0)
        ans = str(src.get('answer', '')).strip()
        q = str(src.get('question', ''))
        if '{' in q and '}' in q and ans:
            true_stmt = re.sub(r'\{[^}]*\}', ans, q, count=1)
            wrong = re.sub(r'\{[^}]*\}', 'NOT-' + ans.split('/')[0].strip(), q, count=1)
            smod = src['source_modules']
            n += 1
            items.append({'id': f'cum.{n}', 'type': 'tf', 'statement': true_stmt,
                          'source_modules': smod, 'answer': True,
                          'explanation': src.get('explanation', ''),
                          'difficulty': int(src.get('difficulty', 2)),
                          'tags': ['cross-module', 'recall']})
            n += 1
            items.append({'id': f'cum.{n}', 'type': 'tf', 'statement': wrong,
                          'source_modules': smod, 'answer': False,
                          'explanation': f'The blanked term was {ans}.',
                          'difficulty': int(src.get('difficulty', 2)),
                          'tags': ['cross-module', 'misconception']})
            tf_made += 2
    if tf_made == 0:
        print(f'{RED}Could not synthesize any true/false items (cloze questions lack {{blank}} markers).{NC}')
        sys.exit(1)

    # balance mcq answers deterministically
    seed = f'{topic}-cum-{rng}'
    new_items, stats = quizbalance.balance_quiz(items, seed)

    text = yaml.dump(new_items, default_flow_style=False, sort_keys=False, allow_unicode=True) + '\n'
    bak = out_path.with_suffix('.yaml.bak')
    if out_path.exists():
        shutil.copy2(out_path, bak)
        print(f'  Backup: {bak}')
    out_path.write_text(text)

    # verify against the same quality rules validate uses
    try:
        import quality
        errs = quality.cumulative_quality_errors(
            out_path, mods, lambda p: yaml.safe_load(Path(p).read_text()))
        errs = [e for e in errs if e] if isinstance(errs, list) else []
    except Exception as exc:
        errs = [f'quality recheck failed: {exc}']
    print(f'{CYAN}Generated {out_path.name}: {len(new_items)} items '
          f'(mcq={sum(1 for i in new_items if i.get("type") == "mcq")}, '
          f'cloze={sum(1 for i in new_items if i.get("type") == "cloze")}, '
          f'tf={sum(1 for i in new_items if i.get("type") == "tf")}){NC}')
    if errs:
        print(f'{YELLOW}Warning: generated file has quality issues:{NC}')
        for e in errs:
            print(f'  {e}')
        sys.exit(1)
    print(f'{GREEN}Quality gate OK.{NC}')


def cmd_add_question(
    topic: str,
    module: str,
    q: str = typer.Option(..., '--q', help='Question text.'),
    a: str = typer.Option(..., '--a', help='Option a text.'),
    b: str = typer.Option(..., '--b', help='Option b text.'),
    c: str = typer.Option('', '--c', help='Option c text.'),
    d: str = typer.Option('', '--d', help='Option d text.'),
    correct: str = typer.Option(..., '--correct', help='Correct letter a-d.'),
    difficulty: int = typer.Option(2, '--difficulty', min=1, max=3),
    tags: str = typer.Option('concept', '--tags', help='Comma-separated tags.'),
    explanation: str = typer.Option('', '--explain', help='Explanation text.'),
):
    """Append one schema-valid MCQ to a module's quiz.yaml, then rebalance."""
    _check_topic(topic)
    path = _check_module(topic, module)
    quiz_path = path / 'quiz.yaml'
    if yaml is None:
        print(f'{RED}PyYAML not available.{NC}')
        sys.exit(1)
    correct = correct.strip().lower()
    if correct not in ('a', 'b', 'c', 'd'):
        print(f'{RED}--correct must be a/b/c/d (got "{correct}").{NC}')
        sys.exit(1)
    if not c or not d:
        print(f'{RED}Schema requires exactly 4 options (a,b,c,d); provide --c and --d.{NC}')
        sys.exit(1)
    options = {'a': a, 'b': b, 'c': c, 'd': d}

    data = []
    if quiz_path.exists():
        data = yaml.safe_load(quiz_path.read_text()) or []
    if not isinstance(data, list):
        print(f'{RED}quiz.yaml must be a top-level list.{NC}')
        sys.exit(1)
    mod_num = module.split('-', 1)[0]
    next_n = len(data) + 1
    item = {
        'id': f'{mod_num}.{next_n}',
        'question': q,
        'options': {k: options[k] for k in ('a', 'b', 'c', 'd')},
        'answer': correct,
        'explanation': explanation,
        'difficulty': difficulty,
        'tags': [t.strip() for t in tags.split(',') if t.strip()],
    }
    data.append(item)
    quiz_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True) + '\n')
    print(f'{GREEN}Added {item["id"]} to {topic}/{module}/quiz.yaml{NC}')
    cmd_balance_quiz(topic, module)


def cmd_balance_cumulative(topic: str):
    """Re-letter MCQ answers in every cumulative_quiz_*.yaml of a topic."""
    _check_topic(topic)
    if yaml is None:
        print(f'{RED}PyYAML not available.{NC}')
        sys.exit(1)
    try:
        import quizbalance
    except ImportError:
        print(f'{RED}quizbalance.py not found in scripts directory.{NC}')
        sys.exit(1)
    files = sorted(_topic_path(topic).glob('cumulative_quiz_*.yaml'))
    if not files:
        print(f'{YELLOW}No cumulative_quiz_*.yaml files in {topic}.{NC}')
        return
    for cuf in files:
        data = yaml.safe_load(cuf.read_text())
        if not isinstance(data, list):
            print(f'{YELLOW}Skip {cuf.name}: not a top-level list.{NC}')
            continue
        new_qs, stats = quizbalance.balance_quiz(data, f'{topic}-{cuf.stem}')
        shutil.copy2(cuf, cuf.with_suffix('.yaml.bak'))
        cuf.write_text(yaml.dump(new_qs, default_flow_style=False, sort_keys=False, allow_unicode=True) + '\n')
        seq = stats['after']
        total = max(1, sum(seq.values()))
        top_share = (sorted(seq.items(), key=lambda kv: (-kv[1], kv[0]))[0][1] / total) * 100 if seq else 0
        status = 'OK' if top_share <= 50 else 'SKEWED'
        print(f'{cuf.name}: re-lettered {stats["mutated"]}, skipped {stats["skipped"]} — spread {top_share:.0f}% {status}')


def cmd_checksyntax(
    topic: str,
    module: str,
    render: str = 'off',
):
    """Generation-stage syntax check for a module's lesson.md.

    Checks fence balance, mermaid blocks, and code blocks (python3
    py_compile / node --check / bash -n when interpreters exist).
    --render api|local adds a render smoke test via render_diagrams.
    """
    _check_topic(topic)
    path = _check_module(topic, module)
    lesson = path / 'lesson.md'
    if not lesson.exists():
        print(f'{RED}No lesson.md at {lesson}{NC}')
        sys.exit(1)

    try:
        import checksyntax
    except ImportError:
        print(f'{RED}checksyntax.py not found in scripts directory.{NC}')
        sys.exit(1)

    hard, warns = checksyntax.check_lesson(
        lesson.read_text(), render_mode=render, lesson_path=lesson
    )
    for w in warns:
        print(f'  {YELLOW}WARN{NC} {w}')
    if hard:
        print(f'{RED}{len(hard)} error(s) in {topic}/{module}:{NC}')
        for h in hard:
            print(f'  {h}')
        sys.exit(1)
    print(f'{GREEN}Syntax OK: {topic}/{module}{NC}')


# ── CLI ─────────────────────────────────────────────────────────

app = typer.Typer(help='Learn Something — study with spaced repetition (FSRS).')

def _fence_parity_errors(md_path: Path):
    """Fence-parity walker: text-as-closer, unclosed fences, bare openers."""
    errs = []
    try:
        lines = md_path.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError as e:
        return [f'read error: {e}']
    infence = False
    opener = None
    for i, line in enumerate(lines, 1):
        st = line.strip()
        if not st.startswith('```'):
            continue
        if not infence:
            infence = True
            opener = i
            if st == '```':
                errs.append(f'line {i}: bare fence opener — no language tag')
        else:
            if st != '```':
                errs.append(
                    f'line {i}: text-as-closer `{st}` — fence opened at line {opener} never closed cleanly'
                )
            infence = False
    if infence:
        errs.append(f'unclosed fence from line {opener} to EOF')
    return errs


def _cloze_extract_errors(cloze_path: Path):
    """Cloze answers must be extractable from {blank} markers in the question."""
    if yaml is None:
        return []
    try:
        data = yaml.safe_load(cloze_path.read_text())
    except Exception as e:
        return [f'parse error: {e}']
    if not isinstance(data, list):
        return ['not a top-level list']
    errs = []
    for q in data:
        qid = q.get('id', '?')
        question = str(q.get('question', ''))
        answer = str(q.get('answer', '')).strip()
        blanks = re.findall(r'\{([^}]{1,120})\}', question)
        blank_blob = ' / '.join(blanks).lower()
        parts = [p.strip().lower() for p in re.split(r'\s*/\s*', answer) if p.strip()]
        if not blanks:
            errs.append(f'{qid}: no {{blank}} marker in question')
            continue
        unmatched = [p for p in parts if p and p not in blank_blob]
        if unmatched:
            errs.append(f'{qid}: answer "{answer}" not extractable from blanks {blanks}')
    return errs


def _consistency_errors(t: Path):
    """Cross-file consistency: H1↔slug↔numbering, quiz id prefixes, dirs⊆syllabus."""
    errs = []
    # syllabus module ids vs directories
    syllabus_ids = []
    syl = t / 'syllabus.yaml'
    if yaml is not None and syl.exists():
        try:
            data = yaml.safe_load(syl.read_text()) or {}
            syllabus_ids = [int(m.get('id')) for m in data.get('modules', []) if m.get('id') is not None]
        except Exception:
            pass
    mod_dirs = sorted(d for d in (t / 'modules').glob('*-*') if d.is_dir()) if (t / 'modules').exists() else []
    dir_nums = {}
    for d in mod_dirs:
        m = re.match(r'^(\d+)-', d.name)
        if m:
            dir_nums[int(m.group(1))] = d.name
        else:
            errs.append(f'modules/{d.name}: directory name not NN-kebab-case')
    if syllabus_ids:
        extra = set(dir_nums) - set(syllabus_ids)
        missing = set(syllabus_ids) - set(dir_nums)
        for n in sorted(extra):
            errs.append(f'directory modules/{dir_nums[n]} has no syllabus module id {n}')
        for n in sorted(missing):
            errs.append(f'syllabus module id {n} has no modules/NN- directory')
    # per-module checks
    for num, dirname in sorted(dir_nums.items()):
        lesson = t / 'modules' / dirname / 'lesson.md'
        quiz = t / 'modules' / dirname / 'quiz.yaml'
        cloze = t / 'modules' / dirname / 'cloze.yaml'
        if lesson.exists():
            content = lesson.read_text(errors='replace')
            h1 = re.search(r'(?m)^#\s*Module\s+(\d+)\s*:', content)
            if not h1:
                errs.append(f'modules/{dirname}/lesson.md: H1 missing "# Module NN:" form')
            elif int(h1.group(1)) != num:
                errs.append(
                    f'modules/{dirname}/lesson.md: H1 says Module {h1.group(1)} but directory number is {num}'
                )
        if yaml is not None and quiz.exists():
            try:
                qs = yaml.safe_load(quiz.read_text())
                if isinstance(qs, list):
                    for q in qs:
                        qid = str(q.get('id', ''))
                        m = re.match(r'^(\d+)\.', qid)
                        if m and int(m.group(1)) != num:
                            errs.append(
                                f'modules/{dirname}/quiz.yaml: id "{qid}" prefix does not match module number {num}'
                            )
                        elif '.' not in qid:
                            errs.append(f'modules/{dirname}/quiz.yaml: id "{qid}" not N.M form')
            except Exception as e:
                errs.append(f'modules/{dirname}/quiz.yaml: parse error {e}')
        if yaml is not None and cloze.exists():
            for e in _cloze_extract_errors(cloze):
                errs.append(f'modules/{dirname}/cloze.yaml: {e}')
    return errs


def cmd_doctor(topic: str):
    """Structural health check: fence parity + cross-file consistency (beyond validate)."""
    _check_topic(topic)
    t = _topic_path(topic)
    results = []
    md_files = sorted(p for p in t.rglob('*.md') if 'srs' not in p.relative_to(t).parts)
    for md in md_files:
        rel = md.relative_to(t)
        errs = _fence_parity_errors(md)
        results.append((f'{rel}', errs))
    cons = _consistency_errors(t)
    if cons:
        results.append(('_consistency', cons))
    any_errs = False
    for name, errors in results:
        if errors:
            any_errs = True
            print(f'{RED}{name}: {len(errors)} finding(s){NC}')
            for err in errors:
                print(f'  - {err}')
        else:
            print(f'{GREEN}{name}: OK{NC}')
    if not any_errs:
        print(f'\n{GREEN}Doctor: no structural issues found.{NC}')
    else:
        print(f'\n{YELLOW}Doctor findings above are advisory — run validate for the quality gate.{NC}')
    sys.exit(0)


def cmd_lint_mermaid(topic: str, module: Optional[str] = None):
    """Advisory mermaid safe-mode lint: risky-but-parseable patterns (quote labels etc.)."""
    _check_topic(topic)
    t = _topic_path(topic)
    try:
        import mermaidcheck
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent))
        import mermaidcheck

    if module:
        paths = [_check_module(topic, module) / 'lesson.md']
    else:
        mroot = t / 'modules'
        paths = sorted(mroot.glob('*/lesson.md')) if mroot.exists() else []

    total = 0
    for p in paths:
        if not p.exists():
            continue
        issues = mermaidcheck.safe_mode_errors(p.read_text())
        rel = p.relative_to(t)
        if issues:
            total += len(issues)
            print(f'{YELLOW}{rel}: {len(issues)} finding(s){NC}')
            for bidx, ln, msg in issues:
                print(f'  - block {bidx} line {ln}: {msg}')
        else:
            print(f'{GREEN}{rel}: OK{NC}')

    if total == 0:
        print(f'\n{GREEN}Mermaid safe-mode: clean.{NC}')
    else:
        print(
            f'\n{YELLOW}{total} advisory finding(s). These may render today but are known '
            f'failure sources across mermaid versions — quote labels/subgraph titles.{NC}'
        )
    sys.exit(0)


app.command('init')(cmd_init)
app.command('start')(cmd_start)
app.command('create-module')(cmd_create_module)
app.command('create-cloze')(cmd_create_cloze)
app.command('quiz')(cmd_quiz)
app.command('cloze')(cmd_cloze)
app.command('cumulative-quiz')(cmd_cumulative_quiz)
app.command('explain')(cmd_explain)
app.command('review')(cmd_review)
app.command('stats')(cmd_stats)
app.command('export')(cmd_export)
app.command('rate')(cmd_rate)
app.command('flag')(cmd_flag)
app.command('feedback')(cmd_feedback)
app.command('analytics')(cmd_analytics)
app.command('forecast')(cmd_forecast)
app.command('study-plan')(cmd_study_plan)
app.command('epub')(cmd_epub)
app.command('epub-regen')(cmd_epub_regen)
app.command('epub-verify')(cmd_epub_verify)
app.command('epub-list-themes')(cmd_epub_list_themes)
app.command('pdf')(cmd_pdf)
app.command('pdf-regen')(cmd_pdf_regen)
app.command('sync')(cmd_sync)
app.command('sync-pull')(cmd_sync_pull)
app.command('validate')(cmd_validate)
app.command('validate-content')(cmd_validate_content)
app.command('feynman')(cmd_explain)
app.command('enrich')(cmd_enrich)
app.command('blurting')(cmd_blurting)
app.command('fsrs-predict')(cmd_fsrs_predict)
app.command('render-diagrams')(cmd_render_diagrams)
app.command('mindmap')(cmd_mindmap)
app.command('balance-quiz')(cmd_balance_quiz)
app.command('gen-cumulative')(cmd_gen_cumulative)
app.command('add-question')(cmd_add_question)
app.command('balance-cumulative')(cmd_balance_cumulative)
app.command('checksyntax')(cmd_checksyntax)
app.command('doctor')(cmd_doctor)
app.command('lint-mermaid')(cmd_lint_mermaid)


def _reader_subjects_path(reader_path=None):
    """Return the Reader's subjects directory."""
    if reader_path:
        return Path(reader_path)
    return Path.home() / '.coursereader' / 'subjects'


if __name__ == '__main__':
    app()
