#!/usr/bin/env python3
"""Tests for scripts/epub.py"""

import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import epub


def test_format_title():
    assert epub._format_title('advanced-react-19') == 'Advanced React 19'
    assert epub._format_title('python-basics') == 'Python Basics'
    assert epub._format_title('intro_to_ml') == 'Intro To Ml'
    assert epub._format_title('Normal Title') == 'Normal Title'
    assert epub._format_title('already-title-case') == 'Already Title Case'
    assert epub._format_title('a') == 'A'
    assert epub._format_title('') == ''
    print('  _format_title: OK')


def test_format_title_edge():
    # multiple dashes become multiple spaces (acceptable)
    name = epub._format_title('multiple--dashes')
    assert 'Multiple' in name and 'Dashes' in name
    # trailing dash becomes trailing space (stripped by .strip())
    assert epub._format_title('trailing-dash-') == 'Trailing Dash'
    # mixed separators
    name = epub._format_title('_-mixed-_')
    assert 'Mixed' in name
    print('  _format_title edge: OK')


def test_slugify():
    assert epub._slugify('Bond Pricing') == 'bond-pricing'
    assert epub._slugify('Hello World!') == 'hello-world'
    assert epub._slugify('What is Python?') == 'what-is-python'
    assert epub._slugify('a/b/c') == 'abc'
    assert epub._slugify('  spaces  ') == 'spaces'
    assert epub._slugify('Single') == 'single'
    print('  _slugify: OK')


def test_slugify_special_chars():
    assert epub._slugify('Price (90% of par)') == 'price-90-of-par'
    assert epub._slugify("Don't panic") == 'dont-panic'
    assert epub._slugify('Section 1.2.3') == 'section-123'
    print('  _slugify special chars: OK')


def test_extract_subheadings():
    content = """Intro text.

## Sub One
Content.

### Subsub
Details.

## Sub Two
More.
"""
    items = epub._extract_subheadings(content)
    assert len(items) == 3
    assert items[0] == (2, 'Sub One', 'sub-one')
    assert items[1] == (3, 'Subsub', 'subsub')
    assert items[2] == (2, 'Sub Two', 'sub-two')
    print('  _extract_subheadings: OK')


def test_extract_subheadings_h1_ignored():
    content = "# H1 Should Be Ignored\n\n## Real Sub\nContent."
    items = epub._extract_subheadings(content)
    assert len(items) == 1
    assert items[0][1] == 'Real Sub'
    print('  _extract_subheadings h1 ignored: OK')


def test_extract_subheadings_empty():
    assert epub._extract_subheadings('No headings') == []
    assert epub._extract_subheadings('') == []
    assert epub._extract_subheadings('##  ') == []  # empty title
    print('  _extract_subheadings empty: OK')


def test_build_hierarchical_toc():
    chapters = [
        ('Module 1: Intro', "## Getting Started\nContent.\n### Setup\nMore."),
        ('Module 2: Advanced', "## Deep Topic\nDetails.\n"),
    ]
    tree = epub._build_hierarchical_toc(chapters)
    assert len(tree) == 2

    ch1 = tree[0]
    assert ch1[0] == 'Module 1: Intro'
    assert ch1[1] == 'ch001.xhtml'
    children = ch1[2]
    assert len(children) == 1, f'Expected 1 child, got {len(children)}'
    # Setup nested under Getting Started (h3 under h2)
    gs = children[0]
    assert gs[0] == 'Getting Started'
    assert gs[1] == 'ch001.xhtml#getting-started'
    assert len(gs[2]) == 1
    assert gs[2][0] == ('Setup', 'ch001.xhtml#setup', [])

    ch2 = tree[1]
    assert ch2[0] == 'Module 2: Advanced'
    assert ch2[1] == 'ch002.xhtml'
    assert len(ch2[2]) == 1
    assert ch2[2][0][0] == 'Deep Topic'
    print('  _build_hierarchical_toc: OK')


def test_build_hierarchical_toc_no_subheadings():
    chapters = [('Single', 'Just text.'), ('Second', 'More text.')]
    tree = epub._build_hierarchical_toc(chapters)
    assert len(tree) == 2
    assert tree[0][2] == []
    assert tree[1][2] == []
    print('  _build_hierarchical_toc no subs: OK')


def test_build_hierarchical_toc_deep_nesting():
    chapters = [('Ch1', "## A\n### A.1\n#### A.1.a\n## B\n")]
    tree = epub._build_hierarchical_toc(chapters)
    assert len(tree) == 1
    children = tree[0][2]
    assert len(children) == 2
    assert children[0][0] == 'A'
    # A's children
    a_children = children[0][2]
    assert len(a_children) == 1
    assert a_children[0][0] == 'A.1'
    print('  _build_hierarchical_toc deep nesting: OK')


def test_render_toc_nav():
    tree = [
        ('Ch1', 'ch001.xhtml', [
            ('Sub1', 'ch001.xhtml#sub1', []),
            ('Sub2', 'ch001.xhtml#sub2', [
                ('Subsub', 'ch001.xhtml#subsub', []),
            ]),
        ]),
        ('Ch2', 'ch002.xhtml', []),
    ]
    html = epub._render_toc_nav(tree)
    assert 'Ch1' in html
    assert 'href="ch001.xhtml#sub1"' in html
    assert 'href="ch001.xhtml#subsub"' in html
    assert 'href="ch002.xhtml"' in html
    assert html.count('<ol>') == 3  # root + sub2 + subsub
    assert html.startswith('<ol>')
    assert html.endswith('</ol>')
    print('  _render_toc_nav: OK')


def test_render_toc_nav_empty():
    assert epub._render_toc_nav([]) == ''
    print('  _render_toc_nav empty: OK')


def test_render_toc_nav_escapes():
    tree = [('Title & <special>', 'ch001.xhtml', [])]
    html = epub._render_toc_nav(tree)
    assert '&amp;' in html
    assert '&lt;' in html
    assert '<special>' not in html  # should be escaped
    print('  _render_toc_nav escapes: OK')


def test_fallback_parse_id_on_headings():
    md = '# H1\n\n## H2\n\n### H3\n\n#### H4'
    html = epub.fallback_parse(md)
    assert 'id="h1"' in html
    assert 'id="h2"' in html
    assert 'id="h3"' in html
    assert 'id="h4"' in html
    print('  fallback_parse heading ids: OK')


def test_fallback_parse_content_preserved():
    md = '# Title\n\nPara text.\n\n## Sub\n\nMore text.'
    html = epub.fallback_parse(md)
    assert '<h1' in html
    assert 'Title' in html
    assert '<h2' in html
    assert 'Sub' in html
    assert 'Para text.' in html
    assert 'More text.' in html
    print('  fallback_parse content preserved: OK')


def test_generate_epub_hierarchical_toc():
    chapters = [
        ('Chapter One', '## First Sub\nText.\n### Subsub\nMore.'),
        ('Chapter Two', '## Second Sub\nText.'),
    ]
    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
        outpath = f.name
    try:
        epub.generate_epub(chapters, outpath, 'Test Book', 'Test Author')

        issues, ch_count, size = epub.verify_epub(outpath)
        fails = [s for s, _ in issues if s == 'FAIL']
        assert not fails, f'Verify failures: {fails}'
        assert ch_count == 2
        assert size > 0

        with zipfile.ZipFile(outpath, 'r') as zf:
            nav = zf.read('EPUB/nav.xhtml').decode('utf-8')
            assert 'Chapter One' in nav
            assert 'Chapter Two' in nav
            assert 'First Sub' in nav
            assert 'Subsub' in nav
            assert 'href="ch001.xhtml#first-sub"' in nav
            assert 'href="ch001.xhtml#subsub"' in nav
            assert 'href="ch002.xhtml#second-sub"' in nav
            assert nav.count('<ol>') >= 2

            ch1 = zf.read('EPUB/ch001.xhtml').decode('utf-8')
            assert 'id="chapter-one"' in ch1

            ch2 = zf.read('EPUB/ch002.xhtml').decode('utf-8')
            assert 'id="chapter-two"' in ch2
    finally:
        os.unlink(outpath)
    print('  generate_epub hierarchical ToC: OK')


def test_generate_epub_empty_chapters():
    chapters = [('Only Chapter', '')]
    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
        outpath = f.name
    try:
        epub.generate_epub(chapters, outpath, 'Empty Test')
        issues, ch_count, _ = epub.verify_epub(outpath)
        fails = [s for s, _ in issues if s == 'FAIL']
        assert not fails
        assert ch_count == 1
    finally:
        os.unlink(outpath)
    print('  generate_epub empty chapters: OK')


def test_generate_epub_no_chapters():
    chapters = []
    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
        outpath = f.name
    try:
        epub.generate_epub(chapters, outpath, 'Empty Book')
        with zipfile.ZipFile(outpath, 'r') as zf:
            names = zf.namelist()
            assert 'EPUB/nav.xhtml' in names
            nav = zf.read('EPUB/nav.xhtml').decode('utf-8')
            # empty tree -> fallback empty ol
            assert '<ol>' in nav
            assert '</ol>' in nav
    finally:
        os.unlink(outpath)
    print('  generate_epub no chapters: OK')


def test_verify_epub_corrupt():
    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
        f.write(b'not a zip file')
        outpath = f.name
    try:
        issues, ch_count, size = epub.verify_epub(outpath)
        assert any('Not a valid ZIP' in m for _, m in issues)
    finally:
        os.unlink(outpath)
    print('  verify_epub corrupt: OK')


def test_split_chapters():
    md = '# Chapter 1\n\nText.\n\n# Chapter 2\n\nMore.'
    chapters = epub.split_chapters(md)
    assert len(chapters) == 2
    assert chapters[0][0] == 'Chapter 1'
    assert chapters[1][0] == 'Chapter 2'
    print('  split_chapters: OK')


def test_split_chapters_single():
    md = '# Only Chapter\n\nText.'
    chapters = epub.split_chapters(md)
    assert len(chapters) == 1
    assert chapters[0][0] == 'Only Chapter'
    print('  split_chapters single: OK')


def test_split_chapters_no_h1():
    md = '## Not h1\n\nText.'
    chapters = epub.split_chapters(md)
    assert len(chapters) == 0
    print('  split_chapters no h1: OK')


def test_escape_text_nodes():
    html = '<p>Hello & welcome</p>'
    result = epub._escape_text_nodes(html)
    assert '&amp;' in result
    print('  _escape_text_nodes: OK')


def test_inline_md():
    # inline MD in list items (processed by _inline_md)
    md = '- **bold** and *italic* and `code` and [link](http://x.com).'
    html = epub.fallback_parse(md)
    assert '<strong>bold</strong>' in html
    assert '<em>italic</em>' in html
    assert '<code>code</code>' in html
    assert '<a href="http://x.com">link</a>' in html
    print('  inline_md: OK')


if __name__ == '__main__':
    tests = [
        test_format_title,
        test_format_title_edge,
        test_slugify,
        test_slugify_special_chars,
        test_extract_subheadings,
        test_extract_subheadings_h1_ignored,
        test_extract_subheadings_empty,
        test_build_hierarchical_toc,
        test_build_hierarchical_toc_no_subheadings,
        test_build_hierarchical_toc_deep_nesting,
        test_render_toc_nav,
        test_render_toc_nav_empty,
        test_render_toc_nav_escapes,
        test_fallback_parse_id_on_headings,
        test_fallback_parse_content_preserved,
        test_generate_epub_hierarchical_toc,
        test_generate_epub_empty_chapters,
        test_generate_epub_no_chapters,
        test_verify_epub_corrupt,
        test_split_chapters,
        test_split_chapters_single,
        test_split_chapters_no_h1,
        test_escape_text_nodes,
        test_inline_md,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f'  FAIL {test.__name__}: {e}')
            failed += 1
    total = len(tests)
    passed = total - failed
    print(f'\n{passed}/{total} passed')
    sys.exit(1 if failed else 0)
