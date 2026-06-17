---
name: wukong-email
description: "Triggered when the user needs to send, read, search/filter, download attachments from, mark as read, or delete email via an IMAP/SMTP mailbox."
version: 1.1.1
author: luochonglie@hotmail.com
license: MIT
metadata:
  hermes:
    tags: [email, smtp, imap, ssl, python, attachments]
---

# Wukong Email Toolkit

A general-purpose Python email toolkit that supports IMAP/SMTP mail servers and can be configured for self-signed or private-CA certificate scenarios.

Core capabilities:

- **SMTP sending**: plain text / HTML / Markdown (auto-converted to HTML + inlined CSS)
- **IMAP receiving**: a two-step SEARCH + FETCH workflow, ~100x faster
- **Attachment handling**: send / receive / download, distinguishing inline images from real attachments
- **Encoded-filename decoding**: RFC 2047 / RFC 2231 / URL encoding all covered
- **Custom SSL**: IMAP and SMTP SSL configured independently; supports standard, self-signed, and private-CA certificates

## When to Use

- The mail server speaks IMAP/SMTP
- You need to adjust SSL verification for self-signed or private-CA certificates
- You need to send HTML/Markdown email (with styling)
- You need to receive email and search/filter/download attachments

**Don't use for**: public mail services (Gmail, Outlook, etc.) → use the standard library or an MCP Email Server.

## Configuration

1. Initialize the user-level config file

```bash
cd ${wukong-email-install-dir}
python3 scripts/init_config.py
```

`init_config.py` creates `~/.wukong-email/.env`; if the file already exists it is not overwritten. After initializing, edit that file and fill in your mailbox account, password, and server settings. The config file is fixed at `~/.wukong-email/.env` — do not place it in the skill install directory, to avoid having personal config overwritten when the skill is upgraded.

After initialization, if `EMAIL_ADDRESS` or `EMAIL_PASSWORD` is empty or still a template placeholder, do not attempt to send or receive mail. First tell the user the config file has been initialized, and ask them to provide:

- `EMAIL_ADDRESS`: mailbox account
- `EMAIL_PASSWORD`: mailbox password
- `EMAIL_FROM_NAME`: sender display name

The password is sensitive. If the user is unwilling to provide it in the conversation, guide them to edit `~/.wukong-email/.env` themselves, then continue with mail operations.

Core config keys:

```bash
# Mailbox credentials
EMAIL_ADDRESS=user@example.com
EMAIL_PASSWORD=your-password
EMAIL_FROM_NAME=Sender Name

# SMTP (sending)
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_SMTP_PORT=465
EMAIL_SMTP_SSL_VERIFY=false

# IMAP (receiving)
EMAIL_IMAP_HOST=imap.example.com
EMAIL_IMAP_PORT=993
EMAIL_IMAP_SSL_VERIFY=false

# Sent folder (friendly name; the system auto-converts it to UTF-7)
EMAIL_SENT_FOLDER=Sent
EMAIL_ATTACHMENTS_DIR=~/.wukong-email/attachments
```

## Script Quick Reference

| Script | Purpose | Detailed docs |
|------|------|----------|
| `send_email.py` | Send email | `references/send_email.md` |
| `list_emails.py` | Search email | `references/list_emails.md` |
| `fetch_emails.py` | Fetch email | `references/fetch_emails.md` |
| `delete_emails.py` | Delete email | `references/delete_emails.md` |
| `mark_read.py` | Mark as read | `references/mark_read.md` |
| `init_config.py` | Initialize `~/.wukong-email/.env` | - |

**⚠️ All scripts must be run from the skill install directory**: `cd ${wukong-email-install-dir} && python3 scripts/xxx.py`

## Common Operations

```bash
# Send email
python3 scripts/send_email.py --to user@example.com --subject "Subject" --body "Body"
python3 scripts/send_email.py --to user@example.com --html --body "# Markdown"

# Search email (JSON by default)
python3 scripts/list_emails.py --days 10
python3 scripts/list_emails.py --days 30 --unread --table

# Fetch email
python3 scripts/fetch_emails.py --uids 2060,2061 --download-attachments

# Delete (preview first, then confirm)
python3 scripts/delete_emails.py --search "SINCE 13-May-2026" --dry-run
python3 scripts/delete_emails.py --search "SINCE 13-May-2026" --yes
```

## Script Detailed Documentation

| Document | Contents |
|------|------|
| `references/send_email.md` | send_email.py — sending email in depth |
| `references/list_emails.md` | list_emails.py — searching email in depth |
| `references/fetch_emails.md` | fetch_emails.py — fetching email in depth |
| `references/delete_emails.md` | delete_emails.py — deleting email in depth |
| `references/mark_read.md` | mark_read.py — marking as read in depth |

## Core Technical Documentation

| Document | Contents |
|------|------|
| `references/imap-search-vs-fetch.md` | IMAP SEARCH vs FETCH workflow, a 100x performance optimization |
| `references/imap-batch-fetch-parsing.md` | Parsing batch FETCH responses (mixed tuple + bytes format) |

## Common Pitfalls

1. **Not running from the skill directory** → you must first locate the wukong-email install directory, then `cd ${wukong-email-install-dir} && python3 scripts/xxx.py`
2. **Config file in the wrong directory** → always use `~/.wukong-email/.env`; do not use a `.env` in the skill root
3. **Sending mail without account/password filled in** → first ask the user to provide `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `EMAIL_FROM_NAME`, or have them edit `~/.wukong-email/.env` themselves
4. **Confusing SSL settings** → IMAP and SMTP are configured independently, via `EMAIL_IMAP_SSL_*` and `EMAIL_SMTP_SSL_*` respectively
5. **Markdown not converted to HTML** → when sending Markdown-styled email you must pass the `--html` flag
6. **Deleting without previewing** → deleting email is irreversible; always preview with `--dry-run` first, then confirm
7. **Pasting raw JSON to the user** → the user cannot see raw terminal output; the agent must format it into a readable summary or table

## Verification Checklist

- [ ] `~/.wukong-email/.env` is configured
- [ ] HTML email uses the `--html` flag
- [ ] `markdown` is installed; if not, install it via `pip install -r requirements.txt` or `uv pip install -r requirements.txt`
