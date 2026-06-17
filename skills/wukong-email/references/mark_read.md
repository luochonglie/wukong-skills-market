# mark_read.py - Mark as read

Mark email as read/unread.

## Features

- Search for emails matching criteria
- Bulk mark as read/unread
- Supports a preview mode

## Parameters

| Parameter | Description | Required |
|------|------|------|
| `--before DATE` | Before this date (DD-Mon-YYYY) | - |
| `--days N` | Last N days | - |
| `--from TEXT` | From contains | - |
| `--subject TEXT` | Subject contains | - |
| `--unread` | Mark as unread (defaults to read) | - |
| `--uids UID1,UID2` | Specify UIDs (comma-separated) | - |
| `--dry-run` | Preview mode; do not execute | - |

## Usage examples

```bash
# Preview (recommended: see how many first)
python3 scripts/mark_read.py --before 01-May-2026 --unread --dry-run
python3 scripts/mark_read.py --from "notifications" --unread --dry-run

# Execute the marking
python3 scripts/mark_read.py --before 01-May-2026 --unread   # Unread before May 1
python3 scripts/mark_read.py --from "notifications" --unread  # Notification-style mail
python3 scripts/mark_read.py --days 7 --unread                 # Unread from the last 7 days
python3 scripts/mark_read.py --uids 2296,2297,2298             # Specific UIDs
```

## Workflow

```
# Step 1: preview (see how many are affected)
python3 scripts/mark_read.py --days 30 --unread --dry-run

# Step 2: after confirming, execute
python3 scripts/mark_read.py --days 30 --unread
```
