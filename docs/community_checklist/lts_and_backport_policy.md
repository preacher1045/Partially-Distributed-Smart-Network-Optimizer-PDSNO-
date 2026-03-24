# LTS And Backport Policy

This policy applies to Community Edition branches in the public repository.

## Policy Scope

This document defines long-term support (LTS) expectations and how fixes are
backported across maintained branches.

## LTS Availability

Unless explicitly declared, community releases are standard releases and not LTS.

Enterprise support windows, if offered, are defined by separate commercial
terms and are not implied by this policy.

When an LTS branch is declared, it should include:

- Named branch (for example: release/1.4-lts)
- Start date and planned end-of-support date
- Supported fix categories

## Standard Release Support

- Standard releases receive best-effort fixes on main.
- Users are expected to upgrade to receive most fixes.

Target community support window for standard releases:

- Latest release line: active support
- Previous release line: security and critical fixes only

Older standard lines are considered end-of-support unless explicitly listed as
maintained.

## Backport Eligibility

Backports are generally limited to:

- Security fixes
- Data integrity or corruption risks
- High-severity regressions with low-risk patch scope

Backports are generally not accepted for:

- New features
- Large refactors
- Behavior changes without urgent risk mitigation

## Backport Requirements

For a fix to be backported:

- The fix must be merged to main first
- The patch should be minimal and low risk
- Tests covering the bug must accompany the change
- Cherry-pick conflicts must be resolved without broad refactor

## End Of Support

When a branch reaches end of support:

- It no longer receives bug or security updates from maintainers
- Users should upgrade to a supported branch
- The status should be reflected in release notes or support documentation

## Recommended LTS Window

When an LTS line is declared, the default target window is:

- 18 months total maintenance
- Full fixes early in lifecycle
- Security and critical fixes in final phase

## Transparency

Maintainers should document:

- Active supported branches
- LTS designation status
- Notable accepted or declined backport decisions
