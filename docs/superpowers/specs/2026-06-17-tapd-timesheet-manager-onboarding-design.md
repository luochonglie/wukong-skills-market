# Design: Onboard `tapd-timesheet-manager` into the Skills Market

- **Date:** 2026-06-17
- **Status:** Approved (awaiting written-spec review)
- **Scope:** Add the existing `skills/tapd-timesheet-manager` skill to the market in a contract-compliant way.

## 1. Background

A new skill, `tapd-timesheet-manager`, was placed under `skills/` but only ships a `SKILL.md`. It does not yet satisfy the market contract defined by `README.md`, `docs/CONTRIBUTING.md`, `schemas/marketplace.schema.json`, and `schemas/skill.schema.json`.

Unlike the existing `wukong-email` skill, which is a Python-script skill (it ships `scripts/`, `requirements.txt`, `env.example`), `tapd-timesheet-manager` is a **pure MCP-orchestration skill**. It contains no executable code. Its `SKILL.md` instructs the agent how to call the `mcp-server-tapd` MCP server to query iterations, analyze missing timesheets, distribute hours, and update task status.

## 2. Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Skill shape | Pure orchestration — no `scripts/`, no `references/` | YAGNI; the skill has no reusable scripts or long reference docs today. `skill.schema.json` allows `contents` to be omitted. |
| Metadata authority | `skill.json` is the single source of truth; `SKILL.md` frontmatter keeps only what the agent dispatcher needs | Avoids drift; schema only validates `skill.json`. |
| Frontmatter in `SKILL.md` | Keep `name`, `description`, `version` only | The large MCP `requires` block is removed — MCP dependency is declared once via `skill.json` `compatibility`. |
| Language | All-English | Matches `wukong-email`; market targets an international audience. `SKILL.md` body is translated to English. |
| MCP dependency declaration | `compatibility: { "mcp-server-tapd": ">=1.0.0" }` | The skill is non-functional without that MCP server; declaring it explicitly is more important here than for `wukong-email`. |

## 3. File Changes

### 3.1 New: `skills/tapd-timesheet-manager/skill.json`

Must validate against `schemas/skill.schema.json`.

```json
{
  "$schema": "../../schemas/skill.schema.json",
  "id": "tapd-timesheet-manager",
  "name": "TAPD Timesheet Manager",
  "description": "TAPD timesheet and task management skill for querying iterations, analyzing missing timesheets, distributing hours across tasks, and updating task status via the mcp-server-tapd MCP server.",
  "version": "1.0.0",
  "entrypoint": "SKILL.md",
  "tags": ["tapd", "timesheet", "mcp", "task-management", "project-management"],
  "author": "luochonglie@hotmail.com",
  "license": "MIT",
  "compatibility": {
    "mcp-server-tapd": ">=1.0.0"
  }
}
```

- `contents` is intentionally omitted (allowed by the schema).
- `id` matches the directory name and is lowercase kebab-case.

### 3.2 Rewrite: `skills/tapd-timesheet-manager/SKILL.md`

- **Frontmatter:** keep only `name`, `description` (English), `version`.
- **Remove** the original frontmatter MCP `requires` block (moved to `skill.json`).
- **Translate** the entire body to English, preserving the existing section structure:
  When to use → Core features (iteration query, missing-timesheet analysis, smart hour distribution, task status management) → Typical workflows (monthly backfill, weekly status check, status update) → Implementation details (workday logic, distribution algorithm, error handling, best practices) → Usage examples → MCP tool reference → Performance.
- **Bug fix:** the original frontmatter listed `get_iterations` twice; the dependency/tool list is now centralized in `skill.json`, so this duplication is gone.

### 3.3 Update: root `marketplace.json`

Append a new entry to the `skills` array (keeps `wukong-email` first):

```json
{
  "id": "tapd-timesheet-manager",
  "name": "TAPD Timesheet Manager",
  "description": "TAPD timesheet and task management skill for querying iterations, analyzing missing timesheets, distributing hours across tasks, and updating task status via the mcp-server-tapd MCP server.",
  "version": "1.0.0",
  "path": "skills/tapd-timesheet-manager",
  "manifest": "skills/tapd-timesheet-manager/skill.json",
  "entrypoint": "skills/tapd-timesheet-manager/SKILL.md",
  "tags": ["tapd", "timesheet", "mcp", "task-management", "project-management"],
  "author": "luochonglie@hotmail.com"
}
```

### 3.4 Update: `README.md` and `README.zh-CN.md`

Add a row to each "Available Skills" table:

```
| `tapd-timesheet-manager` | `1.0.0` | TAPD timesheet and task management via the mcp-server-tapd MCP server: query iterations, analyze missing timesheets, distribute hours, and update task status. |
```

(Translated appropriately in the Chinese README.)

## 4. Validation

Per `docs/CONTRIBUTING.md` Validation Checklist, before committing confirm:

- `marketplace.json` parses as JSON.
- `skills/tapd-timesheet-manager/skill.json` parses as JSON.
- `skills/tapd-timesheet-manager/SKILL.md` exists.
- The three ids (directory, `skill.json`, `marketplace.json`) match and are lowercase kebab-case.
- `marketplace.json` validates against `schemas/marketplace.schema.json`.
- `skill.json` validates against `schemas/skill.schema.json`.

## 5. Commit

Single commit:

```
feat: add tapd-timesheet-manager skill to market
```

## 6. Out of Scope

- No `scripts/`, `references/`, `requirements.txt`, or `env.example` for this skill (pure orchestration).
- No changes to `wukong-email` or to the schemas.
- No CI/lint pipeline changes (none exist today; validation is manual per CONTRIBUTING.md).
