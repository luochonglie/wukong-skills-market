# list_emails.py - Search email

Search email by criteria and return a UID list (JSON by default).

## Features

- **SEARCH**: server-side filtering, returns all matching UIDs
- **FETCH**: fetches only metadata (UID, date, from, subject, size, attachment count)

## Workflow

```
list_emails.py (search) → get UID list → fetch_emails.py (fetch full content)
```

## Parameters

### Search criteria

| Parameter | Description | Example |
|------|------|------|
| `--days N` | Last N days | `--days 10` |
| `--unread` | Unread email | `--unread` |
| `--seen` | Read email | `--seen` |
| `--from TEXT` | From contains | `--from "notifications"` |
| `--to TEXT` | To contains | `--to "user@example.com"` |
| `--subject TEXT` | Subject contains | `--subject "notice"` |
| `--larger N` | Larger than N bytes | `--larger 1048576` |
| `--smaller N` | Smaller than N bytes | `--smaller 10000` |
| `--flagged` | Flagged | `--flagged` |
| `--unflagged` | Not flagged | `--unflagged` |

### Output control

| Parameter | Description |
|------|------|
| (default) | JSON array, for the agent to parse |
| `--table` | Human-readable table |
| `--output-uids` | Output UIDs only (one per line) |
| `--only-with-attachments` | Show only emails with attachments |
| `--limit N` | At most N emails |

## Output formats

### JSON (default)

```json
[
  {"uid": "2471", "date": "2026-05-22 08:12:34", "from": "Sender <sender@...>", "subject": "Test email", "size": 7264, "attachments": 1},
  {"uid": "2470", "date": "2026-05-21 15:30:00", "from": "Notifications <no-reply@example.com>", "subject": "Task reminder", "size": 4521, "attachments": 0}
]
```

### Table (--table)

```
UID        Time                  From                         Subject                                 Size       Attachments
-------------------------------------------------------------------------------------------------------------------
2471       2026-05-22 08:12:34   Sender <sender@...>          Test email                              7.1 KB    1
2470       2026-05-21 15:30:00   Notifications <no-reply@example.com> Task reminder                    4.4 KB    -
-------------------------------------------------------------------------------------------------------------------
Total: 2 emails
```

## Usage examples

```bash
# All email from the last 10 days (JSON)
python3 scripts/list_emails.py --days 10

# Unread email from the last 30 days (table)
python3 scripts/list_emails.py --days 30 --unread --table

# Specific sender
python3 scripts/list_emails.py --days 7 --from "notifications"

# Only those with attachments
python3 scripts/list_emails.py --days 30 --only-with-attachments --table

# Output UIDs only (for piping)
python3 scripts/list_emails.py --days 10 --only-with-attachments --output-uids

# Limit the count
python3 scripts/list_emails.py --days 30 --limit 50 --table
```

## Piping

Fetch emails that have attachments and download them:

```bash
# Get the UID list
UIDS=$(python3 scripts/list_emails.py --days 10 --only-with-attachments --output-uids | tr '\n' ',' | sed 's/,$//')

# Download attachments
python3 scripts/fetch_emails.py --uids "$UIDS" --download-attachments
```

## Agent usage notes

**⚠️ The JSON output is for the agent to parse!**

- The user cannot see raw terminal output
- The agent must format the results into a readable table/list for the user
- Do not just dump the raw JSON to the user

## Performance notes

- `list_emails.py`: SEARCH + FETCH metadata (~50KB)
- Downloading all mail directly: ~10GB
- **A 100x performance improvement**

See: `references/imap-search-vs-fetch.md`
