"""Generation-stage syntax check for lesson.md files.

Checks, per lesson:
  - markdown fence balance (unclosed ``` blocks)
  - mermaid blocks via mermaidcheck.validate_mermaid
  - code blocks via available interpreters (python3 -m py_compile,
    node --check, sh -n) with structural fallback
  - optional mermaid render smoke test (--render api|local) reusing
    render_diagrams.py

Exit 0 = clean (or only warnings). Exit 1 = hard syntax errors found.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import mermaidcheck


def _check_python(code):
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as f:
        f.write(code)
        tmp = f.name
    try:
        r = subprocess.run(
            [sys.executable, '-m', 'py_compile', tmp],
            capture_output=True,
            text=True,
        )
        return r.returncode, r.stderr.strip()
    finally:
        Path(tmp).unlink(missing_ok=True)


def _check_node(code):
    if not shutil.which('node'):
        return None, None  # interpreter unavailable → structural fallback
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(code)
        tmp = f.name
    try:
        r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
        return r.returncode, r.stderr.strip()
    finally:
        Path(tmp).unlink(missing_ok=True)


def _check_sh(code):
    exe = 'bash' if shutil.which('bash') else 'sh'
    r = subprocess.run([exe, '-n'], input=code, capture_output=True, text=True)
    return r.returncode, r.stderr.strip()


def _check_code_block(label, code):
    """Returns (errors, warnings) for one fenced code block."""
    lang = label.strip().split()[0].lower() if label.strip() else ''
    errs, warns = [], []
    if not ''.join(code.split()):
        errs.append('empty code block')
        return errs, warns

    if lang in ('python', 'py'):
        rc, msg = _check_python(code)
        if rc is not None and rc != 0:
            errs.append(f'python syntax error: {msg.splitlines()[-1] if msg else "compile failed"}')
        return errs, warns
    if lang in ('javascript', 'js', 'node'):
        rc, msg = _check_node(code)
        if rc is not None and rc != 0:
            first = msg.splitlines()[0] if msg else 'node --check failed'
            errs.append(f'javascript syntax error: {first}')
        elif rc is None:
            warns.append('node not installed — structural check only')
        return errs, warns
    if lang in ('bash', 'sh', 'shell', 'zsh'):
        rc, msg = _check_sh(code)
        if rc != 0:
            errs.append(f'shell syntax error: {msg.strip()}')
        return errs, warns
    # Unknown language: structural only
    return errs, warns


def check_lesson(text, render_mode='off', lesson_path=None):
    """Scan one lesson's text. Returns (hard_errors, warnings) lists of strings."""
    hard, warns = [], []

    # ── fence balance ──
    fence_lines = [i for i, ln in enumerate(text.split('\n')) if ln.startswith('```')]
    if len(fence_lines) % 2 != 0:
        hard.append(f'unbalanced code fences ({len(fence_lines)} fence lines)')

    # ── per-block scan ──
    blocks = text.split('```')
    # blocks[0] = prose before first fence; then alternating code/prose
    for i in range(1, len(blocks), 2):
        block = blocks[i]
        first_nl = block.find('\n')
        label = block[:first_nl] if first_nl != -1 else block
        code = block[first_nl + 1:] if first_nl != -1 else ''
        block_no = (i + 1) // 2

        if label.strip().lower().startswith('mermaid'):
            for bidx, msg in mermaidcheck.validate_mermaid(f'```mermaid\n{code}```'):
                hard.append(f'mermaid block {block_no}: {msg}')
        else:
            errs, ws = _check_code_block(label, code)
            for e in errs:
                hard.append(f'code block {block_no} ({label.strip() or "?"}): {e}')
            warns.extend(ws)

    # ── optional render smoke test ──
    if render_mode != 'off' and lesson_path:
        try:
            from render_diagrams import render_lesson_diagrams

            count = render_lesson_diagrams(str(lesson_path), mode=render_mode)
            warns.append(f'rendered {count} mermaid diagram(s) ({render_mode})')
        except Exception as e:
            hard.append(f'render smoke test failed: {e}')

    return hard, warns


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    render_mode = 'off'
    if '--render' in argv:
        i = argv.index('--render')
        if i + 1 < len(argv):
            render_mode = argv[i + 1]
    if not args:
        print('usage: checksyntax.py lesson.md [...] [--render api|local|off]', file=sys.stderr)
        return 2

    any_hard = False
    for p in args:
        path = Path(p)
        if not path.exists():
            print(f'{path}: not found', file=sys.stderr)
            any_hard = True
            continue
        hard, warns = check_lesson(path.read_text(encoding='utf-8', errors='replace'),
                                   render_mode, lesson_path=path)
        for w in warns:
            print(f'  WARN {path}: {w}')
        if hard:
            any_hard = True
            for h in hard:
                print(f'{path}: {h}')
        else:
            print(f'{path}: OK')
    return 1 if any_hard else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))