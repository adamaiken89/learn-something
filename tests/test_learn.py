#!/usr/bin/env python3
"""Tests for scripts/learn.py — helpers, CLI commands."""

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import learn


def _make_subject(base, name, lang='en'):
    path = Path(str(base)) / name
    (path / 'modules').mkdir(parents=True)
    (path / 'srs').mkdir(parents=True)
    src = learn.SKILL_DIR / 'templates' / 'syllabus.yaml'
    if src.exists():
        content = src.read_text()
        content = content.replace('"[Subject]"', f'"{name}"')
        content = content.replace('language: en', f'language: {lang}')
        (path / 'syllabus.yaml').write_text(content)
    return path


def _make_module(base, subject, module, answers='B', num=1):
    mod_path = Path(str(base)) / subject / 'modules' / module
    mod_path.mkdir(parents=True, exist_ok=True)
    (mod_path / 'lesson.md').write_text(f'# {module}\n\nContent.\n')
    if isinstance(answers, str):
        answers_l = list(answers)
    else:
        answers_l = list(answers)
    while len(answers_l) < num:
        answers_l.extend(answers_l)
    answers_l = answers_l[:num]
    lines = []
    for i, ans in enumerate(answers_l, 1):
        lines.append(
            f'- id: "{module}.{i}"\n'
            f'  question: "Q{i}?"\n'
            f'  options:\n    A: "OptA"\n    B: "OptB"\n'
            f'    C: "OptC"\n    D: "OptD"\n'
            f'  answer: {ans}\n'
            f'  explanation: "Exp{i}."\n'
            f'  difficulty: 1\n  tags: [test]'
        )
    (mod_path / 'quiz.yaml').write_text('\n'.join(lines))
    return mod_path


def _make_quality_module(base, subject, module):
    """Compliant module: lesson + 8-question quiz that pass the quality gate."""
    mod_path = Path(str(base)) / subject / 'modules' / module
    mod_path.mkdir(parents=True, exist_ok=True)
    lesson = (
        f'# {module}\n\n'
        'Intro.\n\n'
        '```mermaid\n'
        'mindmap\n'
        '  root((Topic))\n'
        '    Idea\n'
        '```\n\n'
        '```mermaid\n'
        'flowchart LR\n  A-->B\n'
        '```\n\n'
        '**Think**\n\nWhy? {blank} missing.\n\n'
        '**Cloze**\n\nfill {blank}\n\n'
        '**Predict**\n\nnext step?\n\n'
        '**Spot the Mistake**\n\nfind the error.\n'
    )
    (mod_path / 'lesson.md').write_text(lesson)
    answers = 'BCDA' * 2  # 8 questions, each letter twice, no 3-run
    lines = []
    for i, ans in enumerate(answers, 1):
        lines.append(
            f'- id: "{module}.{i}"\n'
            f'  question: "Q{i}?"\n'
            f'  options:\n    A: "OptA"\n    B: "OptB"\n'
            f'    C: "OptC"\n    D: "OptD"\n'
            f'  answer: {ans}\n'
            f'  explanation: "Exp{i}."\n'
            f'  difficulty: {1 if i % 2 else 2}\n  tags: [test]'
        )
    (mod_path / 'quiz.yaml').write_text('\n'.join(lines))
    return mod_path


def _make_deck(subject_dir, cards):
    """Write deck in dict format: {"cards": {"id": card}}."""
    p = Path(str(subject_dir)) / 'srs' / 'deck.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(cards, list):
        # Convert old array format to dict format
        deck_dict = {}
        for card in cards:
            cid = card.get('id', 'unknown')
            deck_dict[cid] = card
        cards = {'cards': deck_dict}
    elif isinstance(cards, dict) and 'cards' in cards:
        pass  # already dict format
    else:
        cards = {'cards': cards}
    p.write_text(json.dumps(cards, indent=2))
    return p


# ── Subject helpers ──────────────────────────────────────────────


def test_subject_path():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            p = learn._topic_path('x')
            assert str(p) == str(base / 'x')
        finally:
            learn.SUBJECTS_DIR = orig
    print('  subject_path: OK')


def test_module_path():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            p = learn._module_path('s', 'm')
            assert str(p) == str(base / 's' / 'modules' / 'm')
        finally:
            learn.SUBJECTS_DIR = orig
    print('  module_path: OK')


def test_list_modules():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            (base / 's' / 'modules' / '01-a' / 'lesson.md').parent.mkdir(parents=True)
            (base / 's' / 'modules' / '01-a' / 'lesson.md').write_text('# a')
            (base / 's' / 'modules' / '02-b' / 'lesson.md').parent.mkdir(parents=True)
            (base / 's' / 'modules' / '02-b' / 'lesson.md').write_text('# b')
            (base / 's' / 'modules' / '03-no-lesson').mkdir(parents=True)
            mods = learn._list_modules('s')
            assert mods == ['01-a', '02-b']
        finally:
            learn.SUBJECTS_DIR = orig
    print('  list_modules: OK')


def test_load_save_deck():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            deck = {'cards': {'s-m1-1': {'id': 's-m1-1', 'question': 'q?'}}}
            learn._save_deck('s', deck)
            loaded = learn._load_deck('s')
            assert loaded == deck
        finally:
            learn.SUBJECTS_DIR = orig
    print('  load_save_deck: OK')


def test_load_save_stats():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            stats = {'sessions': [{'date': '2024-01-01', 'type': 'quiz'}]}
            learn._save_stats('s', stats)
            loaded = learn._load_stats('s')
            assert loaded == stats
        finally:
            learn.SUBJECTS_DIR = orig
    print('  load_save_stats: OK')


def test_record_session():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            learn._record_session('s', 'quiz', module='m1', score=3, total=5)
            stats = learn._load_stats('s')
            assert len(stats['sessions']) == 1
            entry = stats['sessions'][0]
            assert entry['type'] == 'quiz'
            assert entry['module'] == 'm1'
            assert entry['score'] == 3
            assert entry['total'] == 5
        finally:
            learn.SUBJECTS_DIR = orig
    print('  record_session: OK')


# ── CLI: init ────────────────────────────────────────────────────


def test_cmd_init_creates_dirs():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            learn.cmd_init(topic='mytopic', lang='en')
            sp = base / 'mytopic'
            assert sp.exists()
            assert (sp / 'modules').exists()
            assert (sp / 'srs').exists()
            assert (sp / 'syllabus.yaml').exists()
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_init_creates_dirs: OK')


def test_cmd_init_lang():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            learn.cmd_init(topic='zhsub', lang='zh')
            syllabus = (base / 'zhsub' / 'syllabus.yaml').read_text()
            assert 'language: zh' in syllabus
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_init_lang: OK')


def test_cmd_init_already_exists():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 'dup')
            try:
                learn.cmd_init(topic='dup', lang='en')
                assert False, 'Should have exited'
            except SystemExit:
                pass
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_init_already_exists: OK')


# ── CLI: start ────────────────────────────────────────────────────


def test_cmd_start_shows_overview():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_module(base, 's', '01-intro')
            learn.cmd_start(topic='s')
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_start_shows_overview: OK')


def test_cmd_start_missing_subject_exits():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            try:
                learn.cmd_start(topic='nonexist')
                assert False, 'Should have exited'
            except SystemExit:
                pass
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_start_missing_subject_exits: OK')


# ── CLI: explain ──────────────────────────────────────────────────


def test_cmd_explain_shows_prompt():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_module(base, 's', '01-intro')
            learn.cmd_explain(topic='s', module='01-intro')
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_explain_shows_prompt: OK')


def test_cmd_explain_missing_module_exits():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            try:
                learn.cmd_explain(topic='s', module='nonexist')
                assert False, 'Should have exited'
            except SystemExit:
                pass
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_explain_missing_module_exits: OK')


# ── CLI: create-module ───────────────────────────────────────────


def test_cmd_create_module():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            learn.cmd_create_module(topic='s', module_id='01-intro')
            mp = base / 's' / 'modules' / '01-intro'
            assert mp.exists()
            assert (mp / 'lesson.md').exists()
            assert (mp / 'quiz.yaml').exists()
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_create_module: OK')


def test_cmd_create_module_with_name():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            learn.cmd_create_module(topic='s', module_id='01-intro', name='Intro')
            lesson = (base / 's' / 'modules' / '01-intro' / 'lesson.md').read_text()
            assert 'Intro' in lesson
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_create_module_with_name: OK')


def test_cmd_create_module_already_exists():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_module(base, 's', '01-intro')
            try:
                learn.cmd_create_module(topic='s', module_id='01-intro')
                assert False, 'Should have exited'
            except SystemExit:
                pass
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_create_module_already_exists: OK')


def test_cmd_create_module_invalid_id():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            for invalid_id in ['intro', '1-intro', '01_Intro', '01-intro!', '001-intro']:
                try:
                    learn.cmd_create_module(topic='s', module_id=invalid_id)
                    assert False, f'Should have exited for {invalid_id}'
                except SystemExit:
                    pass
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_create_module_invalid_id: OK')


def test_cmd_create_module_valid_id():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            learn.cmd_create_module(topic='s', module_id='01-intro')
            mp = base / 's' / 'modules' / '01-intro'
            assert mp.exists()
            learn.cmd_create_module(topic='s', module_id='02-core-concepts')
            mp2 = base / 's' / 'modules' / '02-core-concepts'
            assert mp2.exists()
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_create_module_valid_id: OK')


# ── CLI: quiz ────────────────────────────────────────────────────


def test_cmd_quiz_creates_cards():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_module(base, 's', 'm1', answers='B', num=2)
            inputs = ['b', 'b']  # both correct → B
            with (
                patch('builtins.input', side_effect=inputs),
                patch('random.shuffle', lambda x: None),
            ):
                learn.cmd_quiz(topic='s', module='m1')
            deck = learn._load_deck('s')
            cards = deck.get('cards', {})
            assert len(cards) == 2
            for card in cards.values():
                assert card['repetitions'] == 1
                assert card['interval'] >= 1
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_quiz_creates_cards: OK')


def test_cmd_quiz_wrong_answer_resets():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_module(base, 's', 'm1', answers='B', num=1)
            existing = {
                'cards': {
                    's-m1-m1.1': {
                        'id': 's-m1-m1.1',
                        'questionId': 'm1.1',
                        'moduleId': 'm1',
                        'courseId': 's',
                        'question': 'Q1?',
                        'options': {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd'},
                        'answer': 'B',
                        'explanation': '',
                        'tags': [],
                        'easeFactor': 2.5,
                        'interval': 30,
                        'repetitions': 5,
                        'nextReviewDate': '2024-01-01',
                        'lastReviewed': '2024-01-01',
                        'isStarred': False,
                    }
                }
            }
            _make_deck(base / 's', existing)
            with patch('builtins.input', return_value='a'), patch('random.shuffle', lambda x: None):
                learn.cmd_quiz(topic='s', module='m1')
            deck = learn._load_deck('s')
            cards = deck.get('cards', {})
            assert len(cards) == 1
            card = list(cards.values())[0]
            assert card['repetitions'] == 0
            assert card['interval'] < 30  # decreased after wrong answer
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_quiz_wrong_answer_resets: OK')


# ── CLI: cloze ──────────────────────────────────────────────────


def _make_cloze(base, subject, module, answers=None, num=3):
    """Create cloze.yaml for a module."""
    mod_path = Path(str(base)) / subject / 'modules' / module
    mod_path.mkdir(parents=True, exist_ok=True)
    if answers is None:
        answers = ['term1', 'term2', 'term3'][:num]
    lines = []
    for i, ans in enumerate(answers, 1):
        lines.append(
            f'- id: "c.{i}"\n'
            f'  question: "Complete: The {{blank}} is important"\n'
            f'  answer: "{ans}"\n'
            f'  explanation: "Why {ans} matters"\n'
            f'  difficulty: 1\n  tags: [terminology]'
        )
    (mod_path / 'cloze.yaml').write_text('\n'.join(lines))
    return mod_path


def test_cmd_cloze_creates_cards():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_module(base, 's', 'm1')
            _make_cloze(base, 's', 'm1', answers=['alpha', 'beta', 'gamma'])
            inputs = ['alpha', 'beta', 'gamma']  # all correct
            with (
                patch('builtins.input', side_effect=inputs),
                patch('random.shuffle', lambda x: None),
            ):
                learn.cmd_cloze(topic='s', module='m1')
            deck = learn._load_deck('s')
            cards = deck.get('cards', {})
            assert len(cards) == 3
            for card in cards.values():
                assert card['repetitions'] == 1
                assert card['interval'] >= 1
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_cloze_creates_cards: OK')


def test_cmd_cloze_wrong_answer_resets():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_module(base, 's', 'm1')
            _make_cloze(base, 's', 'm1', answers=['correct'], num=1)
            existing = {
                'cards': {
                    's-m1-c.1': {
                        'id': 's-m1-c.1',
                        'questionId': 'c.1',
                        'moduleId': 'm1',
                        'courseId': 's',
                        'question': 'Complete: The {blank} is important',
                        'answer': 'correct',
                        'explanation': '',
                        'tags': [],
                        'easeFactor': 2.5,
                        'interval': 30,
                        'repetitions': 5,
                        'nextReviewDate': '2024-01-01',
                        'lastReviewed': '2024-01-01',
                        'isStarred': False,
                    }
                }
            }
            _make_deck(base / 's', existing)
            with (
                patch('builtins.input', return_value='wrong'),
                patch('random.shuffle', lambda x: None),
            ):
                learn.cmd_cloze(topic='s', module='m1')
            deck = learn._load_deck('s')
            cards = deck.get('cards', {})
            assert len(cards) == 1
            card = list(cards.values())[0]
            assert card['repetitions'] == 0
            assert card['interval'] < 30  # decreased after wrong answer
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_cloze_wrong_answer_resets: OK')


def test_cmd_create_cloze():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_module(base, 's', 'm1')
            learn.cmd_create_cloze(topic='s', module='m1')
            cloze_path = base / 's' / 'modules' / 'm1' / 'cloze.yaml'
            assert cloze_path.exists()
            content = cloze_path.read_text()
            assert 'c.1' in content
            assert '{blank}' in content
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_create_cloze: OK')


# ── CLI: review ──────────────────────────────────────────────────


def test_cmd_review_shows_due():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_deck(
                base / 's',
                {
                    'cards': {
                        's-m1-m1.1': {
                            'id': 's-m1-m1.1',
                            'questionId': 'm1.1',
                            'moduleId': 'm1',
                            'courseId': 's',
                            'question': 'Q?',
                            'options': {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd'},
                            'answer': 'B',
                            'explanation': '',
                            'tags': [],
                            'easeFactor': 2.5,
                            'interval': 0,
                            'repetitions': 0,
                            'nextReviewDate': '2000-01-01',
                            'lastReviewed': None,
                            'isStarred': False,
                        }
                    }
                },
            )
            with patch('builtins.input', return_value='b'), patch('random.shuffle', lambda x: None):
                learn.cmd_review(topic='s')
            deck = learn._load_deck('s')
            cards = deck.get('cards', {})
            card = list(cards.values())[0]
            assert card['repetitions'] == 1
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_review_shows_due: OK')


def test_cmd_review_no_due():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            far = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
            _make_deck(
                base / 's',
                {
                    'cards': {
                        's-m1-m1.1': {
                            'id': 's-m1-m1.1',
                            'questionId': 'm1.1',
                            'moduleId': 'm1',
                            'courseId': 's',
                            'question': 'Q?',
                            'options': {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd'},
                            'answer': 'B',
                            'explanation': '',
                            'tags': [],
                            'easeFactor': 2.5,
                            'interval': 365,
                            'repetitions': 5,
                            'nextReviewDate': far,
                            'lastReviewed': '2024-01-01',
                            'isStarred': False,
                        }
                    }
                },
            )
            learn.cmd_review(topic='s')
            deck = learn._load_deck('s')
            cards = deck.get('cards', {})
            card = list(cards.values())[0]
            assert card['interval'] == 365  # unchanged
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_review_no_due: OK')


# ── CLI: stats ───────────────────────────────────────────────────


def test_cmd_counts():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            today = datetime.now().strftime('%Y-%m-%d')
            _make_deck(
                base / 's',
                {
                    'cards': {
                        's-m1-m1.1': {
                            'id': 's-m1-m1.1',
                            'questionId': 'm1.1',
                            'moduleId': 'm1',
                            'courseId': 's',
                            'question': 'Q1',
                            'options': {},
                            'answer': 'A',
                            'explanation': '',
                            'tags': [],
                            'easeFactor': 2.5,
                            'interval': 1,
                            'repetitions': 1,
                            'nextReviewDate': today,
                            'lastReviewed': today,
                            'isStarred': False,
                        },
                        's-m1-m1.2': {
                            'id': 's-m1-m1.2',
                            'questionId': 'm1.2',
                            'moduleId': 'm1',
                            'courseId': 's',
                            'question': 'Q2',
                            'options': {},
                            'answer': 'B',
                            'explanation': '',
                            'tags': [],
                            'easeFactor': 2.5,
                            'interval': 30,
                            'repetitions': 10,
                            'nextReviewDate': today,
                            'lastReviewed': today,
                            'isStarred': False,
                        },
                    }
                },
            )
            learn.cmd_stats(topic='s')
            deck = learn._load_deck('s')
            cards = deck.get('cards', {})
            assert len(cards) == 2
            due = [c for c in cards.values() if c.get('nextReviewDate', '2000-01-01') <= today]
            assert len(due) == 2
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_counts: OK')


# ── CLI: rate ────────────────────────────────────────────────────


def test_cmd_rate_saves_rating():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_module(base, 's', '01-intro')
            learn.cmd_rate(topic='s', module='01-intro', score=4, comment='good')
            feedback = learn._load_feedback('s')
            assert len(feedback['ratings']) == 1
            assert feedback['ratings'][0]['score'] == 4
            assert feedback['ratings'][0]['module'] == '01-intro'
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_rate_saves_rating: OK')


def test_cmd_rate_invalid_score_exits():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_module(base, 's', '01-intro')
            try:
                learn.cmd_rate(topic='s', module='01-intro', score=6, comment='')
                assert False, 'Should have exited'
            except SystemExit:
                pass
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_rate_invalid_score_exits: OK')


# ── CLI: flag ────────────────────────────────────────────────────


def test_cmd_flag_saves_flag():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_module(base, 's', '01-intro')
            learn.cmd_flag(topic='s', module='01-intro', flag_type='wrong', detail='typo')
            feedback = learn._load_feedback('s')
            assert len(feedback['flags']) == 1
            assert feedback['flags'][0]['type'] == 'wrong'
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_flag_saves_flag: OK')


def test_cmd_flag_invalid_type_exits():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_module(base, 's', '01-intro')
            try:
                learn.cmd_flag(topic='s', module='01-intro', flag_type='invalid', detail='')
                assert False, 'Should have exited'
            except SystemExit:
                pass
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_flag_invalid_type_exits: OK')


# ── CLI: feedback ────────────────────────────────────────────────


def test_cmd_feedback_aggregates():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_module(base, 's', '01-intro')
            learn.cmd_rate(topic='s', module='01-intro', score=4, comment='')
            learn.cmd_rate(topic='s', module='01-intro', score=2, comment='')
            learn.cmd_feedback(topic='s')
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_feedback_aggregates: OK')


def test_cmd_feedback_no_data():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            learn.cmd_feedback(topic='s')
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_feedback_no_data: OK')


# ── CLI: analytics ───────────────────────────────────────────────


def test_cmd_analytics_with_cards():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            today = datetime.now().strftime('%Y-%m-%d')
            deck = {
                'cards': {
                    's-m1-1.1': {
                        'id': 's-m1-1.1',
                        'questionId': '1.1',
                        'moduleId': 'm1',
                        'courseId': 's',
                        'question': 'Q1?',
                        'answer': 'a. A',
                        'explanation': '',
                        'easeFactor': 2.5,
                        'interval': 1,
                        'repetitions': 1,
                        'nextReviewDate': today,
                        'lastReviewed': today,
                        'isStarred': False,
                    },
                    's-m1-1.2': {
                        'id': 's-m1-1.2',
                        'questionId': '1.2',
                        'moduleId': 'm1',
                        'courseId': 's',
                        'question': 'Q2?',
                        'answer': 'b. B',
                        'explanation': '',
                        'easeFactor': 1.8,
                        'interval': 25,
                        'repetitions': 5,
                        'nextReviewDate': today,
                        'lastReviewed': today,
                        'isStarred': False,
                    },
                }
            }
            learn._save_deck('s', deck)
            learn.cmd_analytics(topic='s')
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_analytics_with_cards: OK')


def test_cmd_analytics_no_data():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            learn.cmd_analytics(topic='s')
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_analytics_no_data: OK')


# ── CLI: forecast ────────────────────────────────────────────────


def test_cmd_forecast_with_cards():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            today = datetime.now().strftime('%Y-%m-%d')
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            next_month = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            deck = {
                'cards': {
                    's-m1-1.1': {
                        'id': 's-m1-1.1',
                        'questionId': '1.1',
                        'moduleId': 'm1',
                        'courseId': 's',
                        'question': 'Due today?',
                        'answer': 'a. A',
                        'explanation': '',
                        'easeFactor': 2.5,
                        'interval': 0,
                        'repetitions': 0,
                        'nextReviewDate': today,
                        'lastReviewed': None,
                        'isStarred': False,
                    },
                    's-m1-1.2': {
                        'id': 's-m1-1.2',
                        'questionId': '1.2',
                        'moduleId': 'm1',
                        'courseId': 's',
                        'question': 'Due tomorrow?',
                        'answer': 'b. B',
                        'explanation': '',
                        'easeFactor': 2.5,
                        'interval': 1,
                        'repetitions': 1,
                        'nextReviewDate': tomorrow,
                        'lastReviewed': today,
                        'isStarred': False,
                    },
                    's-m1-1.3': {
                        'id': 's-m1-1.3',
                        'questionId': '1.3',
                        'moduleId': 'm1',
                        'courseId': 's',
                        'question': 'Due next month?',
                        'answer': 'c. C',
                        'explanation': '',
                        'easeFactor': 2.5,
                        'interval': 30,
                        'repetitions': 3,
                        'nextReviewDate': next_month,
                        'lastReviewed': today,
                        'isStarred': False,
                    },
                }
            }
            learn._save_deck('s', deck)
            learn.cmd_forecast(topic='s')
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_forecast_with_cards: OK')


def test_cmd_forecast_no_deck():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            learn.cmd_forecast(topic='s')
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_forecast_no_deck: OK')


# ── CLI: study-plan ──────────────────────────────────────────────


def test_cmd_study_plan_with_cards():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            today = datetime.now().strftime('%Y-%m-%d')
            deck = {
                'cards': {
                    's-m1-1.1': {
                        'id': 's-m1-1.1',
                        'questionId': '1.1',
                        'moduleId': 'm1',
                        'courseId': 's',
                        'question': 'Q1?',
                        'answer': 'a. A',
                        'explanation': '',
                        'easeFactor': 1.8,
                        'interval': 0,
                        'repetitions': 0,
                        'nextReviewDate': today,
                        'lastReviewed': None,
                        'isStarred': False,
                    },
                }
            }
            learn._save_deck('s', deck)
            learn.cmd_study_plan(topic='s')
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_study_plan_with_cards: OK')


def test_cmd_study_plan_no_deck():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            learn.cmd_study_plan(topic='s')
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_study_plan_no_deck: OK')


# ── CLI: export ──────────────────────────────────────────────────


def test_cmd_export_creates_csv():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            deck = {
                'cards': {
                    's-m1-1.1': {
                        'id': 's-m1-1.1',
                        'questionId': '1.1',
                        'moduleId': 'm1',
                        'courseId': 's',
                        'question': 'Q1?',
                        'answer': 'a. Option A',
                        'explanation': 'Exp1',
                        'easeFactor': 2.5,
                        'interval': 1,
                        'repetitions': 1,
                        'nextReviewDate': '2024-01-02',
                        'lastReviewed': '2024-01-01',
                        'isStarred': False,
                    },
                }
            }
            learn._save_deck('s', deck)
            learn.cmd_export(topic='s')
            csv_path = base / 's' / 'srs' / 'deck.csv'
            assert csv_path.exists()
            content = csv_path.read_text()
            assert 'Q1?' in content
            assert 'Option A' in content
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_export_creates_csv: OK')


def test_cmd_export_no_deck():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            learn.cmd_export(topic='s')
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_export_no_deck: OK')


# ── CLI: sync ────────────────────────────────────────────────────


def test_cmd_sync_exports_to_reader():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_module(base, 's', '01-intro')
            deck = {
                'cards': {
                    's-01-intro-1.1': {
                        'id': 's-01-intro-1.1',
                        'questionId': '1.1',
                        'moduleId': '01-intro',
                        'courseId': 's',
                        'question': 'Q?',
                        'answer': 'a. A',
                        'explanation': '',
                        'easeFactor': 2.5,
                        'interval': 1,
                        'repetitions': 1,
                        'nextReviewDate': '2024-01-02',
                        'lastReviewed': '2024-01-01',
                        'isStarred': False,
                    },
                }
            }
            learn._save_deck('s', deck)
            reader_path = str(base / 'reader')
            learn.cmd_sync(topic='s', reader_path=reader_path)
            reader_deck = Path(reader_path) / 's' / 'srs' / 'deck.json'
            assert reader_deck.exists()
            reader_modules = Path(reader_path) / 's' / 'modules' / '01-intro'
            assert reader_modules.exists()
            assert (reader_modules / 'lesson.md').exists()
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_sync_exports_to_reader: OK')


def test_cmd_sync_no_cards():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            reader_path = str(base / 'reader')
            learn.cmd_sync(topic='s', reader_path=reader_path)
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_sync_no_cards: OK')


# ── CLI: sync-pull ───────────────────────────────────────────────


def test_cmd_sync_pull_imports_from_reader():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            reader_path = base / 'reader'
            reader_topic = reader_path / 's' / 'srs'
            reader_topic.mkdir(parents=True)
            deck = {
                'cards': {
                    's-m1-1.1': {
                        'id': 's-m1-1.1',
                        'questionId': '1.1',
                        'moduleId': 'm1',
                        'courseId': 's',
                        'question': 'Q?',
                        'answer': 'a. A',
                        'explanation': '',
                        'easeFactor': 2.5,
                        'interval': 1,
                        'repetitions': 1,
                        'nextReviewDate': '2024-01-02',
                        'lastReviewed': '2024-01-01',
                        'isStarred': False,
                    },
                }
            }
            (reader_topic / 'deck.json').write_text(json.dumps(deck, indent=2))
            learn.cmd_sync_pull(topic='s', reader_path=str(reader_path))
            cli_deck = learn._load_deck('s')
            assert len(cli_deck.get('cards', {})) == 1
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_sync_pull_imports_from_reader: OK')


def test_cmd_sync_pull_missing_reader_exits():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            try:
                learn.cmd_sync_pull(topic='s', reader_path=str(base / 'nonexist'))
                assert False, 'Should have exited'
            except SystemExit:
                pass
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_sync_pull_missing_reader_exits: OK')


# ── Schema validation ────────────────────────────────────────────


def test_cmd_validate_passes():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, 's')
            _make_quality_module(base, 's', '01-intro')
            # Create a valid deck
            learn._save_deck(
                's',
                {
                    'cards': {
                        's-01-intro-1.1': {
                            'id': 's-01-intro-1.1',
                            'questionId': '1.1',
                            'moduleId': '01-intro',
                            'courseId': 's',
                            'question': 'Q?',
                            'answer': 'a. A',
                            'explanation': '',
                            'easeFactor': 2.5,
                            'interval': 1,
                            'repetitions': 1,
                            'stability': 2.3,
                            'difficulty': 5.0,
                            'lapses': 0,
                            'state': 'Review',
                            'nextReviewDate': '2026-07-10',
                            'lastReviewed': '2026-07-09',
                            'isStarred': False,
                        },
                    }
                },
            )
            try:
                learn.cmd_validate(topic='s')
                assert False, 'Should have exited 0'
            except SystemExit as e:
                assert e.code == 0
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_validate_passes: OK')


def test_cmd_validate_missing_topic():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            try:
                learn.cmd_validate(topic='nonexist')
                assert False, 'Should have exited'
            except SystemExit:
                pass
        finally:
            learn.SUBJECTS_DIR = orig
    print('  cmd_validate_missing_topic: OK')


# ── CLI integration tests ──────────────────────────────────────

try:
    from learn import app
    from typer.testing import CliRunner

    _runner = CliRunner()
    _has_typer_test = True
except ImportError:
    _has_typer_test = False


def test_cli_help_shows_all_commands():
    if not _has_typer_test:
        print('  cli_help_shows_all_commands: SKIP (no typer.testing)')
        return
    result = _runner.invoke(app, ['--help'])
    assert result.exit_code == 0
    for cmd in [
        'init',
        'start',
        'quiz',
        'review',
        'stats',
        'export',
        'rate',
        'flag',
        'feedback',
        'analytics',
        'forecast',
        'study-plan',
        'epub',
        'pdf',
        'sync',
        'validate',
        'feynman',
    ]:
        assert cmd in result.output, f'{cmd} not in help output'


def test_cli_init_help():
    if not _has_typer_test:
        print('  cli_init_help: SKIP (no typer.testing)')
        return
    result = _runner.invoke(app, ['init', '--help'])
    assert result.exit_code == 0
    assert 'topic' in result.output.lower()


def test_cli_quiz_help():
    if not _has_typer_test:
        print('  cli_quiz_help: SKIP (no typer.testing)')
        return
    result = _runner.invoke(app, ['quiz', '--help'])
    assert result.exit_code == 0
    assert '--adaptive' in result.output


def test_cli_feynman_alias():
    if not _has_typer_test:
        print('  cli_feynman_alias: SKIP (no typer.testing)')
        return
    result = _runner.invoke(app, ['feynman', '--help'])
    assert result.exit_code == 0


def test_cli_validate_help():
    if not _has_typer_test:
        print('  cli_validate_help: SKIP (no typer.testing)')
        return
    result = _runner.invoke(app, ['validate', '--help'])
    assert result.exit_code == 0
