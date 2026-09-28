# Portable Agent Plugins migration

**Status: migrated to Agent Plugins v1.0.0.**

This package originally shipped only per-client manifests. None of those is part
of the Agent Plugins format, so a conformant client rejected the package
outright and never reached the 13 skills inside it — a missing root
manifest is fatal, not a warning (§5.1, §5.3).

## What ships now

| File | Role |
|------|------|
| `plugin.json` | Canonical portable manifest (published `agent-plugins.org` 1.0.0 schema) |
| `mcp.json` | Portable MCP configuration (see below) |
| `.codex-plugin/plugin.json` | Codex compatibility manifest, unchanged |
| `.zcode-plugin/plugin.json` | ZCode compatibility manifest, unchanged |
| `kimi.plugin.json` | Kimi compatibility manifest, unchanged |

## Layout rules honoured

- `plugin.json`, `skills/`, `mcp.json` live at the package root.
- The portable manifest declares **only** published-schema fields. The schema is
  closed (`additionalProperties: false`), so it deliberately omits:
  - `interface` — carried at `extensions["com.openai"]["interface"]` (§8)
  - `mcpServers` — discovered from `mcp.json`; it MUST NOT be declared inline (§7.2.1)
  - `skills` — discovered from the fixed `skills/` location; it MUST NOT be declared (§6.1)
- `name` is `comfy-design` — lowercase alphanumerics, `-` and `.` only, starting and
  ending alphanumeric, with no `--` or `..` (§5.5).
- `version` is the **base** version `0.3.0`. The `+codex.<stamp>` build
  metadata in `.codex-plugin/plugin.json` describes that compatibility channel's
  build, not the portable plugin, so it stays there.
- `$schema` is the exact published constant
  `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`.

## Client-owned data

Everything the portable schema has no field for lives under a reverse-domain
client extension namespace (§8):

- `interface`

## Client coverage

`skills/` and `mcp.json` are the portable component types, so **every client in
the [Agent Plugins registry](https://agent-plugins.org/compatible-clients) loads
this package with no client-specific work**: VS Code, Cursor, GitHub Copilot,
ChatGPT & Codex, Kiro, Hermes Agent, OpenClaw, Grok Bot, NanoClaw and OpenHands.

Commands, agents and hooks are explicitly *not* portable, so a client reads them
from the extension directory it owns (§8.2). This package mirrors its
non-portable components accordingly:

- `com.github.copilot/` — `hooks/` for VS Code and GitHub Copilot (they share this namespace)
- `dev.openhands/` — `commands/`, `hooks/` for OpenHands
- `extensions["com.openai"]` — manifest data for ChatGPT & Codex

The root `commands/`, `hooks/` and `agents/` directories are kept unchanged, so
the Codex, ZCode and Kimi channels keep working. `scripts/validate_portable_plugin.py`
fails if a mirror drifts from its root copy.

> **OpenClaw precedence.** OpenClaw checks for a client-specific bundle
> marker (`.codex-plugin/`) before a root `plugin.json`, and treats the
> client-specific format as winning so its richer mappings survive. This
> package ships both, so OpenClaw loads it as a Codex bundle — which keeps
> its commands and hooks working — rather than as an Agent Plugins bundle.
> Removing `.codex-plugin/` would change that, and would break the Codex
> channel, so it stays.

## MCP

`mcp.json` declares 2 server(s):

| Server | Transport |
|--------|------------|
| `comfy-mcp` | `stdio` |
| `comfy-cloud` | `streamable-http` |

The previous `.mcp.json` (Claude Code's dotted convention) is left in
place and unchanged, so clients that load it keep their current
behaviour. Agent Plugins reads only `mcp.json` (§7.2.1), which is why
the dotted file alone left these servers invisible to a conformant
client.

Client-only policy — tool approval modes, per-tool configuration,
startup/tool timeouts and environment-variable allowlists — has no
portable field and was **not** carried into `mcp.json`; the schema is
closed, so an extra field invalidates the whole server entry (§7.2.1).
It remains in `.mcp.json` for the clients that understand it.

## Verifying

The check is machine-runnable and needs no network access or third-party
package:

```bash
python3 scripts/validate_portable_plugin.py
```

It validates the root manifest against the published schema rules (closed field
set, `$schema` constant, name constraints, `author`/`extensions` sub-shapes),
validates `mcp.json` including every closed transport variant and `cwd` form,
checks skill discovery under `skills/`, and asserts identity agreement with the
compatibility manifest.

## References

- [Agent Plugins specification](https://agent-plugins.org/specification)
- [Plugin manifest schema](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json)
- [MCP configuration schema](https://agent-plugins.org/schemas/1.0.0/mcp.schema.json)
