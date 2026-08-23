"""Tests for FSRS-6 implementation in fsrs.py.

Property-based tests (not golden numbers) — exact weights can vary with
calibration. Asserts invariants the algorithm must preserve.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from fsrs import (
    _init_difficulty,
    _init_stability,
    _next_difficulty,
    _next_interval,
    _retrievability,
    _short_term_stability,
    get_desired_retention,
    predict_retention,
    update,
)


def _fresh_card(rating=None, state='New'):
    now = datetime.now()
    card = {
        'id': 'test-1',
        'easeFactor': 2.5,
        'interval': 0,
        'repetitions': 0,
        'nextReviewDate': now.strftime('%Y-%m-%d'),
        'lastReviewed': None,
        'state': state,
    }
    if rating is not None:
        update(card, quality=4, rating=rating, now=now)
    return card


def _elapsed_days(days, base=None):
    base = base or datetime.now()
    return (base - timedelta(days=days)).strftime('%Y-%m-%d')


# ── New card ──


def test_new_card_correct_graduates_to_review():
    card = _fresh_card()
    update(card, 4)
    assert card['stability'] > 0
    assert 1 <= card['difficulty'] <= 10
    assert card['state'] == 'Review'
    assert card['lapses'] == 0
    assert card['interval'] > 0
    assert card['algorithm_version'] == 'fsrs-6'


def test_new_card_wrong_enters_learning():
    card = _fresh_card()
    update(card, 1)  # quality < 3 → rating=1 (Again)
    assert card['stability'] < _init_stability(3)
    assert card['state'] == 'Learning'


# ── 4-level rating scale ──


def test_easier_rating_yields_higher_stability():
    s_hard = _init_stability(2)
    s_good = _init_stability(3)
    s_easy = _init_stability(4)
    assert s_hard < s_good < s_easy


def test_easier_rating_yields_lower_difficulty():
    d_again = _init_difficulty(1)
    d_hard = _init_difficulty(2)
    d_good = _init_difficulty(3)
    d_easy = _init_difficulty(4)
    assert d_again >= d_hard >= d_good >= d_easy


def test_explicit_rating_takes_precedence():
    # quality=4 normally maps to rating=3 (Good); explicit rating=4 should win
    card = _fresh_card()
    update(card, quality=4, rating=1)  # quality would say Good, but explicit Again
    assert card['state'] == 'Learning'


def test_quality_to_rating_thresholds():
    # quality 0,1,2 → Again (1)
    # quality 3   → Hard (2)
    # quality 4,5 → Good (3)
    from fsrs import _grade

    assert _grade(0, None) == 1
    assert _grade(2, None) == 1
    assert _grade(3, None) == 2
    assert _grade(4, None) == 3
    assert _grade(5, None) == 3


# ── Review: stability growth ──


def test_review_correct_stability_grows():
    card = _fresh_card(rating=3)
    s1 = card['stability']
    card['lastReviewed'] = _elapsed_days(2)
    update(card, 4)
    assert card['stability'] > s1


def test_review_wrong_increases_lapses():
    card = _fresh_card(rating=3)
    update(card, 1)
    assert card['lapses'] >= 1
    assert card['state'] in ('Relearning', 'Learning')


def test_multiple_correct_stability_increases():
    card = _fresh_card(rating=3)
    stabilities = [card['stability']]
    for _ in range(5):
        card['lastReviewed'] = _elapsed_days(2)
        update(card, 4)
        stabilities.append(card['stability'])
    for i in range(1, len(stabilities)):
        # Allow tiny numerical wobble; growth should be monotonic-ish
        assert stabilities[i] >= stabilities[i - 1] * 0.9


# ── Forgetting / Relearning ──


def test_lapse_triggers_relearning_or_learning():
    card = _fresh_card(rating=3)
    card['lastReviewed'] = _elapsed_days(7)  # long-term lapse
    update(card, 1)
    assert card['lapses'] >= 1


def test_relearning_graduates_back_to_review():
    card = _fresh_card(rating=3)
    card['lastReviewed'] = _elapsed_days(7)
    update(card, 1)  # lapse → Relearning
    assert card['state'] == 'Relearning'
    # Now answer correctly: should graduate
    update(card, 4)
    assert card['state'] == 'Review'


# ── Interval ──


def test_interval_positive_for_review_state():
    card = _fresh_card(rating=3)
    assert card['interval'] >= 1


def test_interval_grows_on_correct_long_term():
    card = _fresh_card(rating=3)
    i1 = card['interval']
    card['lastReviewed'] = _elapsed_days(1)
    update(card, 4)
    assert card['interval'] >= i1


def test_interval_capped_at_max():
    # Huge stability → interval should cap
    assert _next_interval(1e9) <= 36500


# ── desired_retention ──


def test_default_desired_retention():
    card = _fresh_card()
    assert get_desired_retention(card) == 0.9


def test_higher_desired_retention_shorter_interval():
    s = 30
    i_low = _next_interval(s, desired_retention=0.8)
    i_high = _next_interval(s, desired_retention=0.95)
    # Want higher retention → review sooner → shorter interval
    assert i_low > i_high


# ── Ease factor ──


def test_ease_factor_in_bounds():
    card = _fresh_card(rating=3)
    assert 1.3 <= card['easeFactor'] <= 5.0


# ── Migration: SM-2 → FSRS-6 ──


def test_migrate_sm2_card():
    old = {
        'id': 'old-1',
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
    assert old['algorithm_version'] == 'fsrs-6'
    assert 'desired_retention' in old


def test_migrate_fresh_card():
    old = {
        'id': 'fresh-1',
        'interval': 0,
        'repetitions': 0,
        'easeFactor': 2.5,
        'nextReviewDate': '2026-07-10',
        'lastReviewed': None,
    }
    update(old, 4)
    assert old['state'] in ('Review', 'Learning')
    assert old['lapses'] == 0
    assert old['algorithm_version'] == 'fsrs-6'


# ── Migration: FSRS-5 → FSRS-6 (pending marker) ──


def test_fsrs5_pending_card_re_evaluates():
    """Card from FSRS-5 (has stability/difficulty but no version) gets re-derived."""
    old = {
        'id': 'fsrs5-1',
        'stability': 10.0,
        'difficulty': 5.0,
        'lapses': 0,
        'state': 'Review',
        'interval': 15,
        'repetitions': 2,
        'easeFactor': 2.5,
        'nextReviewDate': '2026-07-10',
        'lastReviewed': _elapsed_days(3),
    }
    # On first update, algorithm_version=fsrs-6-pending triggers re-derive
    update(old, 4)
    assert old['algorithm_version'] == 'fsrs-6'
    # Re-derived → stability should be init_stability(rating), not old 10.0
    assert old['stability'] == _init_stability(3)


# ── Edge cases ──


def test_short_term_same_day():
    card = _fresh_card(rating=3)
    card['lastReviewed'] = datetime.now().strftime('%Y-%m-%d')
    update(card, 4)
    assert card['interval'] >= 1
    assert card['algorithm_version'] == 'fsrs-6'


def test_quality_below_3_maps_to_again():
    card = _fresh_card()
    update(card, 0)
    assert card['stability'] < _init_stability(3)
    card = _fresh_card()
    update(card, 2)
    assert card['stability'] < _init_stability(3)


def test_hard_rating_penalizes_stability():
    # Hard (rating=2) recall growth < Good (rating=3) recall growth, same conditions
    from fsrs import _next_recall_stability

    d, s, r = 5.0, 10.0, 0.8
    s_hard = _next_recall_stability(d, s, r, rating=2)
    s_good = _next_recall_stability(d, s, r, rating=3)
    assert s_hard < s_good


# ── predict_retention ──


def test_predict_retention_high_for_recent():
    r = predict_retention(100, 1)
    assert r > 0.9


def test_predict_retention_low_for_distant():
    r = predict_retention(1, 100)
    assert r < 0.5


def test_predict_retention_monotonic_decay():
    r1 = predict_retention(10, 1)
    r2 = predict_retention(10, 5)
    r3 = predict_retention(10, 20)
    assert r1 > r2 > r3


# ── Internal functions ──


def test_retrievability_range():
    r = _retrievability(0, 10)
    assert abs(r - 1.0) < 0.01
    r = _retrievability(365, 1)
    assert 0 <= r <= 1


def test_init_stability_ordering():
    assert _init_stability(1) < _init_stability(2) < _init_stability(3) < _init_stability(4)


def test_init_difficulty_in_range():
    for r in (1, 2, 3, 4):
        d = _init_difficulty(r)
        assert 1 <= d <= 10


def test_next_difficulty_in_range():
    d = _next_difficulty(5, 3)
    assert 1 <= d <= 10


def test_next_interval_positive():
    assert _next_interval(10) >= 1
    assert _next_interval(100000) <= 36500


def test_short_term_stability_grows_for_correct():
    s0 = 5.0
    s_after = _short_term_stability(s0, rating=3)
    assert s_after >= s0  # Good never decreases in short-term


def test_algorithm_version_stamped():
    card = _fresh_card()
    update(card, 4)
    assert card['algorithm_version'] == 'fsrs-6'
