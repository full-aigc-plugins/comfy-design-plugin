/**
 * DSH host adapter for an Agent Plugin repository.
 *
 * This file is generated into `<plugin-repo>/dsh/lib/index.js` by
 * `dsh-plugins/scripts/add-dsh-host.mjs`. It is self-contained (Node stdlib
 * only) so the repository keeps working as a Claude/Codex/ZCode/Kimi plugin
 * and gains a DeepSeek Harness host at the same time:
 *
 *   - `skills/<name>/SKILL.md`        -> DSH skill catalog entries
 *   - `commands/*.json`               -> DSH user-invocable skills (`/name`)
 *   - `mcp.json`                      -> `cordis.patch.yml` rows (opt-in)
 *
 * Nothing is copied or rewritten on disk: the provider reads the repository's
 * own files, expands `${CLAUDE_PLUGIN_ROOT}` / `${PLUGIN_ROOT}` /
 * `${PLUGIN_DATA}` / `/mnt/skills/user/<name>` in memory, and tolerates the
 * frontmatter that a strict YAML parser would reject (e.g. a description that
 * contains `: `).
 */

import { existsSync } from 'node:fs'
import { mkdir, readFile, readdir } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { homedir } from 'node:os'
import { fileURLToPath, pathToFileURL } from 'node:url'

/** `<repo>/dsh/lib/index.js` -> `<repo>/` */
const REPO_ROOT = fileURLToPath(new URL('../../', import.meta.url))
const SKILLS_DIR = join(REPO_ROOT, 'skills')
const COMMANDS_DIR = join(REPO_ROOT, 'commands')
const DATA_DIR = process.env.DSH_PLUGIN_DATA || join(homedir(), '.dsh', 'plugin-data', 'comfy-design')

const PROVIDER = 'comfy-design'
const SOURCE = 'agent-plugin:comfy-design'
const RANK = 600 // BUNDLED_SKILL_RANK from @deepseek-ai/dsh-skill
const SKILL_NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

/* --------------------------------------------------------- frontmatter ---- */

/** Split `---\\n...\\n---` from the body; null when the file is not a skill. */
function splitFrontmatter(text) {
  if (!text.startsWith('---')) return null
  const match = /^---\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/.exec(text)
  if (!match) return null
  return { frontmatter: match[1], body: text.slice(match[0].length) }
}

/**
 * Read one top-level scalar. Supports plain, quoted and block scalars; this is
 * deliberately tolerant rather than a full YAML parser, because several source
 * skills contain a `description: ... : ...` line that strict YAML rejects.
 */
function scalar(frontmatter, key) {
  const match = new RegExp(`^${key}:[ \\t]*(.*)$`, 'm').exec(frontmatter)
  if (!match) return undefined
  let raw = match[1].trim()
  if (!/^["']/.test(raw)) raw = raw.replace(/\\s+#.*$/, '')

  if (/^[|>][+-]?$/.test(raw)) {
    const rest = frontmatter.slice(match.index + match[0].length).split(/\r?\n/)
    const lines = []
    for (const line of rest) {
      if (line === '') {
        lines.push('')
        continue
      }
      if (!/^\s+/.test(line)) break
      lines.push(line.replace(/^\s{1,4}/, ''))
    }
    while (lines.length && lines[lines.length - 1] === '') lines.pop()
    if (raw.startsWith('>')) {
      return lines
        .join('\n')
        .replace(/([^\n])\n(?!\n)/g, '$1 ')
        .replace(/\n{2,}/g, '\n')
        .trim()
    }
    return lines.join('\n').trim()
  }
  if (raw.startsWith('"') && raw.endsWith('"')) {
    try {
      return JSON.parse(raw)
    } catch {
      return raw.slice(1, -1)
    }
  }
  if (raw.startsWith("'") && raw.endsWith("'")) return raw.slice(1, -1).replace(/''/g, "'")
  return raw
}

function boolValue(frontmatter, key) {
  const value = scalar(frontmatter, key)
  if (value === undefined) return undefined
  return /^(true|yes|on|1)$/i.test(String(value))
}

/* ------------------------------------------------------------- rewriting -- */

function rewrite(text) {
  return String(text)
    .replace(/\$\{CLAUDE_PLUGIN_ROOT\}/g, REPO_ROOT)
    .replace(/\$CLAUDE_PLUGIN_ROOT\b/g, REPO_ROOT)
    .replace(/\$\{PLUGIN_ROOT\}/g, REPO_ROOT)
    .replace(/\$PLUGIN_ROOT\b/g, REPO_ROOT)
    .replace(/\$\{PLUGIN_DATA\}/g, DATA_DIR)
    .replace(/\$PLUGIN_DATA\b/g, DATA_DIR)
    .replace(/\/mnt\/skills\/user\/([A-Za-z0-9_-]+)/g, (_m, name) => join(REPO_ROOT, 'skills', name))
}

function slugify(value) {
  const slug = String(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/-{2,}/g, '-')
  return SKILL_NAME.test(slug) ? slug : undefined
}

/* -------------------------------------------------------------- provider -- */

function parseSkill(text) {
  const parts = splitFrontmatter(text)
  if (!parts) return undefined
  const name = scalar(parts.frontmatter, 'name')
  const description = scalar(parts.frontmatter, 'description')
  if (!name || !description || !SKILL_NAME.test(name)) return undefined
  const whenToUse = scalar(parts.frontmatter, 'whenToUse')
  const modelOff = boolValue(parts.frontmatter, 'disable-model-invocation')
  const userOff = boolValue(parts.frontmatter, 'user-invocable')
  return {
    name,
    description,
    ...(whenToUse ? { whenToUse } : {}),
    invocation: { modelInvocable: modelOff !== true, userInvocable: userOff !== false },
    body: parts.body,
  }
}

async function listSkills(ctx) {
  if (!existsSync(SKILLS_DIR)) return []
  const out = []
  let entries
  try {
    entries = await readdir(SKILLS_DIR, { withFileTypes: true })
  } catch (error) {
    ctx.logger?.warn?.(`[${PROVIDER}] cannot read skills: ${error}`)
    return out
  }
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (!entry.isDirectory()) continue
    const file = join(SKILLS_DIR, entry.name, 'SKILL.md')
    if (!existsSync(file)) continue
    try {
      const parsed = parseSkill(await readFile(file, 'utf8'))
      if (!parsed) {
        ctx.logger?.warn?.(`[${PROVIDER}] skill ${entry.name} skipped: invalid frontmatter`)
        continue
      }
      out.push({
        name: parsed.name,
        description: parsed.description,
        ...(parsed.whenToUse ? { whenToUse: parsed.whenToUse } : {}),
        invocation: parsed.invocation,
        provider: PROVIDER,
        source: SOURCE,
        resourceBase: { kind: 'directory', path: join(SKILLS_DIR, entry.name) },
        rank: RANK,
        locator: pathToFileURL(file),
        path: file,
        command: false,
      })
    } catch (error) {
      ctx.logger?.warn?.(`[${PROVIDER}] skill ${entry.name} skipped: ${error}`)
    }
  }
  return out
}

async function listCommands() {
  if (!existsSync(COMMANDS_DIR)) return []
  const out = []
  let entries
  try {
    entries = await readdir(COMMANDS_DIR, { withFileTypes: true })
  } catch {
    return out
  }
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (!entry.isFile() || !entry.name.endsWith('.json')) continue
    const file = join(COMMANDS_DIR, entry.name)
    try {
      const definition = JSON.parse(await readFile(file, 'utf8'))
      const name = slugify(definition.name || entry.name.replace(/\.json$/, ''))
      if (!name || typeof definition.prompt !== 'string') continue
      out.push({
        name,
        description: String(definition.description || name),
        invocation: { modelInvocable: false, userInvocable: true },
        provider: PROVIDER,
        source: `${SOURCE}:command`,
        resourceBase: { kind: 'directory', path: REPO_ROOT },
        rank: RANK,
        locator: pathToFileURL(file),
        path: file,
        command: true,
      })
    } catch {
      /* a malformed command file is simply not a command */
    }
  }
  return out
}

const provider = {
  name: PROVIDER,

  async list() {
    const ctx = provider.ctx || {}
    const [skills, commands] = await Promise.all([listSkills(ctx), listCommands()])
    const taken = new Set(skills.map((skill) => skill.name))
    for (const command of commands) {
      let name = command.name
      while (taken.has(name)) name = `${name}-command`
      if (name !== command.name) command.name = name
      taken.add(name)
      skills.push(command)
    }
    return skills
  },

  async get(candidate) {
    if (candidate.command === true) {
      const definition = JSON.parse(await readFile(candidate.path, 'utf8'))
      return {
        name: candidate.name,
        description: candidate.description,
        ...(candidate.whenToUse ? { whenToUse: candidate.whenToUse } : {}),
        invocation: candidate.invocation,
        provider: PROVIDER,
        source: candidate.source,
        resourceBase: candidate.resourceBase,
        content: `# /${candidate.name}\n\n${rewrite(definition.prompt || '')}\n`,
      }
    }
    const parsed = parseSkill(await readFile(candidate.path, 'utf8'))
    if (!parsed) throw new Error(`skill ${candidate.name} has invalid frontmatter`)
    return {
      name: parsed.name,
      description: parsed.description,
      ...(parsed.whenToUse ? { whenToUse: parsed.whenToUse } : {}),
      invocation: parsed.invocation,
      provider: PROVIDER,
      source: SOURCE,
      resourceBase: candidate.resourceBase,
      content: rewrite(parsed.body.replace(/^\n+/, '')),
    }
  },
}

/** Cordis plugin metadata. */
export const name = 'comfy-design'
export const inject = ['skills']

/** Register the repository-backed provider on `ctx.skills`. */
export function apply(ctx) {
  provider.ctx = ctx
  try {
    // PLUGIN_DATA is referenced by several skills; create it eagerly.
    // eslint-disable-next-line no-sync
    if (!existsSync(DATA_DIR)) {
      // mkdir is async but the provider only needs the path to exist before use.
      mkdir(DATA_DIR, { recursive: true }).catch(() => {})
    }
  } catch {
    /* a read-only checkout still serves skills */
  }
  ctx.skills.registerProvider(() => provider)
}
