# Learn Something — Agent Modification Guide

## Skill Structure

```
learn-something/
├── SKILL.md           # Frontmatter metadata + main instruction body
├── study-protocol.md  # Learner-facing protocol reference
├── README.md          # General documentation
├── LICENSE            # MIT
├── AGENTS.md          # This file — agent modification guide
├── learn-something-schema/  # Shared JSON schemas (Phase 1)
│   ├── package.json
│   ├── schemas/       # JSON Schema files (deck, card, quiz, question, cloze_question, cloze_quiz, cumulative_question, cumulative_quiz, syllabus, stats, feedback)
│   ├── types/         # TypeScript type definitions
│   └── validate/      # Python + TypeScript validators
├── scripts/
│   ├── learn.sh       # Thin bash wrapper → delegates to learn.py
│   ├── learn.py       # Python CLI (FSRS, quiz engine, all commands)
│   ├── sm2.py         # FSRS-5 algorithm (replaces SM-2)
│   ├── enrich.py      # LLM-based lesson enrichment (cloze/predict/error/diagram/mindmap)
│   ├── render_diagrams.py  # Mermaid → PNG renderer (mmdc CLI or mermaid.ink API)
│   ├── migrate_courses.py  # Normalize legacy/invalid course YAML to canonical shapes (idempotent, --apply)
│   ├── epub.py        # EPUB 3 generator (zero-dep + optional extras)
│   └── pdf.py         # PDF generator (zero-dep + optional engines)
└── templates/
    ├── syllabus.yaml  # 20-module course skeleton
    ├── module.md      # Lesson structure (concrete-first, cloze/predict/error/diagram/mindmap)
    ├── quiz.yaml      # MCQ template (4 options, difficulty 1-3)
    └── cloze.yaml     # Cloze template (fill-in-blank, difficulty 1-3)
```

## Key Modification Points

### SKILL.md frontmatter

```yaml
---
name: learn-something
description: >
  Structured learning framework...
  Trigger: "I want to learn [topic]", ...
---
```

- `name`: must match directory name (`learn-something`)
- `description`: first sentence is summary. Remaining lines = trigger phrases.
- Trigger phrases: space-separated quotes. Each trigger activates skill.

### SKILL.md body

Contains Part A (instruction) + Part B (schema contract): Pedagogy, Content Structure, Content Creation Protocol, Study Protocol, CLI, Cost Model, Integration, Trigger Behavior, Quality Rules, Schema Reference.

- **Part A3/A4 (Content Creation Protocol)**: defines LLM behavior during course creation. Modify if changing AI creation flow. Includes 16 content quality rules now: concrete-first, cloze, predict, error-spotting, dual coding, mindmap, module size cap, etc.
- **Part A5 (Study Protocol)**: defines session types and FSRS rules. Mirror changes into `study-protocol.md`.
- **Part A6 (Trigger Behavior)**: defines first-response behavior. Modify if changing entry flow.

### study-protocol.md

Learner-facing subset of SKILL.md Part A5. Keep in sync — this is the quick reference learners use during study sessions.

### scripts/learn.sh

Thin bash wrapper (9 lines). Delegates all logic to `learn.py`.

### scripts/learn.py

Python CLI. Key subsystems:

| Function               | Purpose                                                                                                                            |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `sm2_update()`         | FSRS-5 algorithm: stability, difficulty, lapses, state                                                                             |
| `cmd_init`             | Create subject directory, copy syllabus template. Flags: `--depth survey                                                           | standard            | deep`, `--pretest` |
| `cmd_start`            | Show subject overview + module list                                                                                                |
| `cmd_create_module`    | Create module from template. Flag: `--name`. module_id must match NN-name (e.g., 01-intro)                                           |
| `cmd_create_cloze`     | Create cloze.yaml from template for a module                                                                                       |
| `cmd_quiz`             | Parse YAML, shuffle, display MCQs, update SRS deck. Flags: `--adaptive`, `--weak-only`                                             |
| `cmd_cloze`            | Cloze (fill-in-blank) quiz. Parse cloze.yaml, display prompts, update SRS deck. Flags: `--adaptive`, `--weak-only`                |
| `cmd_cumulative_quiz`  | Cross-module quiz: 8-10 questions (MCQ/cloze/T/F). Flag: `--modules X-Y`                                                           |
| `cmd_explain`          | Feynman technique prompt with gap detection guide                                                                                  |
| `cmd_review`           | FSRS review: due cards, scoring, interval calc                                                                                     |
| `cmd_blurting`         | Brain-dump before review. Compares user recall to lesson key terms                                                                 |
| `cmd_enrich`           | Add cloze/predict/error/diagram/mindmap/cloze-quiz enrichments to existing lessons via LLM. Flags: `--types`, `--dry-run`, `--render-mode api | local               | off`               |
| `cmd_fsrs_predict`     | Show avg stability, difficulty, retention per topic                                                                                |
| `cmd_stats`            | Card counts, due today, mastery rate, avg ease, session history                                                                    |
| `cmd_export`           | Export deck to CSV for Anki import                                                                                                 |
| `cmd_rate`             | Rate module clarity (1-5 stars), save to feedback.json. Flag: `--comment`                                                          |
| `cmd_flag`             | Report content error (wrong/outdated/confusing). Flag: `--detail`                                                                  |
| `cmd_feedback`         | Aggregate feedback: avg ratings, flag counts, suggest modules                                                                      |
| `cmd_analytics`        | Retention analytics: mastery breakdown, session history, weak modules                                                              |
| `cmd_forecast`         | Forgetting forecast: cards due now/week/month                                                                                      |
| `cmd_study_plan`       | Optimal study session: due + weak cards, skip mastered                                                                             |
| `cmd_epub`             | Generate EPUB book from all modules + quizzes. Flags: `--mermaid`, `--description`                                                 |
| `cmd_epub_regen`       | Regenerate EPUB from cached `book.md`. Flags: `--mermaid`, `--description`                                                         |
| `cmd_epub_verify`      | Validate EPUB structure                                                                                                            |
| `cmd_epub_list_themes` | List available EPUB themes                                                                                                         |
| `cmd_pdf`              | Generate PDF from all modules + quizzes. Flags: `--engine`, `--title`, `--author`                                                  |
| `cmd_pdf_regen`        | Regenerate PDF from cached `book.md`. Flags: `--engine`, `--title`, `--author`                                                     |
| `cmd_sync`             | Export deck to Reader directory (~/.coursereader/subjects/). Flag: `--reader-path`                                                 |
| `cmd_sync_pull`        | Import deck from Reader directory. Flag: `--reader-path`                                                                           |
| `cmd_validate`         | Full quality gate: Pass 1 `_schema_errors` (deck/quiz/cloze/cumulative/syllabus/feedback vs JSON Schema + module dir naming), Pass 2 `_content_syntax_errors` (markdown + mermaid), Pass 3-4 `_quality_checks` (rules 15-16 + statistical). All checks ERR, exit 1 on any failure |
| `cmd_render_diagrams`  | Render ```mermaid blocks in lesson.md to PNG. Flags: `--render-mode api                                                            | local`, `--scale N` |
| `cmd_mindmap`          | Generate/regenerate Mermaid mindmap for a module via LLM                                                                           |

#### FSRS-5 Algorithm (`sm2_update()`)

- Replaces SM-2. Uses 21-parameter model from py-fsrs v6.
- Quality >= 4 (correct) → rating=Good(3). Quality < 3 (wrong) → rating=Again(1). Quality=3 → rating=Hard(2).
- Initial stability S0 = W[rating-1], difficulty D0 = W[4] - exp(W[5] * (rating - 1)) + 1
- Retrievability: R = (1 + FACTOR * t / S) ^ DECAY
- Short-term (elapsed < 1d) vs long-term (elapsed >= 1d) stability updates
- Old SM-2 cards auto-migrate via `_migrate_sm2_card()` on update
- See `sm2.py` for full parameter constants W[0..20]

#### Quiz Engine (`cmd_quiz`)

- Uses Python3 with `yaml` library.
- Options shuffled per question, keys remapped (A-D → a-d).
- Each quiz attempt updates SRS deck with FSRS-5 intervals.
- Falls back to raw display if `yaml` unavailable.
- Adaptive mode: weighted by ease, difficulty ramp, streak skip.

### templates/

| Template        | Purpose                    | Key constraints                                                                                                                                                                                                                    |
| --------------- | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `syllabus.yaml` | 20-module default skeleton | time_hours per module ≤ 1.5 (hard cap, all levels), prerequisites form DAG. Level → module count: beginner ~25-30 (0.5-0.75h each), intermediate ~15-20 (1-1.5h), advanced ~20-30 (1-1.5h, open questions) |
| `module.md`     | Lesson structure           | Must include: Real-World Example → Core Content (with **Think**, **Cloze**, **Predict**, Mermaid per section) → Why This Matters → Key Takeaways → Common Misconception → **Spot the Mistake** → Feynman Explain → Reframe → Drill |
| `quiz.yaml`     | MCQ format                 | 4 options, 1 correct, difficulty 1-3, tags per category                                                                                                                                                                            |

## Content Quality Rules

The 16 content quality rules are the single source of truth in `SKILL.md` → **Part A4** (with automated checks). Do NOT duplicate the rule table here — if rules change, edit SKILL.md only.

## Modification Rules

1. **Keep pedagogy alignment**: Any new feature must fit Marva Collins (rigor/repetition), Feynman (explain-simply), or Desirable Difficulties (spacing/interleaving). Tag new features with which theory they serve.
2. **Keep cost model**: Powered by DeepSeek V4 Flash. Content creation stays ~$0.10/course max. Study sessions stay $0.
3. **Keep time budgets**: Every module ≤ 1.5h (hard cap, all levels; depth via more modules + open questions). Subject ≤ 40h guideline (deep courses may exceed; schema allows 200h).
4. **Keep FSRS-5 correct**: Stability/difficulty formulas match py-fsrs v6. Do not change W parameters without testing against known FSRS implementations.
5. **Keep trigger behavior**: On trigger, enter content creation mode immediately — never generate full course in one shot unless user explicitly asks.
6. **Keep template constraints**: MCQ = exactly 4 options, 1 correct. Module must include Feynman + Reframe sections.
7. **Keep sync**: Changes to study protocol in SKILL.md must be mirrored in `study-protocol.md`. Changes to deck schema must sync between CLI and Reader.
8. **Keep backward compat**: CLI flags and file structure (syllabus.yaml, modules/NN-name/lesson.md, modules/NN-name/quiz.yaml, srs/deck.json) are public API. Breaking changes need migration path.

## Adding Features

1. **CLI**: Add `cmd_<name>(topic: str, ...)` in `learn.py`, register via `app.command('name')(cmd_name)` (typer).
2. **Docs**: Update SKILL.md Part A6 (CLI) and AGENTS.md CLI table.
3. **Study flow**: If affected, update SKILL.md Part A5 + `study-protocol.md`.
4. **Content flow**: If affected, update SKILL.md Part A3/A4.
5. **Cost**: If it adds API calls, verify < $0.10/course (SKILL.md A7).
6. **Schema**: If new data type, add JSON Schema to `learn-something-schema/schemas/`, TypeScript type to `types/`, validator to `validate/python/validate.py`.
7. **Tests**: Add 2+ tests in `tests/test_learn.py` (happy path + error case).
8. **Quality gate**: If adding/removing a quality check, update `_quality_checks()` in `learn.py` + SKILL.md Part B5 table + `content-verify.md`.

## Testing

```bash
# Create test directory
mkdir test-course && cd test-course

# Initialize
../scripts/learn.sh init python

# Create test module
../scripts/learn.sh create-module python 01-intro

# Run quiz
../scripts/learn.sh quiz python 01-intro

# Run review
../scripts/learn.sh review python

# Check stats (includes session history)
../scripts/learn.sh stats python

# Export to Anki CSV
../scripts/learn.sh export python

# Test diagram rendering
../scripts/learn.sh enrich python 01-intro --types diagram --render-mode off
../scripts/learn.sh render-diagrams python 01-intro --render-mode api

# Cleanup
cd .. && rm -rf test-course
```


