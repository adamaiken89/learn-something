# Study Protocol

Three learning theories fused:

| Theory                     | Focus                                   | In practice                                                          |
| -------------------------- | --------------------------------------- | -------------------------------------------------------------------- |
| **Marva Collins**          | Rigor, repetition, high expectations    | Read thoroughly, reframe in own words, answer precisely, no slacking |
| **Feynman Technique**      | Explain simply, find gaps               | Teach concept to imaginary child. If explanation fuzzy — gap found   |
| **Desirable Difficulties** | Make recall harder = retention stronger | Spaced repetition, mixed modules, varied MCQ difficulty              |

## Session types

### LEARN (45-60 min) — Marva
1. `less <topic>/modules/NN-name/lesson.md`
2. Read with full attention. Take notes.
3. Answer reframe prompt (written). Judge the concept.
4. `learn.sh <topic> quiz NN-name` — MCQs
5. Mark module complete

### EXPLAIN (15-20 min) — Feynman
1. Pick concept just studied (or flagged weak in stats)
2. Explain aloud/in writing as if teaching a child:
   - Simplest words. No jargon.
   - Concrete example from daily work
3. Self-check: Any vague language? Missed causal links?
4. For deeper probing: open opencode chat, explain concept to AI. AI finds gaps.

### REVIEW (10-15 min, daily) — Desirable Difficulties
1. `learn.sh <topic> review` → due cards SM-2
2. Cards mixed from multiple modules (interleaved)
3. Correct → interval grows. Wrong → reset 1d.
4. `learn.sh <topic> stats` → retention, weak areas

### MIXED (30-45 min) — all three
- REVIEW 10 min
- LEARN 25 min (one new module)
- EXPLAIN 5 min (Feynman check on new module)

## Spaced Repetition (SM-2)

Each MCQ = 1 SRS card.

| Correctness | Effect                            |
| ----------- | --------------------------------- |
| Correct     | Interval: 1d → 6d → × ease_factor |
| Wrong       | Reset to 1d, re-learn             |

Ease factor min 1.3. Adjusts per card based on answer history.

## Directory structure

```
<topic>/
├── syllabus.yaml       # Full course plan (includes language: en|zh|yue)
├── modules/
│   ├── NN-name/
│   │   ├── lesson.md   # Content + Feynman prompt + reframe
│   │   └── quiz.yaml   # 8-10 MCQs
│   └── ...
└── srs/
    ├── deck.json       # SM-2 card states
    └── stats.json      # Study history
```

## Tips

1. **Space it**: 30 min daily > 3 hours once a week
2. **Mix it**: Interleave review and new material
3. **Test yourself**: Quiz after every read
4. **Explain simply**: If can't explain to child, don't understand
5. **Connect to work**: Relate every concept to daily tasks
6. **Judge critically**: "When is this wrong?" not just "what is this?"
7. **Track weak areas**: Stats show low-scoring modules — revisit
