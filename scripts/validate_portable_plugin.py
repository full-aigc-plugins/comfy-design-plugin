#!/usr/bin/env python3
"""Validate this package against the Agent Plugins v1.0.0 specification.

The Agent Plugins format is a *closed* portable contract: a conformant client
MUST reject a plugin whose root `plugin.json` is missing or invalid, and MUST
NOT discover any of its components. This script is the machine-checkable half
of the claim that the package conforms, so it validates against the published
schema rules directly rather than trusting a hand-maintained checklist.

Checked here:
  * root `plugin.json`  -- presence, closed top-level field set, `$schema`
    constant, plugin-name constraints, `author` / `extensions` sub-shapes
  * root `mcp.json`     -- when present: `$schema` constant, closed top-level
    field set, version agreement with `plugin.json`, and every server entry
    matching exactly one closed transport variant
  * `skills/`           -- discovery shape (immediate children with SKILL.md)
    and Agent Skills frontmatter for each discovered skill
  * parity              -- identity agreement with the client compatibility
    manifest (`.codex-plugin/plugin.json`) when one is shipped

Pure standard library: no third-party dependency and no network access.

Usage:
    python3 scripts/validate_portable_plugin.py [--root DIR] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# --- Published schema constants (agent-plugins.org 1.0.0) ------------------

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"

# plugin.schema.json: additionalProperties false
PLUGIN_TOP_LEVEL = frozenset(
    {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
)
PLUGIN_REQUIRED = frozenset({"$schema", "name"})

# §5.5 / plugin.schema.json name pattern
NAME_PATTERN = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")

# §5.4: the author object may contain only these three string fields.
AUTHOR_ALLOWED = frozenset({"name", "email", "url"})

# mcp.schema.json: additionalProperties false
MCP_TOP_LEVEL = frozenset({"$schema", "mcpServers"})
MCP_REQUIRED = frozenset({"$schema", "mcpServers"})

# §7.2.1 cwd forms: plugin-relative, or rooted at the two reserved placeholders.
CWD_PATTERN = re.compile(r"^(?:\./|\$\{PLUGIN_ROOT\}(?:/|$)|\$\{PLUGIN_DATA\}(?:/|$))")

# §9.2: a plugin may not override the client-provided variables.
RESERVED_ENV = frozenset({"PLUGIN_ROOT", "PLUGIN_DATA"})

# §7.2.1: a bundled executable must use a plugin-relative command.
BUNDLED_COMMAND_PATTERN = re.compile(r"^\./[^\s]+$")

STDIO_FIELDS = frozenset({"type", "command", "args", "env", "cwd"})
REMOTE_FIELDS = frozenset({"type", "url", "headers"})

IDENTITY_FIELDS = (
    "name",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
)

# §8.2: client-specific files live in a top-level directory named exactly the
# extension namespace. The Agent Plugins registry clients each own one, and the
# packages mirror their non-portable components into the directories those
# clients actually read. The root copies stay in place for the Codex / ZCode /
# Kimi channels, so the mirrors are checked for drift rather than assumed.
CLIENT_EXTENSION_MIRRORS = {
    "com.github.copilot": ("hooks",),  # VS Code and GitHub Copilot
    "dev.openhands": ("commands", "agents", "hooks"),  # OpenHands
}

# Build noise that must never be mirrored or compared.
_IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache"}
_IGNORED_SUFFIXES = {".pyc", ".pyo"}


class Report:
    """Collects findings without aborting on the first problem."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.notes: list[str] = []

    def fail(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def note(self, message: str) -> None:
        self.notes.append(message)


def load_json(path: Path, report: Report, where: str):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        report.fail(where, f"is not readable JSON ({exc})")
        return None


# --- plugin.json (§5) ------------------------------------------------------


def check_plugin_manifest(root: Path, report: Report) -> dict | None:
    where = "plugin.json"
    path = root / "plugin.json"
    if not path.is_file():
        report.fail(
            where,
            "missing. A conformant client MUST reject the plugin and MUST NOT "
            "discover its components (§5.1, §5.3).",
        )
        return None

    manifest = load_json(path, report, where)
    if manifest is None:
        return None
    if not isinstance(manifest, dict):
        report.fail(where, f"must be a top-level JSON object, got {type(manifest).__name__}")
        return None

    unknown = sorted(set(manifest) - PLUGIN_TOP_LEVEL)
    if unknown:
        # Non-fatal for a client, but it is a schema violation and a client
        # will report and ignore these fields (§5.2).
        report.fail(
            where,
            f"unknown top-level field(s) {unknown}. The schema is closed; "
            f"client-specific data belongs under `extensions` (§5.2).",
        )

    missing = sorted(PLUGIN_REQUIRED - set(manifest))
    if missing:
        report.fail(where, f"missing required field(s) {missing} (§5.3)")
        return None

    schema = manifest["$schema"]
    if schema != PLUGIN_SCHEMA:
        report.fail(
            where,
            f"$schema is {schema!r}, expected the canonical identifier "
            f"{PLUGIN_SCHEMA!r} (§5.2).",
        )

    name = manifest["name"]
    if not isinstance(name, str):
        report.fail(where, f"name must be a string, got {type(name).__name__} (§5.3)")
    else:
        if not 1 <= len(name) <= 64:
            report.fail(where, f"name is {len(name)} characters, must be 1-64 (§5.5)")
        if not NAME_PATTERN.match(name):
            report.fail(
                where,
                f"name {name!r} violates §5.5 (lowercase alphanumerics, '-', '.'; "
                f"must start and end alphanumeric; no '--' or '..').",
            )

    version = manifest.get("version")
    if version is not None and not isinstance(version, str):
        report.fail(where, f"version must be a string, got {type(version).__name__} (§5.4)")

    keywords = manifest.get("keywords")
    if keywords is not None and (
        not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords)
    ):
        report.fail(where, "keywords must be an array of strings (§5.4)")

    for scalar in ("description", "homepage", "repository", "license"):
        if scalar in manifest and not isinstance(manifest[scalar], str):
            report.fail(where, f"{scalar} must be a string (§5.4)")

    author = manifest.get("author")
    if author is not None:
        if not isinstance(author, dict):
            report.fail(where, "author must be an object (§5.4)")
        else:
            extra = sorted(set(author) - AUTHOR_ALLOWED)
            if extra:
                report.fail(
                    where,
                    f"author has field(s) {extra}; the author object allows only "
                    f"{sorted(AUTHOR_ALLOWED)} and is otherwise invalid (§5.4).",
                )
            for key, value in author.items():
                if not isinstance(value, str):
                    report.fail(where, f"author.{key} must be a string (§5.4)")

    extensions = manifest.get("extensions")
    if extensions is not None:
        if not isinstance(extensions, dict):
            # Non-fatal: the client reports and ignores it (§8.1).
            report.fail(
                where,
                "extensions must be an object keyed by client extension namespace (§8.1).",
            )
        else:
            for namespace, value in extensions.items():
                if not isinstance(value, dict):
                    report.fail(
                        where,
                        f"extensions[{namespace!r}] must be an object (§8.1).",
                    )
                elif not _looks_like_namespace(namespace):
                    report.note(
                        f"extensions key {namespace!r} is not a reverse-domain "
                        f"namespace (§8 suggests a domain the client controls)."
                    )

    return manifest


def _looks_like_namespace(namespace: str) -> bool:
    return bool(re.match(r"^[a-z0-9]+(?:\.[a-z0-9-]+)+$", namespace))


# --- mcp.json (§7.2) -------------------------------------------------------


def check_mcp_manifest(root: Path, plugin: dict | None, report: Report) -> None:
    path = root / "mcp.json"
    where = "mcp.json"
    if not path.is_file():
        return

    doc = load_json(path, report, where)
    if doc is None:
        return
    if not isinstance(doc, dict):
        report.fail(where, f"must be a top-level JSON object, got {type(doc).__name__}")
        return

    unknown = sorted(set(doc) - MCP_TOP_LEVEL)
    if unknown:
        report.fail(
            where,
            f"unknown top-level field(s) {unknown}; mcp.json allows only "
            f"{sorted(MCP_TOP_LEVEL)} and an invalid document disables MCP for "
            f"the whole plugin (§7.2.1, §7.2.2).",
        )
    missing = sorted(MCP_REQUIRED - set(doc))
    if missing:
        report.fail(where, f"missing required field(s) {missing} (§7.2.1)")
        return

    if doc["$schema"] != MCP_SCHEMA:
        report.fail(
            where,
            f"$schema is {doc['$schema']!r}, expected {MCP_SCHEMA!r} (§7.2.1).",
        )

    # §10.1: the mcp.json version must match the version plugin.json declares.
    if plugin is not None:
        p_schema = plugin.get("$schema")
        m_schema = doc["$schema"]
        if isinstance(p_schema, str) and isinstance(m_schema, str):
            p_version = p_schema.rsplit("/", 2)[-2]
            m_version = m_schema.rsplit("/", 2)[-2]
            if p_version != m_version:
                report.fail(
                    where,
                    f"targets Agent Plugins {m_version} but plugin.json targets "
                    f"{p_version}; a mismatch invalidates this document (§10.1).",
                )

    servers = doc["mcpServers"]
    if not isinstance(servers, dict):
        report.fail(where, f"mcpServers must be an object, got {type(servers).__name__}")
        return

    for server_name, entry in servers.items():
        check_server_entry(f"{where} mcpServers[{server_name!r}]", entry, root, report)


def check_server_entry(where: str, entry, root: Path, report: Report) -> None:
    if not isinstance(entry, dict):
        report.fail(where, f"must be an object, got {type(entry).__name__}")
        return

    kind = entry.get("type")
    if kind is None:
        report.fail(
            where,
            "missing required `type`; each server entry MUST match exactly one "
            "closed transport variant (§7.2.1).",
        )
        return

    if kind == "stdio":
        allowed, required = STDIO_FIELDS, {"type", "command"}
    elif kind in ("streamable-http", "sse"):
        allowed, required = REMOTE_FIELDS, {"type", "url"}
    else:
        report.fail(
            where,
            f"unknown type {kind!r}; valid values are 'stdio', "
            f"'streamable-http', 'sse' (§7.2.1).",
        )
        return

    extra = sorted(set(entry) - allowed)
    if extra:
        report.fail(
            where,
            f"unknown field(s) {extra} for the {kind!r} variant; the variant is "
            f"closed, so this makes the entry invalid (§7.2.1).",
        )
    missing = sorted(required - set(entry))
    if missing:
        report.fail(where, f"missing required field(s) {missing} for {kind!r} (§7.2.1)")
        return

    if kind == "stdio":
        _check_stdio(where, entry, root, report)
    else:
        _check_remote(where, entry, report)


def _check_stdio(where: str, entry: dict, root: Path, report: Report) -> None:
    command = entry["command"]
    if not isinstance(command, str) or not command:
        report.fail(where, "command must be a non-empty string (§7.2.1)")
    elif " " in command.strip():
        report.fail(
            where,
            f"command {command!r} must be a single executable token, not a shell "
            f"command string (§7.2.1).",
        )
    elif command.startswith("./"):
        target = (root / command).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError:
            report.fail(
                where,
                f"command {command!r} escapes the plugin root (§4.1).",
            )

    args = entry.get("args")
    if args is not None and (
        not isinstance(args, list) or not all(isinstance(a, str) for a in args)
    ):
        report.fail(where, "args must be an array of strings (§7.2.1)")

    env = entry.get("env")
    if env is not None:
        if not isinstance(env, dict):
            report.fail(where, "env must be an object of strings (§7.2.1)")
        else:
            reserved = sorted(set(env) & RESERVED_ENV)
            if reserved:
                report.fail(
                    where,
                    f"env declares reserved variable(s) {reserved}; a plugin MUST NOT "
                    f"override them and the entry is invalid (§9.2).",
                )
            for key, value in env.items():
                if not isinstance(value, str):
                    report.fail(where, f"env[{key!r}] must be a string (§9.2)")

    cwd = entry.get("cwd")
    if cwd is not None:
        if not isinstance(cwd, str):
            report.fail(where, "cwd must be a string (§7.2.1)")
        elif not CWD_PATTERN.match(cwd):
            report.fail(
                where,
                f"cwd {cwd!r} must be plugin-relative (starting with './') or rooted "
                f"at ${{PLUGIN_ROOT}} / ${{PLUGIN_DATA}} (§7.2.1).",
            )
        elif cwd.startswith("./"):
            target = (root / cwd).resolve()
            try:
                target.relative_to(root.resolve())
            except ValueError:
                report.fail(where, f"cwd {cwd!r} escapes the plugin root (§4.1)")


def _check_remote(where: str, entry: dict, report: Report) -> None:
    url = entry["url"]
    if not isinstance(url, str) or not url:
        report.fail(where, "url must be a non-empty string (§7.2.1)")
        return
    if "${" in url:
        report.fail(
            where,
            f"url {url!r} must not contain placeholders; clients MUST NOT perform "
            f"placeholder or environment-variable expansion in url (§7.2.1).",
        )
    # §7.2.1: an absolute HTTP or HTTPS URL. Parse, don't prefix-match — a bare
    # `https://` or a URL with an empty host or embedded whitespace must not pass.
    from urllib.parse import urlsplit

    if any(ch.isspace() for ch in url):
        report.fail(where, f"url {url!r} must not contain whitespace (§7.2.1)")
    else:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            report.fail(
                where,
                f"url {url!r} must be an absolute HTTP or HTTPS URL with a host (§7.2.1)",
            )
        elif parts.fragment:
            report.fail(where, f"url {url!r} must not contain a fragment (§7.2.1)")

    headers = entry.get("headers")
    if headers is not None:
        if not isinstance(headers, dict):
            report.fail(where, "headers must be an object of strings (§7.2.1)")
        else:
            seen: dict[str, str] = {}
            for key in headers:
                if not isinstance(key, str):
                    report.fail(where, f"header name {key!r} must be a string (§7.2.1)")
                    continue
                lowered = key.lower()
                if lowered in seen:
                    report.fail(
                        where,
                        f"header {key!r} duplicates {seen[lowered]!r} under different "
                        f"casing; header names are case-insensitive (§7.2.1).",
                    )
                seen[lowered] = key
                if "${" in key:
                    report.fail(
                        where,
                        f"header name {key!r} must not contain placeholders (§7.2.1).",
                    )
            for key, value in headers.items():
                if not isinstance(value, str):
                    report.fail(where, f"header {key!r} value must be a string (§7.2.1)")
                elif "${" in value:
                    report.fail(
                        where,
                        f"header {key!r} value must not contain placeholders; header "
                        f"values are literal visible package data (§7.2.1).",
                    )


# --- skills/ (§6.1, §7.1) --------------------------------------------------

FRONTMATTER_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")


def check_skills(root: Path, report: Report) -> tuple[int, list[str]]:
    where = "skills/"
    skills_dir = root / "skills"
    if not skills_dir.exists():
        # §6.2: a missing fixed location is not an error.
        return 0, []
    if not skills_dir.is_dir():
        report.fail(
            where,
            "exists but is not a directory; the skills component type is invalid "
            "without affecting other component types (§6.2).",
        )
        return 0, []

    discovered: list[str] = []
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir():
            # Stray files are not skills; §7.1 only looks at immediate child dirs.
            report.note(f"skills/{child.name} is a file, not a skill directory")
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            report.note(f"skills/{child.name}/ has no SKILL.md and is not a skill")
            continue
        discovered.append(child.name)
        check_skill_md(f"skills/{child.name}/SKILL.md", child, skill_md, report)
    return len(discovered), discovered


def check_skill_md(where: str, skill_dir: Path, path: Path, report: Report) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    # The opening delimiter must be a line that is exactly `---`; a prefix or
    # substring check would accept `---not-a-fence`.
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        report.fail(where, "missing YAML frontmatter; required by the Agent Skills spec (§7.1)")
        return
    end = -1
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end == -1:
        report.fail(where, "unterminated YAML frontmatter")
        return

    fields: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip().strip('"').strip("'")

    name = fields.get("name", "")
    if not name:
        report.fail(where, "frontmatter is missing `name`")
    else:
        if not FRONTMATTER_NAME_RE.match(name):
            report.fail(where, f"frontmatter name {name!r} is not a valid skill identifier")
        if name != skill_dir.name:
            report.fail(
                where,
                f"frontmatter name {name!r} does not match its directory "
                f"{skill_dir.name!r}; discovery is by directory (§7.1).",
            )
    if not fields.get("description"):
        report.fail(where, "frontmatter is missing `description`")


# --- client extension directories (§8.2) ----------------------------------


def _content_files(directory: Path) -> dict[str, Path]:
    """Map relative path -> file for every real content file under `directory`.

    Dot-prefixed paths are skipped along with build caches — mirrors and scans
    must never treat `.DS_Store`, `.gitignore` or similar as content."""
    found: dict[str, Path] = {}
    if not directory.is_dir():
        return found
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(directory)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if any(part in _IGNORED_PARTS for part in path.parts):
            continue
        if path.suffix in _IGNORED_SUFFIXES:
            continue
        found[str(relative)] = path
    return found


def check_client_extensions(root: Path, report: Report) -> None:
    for namespace, sources in CLIENT_EXTENSION_MIRRORS.items():
        namespace_dir = root / namespace
        if not namespace_dir.exists():
            continue
        if not namespace_dir.is_dir():
            report.fail(
                namespace,
                "exists but is not a directory; an extension directory is a "
                "top-level directory named exactly the namespace (§8.2).",
            )
            continue
        if not _looks_like_namespace(namespace):
            report.fail(
                namespace,
                "is not a reverse-domain namespace (§8 suggests a domain the "
                "owning client controls).",
            )

        for source in sources:
            mirror = namespace_dir / source
            source_dir = root / source
            mirrored = _content_files(mirror)
            original = _content_files(source_dir)

            if mirrored and not original:
                report.fail(
                    f"{namespace}/{source}",
                    f"mirrors a root `{source}/` that no longer exists; remove the "
                    f"stale extension directory (§8.2).",
                )
                continue

            for relative in sorted(set(original) - set(mirrored)):
                report.fail(
                    f"{namespace}/{source}/{relative}",
                    f"is missing from the client extension mirror of `{source}/`; "
                    f"refresh the `{namespace}/{source}/` mirror from the root copy (§8.2).",
                )
            for relative in sorted(set(mirrored) - set(original)):
                report.fail(
                    f"{namespace}/{source}/{relative}",
                    f"has no counterpart in the root `{source}/`; remove the stale "
                    f"mirror file (§8.2).",
                )
            for relative in sorted(set(mirrored) & set(original)):
                if mirrored[relative].read_bytes() != original[relative].read_bytes():
                    report.fail(
                        f"{namespace}/{source}/{relative}",
                        f"has drifted from the root `{source}/` copy; refresh the "
                        f"mirror from the root copy (§8.2).",
                    )

            if mirrored:
                report.note(
                    f"{namespace}/{source}/ mirrors {len(mirrored)} file(s) from "
                    f"the root {source}/"
                )


# --- parity with the client compatibility manifest -------------------------


def check_parity(root: Path, plugin: dict | None, report: Report) -> None:
    compat = root / ".codex-plugin" / "plugin.json"
    if plugin is None or not compat.is_file():
        return
    where = ".codex-plugin/plugin.json"
    other = load_json(compat, report, where)
    if not isinstance(other, dict):
        return

    for field in IDENTITY_FIELDS:
        if field in other and plugin.get(field) != other[field]:
            report.fail(
                where,
                f"{field} disagrees with the portable manifest "
                f"({other[field]!r} vs {plugin.get(field)!r}); the two manifests must "
                f"describe one plugin.",
            )

    def base(value):
        return value.split("+", 1)[0] if isinstance(value, str) else value

    if "version" in other and base(plugin.get("version")) != base(other["version"]):
        report.fail(
            where,
            f"version {other['version']!r} does not share the portable base version "
            f"{plugin.get('version')!r}.",
        )

    interface = other.get("interface")
    if isinstance(interface, dict):
        extensions = plugin.get("extensions")
        openai = extensions.get("com.openai") if isinstance(extensions, dict) else None
        carried = openai.get("interface") if isinstance(openai, dict) else None
        if carried is None:
            report.fail(
                where,
                "declares an `interface` block that the portable manifest does not "
                "carry under extensions['com.openai'] (§8).",
            )
        elif carried != interface:
            report.fail(
                where,
                "the `interface` block has drifted from "
                "extensions['com.openai']['interface'].",
            )


# --- entry point -----------------------------------------------------------


def validate(root: Path) -> Report:
    report = Report()
    if not root.is_dir():
        report.fail("root", f"{root} is not a directory")
        return report
    plugin = check_plugin_manifest(root, report)
    check_mcp_manifest(root, plugin, report)
    count, _ = check_skills(root, report)
    if count:
        report.note(f"{count} skill(s) discovered under skills/")
    check_client_extensions(root, report)
    check_parity(root, plugin, report)
    if (root / ".mcp.json").is_file() and not (root / "mcp.json").is_file():
        report.note(
            "`.mcp.json` is present but `mcp.json` is not; Agent Plugins reads only "
            "`mcp.json` at the plugin root, so these MCP servers are invisible to a "
            "conformant client (§6.1, §7.2.1)."
        )
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="plugin package root (default: the repository containing this script)",
    )
    parser.add_argument("--json", action="store_true", help="emit a machine-readable report")
    args = parser.parse_args(argv)

    report = validate(args.root.resolve())

    if args.json:
        json.dump(
            {
                "root": str(args.root.resolve()),
                "ok": not report.errors,
                "errors": report.errors,
                "notes": report.notes,
            },
            sys.stdout,
            indent=2,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
        return 1 if report.errors else 0

    print(f"Agent Plugins v1.0.0 validation: {args.root.resolve()}")
    for note in report.notes:
        print(f"  note  {note}")
    for error in report.errors:
        print(f"  FAIL  {error}")
    if report.errors:
        print(f"\n{len(report.errors)} problem(s) found.")
        return 1
    print("\nPASS - package conforms to Agent Plugins v1.0.0.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
