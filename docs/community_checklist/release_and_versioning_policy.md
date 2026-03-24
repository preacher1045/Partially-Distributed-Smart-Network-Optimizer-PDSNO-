# Release and Versioning Policy

This policy defines release behavior for the Community Edition repository.

## Versioning Standard

The project uses semantic versioning:

- MAJOR: incompatible API or behavior changes
- MINOR: backward-compatible functionality additions
- PATCH: backward-compatible bug fixes

Version format: MAJOR.MINOR.PATCH

This policy aligns with Semantic Versioning 2.0.0.

## Branching Model

- main: stable development line
- release/*: optional stabilization branches for upcoming releases
- feature/* and fix/*: contribution branches merged via pull request

## Release Cadence

- Patch releases: as needed for important bug fixes
- Minor releases: periodic, based on roadmap and readiness
- Major releases: infrequent and planned with migration guidance

Enterprise release trains, if offered, may follow separate timelines and are
not governed by this document.

## Release Criteria

A release should include:

- Passing CI and tests for targeted scope
- Updated changelog entry
- Updated documentation for behavior/API changes
- Clear notes on deprecations or migrations

## Changelog Requirements

Each release note should include:

- Added
- Changed
- Fixed
- Security (if applicable)
- Deprecated/Removed (if applicable)

Changelog format should follow Keep a Changelog structure.

## Release Hygiene

- Releases should be created from a clean tagged commit.
- Release tags should be annotated.
- Release notes should link to notable issues/PRs and migration guidance when
  behavior changes.

## Deprecation Policy

- Deprecated features should be clearly labeled in docs and release notes.
- When possible, provide at least one minor release window before removal.
- Removal of core interfaces should include migration instructions.

## Compatibility Expectations

- Patch updates should not break documented behavior.
- Minor updates should keep backward compatibility except for clearly marked
  experimental areas.
- Major versions may include breaking changes with migration notes.
