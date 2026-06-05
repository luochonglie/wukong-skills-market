# Contributing Skills

This repository is a GitHub-hosted skills market. Each skill must be useful as a standalone directory and discoverable through the root market index.

## Required Layout

Each skill lives under `skills/<skill-id>/`.

```text
skills/<skill-id>/
├── skill.json
├── SKILL.md
├── scripts/
└── references/
```

`scripts/` and `references/` are optional when a skill does not need them, but `skill.json` and `SKILL.md` are required.

## Skill Ids

Use lowercase kebab-case ids:

- good: `wukong-email`
- good: `lark-calendar`
- bad: `Wukong_Email`
- bad: `email skill`

The directory name, `skill.json` id, and `marketplace.json` id must match.

## Metadata

When adding or updating a skill:

1. Add or update `skills/<skill-id>/skill.json`.
2. Add or update the matching entry in `marketplace.json`.
3. Keep `version`, `author`, `tags`, and `description` aligned with `SKILL.md`.
4. Use semantic versions such as `1.1.0`.

## Validation Checklist

Before publishing, confirm:

- `marketplace.json` parses as JSON.
- `skills/<skill-id>/skill.json` parses as JSON.
- `skills/<skill-id>/SKILL.md` exists.
- The market entry points to the correct relative paths.
- The skill id uses lowercase kebab-case.

PowerShell quick check:

```powershell
Get-Content marketplace.json | ConvertFrom-Json | Out-Null
Get-Content skills/<skill-id>/skill.json | ConvertFrom-Json | Out-Null
Test-Path skills/<skill-id>/SKILL.md
```
