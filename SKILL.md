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

Three learning theories fused:

| Theory | Rating | AI Role | Solves |
|--------|--------|---------|--------|
| **Marva Collins** | ★★★★★ | 24/7 Socratic tutor. Endless patience, rigorous text questioning, high expectations. Demands precise answers, pushes deeper. | Marva's weakness: need great teacher. AI never tires. |
| **Feynman Technique** | ★★★★★ | Strict audience + logic auditor. Learner explains concept simply. AI catches gaps, vague language, missing steps. | "Illusion of understanding" — thinking you know when you don't. |
| **Desirable Difficulties** | ★★★★☆ | Flashcard generator, MCQ engine, mixed practice scheduler. Spaced repetition = retrieval difficulty that boosts retention. | Passive re-reading. Forces brain to work during recall. |

### How they combine in one session

| Phase | Theory | What learner does | What AI/CLI does |
|-------|--------|-------------------|------------------|
| **Read** | Marva | Study structured lesson | Writes clear content, sets high bar |
| **Explain** | Feynman | Explain concept in simple terms to "child" | Pokes holes: "you said X but earlier principle says Y — reconcile" |
| **Drill** | Marva + Desirable | Answer MCQs, justify choices | Grades, explains distractors, adds difficulty variants |
| **Judge** | Marva | Critique idea, form opinion | Socratic follow-up: "when would this break?" |
| **Review** | Desirable | SM-2 spaced repetition cards | Schedules optimal recall intervals, mixes topics |

### Marva Collins' Way applied
- **Repetition**: MCQ drill + SRS cycles for repeated exposure
- **Thinking**: Reframe prompts require processing, not just recall
- **Multiple choices**: Test precision of understanding
- **Judge**: Learner evaluates each concept, forms independent opinion
- **Own words**: Reframe step forces personal encoding over parroting

### Feynman Technique applied
- **Explain like I'm 5**: After reading lesson, learner prompted to explain core concept in simplest possible terms
- **Gap detection**: AI scans explanation for vague language ("stuff", "things"), circular reasoning, missing causal links
- **Refine loop**: Identify gap → re-learn that part → explain again → narrower gap each iteration
- **No false fluency**: If learner can't explain simply, they don't understand well enough

### Desirable Difficulties applied
- **Spaced repetition**: SM-2 algorithm. Active recall spaced over days/weeks = harder short-term, stronger long-term
- **Interleaved practice**: Review mixes multiple modules (not block-by-block). Tags enable cross-module mixed sessions
- **Generation effect**: MCQ requires generating answer before seeing options. Explanation written before checking
- **Varied context**: Same concept in different scenarios (pricing → scenario → regulation context)

### Time budget
- Each subject capped at **40h** (13 weeks × 3h/week)
- Modules: 1.5-3h each, ~15-20 modules
- SRS review: ~10-15 min daily

## 2. Content Structure

```
subjects/<topic>/
├── syllabus.yaml             # Course spec
├── modules/
│   ├── NN-module-name/
│   │   ├── lesson.md         # Core content, examples, reframe prompts
│   │   └── quiz.yaml         # 8-10 MCQs
│   └── ...
└── srs/
    ├── deck.json             # SM-2 card state
    └── stats.json            # Study history
```

### syllabus.yaml
```yaml
subject: "Fixed Income Fundamentals"
language: en
time_budget_hours: 40
target_level: intermediate
domain: finance
prerequisites: []
learning_objectives:
  - "Price and yield any bond type"
  - "Calculate duration and convexity"
modules:
  - id: 1
    name: "Bond Fundamentals"
    time_hours: 2
    prerequisites: []
    topics: [terminology, pricing, yield]
```

### quiz.yaml (per module)
```yaml
- id: "1.1"
  question: "Bond selling above par is called a ___ bond"
  options:
    A: discount
    B: premium
    C: par
    D: zero-coupon
  answer: B
  explanation: "Premium: price > face value. Yield < coupon rate."
  difficulty: 1
  tags: [pricing, terminology]
```

## 3. Content Creation Protocol

### A. Scope (15-30 min)
Ask: domain, level, time budget, language, practical use. Propose syllabus.

### B. Per module (10-20 min)
1. Write lesson.md with embedded Feynman prompt + quiz.yaml
2. User reviews, tweaks
3. Proceed

### C. Compile SRS (5 min)
Extract MCQs → SM-2 deck

### Content principles
- **CILO alignment**: Every module must map to ≥1 course learning objective. Content not serving CILOs → skip. "Useless knowledge" rule: if it doesn't help learner meet objectives, don't include.
- **Language**: Create all content in language from syllabus.yaml (`en`/`zh`/`yue`). Questions, explanations, examples all in target language.
- **Practical first**: Start with daily encounters, bridge to theory
- **Domain-relevant examples**: Scenarios from learner's industry
- **MCQ diversity**: 40% recall, 40% application, 20% multi-step
- **Feynman prompt**: Each lesson ends with "Explain [core concept] simply. AI will probe gaps."
- **Desirable difficulty**: MCQs vary difficulty over time. Same concept tested at different angles across modules.
- **Time budget**: Module = ~2h. No module >3h.
- **Progression**: Build on prerequisites. Earlier modules foundational.
- **Skip permitted**: If learner does not specify details (examples, scenarios, depth), generate content anyway — fill gaps with reasonable defaults matching domain and level. Do not block on missing input.

### Content quality rules (mandatory)

Every module MUST pass these checks. If generated content violates any, rewrite before presenting to user.

#### Rule 1: Explain conventions, don't just state them
For every convention or market practice, explain WHY it exists:
- Price quoted as 95–105? It's % of face value ($1,000 par → 95 = $950). Enables comparison across bonds with different face values.
- Semi-annual coupons? Matches bond market convention in US/UK. Affects compounding math.
- Clean vs dirty price? Clean price excludes accrued interest so quoted price doesn't jump on coupon dates.
- 30/360 day count? Simplifies calculation vs actual/actual.

Pattern: state convention → explain origin/purpose → show problem it solves.

#### Rule 2: Answer implicit beginner questions
Learners wonder things the text may not ask. Address these preemptively:
- "Does coupon rate ever change?" → Most bonds: fixed rate, never changes. Floating-rate notes exist but are distinct.
- "Why would anyone pay more than face value?" → Because coupon is higher than prevailing rates. Extra yield justifies premium.
- "What happens at maturity?" → Principal returned. Bond ceases to exist. Price converges to par regardless of purchase price (pull-to-par).
- "What if issuer goes bankrupt?" → Bondholders are creditors, senior to equity. Recovery depends on seniority and collateral.

Each module should anticipate 1-3 such questions and answer them in Core Content.

#### Rule 3: Pull-to-par intuition
Every module involving bond pricing must explain price convergence to face value at maturity:
- A $1,100 bond bought at premium will be worth only $1,000 at maturity → price declines toward par over time.
- A $900 discount bond will be worth $1,000 at maturity → price rises toward par.
- This is NOT driven by market rates. It's mechanical: time remaining shrinks, so remaining cash flows' PV converges to principal.
- Implication: premium bond investors face price depreciation even without rate changes. Discount bond investors get price appreciation (accretion).

#### Rule 4: Causal chain first, formula second
Before showing any formula, explain the intuitive logic:
- Price changes → "New bonds pay 6%. My bond pays 4%. Mine is worth less → price drops until buyer gets same 6% yield."
- Premium/discount → "Compare bond's coupon to current market yield for similar bonds. Coupon > yield? Premium. Coupon < yield? Discount."
- Duration → "Longer maturity = more sensitivity to rate changes because more future payments get re-discounted."
- Convexity → "Price doesn't fall in a straight line. Falls slow down as rates rise (convex)."

#### Rule 5: Practical context for every number
When stating a number or range, explain what it means in practice:
- "YTM 5%" → "If held to maturity and coupons reinvested at 5%, annualized return = 5%. But reinvestment at exact 5% is unlikely — this is a limitation."
- "Duration 7.5 years" → "If rates rise 1%, bond price falls ~7.5%. Works for small changes only (convexity adjustment for large moves)."
- "Investment grade BBB−" → "Lowest rung of IG. One downgrade → falls to HY ('fallen angel'). Many institutional mandates ban HY holdings → forced selling."

#### Rule 6: Answer "how likely" questions explicitly
Learners want to know what's normal vs rare:
- "How often do coupons change?" → For fixed-rate bonds: never. For FRNs: resets periodically (e.g., 3-month SOFR + spread).
- "How often do credit ratings change?" → Infrequent. Stable outlooks common. Negative watch before downgrade.
- "How often yield curve inverts?" → Rare historically. Each inversion preceded recession (though not perfectly predictive).

#### Rule 7: Common misconceptions section (1-2 per module)
Each module must flag 1-2 specific misconceptions beginners hold:
- "Higher coupon = better bond" → No. Higher coupon means more income up front, but lower price appreciation potential. Discount bonds have "built-in" price gain at maturity.
- "YTM is guaranteed return" → No. Assumes reinvestment at same YTM — unrealistic if rates change.
- "AAA bonds are risk-free" → No. Still subject to interest rate risk, inflation risk, liquidity risk. "Risk-free" ≈ government bonds in own currency.

## 4. Study Protocol

### Session types

#### LEARN (45-60 min) — Marva Collins
1. `learn.sh start <subject>` → shows module
2. Read lesson.md
3. Reframe prompt (mental or written)
4. `learn.sh quiz <subject> <module>` → MCQs

#### EXPLAIN (15-20 min) — Feynman Technique
1. Pick concept just studied (or flagged as weak in stats)
2. Explain aloud/in writing as if teaching a child:
   - Use simplest words. No jargon.
   - Give concrete example from daily work
3. AI probes: "You said X. But earlier we learned Y. How do X and Y reconcile?"
   - AI identifies vague language, missing steps, contradictions
   - Learner fills gaps, re-explains
4. Loop until explanation holds without holes

#### REVIEW (10-15 min, daily) — Desirable Difficulties
1. `learn.sh review <subject>` → due cards (SM-2)
2. Cards from multiple modules mixed (interleaved)
3. Correct → interval grows. Wrong → reset to 1d.
4. `learn.sh stats <subject>` → progress, weak areas

#### MIXED (30-45 min) — all three combined
1. REVIEW (10 min): due cards
2. LEARN (20 min): one new module
3. EXPLAIN (5 min): Feynman check on new module's core concept
4. REVIEW (5 min): more due cards

### SM-2 rules
- Correct (q≥3) → interval: 1d → 6d → × ease_factor
- Incorrect → reset 1d
- Ease factor: min 1.3
- Auto-rate: correct = q4, incorrect = q1

### Desirable Difficulties in practice
- **Interleaved decks**: SRS cards tagged by module. Review session mixes 3+ module tags.
- **Varied MCQ difficulty**: Easy recall day 1, harder scenario variants at next interval.
- **Generation**: Learner must type answer before revealing MCQ options (optional CLI mode).
- **Context variation**: Year 2 review of same topic uses different scenarios than year 1.

## 5. CLI

```bash
./scripts/learn.sh init <subject> [lang]         # Create new subject (lang: en|zh|yue, default en)
./scripts/learn.sh start <subject>               # Show overview + modules
./scripts/learn.sh quiz <subject> <module>       # MCQ drill
./scripts/learn.sh explain <subject> <module>    # Feynman prompt + probing guide*
./scripts/learn.sh review <subject>              # SM-2 spaced repetition
./scripts/learn.sh stats <subject>               # Progress + retention
./scripts/learn.sh export <subject>              # Anki CSV export
./scripts/learn.sh feynman <subject> <module>    # Alias for explain
```

*For deeper Feynman probing, enter explanation in opencode chat — AI catches gaps.*



## 6. Cost Model

Powered by **DeepSeek V4 Flash**.

| Phase | Cost |
|-------|------|
| Scope + syllabus | ~$0.01 |
| Per module (~15K tokens output) | ~$0.004 |
| Full course (20 modules, ~300K tokens) | ~$0.08 |
| Per study session | $0 |
| SRS review | $0 |

## 7. Integration

- **Anki**: `learn.sh export <subject>` → CSV/APKG
- **Obsidian/Notion**: Markdown files importable directly
- **Physical**: Print quiz.yaml or lesson.md

## 8. Trigger behavior

Enter content creation mode immediately on trigger:
1. Confirm subject scope iteratively
2. Write module 1
3. Proceed module by module — never generate full course in one shot unless asked
