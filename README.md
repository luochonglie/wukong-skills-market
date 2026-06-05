# wukong-skills-market

[中文](README.zh-CN.md) | English

A GitHub-hosted skills market for Wukong agent skills.

This repository is designed for two audiences:

- People can browse skills, read their docs, and copy a skill directory.
- Tools can parse `marketplace.json` and install skills from stable relative paths.

## Directory Structure

```text
.
├── README.md
├── README.zh-CN.md
├── marketplace.json
├── LICENSE
├── docs/
│   └── CONTRIBUTING.md
├── schemas/
│   ├── marketplace.schema.json
│   └── skill.schema.json
└── skills/
    └── <skill-id>/
        ├── skill.json
        ├── SKILL.md
        ├── requirements.txt
        ├── env.example
        ├── scripts/
        └── references/
```

## Market Contract

This repository follows a lightweight skills market contract:

- `marketplace.json` is the root market index.
- `schemas/marketplace.schema.json` describes the root index format.
- `schemas/skill.schema.json` describes each skill manifest.
- `skills/<skill-id>/skill.json` is the per-skill manifest.
- `skills/<skill-id>/SKILL.md` is the agent-readable skill entrypoint.
- `skills/<skill-id>/scripts/` contains executable helpers for the skill.
- `skills/<skill-id>/references/` contains supporting documentation.

## Available Skills

| Skill | Version | Description |
| --- | --- | --- |
| `wukong-email` | `1.1.0` | IMAP/SMTP email automation skill for sending, reading, searching, downloading attachments, marking read, and deleting email. |

## Market Index

The root `marketplace.json` file is the machine-readable market index. Each skill entry points to:

- the skill directory
- the skill manifest
- the `SKILL.md` entrypoint
- tags, version, author, and description

Each skill directory also contains its own `skill.json`, so the skill remains self-describing when copied out of this repository.

## Manual Installation

Copy the target skill directory into your local skills directory.

```powershell
Copy-Item -Recurse skills/wukong-email $env:CODEX_HOME\skills\wukong-email
```

If `CODEX_HOME` is not set, use your agent runtime's configured skills directory.

## Adding a Skill

Create a new directory under `skills/<skill-id>/`, then add:

- `skill.json`
- `SKILL.md`
- optional `scripts/`
- optional `references/`

After that, add the skill to `marketplace.json`.

Skill ids must use lowercase kebab-case, such as `wukong-email`.

More rules are available in [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).
