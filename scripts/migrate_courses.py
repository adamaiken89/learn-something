#!/usr/bin/env python3
"""Migrate course files to canonical learn-something schema.

Canonical forms (see learn-something-schema/):
  quiz.yaml              top-level list of {id "N.M", question, options {a,b,c,d},
                           answer "a"-"d", explanation?, difficulty 1-3, tags []}
  cloze.yaml             top-level list of {id "c.N", question, answer,
                           explanation?, difficulty, tags}
  cumulative_quiz*.yaml  top-level list of {id "cum.N", type mcq|cloze|tf,
                           question|statement, source_modules [int], options?,
                           answer, explanation?, difficulty, tags}
  srs/deck.json          {"cards": {"<course>-<module>-<qid>": Card}}
  cumulative filenames   zero-padded: cumulative_quiz_01-04.yaml

Run from the subjects directory. Dry-run by default; --apply writes.

Usage:
  python3 migrate_courses.py [course...] [--apply] [--verbose]

No backups written -- git covers undo. Idempotent: already-canonical files
report "no change" and are not rewritten.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

SUBJECTS_DIR = Path.cwd()

MODULE_RE = re.compile(r'^(\d{2})-[a-z0-9]+(-[a-z0-9]+)*$')
CUM_PAD_RE = re.compile(r'^cumulative_quiz_(\d+)-(\d+)\.yaml$')

VERBOSE = False
APPLY = False


def log(msg):
    print(msg)


def vlog(msg):
    if VERBOSE:
        print(msg)


def _coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _options_from(o):
    """Normalize options (dict A-D or list of {label,text} or list of str) to {a,b,c,d}."""
    if isinstance(o, dict):
        return {str(k).strip().lower(): v for k, v in o.items()}
    if isinstance(o, list):
        opts = {}
        for i, e in enumerate(o):
            key = chr(97 + i)
            if isinstance(e, dict):
                key = str(e.get('label') or key).strip().lower()
                opts[key] = e.get('text') or ''
            else:
                opts[key] = str(e)
        return opts
    return None


def _answer_letter(ans):
    if ans is None:
        return 'a'
    if isinstance(ans, int):
        return 'abcd'[ans] if 0 <= ans < 4 else 'a'
    return str(ans).strip().lower()


def normalize_quiz_item(item, mod_num, idx):
    q = {'id': f'{mod_num}.{idx + 1}'}
    q['question'] = item.get('question') or item.get('text') or ''

    opts = None
    if 'options' in item:
        opts = _options_from(item['options'])
    elif 'choices' in item:
        opts = _options_from(item['choices'])
    elif 'answers' in item:
        opts = _options_from(item['answers'])
    q['options'] = opts or {}

    ans = item.get('answer')
    if ans is None:
        ans = item.get('correctOption')
    if ans is None:
        ans = item.get('correct')
    q['answer'] = _answer_letter(ans)

    if item.get('explanation'):
        q['explanation'] = item['explanation']
    difficulty = item.get('difficulty')
    q['difficulty'] = difficulty if difficulty in (1, 2, 3) else 2
    tags = item.get('tags') or []
    if item.get('concept') and item['concept'] not in tags:
        tags = list(tags) + [item['concept']]
    q['tags'] = tags
    return q


def normalize_cloze_item(item, idx):
    import re as _re

    q = {'id': f'c.{idx + 1}'}
    q['question'] = item.get('question') or item.get('text') or ''
    ans = item.get('answer')
    if ans is None and 'answers' in item:
        a = item['answers']
        ans = a[0] if isinstance(a, list) and a else (a if isinstance(a, str) else '')
    if ans is None or (isinstance(ans, str) and not ans.strip()):
        blanks = _re.findall(r'\{([^{}]*)\}', q['question'])
        ans = ' / '.join(b.strip() for b in blanks) if blanks else ''
    q['answer'] = str(ans) if ans is not None else ''
    if item.get('explanation'):
        q['explanation'] = item['explanation']
    difficulty = item.get('difficulty')
    q['difficulty'] = difficulty if difficulty in (1, 2, 3) else 2
    q['tags'] = item.get('tags') or []
    return q


def normalize_cumulative_item(item, idx):
    q = {'id': f'cum.{idx + 1}'}
    qtype = item.get('type')
    question = item.get('question') or item.get('text') or item.get('statement') or ''
    opts_raw = item.get('options')
    opts_map = _options_from(opts_raw) if isinstance(opts_raw, (dict, list)) else None
    tf_like = bool(
        'statement' in item
        or question.strip().lower().startswith(('true or false', 'true/false', 't/f', '真'))
        or (
            opts_map is not None
            and len(opts_map) == 2
            and {'t', 'true', 'yes', 'y', '1', '真', '是'} & set(opts_map.keys())
            and {'f', 'false', 'no', 'n', '0', '假', '否'} & set(opts_map.keys())
        )
    )
    if qtype not in ('mcq', 'cloze', 'tf'):
        qtype = 'tf' if tf_like else ('mcq' if opts_map else 'cloze')
    if qtype == 'mcq' and tf_like and len(opts_map or {}) == 2:
        qtype = 'tf'
    q['type'] = qtype

    sm = item.get('source_modules') or []
    q['source_modules'] = [m for m in (int(m) for m in sm) if m is not None]
    if not q['source_modules']:
        q['source_modules'] = []

    if qtype == 'tf':
        q['statement'] = item.get('statement') or question
        ans = item.get('answer')
        if opts_map is not None and isinstance(ans, str) and len(ans) <= 1:
            raw_val = opts_map.get(ans.strip().lower(), '')
            ans = str(raw_val).strip().lower() in ('true', 't', 'yes', 'y', '1', '真', '是')
        q['answer'] = (
            bool(ans)
            if isinstance(ans, bool)
            else str(ans).strip().lower() in ('true', 't', 'yes', 'y', '1')
        )
    else:
        q['question'] = question
        if opts_map:
            q['options'] = opts_map
        ans = item.get('answer')
        if qtype == 'cloze':
            if isinstance(ans, list):
                q['answer'] = str(ans[0]) if ans else ''
            else:
                q['answer'] = str(ans) if ans is not None else ''
        else:
            q['answer'] = _answer_letter(ans)

    if item.get('explanation'):
        q['explanation'] = item['explanation']
    difficulty = item.get('difficulty')
    q['difficulty'] = difficulty if difficulty in (1, 2, 3) else 2
    q['tags'] = item.get('tags') or []
    return q


def unwrap(data):
    """Return question list from wrapped/dict or list shapes."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ('questions', 'quiz'):
            if key in data and isinstance(data[key], list):
                return data[key]
        return []
    return []


def migrate_yaml(path, kind, mod_num=None):
    """Normalize a quiz/cloze/cumulative yaml file. Returns ('ok'|'skip'|'parse-error'|'needs-authoring', msg)."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        return 'parse-error', str(e).splitlines()[0][:80]

    if data is None:
        data = []

    items = unwrap(data)
    if not items:
        return 'skip', 'no questions found'

    normalized = []
    needs_authoring = False
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            return 'skip', f'item {i} not a mapping'
        if kind == 'quiz':
            n = normalize_quiz_item(item, mod_num, i)
        elif kind == 'cloze':
            n = normalize_cloze_item(item, i)
        else:
            n = normalize_cumulative_item(item, i)
        if kind == 'cloze' and not n.get('answer'):
            needs_authoring = True
        normalized.append(n)

    if normalized == items:
        return 'no-change', f'{len(normalized)} questions'

    if APPLY:
        with open(path, 'w') as f:
            yaml.safe_dump(
                normalized, f, sort_keys=False, allow_unicode=True, default_flow_style=False
            )
    return 'needs-authoring' if needs_authoring else 'ok', f'{len(normalized)} questions'


def pad_cumulative_filenames(course_dir):
    """Rename cumulative_quiz_N-M.yaml -> cumulative_quiz_NN-MM.yaml. Returns list of (old, new)."""
    renames = []
    for f in course_dir.glob('cumulative_quiz_*.yaml'):
        m = CUM_PAD_RE.match(f.name)
        if not m:
            continue
        lo, hi = m.group(1), m.group(2)
        if len(lo) == 2 and len(hi) == 2:
            continue
        new_name = f'cumulative_quiz_{int(lo):02d}-{int(hi):02d}.yaml'
        if new_name != f.name:
            renames.append((f, f.with_name(new_name)))
    return renames


def migrate_deck(course_dir, deck_path, course):
    try:
        with open(deck_path) as f:
            data = json.load(f)
    except Exception as e:
        return 'parse-error', str(e)[:80]

    if isinstance(data, dict) and 'cards' in data and isinstance(data['cards'], dict):
        return 'no-change', f'{len(data["cards"])} cards'

    raw = data['cards'] if isinstance(data, dict) and isinstance(data.get('cards'), list) else data
    if not isinstance(raw, list):
        return 'skip', 'unrecognized deck shape'

    mod_map = {}
    for md in (course_dir / 'modules').glob('*'):
        m = MODULE_RE.match(md.name)
        if md.is_dir() and m:
            mod_map[int(m.group(1))] = md.name

    cards = {}
    for c in raw:
        if not isinstance(c, dict):
            continue
        num = _coerce_int(c.get('module'))
        module = mod_map.get(num, f'{num:02d}' if num is not None else '00')
        qid = str(c.get('id') or '0')
        card_id = f'{course}-{module}-{qid}'
        answer = c.get('answer_text')
        if not answer and c.get('options'):
            opts = c.get('options')
            if isinstance(opts, dict) and c.get('answer'):
                answer = opts.get(str(c['answer']), '')
        if not answer:
            answer = str(c.get('answer') or '')
        nrd = c.get('next_review') or c.get('due') or date.today().isoformat()
        card = {
            'id': card_id,
            'questionId': qid,
            'moduleId': module,
            'courseId': course,
            'question': c.get('question') or '',
            'answer': answer,
            'easeFactor': c.get('ease_factor', 2.5),
            'interval': c.get('interval', 0),
            'repetitions': c.get('repetitions', 0),
            'nextReviewDate': nrd,
            'lastReviewed': c.get('last_reviewed'),
            'isStarred': c.get('is_starred', False),
        }
        cards[card_id] = card

    if APPLY:
        with open(deck_path, 'w') as f:
            json.dump({'cards': cards}, f, indent=2, ensure_ascii=False)

    return 'ok', f'{len(cards)} cards'


def migrate_course(course):
    course_dir = SUBJECTS_DIR / course
    if not course_dir.is_dir():
        log(f'{course}: NOT FOUND')
        return

    log(f'=== {course} ===')
    modules = sorted(course_dir.glob('modules/*'))
    for mod_dir in modules:
        if not mod_dir.is_dir():
            continue
        m = MODULE_RE.match(mod_dir.name)
        if not m:
            continue
        mod_num = int(m.group(1))
        for fname, kind in (('quiz.yaml', 'quiz'), ('cloze.yaml', 'cloze')):
            path = mod_dir / fname
            if not path.exists():
                continue
            status, msg = migrate_yaml(path, kind, mod_num)
            vlog(f'  {path.relative_to(SUBJECTS_DIR)}: {status} ({msg})')
            if status in ('parse-error', 'needs-authoring'):
                log(f'  {fname} in {mod_dir.name}: {status} -- {msg}')

    for path in sorted(course_dir.glob('cumulative_quiz*.yaml')):
        status, msg = migrate_yaml(path, 'cumulative')
        vlog(f'  {path.name}: {status} ({msg})')
        if status == 'parse-error':
            log(f'  cumulative {path.name}: parse-error -- {msg}')

    for old, new in pad_cumulative_filenames(course_dir):
        if APPLY:
            old.rename(new)
            log(f'  renamed {old.name} -> {new.name}')
        else:
            log(f'  would rename {old.name} -> {new.name}')

    deck_path = course_dir / 'srs' / 'deck.json'
    if deck_path.exists():
        status, msg = migrate_deck(course_dir, deck_path, course)
        log(f'  srs/deck.json: {status} ({msg})')


def main():
    global APPLY, VERBOSE
    args = [a for a in sys.argv[1:]]
    APPLY = '--apply' in args
    VERBOSE = '--verbose' in args
    courses = [a for a in args if not a.startswith('--')]

    if not courses:
        courses = sorted(
            d.name
            for d in SUBJECTS_DIR.iterdir()
            if d.is_dir() and (d / 'syllabus.yaml').exists() or (d / 'modules').is_dir()
        )

    for course in courses:
        migrate_course(course)
        print()

    if not APPLY:
        print('Dry run complete. Re-run with --apply to write changes.')


if __name__ == '__main__':
    main()
