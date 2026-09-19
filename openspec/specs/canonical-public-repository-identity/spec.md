# canonical-public-repository-identity Specification

## Purpose
TBD - created by archiving change canonical-public-repository-identity. Update Purpose after archive.
## Requirements
### Requirement: Current public repository identity SHALL match the release repository

The plugin SHALL use its actual GitHub organization and repository name in current manifests, documentation, schema identifiers, tests, and release links.

#### Scenario: A user follows the project homepage

- **WHEN** the user opens a current host manifest or README link
- **THEN** the link resolves to the repository that publishes the referenced release

### Requirement: Current GitHub installation SHALL be immutable

Formal GitHub installation examples and repository-local marketplace entries SHALL pin an existing release tag rather than a moving branch.

#### Scenario: A released version is installed later

- **WHEN** a user repeats the documented GitHub installation command
- **THEN** the resolved source remains the same tagged revision

### Requirement: Historical and host-specific identities SHALL remain truthful

The plugin SHALL retain exact historical repository names, external mirror names, and Codex-specific paths or commands where changing them would falsify evidence or break a host contract.

#### Scenario: Documentation records an external mirror

- **WHEN** the mirror still uses its original repository name
- **THEN** documentation keeps that name and does not present it as the canonical GitHub identity

