# PDSNO Documentation Index

This is the canonical map for PDSNO documentation.

Use this file as the source of truth for:

- What to read first
- Which document is authoritative for each topic
- Which files are archival and not part of the public-facing documentation surface

## Reading Paths

### Path A: New Contributors (Fast Onboarding)

1. `README.md`
2. `CONTRIBUTING.md`
3. `docs/PROJECT_OVERVIEW.md`
4. `docs/architecture.md`
5. `docs/contribution-rules.md`
6. `docs/use_cases.md`

### Path B: Architecture Deep Dive

1. `docs/PROJECT_OVERVIEW.md`
2. `docs/architecture.md`
3. `docs/controller_hierarchy.md`
4. `docs/communication_model.md`
5. `docs/dataflow.md`
6. `docs/nib_spec.md`
7. `docs/nib_consistency.md`
8. `docs/algorithm_lifecycle.md`
9. `docs/api_reference.md`

### Path C: Security And Governance

1. `SECURITY.md`
2. `docs/security_model.md`
3. `docs/threat_model_and_mitigation.md`
4. `docs/community_checklist/support_policy.md`
5. `docs/community_checklist/release_and_versioning_policy.md`
6. `docs/community_checklist/lts_and_backport_policy.md`
7. `docs/community_checklist/governance_model.md`

### Path D: Operations And Deployment

1. `QUICK_START.md`
2. `docs/deployment_guide.md`
3. `docs/not_for_github/OPERATIONAL_RUNBOOK.md`
4. `deployment/helm/README.md`
5. `examples/README.md`

## Canonical Document Ownership

| Topic | Canonical File |
|------|-----------------|
| Project overview and intent | `README.md` |
| Contribution workflow and PR expectations | `CONTRIBUTING.md` |
| System-level architecture | `docs/architecture.md` |
| Hierarchy and governance boundaries | `docs/controller_hierarchy.md` |
| Communication contracts | `docs/communication_model.md`, `docs/api_reference.md` |
| NIB model and consistency | `docs/nib_spec.md`, `docs/nib_consistency.md` |
| Security model | `docs/security_model.md`, `docs/threat_model_and_mitigation.md` |
| Deployment and operations | `docs/deployment_guide.md`, `docs/not_for_github/OPERATIONAL_RUNBOOK.md` |
| Use-case narratives | `docs/use_cases.md` |
| Roadmap and priorities (internal) | `docs/not_for_github/ROADMAP_AND_TODO.md`, `docs/not_for_github/roadmap.md` |

## Architecture Submodule Documents

| File | Purpose |
|------|---------|
| `docs/architecture/approval_logic/config_approval_logic.md` | Approval logic sequence and decision flow |
| `docs/architecture/device_discovery/device_discovery_sequence.md` | Discovery sequence and interaction flow |
| `docs/architecture/policy_propagation/policy_propagation_doc.md` | Policy propagation model |
| `docs/architecture/verification/README.md` | Verification module entry point |
| `docs/architecture/verification/controller_validation_sequence.md` | Controller validation protocol details |

## Public Documentation Scope

The public-facing documentation surface encompasses all files in the repository root and the docs/ directory, excluding those explicitly listed in the **Archived Internal Files** section below. These locations should remain clean, accurate, and link-stable.

## Archived Internal Files

Internal operational and working documents are intentionally grouped under:

- `docs/not_for_github/OPERATIONAL_RUNBOOK.md`
- `docs/not_for_github/Production_hardening.md`
- `docs/not_for_github/Production_readiness_checklist.md`
- `docs/not_for_github/ROADMAP_AND_TODO.md`
- `docs/not_for_github/roadmap.md`
- `docs/not_for_github/pdsno_gap_analysis.md`
- `docs/not_for_github/research_paper_analysis.md`

These files are preserved for traceability but are not part of the official
external documentation surface.

## Documentation Maintenance Standard

When updating documentation:

1. Update this index if navigation or ownership changed.
2. Keep file names stable unless a rename is necessary.
3. Prefer one canonical document per topic; avoid duplicate specifications.
4. Move temporary/integration notes to `docs/not_for_github/`.
5. Keep links relative and valid in GitHub rendering.
