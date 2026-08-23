"""Mermaid syntax validation via mermaid-cli (mmdc) — single source of truth.

Fail-fast design: mmdc is a hard prerequisite for content validation.
No regex fallback — basic pattern checks were removed (false positives,
false negatives); the real parser/renderer is trusted.

Shared by:
  - scripts/learn.py       (validate pass 2 — content syntax; mindmap post-write)
  - scripts/checksyntax.py (generation-stage check)
  - scripts/enrich.py      (post-enrichment write guard)

Public API:
  - resolve_mmdc(offline=False)   -> argv prefix or None
  - validate_block_mmdc(src, ...) -> [messages]        (one diagram source)
  - validate_blocks_mmdc(md, ...) -> [(block_idx, msg)] (whole markdown doc;
    block_idx 0 = environment error, e.g. mmdc unavailable)

Also hosts safe_mode_errors(): advisory lint for risky-but-parseable
patterns (warnings only, never affects exit codes).
"""

import os
import re
import shutil
import subprocess
import tempfile

MMDC_INSTALL_HINT = (
    'mmdc not available — install: npm install -g @mermaid-js/mermaid-cli '
    '(or allow npx network access)'
)


# ---------------------------------------------------------------------------
# Tool resolution


def _check_mmdc():
    """True if the global mmdc binary works."""
    try:
        result = subprocess.run(
            ['mmdc', '--version'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def resolve_mmdc(offline=False):
    """Return (argv_prefix or None, via_network).

    Resolution order: global `mmdc` → `npx -y @mermaid-js/mermaid-cli`
    (skipped under offline). Callers must treat None as a hard error —
    there is no fallback validator.
    """
    if _check_mmdc():
        return ['mmdc'], False
    if not offline and shutil.which('npx'):
        return ['npx', '-y', '@mermaid-js/mermaid-cli'], True
    return None, False


# ---------------------------------------------------------------------------
# Validation


def extract_mermaid_blocks(content):
    """Yield (block_index, first_line_number, block_text) for ```mermaid blocks."""
    for i, m in enumerate(re.finditer(r'```mermaid\s*\n(.*?)```', content, re.DOTALL), 1):
        line_start = content.count('\n', 0, m.start(1)) + 1
        yield i, line_start, m.group(1)


def validate_block_mmdc(source, cmd=None, offline=False):
    """Validate one mermaid diagram source with mmdc.

    Args:
        source: raw diagram source (no fences)
        cmd: pre-resolved argv prefix (from resolve_mmdc); resolved if None
        offline: skip npx fallback when resolving

    Returns list of messages; empty list = valid.
    A single message equal to MMDC_INSTALL_HINT means the tool was unavailable.
    """
    if cmd is None:
        cmd, _ = resolve_mmdc(offline)
        if cmd is None:
            return [MMDC_INSTALL_HINT]

    if not source.strip():
        return ['Empty mermaid block']

    fd, tmp_path = tempfile.mkstemp(suffix='.mmd')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(source)
        try:
            result = subprocess.run(
                [*cmd, '-i', tmp_path, '-t', 'neutral', '--quiet'],
                capture_output=True,
                text=True,
                timeout=120 if len(cmd) > 1 else 30,
            )
            if result.returncode != 0:
                err_msg = (
                    result.stderr.strip().split('\n')[0] if result.stderr else 'invalid syntax'
                )
                return [err_msg]
            return []
        except subprocess.TimeoutExpired:
            return ['mmdc timed out']
    finally:
        os.unlink(tmp_path)


def validate_blocks_mmdc(content, cmd=None, offline=False):
    """Validate all ```mermaid blocks in a markdown document.

    Returns list of (block_num, message); empty list = all valid.
    block_num 0 + MMDC_INSTALL_HINT = tool unavailable (environment error).
    """
    if cmd is None:
        cmd, _ = resolve_mmdc(offline)
        if cmd is None:
            # Only an error if the document actually contains mermaid blocks
            if any(True for _ in extract_mermaid_blocks(content)):
                return [(0, MMDC_INSTALL_HINT)]
            return []

    errors = []
    for idx, _, block in extract_mermaid_blocks(content):
        for msg in validate_block_mmdc(block, cmd=cmd):
            errors.append((idx, msg))
    return errors


# ---------------------------------------------------------------------------
# Safe-mode lint (advisory): patterns that PARSE in some mermaid versions but
# are known render-failure sources. Codified from a 32-diagram repair session.
# These are warnings only — they never affect validate exit codes.

CJK_RE = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')

RISKY_LABEL_RE = re.compile(r'[(){}|<>@]|-->')

SHAPE_PREFIX_OK = re.compile(r'^\s*[\(\[\{>]')  # A[(db)], A{x}, A{{x}}, A>shape]


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
    for idx, start_line, block in extract_mermaid_blocks(content):
        for off, raw in enumerate(block.split('\n')):
            ln = start_line + off
            line = raw.rstrip()

            # + chains: `A + B + C -->` is invalid syntax; use `&`
            if re.match(r'^\s*\w+(\s*\+\s*\w+)+\s*-->', line):
                issues.append(
                    (idx, ln, "node chain with '+' is invalid — use '&' (e.g. A & B & C --> X)")
                )
                continue

            # subgraph titles: unquoted title with parens/CJK/risky chars
            sm = re.match(r'^\s*subgraph\s+(.*)$', line)
            if sm:
                rest = sm.group(1)
                # strip optional id["title"] / id(title) quoted forms
                bare = re.sub(r'\w+\s*\[.*\]\s*$', '', rest)
                bare = re.sub(r'\w+\s*"[^"]*"\s*$', '', bare)
                if bare and (RISKY_LABEL_RE.search(bare) or CJK_RE.search(bare)):
                    issues.append((idx, ln, 'quote subgraph title — subgraph id["Title here"]'))

            # node labels: A[label] where label is unquoted and risky
            for nm in re.finditer(r'\b[A-Za-z_]\w*\[([^\]]*)\]', line):
                label = nm.group(1)
                if SHAPE_PREFIX_OK.match(label) or label.startswith('"'):
                    continue
                if '"' in label:
                    # nested quotes inside unquoted-ish label
                    issues.append((idx, ln, 'nested double quote in label — use #quot; entity'))
                    continue
                reasons = _label_issues(label)
                if reasons:
                    issues.append(
                        (
                            idx,
                            ln,
                            f'unquoted node label {label!r} ({", ".join(reasons)}) — quote it: X["{label}"]',
                        )
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
                    issues.append((idx, ln, f'edge label {label!r} needs quoting or #quot;'))
    return issues


if __name__ == '__main__':
    import sys

    content = sys.stdin.read() if not sys.argv[1:] else open(sys.argv[1]).read()
    errs = validate_blocks_mmdc(content)
    if errs:
        for idx, msg in errs:
            print(f'block {idx}: {msg}')
        sys.exit(1)
    print('mermaid: OK')
