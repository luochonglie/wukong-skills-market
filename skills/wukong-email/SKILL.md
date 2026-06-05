---
name: wukong-email
description: "当用户需要通过 IMAP/SMTP 邮箱发送邮件、读取邮件、搜索/过滤邮件、下载附件、标记已读、删除邮件等操作时触发"
version: 1.1.0
author: luochonglie@hotmail.com
license: MIT
metadata:
  hermes:
    tags: [email, smtp, imap, ssl, python, attachments]
---

# 悟空邮件工具包

基于 Python 的通用邮件工具包，支持 IMAP/SMTP 邮件服务器，并可按需配置自签名或私有 CA 证书场景。

核心能力：
- **SMTP 发送**：纯文本 / HTML / Markdown（自动转 HTML + 内联 CSS）
- **IMAP 接收**：SEARCH + FETCH 两步工作流，100 倍性能提升
- **附件处理**：发送/接收/下载，区分内嵌图片和真实附件
- **中文文件名解码**：RFC 2047 / RFC 2231 / URL 编码全覆盖
- **自定义 SSL**：IMAP/SMTP SSL 配置独立分离，支持标准证书、自签名证书和私有 CA 场景

## When to Use

- 邮件服务器使用 IMAP/SMTP 协议
- 需要为自签名证书或私有 CA 证书调整 SSL 验证
- 需要发送 HTML/Markdown 邮件（带样式）
- 需要接收邮件并搜索/过滤/下载附件

**Don't use for**: 公共邮件服务（Gmail、Outlook 等）→ 用标准库或 MCP Email Server

## 配置
1. 初始化用户级配置文件
```bash
cd ${wukong-email的安装目录}
python3 scripts/init_config.py
```

`init_config.py` 会创建 `~/.wukong-email/.env`；如果文件已存在，不会覆盖。初始化后编辑该文件，填写邮箱账号、密码和服务器配置。配置文件固定为 `~/.wukong-email/.env`，不要放在 skill 安装目录，避免升级 skill 时覆盖个人配置。

初始化后，如果 `EMAIL_ADDRESS` 或 `EMAIL_PASSWORD` 为空，或仍是模板占位值，不要尝试发送或接收邮件。先向用户说明配置文件已初始化，并请用户补充：
- `EMAIL_ADDRESS`：邮箱账号
- `EMAIL_PASSWORD`：邮箱密码
- `EMAIL_FROM_NAME`：发件人显示名称

密码属于敏感信息。如果用户不愿在对话中提供密码，引导用户自行编辑 `~/.wukong-email/.env`，再继续执行邮件操作。

核心配置项：

```bash
# 邮箱凭据
EMAIL_ADDRESS=user@example.com
EMAIL_PASSWORD=your-password
EMAIL_FROM_NAME=Sender Name

# SMTP（发送）
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_SMTP_PORT=465
EMAIL_SMTP_SSL_VERIFY=false

# IMAP（接收）
EMAIL_IMAP_HOST=imap.example.com
EMAIL_IMAP_PORT=993
EMAIL_IMAP_SSL_VERIFY=false

# 已发送文件夹（友好名称，系统自动转 UTF-7）
EMAIL_SENT_FOLDER=已发送
EMAIL_ATTACHMENTS_DIR=~/.wukong-email/attachments
```

## 脚本速查

| 脚本 | 功能 | 详细文档 |
|------|------|----------|
| `send_email.py` | 发送邮件 | `references/send_email.md` |
| `list_emails.py` | 搜索邮件 | `references/list_emails.md` |
| `fetch_emails.py` | 获取邮件 | `references/fetch_emails.md` |
| `delete_emails.py` | 删除邮件 | `references/delete_emails.md` |
| `mark_read.py` | 标记已读 | `references/mark_read.md` |
| `init_config.py` | 初始化 `~/.wukong-email/.env` | - |

**⚠️ 所有脚本必须在 skill 安装目录执行**：`cd ${wukong-email的安装目录} && python3 scripts/xxx.py`

## 常见操作

```bash
# 发送邮件
python3 scripts/send_email.py --to user@example.com --subject "标题" --body "内容"
python3 scripts/send_email.py --to user@example.com --html --body "# Markdown"

# 搜索邮件（默认 JSON）
python3 scripts/list_emails.py --days 10
python3 scripts/list_emails.py --days 30 --unread --table

# 获取邮件
python3 scripts/fetch_emails.py --uids 2060,2061 --download-attachments

# 删除（先预览再确认）
python3 scripts/delete_emails.py --search "SINCE 13-May-2026" --dry-run
python3 scripts/delete_emails.py --search "SINCE 13-May-2026" --yes
```

## 脚本详细文档

| 文档 | 内容 |
|------|------|
| `references/send_email.md` | send_email.py 发送邮件详解 |
| `references/list_emails.md` | list_emails.py 搜索邮件详解 |
| `references/fetch_emails.md` | fetch_emails.py 获取邮件详解 |
| `references/delete_emails.md` | delete_emails.py 删除邮件详解 |
| `references/mark_read.md` | mark_read.py 标记已读详解 |

## 核心技术文档

| 文档 | 内容 |
|------|------|
| `references/imap-search-vs-fetch.md` | IMAP SEARCH vs FETCH 工作流，100倍性能优化 |
| `references/imap-batch-fetch-parsing.md` | 批量 FETCH 响应解析（tuple + bytes 混合格式） |

## Common Pitfalls

1. **未在 skill 目录执行** → 必须先确定 wukong-email 的安装目录，`cd ${wukong-email的安装目录} && python3 scripts/xxx.py`
2. **配置文件放错目录** → 固定使用 `~/.wukong-email/.env`，不要使用 skill 根目录下的 `.env`
3. **未填写账号或密码就发送邮件** → 先请用户补充 `EMAIL_ADDRESS`、`EMAIL_PASSWORD`、`EMAIL_FROM_NAME`，或让用户自行编辑 `~/.wukong-email/.env`
4. **SSL 配置混淆** → IMAP 和 SMTP 独立配置，分别使用 `EMAIL_IMAP_SSL_*` 和 `EMAIL_SMTP_SSL_*`
5. **Markdown 未转 HTML** → 发送 Markdown 样式邮件时必须加 `--html` 参数
6. **删除操作未先预览** → 删除邮件不可逆，必须先用 `--dry-run` 预览，再确认执行
7. **直接贴原始 JSON 给用户** → 用户看不到终端原始输出，Agent 必须整理为可读摘要或表格

## Verification Checklist

- [ ] `~/.wukong-email/.env` 已配置
- [ ] HTML 邮件使用 `--html` 参数
- [ ] `markdown` 确认已安装；如果未安装，用`pip install -r requirements.txt` 或 `uv pip install -r requirements.txt` 安装
