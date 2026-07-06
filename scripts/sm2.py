"""FSRS-5 spaced repetition algorithm.

Replaces SM-2. Uses FSRS-5 model from py-fsrs (open-spaced-repetition/py-fsrs).
Interface: update(card, quality) — compatible with SM-2 callers.

Card schema adds: stability, difficulty, lapses, state
Backward compat: easeFactor, interval, repetitions (derived)
"""

from datetime import datetime, timedelta
from math import exp

# FSRS-5 default parameters (21 params, from py-fsrs v6)
_W = (
    0.212,
    1.2931,
    2.3065,
    8.2956,
    8.2956,
    0.8334,
    3.0194,
    0.001,
    1.8722,
    0.1666,
    0.796,
    1.4835,
    0.0614,
    0.2629,
    1.6483,
    0.6014,
    1.8729,
    0.5425,
    0.0912,
    0.0658,
    0.1542,
)

_DECAY = -_W[20]
_FACTOR = 0.9 ** (1 / _DECAY) - 1
_MAX_INTERVAL = 36500


def _retrievability(elapsed_days, stability):
    return (1 + _FACTOR * elapsed_days / stability) ** _DECAY


def _short_term_stability(stability, rating):
    """Stability for reviews < 1 day after last review."""
    increase = exp(_W[17] * (rating - 3 + _W[18])) * (stability ** (-_W[19]))
    if rating >= 3:
        increase = max(increase, 1.0)
    return max(0.001, stability * increase)


def _init_stability(rating):
    return max(0.001, _W[rating - 1])


def _init_difficulty(rating):
    d = _W[4] - exp(_W[5] * (rating - 1)) + 1
    return min(max(d, 1), 10)


def _linear_damping(delta_d, d):
    return (10 - d) * delta_d / 9


def _mean_reversion(arg1, arg2):
    return _W[7] * arg1 + (1 - _W[7]) * arg2


def _next_difficulty(difficulty, rating):
    arg1 = _W[4] - exp(_W[5] * (4 - 1)) + 1  # initial difficulty for Easy
    delta_d = -_W[6] * (rating - 3)
    arg2 = difficulty + _linear_damping(delta_d, difficulty)
    nd = _mean_reversion(arg1, arg2)
    return min(max(nd, 1), 10)


def _next_recall_stability(difficulty, stability, retrievability, rating):
    hard_penalty = _W[15] if rating == 2 else 1
    easy_bonus = _W[16] if rating == 4 else 1
    delta = (
        exp(_W[8])
        * (11 - difficulty)
        * (stability ** (-_W[9]))
        * (exp((1 - retrievability) * _W[10]) - 1)
        * hard_penalty
        * easy_bonus
    )
    return max(0.001, stability * (1 + delta))


def _next_forget_stability(difficulty, stability, retrievability):
    long_term = (
        _W[11]
        * (difficulty ** (-_W[12]))
        * ((stability + 1) ** _W[13] - 1)
        * exp((1 - retrievability) * _W[14])
    )
    short_term = stability / exp(_W[17] * _W[18])
    return max(0.001, min(long_term, short_term))


def _next_interval(stability):
    interval = (stability / _FACTOR) * ((0.9 ** (1 / _DECAY)) - 1)
    return max(1, min(_MAX_INTERVAL, round(interval)))


def _grade(quality):
    """Map caller quality (0-5) to FSRS rating (1=Again, 3=Good)."""
    if quality >= 4:
        return 3  # Good
    return 1  # Again


def _migrate_sm2_card(card):
    if 'stability' not in card:
        interval = card.get('interval', 0)
        reps = card.get('repetitions', 0)
        ef = card.get('easeFactor', 2.5)
        card['stability'] = max(1.0, interval)
        card['difficulty'] = min(max(5 + (2.5 - ef) * 2, 1), 10)
        card['lapses'] = 0
        card['state'] = 'Review' if reps > 0 else 'New'
    return card


def predict_retention(stability, elapsed_days):
    """Predicted retention probability (0-1) given stability and days since last review."""
    return _retrievability(elapsed_days, stability)


def update(card, quality):
    _migrate_sm2_card(card)

    rating = _grade(quality)
    state = card.get('state', 'New')
    now = datetime.now()

    # Calculate elapsed days and retrievability
    last_review = card.get('lastReviewed')
    if last_review:
        try:
            lr = datetime.strptime(last_review, '%Y-%m-%d')
            elapsed_days = max(0, (now - lr).days)
        except ValueError:
            elapsed_days = 0
    else:
        elapsed_days = 0

    if state == 'New':
        card['stability'] = _init_stability(rating)
        card['difficulty'] = _init_difficulty(rating)
        card['lapses'] = 0
        card['state'] = 'Review'
    elif elapsed_days < 1:
        # Short-term (< 1 day): use short-term formula
        if rating >= 3:
            card['stability'] = _short_term_stability(card['stability'], rating)
        else:
            card['stability'] = _next_forget_stability(card['difficulty'], card['stability'], 1.0)
        card['difficulty'] = _next_difficulty(card['difficulty'], rating)
        if rating < 3:
            card['lapses'] = card.get('lapses', 0) + 1
            card['state'] = 'Relearning'
    elif rating >= 3:
        r = _retrievability(elapsed_days, card['stability'])
        card['stability'] = _next_recall_stability(card['difficulty'], card['stability'], r, rating)
        card['difficulty'] = _next_difficulty(card['difficulty'], rating)
    else:
        r = _retrievability(elapsed_days, card['stability'])
        card['lapses'] = card.get('lapses', 0) + 1
        card['stability'] = _next_forget_stability(card['difficulty'], card['stability'], r)
        card['difficulty'] = _next_difficulty(card['difficulty'], rating)
        card['state'] = 'Relearning'

    interval = _next_interval(card['stability'])
    card['interval'] = interval
    card['easeFactor'] = round(min(max(2.5 - (card['difficulty'] - 5) * 0.15, 1.3), 5.0), 2)
    card['repetitions'] = card.get('repetitions', 0) + 1 if rating >= 3 else 0
    card['nextReviewDate'] = (now + timedelta(days=interval)).strftime('%Y-%m-%d')
    card['lastReviewed'] = now.strftime('%Y-%m-%d')

    return card
