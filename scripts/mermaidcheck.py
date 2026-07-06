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

        # Check subgraph/end pairing
        subgraph_count = len(re.findall(r'^\s*subgraph\b', block_stripped, re.MULTILINE))
        end_count = len(re.findall(r'^\s*end\b', block_stripped, re.MULTILINE))
        if subgraph_count != end_count:
            errors.append(
                (
                    idx,
                    f'subgraph/end mismatch: {subgraph_count} subgraph(s), {end_count} end(s)',
                )
            )

    return errors


if __name__ == '__main__':
    import sys

    content = sys.stdin.read() if not sys.argv[1:] else open(sys.argv[1]).read()
    errs = validate_mermaid(content)
    if errs:
        for idx, msg in errs:
            print(f'block {idx}: {msg}')
        sys.exit(1)
    print('mermaid: OK')