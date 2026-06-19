#!/usr/bin/env python3
"""Tests for scripts/learn.py — SM-2, helpers, CLI commands."""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import learn

# ── Test helpers ─────────────────────────────────────────────────

def _card(ef=2.5, reps=0, interval=0):
    return {'ease_factor': ef, 'repetitions': reps, 'interval': interval}


def _make_subject(base, name, lang="en"):
    path = Path(str(base)) / name
    (path / "modules").mkdir(parents=True)
    (path / "srs").mkdir(parents=True)
    src = learn.SKILL_DIR / "templates" / "syllabus.yaml"
    if src.exists():
        content = src.read_text()
        content = content.replace('"[Subject]"', f'"{name}"')
        content = content.replace('language: en', f'language: {lang}')
        (path / "syllabus.yaml").write_text(content)
    return path


def _make_module(base, subject, module, answers="B", num=1):
    mod_path = Path(str(base)) / subject / "modules" / module
    mod_path.mkdir(parents=True, exist_ok=True)
    (mod_path / "lesson.md").write_text(f"# {module}\n\nContent.\n")
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
    (mod_path / "quiz.yaml").write_text("\n".join(lines))
    return mod_path


def _make_deck(subject_dir, cards):
    p = Path(str(subject_dir)) / "srs" / "deck.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cards, indent=2))
    return p


# ── SM-2 Algorithm ───────────────────────────────────────────────

def test_sm2_first_correct_q4():
    c = _card()
    learn.sm2_update(c, 4)
    assert c['interval'] == 1
    assert c['repetitions'] == 1
    assert c['ease_factor'] == 2.5
    print("  sm2_first_correct_q4: OK")


def test_sm2_second_correct():
    c = _card(reps=1, interval=1)
    learn.sm2_update(c, 4)
    assert c['interval'] == 6
    assert c['repetitions'] == 2
    print("  sm2_second_correct: OK")


def test_sm2_third_correct_mul_ef():
    c = _card(reps=2, interval=6)
    learn.sm2_update(c, 4)
    assert c['interval'] == round(6 * 2.5)
    assert c['repetitions'] == 3
    print("  sm2_third_correct_mul_ef: OK")


def test_sm2_wrong_reset():
    c = _card(reps=5, interval=30)
    learn.sm2_update(c, 1)
    assert c['interval'] == 1
    assert c['repetitions'] == 0
    expected_ef = 2.5 + (0.1 - 4 * (0.08 + 4 * 0.02))
    assert c['ease_factor'] == round(expected_ef, 2)
    print("  sm2_wrong_reset: OK")


def test_sm2_quality_0_ef_drop():
    c = _card()
    learn.sm2_update(c, 0)
    assert c['interval'] == 1
    assert c['repetitions'] == 0
    expected_ef = 2.5 + (0.1 - 5 * (0.08 + 5 * 0.02))
    assert c['ease_factor'] == round(expected_ef, 2)
    print("  sm2_quality_0_ef_drop: OK")


def test_sm2_quality_5_increases_ef():
    c = _card(ef=2.5)
    learn.sm2_update(c, 5)
    assert c['ease_factor'] == round(2.5 + 0.1, 2)
    print("  sm2_quality_5_increases_ef: OK")


def test_sm2_quality_3_decreases_ef():
    c = _card(ef=2.5)
    learn.sm2_update(c, 3)
    expected = 2.5 + (0.1 - 2 * (0.08 + 2 * 0.02))
    assert c['ease_factor'] == round(expected, 2)
    print("  sm2_quality_3_decreases_ef: OK")


def test_sm2_ef_floor():
    c = _card(ef=1.5)
    learn.sm2_update(c, 0)
    assert c['ease_factor'] >= 1.3
    assert c['ease_factor'] == 1.3
    print("  sm2_ef_floor: OK")


def test_sm2_consecutive_wrong_decreases_ef():
    c = _card(reps=2, interval=10)
    ef_before = c['ease_factor']
    learn.sm2_update(c, 1)
    assert c['interval'] == 1
    assert c['repetitions'] == 0
    ef_after_1 = c['ease_factor']
    assert ef_after_1 < ef_before
    learn.sm2_update(c, 1)
    assert c['repetitions'] == 0
    assert c['ease_factor'] < ef_after_1
    print("  sm2_consecutive_wrong_decreases_ef: OK")


def test_sm2_no_next_review_on_fresh():
    c = _card()
    learn.sm2_update(c, 4)
    assert 'next_review' in c
    assert 'last_review' in c
    datetime.strptime(c['next_review'], '%Y-%m-%d')
    datetime.strptime(c['last_review'], '%Y-%m-%d')
    print("  sm2_no_next_review_on_fresh: OK")


def test_sm2_ef_stable_at_2p5():
    c = _card()
    for _ in range(10):
        learn.sm2_update(c, 4)
    assert c['ease_factor'] == 2.5
    print("  sm2_ef_stable_at_2p5: OK")


def test_sm2_interval_grows_with_ef():
    c = _card(reps=2, interval=6, ef=2.0)
    learn.sm2_update(c, 4)
    assert c['interval'] == round(6 * 2.0)
    c2 = _card(reps=2, interval=6, ef=3.0)
    learn.sm2_update(c2, 4)
    assert c2['interval'] > c['interval']
    print("  sm2_interval_grows_with_ef: OK")


# ── Subject helpers ──────────────────────────────────────────────

def test_subject_path():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            p = learn._subject_path("x")
            assert str(p) == str(base / "x")
        finally:
            learn.SUBJECTS_DIR = orig
    print("  subject_path: OK")


def test_module_path():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            p = learn._module_path("s", "m")
            assert str(p) == str(base / "s" / "modules" / "m")
        finally:
            learn.SUBJECTS_DIR = orig
    print("  module_path: OK")


def test_list_modules():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            (base / "s" / "modules" / "01-a" / "lesson.md").parent.mkdir(parents=True)
            (base / "s" / "modules" / "01-a" / "lesson.md").write_text("# a")
            (base / "s" / "modules" / "02-b" / "lesson.md").parent.mkdir(parents=True)
            (base / "s" / "modules" / "02-b" / "lesson.md").write_text("# b")
            (base / "s" / "modules" / "03-no-lesson").mkdir(parents=True)
            mods = learn._list_modules("s")
            assert mods == ["01-a", "02-b"]
        finally:
            learn.SUBJECTS_DIR = orig
    print("  list_modules: OK")


def test_load_save_deck():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            cards = [{"id": "1", "question": "q?"}]
            learn._save_deck("s", cards)
            loaded = learn._load_deck("s")
            assert loaded == cards
        finally:
            learn.SUBJECTS_DIR = orig
    print("  load_save_deck: OK")


def test_load_save_stats():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            stats = {"sessions": [{"date": "2024-01-01", "type": "quiz"}]}
            learn._save_stats("s", stats)
            loaded = learn._load_stats("s")
            assert loaded == stats
        finally:
            learn.SUBJECTS_DIR = orig
    print("  load_save_stats: OK")


def test_record_session():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            learn._record_session("s", "quiz", module="m1", score=3, total=5)
            stats = learn._load_stats("s")
            assert len(stats["sessions"]) == 1
            entry = stats["sessions"][0]
            assert entry["type"] == "quiz"
            assert entry["module"] == "m1"
            assert entry["score"] == 3
            assert entry["total"] == 5
        finally:
            learn.SUBJECTS_DIR = orig
    print("  record_session: OK")


# ── CLI: init ────────────────────────────────────────────────────

def test_cmd_init_creates_dirs():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            args = argparse.Namespace(subject="mytopic", lang="en")
            learn.cmd_init(args)
            sp = base / "mytopic"
            assert sp.exists()
            assert (sp / "modules").exists()
            assert (sp / "srs").exists()
            assert (sp / "syllabus.yaml").exists()
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_init_creates_dirs: OK")


def test_cmd_init_lang():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            learn.cmd_init(argparse.Namespace(subject="zhsub", lang="zh"))
            syllabus = (base / "zhsub" / "syllabus.yaml").read_text()
            assert "language: zh" in syllabus
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_init_lang: OK")


def test_cmd_init_already_exists():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "dup")
            try:
                learn.cmd_init(argparse.Namespace(subject="dup", lang="en"))
                assert False, "Should have exited"
            except SystemExit:
                pass
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_init_already_exists: OK")


# ── CLI: start ────────────────────────────────────────────────────

def test_cmd_start_shows_overview():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            _make_module(base, "s", "01-intro")
            learn.cmd_start(argparse.Namespace(subject="s"))
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_start_shows_overview: OK")


def test_cmd_start_missing_subject_exits():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            try:
                learn.cmd_start(argparse.Namespace(subject="nonexist"))
                assert False, "Should have exited"
            except SystemExit:
                pass
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_start_missing_subject_exits: OK")


# ── CLI: explain ──────────────────────────────────────────────────

def test_cmd_explain_shows_prompt():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            _make_module(base, "s", "01-intro")
            learn.cmd_explain(argparse.Namespace(subject="s", module="01-intro"))
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_explain_shows_prompt: OK")


def test_cmd_explain_missing_module_exits():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            try:
                learn.cmd_explain(argparse.Namespace(subject="s", module="nonexist"))
                assert False, "Should have exited"
            except SystemExit:
                pass
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_explain_missing_module_exits: OK")


# ── CLI: create-module ───────────────────────────────────────────

def test_cmd_create_module():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            args = argparse.Namespace(subject="s", module_id="01-intro", name=None)
            learn.cmd_create_module(args)
            mp = base / "s" / "modules" / "01-intro"
            assert mp.exists()
            assert (mp / "lesson.md").exists()
            assert (mp / "quiz.yaml").exists()
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_create_module: OK")


def test_cmd_create_module_with_name():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            learn.cmd_create_module(
                argparse.Namespace(subject="s", module_id="01-intro", name="Intro")
            )
            lesson = (base / "s" / "modules" / "01-intro" / "lesson.md").read_text()
            assert "Intro" in lesson
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_create_module_with_name: OK")


def test_cmd_create_module_already_exists():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            _make_module(base, "s", "01-intro")
            try:
                learn.cmd_create_module(
                    argparse.Namespace(subject="s", module_id="01-intro", name=None)
                )
                assert False, "Should have exited"
            except SystemExit:
                pass
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_create_module_already_exists: OK")


# ── CLI: quiz ────────────────────────────────────────────────────

def test_cmd_quiz_creates_cards():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            _make_module(base, "s", "m1", answers="B", num=2)
            inputs = ["b", "b"]  # both correct → B
            with patch('builtins.input', side_effect=inputs), \
                 patch('random.shuffle', lambda x: None):
                learn.cmd_quiz(argparse.Namespace(subject="s", module="m1"))
            deck = learn._load_deck("s")
            assert len(deck) == 2
            for card in deck:
                assert card['repetitions'] == 1
                assert card['interval'] == 1
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_quiz_creates_cards: OK")


def test_cmd_quiz_wrong_answer_resets():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            _make_module(base, "s", "m1", answers="B", num=1)
            existing = [{
                'id': 'm1.1', 'question': 'Q1?',
                'options': {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd'},
                'answer': 'B', 'explanation': '',
                'tags': [], 'ease_factor': 2.5,
                'interval': 30, 'repetitions': 5,
                'next_review': '2024-01-01', 'last_review': '2024-01-01',
            }]
            _make_deck(base / "s", existing)
            with patch('builtins.input', return_value='a'), \
                 patch('random.shuffle', lambda x: None):
                learn.cmd_quiz(argparse.Namespace(subject="s", module="m1"))
            deck = learn._load_deck("s")
            assert len(deck) == 1
            assert deck[0]['repetitions'] == 0
            assert deck[0]['interval'] == 1
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_quiz_wrong_answer_resets: OK")


# ── CLI: review ──────────────────────────────────────────────────

def test_cmd_review_shows_due():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            _make_deck(base / "s", [{
                'id': 'm1.1', 'question': 'Q?',
                'options': {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd'},
                'answer': 'B', 'explanation': '',
                'tags': [],
                'ease_factor': 2.5, 'interval': 0, 'repetitions': 0,
                'next_review': '2000-01-01', 'last_review': None,
            }])
            with patch('builtins.input', return_value='b'), \
                 patch('random.shuffle', lambda x: None):
                learn.cmd_review(argparse.Namespace(subject="s"))
            deck = learn._load_deck("s")
            assert deck[0]['repetitions'] == 1
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_review_shows_due: OK")


def test_cmd_review_no_due():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            far = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
            _make_deck(base / "s", [{
                'id': 'm1.1', 'question': 'Q?',
                'options': {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd'},
                'answer': 'B', 'explanation': '',
                'tags': [],
                'ease_factor': 2.5, 'interval': 365, 'repetitions': 5,
                'next_review': far, 'last_review': '2024-01-01',
            }])
            learn.cmd_review(argparse.Namespace(subject="s"))
            deck = learn._load_deck("s")
            assert deck[0]['interval'] == 365  # unchanged
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_review_no_due: OK")


# ── CLI: stats ───────────────────────────────────────────────────

def test_cmd_counts():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        orig = learn.SUBJECTS_DIR
        learn.SUBJECTS_DIR = base
        try:
            _make_subject(base, "s")
            today = datetime.now().strftime('%Y-%m-%d')
            _make_deck(base / "s", [
                {'id': 'm1.1', 'question': 'Q1', 'options': {},
                 'answer': 'A', 'explanation': '', 'tags': [],
                 'ease_factor': 2.5, 'interval': 1, 'repetitions': 1,
                 'next_review': today, 'last_review': today},
                {'id': 'm1.2', 'question': 'Q2', 'options': {},
                 'answer': 'B', 'explanation': '', 'tags': [],
                 'ease_factor': 2.5, 'interval': 30, 'repetitions': 10,
                 'next_review': today, 'last_review': today},
            ])
            learn.cmd_stats(argparse.Namespace(subject="s"))
            deck = learn._load_deck("s")
            assert len(deck) == 2
            due = [c for c in deck
                   if c.get('next_review', '2000-01-01') <= today]
            assert len(due) == 2
        finally:
            learn.SUBJECTS_DIR = orig
    print("  cmd_counts: OK")


# ── SM-2 integration: full cycle ─────────────────────────────────

def test_sm2_full_cycle():
    c = _card()
    learn.sm2_update(c, 4)
    assert c['interval'] == 1 and c['repetitions'] == 1
    ef_a = c['ease_factor']
    learn.sm2_update(c, 3)
    assert c['interval'] == 6 and c['repetitions'] == 2
    ef_b = c['ease_factor']
    assert ef_b < ef_a
    learn.sm2_update(c, 4)
    assert c['interval'] == round(6 * ef_b)
    assert c['repetitions'] == 3
    learn.sm2_update(c, 1)
    assert c['interval'] == 1 and c['repetitions'] == 0
    learn.sm2_update(c, 4)
    assert c['interval'] == 1 and c['repetitions'] == 1
    print("  sm2_full_cycle: OK")


# ── Runner ───────────────────────────────────────────────────────

if __name__ == '__main__':
    tests = [
        test_sm2_first_correct_q4,
        test_sm2_second_correct,
        test_sm2_third_correct_mul_ef,
        test_sm2_wrong_reset,
        test_sm2_quality_0_ef_drop,
        test_sm2_quality_5_increases_ef,
        test_sm2_quality_3_decreases_ef,
        test_sm2_ef_floor,
        test_sm2_consecutive_wrong_decreases_ef,
        test_sm2_no_next_review_on_fresh,
        test_sm2_ef_stable_at_2p5,
        test_sm2_interval_grows_with_ef,
        test_sm2_full_cycle,
        test_subject_path,
        test_module_path,
        test_list_modules,
        test_load_save_deck,
        test_load_save_stats,
        test_record_session,
        test_cmd_start_shows_overview,
        test_cmd_start_missing_subject_exits,
        test_cmd_explain_shows_prompt,
        test_cmd_explain_missing_module_exits,
        test_cmd_init_creates_dirs,
        test_cmd_init_lang,
        test_cmd_init_already_exists,
        test_cmd_create_module,
        test_cmd_create_module_with_name,
        test_cmd_create_module_already_exists,
        test_cmd_quiz_creates_cards,
        test_cmd_quiz_wrong_answer_resets,
        test_cmd_review_shows_due,
        test_cmd_review_no_due,
        test_cmd_counts,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f'  FAIL {test.__name__}: {e}')
            failed += 1
    total = len(tests)
    passed = total - failed
    print(f'\n{passed}/{total} passed')
    sys.exit(1 if failed else 0)
