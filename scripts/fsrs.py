"""FSRS-6 spaced repetition algorithm.

Replaces FSRS-5 (formerly sm2.py). Self-contained — no py-fsrs dependency.

Algorithm source: open-spaced-repetition/py-fsrs v6.
Parameter set: 19 weights (down from 21 in FSRS-5).
Rating scale: 1=Again, 2=Hard, 3=Good, 4=Easy (4-level, was 3-level).
States: New → Learning → Review → Relearning → (lapse) → Relearning.

Public interface:
    update(card, quality, rating=None) — schedule next review
    predict_retention(stability, elapsed_days) — R(t, S)
    get_desired_retention(card) — per-card target R (default 0.9)

Card schema (additions vs FSRS-5):
    + algorithm_version: "fsrs-6"
    + desired_retention: float (optional, default 0.9)
    + learning_step: int days (optional, default 0 = same-day)
    ~ state: now includes "Learning"

Backward compat:
    Old SM-2 / FSRS-5 cards auto-migrate on first update() via _migrate_card().
    easeFactor/interval/repetitions kept as derived fields.
"""

from datetime import datetime, timedelta
from math import exp

# FSRS-6 default parameters (19 params, py-fsrs v6)
_W = (
    0.4072,  # W[0]  init S for Again
    1.1829,  # W[1]  init S for Hard
    3.1262,  # W[2]  init S for Good
    15.4722,  # W[3]  init S for Easy
    7.2102,  # W[4]  D0 constant
    0.5316,  # W[5]  D0 slope
    1.0651,  # W[6]  difficulty delta
    0.0054,  # W[7]  mean reversion weight
    1.4834,  # W[8]  recall stability factor
    0.1196,  # W[9]  recall stability retrievability exponent
    1.0005,  # W[10] recall stability forgetting modifier
    1.6164,  # W[11] forget stability factor
    0.1544,  # W[12] forget stability difficulty exponent
    0.8699,  # W[13] forget stability stability exponent
    2.0141,  # W[14] forget stability retrievability modifier
    0.0072,  # W[15] hard penalty
    0.5855,  # W[16] easy bonus
    1.2253,  # W[17] short-term stability slope (+ DECAY source)
    0.0461,  # W[18] short-term stability rating offset
    0.0978,  # W[19] short-term stability stability exponent
)

_DECAY = -_W[17]
_FACTOR = 0.9 ** (1 / _DECAY) - 1
_MAX_INTERVAL = 36500
_DEFAULT_DESIRED_RETENTION = 0.9
_DEFAULT_LEARNING_STEP = 0  # days; 0 = same-day graduation


# ── Core math ───────────────────────────────────────────────────


def _retrievability(elapsed_days, stability):
    return (1 + _FACTOR * elapsed_days / stability) ** _DECAY


def predict_retention(stability, elapsed_days):
    """Predicted retention probability (0-1) given stability and days since last review."""
    return _retrievability(elapsed_days, stability)


def _short_term_stability(stability, rating):
    """Stability for reviews < 1 day after last review."""
    increase = exp(_W[17] * (rating - 3 + _W[18])) * (stability ** -_W[19])
    if rating >= 3:
        increase = max(increase, 1.0)
    return max(0.001, stability * increase)


def _init_stability(rating):
    return max(0.001, _W[rating - 1])


def _init_difficulty(rating):
    # FSRS-6: baseline uses rating-3 (midpoint), not rating-1
    d = _W[4] - exp(_W[5] * (rating - 3)) + 1
    return min(max(d, 1), 10)


def _linear_damping(delta_d, d):
    return (10 - d) * delta_d / 9


def _mean_reversion(arg1, arg2):
    return _W[7] * arg1 + (1 - _W[7]) * arg2


def _next_difficulty(difficulty, rating):
    # FSRS-6 baseline: initial difficulty for rating=3 (Good)
    arg1 = _init_difficulty(3)
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
        * (stability ** -_W[9])
        * (exp((1 - retrievability) * _W[10]) - 1)
        * hard_penalty
        * easy_bonus
    )
    return max(0.001, stability * (1 + delta))


def _next_forget_stability(difficulty, stability, retrievability):
    long_term = (
        _W[11]
        * (difficulty ** -_W[12])
        * ((stability + 1) ** _W[13] - 1)
        * exp((1 - retrievability) * _W[14])
    )
    short_term = stability / exp(_W[17] * _W[18])
    return max(0.001, min(long_term, short_term))


def get_desired_retention(card):
    return card.get('desired_retention', _DEFAULT_DESIRED_RETENTION)


def _next_interval(stability, desired_retention=None):
    """FSRS-6: interval solves R(t, S) = desired_retention for t."""
    r = desired_retention if desired_retention is not None else 0.9
    # R = (1 + factor*t/S)^decay → t = S/factor * (r^(1/decay) - 1)
    interval = (stability / _FACTOR) * (r ** (1 / _DECAY) - 1)
    return max(1, min(_MAX_INTERVAL, round(interval)))


# ── Rating mapping ──────────────────────────────────────────────


def _grade(quality, explicit_rating):
    """Map caller input to FSRS-6 rating (1-4).

    Callers may pass either:
      - quality (0-5 SM-2 style): collapsed to 4-level via thresholds
      - explicit_rating (1-4): passed through directly
    """
    if explicit_rating is not None:
        return max(1, min(4, int(explicit_rating)))
    if quality >= 4:
        return 3  # Good
    if quality == 3:
        return 2  # Hard
    return 1  # Again (quality 0-2)


# ── Migration (SM-2 / FSRS-5 → FSRS-6) ──────────────────────────


def _migrate_card(card):
    """Idempotent. Adds FSRS-6 fields if missing; recomputes from FSRS-5 if needed.

    Migration sources:
      A) SM-2:    no stability/difficulty fields present
      B) FSRS-5:  has stability/difficulty but no algorithm_version
                  → recompute via FSRS-6 formulas on next update()
                  (just stamp version; update() will rederive)
    """
    if 'stability' not in card:
        # Path A: SM-2 → FSRS-6 in one step
        interval = card.get('interval', 0)
        reps = card.get('repetitions', 0)
        ef = card.get('easeFactor', 2.5)
        card['stability'] = max(1.0, float(interval) if interval else 1.0)
        card['difficulty'] = min(max(5 + (2.5 - ef) * 2, 1), 10)
        card['lapses'] = 0
        card['state'] = 'Review' if reps > 0 else 'New'

    # Stamp defaults if missing
    card.setdefault('desired_retention', _DEFAULT_DESIRED_RETENTION)
    card.setdefault('learning_step', _DEFAULT_LEARNING_STEP)

    # Mark algorithm version — update() may overwrite on next call
    if card.get('algorithm_version') != 'fsrs-6':
        card['algorithm_version'] = 'fsrs-6-pending'
    return card


# ── Main update ─────────────────────────────────────────────────


def update(card, quality, rating=None, now=None):
    """Schedule next review. Returns updated card.

    Args:
        card: card dict (mutated in place and returned)
        quality: int 0-5 (SM-2 style, mapped to 1-4)
        rating: int 1-4 (FSRS-6 native, takes precedence if given)
        now: datetime (defaults to datetime.now(); injectable for tests)
    """
    _migrate_card(card)

    fsrs_rating = _grade(quality, rating)
    state = card.get('state', 'New')
    now = now or datetime.now()

    # Elapsed days since last review
    last_review = card.get('lastReviewed')
    if last_review:
        try:
            lr = datetime.strptime(last_review, '%Y-%m-%d')
            elapsed_days = max(0, (now - lr).days)
        except ValueError:
            elapsed_days = 0
    else:
        elapsed_days = 0

    # FSRS-5→6 re-derive: if pending, treat as fresh init for current rating
    pending_reeval = card.get('algorithm_version') == 'fsrs-6-pending'

    if state == 'New':
        card['stability'] = _init_stability(fsrs_rating)
        card['difficulty'] = _init_difficulty(fsrs_rating)
        card['lapses'] = 0
        # New cards skip Learning if rating is Good/Easy; Again/Hard go to Learning
        if fsrs_rating >= 3:
            card['state'] = 'Review'
        else:
            card['state'] = 'Learning'
    elif state == 'Learning':
        # In Learning: only short-term formula applies
        if fsrs_rating >= 3:
            # Graduate to Review
            card['stability'] = _init_stability(fsrs_rating)
            card['difficulty'] = _init_difficulty(fsrs_rating)
            card['state'] = 'Review'
        else:
            # Stay in Learning; reset short-term stability
            card['stability'] = _short_term_stability(card.get('stability', 1.0), fsrs_rating)
    elif state == 'Relearning':
        if fsrs_rating >= 3:
            # Graduate back to Review
            r = _retrievability(elapsed_days, card.get('stability', 1.0))
            card['stability'] = _next_recall_stability(
                card['difficulty'], card.get('stability', 1.0), r, fsrs_rating
            )
            card['difficulty'] = _next_difficulty(card['difficulty'], fsrs_rating)
            card['state'] = 'Review'
        else:
            # Still lapsing; same-day, short-term
            card['stability'] = _short_term_stability(card.get('stability', 1.0), fsrs_rating)
    elif elapsed_days < 1:
        # Same-day review (any state): short-term formula
        if fsrs_rating >= 3:
            card['stability'] = _short_term_stability(card.get('stability', 1.0), fsrs_rating)
        else:
            card['stability'] = _next_forget_stability(
                card.get('difficulty', 5.0), card.get('stability', 1.0), 1.0
            )
            card['lapses'] = card.get('lapses', 0) + 1
            card['state'] = 'Relearning'
        card['difficulty'] = _next_difficulty(card.get('difficulty', 5.0), fsrs_rating)
    elif fsrs_rating >= 3:
        # Long-term correct
        if pending_reeval:
            # Re-derive: use init formulas with new rating, not cumulative recall
            card['stability'] = _init_stability(fsrs_rating)
            card['difficulty'] = _init_difficulty(fsrs_rating)
        else:
            r = _retrievability(elapsed_days, card.get('stability', 1.0))
            card['stability'] = _next_recall_stability(
                card['difficulty'], card['stability'], r, fsrs_rating
            )
            card['difficulty'] = _next_difficulty(card['difficulty'], fsrs_rating)
    else:
        # Long-term lapse
        r = _retrievability(elapsed_days, card.get('stability', 1.0))
        card['lapses'] = card.get('lapses', 0) + 1
        card['stability'] = _next_forget_stability(
            card.get('difficulty', 5.0), card.get('stability', 1.0), r
        )
        card['difficulty'] = _next_difficulty(card.get('difficulty', 5.0), fsrs_rating)
        card['state'] = 'Relearning'

    # Schedule next review
    desired = get_desired_retention(card)
    if card['state'] in ('Learning', 'Relearning'):
        # Same-day or 1-day step; not the long-term schedule
        interval = card.get('learning_step', _DEFAULT_LEARNING_STEP) or 0
    else:
        interval = _next_interval(card.get('stability', 1.0), desired_retention=desired)

    card['interval'] = interval
    card['easeFactor'] = round(
        min(max(2.5 - (card.get('difficulty', 5.0) - 5) * 0.15, 1.3), 5.0), 2
    )
    card['repetitions'] = card.get('repetitions', 0) + 1 if fsrs_rating >= 3 else 0
    card['nextReviewDate'] = (now + timedelta(days=interval)).strftime('%Y-%m-%d')
    card['lastReviewed'] = now.strftime('%Y-%m-%d')
    card['algorithm_version'] = 'fsrs-6'

    return card
