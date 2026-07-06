#!/usr/bin/env python3
"""PDF builder with zero-dep fallback + optional weasyprint.

Builds PDF from Learn Something subject directory or markdown file.
Backend priority: weasyprint (CSS-styled) → pandoc → stdlib-only text PDF.

Usage:
  pdf.py build <subject-dir> <output> [--title TITLE] [--author AUTHOR]
  pdf.py from-md <markdown-file> <output> [--title TITLE] [--author AUTHOR]
"""

import argparse
import os
import re
import subprocess
import sys
import textwrap
import zlib
from datetime import datetime
from html import escape as html_escape
from xml.sax.saxutils import escape

HAS_WEASYPRINT = False
HAS_YAML = False
HAS_PANDOC = False

try:
    import weasyprint

    HAS_WEASYPRINT = True
except ImportError:
    pass

try:
    import yaml

    HAS_YAML = True
except ImportError:
    pass

try:
    subprocess.run(['pandoc', '--version'], capture_output=True, check=True)
    HAS_PANDOC = True
except (FileNotFoundError, subprocess.CalledProcessError):
    pass


def _format_title(name):
    name = re.sub(r'[-_]', ' ', name)
    return name.strip().title()


def _inline_md(text):
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img alt="\1" src="\2"/>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    text = re.sub(r'`([^`]+)`', lambda m: f'<code>{escape(m.group(1))}</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    return text


def _md_to_plain_lines(md_text):
    lines = md_text.split('\n')
    result = []
    in_code = False

    for line in lines:
        s = line.strip()

        if s.startswith('```'):
            if in_code:
                result.append('')
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            result.append(f'  {s}')
            continue

        if not s:
            result.append('')
            continue
        if s == '---':
            result.append('────────────────────────────────────')
            continue

        if s.startswith('##### '):
            result.append(f'  {s[6:]}')
            continue
        if s.startswith('#### '):
            result.append(f'  {s[5:]}')
            continue
        if s.startswith('### '):
            result.append('')
            result.append(s[4:])
            result.append('')
            continue
        if s.startswith('## '):
            result.append('')
            result.append(s[3:])
            result.append('')
            continue
        if s.startswith('# '):
            result.append('')
            result.append(s[2:].upper())
            result.append('')
            continue

        if s.startswith('> '):
            result.append(f'> {s[2:]}')
            continue

        if s.startswith('- '):
            result.append(f'  * {s[2:]}')
            continue

        ol_match = re.match(r'^\d+\.\s+(.*)', s)
        if ol_match:
            result.append(f'  {s}')
            continue

        if '|' in s:
            cells = [c.strip() for c in s.split('|') if c.strip()]
            if cells:
                result.append('  | ' + ' | '.join(cells) + ' |')
            continue

        result.append(s)

    return result


def collect_subject_md(subject_dir):
    modules_dir = os.path.join(subject_dir, 'modules')
    if not os.path.isdir(modules_dir):
        print(f'Missing: {modules_dir}', file=sys.stderr)
        sys.exit(1)

    parts = []
    mod_names = sorted(
        d for d in os.listdir(modules_dir) if os.path.isdir(os.path.join(modules_dir, d))
    )

    for i, name in enumerate(mod_names):
        mod_path = os.path.join(modules_dir, name)
        lesson_path = os.path.join(mod_path, 'lesson.md')
        quiz_path = os.path.join(mod_path, 'quiz.yaml')

        if i > 0:
            parts.append('\n---\n')

        if os.path.isfile(lesson_path):
            with open(lesson_path, 'r', encoding='utf-8') as f:
                parts.append(f.read().rstrip())

        if os.path.isfile(quiz_path) and HAS_YAML:
            with open(quiz_path, 'r', encoding='utf-8') as f:
                try:
                    questions = yaml.safe_load(f)
                    if questions:
                        parts.append(f'\n## Quiz: {name}\n')
                    for q in questions:
                        ans = q.get('answer', '')
                        parts.append(f'\n### {q.get("question", "")}\n')
                        for k, v in q.get('options', {}).items():
                            mark = '[✓]' if k == ans else '[ ]'
                            parts.append(f'{mark} {k}: {v}\n')
                        parts.append(f'\n**Answer:** {ans}\n')
                        parts.append(f'{q.get("explanation", "")}\n')
                except Exception:
                    parts.append(f'\n## Quiz: {name}\n\n(quiz parse error)\n')
        elif os.path.isfile(quiz_path):
            parts.append(f'\n## Quiz: {name}\n\n(install yaml library to include quizzes)\n')

    return '\n'.join(parts)


# ── Zero-dep PDF generator ─────────────────────────────────────


def _sanitize_latin1(s):
    """Replace non-latin-1 chars with ASCII equivalents."""
    replacements = {
        '\u2713': '[x]',
        '\u2717': '[ ]',
        '\u2022': '*',
        '\u2013': '-',
        '\u2014': '--',
        '\u2018': "'",
        '\u2019': "'",
        '\u201c': '"',
        '\u201d': '"',
        '\u2026': '...',
        '\u2192': '->',
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s.encode('latin-1', errors='replace').decode('latin-1')


def _escape_pdf(s):
    s = _sanitize_latin1(s)
    s = s.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    s = s.replace('\r', '').replace('\n', '\\n')
    return s


class RawPDF:
    """Minimal PDF generator using stdlib only. Letter size, Helvetica."""

    FONT_SIZE = 11
    CODE_SIZE = 9
    LINE_H = 14
    CODE_LINE_H = 11
    MARGIN_L = 60
    MARGIN_R = 60
    MARGIN_T = 60
    MARGIN_B = 60
    PAGE_W = 612
    PAGE_H = 792
    PAGE_WRITE = PAGE_W - MARGIN_L - MARGIN_R
    CHARS_PER_LINE = 72

    def __init__(self, title='Document', author='Learn Something'):
        self.title = title
        self.author = author
        self.objs = []
        self.pages = []
        self.font_helv = None
        self.font_bold = None
        self.font_cour = None

    def _obj(self, body):
        n = len(self.objs) + 1
        self.objs.append(f'{n} 0 obj\n{body}\nendobj')
        return n

    def _stream(self, content):
        data = content.encode('latin-1')
        comp = zlib.compress(data)
        return self._obj(
            f'<< /Length {len(comp)} /Filter /FlateDecode >>\nstream\n'
            f'{comp.decode("latin-1")}\nendstream'
        )

    def _font_def(self, basefont):
        return f'<< /Type /Font /Subtype /Type1 /BaseFont /{basefont} >>'

    def _render_page(self, items):
        lines = []
        lines.append('BT')
        for it in items:
            kind = it[0]
            if kind == 'text':
                _, x, y, txt, font = it
                lines.append(f'/F{font} {self.FONT_SIZE} Tf')
                lines.append(f'1 0 0 1 {x:.0f} {y:.0f} Tm')
                lines.append(f'({_escape_pdf(txt)}) Tj')
            elif kind == 'code':
                _, x, y, txt = it
                lines.append(f'/F3 {self.CODE_SIZE} Tf')
                lines.append(f'1 0 0 1 {x:.0f} {y:.0f} Tm')
                lines.append(f'({_escape_pdf(txt)}) Tj')
            elif kind == 'title':
                _, x, y, txt = it
                lines.append('/F2 20 Tf')
                lines.append(f'1 0 0 1 {x:.0f} {y:.0f} Tm')
                lines.append(f'({_escape_pdf(txt)}) Tj')
        lines.append('ET')

        content_id = self._stream('\n'.join(lines))

        font_refs = []
        if self.font_helv:
            font_refs.append(f'/F1 {self.font_helv} 0 R')
        if self.font_bold:
            font_refs.append(f'/F2 {self.font_bold} 0 R')
        if self.font_cour:
            font_refs.append(f'/F3 {self.font_cour} 0 R')

        page_id = self._obj(
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.PAGE_W} {self.PAGE_H}]'
            f' /Contents {content_id} 0 R'
            f' /Resources << /Font << {" ".join(font_refs)} >> >> >>'
        )
        self.pages.append(page_id)

    def build(self, text_lines):
        fonts = {
            'Helv': self._font_def('Helvetica'),
            'Bold': self._font_def('Helvetica-Bold'),
            'Cour': self._font_def('Courier'),
        }
        self.font_helv = self._obj(fonts['Helv'])
        self.font_bold = self._obj(fonts['Bold'])
        self.font_cour = self._obj(fonts['Cour'])

        self._add_cover_page()
        self._add_content_pages(text_lines)

        kids = ' '.join(f'{p} 0 R' for p in self.pages)
        pages_id = self._obj(f'<< /Type /Pages /Kids [{kids}] /Count {len(self.pages)} >>')

        self._obj(
            f'<< /Title ({_escape_pdf(self.title)})'
            f' /Author ({_escape_pdf(self.author)})'
            f' /Producer (Learn Something)'
            f' /CreationDate ({datetime.now().strftime("%Y%m%d%H%M%S")}) >>'
        )

        self._obj(f'<< /Type /Catalog /Pages {pages_id} 0 R /Lang (en-US) >>')

        return '%PDF-1.4\n' + '\n'.join(self.objs) + '\n%%EOF\n'

    def _add_cover_page(self):
        title = self.title[:60]
        author = self.author[:60]
        x = self.MARGIN_L
        y = self.PAGE_H // 2 + 40
        self._render_page(
            [
                ('title', x, y, title),
                ('text', x, y - 30, f'by {author}', 1),
            ]
        )

    def _add_content_pages(self, text_lines):
        x = self.MARGIN_L
        y = self.PAGE_H - self.MARGIN_T
        max_y = self.MARGIN_B
        page_items = []

        def flush():
            nonlocal page_items, y
            if page_items:
                self._render_page(page_items)
                page_items = []
                y = self.PAGE_H - self.MARGIN_T

        for line in text_lines:
            is_heading = line and (line.isupper() and len(line) > 2) or (line.startswith('## '))
            is_sep = line.startswith('──')
            is_code = line.startswith('  ')
            is_empty = not line.strip()

            if is_sep:
                continue

            if is_empty:
                y -= self.LINE_H // 2
                if y < max_y:
                    flush()
                continue

            for wrapped in (
                textwrap.wrap(line, width=self.CHARS_PER_LINE) if not is_code else [line]
            ):
                if y < max_y:
                    flush()

                wrapped = wrapped.rstrip()
                if is_heading:
                    page_items.append(('text', x, y, wrapped, 2))
                elif is_code:
                    page_items.append(('code', x + 10, y, wrapped))
                else:
                    page_items.append(('text', x, y, wrapped, 1))
                y -= self.LINE_H if not is_code else self.CODE_LINE_H

        if page_items:
            self._render_page(page_items)


def _generate_raw_pdf(md_text, output_path, title='Document', author='Learn Something'):
    plain_lines = _md_to_plain_lines(md_text)
    pdf = RawPDF(title=title, author=author)
    data = pdf.build(plain_lines)
    with open(output_path, 'wb') as f:
        f.write(data.encode('latin-1'))


def _html_to_pdf_via_weasyprint(html, output_path):
    doc = weasyprint.HTML(string=html).render()
    doc.write_pdf(output_path)


def _html_to_pdf_via_pandoc(html, output_path):
    p = subprocess.run(
        ['pandoc', '-f', 'html', '-o', output_path],
        input=html,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if p.returncode != 0:
        raise RuntimeError(f'pandoc failed: {p.stderr}')


def _make_html(md_text, title='Document', author='Learn Something'):
    lines = []
    lines.append('<!DOCTYPE html>')
    lines.append('<html><head>')
    lines.append(f'<meta charset="utf-8"><title>{html_escape(title)}</title>')
    lines.append(f'<meta name="author" content="{html_escape(author)}">')
    lines.append('<style>')
    lines.append(
        'body { font-family: Georgia, serif; max-width: 38em; margin: 2em auto; '
        'line-height: 1.7; color: #333; padding: 0 1em; }'
    )
    lines.append('h1, h2, h3 { font-family: Helvetica, Arial, sans-serif; color: #111; }')
    lines.append('h1 { font-size: 1.6em; border-bottom: 2px solid #0366d6; }')
    lines.append('h2 { font-size: 1.3em; border-bottom: 1px solid #ddd; }')
    lines.append(
        'pre { background: #f5f5f5; padding: 1em; border-radius: 4px; '
        'font-size: 0.85em; overflow-x: auto; }'
    )
    lines.append('code { font-family: "SF Mono", Consolas, monospace; }')
    lines.append('p code { background: #f0f0f0; padding: 0.15em 0.3em; border-radius: 3px; }')
    lines.append('table { border-collapse: collapse; width: 100%; margin: 1em 0; }')
    lines.append('th, td { border: 1px solid #ddd; padding: 0.4em 0.6em; text-align: left; }')
    lines.append('th { background: #f0f0f0; }')
    lines.append(
        'blockquote { border-left: 4px solid #0366d6; margin: 1em 0; '
        'padding: 0.5em 1em; color: #555; background: #f8f9fa; }'
    )
    lines.append('</style>')
    lines.append('</head><body>')

    in_code = False
    for md_line in md_text.split('\n'):
        s = md_line.strip()
        if s.startswith('```'):
            if in_code:
                lines.append('</code></pre>')
                in_code = False
            else:
                lang = s[3:].strip()
                lines.append(f'<pre><code class="language-{lang}">')
                in_code = True
            continue
        if in_code:
            lines.append(html_escape(md_line))
            continue
        if not s:
            lines.append('<p>&nbsp;</p>')
            continue
        if s == '---':
            lines.append('<hr/>')
            continue
        if s.startswith('##### '):
            lines.append(f'<h5>{_inline_md(s[6:])}</h5>')
            continue
        if s.startswith('#### '):
            lines.append(f'<h4>{_inline_md(s[5:])}</h4>')
            continue
        if s.startswith('### '):
            lines.append(f'<h3>{_inline_md(s[4:])}</h3>')
            continue
        if s.startswith('## '):
            lines.append(f'<h2>{_inline_md(s[3:])}</h2>')
            continue
        if s.startswith('# '):
            lines.append(f'<h1>{_inline_md(s[2:])}</h1>')
            continue
        if s.startswith('> '):
            lines.append(f'<blockquote><p>{_inline_md(s[2:])}</p></blockquote>')
            continue
        if s.startswith('- '):
            lines.append(f'<li>{_inline_md(s[2:])}</li>')
            continue
        ol_match = re.match(r'^\d+\.\s+(.*)', s)
        if ol_match:
            lines.append(f'<li>{_inline_md(ol_match.group(1))}</li>')
            continue
        if '|' in s:
            cells = [html_escape(c.strip()) for c in s.split('|') if c.strip()]
            if cells:
                lines.append(f'<tr>{"".join(f"<td>{c}</td>" for c in cells)}</tr>')
            continue
        lines.append(f'<p>{_inline_md(s)}</p>')

    if in_code:
        lines.append('</code></pre>')

    lines.append('</body></html>')
    return '\n'.join(lines)


def generate_pdf(md_text, output_path, title='Document', author='Learn Something', engine='auto'):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)

    if engine == 'auto':
        if HAS_WEASYPRINT:
            engine = 'weasyprint'
        elif HAS_PANDOC:
            engine = 'pandoc'
        else:
            engine = 'raw'

    if engine == 'weasyprint' and HAS_WEASYPRINT:
        html = _make_html(md_text, title, author)
        print('Rendering with weasyprint...', file=sys.stderr)
        _html_to_pdf_via_weasyprint(html, output_path)
        print(f'PDF (weasyprint): {output_path}', file=sys.stderr)
        return

    if engine == 'pandoc' and HAS_PANDOC:
        html = _make_html(md_text, title, author)
        print('Rendering with pandoc...', file=sys.stderr)
        _html_to_pdf_via_pandoc(html, output_path)
        print(f'PDF (pandoc): {output_path}', file=sys.stderr)
        return

    print('Rendering with stdlib (text-only PDF)...', file=sys.stderr)
    _generate_raw_pdf(md_text, output_path, title, author)
    print(f'PDF (stdlib): {output_path}', file=sys.stderr)


# ── CLI ────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description='PDF builder for Learn Something')
    sub = parser.add_subparsers(dest='command')

    p_build = sub.add_parser('build', help='Build PDF from subject directory')
    p_build.add_argument('subject_dir')
    p_build.add_argument('output')
    p_build.add_argument('--title', default=None)
    p_build.add_argument('--author', default='Learn Something')
    p_build.add_argument(
        '--engine',
        default='auto',
        choices=['auto', 'weasyprint', 'pandoc', 'raw'],
        help='PDF engine: auto (default), weasyprint, pandoc, raw (stdlib)',
    )

    p_md = sub.add_parser('from-md', help='Build PDF from markdown file')
    p_md.add_argument('markdown_file')
    p_md.add_argument('output')
    p_md.add_argument('--title', default=None)
    p_md.add_argument('--author', default='Learn Something')
    p_md.add_argument(
        '--engine',
        default='auto',
        choices=['auto', 'weasyprint', 'pandoc', 'raw'],
        help='PDF engine: auto (default), weasyprint, pandoc, raw (stdlib)',
    )

    args = parser.parse_args()

    if args.command not in ('build', 'from-md'):
        parser.print_help()
        sys.exit(1)

    if args.command == 'build':
        subject_dir = args.subject_dir
        if not os.path.isdir(subject_dir):
            print(f'Subject directory not found: {subject_dir}', file=sys.stderr)
            sys.exit(1)
        title = args.title or _format_title(os.path.basename(os.path.normpath(subject_dir)))
        author = args.author
        md_text = collect_subject_md(subject_dir)
        book_md = os.path.join(subject_dir, 'book.md')
        with open(book_md, 'w', encoding='utf-8') as f:
            f.write(md_text)
        print(f'Intermediate markdown: {book_md}')
    else:
        md_file = args.markdown_file
        if not os.path.isfile(md_file):
            print(f'Markdown file not found: {md_file}', file=sys.stderr)
            sys.exit(1)
        title = args.title or _format_title(os.path.splitext(os.path.basename(md_file))[0])
        author = args.author
        with open(md_file, 'r', encoding='utf-8') as f:
            md_text = f.read()

    output = args.output
    generate_pdf(md_text, output, title, author, engine=args.engine)
    size_kb = os.path.getsize(output) / 1024
    print(f'PDF: {output} ({size_kb:.1f} KB)')


if __name__ == '__main__':
    main()
