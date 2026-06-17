#!/usr/bin/env python3
"""EPUB builder with optional syntax highlighting + table support.

Dependencies (optional):
  - markdown + pygments: full GFM tables, monokai code highlighting
  - yaml: quiz inclusion
  Falls back to stdlib-only parser (still handles tables, lists, code).

Usage:
  epub.py build <subject-dir> <output> [--title TITLE] [--author AUTHOR]
  epub.py from-md <markdown-file> <output> [--title TITLE] [--author AUTHOR]
  epub.py css
"""

import argparse
import os
import re
import sys
import uuid
import zipfile
from datetime import datetime
import html.parser
from xml.sax.saxutils import escape
from html import unescape as html_unescape

# ── Optional dependencies ─────────────────────────────────────

HAS_MARKDOWN = False
HAS_PYGMENTS = False
HAS_YAML = False

try:
    import markdown as _md
    HAS_MARKDOWN = True
except ImportError:
    pass

try:
    from pygments.formatters import HtmlFormatter
    HAS_PYGMENTS = True
except ImportError:
    pass

try:
    import yaml
    HAS_YAML = True
except ImportError:
    pass

# ── CSS ────────────────────────────────────────────────────────

def make_css(use_pygments=False):
    base = '''/* Clean Modern theme */
@namespace epub "http://www.idpf.org/2007/ops";

body {
  font-family: Georgia, "Times New Roman", serif;
  line-height: 1.7;
  color: #333;
  background: #fff;
  margin: 1em 2em;
  max-width: 38em;
  word-wrap: break-word;
}

h1, h2, h3, h4 {
  font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
  color: #111;
  font-weight: 600;
  line-height: 1.3;
  page-break-after: avoid;
}

h1 {
  font-size: 1.6em;
  border-bottom: 2px solid #0366d6;
  padding-bottom: 0.3em;
  margin-top: 1.5em;
}

h2 {
  font-size: 1.3em;
  color: #222;
  border-bottom: 1px solid #e0e0e0;
  padding-bottom: 0.2em;
  margin-top: 1.3em;
}

h3 {
  font-size: 1.1em;
  color: #444;
  margin-top: 1.2em;
}

h1:first-child { margin-top: 0; }

a { color: #0366d6; text-decoration: none; }
a:hover { text-decoration: underline; }

p { margin: 0.6em 0; }

blockquote {
  border-left: 4px solid #0366d6;
  margin: 1em 0;
  padding: 0.5em 1em;
  color: #555;
  background: #f8f9fa;
}

blockquote p { margin: 0.3em 0; }

pre {
  background: #1e1e1e;
  padding: 1em;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 0.85em;
  line-height: 1.45;
  page-break-inside: avoid;
}

code {
  font-family: "SF Mono", "Fira Code", "Cascadia Code", "Liberation Mono", Consolas, monospace;
  font-size: 0.9em;
}

p code, li code, td code {
  background: #f0f0f0;
  padding: 0.15em 0.3em;
  border-radius: 3px;
  color: #d63384;
}

pre code {
  background: none;
  padding: 0;
  color: #e0e0e0;
  font-size: 1em;
}

table {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
  font-size: 0.95em;
}

th, td {
  border: 1px solid #ddd;
  padding: 0.5em 0.75em;
  text-align: left;
  vertical-align: top;
}

th {
  background: #f0f0f0;
  font-weight: 600;
}

tr:nth-child(even) { background: #f8f8f8; }

ul, ol { margin: 0.5em 0; padding-left: 1.5em; }
li { margin: 0.3em 0; }

hr {
  border: none;
  border-top: 1px solid #ddd;
  margin: 1.5em 0;
}

img {
  max-width: 100%;
  height: auto;
  margin: 1em 0;
}

strong { font-weight: 600; }
em { font-style: italic; }

.cover {
  text-align: center;
  padding-top: 30vh;
}

.cover h1 {
  border: none;
  font-size: 2em;
  margin: 0;
}

.cover p {
  color: #888;
  font-size: 1.1em;
}

@page { margin: 2em; }
h1, h2, h3, h4 { page-break-after: avoid; }
pre, blockquote, table { page-break-inside: avoid; }
'''
    if use_pygments:
        try:
            base += HtmlFormatter(style='monokai').get_style_defs('.codehilite')
            base += '.codehilite { background: none !important; }\n'
            base += '.codehilite .k, .codehilite .kc, .codehilite .kd, .codehilite .kn, .codehilite .kp, .codehilite .kr, .codehilite .kt, .codehilite .ow { font-weight: bold; }\n'
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
                result.append(f'<pre><code{lang_attr}>{escape(chr(10).join(code_buf))}</code></pre>')
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
            t = s[5:]; hid = _slugify(t)
            close_block(); result.append(f'<h4 id="{hid}">{_inline_md(t)}</h4>'); i += 1; continue
        if s.startswith('### '):
            t = s[4:]; hid = _slugify(t)
            close_block(); result.append(f'<h3 id="{hid}">{_inline_md(t)}</h3>'); i += 1; continue
        if s.startswith('## '):
            t = s[3:]; hid = _slugify(t)
            close_block(); result.append(f'<h2 id="{hid}">{_inline_md(t)}</h2>'); i += 1; continue
        if s.startswith('# '):
            t = s[2:]; hid = _slugify(t)
            close_block(); result.append(f'<h1 id="{hid}">{_inline_md(t)}</h1>'); i += 1; continue

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
            if not s2 or s2.startswith('#') or s2.startswith('>') or s2.startswith('- ') or re.match(r'^\d+\.\s', s2) or s2.startswith('```') or s2 == '---' or ('|' in s2 and i + 1 < len(lines) and re.match(r'^[\s|:\-]+$', lines[i + 1].strip())):
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

_KNOWN_HTML_TAGS = frozenset({
    'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'dl', 'dt', 'dd',
    'strong', 'em', 'b', 'i', 'u', 's', 'strike', 'del', 'ins', 'sub', 'sup', 'small', 'big',
    'code', 'pre', 'kbd', 'samp', 'tt', 'var', 'q', 'cite', 'abbr', 'acronym',
    'a', 'img', 'br', 'hr', 'wbr',
    'div', 'span', 'blockquote',
    'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'col', 'colgroup',
    'caption', 'figure', 'figcaption',
    'section', 'article', 'nav', 'header', 'footer', 'main', 'aside',
    'details', 'summary', 'dialog',

    'html', 'head', 'body', 'title', 'meta', 'link', 'style', 'script',
    'nav', 'embed', 'object', 'param', 'source', 'track',
    'iframe', 'canvas', 'svg', 'math',
    'ruby', 'rt', 'rp',
})


class _TextNodeEscaper(html.parser.HTMLParser):
    """HTML parser that escapes non-standard tags for XHTML compliance."""

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
            # Unknown tag — escape it as text
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
    """Escape &, <, > in text nodes for XHTML compliance."""
    parser = _TextNodeEscaper()
    try:
        parser.feed(html_str)
        parser.close()
        return parser.result()
    except Exception:
        # Fallback: escape entire string except known tags
        return re.sub(
            r'<(\/?[a-zA-Z][a-zA-Z0-9]*\b[^>]*)>',
            lambda m: m.group(0),
            html_str.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        )


# ── Syntax highlighting (inline styles for EPUB compat) ────────

def _highlight_html(html):
    if not HAS_PYGMENTS:
        return html

    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer, TextLexer
    from pygments.formatters import HtmlFormatter

    fmt = HtmlFormatter(style='monokai', noclasses=False, nowrap=True)

    def _replace(m):
        pre_tag = m.group(1)
        code_tag = m.group(2)
        code_text = html_unescape(m.group(3))

        lang = ''
        cm = re.search(r'class="[^"]*language-([^"]*)"', code_tag)
        if cm:
            lang = cm.group(1)

        try:
            lexer = get_lexer_by_name(lang, stripall=True) if lang else guess_lexer(code_text[:1024])
        except Exception:
            lexer = TextLexer()

        try:
            highlighted = highlight(code_text, lexer, fmt)
        except Exception:
            return m.group(0)

        return f'<pre style="background:#1e1e1e;padding:1em;border-radius:4px;overflow-x:auto;font-size:0.85em;line-height:1.45;page-break-inside:avoid"><code class="codehilite" style="background:none;padding:0;font-size:1em">{highlighted}</code></pre>'

    html = re.sub(r'(<pre[^>]*>)(<code[^>]*>)(.*?)(</code></pre>)', _replace, html, flags=re.DOTALL)
    return html


# ── Title formatting + slugify ─────────────────────────────────

def _format_title(name):
    """Convert kebab-case or snake_case directory names to Title Case."""
    name = re.sub(r'[-_]', ' ', name)
    return name.strip().title()


def _slugify(text):
    """Convert heading text to HTML anchor ID."""
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
    for line in lines:
        if line.startswith('# ') and line.strip() != '# ':
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
    modules_dir = os.path.join(subject_dir, 'modules')
    if not os.path.isdir(modules_dir):
        print(f"Missing: {modules_dir}", file=sys.stderr)
        sys.exit(1)

    parts = []
    mod_names = sorted(d for d in os.listdir(modules_dir) if os.path.isdir(os.path.join(modules_dir, d)))

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
                            parts.append(f'\n### {q["question"]}\n')
                            for k, v in q.get('options', {}).items():
                                mark = '✓' if k == ans else ' '
                                parts.append(f'- [{mark}] {k}: {v}\n')
                            parts.append(f'\n**Answer:** {ans}\n')
                            parts.append(f'{q.get("explanation", "")}\n')
                except Exception as e:
                    parts.append(f'\n## Quiz: {name}\n\n(quiz parse error: {e})\n')
        elif os.path.isfile(quiz_path):
            parts.append(f'\n## Quiz: {name}\n\n(install yaml library to include quizzes)\n')

    return '\n'.join(parts)


# ── Hierarchical ToC navigation ────────────────────────────────

def _extract_subheadings(content):
    """Extract (level, title, slug) for h2/h3 within chapter content."""
    items = []
    for line in content.split('\n'):
        s = line.strip()
        if s.startswith('## '):
            t = s[3:].strip()
            items.append((2, t, _slugify(t)))
        elif s.startswith('### '):
            t = s[4:].strip()
            items.append((3, t, _slugify(t)))
    return items


def _build_hierarchical_toc(chapters):
    """Build nested (title, href, children) tree from chapters + sub-headings."""
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
    """Render nested heading tree as <ol> HTML."""
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


# ── EPUB generation ────────────────────────────────────────────

def generate_epub(chapters, output_path, title, author='Learn Anything'):
    uid = str(uuid.uuid4())
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    css = make_css(use_pygments=HAS_PYGMENTS)

    parent = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(parent, exist_ok=True)

    xhtml_files = {}
    manifest = []
    spine = []

    cover_html = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{escape(title)}</title><link rel="stylesheet" type="text/css" href="style.css"/></head>
<body class="cover">
<h1>{escape(title)}</h1>
<p>Generated by Learn Anything — {datetime.now().strftime('%Y-%m-%d')}</p>
</body></html>'''
    xhtml_files['cover.xhtml'] = cover_html
    manifest.append(('cover.xhtml', 'application/xhtml+xml', 'cover'))
    spine.append(('cover', True))

    for idx, (ch_title, content) in enumerate(chapters, 1):
        if HAS_MARKDOWN:
            md = _md.Markdown(extensions=['extra', 'toc'], output_format='xhtml')
            html_content = md.convert(content)
        else:
            html_content = fallback_parse(content)
        html_content = _escape_text_nodes(html_content)
        html_content = _highlight_html(html_content)

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

    nav_html = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Table of Contents</title></head>
<body>
<nav epub:type="toc">
<h1>Table of Contents</h1>
{toc_nav_body}
</nav>
</body>
</html>'''
    xhtml_files['nav.xhtml'] = nav_html
    manifest.append(('nav.xhtml', 'application/xhtml+xml', 'nav'))

    opf_manifest = '<item id="css" href="style.css" media-type="text/css"/>\n'
    for fname, mtype, pid in manifest:
        opf_manifest += f'<item id="{pid}" href="{fname}" media-type="{mtype}"/>\n'

    opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="book-id">{escape(uid)}</dc:identifier>
<dc:title>{escape(title)}</dc:title>
<dc:language>en</dc:language>
<dc:creator>{escape(author)}</dc:creator>
<dc:date>{escape(now)}</dc:date>
<meta property="dcterms:modified">{escape(now)}</meta>
</metadata>
<manifest>
{opf_manifest}</manifest>
<spine>
'''
    for pid, linear in spine:
        lin = '' if linear else ' linear="no"'
        opf += f'<itemref idref="{pid}"{lin}/>\n'
    opf += '</spine>\n</package>'

    container = '''<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles>
<rootfile full-path="EPUB/content.opf" media-type="application/oebps-package+xml"/>
</rootfiles>
</container>'''

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        zf.writestr('META-INF/container.xml', container)
        zf.writestr('EPUB/content.opf', opf)
        zf.writestr('EPUB/style.css', css)
        for fname, content in xhtml_files.items():
            zf.writestr(f'EPUB/{fname}', content)


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

    # mimetype
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

    # container.xml
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

    # content.opf
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
    parser = argparse.ArgumentParser(description='EPUB builder for Learn Anything')
    sub = parser.add_subparsers(dest='command')

    p_build = sub.add_parser('build', help='Build EPUB from subject directory')
    p_build.add_argument('subject_dir')
    p_build.add_argument('output')
    p_build.add_argument('--title', default=None)
    p_build.add_argument('--author', default='Learn Anything')

    p_vfy = sub.add_parser('verify', help='Validate EPUB file structure')
    p_vfy.add_argument('epub_file')

    p_md = sub.add_parser('from-md', help='Build EPUB from markdown file')
    p_md.add_argument('markdown_file')
    p_md.add_argument('output')
    p_md.add_argument('--title', default=None)
    p_md.add_argument('--author', default='Learn Anything')

    sub.add_parser('css', help='Print CSS for customization')

    args = parser.parse_args()

    if args.command == 'css':
        print(make_css(use_pygments=False))
        return

    if args.command == 'verify':
        epub = args.epub_file
        if not os.path.isfile(epub):
            print(f"File not found: {epub}", file=sys.stderr)
            sys.exit(1)
        issues, chapters, size = verify_epub(epub)
        print(f"EPUB: {epub}")
        for severity, msg in issues:
            icon = '✓' if severity == 'OK' else ('⚠' if severity == 'WARN' else '✗')
            print(f"  {icon} {severity}: {msg}")
        ch_label = f'{chapters} chapters' if chapters else 'no chapters'
        size_kb = size / 1024
        print(f"  Summary: {ch_label}, {size_kb:.1f} KB")
        fails = sum(1 for s, _ in issues if s == 'FAIL')
        print(f"  Status: {'VALID' if fails == 0 else f'INVALID ({fails} failures)'}")
        sys.exit(0 if fails == 0 else 1)

    if args.command not in ('build', 'from-md'):
        parser.print_help()
        sys.exit(1)

    if args.command == 'build':
        subject_dir = args.subject_dir
        if not os.path.isdir(subject_dir):
            print(f"Subject directory not found: {subject_dir}", file=sys.stderr)
            sys.exit(1)
        title = args.title or _format_title(os.path.basename(os.path.normpath(subject_dir)))
        author = args.author
        md_text = collect_subject_md(subject_dir)
        book_md = os.path.join(subject_dir, 'book.md')
        with open(book_md, 'w', encoding='utf-8') as f:
            f.write(md_text)
        print(f"Intermediate markdown: {book_md}")
    else:
        md_file = args.markdown_file
        if not os.path.isfile(md_file):
            print(f"Markdown file not found: {md_file}", file=sys.stderr)
            sys.exit(1)
        title = args.title or _format_title(os.path.splitext(os.path.basename(md_file))[0])
        author = args.author
        with open(md_file, 'r', encoding='utf-8') as f:
            md_text = f.read()

    output = args.output
    chapters = split_chapters(md_text)
    if not chapters:
        chapters = [(title, md_text)]
    generate_epub(chapters, output, title, author)
    size_kb = os.path.getsize(output) / 1024
    print(f"EPUB: {output} ({len(chapters)} chapters, {size_kb:.1f} KB)")


if __name__ == '__main__':
    main()
