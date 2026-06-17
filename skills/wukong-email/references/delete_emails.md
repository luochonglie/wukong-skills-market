# delete_emails.py - Delete email

Move email to the "Deleted" folder (recoverable).

## Features

- Filter email via IMAP search criteria
- Move to the "Deleted" folder (recoverable from the trash)
- Supports a preview-and-confirm flow

## Parameters

| Parameter | Description | Required |
|------|------|------|
| `--search CRITERIA` | IMAP search criteria | ✅ |
| `--folder FOLDER` | Source folder (default INBOX) | - |
| `--deleted-folder FOLDER` | Target folder (default Trash) | - |
| `--limit N` | Delete at most N | - |
| `--preview N` | Preview the first N (default 10) | - |
| `--dry-run` | Preview mode; do not delete | - |
| `--yes` | Skip confirmation and execute | - |

## IMAP search criteria

| Criterion | Description | Example |
|------|------|------|
| `SINCE "DD-Mon-YYYY"` | After date | `SINCE "13-May-2026"` |
| `BEFORE "DD-Mon-YYYY"` | Before date | `BEFORE "01-May-2026"` |
| `FROM "email"` | Sender | `FROM "spam@example.com"` |
| `SUBJECT "text"` | Subject contains | `SUBJECT "newsletter"` |
| `TO "email"` | Recipient contains | `TO "user@example.com"` |
| `UNSEEN` | Unread | `UNSEEN` |
| `SEEN` | Read | `SEEN` |
| `FLAGGED` | Flagged | `FLAGGED` |

Combinable: `SINCE "13-May-2026" FROM "notifications"`

## Usage examples

```bash
# Preview (dry-run)
python3 scripts/delete_emails.py --search "SINCE 13-May-2026" --dry-run
python3 scripts/delete_emails.py --search 'FROM "spam@example.com"' --dry-run

# Preview count limit
python3 scripts/delete_emails.py --search "UNSEEN" --preview 5 --dry-run

# Execute deletion (preview first, then confirm)
python3 scripts/delete_emails.py --search "SINCE 13-May-2026" --yes

# Limit count
python3 scripts/delete_emails.py --search "UNSEEN" --limit 10 --yes

# Specific subject
python3 scripts/delete_emails.py --search 'SUBJECT "newsletter"' --yes
```

## Mandatory flow (the agent must follow this)

1. **Preview with `--dry-run` first** → show the matched email list
2. **Wait for user confirmation** → the user must explicitly say "delete"/"execute"
3. **Execute with `--yes`** → this is an irreversible operation; never execute directly

```
❌ Wrong: executing deletion directly
python3 scripts/delete_emails.py --search "UNSEEN" --limit 10

✅ Correct: preview → wait for confirmation → execute
# Step 1: preview
python3 scripts/delete_emails.py --search "UNSEEN" --limit 10 --dry-run
# Wait for user confirmation...
# Step 2: execute
python3 scripts/delete_emails.py --search "UNSEEN" --limit 10 --yes
```

## Recovering deleted email

After email is moved to the "Deleted" folder, it can be moved back to INBOX from the "Deleted" folder in the mail client.
