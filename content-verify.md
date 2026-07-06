# Content Verification — Evidence-Based Quality Check

Load after each module generation. Verify against criteria below before presenting.

## Checklist (from Content Design Mod17)

- [ ] Concrete problem/example first, not abstract definition?
- [ ] ≤2 concepts per section (~WM limit, CLT Mod2)?
- [ ] Active engagement: cloze, predict, error-spot? (Retrieval Mod7, Feedback Mod12)
- [ ] Immediate feedback after every exercise? (Feedback Mod12)
- [ ] Non-redundant diagram for structure/relationships? (Dual Coding Mod6, Redundancy Effect CLT Mod2)
- [ ] No extraneous fluff? (CLT Mod2 — extraneous load)
- [ ] Builds on previous modules? (schema building, CLT Mod2)
- [ ] Ends with retrieval opportunity (Feynman/Drill)? (Retrieval Mod7)

## Redundancy Effect Check

If same info appears through verbal AND visual channel simultaneously, mark violation:

| Violation | Example | Fix |
|-----------|---------|-----|
| Diagram repeats text paragraph | Paragraph describing flowchart + same flowchart | Remove paragraph. Diagram alone sufficient. |
| Narration + identical on-screen text | "The heart pumps blood" written AND narrated | Use narration OR text, not both (Mayer redundancy principle). |
| Separate legend for self-labeled diagram | "Fig 1: A=heart, B=lungs" when labels already on diagram | Remove legend. Integrate labels onto diagram (spatial contiguity). |

## Design Strategies (use ≥2 per module)

| Strategy | Usage | Science |
|----------|-------|---------|
| **Chunking** | Break complex topics into 2-4 sub-topics per section | CLT Mod2 — WM ~4 chunk limit |
| **Fading worked examples** | Full worked → partial (fill blanks) → independent | CLT Mod2 — worked example effect |
| **Self-explanation prompts** | "Why does this step work?" after each claim | Deep Proc Mod5 — elaborative interrogation |
| **Pre-training** | Introduce key terms before complex interaction | CLT Mod2 — reduced momentary intrinsic load |

## Automated checks

- **Quality rules (16) + canonical shapes**: `learn.sh validate <topic>` — full gate (schema + syntax + quality, all ERR). Rule table lives in `SKILL.md` Part A4; shapes + conventions in Part B.
- **YAML gotchas** (unquoted `@`, `": "` in scalars, `{...}` escapes, `questions:` wrapper): see `SKILL.md` Part B4.
- **Markdown/mermaid syntax**: run within `learn.sh validate <topic>` (basic fallback if `pymarkdownlnt`/`mmdc` absent).

If any item fails, rewrite affected section. Cite violated principle.
