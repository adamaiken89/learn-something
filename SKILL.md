---
name: learn-something
description: >
    Structured learning framework for any subject from text. Create syllabus +
    lessons + MCQ quizzes interactively with LLM. Study via CLI with spaced
    repetition (FSRS-5). Three-theory pedagogy: Marva Collins' Way (repetition,
    reframing, high expectations), Feynman Technique (explain-simply, find gaps),
    Desirable Difficulties (spaced/MCQ/retrieval). Cost-effective: content
    creation ~$0.10 per course; per-session cost = $0.
    Trigger: "I want to learn [topic]", "build curriculum for [subject]",
    "create learning module", "help me study [topic]", "/learn [topic]"
---

# Learn Something Framework

Turn subject into structured curriculum via interactive LLM session.
Study via CLI: read lessons, explain-back, drill MCQs, spaced repetition.

# Part A — Instruction Level

What to do when authoring content. Schema-level contract lives in Part B; every structural fact is enforced there by `learn.sh validate`.

## A1. Pedagogy

Three theories fused:

| Theory                     | AI role                                                           | Problem solved                       |
| -------------------------- | ----------------------------------------------------------------- | ------------------------------------ |
| **Marva Collins**          | Socratic tutor. Rigorous Q&A, high expectations, endless patience | Needs great teacher. AI never tires. |
| **Feynman Technique**      | Gap detector. Learner explains simply → AI finds holes            | Illusion of understanding            |
| **Desirable Difficulties** | Spaced scheduler. FSRS retrieval + interleaved practice           | Passive re-reading                   |

### Session phase → theory mapping

| Phase       | Theory            | Learner                | AI/CLI                                 |
| ----------- | ----------------- | ---------------------- | -------------------------------------- |
| **Read**    | Marva             | Study lesson           | Write clear content                    |
| **Explain** | Feynman           | Explain concept simply | Probe: "you said X, but Y — reconcile" |
| **Drill**   | Marva + Desirable | Answer MCQs, justify   | Grade, explain distractors             |
| **Judge**   | Marva             | Critique, form opinion | Socratic follow-up                     |
| **Review**  | Desirable         | Active recall via FSRS | Schedule optimal intervals             |

## A2. Course design

**Time budget (hard cap):** every module ≤ 1.5h, regardless of level. Depth comes from more modules, not longer ones. Subject ≤ 40h guideline (deep courses may exceed; schema allows up to 200h).

| Level | Module time | Modules per course | Why |
|---|---|---|---|
| **beginner** | 30-45 min | more (~25-30) | More checkpoints = more frequent success feedback |
| **intermediate** | 1-1.5h | ~15-20 | Balance depth vs momentum |
| **advanced** | 1-1.5h | more (~20-30) | Long topics split short; open questions carry depth |

- SRS review: ~10-15 min daily

**Question mix by level:** beginner = mostly closed (MCQ/cloze, one right answer) for low-friction checkpoints; advanced = open-ended (explain trade-offs, design a solution, critique a claim, compare approaches).

## A3. Content creation workflow

1. **Scope** (5 min): Ask domain/level/time budget/lang/use case. Propose syllabus.
2. **Outline stage**: Verify module DAG + prerequisite chain. Check time budget.
3. **Per module** (10 min): Create module with `learn.sh create-module <topic> NN-name`. Zero-padded two-digit number + kebab-case name (e.g., `01-intro`, `02-core-concepts`). Write lesson.md + quiz.yaml + cloze.yaml. Apply Part A rules inline. Keep lesson.md ≤12,000 characters. If content overflows, split into additional modules and update syllabus. User reviews. Proceed.
4. **Validate**: Run `learn.sh validate <topic> [module]`. Fix all ERR + WARN before proceeding. Quality gate is blocking (all checks ERR).
5. **Pre-publication**: Load `content-verify.md`. Run checklist. Fix violations.
6. **Compile SRS** (2 min): Extract MCQs → FSRS-5 deck.
7. **Cumulative quizzes**: After every 3-5 modules, generate `cumulative_quiz_XX-YY.yaml` in subject root (zero-padded module range, e.g. `cumulative_quiz_01-04.yaml`). See B2 for exact shape. Single-file `cumulative_quiz.yaml` also accepted.

## A4. Content principles + quality rules

### Design principles

- **CILO alignment**: Every module serves ≥1 learning objective. No filler.
- **Language**: All content in syllabus.yaml language (`en`/`zh`/`yue`).
- **Practical first**: Start with concrete example before abstract definition.
- **Domain-relevant**: Scenarios from learner's industry.
- **MCQ diversity**: 40% recall, 40% application, 20% multi-step. Beginner skews recall; advanced shifts to open questions.
- **Feynman prompt**: Every lesson ends with explanation task + AI gap probe.
- **Desirable difficulty**: Same concept tested at different angles across modules.
- **Progression**: Build on prerequisites. Earlier modules foundational.
- **Skip permitted**: Learner gives sparse input? Generate content anyway with sensible defaults. Do not block.
- **Socratic throughout**: Every major concept followed by a question that makes learner stop and think — not only at module end. Pattern: state concept → ask "why?" / "what if?" → answer immediately so learner can self-check.

### Quality rules (16) — enforced by `learn.sh validate`

All 16 below have an automated check in the quality gate (see B5). `Mindmap` (15) and `Module size` (16) are ERR; the rest are WARN.

| # | Rule | What to do | Automated check |
|---|---|---|---|
| 1 | Explain conventions | State why convention exists, not just what it is | WARN: conventions prose heuristic |
| 2 | Answer implicit Qs | Anticipate 1-3 questions learner hasn't asked | WARN: Q&A block presence |
| 3 | Pull-to-par intuition | Explain price → face value at maturity is mechanical | WARN |
| 4 | Causal chain first | Intuitive logic before formula | WARN |
| 5 | Practical context | Every number gets real meaning | WARN |
| 6 | "How likely" | Tell normal vs rare frequencies | WARN |
| 7 | Common misconceptions | Flag 1-2 specific errors beginners hold | WARN |
| 8 | Socratic throughout | Every concept section embeds **Think** question + immediate answer | WARN: `> **Think**:` blockquote in non-fence content |
| 9 | Dual coding | Every concept gets non-redundant diagram (Mermaid, ascii, hierarchy). Mermaid palette: `#5c7a99`/`#5c8a6a`/`#b8924a`/`#b86a4a`/`#7a5a8a`/`#888`, strokes `#333`, theme `neutral` | WARN: ```mermaid blocks |
| 10 | Concrete-first | Start module with real-world example before abstract definition | WARN |
| 11 | Cloze deletions | 3-5 per module. Key terms blanked as `{term}`. Format: `{blank}` marks the term to fill in. Good cloze = conceptual context, not trivial blanking | WARN: `{...}` in non-fence content |
| 12 | Predict-next | 2-3 per module. Learner commits to outcome before reveal | WARN: `> **Predict**:` blockquote |
| 13 | Error-spotting | 1-2 per module. Present plausible wrong solution | WARN: `> **Spot the Mistake**:` blockquote or `## Spot the Mistake` heading with prose body |
| 14 | Graduated examples | Full worked → partial → independent | WARN |
| 15 | Module mindmap | **Compulsory.** Mermaid mindmap at top of lesson.md (after metadata, before Learning Objectives). ` ```mermaid\nmindmap\n  root((Module Title))`, max 3 levels deep | ERR: mindmap present |
| 16 | Module size limit | lesson.md ≤12,000 characters target. Split if over. 12,000-13,000 WARN; >13,000 hard ERR | ERR: char count >13,000 |

## A5. Study protocol

### Session types

| Type        | Duration  | What to do                                                                       |
| ----------- | --------- | -------------------------------------------------------------------------------- |
| **LEARN**   | 45-60 min | `learn.sh start` → read lesson → reframe → `learn.sh quiz`                       |
| **EXPLAIN** | 15-20 min | Pick concept. Explain simply aloud/in writing. AI probes gaps. Loop until holds. |
| **BLURT**   | 10-15 min | `learn.sh blurting <topic> <module>` — brain-dump before review, AI shows gaps   |
| **REVIEW**  | 10-15 min | `learn.sh review` → due FSRS cards (interleaved across modules)                  |
| **MIXED**   | 30-45 min | BLURT (10min) → REVIEW (10min) → LEARN (20min) → EXPLAIN (5min)                  |

### FSRS rules

- Uses FSRS-5 algorithm (replaces SM-2). Cards tracked by: stability, difficulty, lapses, state.
- Correct (q≥4): stability grows with recall. Wrong (q<3): stability drops, difficulty rises.
- See `sm2.py` for full FSRS parameter set.
- `learn.sh fsrs-predict <topic>` shows avg stability/difficulty/retention per topic.
- Old SM-2 decks auto-migrate on first review after upgrade.

### Desirable Difficulties in practice

- **Interleaved**: Review session mixes 3+ module tags.
- **Varied difficulty**: Easy recall day 1 → harder scenario variants at next interval.
- **Generation**: Type answer before seeing options (optional CLI mode).
- **Context variation**: Year 2 uses different scenarios than year 1.

## A6. CLI

````
# ── Content Creation ──────────────────────────────
learn.sh init <topic> [lang] [--depth survey|standard|deep] [--pretest]
                                         # Initialize topic dir with syllabus template
                                         # --depth: survey (~6 modules), standard (~18), deep (~28)
                                         # --pretest: test first, skip known content
learn.sh start <topic>                       # Overview + module list
learn.sh create-module <topic> <id>          # Create module from template
learn.sh create-cloze <topic> <module>      # Create cloze.yaml from template
learn.sh enrich <topic> [module|--all] [--types cloze,predict,error,diagram,cloze-quiz] [--dry-run] [--render-mode api|local|off]
                                         # Add cloze/predict/error/diagram to existing lessons
                                         # Uses DeepSeek API. Backup as .md.bak
                                         # --types: comma-separated subset of types (includes cloze-quiz for cloze.yaml generation)
                                         # --render-mode: auto-render diagrams to PNG (default: api)
learn.sh render-diagrams <topic> [module] [--render-mode api|local] [--scale N]
                                         # Render ```mermaid blocks to PNG in lesson.md
                                         # --render-mode: api (mermaid.ink) or local (mmdc CLI)
                                         # --scale: PNG scale factor (default 2 = 300dpi)
learn.sh mindmap <topic> <module>           # Generate/regenerate Mermaid mindmap for module

# ── Study ─────────────────────────────────────────
learn.sh quiz <topic> <module> [--adaptive] [--weak-only]
                                         # MCQ drill
                                         # --adaptive: weighted by ease, difficulty ramp, streak skip
                                         # --weak-only: only cards with ease < 2.0
learn.sh cloze <topic> <module> [--adaptive] [--weak-only]
                                         # Cloze (fill-in-blank) drill
                                         # --adaptive: weighted by ease, difficulty ramp, streak skip
                                         # --weak-only: only cards with ease < 2.0
learn.sh cumulative-quiz <topic> [--modules X-Y]
                                         # Cross-module quiz (8-10 questions, mix of MCQ/cloze/T/F)
                                         # --modules: filter to specific module range
learn.sh explain <topic> <module>            # Feynman prompt guide
learn.sh review <topic>                      # FSRS spaced repetition
learn.sh blurting <topic> <module>           # Brain-dump before review. AI compares to lesson

# ── Progress & Analytics ──────────────────────────
learn.sh stats <topic>                       # Progress + retention
learn.sh analytics <topic>                   # Mastery breakdown, weak modules, session history
learn.sh forecast <topic>                    # Cards due: now / week / month / later
learn.sh study-plan <topic>                  # Optimal session: due + weak, skip mastered
learn.sh fsrs-predict <topic>                # Avg stability, difficulty, retention per topic

# ── Feedback ──────────────────────────────────────
learn.sh rate <topic> <module> <1-5>         # Rate module clarity
learn.sh flag <topic> <module> <type>        # Report error (wrong/outdated/confusing)
learn.sh feedback <topic>                    # Aggregate ratings + flag counts

# ── Export ────────────────────────────────────────
learn.sh export <topic>                      # Anki CSV export
learn.sh epub <topic> [file] [--local] [--description TEXT]
                                         # Export to EPUB book
                                         # --local: use mmdc CLI for Mermaid
                                         # --description: cover page description
learn.sh epub-regen <topic> [file] [--local] [--description TEXT]
                                         # Regenerate EPUB from cached markdown
learn.sh epub-verify <topic> [file]          # Validate EPUB structure
learn.sh epub-list-themes                    # List available EPUB themes
learn.sh pdf <topic> [file] [--engine auto|weasyprint|pandoc|raw]
                                         # Export to PDF
learn.sh pdf-regen <topic> [file] [--engine] # Regenerate PDF from cached book.md

# ── Sync ──────────────────────────────────────────
learn.sh sync <topic>                        # Export to Reader dir (~/.coursereader/subjects/)
learn.sh sync-pull <topic>                   # Import deck from Reader dir

# ── Validation ──────────────────────────────────────
learn.sh validate <topic> [module]           # Full gate: schema + naming + content syntax + quality (see B5)
learn.sh validate-content <topic> [module]   # Deprecated alias → validate
````

## A7. Cost, Integration, Trigger

### Cost model (DeepSeek V4 Flash)

| Phase                           | Cost          |
| ------------------------------- | ------------- |
| Scope + syllabus                | ~$0.01        |
| Per module (~15K tokens out)    | ~$0.004       |
| Enrich per module (all 4 types) | ~$0.01        |
| Enrich per type (per module)    | ~$0.002-0.004 |
| Full course (20 modules)        | ~$0.08        |
| Full course + enrich            | ~$0.28        |
| Study session / SRS review      | $0            |

### Integration

- **Anki**: `learn.sh export` → CSV/APKG
- **Obsidian/Notion**: Markdown imports directly
- **Print**: Print lesson.md or quiz.yaml
- **EPUB**: `learn.sh epub <subject>` generates EPUB 3 (hierarchical ToC, syntax highlighting, quizzes, Mermaid via mermaid.ink API default, `--local` for offline mmdc). Workflow: `epub` (assemble + build) → `epub-verify`; `epub-regen` rebuilds from cached `book.md`.
- **PDF**: `learn.sh pdf <subject>` (stdlib fallback, optional weasyprint/pandoc). `pdf-regen` from cached `book.md`.

### Trigger behavior

Enter content creation mode immediately:

1. Confirm scope iteratively.
2. Write module 1.
3. Proceed module by module — never full course in one shot unless asked.

---

# Part B — Schema Level Check

Machine-readable contract. Every artifact validates against `learn-something-schema/schemas/` via `learn.sh validate <topic>`. Structural rules are enforced here, not in prose.

## B1. Directory structure

```
<topic>/
├── syllabus.yaml             # Course spec (see B2)
├── cumulative_quiz_XX-YY.yaml   # Cross-module quizzes (after every 3-5 modules)
├── modules/
│   ├── NN-name/              # Dir name must match NN-kebab-case
│   │   ├── lesson.md         # Core content + exercises (≤12,000 chars)
│   │   ├── quiz.yaml         # 8-10 MCQs
│   │   └── cloze.yaml        # 8-10 cloze questions
│   └── ...
└── srs/
    ├── deck.json             # FSRS-5 cards {cards: {id: card}}
    └── stats.json            # History
```

## B2. Canonical shapes

| File | Shape |
|---|---|
| `syllabus.yaml` | Top-level map: `subject`, `language`, `time_budget_hours`, `target_level`, `modules` (array of `{id: int, name, time_hours ≤1.5, prerequisites: [int], topics: [str]}`) |
| `quiz.yaml` | **Top-level array** (NOT wrapped in `questions:`). Each item: `{id: "N.M", question, options: {a..d}, answer: a\|b\|c\|d (lowercase), explanation, difficulty: 1-3, tags: []}` |
| `cloze.yaml` | Top-level array. Each item: `{id: "c.N", question, answer, explanation, difficulty, tags}`. Answer auto-extractable from `{...}` braces |
| `cumulative_quiz_XX-YY.yaml` | Top-level array. Each item: `{id: "cum.N", type: mcq\|cloze\|tf, source_modules: [int], question OR statement, options, answer, difficulty, tags}` |
| `srs/deck.json` | `{cards: {id: card}}` map format, camelCase fields |

### Field conventions (shared across all shapes)

- **Difficulty**: `1=recall, 2=comprehension, 3=application`
- **Tags vocabulary**: quiz → `terminology, concept, formula, scenario, comparison, calculation`; cloze → `terminology, concept, formula, process, comparison`; cumulative → `cross-module, recall, synthesis, misconception`
- **Options**: exactly 4 (`a,b,c,d`), exactly 1 correct. Lowercase keys + answers are canonical.
- **Question-per-objective**: at least 1 quiz question per syllabus learning objective.
- **Difficulty mix**: ~40% difficulty 1, 40% difficulty 2, 20% difficulty 3 per file.
- **Answer distribution**: no more than 2 consecutive questions share same answer letter; overall spread balanced across a/b/c/d (MCQ: roughly 1 each per 4).
- **Cumulative mix**: 4 MCQ + 3 cloze + 3 T/F = 10 items.

## B3. Naming conventions

- Module dirs: `NN-kebab-case` (zero-padded two-digit + kebab), e.g. `01-intro`.
- Cumulative quizzes: `cumulative_quiz_XX-YY.yaml` (zero-padded range). Single `cumulative_quiz.yaml` tolerated.
- IDs: quiz `N.M`, cloze `c.N`, cumulative `cum.N`.
- JSON fields: camelCase. YAML keys: lowercase a-d.

## B4. YAML gotchas (breaks parsing — always double-quote these)

- `@` at start of a plain scalar (e.g. `@ConfigurationProperties`) — illegal in YAML plain scalars
- `": "` inside an unquoted list/map scalar (e.g. `- Total: 3`) — parsed as nested mapping
- `{...}` braces inside double-quoted scalars must be literal (no `\{` escapes)
- Quiz/cloze/cumulative files must be **top-level arrays** — `questions:` wrapper breaks CLI + validation

Auto-fix most of these + normalize shapes with `python3 scripts/migrate_courses.py [topic] --apply` (idempotent; run from subject dir).

## B5. Validation (quality gate)

`learn.sh validate <topic> [module]` = single full gate. Four passes, all report-only (never writes to disk; legacy courses stay as-is but fail until regenerated):

| Pass | Checks | Severity |
|---|---|---|
| 1. Schema | quiz/cloze/cumulative/syllabus/deck/feedback vs JSON Schema; module dir naming; junk files | ERR |
| 2. Content syntax | markdown (pymarkdownlnt or basic) + mermaid (mmdc or basic) on lesson.md | ERR |
| 3. Quality | Rules 15-16: mindmap present; lesson.md ≤12,000 chars | ERR |
| 4. Quality (statistical) | Rules 1-14 signals: Think/Cloze/Predict/Spot-the-Mistake blocks, mermaid diagrams, difficulty mix, answer rotation/spread, item counts, Q-per-LO, cumulative coverage + type mix | ERR |

All checks are ERR — exit code 1 if any fails. No WARN tier. Schema sources: `learn-something-schema/` (JSON Schema files, TypeScript types, python validator). `validate-content` = deprecated alias for backward compatibility.

Generated decks may carry ISO date-times (Reader-rewritten) or date-only (CLI-written) — both accepted by schema.
