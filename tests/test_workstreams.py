#!/usr/bin/env python3
"""Golden-fixture tests for the quality/syntax workstreams.

Error-class fixtures: each BAD fixture must be flagged by the matching
checker; each GOOD fixture must pass clean. Zero-dep direct-run runner,
mirrors tests/test_learn.py.

Covers:
  - quality.py: answer rotation, quiz/cumulative statistical rules
  - quizbalance.py: order-preserving cyclic re-lettering
  - mermaidcheck.py: subgraph/end scoping by diagram type + safe-mode lint
  - learn.py fence-parity walker + cloze extractability
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

import learn
import mermaidcheck
import quality
import quizbalance

# ── quality.py ────────────────────────────────────────────────────


def _quiz_item(i, ans):
    return {
        'id': f'1.{i}',
        'question': f'Q{i}?',
        'options': {'a': 'A', 'b': 'B', 'c': 'C', 'd': 'D'},
        'answer': ans,
        'explanation': 'e',
        'difficulty': 1,
        'tags': ['test'],
    }


def test_quiz_rotation_violation_flagged():
    qs = [_quiz_item(1, 'a'), _quiz_item(2, 'a'), _quiz_item(3, 'a')]
    errs = [
        e
        for e in quality.quiz_quality_errors(qs)
        if 'rotation' in str(e).lower() or 'consecutive' in str(e).lower()
    ]
    assert errs, f'expected rotation violation, got {quality.quiz_quality_errors(qs)}'
    print('  quiz_rotation_bad_flagged: OK')


def test_quiz_rotation_balanced_clean():
    qs = [_quiz_item(i, a) for i, a in enumerate('bcda' * 2, 1)]
    errs = [
        e
        for e in quality.quiz_quality_errors(qs)
        if 'rotation' in str(e).lower() or 'consecutive' in str(e).lower()
    ]
    assert not errs, f'balanced sequence flagged: {errs}'
    print('  quiz_rotation_good_clean: OK')


def _cum_path(lo, hi):
    return Path(f'cumulative_quiz_{lo:02d}-{hi:02d}.yaml')


def test_cumulative_range_span():
    cuf = _cum_path(1, 6)
    item = {'id': 'cum.1', 'type': 'tf', 'source_modules': [1], 'statement': 'x', 'answer': True, 'difficulty': 1, 'tags': []}
    mods = ['01-a', '02-b', '03-c', '04-d', '05-e', '06-f']
    errs = quality.cumulative_quality_errors(cuf, mods, lambda p: [item])
    assert any('spans' in str(e) for e in errs), f'span>4 not caught: {errs}'
    print('  cumulative_span_bad_flagged: OK')


def test_cumulative_source_outside_range():
    cuf = _cum_path(1, 2)
    item = {'id': 'cum.1', 'type': 'tf', 'source_modules': [9], 'statement': 'x', 'answer': True, 'difficulty': 1, 'tags': []}
    mods = ['01-a', '02-b', '03-c']
    errs = quality.cumulative_quality_errors(cuf, mods, lambda p: [item])
    assert any('source_modules' in str(e) for e in errs), (
        f'out-of-range source not caught: {errs}'
    )
    print('  cumulative_source_bad_flagged: OK')


def _cum_item(i, typ='mcq', **kw):
    base = {'id': f'cum.{i}', 'type': typ, 'source_modules': [1], 'difficulty': 1, 'tags': []}
    if typ == 'mcq':
        base.update({'question': f'q{i}?', 'options': {'a': 'A', 'b': 'B', 'c': 'C', 'd': 'D'}, 'answer': kw.get('ans', 'a')})
    elif typ == 'tf':
        base.update({'statement': f's{i}', 'answer': True})
    else:
        term = kw.get('term', 'x')
        base.update({'question': f'{term} blank', 'answer': term})
    return base


def _cum_minimal_valid(ans_seq='abcdabcd'):
    """8 mcq (balanced) + 1 cloze + 1 tf = valid shape for range 01-02."""
    items = [_cum_item(i, 'mcq', ans=a) for i, a in enumerate(ans_seq[:8], 1)]
    items.append(_cum_item(9, 'cloze'))
    items.append(_cum_item(10, 'tf'))
    for it in items[8:]:
        it['source_modules'] = [2]
    return items


def test_cumulative_mcq_rotation():
    cuf = _cum_path(1, 2)
    mods = ['01-a', '02-b']
    bad = _cum_minimal_valid('aaaaaaaa')
    errs = quality.cumulative_quality_errors(cuf, mods, lambda p: bad)
    assert any('rotation' in str(e).lower() or 'consecutive' in str(e).lower() for e in errs), (
        f'mcq rotation violation not caught in cumulative: {errs}'
    )
    good = _cum_minimal_valid()
    errs2 = quality.cumulative_quality_errors(cuf, mods, lambda p: good)
    assert not errs2, f'valid cumulative flagged: {errs2}'
    print('  cumulative_mcq_rotation: OK')


def test_cumulative_type_mix():
    cuf = _cum_path(1, 1)
    items = [_cum_item(i, 'mcq') for i in range(1, 9)]
    errs = quality.cumulative_quality_errors(cuf, ['01-a'], lambda p: items)
    assert any('type mix' in str(e) for e in errs), (
        f'missing type mix not caught: {errs}'
    )
    print('  cumulative_typemix_bad_flagged: OK')


# ── quizbalance.py ────────────────────────────────────────────────


def test_balance_preserves_option_order():
    qs = [{
        'id': '1.1', 'question': 'Q?',
        'options': {'a': 'right', 'b': 'w1', 'c': 'w2', 'd': 'w3'},
        'answer': 'a',
    }]
    new, stats = quizbalance.balance_quiz(qs, seed='order-seed')
    texts_after = list(new[0]['options'].values())
    orig = ['right', 'w1', 'w2', 'w3']
    is_rotation = any(orig[k:] + orig[:k] == texts_after for k in range(4))
    assert is_rotation, f'options reordered arbitrarily: {texts_after}'
    assert new[0]['options'][new[0]['answer']] == 'right'
    print('  balance_option_order_preserved: OK')


def test_balance_correct_intact_and_idempotent():
    qs = [
        {'id': '1.1', 'question': 'Q1', 'options': {'a': 'r1', 'b': 'b1', 'c': 'c1', 'd': 'd1'}, 'answer': 'c'},
        {'id': '1.2', 'question': 'Q2', 'options': {'a': 'a2', 'b': 'r2', 'c': 'c2', 'd': 'd2'}, 'answer': 'b'},
        {'id': '1.3', 'question': 'Q3', 'options': {'a': 'a3', 'b': 'b3', 'c': 'r3', 'd': 'd3'}, 'answer': 'c'},
        {'id': '1.4', 'question': 'Q4', 'options': {'a': 'a4', 'b': 'b4', 'c': 'c4', 'd': 'r4'}, 'answer': 'd'},
        {'id': '1.5', 'question': 'Q5', 'options': {'a': 'a5', 'b': 'b5', 'c': 'c5', 'd': 'r5'}, 'answer': 'd'},
        {'id': '1.6', 'question': 'Q6', 'answer': 'x'},  # no options — skipped
    ]
    orig_correct = {q['id']: q['options'][q['answer']] for q in qs if isinstance(q.get('options'), dict)}
    new, stats = quizbalance.balance_quiz(qs, seed='idem-seed')
    new_correct = {q['id']: q['options'][q['answer']] for q in new if isinstance(q.get('options'), dict)}
    assert new_correct == orig_correct, f'correct option text changed: {new_correct}'
    assert stats['skipped'] == 1
    new2, _ = quizbalance.balance_quiz(new, seed='idem-seed')
    assert new == new2, 'not idempotent'
    print('  balance_correct_intact_idempotent: OK')


# ── mermaidcheck.py ───────────────────────────────────────────────


def test_sequence_alt_end_not_subgraph_error():
    content = '''```mermaid
sequenceDiagram
    A->>B: hi
    alt ok
        B-->>A: yes
    else no
        B-->>A: nope
    end
```'''
    assert mermaidcheck.validate_mermaid(content) == [], mermaidcheck.validate_mermaid(content)
    print('  sequence_alt_end_clean: OK')


def test_flowchart_missing_end_flagged():
    content = '''```mermaid
flowchart LR
    subgraph SG["T"]
      A --> B
```'''
    errs = mermaidcheck.validate_mermaid(content)
    assert errs, 'missing end should be flagged'
    print('  flowchart_missing_end_flagged: OK')


BAD_MERMAID = '''```mermaid
flowchart LR
    A[Calculate % Change<br/>|new - prev|] --> B
    C -->|Depth <= limit| D
    E -- Cost > quota --> F
    G + H + I --> J
    subgraph SG (Greedy)
      K[Pass@1 score]
    end
    L[喺呢度] --> M
```

```mermaid
flowchart LR
    A["safe quoted label"] -->|"ok <= here"| B["plain"]
    subgraph S1["Quoted title"]
      C["fine"]
    end
```'''


def test_safemode_flags_all_risky_classes():
    issues = mermaidcheck.safe_mode_errors(BAD_MERMAID)
    msgs = ' || '.join(m for _, _, m in issues)
    for needle in (
        'unquoted node label',
        '|"Depth <= limit"|',
        "Cost > quota",
        "'&'",
        'subgraph id[',
        'CJK',
    ):
        assert needle in msgs, f'missing {needle!r} in findings:\n{msgs}'
    # block 2 (good) must contribute nothing
    assert all(b == 1 for b, _, _ in issues), f'good block flagged: {issues}'
    print('  safemode_bad_classes_flagged: OK')


def test_safemode_clean_on_safe_diagram():
    good = BAD_MERMAID.split('```')[2]
    assert mermaidcheck.safe_mode_errors(good) == []
    print('  safemode_good_clean: OK')


# ── fence parity + cloze extractability (learn.py doctor internals) ──


def test_fence_parity_text_closer_and_bare_opener():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'lesson.md'
        # ```text in CLOSER position (retype-corruption artifact) + bare opener
        p.write_text('# T\n\n```\nfoo\n```text\n\n```\nbare opener never closed\n')
        errs = learn._fence_parity_errors(p)
        joined = '\n'.join(errs)
        assert 'text-as-closer' in joined, f'text-as-closer not flagged: {errs}'
        assert 'bare fence opener' in joined
        assert 'unclosed' in joined.lower()
    print('  fence_parity_corruptions_flagged: OK')


def test_fence_parity_clean_file():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'lesson.md'
        p.write_text('# T\n\n```python\nprint(1)\n```\n\ntext.\n')
        assert learn._fence_parity_errors(p) == []
    print('  fence_parity_good_clean: OK')


def test_cloze_answer_extractability():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'cloze.yaml'
        import yaml

        items = [
            {'id': 'c.1', 'question': 'The {b-tree} governs lookups.', 'answer': 'b-tree', 'difficulty': 1, 'tags': []},
            {'id': 'c.2', 'question': 'The {wal} flushes first.', 'answer': 'totally unrelated', 'difficulty': 1, 'tags': []},
            {'id': 'c.3', 'question': 'No blanks here at all.', 'answer': 'x', 'difficulty': 1, 'tags': []},
        ]
        p.write_text(yaml.dump(items, allow_unicode=True))
        errs = learn._cloze_extract_errors(p)
        joined = '\n'.join(errs)
        assert 'c.1' not in joined, f'good cloze flagged: {joined}'
        assert 'c.2' in joined and 'not extractable' in joined
        assert 'c.3' in joined and ('blank' in joined.lower())
    print('  cloze_extract_errors_flagged: OK')


if __name__ == '__main__':
    tests = [
        v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)
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
