# PDSNO Good First Issues

This file contains ready-to-open GitHub issue drafts for first-time contributors.

## 1) Fix broken roadmap link in PROJECT_OVERVIEW
- Labels: good first issue, documentation
- Estimated effort: Small (under 1 hour)
- Why this is good-first: One-line docs fix, very low blast radius.

### Skills required
- [ ] Documentation — Markdown, improving existing docs

### Getting started
Open `docs/PROJECT_OVERVIEW.md` and search for `../ROADMAP_AND_TODO.md`. The link is in the "Current Development Stage" section. Check `docs/ROADMAP_AND_TODO.md` to verify the correct relative path, then update the link to point there instead.

### Problem
`docs/PROJECT_OVERVIEW.md` links to `../ROADMAP_AND_TODO.md`, but the roadmap lives under `docs/`.

### Where to work
- `docs/PROJECT_OVERVIEW.md` (roadmap link near current development stage section)

### Acceptance criteria
- [ ] Link points to `docs/ROADMAP_AND_TODO.md`
- [ ] Link works in GitHub Markdown rendering
- [ ] No other links in the edited section are broken

---

## 2) Fix stale threat-model reference in security model doc
- Labels: good first issue, documentation
- Estimated effort: Small (under 1 hour)
- Why this is good-first: Single-file consistency fix.

### Skills required
- [ ] Documentation — Markdown, improving existing docs

### Getting started
Open `docs/security_model.md` and search for references to the threat model file. Look at the bottom of the file where it says "Full threat scenarios and mitigations". Check which file is the canonical threat model doc by searching the repo for `threat_model_and_mitigation.md` vs other variants.

### Problem
`docs/security_model.md` references `docs/architecture/policy_propagation/threat_model_and_mitigation.md`, while canonical threat model doc is `docs/threat_model_and_mitigation.md`.

### Where to work
- `docs/security_model.md`

### Acceptance criteria
- [ ] Reference updated to canonical threat model path
- [ ] The link resolves in GitHub
- [ ] No stale threat-model references remain in this file

---

## 3) Rename typo file treat_model_and_mitigation.md and update references
- Labels: good first issue, documentation
- Estimated effort: Small (under 1 hour)
- Why this is good-first: Bounded rename with straightforward reference updates.

### Skills required
- [ ] Documentation — Markdown, improving existing docs

### Getting started
Start by locating the typo file: `docs/architecture/policy_propagation/treat_model_and_mitigation.md`. Use `git grep" or GitHub search to find all references to "treat_model" in the repository, then update each one. Finally, rename the file using `git mv` to preserve history.

### Problem
File name has typo: `docs/architecture/policy_propagation/treat_model_and_mitigation.md`.

### Where to work
- Rename file under `docs/architecture/policy_propagation/`
- Update any references to the old typo name

### Acceptance criteria
- [ ] File name is corrected (threat vs treat)
- [ ] No references to old typo path remain
- [ ] Docs links still resolve after rename

---

## 4) Replace stale THREAT_MODEL.md reference in policy propagation doc
- Labels: good first issue, documentation
- Estimated effort: Small (under 1 hour)
- Why this is good-first: Minimal change with immediate docs accuracy improvement.

### Skills required
- [ ] Documentation — Markdown, improving existing docs

### Getting started
Open `docs/architecture/policy_propagation/policy_propagation_doc.md` and search for "THREAT_MODEL.md". You'll find it near the end of the document. Check the repository to find the actual threat model doc location, then replace the reference with the correct path.

### Problem
`docs/architecture/policy_propagation/policy_propagation_doc.md` says "See THREAT_MODEL.md", but that file does not exist.

### Where to work
- `docs/architecture/policy_propagation/policy_propagation_doc.md`

### Acceptance criteria
- [ ] Replace stale reference with current threat model document path
- [ ] Link resolves in GitHub Markdown
- [ ] No orphan threat-model references left in this doc

---

## 5) Fix frontmatter depends_on paths in use_cases.md
- Labels: good first issue, documentation
- Estimated effort: Small (under 1 hour)
- Why this is good-first: Metadata-only correction with low risk.

### Skills required
- [ ] Documentation — Markdown, improving existing docs

### Getting started
Open `docs/use_cases.md` and look at the YAML frontmatter at the top (the section between `---` lines). The `depends_on` field has incomplete paths. Look at the actual file structure under `docs/architecture/` to find the correct full paths for each referenced document.

### Problem
`docs/use_cases.md` frontmatter has incomplete `depends_on` paths for architecture docs.

### Where to work
- `docs/use_cases.md`

### Acceptance criteria
- [ ] `depends_on` paths point to existing files
- [ ] Frontmatter remains valid YAML
- [ ] No broken path in the `depends_on` list

---

## 6) Reconcile contradictory checklist items in ROADMAP_AND_TODO
- Labels: good first issue, documentation
- Estimated effort: Medium (1-2 hours)
- Why this is good-first: Clear editing task, no runtime code impact.

### Skills required
- [ ] Documentation — Markdown, improving existing docs

### Getting started
Open `docs/ROADMAP_AND_TODO.md` and search for duplicate entries (use `grep` or your editor's find function). Pay special attention to tasks marked as both complete `[x]` and not started `[ ]` in different sections. Check the repository state (does the file exist? is code implemented?) to determine the correct status for each task.

### Problem
`docs/ROADMAP_AND_TODO.md` has status mismatches and duplicate/contradictory checklist entries (for example, CONTRIBUTING appears both complete and not started in different sections).

### Where to work
- `docs/ROADMAP_AND_TODO.md`

### Acceptance criteria
- [ ] Contradictory duplicate tasks are resolved
- [ ] Status markers reflect current repository reality
- [ ] Roadmap remains internally consistent after edits

---

## 7) Remove duplicate lines in docs index public-scope section
- Labels: good first issue, documentation
- Estimated effort: Small (under 1 hour)
- Why this is good-first: Tiny cleanup, easy review.

### Skills required
- [ ] Documentation — Markdown, improving existing docs

### Getting started
Open `docs/INDEX.md` and scroll to the "Public Documentation Scope" section. You'll see two identical lines in that section. Remove one of them and ensure the list remains readable and complete.

### Problem
`docs/INDEX.md` includes duplicated root-doc scope lines in the public documentation section.

### Where to work
- `docs/INDEX.md`

### Acceptance criteria
- [ ] Duplicate lines removed
- [ ] Public scope list remains complete and readable
- [ ] No accidental changes outside cleanup scope

---

## 8) Add missing script: add_device_credentials.py (referenced by runbook)
- Labels: good first issue, help wanted, scripts
- Estimated effort: Medium (2-4 hours)
- Why this is good-first: Independent utility script with clear CLI behavior.

### Skills required
- [ ] Python (general — data classes, typing, basic OOP)
- [ ] DevOps — Docker, ContainerLab, GitHub Actions

### Getting started
Open `docs/not_for_github/OPERATIONAL_RUNBOOK.md` and search for "add_device_credentials.py" to see how it's called. Create a new Python file in the `scripts/` directory using the existing scripts (like `generate_bootstrap_token.py`) as a template. The script should use `argparse` for CLI argument parsing and the secret manager for storing credentials.

### Problem
`docs/not_for_github/OPERATIONAL_RUNBOOK.md` references `scripts/add_device_credentials.py`, but file does not exist.

### Where to work
- New file: `scripts/add_device_credentials.py`
- Reference source: `docs/not_for_github/OPERATIONAL_RUNBOOK.md`

### Acceptance criteria
- [ ] Script exists with argparse CLI (`--device-id`, `--ip`, `--username`, `--password`)
- [ ] Script validates required args and prints actionable output
- [ ] `python scripts/add_device_credentials.py --help` works
- [ ] Runbook reference is accurate to implemented CLI

---

## 9) Add missing script: backup_database.sh (referenced by runbook)
- Labels: good first issue, devops, scripts
- Estimated effort: Small to Medium (1-2 hours)
- Why this is good-first: Self-contained shell utility with clear success condition.

### Skills required
- [ ] DevOps — Docker, ContainerLab, GitHub Actions

### Getting started
Open `docs/not_for_github/OPERATIONAL_RUNBOOK.md` and search for "backup_database.sh" to see the expected behavior (it's mentioned in a cron job example). Create a new bash script in `scripts/` that uses SQLite's `.backup` command to create a timestamped backup file. Test it locally with `bash scripts/backup_database.sh`.

### Problem
`docs/not_for_github/OPERATIONAL_RUNBOOK.md` references `/opt/pdsno/scripts/backup_database.sh`, but script is missing.

### Where to work
- New file: `scripts/backup_database.sh`
- Reference source: `docs/not_for_github/OPERATIONAL_RUNBOOK.md`

### Acceptance criteria
- [ ] Script creates timestamped SQLite backup
- [ ] Script exits non-zero on failure
- [ ] Script includes usage/help comments at top
- [ ] Runbook command is valid for shipped script

---

## 10) Add missing script: test_device_connection.py (referenced by runbook)
- Labels: good first issue, scripts, networking
- Estimated effort: Medium (2-4 hours)
- Why this is good-first: Bounded diagnostic CLI utility.

### Skills required
- [ ] Python (networking — sockets, Netmiko, PyEZ, eAPI)

### Getting started
Open `docs/not_for_github/OPERATIONAL_RUNBOOK.md` and search for "test_device_connection.py" to see the expected interface. Look at existing scripts in `scripts/` for CLI patterns (argparse usage). The script should do basic connectivity tests (ping, SNMP) and report results clearly. Start with ping and add SNMP if time permits.

### Problem
`docs/not_for_github/OPERATIONAL_RUNBOOK.md` references `scripts/test_device_connection.py --ip <device_ip>`, but script is missing.

### Where to work
- New file: `scripts/test_device_connection.py`
- Reference source: `docs/not_for_github/OPERATIONAL_RUNBOOK.md`

### Acceptance criteria
- [ ] Script accepts `--ip` and runs basic connectivity check
- [ ] Results are clearly reported (success/failure + reason)
- [ ] `--help` output is present and accurate
- [ ] Runbook command matches implemented CLI

---

## 11) Add missing script: check_rbac.py (referenced by runbook)
- Labels: good first issue, scripts, security
- Estimated effort: Medium (2-4 hours)
- Why this is good-first: Focused read-only diagnostic utility.

### Skills required
- [ ] Python (general — data classes, typing, basic OOP)
- [ ] Security — reviewing cryptographic code

### Getting started
Open `docs/not_for_github/OPERATIONAL_RUNBOOK.md` and search for "check_rbac.py" to see its expected usage. Create a Python script in `scripts/` that loads `config/context_runtime.yaml` and queries role/permission info for a given entity ID. Print results in a readable format. Look at `scripts/health_check.py` for pattern examples.

### Problem
`docs/not_for_github/OPERATIONAL_RUNBOOK.md` references `scripts/check_rbac.py --entity-id <approver_id>`, but script is missing.

### Where to work
- New file: `scripts/check_rbac.py`
- Reference source: `docs/not_for_github/OPERATIONAL_RUNBOOK.md`

### Acceptance criteria
- [ ] Script accepts `--entity-id`
- [ ] Script prints role/permission information from available context sources
- [ ] Script handles missing entity gracefully
- [ ] Runbook usage line works as documented

---

## 12) Add missing script: cleanup_old_data.py (referenced by runbook)
- Labels: good first issue, scripts, maintenance
- Estimated effort: Medium (2-4 hours)
- Why this is good-first: Clear operational task and measurable output.

### Skills required
- [ ] Python (general — data classes, typing, basic OOP)
- [ ] Python (SQLite / database operations)

### Getting started
Open `docs/not_for_github/OPERATIONAL_RUNBOOK.md` and search for "cleanup_old_data.py" to see usage examples. Create a Python script in `scripts/` with argparse that accepts `--older-than` (e.g., "30days") and optionally `--dry-run`. Query the NIB SQLite database to find and delete old records from the Event Log table. Log what was deleted.

### Problem
`docs/not_for_github/OPERATIONAL_RUNBOOK.md` references `scripts/cleanup_old_data.py --older-than ...`, but script is missing.

### Where to work
- New file: `scripts/cleanup_old_data.py`
- Reference source: `docs/not_for_github/OPERATIONAL_RUNBOOK.md`

### Acceptance criteria
- [ ] Script accepts `--older-than` (for example: 30days)
- [ ] Script supports dry-run mode
- [ ] Script logs/deletes old records according to policy
- [ ] Runbook examples match script behavior

---

## 13) Implement Azure Key Vault methods in secret manager
- Labels: good first issue, security, python
- Estimated effort: Medium (2-4 hours)
- Why this is good-first: Isolated TODO with existing AWS/Vault patterns to mirror.

### Skills required
- [ ] Python (general — data classes, typing, basic OOP)
- [ ] Security — reviewing cryptographic code

### Getting started
Open `pdsno/security/secret_manager.py` and search for `_store_azure` and `_retrieve_azure`. These methods currently raise `NotImplementedError`. Look at the `_store_aws` and `_retrieve_vault` methods just above them to understand the pattern, then implement the Azure methods following the same structure using the Azure SDK.

### Problem
`pdsno/security/secret_manager.py` has `_store_azure` and `_retrieve_azure` raising `NotImplementedError`.

### Where to work
- `pdsno/security/secret_manager.py`
- `requirements.txt` (if Azure SDK dependencies are required)

### Acceptance criteria
- [ ] `_store_azure` implemented
- [ ] `_retrieve_azure` implemented
- [ ] Errors are handled and logged consistently with other backends
- [ ] Tests or validation steps documented for Azure path

---

## 14) Improve PostgreSQL initialization path in init_db.py
- Labels: good first issue, python, datastore
- Estimated effort: Medium (2-4 hours)
- Why this is good-first: Single-file improvement with clear user-facing result.

### Skills required
- [ ] Python (general — data classes, typing, basic OOP)
- [ ] Python (SQLite / database operations)

### Getting started
Open `scripts/init_db.py` and search for the `_init_postgres_schema` method. It currently exits with "PostgreSQL initialization not yet implemented". Decide whether to implement minimal PostgreSQL support (mirroring SQLite schema) or provide graceful guidance to users. Look at the SQLite implementation as a reference for the schema structure.

### Problem
`scripts/init_db.py` exits with "PostgreSQL initialization not yet implemented".

### Where to work
- `scripts/init_db.py`

### Acceptance criteria
- [ ] PostgreSQL path provides actionable behavior (implement minimal init or graceful explicit guidance)
- [ ] Exit codes and logs are clear
- [ ] Script help text reflects actual support level

---

## 15) Add GitHub Actions workflow for pytest
- Labels: good first issue, devops, ci
- Estimated effort: Small to Medium (1-2 hours)
- Why this is good-first: Standard CI setup with immediate contributor value.

### Skills required
- [ ] DevOps — Docker, ContainerLab, GitHub Actions

### Getting started
Create a new file at `.github/workflows/test.yml`. Look at the GitHub Actions documentation and existing workflow patterns online. The workflow should: install Python 3.11+, install dependencies from `requirements.txt`, and run `pytest`. It should trigger on push to main and on pull requests. Check `CONTRIBUTING.md` to see if CI expectations are documented.

### Problem
Roadmap calls for CI, but there is no workflow file under `.github/workflows/`.

### Where to work
- New file: `.github/workflows/test.yml`
- Optional doc touchpoint: `CONTRIBUTING.md`

### Acceptance criteria
- [ ] Workflow runs on push and pull_request
- [ ] Workflow installs dependencies and runs pytest
- [ ] Workflow uses a supported Python version (3.11+)
- [ ] Badge/status can be seen on pull requests

---

## 16) Implement RC discovery TODOs in distributed example
- Labels: good first issue, python, examples
- Estimated effort: Medium (2-4 hours)
- Why this is good-first: Two explicit TODOs in one function, easy to scope.

### Skills required
- [ ] Python (general — data classes, typing, basic OOP)
- [ ] Architecture / design — no code required

### Getting started
Open `examples/rc_process_distributed.py` and search for "TODO Phase 7". You'll find two TODOs in the `handle_discovery_report` function. Read the Regional Controller module docs to understand what should happen when discovery reports arrive, then implement: (1) writing an audit event to the NIB, and (2) checking discovery counts for anomalies.

### Problem
`examples/rc_process_distributed.py` contains TODOs to trigger anomaly handling and write RC-level audit event on discovery reports.

### Where to work
- `examples/rc_process_distributed.py`

### Acceptance criteria
- [ ] Discovery handler writes an RC-level audit event
- [ ] Simple anomaly trigger path is implemented for high-count reports
- [ ] Behavior is visible via logs and/or a focused test

---

## 17) Fix docs-site repository/source-of-truth links and status wording
- Labels: good first issue, documentation, website
- Estimated effort: Medium (1-3 hours)
- Why this is good-first: External docs polish, no runtime risk.

### Skills required
- [ ] Documentation — Markdown, improving existing docs

### Getting started
Visit the live docs site at https://preacher1045.github.io/PDSNO_DOCS_SITE/ and look for placeholder repository links and status text. Cross-check the homepage against `README.md` and `docs/ROADMAP_AND_TODO.md` in the repository to identify what needs updating. The docs site source is likely in a docs/ or mkdocs/ folder — update the source and verify the site rebuilds correctly.

### Problem
Published docs site currently contains placeholder/stale repository references and status wording that may drift from current repo state.

### Where to work
- Docs site source files (MkDocs content/config for the published site)
- Cross-check against repository docs: `README.md`, `docs/ROADMAP_AND_TODO.md`

### Acceptance criteria
- [ ] Repository link points to the actual project repo
- [ ] Status section matches current repository state
- [ ] Site builds and pages render correctly after updates

---

## 18) Optional cleanup: standardize docs header metadata coverage
- Labels: good first issue, documentation
- Estimated effort: Medium (2-4 hours)
- Why this is good-first: Mechanical docs hygiene task with clear checklist.

### Skills required
- [ ] Documentation — Markdown, improving existing docs

### Getting started
Read `docs/ROADMAP_AND_TODO.md` to see the standard header fields required (`title`, `status`, `author`, `last_updated`, `component`, `depends_on`). Pick a subset of high-value docs (start with `docs/architecture/` subdirectory) and add missing YAML frontmatter to each. Look at `docs/security_model.md` for a good example of proper frontmatter.

### Problem
Roadmap requests standard headers (`title`, `status`, `author`, `last_updated`, `component`, `depends_on`) across docs, but coverage is inconsistent.

### Where to work
- `docs/` markdown files (incremental pass)
- Reference policy: `docs/ROADMAP_AND_TODO.md`

### Acceptance criteria
- [ ] Agreed metadata fields are present on target docs set
- [ ] YAML frontmatter remains valid
- [ ] No broken links introduced by header edits

---

## Priority Order for Opening (Quick Wins First)

Open issues in this order to guide contributors from easiest to harder tasks:

### Tier 1: Quick Fixes (< 1 hour each) — Open first
- [ ] #1 Fix broken roadmap link in PROJECT_OVERVIEW
- [ ] #2 Fix stale threat-model reference in security model doc
- [ ] #4 Replace stale THREAT_MODEL.md reference in policy propagation doc
- [ ] #7 Remove duplicate lines in docs index public-scope section

### Tier 2: Documentation Consistency (1-2 hours each) — Open after tier 1
- [ ] #3 Rename typo file treat_model_and_mitigation.md and update references
- [ ] #5 Fix frontmatter depends_on paths in use_cases.md
- [ ] #6 Reconcile contradictory checklist items in ROADMAP_AND_TODO

### Tier 3: Operational Scripts (2-4 hours each) — Open as capacity allows
- [ ] #8 Add missing script: add_device_credentials.py
- [ ] #9 Add missing script: backup_database.sh
- [ ] #10 Add missing script: test_device_connection.py
- [ ] #11 Add missing script: check_rbac.py
- [ ] #12 Add missing script: cleanup_old_data.py

### Tier 4: Code Implementation (2-4 hours each) — For intermediate contributors
- [ ] #13 Implement Azure Key Vault methods in secret manager
- [ ] #14 Improve PostgreSQL initialization path in init_db.py
- [ ] #16 Implement RC discovery TODOs in distributed example

### Tier 5: Infrastructure & Polish (1-3 hours each) — Optional/parallel work
- [ ] #15 Add GitHub Actions workflow for pytest
- [ ] #17 Fix docs-site repository/source-of-truth links and status wording
- [ ] #18 Optional cleanup: standardize docs header metadata coverage

---

## GitHub Setup: Create Milestones First

Before opening issues, create these 5 milestones in your GitHub repository:

1. Go to **Settings** → **Milestones** → **New Milestone**
2. Create the following (in order):

| Milestone | Description | Target Date (optional) |
|-----------|-------------|----------------------|
| **Tier 1: Quick Wins** | Documentation fixes under 1 hour — start here | ASAP |
| **Tier 2: Docs Consistency** | Documentation consistency and metadata (1-2 hours) | Week 1 |
| **Tier 3: Operational Scripts** | Runbook-referenced scripts (2-4 hours each) | Week 2 |
| **Tier 4: Code Implementation** | Code stubs and backend support (2-4 hours) | Week 3 |
| **Tier 5: Infrastructure & Polish** | CI/CD and optional polish (1-3 hours) | Week 4+ |

Once milestones exist, when you open each issue on GitHub, assign it to the corresponding milestone.

---

## Mapping: Issues to Milestones

- **Tier 1**: Issues #1, #2, #4, #7
- **Tier 2**: Issues #3, #5, #6
- **Tier 3**: Issues #8, #9, #10, #11, #12
- **Tier 4**: Issues #13, #14, #16
- **Tier 5**: Issues #15, #17, #18

---

## Notes for Maintainers
- Create milestones before opening issues so you can assign each issue to one.
- Recommend opening issues incrementally by tier (5-8 at a time) to avoid overwhelming new contributors.
- For each opened issue, use the template below and adapt the provided details.
- For each opened issue, include exact file path(s), expected output, and one command contributors can run to validate completion.

---

## GitHub Issue Template (Copy-Paste Ready)

Use the title and description from each issue above, and adapt this template:

```
**What needs to be done**
[Copy from "Problem" section above]

**Where in the codebase**
- Primary file(s): [from "Where to work"]
- Related reference(s): [from "Reference source"]

**What skills does this require?**
[Check applicable skills from each issue]

**Estimated effort**
[From Estimated effort field]

**Acceptance criteria**
[Copy checklist from "Acceptance criteria" section]

**Getting started hint**
[Provide one command: example: `git log --oneline docs/PROJECT_OVERVIEW.md` to see recent changes to this file]

**Additional context**
See `issues.md` in repo root for complete good-first-issue inventory.
```
