# @learn-something/schema

Shared JSON Schema definitions for the learn-something ecosystem. Both the CLI (`learn.py`) and the desktop reader validate against these schemas.

## Schemas

| Schema     | File                           | Description                        |
| ---------- | ------------------------------ | ---------------------------------- |
| `deck`     | `schemas/deck.schema.json`     | SRS card deck (`srs/deck.json`)    |
| `card`     | `schemas/card.schema.json`     | Individual SRS card                |
| `quiz`     | `schemas/quiz.schema.json`     | Quiz questions (`quiz.yaml`)       |
| `question` | `schemas/question.schema.json` | Single quiz question               |
| `syllabus` | `schemas/syllabus.schema.json` | Course syllabus (`syllabus.yaml`)  |
| `stats`    | `schemas/stats.schema.json`    | Session history (`srs/stats.json`) |
| `feedback` | `schemas/feedback.json`        | Module ratings and flags           |

## Key Design Decisions

- **camelCase** — all field names use camelCase (matches Reader convention)
- **Card ID** — `{courseId}-{moduleId}-{questionId}` (matches Reader format)
- **Quiz keys** — lowercase `a-d` (matches Reader)
- **deck.json** — `{cards: Record<string, Card>}` object structure (matches Reader)
- **date-time** — ISO 8601 format

## Validation

### Python

```bash
pip install jsonschema pyyaml
python validate/python/validate.py deck path/to/deck.json
python validate/python/validate.py quiz path/to/quiz.yaml
python validate/python/validate.py syllabus path/to/syllabus.yaml
```

### TypeScript

```typescript
import { validateDeck, validateQuiz } from '@learn-something/schema/validate';

const errors = validateDeck(deckData);
if (errors.length > 0) {
  console.error('Invalid deck:', errors);
}
```

## Versioning

- Schema version: `1.0.0`
- Breaking changes bump major version
- Each schema has a `$id` URL for identification
- Both tools pin schema version and validate on load

## Migration from Legacy Formats

The CLI's legacy format (array-based deck, uppercase quiz keys, snake_case fields) is automatically converted to v1 on first load when `--validate` is used.
