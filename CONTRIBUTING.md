# Contributing to PDSNO

Thank you for your interest in contributing.

This project welcomes code, documentation, tests, design discussions, and bug
reports. Please read this guide before opening a pull request.

## Start Here

Read these documents first:

1. `README.md`
2. `docs/INDEX.md`
3. `docs/PROJECT_OVERVIEW.md`
4. `docs/architecture.md`
5. `docs/contribution-rules.md`

If architecture intent is unclear, open an issue before implementing a large
change.

## Development Setup

```bash
# 1) Clone
git clone https://github.com/AtlasIris/PDSNO.git
cd PDSNO

# 2) Virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3) Dependencies
pip install -r requirements.txt

# 4) Initialize local NIB database
python scripts/init_db.py --db config/pdsno.db

# 5) Verify tests
pytest tests/ -v
```

## Contribution Workflow

1. Open or find an issue describing the change.
2. Create a branch from `main`.
3. Implement the change with tests and documentation updates.
4. Run tests locally.
5. Open a pull request with a clear explanation of behavior changes.

Suggested branch naming:

- `feature/<short-topic>`
- `fix/<short-topic>`
- `docs/<short-topic>`
- `chore/<short-topic>`

## Pull Request Checklist

- Change is scoped and focused.
- Tests added or updated for behavior changes.
- `pytest tests/ -v` passes locally.
- Documentation updated when behavior or interfaces changed.
- PR description includes: problem, approach, validation, and risk.

## Coding Expectations

- Python 3.11+ compatibility.
- Prefer type hints for new/changed code.
- Keep modules cohesive; avoid broad refactors in feature PRs.
- Do not bypass hierarchy/approval semantics without explicit design discussion.

Core architectural constraints:

1. State is authoritative in the NIB.
2. Significant actions must be auditable.
3. Controller hierarchy enforces governance boundaries.

## Documentation Expectations

If code behavior changes, documentation must change in the same PR.

Use these docs as canonical anchors:

- Architecture and design: `docs/architecture.md`
- Communication contracts: `docs/api_reference.md`
- Data model and NIB behavior: `docs/nib_spec.md`
- Security model: `docs/security_model.md`
- Operational behavior: `docs/OPERATIONAL_RUNBOOK.md`

## Security Reporting

Do not open public issues for security vulnerabilities.

Follow `SECURITY.md` for responsible disclosure.

For general support expectations and issue triage scope, see `SUPPORT.md`.

## Community Conduct

All participation must follow `.github/CODE_OF_CONDUCT.md`.
