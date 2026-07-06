#!/usr/bin/env python3
"""EPUB builder with theme support and e-ink adaptations.

Dependencies (optional):
  - markdown + pygments: full GFM tables, code highlighting
  - yaml: quiz inclusion
  Falls back to stdlib-only parser.

Usage:
  epub.py build <subject-dir> <output> [--theme NAME] [--title TITLE] [--author AUTHOR]
  epub.py from-md <markdown-file> <output> [--theme NAME] [--title TITLE] [--author AUTHOR]
  epub.py css [--theme NAME]
  epub.py list-themes
"""

import argparse
import base64
import hashlib
import html.parser
import importlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime
from html import unescape as html_unescape
from xml.sax.saxutils import escape

THEMES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'themes.json')

# ── Optional dependencies ─────────────────────────────────────

HAS_MARKDOWN = False
HAS_PYGMENTS = False
HAS_YAML = False

try:
    import markdown as _md

    HAS_MARKDOWN = True
except ImportError:
    pass

HAS_PYGMENTS = importlib.util.find_spec('pygments') is not None

try:
    import yaml

    HAS_YAML = True
except ImportError:
    pass

# ── Theme loading ──────────────────────────────────────────────


def load_themes():
    if not os.path.isfile(THEMES_FILE):
        print(f'Themes file not found: {THEMES_FILE}', file=sys.stderr)
        sys.exit(1)
    with open(THEMES_FILE, 'r', encoding='utf-8') as f:
        themes = json.load(f)
    return themes


def get_theme(name, themes):
    if name not in themes:
        available = ', '.join(sorted(themes.keys()))
        print(f'Unknown theme: {name}', file=sys.stderr)
        print(f'Available themes: {available}', file=sys.stderr)
        sys.exit(1)
    return themes[name]


def resolve_alpha(color):
    """Convert rgba() and transparent to solid colors for e-ink compatibility."""
    if color == 'transparent':
        return None
    m = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)', color)
    if not m:
        return color
    r, g, b, a = int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4))
    if a >= 0.85:
        return f'#{r:02x}{g:02x}{b:02x}'
    blended_r = int(255 * (1 - a) + r * a)
    blended_g = int(255 * (1 - a) + g * a)
    blended_b = int(255 * (1 - a) + b * a)
    return f'#{blended_r:02x}{blended_g:02x}{blended_b:02x}'


def resolve_alpha_for_bg(color, bg_hex):
    """Blend rgba() against a specific background hex color."""
    if color == 'transparent':
        return None
    m = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)', color)
    if not m:
        return color
    r1, g1, b1 = int(m.group(1)), int(m.group(2)), int(m.group(3))
    a = float(m.group(4))
    if bg_hex == 'transparent':
        bg_hex = '#ffffff'
    bg_hex = bg_hex.lstrip('#')
    r2, g2, b2 = int(bg_hex[0:2], 16), int(bg_hex[2:4], 16), int(bg_hex[4:6], 16)
    blended_r = int(r2 * (1 - a) + r1 * a)
    blended_g = int(g2 * (1 - a) + g1 * a)
    blended_b = int(b2 * (1 - a) + b1 * a)
    return f'#{blended_r:02x}{blended_g:02x}{blended_b:02x}'


def is_dark_theme(bg):
    """Check if a background color is dark (low luminance)."""
    if bg == 'transparent':
        return True
    bg = bg.lstrip('#')
    r, g, b = int(bg[0:2], 16), int(bg[2:4], 16), int(bg[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return luminance < 0.5


DARK_THEMES_WARNING = """\
Warning: {theme} has a dark background. On e-ink displays (Kobo, Kindle),
dark backgrounds appear as reflective gray with lower contrast. Recommended
e-ink themes: sepia, notebook, light, monokai-light, dracula-light.
Use --theme <name> to choose a different theme.
"""

# ── CSS generation ──────────────────────────────────────────────


def make_css(tokens, use_pygments=False):
    """Generate themed CSS from theme tokens.

    E-ink adaptations:
    - rgba() with low opacity → blended with white background
    - transparent bg → solid theme bg
    - Code blocks keep dark background for programming feel
    """
    bg = tokens.get('bg', '#ffffff')
    text = tokens.get('text', '#333333')
    h1 = tokens.get('h1', '#111111')
    h1_underline = tokens.get('h1Underline', '#0366d6')
    h2 = tokens.get('h2', '#222222')
    h2_border = tokens.get('h2Border', '#e0e0e0')
    h3 = tokens.get('h3', '#444444')
    strong = tokens.get('strong', '#111111')
    em = tokens.get('em', '#555555')
    link = tokens.get('link', '#0366d6')
    code_bg = tokens.get('codeBg', '#f0f0f0')
    code_text = tokens.get('codeText', '#d63384')
    pre_bg = tokens.get('preBg', '#1e1e1e')
    bq_border = tokens.get('bqBorder', '#0366d6')
    bq_text = tokens.get('bqText', '#555555')
    bq_bg = tokens.get('bqBg', 'rgba(3, 102, 214, 0.04)')
    table_border = tokens.get('tableBorder', '#e0e0e0')
    th_bg = tokens.get('thBg', '#f0f0f0')
    th_text = tokens.get('thText', '#111111')
    td_text = tokens.get('tdText', '#333333')
    quiz_correct = tokens.get('quizCorrectText', tokens.get('hlString', '#16a34a'))
    td_even_bg = tokens.get('tdEvenBg', 'rgba(240, 240, 240, 0.4)')
    hr_border = tokens.get('hrBorder', '#e0e0e0')
    hl_keyword = tokens.get('hlKeyword', '#f92672')
    hl_builtin = tokens.get('hlBuiltin', '#66d9ef')
    hl_string = tokens.get('hlString', '#e6db74')
    hl_number = tokens.get('hlNumber', '#fd971f')
    hl_comment = tokens.get('hlComment', '#75715e')
    hl_meta = tokens.get('hlMeta', '#a6e22e')
    hl_variable = tokens.get('hlVariable', '#f8f8f2')
    hl_symbol = tokens.get('hlSymbol', '#fd971f')
    hl_tag = tokens.get('hlTag', '#f92672')
    hl_attr = tokens.get('hlAttr', '#a6e22e')

    bq_bg_solid = resolve_alpha_for_bg(bq_bg, bg)
    td_even_bg_solid = resolve_alpha_for_bg(td_even_bg, bg)

    base = f"""/* EPUB theme: {tokens.get('_name', 'custom')} */
@namespace epub "http://www.idpf.org/2007/ops";

body {{
  font-family: Georgia, "Times New Roman", serif;
  line-height: 1.7;
  color: {text};
  background: {bg};
  margin: 1em 2em;
  max-width: 38em;
  word-wrap: break-word;
}}

h1, h2, h3, h4 {{
  font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
  font-weight: 600;
  line-height: 1.3;
  page-break-after: avoid;
}}

h1 {{
  font-size: 1.6em;
  color: {h1};
  border-bottom: 2px solid {h1_underline};
  padding-bottom: 0.3em;
  margin-top: 1.5em;
}}

h2 {{
  font-size: 1.3em;
  color: {h2};
  border-bottom: 1px solid {h2_border};
  padding-bottom: 0.2em;
  margin-top: 1.3em;
}}

h3 {{
  font-size: 1.1em;
  color: {h3};
  margin-top: 1.2em;
}}

h1:first-child {{ margin-top: 0; }}

a {{ color: {link}; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

p {{ margin: 0.6em 0; }}

strong {{ color: {strong}; font-weight: 600; }}
em {{ color: {em}; font-style: italic; }}

blockquote {{
  border-left: 4px solid {bq_border};
  margin: 1em 0;
  padding: 0.5em 1em;
  color: {bq_text};
  background: {bq_bg_solid};
}}

blockquote p {{ margin: 0.3em 0; }}

pre {{
  background: {pre_bg};
  padding: 1em;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 0.85em;
  line-height: 1.45;
  page-break-inside: avoid;
}}

code {{
  font-family: "SF Mono", "Fira Code", "Cascadia Code", "Liberation Mono", Consolas, monospace;
  font-size: 0.9em;
}}

p code, li code, td code {{
  background: {code_bg};
  padding: 0.15em 0.3em;
  border-radius: 3px;
  color: {code_text};
}}

pre code {{
  background: none;
  padding: 0;
  color: {hl_variable};
  font-size: 1em;
}}

table {{
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
  font-size: 0.95em;
}}

th, td {{
  border: 1px solid {table_border};
  padding: 0.5em 0.75em;
  text-align: left;
  vertical-align: top;
}}

th {{
  background: {th_bg};
  color: {th_text};
  font-weight: 600;
}}

td {{
  color: {td_text};
}}

tr:nth-child(even) td {{
  background: {td_even_bg_solid};
}}

ul, ol {{ margin: 0.5em 0; padding-left: 1.5em; }}
li {{ margin: 0.3em 0; }}

hr {{
  border: none;
  border-top: 1px solid {hr_border};
  margin: 1.5em 0;
}}

img {{
  max-width: 100%;
  height: auto;
  margin: 1em 0;
}}

.cover {{
  text-align: center;
  padding-top: 30vh;
}}

.cover h1 {{
  border: none;
  font-size: 2em;
  margin: 0;
}}

.cover p {{
  color: #888;
  font-size: 1.1em;
}}

@page {{ margin: 2em; }}
h1, h2, h3, h4 {{ page-break-after: avoid; }}
pre, blockquote, table {{ page-break-inside: avoid; }}

.quiz-question {{
  font-weight: 600;
  color: {strong};
  margin: 1.2em 0 0.4em 0;
}}

.quiz-option {{
  margin: 0.2em 0;
  padding-left: 1em;
  color: {text};
}}

.quiz-answer {{
  margin-top: 0.5em;
  font-size: 0.9em;
  color: {quiz_correct};
}}

.quiz-explanation {{
  margin: 0.3em 0 0 1em;
  font-style: italic;
  color: {hl_comment};
  font-size: 0.92em;
}}

.quiz-difficulty {{
  font-size: 0.8em;
  color: {hl_number};
  letter-spacing: 0.1em;
  margin: 0 0 0.2em 0;
}}
"""
    if use_pygments:
        try:
            hl_css = f"""
.codehilite {{ background: none !important; }}
.codehilite .k, .codehilite .kc, .codehilite .kd, .codehilite .kn,
.codehilite .kp, .codehilite .kr, .codehilite .kt {{ color: {hl_keyword}; font-weight: bold; }}
.codehilite .ow {{ color: {hl_builtin}; font-weight: bold; }}
.codehilite .nb, .codehilite .bp {{ color: {hl_builtin}; }}
.codehilite .s, .codehilite .s2, .codehilite .s1, .codehilite .sc,
.codehilite .sd, .codehilite .se, .codehilite .sh, .codehilite .si,
.codehilite .sx, .codehilite .sr {{ color: {hl_string}; }}
.codehilite .mi, .codehilite .mf, .codehilite .mh, .codehilite .mo,
.codehilite .il, .codehilite .mb, .codehilite .mx {{ color: {hl_number}; }}
.codehilite .c, .codehilite .cm, .codehilite .cp, .codehilite .c1,
.codehilite .cs {{ color: {hl_comment}; font-style: italic; }}
.codehilite .nd, .codehilite .ne, .codehilite .nf, .codehilite .nx {{ color: {hl_meta}; }}
.codehilite .nv, .codehilite .vc, .codehilite .vg, .codehilite .vi {{ color: {hl_variable}; }}
.codehilite .na {{ color: {hl_attr}; }}
.codehilite .nt {{ color: {hl_tag}; }}
.codehilite .no {{ color: {hl_symbol}; }}
.codehilite .err {{ color: {hl_variable}; }}
"""
            base += hl_css + '\n'
        except Exception:
            pass
    return base


# ── Fallback markdown parser (stdlib only) ─────────────────────


def _inline_md(text):
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img alt="\1" src="\2"/>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    text = re.sub(r'`([^`]+)`', lambda m: f'<code>{escape(m.group(1))}</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    return text


def _parse_table(lines, start):
    header_line = lines[start].strip()
    if '|' not in header_line:
        return None, 0
    sep_line = lines[start + 1].strip() if start + 1 < len(lines) else ''
    if not re.match(r'^[\s|:\-]+$', sep_line):
        return None, 0

    headers = [c.strip() for c in header_line.split('|')[1:-1]]
    rows_html = []
    rows_html.append('<thead><tr>')
    for h in headers:
        rows_html.append(f'<th>{_inline_md(h)}</th>')
    rows_html.append('</tr></thead>')
    rows_html.append('<tbody>')
    i = start + 2
    while i < len(lines):
        row = lines[i].strip()
        if not row or '|' not in row:
            break
        cells = [c.strip() for c in row.split('|')[1:-1]]
        if len(cells) != len(headers):
            break
        rows_html.append('<tr>')
        for cell in cells:
            rows_html.append(f'<td>{_inline_md(cell)}</td>')
        rows_html.append('</tr>')
        i += 1
    rows_html.append('</tbody>')
    return ['<table>'] + rows_html + ['</table>'], i - start


def fallback_parse(text):
    lines = text.split('\n')
    result = []
    i = 0
    in_code = False
    code_buf = []
    code_lang = None
    in_bq = False
    in_ul = False
    in_ol = False

    def close_block():
        nonlocal in_bq, in_ul, in_ol
        if in_bq:
            result.append('</blockquote>')
            in_bq = False
        if in_ul:
            result.append('</ul>')
            in_ul = False
        if in_ol:
            result.append('</ol>')
            in_ol = False

    def add_bq(content):
        nonlocal in_bq
        if not in_bq:
            result.append('<blockquote>')
            in_bq = True
        if content:
            result.append(f'<p>{_inline_md(content)}</p>')

    def add_li(content, ordered=False):
        nonlocal in_ul, in_ol
        if ordered:
            if not in_ol:
                if in_ul:
                    result.append('</ul>')
                    in_ul = False
                result.append('<ol>')
                in_ol = True
            result.append(f'<li>{_inline_md(content)}</li>')
        else:
            if not in_ul:
                if in_ol:
                    result.append('</ol>')
                    in_ol = False
                result.append('<ul>')
                in_ul = True
            result.append(f'<li>{_inline_md(content)}</li>')

    while i < len(lines):
        s = lines[i].strip()
        if s.startswith('```'):
            if in_code:
                lang_attr = f' class="language-{code_lang}"' if code_lang else ''
                result.append(
                    f'<pre><code{lang_attr}>{escape(chr(10).join(code_buf))}</code></pre>'
                )
                code_buf = []
                in_code = False
                code_lang = None
            else:
                in_code = True
                lang = s[3:].strip()
                code_lang = lang if lang else None
            i += 1
            continue
        if in_code:
            code_buf.append(lines[i])
            i += 1
            continue

        if not s:
            close_block()
            i += 1
            continue
        if s == '---':
            close_block()
            result.append('<hr/>')
            i += 1
            continue

        if s.startswith('#### '):
            t = s[5:]
            hid = _slugify(t)
            close_block()
            result.append(f'<h4 id="{hid}">{_inline_md(t)}</h4>')
            i += 1
            continue
        if s.startswith('### '):
            t = s[4:]
            hid = _slugify(t)
            close_block()
            result.append(f'<h3 id="{hid}">{_inline_md(t)}</h3>')
            i += 1
            continue
        if s.startswith('## '):
            t = s[3:]
            hid = _slugify(t)
            close_block()
            result.append(f'<h2 id="{hid}">{_inline_md(t)}</h2>')
            i += 1
            continue
        if s.startswith('# '):
            t = s[2:]
            hid = _slugify(t)
            close_block()
            result.append(f'<h1 id="{hid}">{_inline_md(t)}</h1>')
            i += 1
            continue

        if '|' in s and i + 1 < len(lines) and re.match(r'^[\s|:\-]+$', lines[i + 1].strip()):
            close_block()
            table_html, consumed = _parse_table(lines, i)
            if table_html:
                result.extend(table_html)
                i += consumed
                continue

        if s.startswith('>'):
            add_bq(s.lstrip('> ').strip())
            i += 1
            continue
        elif in_bq:
            result.append('</blockquote>')
            in_bq = False

        if s.startswith('- '):
            add_li(s[2:], ordered=False)
            i += 1
            continue
        elif in_ul:
            result.append('</ul>')
            in_ul = False

        ol_match = re.match(r'^\d+\.\s+(.*)', s)
        if ol_match:
            add_li(ol_match.group(1), ordered=True)
            i += 1
            continue
        elif in_ol:
            result.append('</ol>')
            in_ol = False

        para = []
        while i < len(lines):
            s2 = lines[i].strip()
            if (
                not s2
                or s2.startswith('#')
                or s2.startswith('>')
                or s2.startswith('- ')
                or re.match(r'^\d+\.\s', s2)
                or s2.startswith('```')
                or s2 == '---'
                or (
                    '|' in s2
                    and i + 1 < len(lines)
                    and re.match(r'^[\s|:\-]+$', lines[i + 1].strip())
                )
            ):
                break
            para.append(lines[i].strip())
            i += 1
        if para:
            close_block()
            result.append(f'<p>{" ".join(para)}</p>')
            continue

        i += 1

    close_block()
    if in_code:
        lang_attr = f' class="language-{code_lang}"' if code_lang else ''
        result.append(f'<pre><code{lang_attr}>{escape(chr(10).join(code_buf))}</code></pre>')
    return '\n'.join(result)


# ── XHTML text node escaping ────────────────────────────────────

_KNOWN_HTML_TAGS = frozenset(
    {
        'p',
        'h1',
        'h2',
        'h3',
        'h4',
        'h5',
        'h6',
        'ul',
        'ol',
        'li',
        'dl',
        'dt',
        'dd',
        'strong',
        'em',
        'b',
        'i',
        'u',
        's',
        'strike',
        'del',
        'ins',
        'sub',
        'sup',
        'small',
        'big',
        'code',
        'pre',
        'kbd',
        'samp',
        'tt',
        'var',
        'q',
        'cite',
        'abbr',
        'acronym',
        'a',
        'img',
        'br',
        'hr',
        'wbr',
        'div',
        'span',
        'blockquote',
        'table',
        'thead',
        'tbody',
        'tfoot',
        'tr',
        'th',
        'td',
        'col',
        'colgroup',
        'caption',
        'figure',
        'figcaption',
        'section',
        'article',
        'nav',
        'header',
        'footer',
        'main',
        'aside',
        'details',
        'summary',
        'dialog',
        'html',
        'head',
        'body',
        'title',
        'meta',
        'link',
        'style',
        'script',
        'embed',
        'object',
        'param',
        'source',
        'track',
        'iframe',
        'canvas',
        'svg',
        'math',
        'ruby',
        'rt',
        'rp',
    }
)


class _TextNodeEscaper(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self._result = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in _KNOWN_HTML_TAGS:
            attrs_str = ''
            for k, v in attrs:
                v_esc = escape(v) if v is not None else ''
                attrs_str += f' {k}="{v_esc}"'
            self._result.append(f'<{tag}{attrs_str}>')
        else:
            self._result.append(escape(f'<{tag}>'))

    def handle_endtag(self, tag):
        if tag.lower() in _KNOWN_HTML_TAGS:
            self._result.append(f'</{tag}>')
        else:
            self._result.append(escape(f'</{tag}>'))

    def handle_startendtag(self, tag, attrs):
        if tag.lower() in _KNOWN_HTML_TAGS:
            attrs_str = ''
            for k, v in attrs:
                v_esc = escape(v) if v is not None else ''
                attrs_str += f' {k}="{v_esc}"'
            self._result.append(f'<{tag}{attrs_str}/>')
        else:
            self._result.append(escape(f'<{tag}/>'))

    def handle_data(self, data):
        self._result.append(escape(data))

    def handle_entityref(self, name):
        self._result.append(f'&{name};')

    def handle_charref(self, name):
        self._result.append(f'&#{name};')

    def handle_comment(self, data):
        self._result.append(f'<!--{data}-->')

    def handle_decl(self, decl):
        self._result.append(f'<!{decl}>')

    def handle_pi(self, data):
        self._result.append(f'<?{data}>')

    def result(self):
        return ''.join(self._result)


def _escape_text_nodes(html_str):
    parser = _TextNodeEscaper()
    try:
        parser.feed(html_str)
        parser.close()
        return parser.result()
    except Exception:
        return html_str


# ── Syntax highlighting ────────────────────────────────────


def _highlight_html(html, tokens):
    if not HAS_PYGMENTS:
        return html

    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import TextLexer, get_lexer_by_name, guess_lexer

    # Use monokai-style inline highlighting regardless of body theme
    fmt = HtmlFormatter(noclasses=False, nowrap=True)

    def _replace(m):
        code_tag = m.group(2)
        code_text = html_unescape(m.group(3))

        lang = ''
        cm = re.search(r'class="[^"]*language-([^"]*)"', code_tag)
        if cm:
            lang = cm.group(1)

        try:
            lexer = (
                get_lexer_by_name(lang, stripall=True) if lang else guess_lexer(code_text[:1024])
            )
        except Exception:
            lexer = TextLexer()

        try:
            highlighted = highlight(code_text, lexer, fmt)
        except Exception:
            return m.group(0)

        pre_bg = tokens.get('preBg', '#1e1e1e')
        return f'<pre style="background:{pre_bg};padding:1em;border-radius:4px;overflow-x:auto;font-size:0.85em;line-height:1.45;page-break-inside:avoid"><code class="codehilite" style="background:none;padding:0;font-size:1em">{highlighted}</code></pre>'

    html = re.sub(r'(<pre[^>]*>)(<code[^>]*>)(.*?)(</code></pre>)', _replace, html, flags=re.DOTALL)
    return html


# ── Mermaid diagram rendering ──────────────────────────────────

MERMAID_DEFAULT_MODE = 'api'
DIAGRAM_DIR = 'diagrams'


def _mermaid_render(source, mode, tmp_dir, idx):
    if mode == 'off':
        return None
    svg = None
    if mode == 'local':
        svg = _mermaid_render_local(source, tmp_dir, idx)
    if svg is None and mode in ('api', 'local'):
        svg = _mermaid_render_api(source)
    return svg


def _mermaid_render_local(source, tmp_dir, idx):
    mmd_file = os.path.join(tmp_dir, f'diagram_{idx:03d}.mmd')
    svg_file = os.path.join(tmp_dir, f'diagram_{idx:03d}.svg')
    try:
        with open(mmd_file, 'w', encoding='utf-8') as f:
            f.write(source)
        subprocess.run(
            ['mmdc', '-i', mmd_file, '-o', svg_file, '-q'],
            capture_output=True,
            timeout=30,
            check=True,
        )
        with open(svg_file, 'r', encoding='utf-8') as f:
            return f.read()
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None


def _mermaid_render_api(source):
    try:
        import urllib.request

        encoded = base64.urlsafe_b64encode(source.encode('utf-8')).decode('ascii')
        url = f'https://mermaid.ink/svg/{encoded}'
        req = urllib.request.Request(url, headers={'User-Agent': 'learn-something/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8')
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _process_mermaid_blocks(html, mode, tmp_dir):
    svg_files = []
    idx = [0]

    def replace(m):
        code_escaped = m.group(1)
        code = html_unescape(code_escaped)
        svg_content = _mermaid_render(code, mode, tmp_dir, idx[0])
        filename = f'diagram_{idx[0]:03d}.svg'
        idx[0] += 1
        if svg_content:
            svg_files.append((filename, svg_content))
            return f'<figure><img src="{filename}" alt="Diagram"/></figure>'
        else:
            return f'<figure><pre><code class="language-mermaid">{escape(code)}</code></pre><figcaption>Mermaid diagram (install mmdc or enable network to render)</figcaption></figure>'

    html = re.sub(
        r'<pre><code\s+class="[^"]*\blanguage-mermaid\b[^"]*">(.*?)</code></pre>',
        replace,
        html,
        flags=re.DOTALL,
    )
    return html, svg_files


# ── Procedural SVG cover generation ───────────────────────────

COVER_PALETTES = [
    {
        'bg': '#1a1a2e',
        'primary': '#e94560',
        'secondary': '#0f3460',
        'accent': '#16213e',
        'text': '#eee',
    },
    {
        'bg': '#0d1117',
        'primary': '#58a6ff',
        'secondary': '#1f6feb',
        'accent': '#388bfd',
        'text': '#f0f6fc',
    },
    {
        'bg': '#1b1b2f',
        'primary': '#e43f5a',
        'secondary': '#162447',
        'accent': '#1f4068',
        'text': '#eaeaea',
    },
    {
        'bg': '#0b0c10',
        'primary': '#66fcf1',
        'secondary': '#45a29e',
        'accent': '#c5c6c7',
        'text': '#f0f0f0',
    },
    {
        'bg': '#2d132c',
        'primary': '#ee4540',
        'secondary': '#c72c41',
        'accent': '#801336',
        'text': '#f5f5f5',
    },
    {
        'bg': '#1a1a2e',
        'primary': '#e94560',
        'secondary': '#533483',
        'accent': '#0f3460',
        'text': '#eee',
    },
    {
        'bg': '#0a0a0a',
        'primary': '#ff6b35',
        'secondary': '#004e89',
        'accent': '#1a659e',
        'text': '#f7f7f7',
    },
    {
        'bg': '#16161a',
        'primary': '#7f5af0',
        'secondary': '#2cb67d',
        'accent': '#e16162',
        'text': '#fffffe',
    },
]

LIGHT_PALETTES = [
    {
        'bg': '#fafafa',
        'primary': '#f92672',
        'secondary': '#a6e22e',
        'accent': '#66d9ef',
        'text': '#1a1a1a',
    },
    {
        'bg': '#f8f8f8',
        'primary': '#d64a9e',
        'secondary': '#7c3aed',
        'accent': '#3db85e',
        'text': '#1a1a1a',
    },
    {
        'bg': '#f5f5f5',
        'primary': '#2563eb',
        'secondary': '#7c3aed',
        'accent': '#16a34a',
        'text': '#111111',
    },
    {
        'bg': '#faf8f5',
        'primary': '#8b3a62',
        'secondary': '#2563eb',
        'accent': '#ca8a04',
        'text': '#1a1a1a',
    },
    {
        'bg': '#ffffff',
        'primary': '#d91a5c',
        'secondary': '#6366f1',
        'accent': '#7cb342',
        'text': '#1a1a1a',
    },
    {
        'bg': '#fbf0d9',
        'primary': '#9b4d84',
        'secondary': '#6366f1',
        'accent': '#a0896e',
        'text': '#3d2b1a',
    },
    {
        'bg': '#f0f0f0',
        'primary': '#444444',
        'secondary': '#888888',
        'accent': '#666666',
        'text': '#111111',
    },
    {
        'bg': '#fafafa',
        'primary': '#e94560',
        'secondary': '#0f3460',
        'accent': '#16213e',
        'text': '#1a1a1a',
    },
]


def _title_hash(title):
    h = hashlib.sha256(title.encode('utf-8')).hexdigest()
    return int(h[:8], 16)


def _is_light_bg(bg_color):
    if not bg_color:
        return False
    bg_color = bg_color.lstrip('#')
    if len(bg_color) != 6:
        return False
    r, g, b = int(bg_color[0:2], 16), int(bg_color[2:4], 16), int(bg_color[4:6], 16)
    return (r * 299 + g * 587 + b * 114) / 1000 > 128


def _pick_palette(title, bg_color=None):
    idx = _title_hash(title) % len(COVER_PALETTES)
    if bg_color and _is_light_bg(bg_color):
        palettes = LIGHT_PALETTES + COVER_PALETTES
        return palettes[idx % len(palettes)]
    return COVER_PALETTES[idx]


def _svg_text_width(text, font_size):
    return len(text) * font_size * 0.55


def _wrap_text(text, max_width, font_size):
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = ' '.join(current + [word])
        if _svg_text_width(test, font_size) > max_width and current:
            lines.append(' '.join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(' '.join(current))
    return lines


def generate_cover_svg(title, author='', description='', theme_tokens=None, chapter_count=0):
    pal = _pick_palette(title, theme_tokens.get('bg') if theme_tokens else None)
    rng = random.Random(_title_hash(title))

    w, h = 1264, 1680
    svg_parts = []

    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
    )
    svg_parts.append(f'<rect width="{w}" height="{h}" fill="{pal["bg"]}"/>')

    pattern_type = _title_hash(title) % 6

    if pattern_type == 0:
        for _ in range(60):
            cx = rng.randint(0, w)
            cy = rng.randint(0, h)
            r = rng.randint(20, 120)
            opacity = rng.uniform(0.05, 0.15)
            color = pal['primary'] if rng.random() > 0.5 else pal['secondary']
            svg_parts.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" opacity="{opacity}"/>'
            )
    elif pattern_type == 1:
        for i in range(12):
            y = 60 + i * 65
            amplitude = rng.randint(15, 40)
            freq = rng.uniform(0.003, 0.008)
            points = []
            for x in range(0, w + 20, 10):
                dy = y + math.sin(x * freq + i * 0.7) * amplitude
                points.append(f'{x},{dy:.1f}')
            opacity = rng.uniform(0.06, 0.18)
            color = pal['primary'] if i % 3 == 0 else pal['secondary']
            svg_parts.append(
                f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2" opacity="{opacity}"/>'
            )
    elif pattern_type == 2:
        for _ in range(8):
            x1 = rng.randint(-100, w + 100)
            y1 = rng.randint(-100, h + 100)
            x2 = rng.randint(-100, w + 100)
            y2 = rng.randint(-100, h + 100)
            color = pal['primary'] if rng.random() > 0.4 else pal['secondary']
            opacity = rng.uniform(0.04, 0.12)
            svg_parts.append(
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{rng.randint(1, 4)}" opacity="{opacity}"/>'
            )
        for _ in range(25):
            cx = rng.randint(0, w)
            cy = rng.randint(0, h)
            r = rng.randint(3, 8)
            svg_parts.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{pal["accent"]}" opacity="0.3"/>'
            )
    elif pattern_type == 3:
        cols = rng.randint(8, 14)
        rows = rng.randint(6, 10)
        cell_w = w // cols
        cell_h = h // rows
        for r in range(rows):
            for c in range(cols):
                if rng.random() > 0.6:
                    x = c * cell_w + cell_w // 2
                    y = r * cell_h + cell_h // 2
                    sz = rng.randint(cell_w // 4, cell_w // 2)
                    color = pal['primary'] if (r + c) % 3 == 0 else pal['secondary']
                    opacity = rng.uniform(0.04, 0.14)
                    if rng.random() > 0.5:
                        svg_parts.append(
                            f'<rect x="{x - sz // 2}" y="{y - sz // 2}" width="{sz}" height="{sz}" fill="{color}" opacity="{opacity}" rx="4"/>'
                        )
                    else:
                        svg_parts.append(
                            f'<circle cx="{x}" cy="{y}" r="{sz // 2}" fill="{color}" opacity="{opacity}"/>'
                        )

    elif pattern_type == 4:
        hex_r = 40
        hex_h = hex_r * 2
        hex_w = math.sqrt(3) * hex_r
        cols = int(w / (hex_w * 0.75)) + 3
        rows = int(h / (hex_h * 0.5)) + 3
        for row in range(rows):
            for col in range(cols):
                cx = col * hex_w * 0.75 + (row % 2) * hex_w * 0.375
                cy = row * hex_h * 0.5
                if rng.random() > 0.55:
                    pts = []
                    for i in range(6):
                        angle = math.pi / 3 * i - math.pi / 6
                        px = cx + hex_r * math.cos(angle)
                        py = cy + hex_r * math.sin(angle)
                        pts.append(f'{px:.1f},{py:.1f}')
                    color = pal['primary'] if (row + col) % 3 == 0 else pal['secondary']
                    opacity = rng.uniform(0.04, 0.12)
                    svg_parts.append(
                        f'<polygon points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.5" opacity="{opacity}"/>'
                    )

    elif pattern_type == 5:
        tri_size = 60
        spacing_x = tri_size * 0.87
        spacing_y = tri_size * 0.75
        num_cols = int(w / spacing_x) + 3
        num_rows = int(h / spacing_y) + 3
        for row in range(num_rows):
            for col in range(num_cols):
                cx = col * spacing_x + (row % 2) * spacing_x * 0.5
                cy = row * spacing_y
                if rng.random() > 0.4:
                    up = (row + col) % 2 == 0
                    if up:
                        pts = f'{cx},{cy - tri_size * 0.58} {cx - tri_size * 0.5},{cy + tri_size * 0.29} {cx + tri_size * 0.5},{cy + tri_size * 0.29}'
                    else:
                        pts = f'{cx},{cy + tri_size * 0.58} {cx - tri_size * 0.5},{cy - tri_size * 0.29} {cx + tri_size * 0.5},{cy - tri_size * 0.29}'
                    color = pal['primary'] if (row + col) % 2 == 0 else pal['secondary']
                    opacity = rng.uniform(0.03, 0.10)
                    svg_parts.append(
                        f'<polygon points="{pts}" fill="none" stroke="{color}" stroke-width="1.5" opacity="{opacity}"/>'
                    )

    overlay_y = h * 0.30
    svg_parts.append(
        f'<defs><linearGradient id="ovg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{pal["bg"]}" stop-opacity="0.85"/>'
        f'<stop offset="45%" stop-color="{pal["bg"]}" stop-opacity="0.70"/>'
        f'<stop offset="100%" stop-color="{pal["bg"]}" stop-opacity="0"/>'
        f'</linearGradient></defs>'
    )
    svg_parts.append(
        f'<rect x="0" y="{overlay_y - 40}" width="{w}" height="{h - overlay_y + 40}" fill="url(#ovg)"/>'
    )

    accent_line_y = overlay_y + 10
    svg_parts.append(
        f'<rect x="100" y="{accent_line_y}" width="220" height="10" fill="{pal["primary"]}" rx="5"/>'
    )

    title_font = 140
    title_x = 100
    title_y = accent_line_y + 140
    title_lines = _wrap_text(title, w - 200, title_font)
    for i, line in enumerate(title_lines):
        svg_parts.append(
            f'<text x="{title_x}" y="{title_y + i * 160}" font-family="Georgia, serif" font-size="{title_font}" font-weight="bold" fill="{pal["text"]}">{escape(line)}</text>'
        )

    desc_font = 60
    desc_y = title_y + len(title_lines) * 160 + 50
    if description:
        desc_lines = _wrap_text(description, w - 200, desc_font)
        for i, line in enumerate(desc_lines[:3]):
            svg_parts.append(
                f'<text x="{title_x}" y="{desc_y + i * 72}" font-family="Georgia, serif" font-size="{desc_font}" fill="{pal["text"]}" opacity="0.7">{escape(line)}</text>'
            )
        desc_y += len(desc_lines[:3]) * 72 + 30

    if chapter_count > 0:
        subtitle = f'{chapter_count} modules'
        svg_parts.append(
            f'<text x="{title_x}" y="{desc_y + 30}" font-family="Arial, sans-serif" font-size="40" fill="{pal["primary"]}" opacity="0.8">{escape(subtitle)}</text>'
        )
        desc_y += 72

    if author:
        svg_parts.append(
            f'<text x="{title_x}" y="{h - 120}" font-family="Arial, sans-serif" font-size="48" fill="{pal["text"]}" opacity="0.5">{escape(author)}</text>'
        )

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


# ── Title formatting + slugify ─────────────────────────────────


def _format_title(name):
    name = re.sub(r'[-_]', ' ', name)
    return name.strip().title()


def _slugify(text):
    slug = text.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


# ── Chapter splitting ──────────────────────────────────────────


def split_chapters(text):
    chapters = []
    lines = text.split('\n')
    cur_title = None
    cur_lines = []
    in_fence = False
    for line in lines:
        if line.strip().startswith('```'):
            in_fence = not in_fence
        if line.startswith('# ') and line.strip() != '# ' and not in_fence:
            if cur_title is not None:
                chapters.append((cur_title, '\n'.join(cur_lines)))
            cur_title = line[2:].strip()
            cur_lines = []
        else:
            cur_lines.append(line)
    if cur_title is not None:
        chapters.append((cur_title, '\n'.join(cur_lines)))
    return chapters


# ── Subject markdown assembly ──────────────────────────────────


def collect_subject_md(subject_dir):
    """Collect subject markdown + diagram image assets.

    Returns:
        (markdown_text, assets_dict) where assets_dict maps
        unique_name -> PNG bytes for diagram images.
    """
    modules_dir = os.path.join(subject_dir, 'modules')
    if not os.path.isdir(modules_dir):
        print(f'Missing: {modules_dir}', file=sys.stderr)
        sys.exit(1)

    parts = []
    assets = {}  # {unique_name: PNG bytes} for diagram images
    mod_names = sorted(
        d for d in os.listdir(modules_dir) if os.path.isdir(os.path.join(modules_dir, d))
    )

    for i, name in enumerate(mod_names):
        mod_path = os.path.join(modules_dir, name)
        lesson_path = os.path.join(mod_path, 'lesson.md')
        quiz_path = os.path.join(mod_path, 'quiz.yaml')
        diag_path = os.path.join(mod_path, 'diagrams')

        if i > 0:
            parts.append('\n---\n')

        if os.path.isfile(lesson_path):
            with open(lesson_path, 'r', encoding='utf-8') as f:
                lesson_text = f.read()

            # Collect diagram images and adjust paths
            if os.path.isdir(diag_path):
                for fname in sorted(os.listdir(diag_path)):
                    if fname.lower().endswith('.png'):
                        src_path = os.path.join(diag_path, fname)
                        with open(src_path, 'rb') as f:
                            data = f.read()
                        asset_key = f'{name}_{fname}'
                        assets[asset_key] = data
                        # Replace relative diagram paths with EPUB-internal paths
                        lesson_text = lesson_text.replace(
                            f'({DIAGRAM_DIR}/{fname})',
                            f'({asset_key})',
                        )

            parts.append(lesson_text.rstrip())
        if os.path.isfile(quiz_path) and HAS_YAML:
            try:
                with open(quiz_path, 'r', encoding='utf-8') as f:
                    questions = yaml.safe_load(f)
                if questions:
                    parts.append(f'\n## Quiz: {name}\n')
                for qi, q in enumerate(questions):
                    if qi > 0:
                        parts.append('<hr/>\n')
                    ans = q.get('answer', '')
                    diff = q.get('difficulty', 0)
                    stars = '★' * diff + '☆' * (3 - diff) if 1 <= diff <= 3 else ''
                    qtext = escape(q.get('question', ''))
                    parts.append(f'<p class="quiz-question">{qtext}</p>\n')
                    if stars:
                        parts.append(f'<p class="quiz-difficulty">{stars}</p>\n')
                    for k in ('A', 'B', 'C', 'D'):
                        opts = q.get('options', {})
                        v = opts.get(k) or opts.get(k.lower(), '')
                        parts.append(
                            f'<p class="quiz-option"><strong>{k}.</strong> {escape(v)}</p>\n'
                        )
                    parts.append(
                        f'<p class="quiz-answer"><strong>Answer:</strong> {escape(ans)}</p>\n'
                    )
                    expl = escape(q.get('explanation', ''))
                    if expl:
                        parts.append(f'<p class="quiz-explanation">{expl}</p>\n')
            except Exception as e:
                parts.append(f'\n## Quiz: {name}\n\n(quiz parse error: {e})\n')
        elif os.path.isfile(quiz_path):
            parts.append(f'\n## Quiz: {name}\n\n(install yaml library to include quizzes)\n')

    return '\n'.join(parts), assets


# ── Hierarchical ToC navigation ────────────────────────────────


TOC_SKIP_HEADINGS = {
    'why this matters',
    'common questions',
    'common misconception',
    'common misconceptions',
    'feynman explain',
    'reframe',
    'drill',
    'core content',
    'key takeaways',
    'takeaways',
    'think',
    'examples',
    'example',
    'overview',
    'introduction',
    'prerequisites',
    'summary',
    'learning objectives',
    'quiz',
}


def _extract_subheadings(content):
    items = []
    for line in content.split('\n'):
        s = line.strip()
        if s.startswith('## '):
            t = s[3:].strip()
            if t.lower() not in TOC_SKIP_HEADINGS:
                items.append((2, t, _slugify(t)))
        elif s.startswith('### '):
            t = s[4:].strip()
            items.append((3, t, _slugify(t)))
    return items


def _build_hierarchical_toc(chapters):
    tree = []
    stack = [(0, tree)]

    for ch_idx, (ch_title, ch_content) in enumerate(chapters, 1):
        ch_file = f'ch{ch_idx:03d}.xhtml'
        h1_href = ch_file
        h1_node = (ch_title, h1_href, [])
        h1_level = 1

        while stack and stack[-1][0] >= h1_level:
            stack.pop()
        if stack:
            stack[-1][1].append(h1_node)
        stack.append((h1_level, h1_node[2]))

        for sub_level, sub_title, sub_slug in _extract_subheadings(ch_content):
            href = f'{ch_file}#{sub_slug}'
            node = (sub_title, href, [])

            while stack and stack[-1][0] >= sub_level:
                stack.pop()
            if stack:
                stack[-1][1].append(node)
            stack.append((sub_level, node[2]))

    return tree


def _render_toc_nav(tree, depth=0):
    if not tree:
        return ''
    indent = '  ' * depth
    parts = [f'{indent}<ol>']
    for title, href, children in tree:
        parts.append(f'{indent}  <li><a href="{escape(href)}">{escape(title)}</a>')
        if children:
            parts.append(_render_toc_nav(children, depth + 2))
        parts.append(f'{indent}  </li>')
    parts.append(f'{indent}</ol>')
    return '\n'.join(parts)


def _generate_ncx(tree, title, uid):
    counter = [0]

    def _render_ncx_nodes(nodes, indent=4):
        result = []
        for title, href, children in nodes:
            counter[0] += 1
            result.append(
                f'{" " * indent}<navPoint id="navpoint-{counter[0]}" playOrder="{counter[0]}">'
            )
            result.append(f'{" " * (indent + 2)}<navLabel><text>{escape(title)}</text></navLabel>')
            result.append(f'{" " * (indent + 2)}<content src="{escape(href)}"/>')
            if children:
                result.extend(_render_ncx_nodes(children, indent + 2))
            result.append(f'{" " * indent}</navPoint>')
        return result

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">',
        '  <head>',
        f'    <meta name="dtb:uid" content="{escape(uid)}"/>',
        '    <meta name="dtb:depth" content="1"/>',
        '    <meta name="dtb:totalPageCount" content="0"/>',
        '    <meta name="dtb:maxPageNumber" content="0"/>',
        '  </head>',
        f'  <docTitle><text>{escape(title)}</text></docTitle>',
        '  <navMap>',
    ]
    parts.extend(_render_ncx_nodes(tree))
    parts.append('  </navMap>')
    parts.append('</ncx>')
    return '\n'.join(parts)


# ── SVG → PNG conversion ──────────────────────────────────────


def _svg_to_png(svg_content):
    import subprocess

    if isinstance(svg_content, str):
        svg_content = svg_content.encode('utf-8')
    try:
        p = subprocess.run(
            ['rsvg-convert', '--format', 'png', '--width', '1264', '--height', '1680'],
            input=svg_content,
            capture_output=True,
            timeout=30,
        )
        if p.returncode == 0 and len(p.stdout) > 100:
            return p.stdout
    except Exception:
        pass
    return None


# ── EPUB generation ────────────────────────────────────────────


def generate_epub(
    chapters,
    output_path,
    title,
    author='Learn Something',
    mermaid_mode='api',
    description='',
    theme_tokens=None,
    assets=None,
):
    uid = str(uuid.uuid4())
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    if theme_tokens is None:
        themes = load_themes()
        theme_tokens = get_theme('notebook', themes)
    css = make_css(theme_tokens, use_pygments=HAS_PYGMENTS)

    parent = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(parent, exist_ok=True)

    xhtml_files = {}
    manifest = []
    spine = []
    all_svg_files = []
    all_png_files = []

    if assets is None:
        assets = {}

    tmp_dir = tempfile.mkdtemp(prefix='opencode-mermaid-')

    cover_svg = generate_cover_svg(title, author, description, theme_tokens, len(chapters))
    xhtml_files['cover.svg'] = cover_svg

    cover_png = _svg_to_png(cover_svg)
    if cover_png:
        xhtml_files['cover.png'] = cover_png
        manifest.append(('cover.png', 'image/png', 'cover-image'))
        cover_img = 'cover.png'
    else:
        manifest.append(('cover.svg', 'image/svg+xml', 'cover-image'))
        cover_img = 'cover.svg'

    cover_xhtml = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Cover</title>
<style>
html, body {{ margin:0; padding:0; height:100%; }}
.cover-wrap {{ text-align:center; width:100%; height:100%; display:flex; align-items:center; justify-content:center; }}
.cover-wrap img {{ max-width:100%; max-height:100%; }}
</style>
</head>
<body>
<div class="cover-wrap">
<img src="{cover_img}" alt="Cover"/>
</div>
</body>
</html>'''
    xhtml_files['cover.xhtml'] = cover_xhtml
    manifest.append(('cover.xhtml', 'application/xhtml+xml', 'cover'))
    spine.append(('cover', True))

    for idx, (ch_title, content) in enumerate(chapters, 1):
        if HAS_MARKDOWN:
            md = _md.Markdown(extensions=['extra', 'toc'], output_format='xhtml')
            html_content = md.convert(content)
        else:
            html_content = fallback_parse(content)
        html_content = _escape_text_nodes(html_content)
        html_content, svg_files = _process_mermaid_blocks(html_content, mermaid_mode, tmp_dir)
        html_content = _highlight_html(html_content, theme_tokens)
        all_svg_files.extend(svg_files)

        filename = f'ch{idx:03d}.xhtml'
        pid = f'ch{idx}'

        page = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{escape(ch_title)}</title><link rel="stylesheet" type="text/css" href="style.css"/></head>
<body>
<h1 id="{_slugify(ch_title)}">{escape(ch_title)}</h1>
{html_content}
</body></html>'''
        xhtml_files[filename] = page
        manifest.append((filename, 'application/xhtml+xml', pid))
        spine.append((pid, True))

    spine.append(('nav', False))

    toc_tree = _build_hierarchical_toc(chapters)
    toc_nav_body = _render_toc_nav(toc_tree) if toc_tree else '<ol>\n</ol>'

    nav_html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Table of Contents</title></head>
<body>
<nav epub:type="toc">
<h1>Table of Contents</h1>
{toc_nav_body}
</nav>
</body>
</html>"""
    xhtml_files['nav.xhtml'] = nav_html
    manifest.append(('nav.xhtml', 'application/xhtml+xml', 'nav'))

    ncx_content = _generate_ncx(toc_tree, title, uid)
    manifest.append(('toc.ncx', 'application/x-dtbncx+xml', 'ncx'))

    svg_idx = 0
    for svg_fname, svg_content in all_svg_files:
        svg_idx += 1
        manifest.append((svg_fname, 'image/svg+xml', f'svg{svg_idx}'))

    png_idx = 0
    for asset_key, png_bytes in assets.items():
        png_idx += 1
        fname = f'img_{asset_key}'
        all_png_files.append((fname, png_bytes))
        manifest.append((fname, 'image/png', f'img{png_idx}'))

    opf_manifest = '<item id="css" href="style.css" media-type="text/css"/>\n'
    for fname, mtype, pid in manifest:
        props = ' properties="cover-image"' if pid == 'cover-image' else ''
        opf_manifest += f'<item id="{pid}" href="{fname}" media-type="{mtype}"{props}/>\n'

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="book-id">{escape(uid)}</dc:identifier>
<dc:title>{escape(title)}</dc:title>
<dc:language>en</dc:language>
<dc:creator>{escape(author)}</dc:creator>
<dc:date>{escape(now)}</dc:date>
<meta property="dcterms:modified">{escape(now)}</meta>
<meta name="cover" content="cover-image"/>
</metadata>
<manifest>
{opf_manifest}</manifest>
 <spine toc="ncx">
"""
    for pid, linear in spine:
        lin = '' if linear else ' linear="no"'
        opf += f'<itemref idref="{pid}"{lin}/>\n'
    opf += '</spine>\n</package>'

    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles>
<rootfile full-path="EPUB/content.opf" media-type="application/oebps-package+xml"/>
</rootfiles>
</container>"""

    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
            zf.writestr('META-INF/container.xml', container)
            zf.writestr('EPUB/content.opf', opf)
            zf.writestr('EPUB/style.css', css)
            for fname, content in xhtml_files.items():
                zf.writestr(f'EPUB/{fname}', content)
            for svg_fname, svg_content in all_svg_files:
                zf.writestr(f'EPUB/{svg_fname}', svg_content)
            for png_fname, png_bytes in all_png_files:
                zf.writestr(f'EPUB/{png_fname}', png_bytes)
            zf.writestr('EPUB/toc.ncx', ncx_content)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── EPUB verification ──────────────────────────────────────────


def verify_epub(path):
    import xml.etree.ElementTree as ET

    issues = []
    opf_path = None

    try:
        zf = zipfile.ZipFile(path, 'r')
    except zipfile.BadZipFile:
        return [('FAIL', 'Not a valid ZIP file')], 0, 0

    names = zf.namelist()
    total_size = sum(zf.getinfo(n).file_size for n in names)

    if 'mimetype' not in names:
        issues.append(('FAIL', 'Missing mimetype'))
    else:
        mt = zf.read('mimetype').decode('utf-8').strip()
        if mt != 'application/epub+zip':
            issues.append(('FAIL', f'mimetype wrong: "{mt}"'))
        else:
            info = zf.getinfo('mimetype')
            if info.compress_type != zipfile.ZIP_STORED:
                issues.append(('WARN', 'mimetype not ZIP_STORED'))
            issues.append(('OK', 'mimetype: application/epub+zip'))

    if 'META-INF/container.xml' not in names:
        issues.append(('FAIL', 'Missing META-INF/container.xml'))
    else:
        try:
            cxml = zf.read('META-INF/container.xml')
            root = ET.fromstring(cxml)
            rfs = root.findall('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile')
            if not rfs:
                issues.append(('FAIL', 'No rootfile in container'))
            else:
                for rf in rfs:
                    p = rf.get('full-path')
                    if p:
                        opf_path = p
                issues.append(('OK', f'META-INF/container.xml → {opf_path}'))
        except ET.ParseError as e:
            issues.append(('FAIL', f'container.xml parse: {e}'))

    if opf_path and opf_path not in names:
        issues.append(('FAIL', f'OPF not found: {opf_path}'))
        opf_path = None

    if opf_path:
        try:
            opf = ET.fromstring(zf.read(opf_path))
            ns = 'http://www.idpf.org/2007/opf'
            dc = 'http://purl.org/dc/elements/1.1/'
            dir_ = os.path.dirname(opf_path)

            title = opf.findall(f'.//{{{dc}}}title')
            if not title:
                issues.append(('FAIL', 'Missing dc:title'))
            else:
                issues.append(('OK', f'dc:title: {title[0].text or "(empty)"}'))

            if not opf.findall(f'.//{{{dc}}}identifier'):
                issues.append(('FAIL', 'Missing dc:identifier'))
            else:
                issues.append(('OK', 'dc:identifier present'))

            if not opf.findall(f'.//{{{dc}}}language'):
                issues.append(('WARN', 'Missing dc:language'))
            else:
                issues.append(('OK', 'dc:language present'))

            manifest = opf.find(f'.//{{{ns}}}manifest')
            items = manifest.findall(f'{{{ns}}}item') if manifest is not None else []
            if not items:
                issues.append(('FAIL', 'Empty manifest'))
            else:
                issues.append(('OK', f'Manifest: {len(items)} items'))
            xhtml_count = 0
            found_nav = False
            for item in items:
                href = item.get('href', '')
                mt = item.get('media-type', '')
                pid = item.get('id', '')
                if pid == 'nav':
                    found_nav = True
                ip = os.path.join(dir_, href) if href else None
                if ip and ip not in names:
                    issues.append(('FAIL', f'Manifest item missing: {href}'))
                if mt == 'application/xhtml+xml' and ip and ip in names:
                    xhtml_count += 1
                    try:
                        ET.fromstring(zf.read(ip))
                    except ET.ParseError as e:
                        issues.append(('FAIL', f'Invalid XHTML {href}: {e}'))
            if found_nav:
                issues.append(('OK', 'Navigation: nav.xhtml'))
            else:
                issues.append(('WARN', 'No nav item in manifest'))
            if xhtml_count:
                issues.append(('OK', f'{xhtml_count} XHTML files well-formed'))

            spine = opf.find(f'.//{{{ns}}}spine')
            refs = spine.findall(f'{{{ns}}}itemref') if spine is not None else []
            if not refs:
                issues.append(('FAIL', 'Empty spine'))
            else:
                issues.append(('OK', f'Spine: {len(refs)} items'))
        except ET.ParseError as e:
            issues.append(('FAIL', f'OPF parse error: {e}'))

    zf.close()
    chapter_count = sum(1 for n in names if re.match(r'EPUB/ch\d+\.xhtml', n))
    return issues, chapter_count, total_size


# ── CLI ────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description='EPUB builder for Learn Something')
    sub = parser.add_subparsers(dest='command')

    p_build = sub.add_parser('build', help='Build EPUB from subject directory')
    p_build.add_argument('subject_dir')
    p_build.add_argument('output')
    p_build.add_argument('--theme', default='notebook', help='Theme name (default: notebook)')
    p_build.add_argument('--title', default=None)
    p_build.add_argument('--author', default='Learn Something')
    p_build.add_argument('--description', default='', help='Cover page description')
    p_build.add_argument(
        '--mermaid',
        default=MERMAID_DEFAULT_MODE,
        choices=['api', 'local', 'off'],
        help='Mermaid rendering mode: api (default), local (mmdc CLI), off (skip)',
    )

    p_vfy = sub.add_parser('verify', help='Validate EPUB file structure')
    p_vfy.add_argument('epub_file')

    p_md = sub.add_parser('from-md', help='Build EPUB from markdown file')
    p_md.add_argument('markdown_file')
    p_md.add_argument('output')
    p_md.add_argument('--theme', default='notebook', help='Theme name (default: notebook)')
    p_md.add_argument('--title', default=None)
    p_md.add_argument('--author', default='Learn Something')
    p_md.add_argument('--description', default='', help='Cover page description')
    p_md.add_argument(
        '--mermaid',
        default=MERMAID_DEFAULT_MODE,
        choices=['api', 'local', 'off'],
        help='Mermaid rendering mode: api (default), local (mmdc CLI), off (skip)',
    )

    p_css = sub.add_parser('css', help='Print CSS for the given theme')
    p_css.add_argument('--theme', default='notebook', help='Theme name (default: notebook)')

    sub.add_parser('list-themes', help='List available themes')

    args = parser.parse_args()

    if args.command == 'list-themes':
        themes = load_themes()
        print('Available themes:')
        for name in sorted(themes.keys()):
            t = themes[name]
            bg = t.get('bg', 'N/A')
            print(f'  {name:20s} bg={bg}')
        return

    if args.command == 'css':
        theme_name = args.theme
        themes = load_themes()
        tokens = get_theme(theme_name, themes)
        tokens['_name'] = theme_name
        css = make_css(tokens, use_pygments=False)
        print(css)
        return

    if args.command == 'verify':
        epub = args.epub_file
        if not os.path.isfile(epub):
            print(f'File not found: {epub}', file=sys.stderr)
            sys.exit(1)
        issues, chapters, size = verify_epub(epub)
        print(f'EPUB: {epub}')
        for severity, msg in issues:
            icon = '✓' if severity == 'OK' else ('⚠' if severity == 'WARN' else '✗')
            print(f'  {icon} {severity}: {msg}')
        ch_label = f'{chapters} chapters' if chapters else 'no chapters'
        size_kb = size / 1024
        print(f'  Summary: {ch_label}, {size_kb:.1f} KB')
        fails = sum(1 for s, _ in issues if s == 'FAIL')
        print(f'  Status: {"VALID" if fails == 0 else f"INVALID ({fails} failures)"}')
        sys.exit(0 if fails == 0 else 1)

    if args.command not in ('build', 'from-md'):
        parser.print_help()
        sys.exit(1)

    theme_name = args.theme
    themes = load_themes()
    tokens = get_theme(theme_name, themes)
    tokens['_name'] = theme_name

    if is_dark_theme(tokens.get('bg', '#ffffff')):
        print(DARK_THEMES_WARNING.format(theme=theme_name), file=sys.stderr)

    if args.command == 'build':
        subject_dir = args.subject_dir
        if not os.path.isdir(subject_dir):
            print(f'Subject directory not found: {subject_dir}', file=sys.stderr)
            sys.exit(1)
        title = args.title or _format_title(os.path.basename(os.path.normpath(subject_dir)))
        author = args.author
        description = args.description
        md_text, assets = collect_subject_md(subject_dir)
        book_md = os.path.join(subject_dir, 'book.md')
        with open(book_md, 'w', encoding='utf-8') as f:
            f.write(md_text)
        print(f'Intermediate markdown: {book_md}')
        print(f'Diagram assets: {len(assets)} PNG file(s)')
    else:
        md_file = args.markdown_file
        if not os.path.isfile(md_file):
            print(f'Markdown file not found: {md_file}', file=sys.stderr)
            sys.exit(1)
        title = args.title or _format_title(os.path.splitext(os.path.basename(md_file))[0])
        author = args.author
        description = args.description
        with open(md_file, 'r', encoding='utf-8') as f:
            md_text = f.read()
        assets = {}

    output = args.output
    chapters = split_chapters(md_text)
    if not chapters:
        chapters = [(title, md_text)]
    generate_epub(
        chapters,
        output,
        title,
        author,
        mermaid_mode=args.mermaid,
        description=description,
        theme_tokens=tokens,
        assets=assets,
    )
    size_kb = os.path.getsize(output) / 1024
    print(f'EPUB: {output} ({len(chapters)} chapters, {size_kb:.1f} KB)')
    print(f'Theme: {theme_name}')


if __name__ == '__main__':
    main()
