# PDSNO Documentation Portal Map

This file is intended as a source blueprint for generating an external
documentation site (MkDocs, Docusaurus, Sphinx, or custom static docs).

## Navigation Blueprint

### 1. Introduction

- `README.md` (adapted as homepage)
- `docs/PROJECT_OVERVIEW.md`
- `docs/use_cases.md`

### 2. Core Architecture

- `docs/architecture.md`
- `docs/controller_hierarchy.md`
- `docs/communication_model.md`
- `docs/dataflow.md`
- `docs/algorithm_lifecycle.md`

### 3. Data And Consistency

- `docs/nib_spec.md`
- `docs/nib_consistency.md`

### 4. Protocols And APIs

- `docs/api_reference.md`
- `docs/architecture/verification/controller_validation_sequence.md`
- `docs/architecture/approval_logic/config_approval_logic.md`
- `docs/architecture/device_discovery/device_discovery_sequence.md`
- `docs/architecture/policy_propagation/policy_propagation_doc.md`

### 5. Security And Trust

- `SECURITY.md`
- `docs/security_model.md`
- `docs/threat_model_and_mitigation.md`

### 6. Deployment And Operations

- `QUICK_START.md`
- `docs/deployment_guide.md`
- `deployment/helm/README.md`

Internal operational runbooks and analysis files in `docs/not_for_github/` are
excluded from public documentation site navigation.

### 7. Governance And Community

- `CONTRIBUTING.md`
- `.github/CODE_OF_CONDUCT.md`
- `docs/community_checklist/support_policy.md`
- `docs/community_checklist/release_and_versioning_policy.md`
- `docs/community_checklist/lts_and_backport_policy.md`
- `docs/community_checklist/governance_model.md`
- `docs/community_checklist/community_support_scope.md`

### 8. Internal Planning (Excluded)

- `docs/not_for_github/ROADMAP_AND_TODO.md`
- `docs/not_for_github/roadmap.md`

These files are maintainer planning artifacts and should not be published in the public docs portal.

## Suggested Metadata For Docs Pages

For each page in the docs site, include:

- Page title
- Last updated date
- Scope tag (`concept`, `reference`, `tutorial`, `operations`, `governance`)
- Owner tag (`core`, `security`, `ops`, `community`)

## Authoring Standards For Deep Technical Docs

1. Start with intent and system boundary.
2. Define assumptions and invariants.
3. Include sequence diagrams and message examples for protocol-heavy sections.
4. Keep normative requirements explicit using `MUST`, `SHOULD`, and `MAY`.
5. Separate design rationale from implementation details.
6. Add failure modes and recovery behavior for operational sections.
7. Keep a single canonical source for each contract/schema.

## Exclusion Rule

Do not publish files under `docs/not_for_github/` in the public documentation
portal. They are historical artifacts, not canonical docs.
