# Governance Model

This governance model applies to the public Community Edition repository.

## Governance Goals

This project governance model is designed to:

- Keep architectural direction coherent
- Keep decision-making transparent
- Provide a clear contributor path from user to maintainer

## Roles

- Maintainer: merges changes, curates roadmap, enforces project standards
- Reviewer: performs technical review and recommends merge/block decisions
- Contributor: submits issues, documentation updates, and code changes

## Maintainer Responsibilities

- Preserve architectural principles documented in docs/
- Keep releases and changelogs current
- Triaging critical issues and security-impacting regressions
- Ensure contribution process remains clear and fair

## Decision Process

- Routine changes: approved by one maintainer after review
- Architecture-affecting changes: require explicit architecture review
- Breaking changes: require documented migration notes before merge

## Decision Model

- Default model: lazy consensus in public discussion
- Routine code/docs changes: one maintainer approval is sufficient
- High-impact changes: two maintainer approvals are required
- Security-sensitive changes: coordinate with SECURITY.md process

## Community Vs Enterprise Governance

- Community Edition governance is transparent and repository-first.
- Enterprise product governance, if introduced, may include internal product,
	support, and release controls defined by commercial policy.
- Enterprise decisions must not retroactively weaken existing open-source
	obligations in this repository.

## Proposal Workflow

For significant changes, open an issue with:

- Problem statement
- Constraints and tradeoffs
- Proposed design
- Rollout or migration plan

Maintainers may request an RFC-style document for high-impact changes.

## Disagreements

- Technical disagreements are resolved with reproducible evidence,
	measurements, and alignment with architecture documents.
- If consensus is not reached, maintainers make final decisions and record the
	rationale in issue or PR discussion.

## Transparency Requirements

- Architectural decisions should be documented in docs/.
- Significant decisions should be linked from issue/PR history.
- Breaking changes require migration notes before release tagging.

## Maintainer Changes

- New maintainers are nominated based on sustained, high-quality contributions.
- Maintainer status can be removed for long inactivity or policy violations.
- Role changes should be announced in repository discussions or release notes.

## Code Of Conduct

All participation must follow [.github/CODE_OF_CONDUCT.md](../../.github/CODE_OF_CONDUCT.md).
