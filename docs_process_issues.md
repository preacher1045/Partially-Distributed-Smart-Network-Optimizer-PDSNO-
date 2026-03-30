# PDSNO Docs and Process Issue Portfolio

This file contains non-coding issues: documentation quality, contributor process,
and architecture planning proposals.

Templates covered:
- good_first_issue_template.yaml
- bug_report.yaml
- feature_request.yaml
- architectural_proposal.yaml

---

## Section A: Good First Issues (Docs)

Use template: [GOOD FIRST ISSUE] <short description>
Default labels: good first issue, help wanted

### D1) [GOOD FIRST ISSUE] Remove duplicate lines in docs INDEX public-scope section ✅

Labels: good first issue, help wanted, documentation

What needs to be done:
Remove duplicated lines from the Public Documentation Scope section in docs/meta/01_INDEX.md and keep the list complete.

Where in the codebase:
- Primary file: docs/meta/01_INDEX.md

Estimated effort:
Small - under 2 hours

Acceptance criteria:
- [ ] Duplicate lines removed
- [ ] Public scope list remains complete and readable
- [ ] No accidental edits outside cleanup scope

---

### D2) [GOOD FIRST ISSUE] Fix stale threat-model reference in security_model.md ✅

Labels: good first issue, help wanted, documentation

What needs to be done:
Replace stale threat model references in docs/reference/04_security_model.md with docs/reference/05_threat_model_and_mitigation.md.

Where in the codebase:
- Primary file: docs/reference/04_security_model.md
- Related reference: docs/reference/05_threat_model_and_mitigation.md

Estimated effort:
Small - under 2 hours

Acceptance criteria:
- [ ] Canonical threat-model path used everywhere in docs/reference/04_security_model.md
- [ ] Link resolves in GitHub
- [ ] No stale threat-model references remain

---

### D3) [GOOD FIRST ISSUE] Rename typo file treat_model_and_mitigation.md and update references ✅

Labels: good first issue, help wanted, documentation

What needs to be done:
Rename docs/architecture/policy_propagation/treat_model_and_mitigation.md to threat_model_and_mitigation.md and update references.

Where in the codebase:
- Primary file: docs/architecture/policy_propagation/treat_model_and_mitigation.md
- Related references: repository-wide path references

Estimated effort:
Small - under 2 hours

Acceptance criteria:
- [ ] File renamed with correct spelling
- [ ] No references to old typo path remain
- [ ] Updated links resolve

---

### D4) [GOOD FIRST ISSUE] Replace stale THREAT_MODEL.md reference in policy propagation doc ✅

Labels: good first issue, help wanted, documentation

What needs to be done:
Replace THREAT_MODEL.md placeholder reference with canonical threat model path.

Where in the codebase:
- Primary file: docs/architecture/policy_propagation/01_policy_propagation_doc.md
- Related reference: docs/reference/05_threat_model_and_mitigation.md

Estimated effort:
Small - under 2 hours

Acceptance criteria:
- [ ] Stale THREAT_MODEL.md reference removed
- [ ] Correct path linked
- [ ] Link renders correctly in GitHub

---

## Section B: Bug Report Candidates (Docs)

Use template: [BUG] <short description>
Default labels: bug

### D5) [BUG] policy_propagation_doc.md references non-existent THREAT_MODEL.md ✅

Steps to Reproduce:
1. Open docs/architecture/policy_propagation/01_policy_propagation_doc.md.
2. Search for THREAT_MODEL.md.
3. Follow the referenced path.
4. Observe that the target file does not exist.

Expected Behavior:
The threat model reference should point to an existing canonical document path.

---

## Section C: Feature Request Candidates (Process)

Use template: [FEATURE] <short description>
Default labels: enhancement

### D6) [FEATURE] Add issue triage guide to CONTRIBUTING for all template types ✅

Describe the feature:
Add a concise triage and issue-routing section in CONTRIBUTING so contributors know when to use good_first_issue, bug_report, feature_request, or architectural_proposal templates.

Proposed implementation:
- Add "Issue Intake and Triage" section in CONTRIBUTING.md.
- Include template decision tree and minimum issue quality fields.

---

### D7) [FEATURE] Add automated issue labeling policy document ✅

Describe the feature:
Add a documented label taxonomy and assignment policy to keep issue backlog discoverable and contributor-friendly.

Proposed implementation:
- Create docs/issue_labeling_policy.md.
- Define semantic labels: area/*, priority/*, effort/*, type/*.
- Add usage guidance for maintainers.

---

### D8) [FEATURE] Add docs link checker workflow for markdown links ✅

Describe the feature:
Add CI job that validates markdown links in docs and root docs files to prevent stale links reaching contributors.

Proposed implementation:
- Add GitHub Actions workflow using markdown-link-check or equivalent.
- Scope to docs/*.md and root documentation files.
- Fail build on broken internal links.

---

## Section D: Architectural Proposal Candidates

Use template: [ARCH] <short description>
Default labels: architecture

### D9) [ARCH] Define GC failover architecture for controller hierarchy ✅

GitHub issue: #41 (open)

Proposal Summary:
Formalize Global Controller failover strategy currently documented as an open question to reduce operational uncertainty.

Motivation:
Current docs identify GC failover as unresolved. This is a platform-level availability risk for production deployments.

Affected Components:
- [x] Global Controller
- [x] Regional Controller
- [ ] Local Controller
- [ ] Discovery Engine
- [x] Communication Layer
- [x] Data Layer
- [ ] Other

Additional Context:
Reference: docs/foundations/04_controller_hierarchy.md open question note and failover planning discussion.

---

### D10) [ARCH] Formalize adaptive consistency promotion plan from PoC to production ✅

Proposal Summary:
Define a clear transition path from the current PoC consistency behavior (single SQLite backend) to the full adaptive consistency model described in docs/reference/02_nib_spec.md with Phase 6+ dual-backend architecture (PostgreSQL for durable data, Redis for transient data).

Motivation:
The adaptive consistency two-tier data classification is documented as the target production model, but the implementation milestones and migration strategy are not explicit. Contributors need clear understanding of:
- Why the unified SQLite approach is correct for Phases 1-5 (PoC validation before operational complexity)
- What growth signals trigger backend migration (distributed deployments, throughput bottlenecks, durability audit compliance)
- How Phase 6+ dual-backend architecture works without requiring changes to controller logic (via swappable NIBStore abstraction)
- When reconsideration is needed (decision gates, not speculative)

Affected Components:
- [ ] Global Controller
- [ ] Regional Controller
- [ ] Local Controller
- [ ] Discovery Engine
- [ ] Communication Layer
- [x] Data Layer
- [ ] Other

📎 Additional Context:
Complete migration strategy documented in [docs/foundations/07_data_persistence_architecture.md](docs/foundations/07_data_persistence_architecture.md):
- Four growth signals that indicate when to migrate (distribution, throughput, audit compliance, data type mismatch)
- Phase 6+ target architecture diagram (PostgreSQL with Raft consensus for durable data, Redis cluster for transient data, swappable via NIBStore)
- Step-by-step 4-phase migration path (stabilize interface → implement PostgreSQL backend → implement Redis backend → cutover)
- How staged schema split (logical separation in schema.sql now, physical separation later) enables zero-downtime migration

Related issue: Depends on [04_controller_hierarchy.md](docs/foundations/04_controller_hierarchy.md) and [02_nib_spec.md](docs/reference/02_nib_spec.md) durable/transient classification.

---

### D11) [ARCH] Define canonical public-vs-internal docs publication boundary ✅

Proposal Summary:
Codify which docs are publishable vs internal-only and enforce this boundary in docs portal generation.

Motivation:
As contributor count increases, unclear publication boundaries can create confusion and accidental exposure of internal-only docs.

---

## Milestone Mapping (Docs and Process)

1. Quick Wins
- D1, D2, D4, D5

2. Docs Consistency
- D3, D6

3. Operational Scripts
- None in this file

4. Code Implementation
- None in this file

5. Infrastructure & Polish
- D7, D8, D9, D10, D11
