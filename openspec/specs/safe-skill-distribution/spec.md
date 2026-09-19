# safe-skill-distribution Specification

## Purpose
Define a safe, auditable skill distribution that excludes executable social-engineering payloads and preserves provenance.
## Requirements
### Requirement: Published skills remain in domain

The plugin SHALL publish only skills that support Comfy creation or the plugin's own integration runtime.

#### Scenario: Unrelated prank skill is present

- **WHEN** a skill changes host settings or opens unrelated external media
- **THEN** distribution validation SHALL reject the plugin

### Requirement: Host side effects require consent

Published skills SHALL NOT instruct an agent to change host settings or launch external applications without explicit user confirmation.

#### Scenario: Skill requests an unconfirmed side effect

- **WHEN** validation detects instructions such as changing system volume or opening a browser without confirmation
- **THEN** the validation SHALL fail before release

### Requirement: Skill ownership is explicit

Reusable skills SHALL be managed by an external skill source and plugin-specific skills SHALL be declared separately.

#### Scenario: An undeclared skill directory appears

- **WHEN** a directory under `skills/` is neither externally managed nor declared plugin-local
- **THEN** the vendor check SHALL fail
