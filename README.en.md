# Comfy（ComfyUI 工作流）

> Local image, video, audio and 3D workflows

**Version**: 0.5.0 · **License**: Apache-2.0 · **Skills**: 14

[简体中文](README.md) · [Install](#installation) · [Quick start](#quick-start) · [Project layout](#project-layout)

## Positioning

Local-first ComfyUI workflows for images, video, audio and 3D. Partner models and uploads escalate to Comfy Cloud only when opted in.

This plugin belongs to the engineering-tools line and is for users who need a real operation on a repository or service with verifiable results.

## At a glance

```text
repository / service / config / request
        │
        ▼
Comfy（ComfyUI 工作流） skill (inspect → plan → execute → verify)
        │
        ├── MCP server
        └── pinned CLI / API
        │
        ▼
change + evidence + rollback path
```

## Capabilities and boundaries

| Capability | What it does | Boundary |
|---|---|---|
| Inspect | Read current state and configuration | No edits without authorization |
| Plan | State steps and impact | High-risk actions need explicit confirmation |
| Execute | Operate through MCP or pinned tools | No bypassing permissions or audit |
| Verify | Read back results, logs, and state | Exit code 0 is not goal completion |
| Recover | Keep a rollback path and evidence | No automatic replay when uncertain |

## Architecture and core flow

```text
Host / agent
   │  invokes a skill
   ▼
skills/comfy-design-*  ──►  MCP server / pinned CLI
                              │
                              ▼
                     target system / repository
                              │
                              ▼
                     read back, verify, report
```

Rules:

1. Inspect read-only, then plan, then execute.
2. State the target, scope, credentials, and rollback.
3. Read the real target after execution; do not trust only the exit code.
4. Stop and report when uncertain; never auto-retry side effects.

## Compatibility

| Item | Status |
|---|---|
| Host | Hosts with MCP support |
| Runtime | Follow the plugin manifest and actual environment |
| Platforms | Follow release notes and the target system |

## Installation

```bash
codex plugin marketplace add partme-ai/full-aigc-plugins
codex plugin add comfy-design@full-aigc-plugins
```

Restart the host and start read-only.

## Quick start

1. Confirm target, environment, permissions, and impact.
2. Inspect current state and record a baseline.
3. Make one bounded change.
4. Read back target state, logs, and key metrics.
5. Keep evidence; recover through the rollback path on failure.

## Configuration

Configure the MCP endpoint, authentication, and target environment per plugin docs. Never commit tokens, passwords, or private keys.

## Extension contract

New skills use the `comfy-design-` prefix, declare triggers, permission boundaries, and failure handling, operate through MCP or pinned tools, and read back after every change.

## Retry, idempotency, and recovery

- Inspect the current target state after a failure.
- Do not replay operations with side effects.
- Confirm idempotency and rollback before retrying.
- Keep command, log, and result evidence.

## Data and state

- Read credentials only from secure configuration.
- Record state before and after the change.
- Do not copy production data to uncontrolled directories.

## Security

- Follow least privilege.
- Require explicit confirmation for high-risk actions.
- On a suspected credential leak, rotate before cleaning traces.
- Never bypass audit, permissions, or branch protection.

## Observability and operation

Record command, target, time, result, and key metrics; read back real state before delivery.

## Development and verification

```bash
node --test
python3 -m pytest
```

## Packaging and release

Version matches manifests, marketplace, and tag; after release, reinstall and run one read-only inspection.

## Upgrade and migration

Back up configuration and state; confirm compatibility; reverify connectivity and permissions after migration.

## Troubleshooting

| Symptom | Check |
|---|---|
| Connection fails | Endpoint, network, authentication |
| Permission denied | Role and token scope |
| No effect | Read back target state and logs |
| Uncertain result | Stop retrying and inspect the target |

## Project layout

```text
comfy-design-plugin/
├── .zcode-plugin/      # ZCode manifest
├── .codex-plugin/      # Codex manifest
├── skills/             # 14 skills
├── docs/               # architecture and verification
└── assets/             # icons and static assets
```

## Contributing and support

Include plugin version, host, target environment, command, log, and expected result. Do not attach credentials or production data.

## License

Apache-2.0. See [LICENSE](LICENSE).
