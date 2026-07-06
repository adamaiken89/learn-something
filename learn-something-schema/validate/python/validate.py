#!/usr/bin/env python3
"""
Validate learn-something data files against shared JSON schemas.

Usage:
    python validate.py deck <path_to_deck.json>
    python validate.py quiz <path_to_quiz.yaml>
    python validate.py syllabus <path_to_syllabus.yaml>
    python validate.py stats <path_to_stats.json>
    python validate.py feedback <path_to_feedback.json>
"""

import json
import sys
from pathlib import Path

SCHEMA_DIR = Path(__file__).parent.parent.parent / 'schemas'


def load_schema(name: str) -> dict:
    schema_path = SCHEMA_DIR / f'{name}.schema.json'
    if not schema_path.exists():
        raise FileNotFoundError(f'Schema not found: {schema_path}')
    with open(schema_path) as f:
        return json.load(f)


def validate_json(data: dict, schema_name: str) -> list[str]:
    """Validate data against a JSON schema. Returns list of errors (empty = valid)."""
    try:
        import jsonschema
    except ImportError:
        return ['jsonschema not installed. Run: pip install jsonschema']

    schema = load_schema(schema_name)
    validator = jsonschema.Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = '.'.join(str(p) for p in error.absolute_path)
        prefix = f'{path}: ' if path else ''
        errors.append(f'{prefix}{error.message}')
    return errors


def validate_yaml_file(filepath: str, schema_name: str) -> list[str]:
    """Load YAML file and validate against schema."""
    try:
        import yaml
    except ImportError:
        return ['PyYAML not installed. Run: pip install pyyaml']

    path = Path(filepath)
    if not path.exists():
        return [f'File not found: {filepath}']

    with open(path) as f:
        data = yaml.safe_load(f)

    return validate_json(data, schema_name)


def validate_json_file(filepath: str, schema_name: str) -> list[str]:
    """Load JSON file and validate against schema."""
    path = Path(filepath)
    if not path.exists():
        return [f'File not found: {filepath}']

    with open(path) as f:
        data = json.load(f)

    return validate_json(data, schema_name)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    schema_name = sys.argv[1]
    filepath = sys.argv[2]

    valid_schemas = ['deck', 'quiz', 'cumulative_quiz', 'syllabus', 'stats', 'feedback', 'card', 'question', 'cumulative_question', 'cloze_quiz', 'cloze_question']
    if schema_name not in valid_schemas:
        print(f'Unknown schema: {schema_name}')
        print(f'Valid schemas: {", ".join(valid_schemas)}')
        sys.exit(1)

    # Determine file type
    path = Path(filepath)
    if path.suffix in ('.yaml', '.yml'):
        errors = validate_yaml_file(filepath, schema_name)
    elif path.suffix == '.json':
        errors = validate_json_file(filepath, schema_name)
    else:
        print(f'Unsupported file type: {path.suffix}')
        sys.exit(1)

    if errors:
        print(f'INVALID — {len(errors)} error(s):')
        for err in errors:
            print(f'  - {err}')
        sys.exit(1)
    else:
        print('VALID')
        sys.exit(0)


if __name__ == '__main__':
    main()
