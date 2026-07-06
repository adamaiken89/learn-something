"""Enrich existing lessons with learning science interventions.

Adds cloze deletions, predict-next blocks, error-spotting exercises,
and Mermaid diagrams to existing lesson.md files via LLM.
"""

import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

_API_URL = 'https://api.deepseek.com/chat/completions'
_MODEL = 'deepseek-chat'
_DEFAULT_TYPES = ['cloze', 'predict', 'error', 'diagram', 'mindmap', 'cloze-quiz']

_TYPE_PROMPTS = {
    'cloze': (
        'Add 3-5 cloze deletions ({term} blanks) to this lesson. '
        'Insert after key concept explanations. '
        'Format: `> **Cloze**: "...{blank}..." — *Answer: term*`\n'
        'Return the full lesson with cloze markers inserted inline.'
    ),
    'predict': (
        'Add 2-3 predict-next blocks to this lesson. '
        'Place after each causal chain explanation, before revealing the outcome. '
        'Format: `> **Predict**: [causal question]?\n> *Answer: [explanation]*`\n'
        'Return the full lesson with predict blocks inserted.'
    ),
    'error': (
        'Add 1-2 "Spot the Mistake" exercises to this lesson. '
        "Present a plausible wrong solution, then ask what's wrong. "
        "Format: `> **Spot the Mistake**: [scenario with error]\n> What's wrong?\n> *Answer: [explanation]*`\n"
        'Return the full lesson with exercises inserted.'
    ),
    'diagram': (
        'Add mermaid diagrams to this lesson for concepts where diagrams would help understanding. '
        'Focus on relationships, workflows, branching logic, or causal chains. '
        'Format: ```mermaid\n[diagram code]\n```\n'
        'Return the full lesson with diagrams inserted before relevant sections.'
    ),
    'mindmap': (
        'Add a Mermaid mindmap at the top of this lesson (after metadata, before Learning Objectives). '
        "Show the module's knowledge hierarchy: central concept → key topics → sub-concepts. "
        'Use `mindmap` syntax. Max 3 levels deep. Keep concise. '
        'Format: ```mermaid\nmindmap\n  root((Title))\n    Topic\n      Sub\n```\n'
        'Return the full lesson with mindmap inserted at top.'
    ),
    'cloze-quiz': (
        'Generate 8-10 cloze (fill-in-blank) questions from this lesson. '
        'Each question tests key terms, concepts, or relationships. '
        'Use {blank} to mark the term to fill in. '
        'Difficulty distribution: 40% d1 (recall), 40% d2 (comprehension), 20% d3 (application). '
        'Format as YAML array:\n'
        '- id: "c.1"\n'
        '  question: "Complete: [sentence with {blank}]"\n'
        '  answer: "[blank term]"\n'
        '  explanation: "[Why this term matters]"\n'
        '  difficulty: 1\n'
        '  tags: [terminology]\n\n'
        'Return ONLY the YAML array, no markdown fencing or explanation.'
    ),
}


def _api_key():
    key = os.environ.get('LEARN_ANYTHING_API_KEY')
    if key:
        return key
    config_path = Path.home() / '.config' / 'learn-something' / 'config.json'
    if config_path.exists():
        try:
            with open(config_path) as f:
                cfg = json.load(f)
                return cfg.get('api_key')
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def _call_llm(
    prompt,
    system_prompt='You are a learning science expert. Enhance lessons with evidence-based interventions.',
):
    key = _api_key()
    if not key:
        print(
            'Error: No API key found. Set LEARN_SOMETHING_API_KEY env var or create ~/.config/learn-something/config.json',
            file=sys.stderr,
        )
        print('Format: {"api_key": "sk-..."}', file=sys.stderr)
        sys.exit(1)

    payload = json.dumps(
        {
            'model': _MODEL,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.3,
            'max_tokens': 8192,
        }
    ).encode()

    req = urllib.request.Request(
        _API_URL,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {key}',
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
        return result['choices'][0]['message']['content']
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f'API error {e.code}: {body}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error calling LLM: {e}', file=sys.stderr)
        sys.exit(1)


def _backup(path):
    bak = path.with_suffix('.md.bak')
    shutil.copy2(path, bak)
    return bak


def enrich_lesson(lesson_path, types=None, dry_run=False, render_mode='api'):
    """Add enrichment sections to a lesson.md file.

    Args:
        lesson_path: Path to lesson.md
        types: List of enrichment types (default: all)
        dry_run: If True, print diff instead of writing
        render_mode: Diagram render mode ('api', 'local', or 'off')
    """
    lesson_path = Path(lesson_path)
    if not lesson_path.exists():
        print(f'Error: {lesson_path} not found', file=sys.stderr)
        sys.exit(1)

    types = types or _DEFAULT_TYPES
    original = lesson_path.read_text()

    for t in types:
        if t not in _TYPE_PROMPTS:
            print(f'Unknown type: {t}. Valid: {_DEFAULT_TYPES}', file=sys.stderr)
            sys.exit(1)

    # Separate cloze-quiz from other types (writes to cloze.yaml, not lesson.md)
    cloze_quiz_types = [t for t in types if t == 'cloze-quiz']
    lesson_types = [t for t in types if t != 'cloze-quiz']

    for t in lesson_types:
        prompt = (
            f'Current lesson content:\n\n{original}\n\n'
            f'Task: {_TYPE_PROMPTS[t]}\n\n'
            'Keep ALL existing content verbatim. Only add new elements.'
        )
        system = (
            'You are a learning science expert. Add retrieval practice and active learning '
            'interventions to lessons. Output only the enhanced markdown, no explanation.'
        )
        print(f'  Enriching: {t}...', end=' ', flush=True)
        result = _call_llm(prompt, system)
        original = result
        print('done')

    # Handle cloze-quiz: generate cloze.yaml
    if cloze_quiz_types:
        cloze_path = lesson_path.parent / 'cloze.yaml'
        prompt = f'Current lesson content:\n\n{original}\n\nTask: {_TYPE_PROMPTS["cloze-quiz"]}\n\n'
        system = (
            'You are a learning science expert. Generate cloze questions from lesson content. '
            'Output only the YAML array, no explanation.'
        )
        print('  Generating: cloze.yaml...', end=' ', flush=True)
        result = _call_llm(prompt, system)

        # Clean up: strip markdown fencing if present
        result = result.strip()
        if result.startswith('```'):
            result = result.split('\n', 1)[1] if '\n' in result else result[3:]
        if result.endswith('```'):
            result = result[:-3]
        result = result.strip()

        if dry_run:
            print('\n--- cloze.yaml preview ---')
            print(result[:500])
            print('...')
        else:
            with open(cloze_path, 'w') as f:
                f.write(result + '\n')
            print('done')
            print(f'  Written: {cloze_path}')

    # Only write lesson.md if lesson types were processed
    if lesson_types:
        if dry_run:
            print('\n--- DIFF ---')
            if original != lesson_path.read_text():
                # Simple diff: show first 500 chars
                print(original[:500])
                print('...')
            else:
                print('(no changes)')
            return

        bak = _backup(lesson_path)
        lesson_path.write_text(original)
        print(f'  Backup: {bak}')
        print(f'  Written: {lesson_path}')

        # Auto-render diagrams if 'diagram' type was enriched
        if 'diagram' in types and render_mode != 'off':
            try:
                from render_diagrams import render_lesson_diagrams

                count = render_lesson_diagrams(str(lesson_path), mode=render_mode)
                if count:
                    print(f'  Rendered {count} diagram(s) to PNG')
                else:
                    print('  (no mermaid blocks found to render)')
            except ImportError:
                print('  (render_diagrams.py not available, skipping PNG render)')
            except Exception as e:
                print(f'  (diagram render error: {e})')
    elif dry_run:
        print('(no lesson.md changes)')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Enrich lessons with learning science interventions'
    )
    parser.add_argument('path', help='Path to lesson.md')
    parser.add_argument('--types', nargs='+', choices=_DEFAULT_TYPES, default=_DEFAULT_TYPES)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument(
        '--render-mode',
        choices=['api', 'local', 'off'],
        default='api',
        help='Diagram render mode (default: api)',
    )
    args = parser.parse_args()
    enrich_lesson(args.path, args.types, args.dry_run, args.render_mode)
