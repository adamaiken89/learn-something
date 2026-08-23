# Code & File Conventions

Authoritative conventions for this repo. CI enforces the automated subset
(ruff check + ruff format + tests). Everything here reflects current practice —
change code first, then this file, never the reverse.

## Formatting & Lint

| Tool | Config | Gate |
|---|---|---|
| `ruff check` | defaults (line-length 88) | CI + top of `tests/run.sh` |
| `ruff format` | defaults | CI (`--check`) |
| `.editorconfig` | 4-space indent, LF, UTF-8, final newline | editor-level |

- **Ruff is pinned** (`ruff==0.16.4` in CI). Formatter output differs between
  minor versions — upgrade deliberately: bump the pin, run `ruff format`,
  commit formatting churn separately from logic changes.

- Markdown: trailing whitespace preserved (`*.md` exempt in editorconfig).
- YAML: 2-space indent.
- Run `ruff format scripts/ tests/` before committing Python changes.
- Local gate: `bash tests/run.sh` fails fast on lint.

## Repository Layout

```
learn-something/
├── SKILL.md                  # Agent instruction body + schema contract (Part A/B)
├── AGENTS.md                 # Structure + how-to-modify guide
├── CONVENTIONS.md            # This file
├── README.md                 # User docs + prerequisites
├── study-protocol.md         # Learner-facing mirror of SKILL.md Part A5
├── content-verify.md         # Verification checklist (points at SKILL.md B5)
├── VERSION                   # Single-line version
├── scripts/                  # All executable logic (snake_case.py)
├── tests/                    # Zero-dep direct-run suites
├── templates/                # syllabus.yaml / module.md / quiz.yaml / cloze.yaml
└── learn-something-schema/   # Canonical JSON Schemas + py/TS validator wrappers
```

Runtime data lives outside the repo: `~/.coursereader/subjects/<topic>/`
(`syllabus.yaml`, `modules/NN-name/…`, `srs/deck.json`).

## Python Conventions

### Environment
- Runtime: system `python3` (≥3.8). **No venv**; deps installed with
  `pip install --break-system-packages`.
- **Stdlib-first.** Optional deps (`typer`, `yaml`, `markdown`, `pygments`,
  `jsonschema`) must degrade gracefully:

  ```python
  try:
      import yaml
  except ImportError:
      # fallback path or clear message; never a bare crash
  ```

### CLI (learn.py)
- One function per command: `cmd_<name>(topic: str, ...)`.
- Register: `app.command('kebab-name')(cmd_name)` (typer).
- Output: human-readable `print()`; no logging framework.
- Exit codes: `0` success, `1` any failure (validation, missing prerequisite).
- Flags are part of the public API — breaking changes need a migration path.

### Style
- Files `snake_case.py`; functions/variables `snake_case`; constants
  `UPPER_SNAKE`; internal helpers `_leading_underscore`.
- Triple-quoted docstrings on public functions; `Args:` section when
  parameters aren't self-evident.
- Prefer `pathlib.Path`; `os.path` tolerated only in pre-existing epub/pdf code.
- Type hints: optional, match surrounding module.

### Failure philosophy
- **Fail fast on environment prerequisites.** Pattern (see
  `mermaidcheck.resolve_mmdc`): resolve tool → if absent, hard error +
  actionable install hint + exit 1. Never silently downgrade a validation.
- Validation errors report location (`module: block N: message`) and exit 1.
- Generators may back up files (`.bak`) before overwriting and say so.

## Data & File Naming

- Module dirs: `NN-name` — zero-padded two-digit number + kebab-case slug.
- lesson.md H1: `# Module NN: <Human Title>` — colon + human title, never the slug.
- Quiz YAML: exactly 4 options, 1 correct, difficulty 1–3; answers re-lettered
  by `quizbalance` into balanced spread.
- Canonical data shapes: JSON Schema files in `learn-something-schema/schemas/`
  are the source of truth; validators wrap them, never re-implement.
- Mermaid: theme `neutral`; palette `#5c7a99/#5c8a6a/#b8924a/#b86a4a/#7a5a8a/#888`,
  strokes `#333`. Validation = mmdc only (hard prerequisite).

## Documentation Single Sources

| Topic | Source | Everyone else |
|---|---|---|
| 17 quality rules | SKILL.md Part A4 | mirror nothing |
| Automated checks table | SKILL.md Part B5 | content-verify.md links only |
| Study protocol | SKILL.md Part A5 | mirrored verbatim in study-protocol.md |
| Structure / modification | AGENTS.md | — |
| Schema contract | SKILL.md Part B + schemas/ | — |

Docs drift is a bug. Fix code + source doc together in one commit.

## Tests

- Runner: plain `python3 tests/test_<area>.py` — **no pytest**.
  `tests/run.sh` runs all suites + ruff gate.
- Discovery: every callable starting `test_` in module globals runs
  automatically (sorted); print `<name>: OK` per test, summary `N/N passed`.
- Imports: `sys.path.insert(0, .../scripts)` then import modules directly.
- Mocking: save/restore attributes around the call (try/finally) — no mock lib:

  ```python
  orig = mod.func
  try:
      mod.func = lambda ...: ...
      ...
  finally:
      mod.func = orig
  ```

- Fixtures: module-level `GOOD_*` / `BAD_*` string constants near their tests.
- Coverage rule: every feature ships ≥2 tests (happy path + error case).
- Optional-tool tests (`mmdc`): skip with printed reason when the tool is
  unavailable offline — never fail the suite for a missing environment extra.
- Temp data: `tempfile.TemporaryDirectory()`, cleaned up implicitly.

## Workflow Checklist (per change)

1. Edit code + its single-source doc together.
2. `ruff format scripts/ tests/ && ruff check scripts/ tests/`
3. `bash tests/run.sh` — all suites green.
4. Smoke affected CLI command against a real course in `~/.coursereader/subjects`.
5. Commit (conventional style: `feat:/fix:/docs:/test:/chore:` scope optional).
