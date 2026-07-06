"""Tests for FSRS-5 implementation in sm2.py."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from sm2 import (
    _init_difficulty,
    _init_stability,
    _next_difficulty,
    _next_interval,
    _retrievability,
    predict_retention,
    update,
)


def _fresh_card():
    now = datetime.now().strftime('%Y-%m-%d')
    return {
        'repetitions': 0,
        'interval': 0,
        'easeFactor': 2.5,
        'nextReviewDate': now,
        'lastReviewed': None,
    }


def _elapsed_days(days):
    return (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')


# ── New card ──


def test_new_card_correct():
    card = _fresh_card()
    update(card, 4)
    assert card['stability'] > 0
    assert card['difficulty'] >= 1
    assert card['state'] == 'Review'
    assert card['lapses'] == 0
    assert card['interval'] > 0


def test_new_card_wrong():
    card = _fresh_card()
    update(card, 1)
    assert card['stability'] < _init_stability(3)
    assert card['difficulty'] > _init_difficulty(3)
    assert card['state'] == 'Review'


# ── Review: stability growth ──


def test_review_correct_stability_grows():
    card = _fresh_card()
    update(card, 4)
    s1 = card['stability']
    # Next-day review for long-term formula path
    card['lastReviewed'] = _elapsed_days(1)
    update(card, 4)
    assert card['stability'] > s1


def test_review_wrong_stability_drops():
    card = _fresh_card()
    update(card, 4)
    s1 = card['stability']
    update(card, 1)
    assert card['stability'] < s1
    assert card['lapses'] >= 1


def test_multiple_correct_stability_increases():
    card = _fresh_card()
    stabilities = []
    for i in range(5):
        if i > 0:
            card['lastReviewed'] = _elapsed_days(1)
        update(card, 4)
        stabilities.append(card['stability'])
    for i in range(1, len(stabilities)):
        assert stabilities[i] >= stabilities[i - 1] * 0.9


# ── Forgetting / Relearning ──


def test_forgetting_triggers_relearning():
    card = _fresh_card()
    update(card, 4)
    update(card, 1)
    assert card['state'] == 'Relearning'
    assert card['lapses'] >= 1


def test_review_wrong_after_long_term():
    card = _fresh_card()
    update(card, 4)
    s_before = card['stability']
    card['lastReviewed'] = _elapsed_days(7)
    update(card, 1)
    assert card['stability'] < s_before
    assert card['state'] == 'Relearning'


# ── Interval ──


def test_interval_monotonic_on_correct():
    card = _fresh_card()
    update(card, 4)
    i1 = card['interval']
    card['lastReviewed'] = _elapsed_days(1)
    update(card, 4)
    assert card['interval'] >= i1


# ── Ease factor ──


def test_ease_factor_in_bounds():
    card = _fresh_card()
    update(card, 4)
    assert card['easeFactor'] >= 1.3
    assert card['easeFactor'] <= 5.0


# ── Migration ──


def test_migrate_sm2_card():
    old = {
        'interval': 5,
        'repetitions': 3,
        'easeFactor': 2.5,
        'nextReviewDate': '2026-07-10',
        'lastReviewed': '2026-07-05',
    }
    update(old, 4)
    assert 'stability' in old
    assert 'difficulty' in old
    assert 'lapses' in old
    assert old['state'] == 'Review'


def test_migrate_fresh_card():
    old = {
        'interval': 0,
        'repetitions': 0,
        'easeFactor': 2.5,
        'nextReviewDate': '2026-07-10',
        'lastReviewed': None,
    }
    update(old, 4)
    assert old['state'] == 'Review'
    assert old['lapses'] == 0


# ── Edge cases ──


def test_short_term_same_day():
    card = _fresh_card()
    update(card, 4)
    card['lastReviewed'] = datetime.now().strftime('%Y-%m-%d')
    update(card, 4)
    assert card['state'] == 'Review'
    assert card['interval'] > 0
    assert 'lastReviewed' in card


def test_quality_below_3_maps_to_again():
    card = _fresh_card()
    update(card, 0)
    assert card['stability'] < _init_stability(3)
    card = _fresh_card()
    update(card, 2)
    assert card['stability'] < _init_stability(3)


# ── predict_retention ──


def test_predict_retention_high_for_recent():
    r = predict_retention(100, 1)
    assert r > 0.9


def test_predict_retention_low_for_distant():
    r = predict_retention(1, 100)
    assert r < 0.5


# ── Internal functions ──


def test_retrievability_range():
    r = _retrievability(0, 10)
    assert abs(r - 1.0) < 0.01
    r = _retrievability(365, 1)
    assert 0 <= r <= 1


def test_init_stability_order():
    s3 = _init_stability(3)
    s1 = _init_stability(1)
    assert s3 > s1


def test_init_difficulty_in_range():
    d = _init_difficulty(3)
    assert 1 <= d <= 10


def test_next_difficulty_in_range():
    d = _next_difficulty(5, 3)
    assert 1 <= d <= 10


def test_next_interval_positive():
    assert _next_interval(10) >= 1
    assert _next_interval(100000) <= 36500
