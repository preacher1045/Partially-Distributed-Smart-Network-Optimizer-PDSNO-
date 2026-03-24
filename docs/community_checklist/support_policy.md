# Community Support Policy

This document applies to the public open-source repository and defines the
support model for the Community Edition.

## Purpose

This policy defines what support the project provides to community users,
what is out of scope, and what response expectations contributors can rely on.

This policy follows common open-source best practices:

- Public, issue-tracker based support
- Best-effort (non-SLA) response model
- Explicit support windows documented in release policy

## Support Channels

- GitHub issues are the primary support channel.
- Security issues must follow the process in SECURITY.md and must not be posted
	publicly.
- Architecture questions should include context, expected behavior, and current
	behavior.

## Scope Of Community Support

Community support is best-effort and includes:

- Clarification of documented behavior
- Reproducible bug triage
- Guidance for supported development setup
- Discussion of proposed enhancements

Community support does not guarantee:

- Immediate responses
- Private support sessions
- Custom implementation work
- Backport requests for every branch

## Supported Versions

Version support is defined by active branches documented in release notes.
Community support is focused on:

- main (current development line)
- latest stable release line
- active LTS line, if explicitly declared

## Response Targets

These are goals, not SLA commitments:

- New issue triage: 5 business days
- Reproducible bug acknowledgement: 10 business days
- Pull request first review: 10 business days

## Issue Requirements

Issues should include:

- PDSNO version/commit hash
- Environment details (OS, Python version)
- Reproduction steps
- Expected and actual behavior
- Relevant logs or tracebacks

Issues missing core reproduction detail may be labeled needs-info and closed if
the missing information is not provided.

## Priority Model

- P0: Security or data integrity risk
- P1: Core workflow broken without workaround
- P2: Major feature degraded with workaround
- P3: Minor defects, documentation fixes, and enhancements

## Closure And Staleness

- Resolved issues are closed after fix or documented decision.
- Stale issues may be closed after 30 days without requested follow-up.
- Closed issues can be reopened with new reproducible evidence.

## Relationship To Commercial Support

Community support is best-effort and public.

Enterprise/commercial support, if offered, is governed by separate commercial
agreements and may include private channels, guaranteed response times, and
SLA-backed commitments that are not part of this policy.
