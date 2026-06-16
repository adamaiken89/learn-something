#!/usr/bin/env python3
"""Generate EPUB 3 from markdown. Zero external dependencies.

Usage: epubgen.py input.md output.epub "Title" ["Author"]
"""

import sys
import os
import re
import uuid
import zipfile
from xml.sax.saxutils import escape
from datetime import datetime


def inline_md(text):
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img alt="\1" src="\2"/>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    return text


def md_to_html(text):
    lines = text.split('\n')
    result = []
    i = 0
    in_code = False
    code_buf = []
    in_bq = False
    in_ul = False

    def close_block():
        nonlocal in_bq, in_ul
        if in_bq:
            result.append('</blockquote>')
            in_bq = False
        if in_ul:
            result.append('</ul>')
            in_ul = False

    def add_bq(content):
        nonlocal in_bq
        if not in_bq:
            result.append('<blockquote>')
            in_bq = True
        if content:
            result.append(f'<p>{inline_md(content)}</p>')

    def add_li(content):
        nonlocal in_ul
        if not in_ul:
            result.append('<ul>')
            in_ul = True
        result.append(f'<li>{inline_md(content)}</li>')

    while i < len(lines):
        s = lines[i].strip()

        if s.startswith('```'):
            if in_code:
                result.append(f'<pre><code>{escape(chr(10).join(code_buf))}</code></pre>')
                code_buf = []
                in_code = False
            else:
                in_code = True
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

        if s.startswith('### '):
            close_block()
            result.append(f'<h3>{inline_md(s[4:])}</h3>')
            i += 1
            continue
        if s.startswith('## '):
            close_block()
            result.append(f'<h2>{inline_md(s[3:])}</h2>')
            i += 1
            continue
        if s.startswith('# '):
            close_block()
            result.append(f'<h1>{inline_md(s[2:])}</h1>')
            i += 1
            continue

        if s.startswith('>'):
            add_bq(s.lstrip('> ').strip())
            i += 1
            continue
        elif in_bq:
            result.append('</blockquote>')
            in_bq = False

        if s.startswith('- '):
            add_li(s[2:])
            i += 1
            continue
        elif in_ul:
            result.append('</ul>')
            in_ul = False

        para = []
        while i < len(lines):
            s2 = lines[i].strip()
            if not s2 or s2.startswith('#') or s2.startswith('>') or s2.startswith('- ') or s2.startswith('```') or s2 == '---':
                break
            para.append(lines[i].strip())
            i += 1
        if para:
            result.append(f'<p>{" ".join(para)}</p>')
            continue

        i += 1

    close_block()
    if in_code:
        result.append(f'<pre><code>{escape(chr(10).join(code_buf))}</code></pre>')

    return '\n'.join(result)


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


def generate_epub(chapters, output_path, title, author='Learn Anything'):
    uid = str(uuid.uuid4())
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

    css = (
        'body { font-family: Georgia, serif; line-height: 1.6; margin: 1em 2em; max-width: 40em; }\n'
        'h1, h2, h3 { font-family: Helvetica, Arial, sans-serif; }\n'
        'h1 { border-bottom: 2px solid #333; padding-bottom: 0.3em; }\n'
        'h2 { color: #444; margin-top: 1.5em; }\n'
        'h3 { color: #666; }\n'
        'blockquote { border-left: 3px solid #ccc; margin: 1em 0; padding: 0.5em 1em; color: #555; background: #f9f9f9; }\n'
        'pre { background: #f5f5f5; padding: 1em; border: 1px solid #ddd; overflow-x: auto; }\n'
        'code { background: #f5f5f5; padding: 0.15em 0.3em; font-size: 0.9em; }\n'
        'pre code { background: none; padding: 0; }\n'
        'ul { margin: 0.5em 0; }\n'
        'li { margin: 0.3em 0; }\n'
        'hr { border: none; border-top: 1px solid #ddd; margin: 2em 0; }\n'
        'img { max-width: 100%; height: auto; }\n'
        '.cover { text-align: center; padding-top: 20%; }\n'
        '.cover h1 { border: none; font-size: 2em; }\n'
        '.cover p { color: #666; }\n'
    )

    parent = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(parent, exist_ok=True)

    xhtml_files = {}
    manifest = []
    spine = []
    nav_items = []

    cover_html = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">\n'
        '<head><title>' + escape(title) + '</title><link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
        '<body class="cover">\n'
        '<h1>' + escape(title) + '</h1>\n'
        '<p>Generated by Learn Anything — ' + datetime.now().strftime('%Y-%m-%d') + '</p>\n'
        '</body>\n</html>'
    )
    xhtml_files['cover.xhtml'] = cover_html
    manifest.append(('cover.xhtml', 'application/xhtml+xml', 'cover'))
    spine.append(('cover', True))

    for idx, (ch_title, content) in enumerate(chapters, 1):
        html_content = md_to_html(content)
        filename = f'ch{idx:03d}.xhtml'
        pid = f'ch{idx}'

        page = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml">\n'
            '<head><title>' + escape(ch_title) + '</title><link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
            '<body>\n' + html_content + '\n</body>\n</html>'
        )

        xhtml_files[filename] = page
        manifest.append((filename, 'application/xhtml+xml', pid))
        spine.append((pid, True))
        nav_items.append((filename, ch_title))

    nav_html = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">\n'
        '<head><title>Table of Contents</title></head>\n'
        '<body>\n<nav epub:type="toc">\n<h1>Table of Contents</h1>\n<ol>\n'
    )
    for fname, ch_title in nav_items:
        nav_html += f'<li><a href="{fname}">{escape(ch_title)}</a></li>\n'
    nav_html += '</ol>\n</nav>\n</body>\n</html>'

    xhtml_files['nav.xhtml'] = nav_html
    manifest.append(('nav.xhtml', 'application/xhtml+xml', 'nav'))

    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        '<dc:identifier id="book-id">' + escape(uid) + '</dc:identifier>\n'
        '<dc:title>' + escape(title) + '</dc:title>\n'
        '<dc:language>en</dc:language>\n'
        '<dc:creator>' + escape(author) + '</dc:creator>\n'
        '<dc:date>' + escape(now) + '</dc:date>\n'
        '<meta property="dcterms:modified">' + escape(now) + '</meta>\n'
        '</metadata>\n'
        '<manifest>\n'
        '<item id="css" href="style.css" media-type="text/css"/>\n'
    )
    for fname, mtype, pid in manifest:
        opf += f'<item id="{pid}" href="{fname}" media-type="{mtype}"/>\n'
    opf += '</manifest>\n<spine>\n'
    for pid, _ in spine:
        opf += f'<itemref idref="{pid}"/>\n'
    opf += '</spine>\n</package>'

    container = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        '<rootfiles>\n'
        '<rootfile full-path="EPUB/content.opf" media-type="application/oebps-package+xml"/>\n'
        '</rootfiles>\n'
        '</container>'
    )

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        zf.writestr('META-INF/container.xml', container)
        zf.writestr('EPUB/content.opf', opf)
        zf.writestr('EPUB/style.css', css)
        for fname, content in xhtml_files.items():
            zf.writestr(f'EPUB/{fname}', content)

    return len(nav_items)


def main():
    if len(sys.argv) < 4:
        print(f'Usage: {sys.argv[0]} input.md output.epub "Title" ["Author"]', file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    title = sys.argv[3]
    author = sys.argv[4] if len(sys.argv) > 4 else 'Learn Anything'

    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()

    chapters = split_chapters(text)
    if not chapters:
        chapters = [(title, text)]

    count = generate_epub(chapters, output_path, title, author)
    print(f'EPUB: {output_path} ({count} chapters)')


if __name__ == '__main__':
    main()
