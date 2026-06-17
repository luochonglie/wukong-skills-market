# fetch_emails.py - Fetch email

Fetch email content by UID and download attachments.

## Features

- Fetch email content by a UID list
- Download email attachments (auto-distinguishes real attachments from inline images)
- Encoded-filename decoding support (RFC 2047 / RFC 2231 / URL encoding)

## Parameters

| Parameter | Description | Required |
|------|------|------|
| `--uids UID1,UID2,...` | Email UID list (comma-separated) | ✅ |
| `--download-attachments` | Auto-download attachments | - |
| `--force-download` | Force re-download (overwrite existing) | - |
| `--list` | Only list emails; do not show body | - |
| `--full` | Show full body (default: first 500 chars only) | - |
| `--folder FOLDER` | Mailbox folder (default INBOX) | - |
| `--limit N` | Number to fetch (default 10) | - |

## Usage examples

```bash
# List emails (no body shown)
python3 scripts/fetch_emails.py --uids 2060,2061,2062 --list

# Fetch full emails
python3 scripts/fetch_emails.py --uids 2060,2061 --full

# Download attachments
python3 scripts/fetch_emails.py --uids 2060,2061 --download-attachments

# Force re-download
python3 scripts/fetch_emails.py --uids 2060 --download-attachments --force-download
```

## Output description

### --list (list only)

```
=== Email 1/2 ===
UID: 2061
From: Sender <user@example.com>
Subject: Test email
Time: 2026-05-22 08:12:34
Size: 7264 bytes
Attachments: 1
  - document.pdf

=== Email 2/2 ===
...
```

### --download-attachments

```
Fetching emails UID: 2060, 2061
[2060] Subject: Test email
  Found attachment: document.pdf (23456 bytes)
  Saved to: ~/.wukong-email/attachments/2060/document.pdf
  Saved email_info.txt
[2061] Subject: Report
  Found attachment: monthly-report.xlsx (56789 bytes)
  Saved to: ~/.wukong-email/attachments/2061/monthly-report.xlsx
```

## Attachment save location

```
EMAIL_ATTACHMENTS_DIR/
└── <UID>/
    ├── file1.ext
    ├── file2.ext
    └── email_info.txt  # email metadata
```

## Important notes

1. **You must obtain UIDs first**: run `list_emails.py` to get UIDs, then pass them to `fetch_emails.py`
2. **IMAP has no search capability**: FETCH only retrieves data, it cannot search. You must do SEARCH → FETCH in two steps
3. **Batch fetching is faster**: comma-separate UIDs to fetch in one call; do not loop

See: `references/imap-search-vs-fetch.md`
