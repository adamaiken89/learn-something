# Learn Something

Structured learning framework for any subject — study via CLI with spaced repetition (FSRS-5). Three-theory pedagogy: Marva Collins, Feynman Technique, Desirable Difficulties.

Full spec: creation protocol, pedagogy, session types, subject schema, quality rules → `SKILL.md`. Learner session quick-reference → `study-protocol.md`.

## Prerequisites

- Python 3.8+ (stdlib only; `pip install pyyaml` recommended for quizzes)
- Node.js + **mermaid-cli** for mermaid diagram validation (hard requirement, no fallback):
  ```
  npm install -g @mermaid-js/mermaid-cli
  ```
- Dev only: `ruff` (lint + format gate — see [CONVENTIONS.md](CONVENTIONS.md)):
  ```
  pip install --break-system-packages ruff
  ```

## Quick Start

1. **Trigger creation**: Say `I want to learn [topic]` or `learn.sh init <subject>`
2. **Study**: `learn.sh start <subject>` → `learn.sh quiz <subject> <module>`
3. **Review daily**: `learn.sh review <subject>`

## CLI Commands

```
learn.sh init <subject> [lang]   Create new subject (en|zh|yue)
learn.sh start <subject>         Show overview + modules
learn.sh create-module <subject> <NN-name>
learn.sh quiz <subject> <mod>    MCQ drill
learn.sh cloze <subject> <mod>   Fill-in-blank drill
learn.sh explain <subject> <mod> Feynman technique prompt
learn.sh feynman <subject> <mod> Alias for explain
learn.sh review <subject>        FSRS-5 spaced repetition
learn.sh stats <subject>         Progress + retention
learn.sh export <subject>        Anki CSV export
learn.sh epub <subject> [file]   Export course to EPUB book
learn.sh balance-quiz <subject> <mod>  Re-letter quiz answers: balanced, no 3-run (idempotent)
learn.sh checksyntax <subject> <mod>   Lint lesson.md: mermaid + code blocks + fences
learn.sh validate <subject>      Full quality gate (schema + content + rules)
```

## EPUB Generation

After creating course content, generate portable EPUB book:

```
learn.sh epub <subject>              # Full build: assemble + generate
learn.sh epub-regen <subject>        # Regenerate from cached book.md (faster)
learn.sh epub-verify <subject>       # Validate EPUB structure
```

### Agent workflow

1. Create all modules via content creation protocol (SKILL.md Part A4)
2. Run `learn.sh epub <subject>` to assemble lessons + quizzes into single EPUB
   - Script collects all `lesson.md` + `quiz.yaml` → writes `book.md` → generates EPUB
3. Run `learn.sh epub-verify <subject>` to validate output
4. To update after module edits: `learn.sh epub-regen <subject>` (skips assembly)

Manual alternative: `epub.py build <subject-dir> <output>` or `epub.py from-md <book.md> <output>`.

## Cost Model

Powered by **DeepSeek V4 Flash**.

| Phase                    | Cost    |
| ------------------------ | ------- |
| Scope + syllabus         | ~$0.01  |
| Per module (~15K tokens) | ~$0.004 |
| Full course (20 modules) | ~$0.08  |
| Per study session        | $0      |

## License

MIT
