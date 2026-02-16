---
title: Contributing to PDSNO
status: Active
author: Alexander Adjei
last_updated: 2026-02-16
---

# Contributing to PDSNO

## Before You Start

Read these three documents before writing any code or submitting a PR:
1. `docs/PROJECT_OVERVIEW.md` — what PDSNO is and why it exists
2. `docs/architecture/architecture.md` — the design you are working within
3. `docs/INDEX.md` — map of all documentation

If anything in the architecture is unclear, open an issue and ask before building
something that may need to be rearchitected.

---

## Development Setup

```bash
# 1. Clone the repo
git clone https://github.com/<org>/pdsno.git
cd pdsno

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # test + lint tools

# 4. Initialize the development NIB
python -m pdsno.data.init_nib --env dev

# 5. Run the test suite to confirm everything works
pytest tests/ -v
```

---

## Code Standards

**Python version:** 3.11+. Use type hints on all function signatures.

**NIB access:** No controller module may import or instantiate a storage backend
directly. All NIB access goes through `NIBStore`. If you find yourself writing
`sqlite3.connect(...)` in a controller, stop — that is wrong.

**NIBResult checking:** Every NIBStore method that modifies state returns a
`NIBResult`. You must check it. Do not assume success.

```python
# Wrong
nib.upsert_device(device)

# Right
result = nib.upsert_device(device)
if not result.success:
    nib.write_event(Event(...))
    raise SomeAppropriateError(result.error)
```

**Algorithm structure:** All algorithm modules follow `initialize / execute / finalize`.
See `docs/algorithm_lifecycle.md`.

**Audit first:** Write the NIB audit event before or immediately after the action
it records. Never let a significant state change happen without an Event Log entry.

---

## Architecture Review Rules

Before submitting a PR that touches system design, check these rules
(from `docs/architecture/contibution-rules.md`):

1. Does your change require a controller to trust its own local memory for a
   network fact? → Wrong. Use the NIB.
2. Does your change allow a lower-tier controller to skip a higher-tier approval? → Wrong.
3. Does your change write to the NIB without writing an Event Log entry? → Wrong.
4. Does your change introduce a new interface between controllers not in `api_reference.md`? → Add it to the doc first, then implement.
5. Does your change affect the NIB schema? → Update `nib_spec.md` and write a migration.

---

## Branching and PRs

```
main          — stable, tagged releases only
dev           — integration branch; all feature branches merge here
feature/<name> — your work
fix/<issue>    — bug fixes
```

PR requirements:
- All tests pass (`pytest tests/ -v`)
- No new linting errors (`ruff check .`)
- If you changed architecture: updated relevant doc in `docs/`
- PR description explains *why*, not just *what*

---

## Documentation Standards

If you change behaviour, update the doc. The two must stay in sync.

Document file locations:
- Architecture changes → `docs/architecture/`
- New message type → `docs/api_reference.md`
- New use case → `docs/use_cases.md`
- New NIB table or field → `docs/architecture/nib/nib_spec.md` + migration script

Keep docs in prose with code blocks for pseudocode and schemas. Avoid bullet-point
walls — a sentence explains reasoning better than a list item.

---

## Questions?

Open a GitHub issue tagged `question`. If it touches architecture, tag it
`architecture-review` and it will be reviewed before any related implementation begins.
