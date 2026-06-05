# wukong-skills-market

中文 | [English](README.md)

这是一个基于 GitHub 托管的 Wukong Agent skills market。

这个仓库同时面向两类使用者：

- 人可以浏览技能、阅读文档，并手动复制某个 skill 目录。
- 工具可以解析 `marketplace.json`，再根据稳定的相对路径安装技能。

## 目录结构

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

## Market 约定

本仓库采用轻量 skills market 结构：

- `marketplace.json` 是根市场索引。
- `schemas/marketplace.schema.json` 描述根索引格式。
- `schemas/skill.schema.json` 描述单个 skill manifest 格式。
- `skills/<skill-id>/skill.json` 是单个 skill 的 manifest。
- `skills/<skill-id>/SKILL.md` 是 Agent 可读取的 skill 入口。
- `skills/<skill-id>/scripts/` 存放该 skill 的可执行辅助脚本。
- `skills/<skill-id>/references/` 存放该 skill 的参考文档。

## 当前技能

| Skill | 版本 | 说明 |
| --- | --- | --- |
| `wukong-email` | `1.1.0` | 基于 IMAP/SMTP 的邮件自动化 skill，支持发送、读取、搜索、下载附件、标记已读和删除邮件。 |

## 市场索引

根目录的 `marketplace.json` 是机器可读的市场索引。每个 skill 条目指向：

- skill 目录
- skill manifest
- `SKILL.md` 入口文件
- 标签、版本、作者和说明

每个 skill 目录也包含自己的 `skill.json`，因此即使被单独复制出仓库，skill 仍然是自描述的。

## 手动安装

将目标 skill 目录复制到本地 skills 目录。

```powershell
Copy-Item -Recurse skills/wukong-email $env:CODEX_HOME\skills\wukong-email
```

如果没有设置 `CODEX_HOME`，请使用你的 Agent 运行环境配置的 skills 目录。

## 添加技能

在 `skills/<skill-id>/` 下创建新目录，并添加：

- `skill.json`
- `SKILL.md`
- 可选的 `scripts/`
- 可选的 `references/`

然后把该 skill 添加到 `marketplace.json`。

Skill id 必须使用小写 kebab-case，例如 `wukong-email`。

更多规则见 [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)。
