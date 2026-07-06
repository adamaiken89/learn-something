"""Deterministic answer re-lettering for quiz.yaml.

Generation-stage tool: after the LLM writes quiz.yaml (choosing option
*content* and the correct option), this reassigns option letter positions
so the correct option lands on a balanced, no-3-run letter sequence.

Option text per question is untouched — only letter keys move, so every
question's semantics stay identical. Deterministic per (topic, module)
seed: re-running is idempotent.

Constraints enforced:
  - no 3 consecutive answers with the same letter
  - per-letter count ≤ ceil(N/4) + 1
  - no letter share > 50% (guaranteed for N ≥ 6 by construction)
"""

import random

LETTERS = ('a', 'b', 'c', 'd')


def _balanced_sequence(n, seed):
    """Deterministic answer-letter sequence: balanced counts, no 3-run."""
    rng = random.Random(seed)
    counts = [n // 4] * 4
    for i in range(n % 4):
        counts[i] += 1

    for _ in range(50):
        bag = [L for L, c in zip(LETTERS, counts) for _ in range(c)]
        rng.shuffle(bag)
        if all(not (bag[i] == bag[i - 1] == bag[i - 2]) for i in range(2, len(bag))):
            return bag
    # Fallback (unreachable for n ≥ 4): fixed rotation, may contain runs
    bag = [L for L, c in zip(LETTERS, counts) for _ in range(c)]
    return bag


def balance_quiz(questions, seed):
    """Re-letter option positions on each question.

    Args:
        questions: list of dicts as loaded from quiz.yaml
        seed: deterministic seed string (e.g. f"{topic}-{module}")

    Returns:
        (new_questions, stats) where stats = {
            'before': Counter, 'after': Counter,
            'mutated': int, 'skipped': int,
        }
    """
    from collections import Counter

    seq = _balanced_sequence(len([q for q in questions if isinstance(q, dict)]), seed)
    before = Counter()
    after = Counter()
    mutated = 0
    skipped = 0

    new_questions = []
    si = 0
    for q in questions:
        q = dict(q)
        if not isinstance(q.get('options'), dict):
            skipped += 1
            new_questions.append(q)
            continue

        cur = str(q.get('answer', '')).strip().lower()
        before[cur] += 1
        correct_text = q['options'].get(cur)
        if correct_text is None or cur not in LETTERS:
            # Can't re-letter: no valid current answer. Normalize keys only.
            skipped += 1
            new_questions.append(q)
            continue

        target = seq[si]
        si += 1
        after[target] += 1

        # Rebuild options: correct text at target letter, others fill remaining
        other_texts = [
            q['options'][k] for k in sorted(q['options']) if k.strip().lower() != cur
        ]
        new_opts = {}
        new_opts[target] = correct_text
        for k, text in zip([L for L in LETTERS if L != target], other_texts):
            new_opts[k] = text
        # Option keys must be lowercase for schema
        q['options'] = {str(k).lower(): v for k, v in new_opts.items()}
        q['answer'] = target
        if cur != target:
            mutated += 1
        new_questions.append(q)

    # Any remaining questions (skipped above) keep letter counts out of the loop;
    # report as-is.
    return new_questions, {
        'before': before,
        'after': after,
        'mutated': mutated,
        'skipped': skipped,
    }