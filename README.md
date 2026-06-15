# Learn Anything

Structured learning framework for any subject — study via CLI with spaced repetition (SM-2). Three-theory pedagogy: Marva Collins, Feynman Technique, Desirable Difficulties.

## Features

- **Interactive curriculum creation**: LLM-driven syllabus + lesson + MCQ generation
- **CLI study system**: read lessons, Feynman explain-back, MCQ drills, spaced repetition
- **SM-2 spaced repetition**: optimal recall intervals, mixed-module interleaving
- **Cost-effective**: ~$0.10 per course creation, $0 per study session
- **Portable**: Markdown files importable into Anki, Obsidian, Notion

## Quick Start

1. **Trigger creation**: Say `I want to learn [topic]` or `learn.sh init <subject>`
2. **Study**: `learn.sh start <subject>` → `learn.sh quiz <subject> <module>`
3. **Review daily**: `learn.sh review <subject>`

## CLI Commands

```
learn.sh init <subject>          Create new subject skeleton
learn.sh start <subject>         Show overview + modules
learn.sh quiz <subject> <mod>    MCQ drill
learn.sh explain <subject> <mod> Feynman technique prompt
learn.sh feynman <subject> <mod> Alias for explain
learn.sh review <subject>        SM-2 spaced repetition
learn.sh stats <subject>         Progress + retention
learn.sh export <subject>        Anki CSV export
```

## Subject Structure

```
subjects/<topic>/
├── syllabus.yaml       # Course spec
├── modules/
│   ├── NN-name/
│   │   ├── lesson.md   # Core content, examples, reframe prompts
│   │   └── quiz.yaml   # 8-10 MCQs
│   └── ...
└── srs/
    ├── deck.json       # SM-2 card state
    └── stats.json      # Study history
```

## Pedagogy

| Theory | Role |
|--------|------|
| **Marva Collins** | Rigor, repetition, high expectations. Read thoroughly, answer precisely. |
| **Feynman Technique** | Explain simply → find gaps → refine. Teach concept to imaginary child. |
| **Desirable Difficulties** | Spaced repetition, interleaved modules, varied MCQ difficulty. |

## Session Types

| Session | Duration | Focus |
|---------|----------|-------|
| **LEARN** | 45-60 min | Read lesson, reframe, MCQ drill |
| **EXPLAIN** | 15-20 min | Feynman explain-back, AI gap detection |
| **REVIEW** | 10-15 min | SM-2 spaced repetition (daily) |
| **MIXED** | 30-45 min | REVIEW + LEARN + EXPLAIN combined |

## Cost Model

Powered by **DeepSeek V4 Flash**.

| Phase | Cost |
|-------|------|
| Scope + syllabus | ~$0.01 |
| Per module (~15K tokens) | ~$0.004 |
| Full course (20 modules) | ~$0.08 |
| Per study session | $0 |

## License

MIT
