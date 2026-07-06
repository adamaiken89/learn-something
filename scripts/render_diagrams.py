"""Render Mermaid diagram blocks in lesson.md to PNG images.

Scans lesson.md for ```mermaid fenced code blocks, renders each to a 2x PNG
via mmdc CLI or mermaid.ink API, stores original .mmd source alongside the PNG,
and replaces the fenced block with ![diagram](diagrams/...) in the lesson text.

Usage:
  from render_diagrams import render_lesson_diagrams
  render_lesson_diagrams('/path/to/lesson.md', mode='api', scale=2)

Or standalone:
  python render_diagrams.py lesson.md [--mode api|local] [--scale 2]
"""

import base64
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

DIAGRAM_DIR = 'diagrams'
"""Subdirectory under the module to store diagram PNG + source files."""


def _mmdc_available():
    """Check if mmdc CLI is installed."""
    try:
        subprocess.run(
            ['mmdc', '--version'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _render_local(source, out_path, scale=2):
    """Render mermaid source to PNG via mmdc CLI.

    Args:
        source: Mermaid diagram source text
        out_path: Path for output PNG
        scale: Scale factor (2 = 300dpi for e-ink)

    Returns:
        True on success, False on failure
    """
    tmp_mmd = out_path.with_suffix('.mmd.tmp')
    try:
        tmp_mmd.write_text(source, encoding='utf-8')
        subprocess.run(
            ['mmdc', '-i', str(tmp_mmd), '-o', str(out_path), '-s', str(scale), '-q'],
            capture_output=True,
            timeout=30,
            check=True,
        )
        return out_path.exists()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False
    finally:
        if tmp_mmd.exists():
            tmp_mmd.unlink()


def _render_api(source, scale=2):
    """Render mermaid source to PNG via mermaid.ink API.

    Args:
        source: Mermaid diagram source text
        scale: Scale factor

    Returns:
        PNG bytes on success, None on failure
    """
    try:
        encoded = base64.urlsafe_b64encode(source.encode('utf-8')).decode('ascii')
        url = f'https://mermaid.ink/png/{encoded}?scale={scale}'
        req = urllib.request.Request(url, headers={'User-Agent': 'learn-something/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _find_mermaid_blocks(text):
    """Find all ```mermaid ... ``` blocks in text.

    Returns:
        List of (start_line, end_line, source) tuples (0-indexed lines)
    """
    blocks = []
    lines = text.split('\n')
    in_block = False
    block_start = 0
    source_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('```') and not in_block:
            fence_lang = stripped[3:].strip()
            if fence_lang == 'mermaid':
                in_block = True
                block_start = i
                source_lines = []
        elif stripped.startswith('```') and in_block:
            in_block = False
            source = '\n'.join(source_lines)
            blocks.append((block_start, i, source))
        elif in_block:
            source_lines.append(line)

    return blocks


def render_lesson_diagrams(lesson_path, mode='api', scale=2):
    """Render all ```mermaid blocks in a lesson.md to PNG images.

    For each block:
    1. Write .mmd source to diagrams/diagram_NNN.mmd
    2. Render PNG via chosen mode (local=mmdc CLI, api=mermaid.ink)
    3. Replace fenced block with ![Diagram](diagrams/diagram_NNN.png)

    Args:
        lesson_path: Path to lesson.md file
        mode: 'api' (mermaid.ink, zero deps) or 'local' (mmdc CLI)
        scale: PNG scale factor (2 = 300dpi for e-ink)

    Returns:
        Number of diagrams rendered (0 if none found or all failed)
    """
    lesson_path = Path(lesson_path)
    if not lesson_path.exists():
        print(f'Error: {lesson_path} not found', file=sys.stderr)
        return 0

    text = lesson_path.read_text(encoding='utf-8')
    blocks = _find_mermaid_blocks(text)
    if not blocks:
        return 0

    # Create diagrams directory alongside lesson.md
    diag_dir = lesson_path.parent / DIAGRAM_DIR
    diag_dir.mkdir(parents=True, exist_ok=True)

    # Prefer local if requested and available; fall back to API
    use_local = (mode == 'local') and _mmdc_available()
    if mode == 'local' and not use_local:
        print('  mmdc not available, falling back to mermaid.ink API')
        use_local = False

    rendered = 0

    # Process blocks in reverse order (so line offsets don't shift as we replace)
    for start_line, end_line, source in reversed(blocks):
        idx = rendered  # use processed count as index (reversed, so fine)

        mmd_path = diag_dir / f'diagram_{idx:03d}.mmd'
        png_path = diag_dir / f'diagram_{idx:03d}.png'
        success = False

        if use_local:
            success = _render_local(source, png_path, scale)
            if success:
                # Write .mmd source
                mmd_path.write_text(f'```mermaid\n{source}\n```\n', encoding='utf-8')
        else:
            png_bytes = _render_api(source, scale)
            if png_bytes:
                png_path.write_bytes(png_bytes)
                mmd_path.write_text(f'```mermaid\n{source}\n```\n', encoding='utf-8')
                success = True

        if success:
            # Build replacement: image reference + HTML comment with source path
            rel_path = f'{DIAGRAM_DIR}/diagram_{idx:03d}.png'
            replacement = (
                f'![Diagram]({rel_path})\n<!-- Source: {DIAGRAM_DIR}/diagram_{idx:03d}.mmd -->'
            )

            # Replace in text (lines are 0-indexed)
            lines = text.split('\n')
            # Include the ```mermaid opening and closing fences
            lines = lines[:start_line] + [replacement] + lines[end_line + 1 :]
            text = '\n'.join(lines)
            rendered += 1

    if rendered:
        lesson_path.write_text(text, encoding='utf-8')

    return rendered


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Render mermaid diagrams in lesson.md to PNG')
    parser.add_argument('lesson_path', help='Path to lesson.md file')
    parser.add_argument(
        '--mode',
        choices=['api', 'local'],
        default='api',
        help='Rendering mode: api=mermaid.ink (default), local=mmdc CLI',
    )
    parser.add_argument(
        '--scale', type=int, default=2, help='PNG scale factor (default 2 = 300dpi)'
    )
    args = parser.parse_args()

    count = render_lesson_diagrams(args.lesson_path, args.mode, args.scale)
    if count:
        print(f'Rendered {count} diagram(s) to PNG')
    else:
        print('No mermaid blocks found or all failed')
