---
name: learn-anything
description: >
  Structured learning framework for any subject from text. Create syllabus +
  lessons + MCQ quizzes interactively with LLM. Study via CLI with spaced
  repetition (SM-2). Three-theory pedagogy: Marva Collins' Way (repetition,
  reframing, high expectations), Feynman Technique (explain-simply, find gaps),
  Desirable Difficulties (spaced/MCQ/retrieval). Cost-effective: content
  creation ~$0.10 per course; per-session cost = $0.
  Trigger: "I want to learn [topic]", "build curriculum for [subject]",
  "create learning module", "help me study [topic]", "/learn [topic]"
---

# Learn Anything Framework

Turn subject into structured curriculum via interactive LLM session.
Study via CLI: read lessons, explain-back, drill MCQs, spaced repetition.

## 1. Pedagogy

Three theories fused:

| Theory | AI role | Problem solved |
|--------|---------|----------------|
| **Marva Collins** | Socratic tutor. Rigorous Q&A, high expectations, endless patience | Needs great teacher. AI never tires. |
| **Feynman Technique** | Gap detector. Learner explains simply → AI finds holes | Illusion of understanding |
| **Desirable Difficulties** | Spaced scheduler. SM-2 retrieval + interleaved practice | Passive re-reading |

### Session phase → theory mapping

| Phase | Theory | Learner | AI/CLI |
|-------|--------|---------|--------|
| **Read** | Marva | Study lesson | Write clear content |
| **Explain** | Feynman | Explain concept simply | Probe: "you said X, but Y — reconcile" |
| **Drill** | Marva + Desirable | Answer MCQs, justify | Grade, explain distractors |
| **Judge** | Marva | Critique, form opinion | Socratic follow-up |
| **Review** | Desirable | Active recall via SM-2 | Schedule optimal intervals |

### Time budget
- Subject: **40h max** (13 wk × 3h/wk)
- Module: 1.5-3h, ~15-20 per subject
- SRS review: ~10-15 min daily

## 2. Content Structure

```
subjects/<topic>/
├── syllabus.yaml             # Course spec
├── modules/
│   ├── NN-name/
│   │   ├── lesson.md         # Core content + exercises
│   │   └── quiz.yaml         # 8-10 MCQs
│   └── ...
└── srs/
    ├── deck.json             # SM-2 cards
    └── stats.json            # History
```

Full templates in `templates/`. Key: syllabus.yaml (20-module skeleton), module.md (lesson structure), quiz.yaml (4-option MCQ format).

## 3. Content Creation Protocol

### Workflow
1. **Scope** (5 min): Ask domain/level/time budget/lang/use case. Propose syllabus.
2. **Per module** (10 min): Write lesson.md + quiz.yaml. User reviews. Proceed.
3. **Compile SRS** (2 min): Extract MCQs → SM-2 deck.

### Content principles
- **CILO alignment**: Every module serves ≥1 learning objective. No filler.
- **Language**: All content in syllabus.yaml language (`en`/`zh`/`yue`).
- **Practical first**: Start with daily encounters → theory.
- **Domain-relevant**: Scenarios from learner's industry.
- **MCQ diversity**: 40% recall, 40% application, 20% multi-step.
- **Feynman prompt**: Every lesson ends with explanation task + AI gap probe.
- **Desirable difficulty**: Same concept tested at different angles across modules.
- **Time budget**: Module ≤3h. Subject ≤40h.
- **Progression**: Build on prerequisites. Earlier modules foundational.
- **Skip permitted**: Learner gives sparse input? Generate content anyway with sensible defaults. Do not block.
- **Socratic throughout**: Every major concept is followed by a question that makes learner stop and think — not at end of module only, but inline after each new idea. Question → brief answer/explanation immediately after so learner can self-check. Pattern: state concept → ask "why?" or "what if?" → answer.
- **Mermaid diagrams**: For concepts with branching logic, state machines, workflows, or causal chains: generate Mermaid flowchart/sequence/state diagram. Place after concept explanation, before **Think** question.

### Content quality rules (9)

| # | Rule | What to do | Bad example → Good example |
|---|------|------------|----------------------------|
| 1 | Explain conventions | State why convention exists, not just what it is | "Price quoted 95" → "95 = 95% of $1,000 par. % convention enables comparison across bonds with different face values." |
| 2 | Answer implicit Qs | Anticipate 1-3 questions learner hasn't asked | Silent on coupons → "Does coupon ever change? No for fixed-rate. Yes for FRNs (resets periodically)." |
| 3 | Pull-to-par intuition | Explain price → face value at maturity is mechanical | "Price converges to par because time shrinks + remaining CFs' PV converges to principal. Not driven by rates." |
| 4 | Causal chain first | Intuitive logic before formula | Jump to bond pricing formula → "New bonds pay 6%. My bond pays 4%. Mine less valuable → price drops until yield matches." |
| 5 | Practical context | Every number gets real meaning | "Duration 7.5" → "1% rate rise → ~7.5% price drop (small moves only; convexity adjustment for large)." |
| 6 | "How likely" | Tell normal vs rare frequencies | Omit → "Yield curve inverts rarely. Each inversion preceded recession (~8mo). Not perfectly predictive." |
| 7 | Common misconceptions | Flag 1-2 specific errors beginners hold | "Higher coupon = better bond" → "No. Discount bonds have built-in price gain at maturity (accretion)." |
| 8 | Socratic throughout | Every concept section embeds **Think** question + immediate answer | Learner reads passively → forced to stop, process, self-check before proceeding |
| 9 | Mermaid diagrams for complex concepts | If concept involves branching logic, state transitions, workflows, or causal chain with 3+ nodes: include ````mermaid` diagram. Prefer sequence, flowchart, or state diagram types. | "Bond amortization schedule explained in text only" → add ````mermaid\ngraph LR\nA[Issue] --> B[Coupon payments]\nB --> C[Principal at maturity]\n```` |

## 4. Study Protocol

### Session types

| Type | Duration | What to do |
|------|----------|------------|
| **LEARN** | 45-60 min | `learn.sh start` → read lesson → reframe → `learn.sh quiz` |
| **EXPLAIN** | 15-20 min | Pick concept. Explain simply aloud/in writing. AI probes gaps. Loop until holds. |
| **REVIEW** | 10-15 min | `learn.sh review` → due SM-2 cards (interleaved across modules) |
| **MIXED** | 30-45 min | REVIEW (10min) → LEARN (20min) → EXPLAIN (5min) → REVIEW (5min) |

### SM-2 rules
- Correct (q≥3): interval grows 1d → 6d → × ease_factor. Wrong: reset 1d.
- Ease factor min 1.3. Auto-rate: correct = q4, wrong = q1.

### Desirable Difficulties in practice
- **Interleaved**: Review session mixes 3+ module tags.
- **Varied difficulty**: Easy recall day 1 → harder scenario variants at next interval.
- **Generation**: Type answer before seeing options (optional CLI mode).
- **Context variation**: Year 2 uses different scenarios than year 1.

## 5. CLI

```
learn.sh init <subject> [lang]        # Create subject (en|zh|yue)
learn.sh start <subject>              # Overview + module list
learn.sh create-module <subject> <id> # Create module from template
learn.sh quiz <subject> <module>      # MCQ drill
learn.sh explain <subject> <module>   # Feynman prompt guide
learn.sh review <subject>             # SM-2 spaced repetition
learn.sh stats <subject>              # Progress + retention
learn.sh export <subject>             # Anki CSV export
learn.sh epub <subject> [file] [--local]        # Export course to EPUB book (--local: use mmdc CLI)
learn.sh epub-regen <subject> [file] [--local]  # Regenerate EPUB from cached markdown
learn.sh epub-verify <subject> [file]           # Validate EPUB structure
learn.sh pdf <subject> [file] [--engine]        # Export course to PDF (auto/weasyprint/pandoc/raw)
learn.sh pdf-regen <subject> [file] [--engine]  # Regenerate PDF from cached book.md
```

## 6. Cost Model (DeepSeek V4 Flash)

| Phase | Cost |
|-------|------|
| Scope + syllabus | ~$0.01 |
| Per module (~15K tokens out) | ~$0.004 |
| Full course (20 modules) | ~$0.08 |
| Study session / SRS review | $0 |

## 7. Integration

- **Anki**: `learn.sh export` → CSV/APKG
- **Obsidian/Notion**: Markdown imports directly
- **Print**: Print lesson.md or quiz.yaml
- **EPUB**: `learn.sh epub <subject>` generates EPUB 3 with hierarchical ToC, syntax highlighting, quizzes, Mermaid diagrams (mermaid.ink API by default, `--local` for offline mmdc CLI)
- **PDF**: `learn.sh pdf <subject>` generates PDF with zero-dep stdlib fallback or optional weasyprint/pandoc engine (`--engine weasyprint`)

### EPUB generation workflow

1. Content created → all modules complete
2. Run `learn.sh epub <subject>` or `learn.sh epub-regen <subject> [file]`
   - `epub`: assembles subject dir (lesson.md + quiz.yaml per module) → `book.md` → EPUB
   - `epub-regen`: rebuild EPUB from existing `book.md` (skip assembly, faster after edits)
   - `--description "text"` adds cover page description
3. Validate: `learn.sh epub-verify <subject> [file]`
4. Underlying script: `epub.py build <subject-dir> <output> [--title TITLE] [--author AUTHOR] [--description DESC]`
   - Also: `epub.py from-md <markdown-file> <output>` for custom markdown
   - Zero-dep fallback parser or optional `markdown` + `pygments` for GFM tables + syntax highlighting
   - Mermaid diagrams rendered to SVG via mermaid.ink API (default) or local mmdc CLI (`--mermaid local`)
   - Generates valid EPUB 3 (cover SVG, nav, spine, manifest, XHTML content, SVG diagrams)
   - Cover: procedural SVG generated from title hash (8 color palettes, 4 pattern types). Deterministic, zero-dep.

### PDF generation workflow

1. Content created → all modules complete
2. Run `learn.sh pdf <subject>` or `learn.sh pdf-regen <subject> [file]`
   - `pdf`: assembles subject dir (lesson.md + quiz.yaml per module) → `book.md` → PDF
   - `pdf-regen`: rebuild PDF from existing `book.md` (skip assembly, faster after edits)
3. Underlying script: `pdf.py build <subject-dir> <output> [--title TITLE] [--engine auto|weasyprint|pandoc|raw]`
   - Also: `pdf.py from-md <markdown-file> <output>` for custom markdown
   - Engine priority: weasyprint (best, pip install) → pandoc → stdlib-only text PDF (zero deps)
   - Default `--engine auto` picks best available engine

## 8. Trigger behavior

Enter content creation mode immediately:
1. Confirm scope iteratively.
2. Write module 1.
3. Proceed module by module — never full course in one shot unless asked.
