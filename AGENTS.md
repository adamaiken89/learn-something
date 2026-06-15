# Learn Anything — Agent Modification Guide

## Skill Structure

```
learn-anything/
├── SKILL.md           # Frontmatter metadata + main instruction body
├── study-protocol.md  # Learner-facing protocol reference
├── README.md          # General documentation
├── LICENSE            # MIT
├── AGENTS.md          # This file — agent modification guide
├── scripts/
│   └── learn.sh       # CLI entrypoint (bash, SM-2, quiz engine)
└── templates/
    ├── syllabus.yaml  # 20-module course skeleton
    ├── module.md      # Lesson structure with Feynman/reframe/drill sections
    └── quiz.yaml      # MCQ template (4 options, difficulty 1-3)
```

## Key Modification Points

### SKILL.md frontmatter

```yaml
---
name: learn-anything
description: >
  Structured learning framework...
  Trigger: "I want to learn [topic]", ...
---
```

- `name`: must match directory name (`learn-anything`)
- `description`: first sentence is summary. Remaining lines = trigger phrases.
- Trigger phrases: space-separated quotes. Each trigger activates skill.

### SKILL.md body

Contains sections: Pedagogy, Content Structure, Content Creation Protocol, Study Protocol, CLI, Cost Model, Integration, Trigger Behavior.

- **Section 3 (Content Creation Protocol)**: defines LLM behavior during course creation. Modify if changing AI creation flow.
- **Section 4 (Study Protocol)**: defines session types and SM-2 rules. Mirror any changes here into `study-protocol.md`.
- **Section 8 (Trigger Behavior)**: defines first-response behavior. Modify if changing entry flow.

### study-protocol.md

Learner-facing subset of SKILL.md Section 4. Keep in sync — this is the quick reference learners use during study sessions.

### scripts/learn.sh

Bash CLI. Key subsystems:

| Function | Lines | Purpose |
|----------|-------|---------|
| `cmd_init` | 32-43 | Create subject directory, copy syllabus template |
| `cmd_quiz` | 74-171 | Parse YAML, shuffle, display MCQs, update SRS deck |
| `cmd_review` | 173-263 | SM-2 algorithm: due cards, scoring, interval calc |
| `cmd_stats` | 265-305 | Show card counts, due today, mastery rate, avg ease |
| `cmd_export` | 340-370 | Export deck to CSV for Anki import |

#### SM-2 Algorithm (cmd_review, lines 231-256)

- Quality >= 3 (correct): interval grows (1d → 6d → × ease_factor), repetitions++
- Quality < 3 (wrong): reset reps=0, interval=1d
- Ease factor adjustment: `ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))`
- Min ease factor: 1.3

#### Quiz Engine (cmd_quiz, lines 74-171)

- Uses Python3 with `yaml` library. Falls back to raw `cat` if Python unavailable.
- Options shuffled per question, keys remapped (A-D → a-d).
- Each quiz attempt creates SRS cards if missing.

### templates/

| Template | Purpose | Key constraints |
|----------|---------|-----------------|
| `syllabus.yaml` | 20-module default skeleton | time_hours per module ≤ 3, prerequisites form DAG |
| `module.md` | Lesson structure | Must include: Core Content, Feynman Explain, Reframe, Drill |
| `quiz.yaml` | MCQ format | 4 options, 1 correct, difficulty 1-3, tags per category |

## Modification Rules

1. **Keep pedagogy alignment**: Any new feature must fit Marva Collins (rigor/repetition), Feynman (explain-simply), or Desirable Difficulties (spacing/interleaving). Tag new features with which theory they serve.
2. **Keep cost model**: Powered by DeepSeek V4 Flash. Content creation stays ~$0.10/course max. Study sessions stay $0.
3. **Keep time budgets**: Module ≤ 3h. Subject ≤ 40h.
4. **Keep SM-2 correct**: Interval progression and ease factor formula are standard SM-2. Do not change without testing against known SM-2 implementations.
5. **Keep trigger behavior**: On trigger, enter content creation mode immediately — never generate full course in one shot unless user explicitly asks.
6. **Keep template constraints**: MCQ = exactly 4 options, 1 correct. Module must include Feynman + Reframe sections.
7. **Keep sync**: Changes to study protocol in SKILL.md must be mirrored in `study-protocol.md`.
8. **Keep backward compat**: CLI flags and file structure (syllabus.yaml, modules/NN-name/lesson.md, modules/NN-name/quiz.yaml, srs/deck.json) are public API. Breaking changes need migration path.

## Adding Features

1. Add CLI subcommand: new `cmd_*` function in `learn.sh`, register in `case` block and `help` text.
2. Update SKILL.md Section 5 (CLI) with new command.
3. If feature affects study flow, update Section 4 (Study Protocol) and `study-protocol.md`.
4. If feature affects content creation, update Section 3 (Content Creation Protocol).
5. If feature affects cost, update Section 6 (Cost Model) and verify < $0.10/course.
6. Add test: run existing `learn.sh` commands against a test subject.

## Testing

```bash
# Create test subject
./scripts/learn.sh init test-subject

# Verify structure
ls -R subjects/test-subject/

# Create test module
mkdir -p subjects/test-subject/modules/01-intro
# Add lesson.md and quiz.yaml

# Run quiz
./scripts/learn.sh quiz test-subject 01-intro

# Run review
./scripts/learn.sh review test-subject

# Check stats
./scripts/learn.sh stats test-subject

# Cleanup
rm -rf subjects/test-subject
```
