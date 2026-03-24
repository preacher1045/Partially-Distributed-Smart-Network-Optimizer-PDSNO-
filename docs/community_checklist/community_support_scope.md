# Community Support Scope

## Intent

This document defines what the community edition supports by default and what
is considered advanced or out of scope for best-effort support.

This scope applies only to the Community Edition in this repository.

## In Scope

- Core controller hierarchy behavior (GC/RC/LC)
- NIB-backed state and audit/event flow
- Documented examples under examples/
- Public APIs and workflows described in docs/
- Test and bugfix contributions aligned to current architecture

## Limited Scope

- Experimental features under active development
- Niche deployment patterns not documented in official guides
- Non-default infrastructure combinations

Limited scope items may receive guidance but do not have guaranteed timelines.

## Support Levels

Community support is categorized as:

- Fully supported: documented and tested workflows in active release lines
- Best-effort supported: experimental or less common deployment patterns
- Unsupported: custom/private enterprise requirements and paid services

## Out Of Scope

- Custom feature implementation for specific organizations
- Guaranteed compatibility for all vendor or proprietary environments
- 24x7 incident handling
- Formal compliance attestations and audit packages
- Migration planning for private enterprise stacks

## Enterprise Boundary

The following categories are typically Enterprise Edition candidates when
offered commercially:

- SLA-backed incident response and private support channels
- Compliance reporting packs and formal audit deliverables
- Advanced governance workflows for large organizations
- Deployment consulting and migration services

## Environment Expectations

Community support assumes:

- A currently supported Python version
- Reproducibility with repository setup instructions
- No unsupported local patches changing core behavior

## Support Matrix

| Area | Community Scope | Notes |
|---|---|---|
| Bug triage | Yes | Best-effort |
| Security vulnerability intake | Yes | Via SECURITY.md process |
| Feature requests | Yes | Prioritized by roadmap fit |
| Architecture consultation | Limited | High-level guidance only |
| Deployment consulting | No | Not part of community scope |
| SLA-backed support | No | Reserved for commercial terms |

## How To Get Faster Help

- Provide a minimal reproducible case
- Link relevant logs and configuration snippets
- Reference documentation sections already checked
- Suggest a concrete expected outcome
