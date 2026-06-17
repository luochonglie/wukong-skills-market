# send_email.py - Send email

Send plain-text, HTML, or Markdown email, with attachment support and automatic save-to-Sent after sending.

## Features

- **Plain text**: sent as-is
- **HTML**: send HTML markup directly
- **Markdown**: auto-detected and converted to HTML (with inlined styles, mail-client compatible)
- **Attachments**: supports multiple attachments
- **Auto-save**: automatically saved to the Sent folder after sending

## Parameters

| Parameter | Description | Required |
|------|------|------|
| `--to` | Recipient(s) (comma-separated for multiple) | ✅ |
| `--subject` | Email subject | ✅ |
| `--body` | Email body | ✅ |
| `--html` | Force HTML format (also works when Markdown is auto-detected) | - |
| `--attach FILE` | Attachment path (may be repeated) | - |
| `--cc` | Cc | - |
| `--bcc` | Bcc | - |

## Markdown auto-conversion

The script auto-detects Markdown syntax (headings, lists, bold, code blocks, tables, etc.) and converts it to HTML with inlined styles.

**Dependency**: `python3-markdown` (`sudo apt install python3-markdown`)

If not installed, it falls back to sending plain text and prints a warning.

## Usage examples

```bash
# Plain text
python3 scripts/send_email.py --to user@example.com --subject "Hello" --body "World"

# Auto-detect Markdown (recommended)
python3 scripts/send_email.py --to user@example.com --subject "Report" --body "
# Today's summary

## Done
- [x] Task A
- [x] Task B

## TODO
1. Task C
2. Task D
"

# Force HTML
python3 scripts/send_email.py --to user@example.com --subject "HTML email" --html --body "<h1>Heading</h1><p>Body</p>"

# With attachment
python3 scripts/send_email.py --to user@example.com --subject "Please review" --body "Attachment sent" --attach report.pdf

# Multiple attachments
python3 scripts/send_email.py --to user@example.com --subject "Multiple attachments" --body "Please review" --attach a.pdf --attach b.pdf

# Multiple recipients + cc
python3 scripts/send_email.py --to a@example.com,b@example.com --cc c@example.com --subject "Broadcast" --body "Body"
```

## Sent folder

After sending, the message is automatically saved to the Sent folder. Smart-detection logic:

1. **Exact match**: configure `EMAIL_SENT_FOLDER=Sent` → matches UTF-7 encoding
2. **Common names**: Sent / Sent Items / Sent Mail
3. **Flag detection**: identified via the `\Sent` flag

## Common issues

| Issue | Cause | Fix |
|------|------|------|
| Markdown not converted to HTML | `--html` not passed | Add `--html`, or let the script auto-detect |
| Send failed | SSL verification failed | Check `EMAIL_SMTP_SSL_VERIFY=false` |
