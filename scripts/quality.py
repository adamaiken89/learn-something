"""Shared content-quality rule engine.

Single source of truth for the quality/statistical rules enforced by
`learn.sh validate`. Imported by learn.py (validate), checksyntax.py,
and the generators so post-write hooks call one function instead of
re-implementing rules ad hoc.

Schema validation stays in learn.py (_schema_errors); this module owns
the pedagogical/statistical layer:

- lesson.md structural rules 8, 11, 12, 13, 15 (ERR) and 9, 16, 17 (WARN)
- quiz.yaml statistical checks (count, Q-per-LO, rotation, spread, difficulty)
- cloze.yaml count check
- cumulative_quiz_XX-YY.yaml coverage checks

No typer dependency: callers pass a topic directory Path.
"""

import re
import sys
from collections import Counter

YELLOW = '\033[93m'
NC = '\033[0m'


def quality_checks(t, module=None, max_chars=12000):
    """Pass 3+4: quality gate. Rule 15 ERR; rule 16 WARN only (user-determined threshold).

    t: pathlib.Path to the topic directory.
    Returns list of (relative_name, [error strings]).
    WARN-level findings print to stderr directly (rules 9, 16, 17).
    """
    import yaml as _yaml

    results = []

    if module:
        mods = [module]
    else:
        mods = sorted(d.name for d in t.glob('modules/*') if d.is_dir())

    # Load syllabus learning objectives for Q-per-LO check
    n_objectives = 0
    syll_path = t / 'syllabus.yaml'
    if syll_path.exists():
        try:
            syll = _yaml.safe_load(syll_path.read_text())
            n_objectives = len(syll.get('learning_objectives', [])) if isinstance(syll, dict) else 0
        except Exception:
            pass

    for m in mods:
        mod_path = t / 'modules' / m

        # ── lesson.md structural checks ──
        lesson_path = mod_path / 'lesson.md'
        if lesson_path.exists():
            content = lesson_path.read_text(encoding='utf-8', errors='replace')
            errs = []

            # Rule 15: mindmap compulsory
            if not re.search(r'```mermaid\s*\n\s*mindmap', content) and not re.search(
                r'```\s*mindmap', content
            ):
                errs.append(
                    'quality: missing module mindmap (```mermaid\\nmindmap ...) — rule 15, compulsory'
                )
            # Rule 16: module size — WARN only, threshold user-determined via --max-chars.
            # Primary size control is the module time budget (syllabus time_hours ≤ 1.5h).
            if len(content) > max_chars:
                print(
                    f'{YELLOW}  WARN: lesson.md {len(content)} chars > {max_chars} (--max-chars) — rule 16 (soft target, non-blocking)',
                    file=sys.stderr,
                )
            # Rule 17: human-readable H1 — `# Module NN: <name>` with plain-number id.
            # Slug leak (`# Module NN-name: ...`) = folder name copied into the title; WARN only.
            h1 = re.search(r'(?m)^#\s*Module\s+([^:]+):', content)
            if not h1:
                print(
                    f'{YELLOW}  WARN: no `# Module NN: <name>` H1 — rule 17 (human-readable title){NC}',
                    file=sys.stderr,
                )
            elif not h1.group(1).strip().isdigit():
                print(
                    f'{YELLOW}  WARN: H1 module id "{h1.group(1).strip()}" is not a plain number — rule 17 (no directory slug in title){NC}',
                    file=sys.stderr,
                )
            # Fence-aware view: strip ``` code/mermaid blocks so content-block rules
            # only see prose/blockquotes (kills Mermaid node-brace false positives too)
            non_fence = re.sub(r'```[^\n]*\n.*?```', '', content, flags=re.DOTALL)
            # Rule 8: Socratic Think blocks — > **Think** blockquote form
            if not re.search(r'(?m)^>\s*\*\*Think\*\*', non_fence):
                errs.append('quality: no > **Think** blockquote — rule 8')
            # Rule 11: cloze deletions (non-fence content only)
            if not re.search(r'\*\*Cloze\*\*|\{[^}]{1,60}\}', non_fence):
                errs.append('quality: no cloze {blank} in lesson — rule 11')
            # Rule 12: predict-next — > **Predict** blockquote form
            if not re.search(r'(?m)^>\s*\*\*Predict\*\*', non_fence):
                errs.append('quality: no > **Predict** blockquote — rule 12')
            # Rule 13: error-spotting — > **Spot the Mistake** blockquote OR
            # ## Spot the Mistake heading whose section has non-fence body
            ok13 = bool(re.search(r'(?m)^>\s*\*\*Spot the Mistake\*\*', non_fence))
            if not ok13:
                heading = re.search(r'(?m)^##\s+Spot the Mistake\b', content)
                if heading:
                    sect = content[heading.end() :]
                    nxt = re.search(r'^##\s+', sect, re.MULTILINE)
                    if nxt:
                        sect = sect[: nxt.start()]
                    sect_non_fence = re.sub(r'```[^\n]*\n.*?```', '', sect, flags=re.DOTALL)
                    ok13 = any(ln.strip() for ln in sect_non_fence.split('\n'))
            if not ok13:
                errs.append('quality: no Spot the Mistake exercise — rule 13')
            # Rule 9: dual coding — visual asset present (WARN).
            # Per §A4.1: mermaid block or markdown table counts.
            has_visual = bool(re.search(r'```mermaid', content)) or bool(
                re.search(r'^\|.+\|\s*\n\|[\s\-:|]+\|', content, re.MULTILINE)
            )
            if not has_visual:
                print(
                    f'{YELLOW}  WARN: no visual asset (mermaid/table/comic) — rule 9 (dual coding){NC}'
                )
            if errs:
                results.append((f'{m}/lesson.md', errs))

        # ── quiz.yaml checks ──
        quiz_path = mod_path / 'quiz.yaml'
        if quiz_path.exists():
            try:
                qs = _yaml.safe_load(quiz_path.read_text())
                errs = []
                if not isinstance(qs, list):
                    errs.append('quality: quiz.yaml not a top-level list')
                else:
                    errs.extend(quiz_quality_errors(qs, n_objectives))
                if errs:
                    results.append((f'{m}/quiz.yaml', errs))
            except Exception as e:
                results.append((f'{m}/quiz.yaml', [f'quality: parse error {e}']))

        # ── cloze.yaml checks ──
        cloze_path = mod_path / 'cloze.yaml'
        if cloze_path.exists():
            try:
                cs = _yaml.safe_load(cloze_path.read_text())
                errs = []
                if not isinstance(cs, list):
                    errs.append('quality: cloze.yaml not a top-level list')
                elif len(cs) < 8:
                    errs.append(f'quality: {len(cs)} cloze questions < 8 minimum — target 8-10')
                if errs:
                    results.append((f'{m}/cloze.yaml', errs))
            except Exception as e:
                results.append((f'{m}/cloze.yaml', [f'quality: parse error {e}']))

    # ── cumulative quiz coverage ──
    cum_files = sorted(t.glob('cumulative_quiz*.yaml'))
    if len(mods) >= 3 and not cum_files:
        results.append(
            (
                'cumulative_quiz_XX-YY.yaml',
                ['quality: no cumulative quiz — needed after 3+ modules'],
            )
        )

    for cuf in cum_files:
        cerrs = cumulative_quality_errors(
            cuf, mods, loader=lambda p: _yaml.safe_load(p.read_text())
        )
        if cerrs:
            results.append((cuf.name, cerrs))

    return results


def answer_rotation_error(ans, label='answer rotation'):
    """No 3 consecutive questions share the same answer letter."""
    for i in range(2, len(ans)):
        if ans[i] == ans[i - 1] == ans[i - 2] and ans[i] in 'abcd':
            return f'quality: 3+ consecutive same answer letter (q{i + 1}) — {label}'
    return None


def quiz_quality_errors(qs, n_objectives=0):
    """Statistical checks for a parsed quiz.yaml top-level list."""
    errs = []
    # item count 8-10 (schema floor 5; quality target 8-10)
    if len(qs) < 8:
        errs.append(f'quality: {len(qs)} questions < 8 minimum — target 8-10')
    # ≥1 Q per learning objective
    if n_objectives and len(qs) < n_objectives:
        errs.append(f'quality: {len(qs)} questions < {n_objectives} learning objectives')
    # answer rotation: no 3 consecutive same letter
    ans = [str(q.get('answer', '')).lower() for q in qs]
    rot = answer_rotation_error(ans)
    if rot:
        errs.append(rot)
    # answer spread: no letter > 50%
    if ans:
        counts = Counter(a for a in ans if a in 'abcd')
        if counts:
            top = max(counts.values()) / len(ans)
            if top > 0.5:
                errs.append(
                    f'quality: answer spread skewed ({max(counts, key=counts.get)} = {top:.0%})'
                )
    # difficulty mix ~40/40/20
    ds = [q.get('difficulty') for q in qs if isinstance(q, dict)]
    if ds:
        c = Counter(ds)
        p3 = c.get(3, 0) / len(ds)
        if p3 > 0.4:
            errs.append(f'quality: difficulty 3 dominates ({p3:.0%}) — target ~40/40/20')
    return errs


def cumulative_quality_errors(cuf, mods, loader):
    """Checks for one cumulative_quiz_XX-YY.yaml file. loader(Path) -> parsed YAML."""
    range_errs = []
    m = re.match(r'^cumulative_quiz_(\d+)-(\d+)\.yaml$', cuf.name)
    lo = hi = None
    if not m:
        range_errs.append('quality: filename must carry module range cumulative_quiz_XX-YY.yaml')
    else:
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo < 1 or hi < lo:
            range_errs.append(f'quality: invalid module range {cuf.name}')
        elif hi - lo + 1 > 4:
            range_errs.append(
                f'quality: range {cuf.name} spans {hi - lo + 1} modules — max 4 per cumulative quiz'
            )
        elif mods:
            course_max = max(int(d.split('-', 1)[0]) for d in mods)
            if len(mods) >= 3 and hi > course_max:
                range_errs.append(
                    f'quality: range {cuf.name} ends at module {hi} beyond course ({course_max})'
                )
    try:
        cq = loader(cuf)
        if not isinstance(cq, list):
            return range_errs + ['quality: not a top-level list']
        types = [q.get('type', 'mcq') for q in cq]
        c = Counter(types)
        mcq, cloze, tf = c.get('mcq', 0), c.get('cloze', 0), c.get('tf', 0)
        errs = []
        if mcq < 1 or cloze < 1 or tf < 1:
            errs.append(f'quality: cumulative type mix {dict(c)} — need ≥1 each of mcq/cloze/tf')
        if len(cq) < 8:
            errs.append(f'quality: {len(cq)} questions < 8 minimum')
        if lo is not None and not range_errs:
            for q in cq:
                sm = q.get('source_modules')
                if isinstance(sm, list) and any(
                    not isinstance(x, int) or x < lo or x > hi for x in sm
                ):
                    errs.append(
                        f'quality: source_modules [{sm}] outside range {lo}-{hi} ({q.get("id")})'
                    )
        ans = [str(q.get('answer', '')).lower() for q in cq if q.get('type') == 'mcq']
        rot = answer_rotation_error(ans)
        if rot:
            errs.append(rot.replace(' — answer rotation', ''))
        if errs or range_errs:
            return range_errs + errs
        return []
    except Exception as e:
        return range_errs + [f'quality: parse error {e}']
