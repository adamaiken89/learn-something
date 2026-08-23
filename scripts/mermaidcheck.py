"""Basic Mermaid syntax validation without external tools.

Shared by:
  - scripts/learn.py       (validate pass 2 — content syntax)
  - scripts/checksyntax.py (generation-stage check)

Returns list of (block_index, message) tuples; empty list = OK.
"""

import re

DIAGRAM_TYPES = [
    'graph',
    'flowchart',
    'sequence',
    'state',
    'class',
    'er',
    'gantt',
    'pie',
    'git',
    'mindmap',
    'timeline',
    'requirement',
    'block',
    'journey',
    'sankey',
    'xychart',
    'quadrant',
    'block-beta',
]


def validate_mermaid(content):
    """Basic mermaid syntax validation without external tools.

    Returns list of (block_num, message) tuples.
    """
    errors = []
    blocks = re.findall(
        r'```mermaid\s*\n(.*?)```',
        content,
        re.DOTALL,
    )

    for idx, block in enumerate(blocks, 1):
        block_stripped = block.strip()
        if not block_stripped:
            errors.append((idx, 'Empty mermaid block'))
            continue

        # Check diagram type declared
        first_line = block_stripped.split('\n')[0].strip().lower()
        has_type = any(first_line.startswith(dt) for dt in DIAGRAM_TYPES)
        if not has_type:
            errors.append(
                (idx, f'Missing diagram type keyword (first line: "{first_line[:40]}...")')
            )

        # Check arrow syntax (basic) + style/class color hex validity
        for line in block_stripped.split('\n'):
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith('%%'):
                continue
            if line_stripped.lower().startswith('style ') or line_stripped.lower().startswith(
                'class '
            ):
                all_colors = re.findall(r'#[0-9a-zA-Z]{2,8}', line_stripped)
                for color in all_colors:
                    hex_part = color[1:]
                    if len(hex_part) not in (3, 4, 6, 8):
                        errors.append((idx, f'Invalid hex color length: {color}'))
                    elif not all(c in '0123456789abcdefABCDEF' for c in hex_part):
                        errors.append(
                            (idx, f'Invalid hex color: {color} (non-hex characters)')
                        )

        # Check subgraph/end pairing — only flowchart/graph families use
        # `subgraph ... end` blocks. Other types (sequenceDiagram alt/end,
        # gantt, mindmap...) have their own block keywords and must not be
        # counted here (false-positive source).
        diagram_kw = first_line.split()[0].rstrip(';') if first_line.split() else ''
        if diagram_kw in ('flowchart', 'graph'):
            subgraph_count = len(re.findall(r'^\s*subgraph\b', block_stripped, re.MULTILINE))
            end_count = len(
                re.findall(
                    r'^\s*(?:end\b|endif\b|endwhile\b|endswitch\b)',
                    block_stripped,
                    re.MULTILINE,
                )
            )
            if subgraph_count != end_count:
                errors.append(
                    (
                        idx,
                        f'subgraph/end mismatch: {subgraph_count} subgraph(s), {end_count} end(s)',
                    )
                )

    return errors


# ---------------------------------------------------------------------------
# Safe-mode lint (advisory): patterns that PARSE in some mermaid versions but
# are known render-failure sources. Codified from a 32-diagram repair session.
# These are warnings only — they never affect validate exit codes.

CJK_RE = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')

RISKY_LABEL_RE = re.compile(r'[(){}|<>@]|-->')

SHAPE_PREFIX_OK = re.compile(r'^\s*[\(\[\{>]')  # A[(db)], A{x}, A{{x}}, A>shape]


def _mermaid_blocks(content):
    """Yield (block_index, first_line_number, block_text) for ```mermaid blocks."""
    for i, m in enumerate(re.finditer(r'```mermaid\s*\n(.*?)```', content, re.DOTALL), 1):
        line_start = content.count('\n', 0, m.start(1)) + 1
        yield i, line_start, m.group(1)


def _label_issues(label):
    """Human-readable reasons a node/edge label should be quoted."""
    reasons = []
    if RISKY_LABEL_RE.search(label):
        reasons.append('risky chars (){}|<>@')
    if CJK_RE.search(label):
        reasons.append('CJK text')
    return reasons


def safe_mode_errors(content):
    """Advisory lint: risky-but-parseable mermaid patterns.

    Returns list of (block_idx, line_no, message).
    """
    issues = []
    for idx, start_line, block in _mermaid_blocks(content):
        for off, raw in enumerate(block.split('\n')):
            ln = start_line + off
            line = raw.rstrip()

            # + chains: `A + B + C -->` is invalid syntax; use `&`
            if re.match(r'^\s*\w+(\s*\+\s*\w+)+\s*-->', line):
                issues.append((idx, ln, "node chain with '+' is invalid — use '&' (e.g. A & B & C --> X)"))
                continue

            # subgraph titles: unquoted title with parens/CJK/risky chars
            sm = re.match(r'^\s*subgraph\s+(.*)$', line)
            if sm:
                rest = sm.group(1)
                # strip optional id["title"] / id(title) quoted forms
                bare = re.sub(r'\w+\s*\[.*\]\s*$', '', rest)
                bare = re.sub(r'\w+\s*"[^"]*"\s*$', '', bare)
                if bare and (RISKY_LABEL_RE.search(bare) or CJK_RE.search(bare)):
                    issues.append(
                        (idx, ln, 'quote subgraph title — subgraph id["Title here"]')
                    )

            # node labels: A[label] where label is unquoted and risky
            for nm in re.finditer(r'\b[A-Za-z_]\w*\[([^\]]*)\]', line):
                label = nm.group(1)
                if SHAPE_PREFIX_OK.match(label) or label.startswith('"'):
                    continue
                if '"' in label:
                    # nested quotes inside unquoted-ish label
                    issues.append(
                        (idx, ln, 'nested double quote in label — use #quot; entity')
                    )
                    continue
                reasons = _label_issues(label)
                if reasons:
                    issues.append(
                        (idx, ln, f'unquoted node label {label!r} ({", ".join(reasons)}) — quote it: X["{label}"]')
                    )

            # edge labels via pipes: -->|label|
            for em in re.finditer(r'\|\s*([^|\n]*?)\s*\|', line):
                label = em.group(1)
                if label.startswith('"') and label.endswith('"') and len(label) >= 2:
                    inner = label[1:-1]
                    if '"' in inner:
                        issues.append((idx, ln, 'nested double quote in edge label — use #quot;'))
                elif '"' in label:
                    issues.append((idx, ln, 'nested double quote in edge label — use #quot;'))
                elif RISKY_LABEL_RE.search(label) or CJK_RE.search(label):
                    issues.append(
                        (idx, ln, f'unquoted edge label {label!r} — quote it: |"{label}"|')
                    )

            # edge labels via -- text --> form
            for dm in re.finditer(r'--\s+(.+?)\s+-->', line):
                label = dm.group(1)
                if not (label.startswith('"') and label.endswith('"')) and (
                    RISKY_LABEL_RE.search(label) or CJK_RE.search(label) or '"' in label
                ):
                    issues.append(
                        (idx, ln, f'edge label {label!r} needs quoting or #quot;')
                    )
    return issues


if __name__ == '__main__':
    import sys

    content = sys.stdin.read() if not sys.argv[1:] else open(sys.argv[1]).read()
    errs = validate_mermaid(content)
    if errs:
        for idx, msg in errs:
            print(f'block {idx}: {msg}')
        sys.exit(1)
    print('mermaid: OK')