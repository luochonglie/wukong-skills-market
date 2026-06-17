# IMAP SEARCH vs FETCH command comparison

## Core conclusion

**❌ The IMAP FETCH command has no search capability!**

You must use a **two-step workflow**:
1. **SEARCH** command → filter email, returns a UID list
2. **FETCH** command → fetch email data for the specified UIDs

---

## Command comparison

### IMAP SEARCH command (search/filter)

| Item | Description |
|------|------|
| **Purpose** | Search/filter email |
| **Returns** | A **UID list** of matching items |
| **Trait** | ⚡ **does not download email content** (fast) |

**Example**:
```python
# Search email from the last 10 days
status, messages = imap.search(None, 'SINCE "13-May-2026"')

# Returns: b'2035 2036 2037 2038 2039 ...' (UID list)
# Result: 54 emails found
```

**Supported search criteria**:
- `SINCE "13-May-2026"` - date
- `FROM "user@example.com"` - sender
- `SUBJECT "test"` - subject
- `TO "user@example.com"` - recipient
- `SEEN` / `UNSEEN` - read / unread
- `FLAGGED` / `UNFLAGGED` - flagged / not flagged
- `LARGER 100000` - larger than 100KB
- `SMALLER 1000000` - smaller than 1MB
- Combinable: `SINCE "13-May-2026" FROM "user@example.com"`

See: `imap-search-syntax.md`

---

### IMAP FETCH command (fetch data)

| Item | Description |
|------|------|
| **Purpose** | Fetch email data |
| **Returns** | Email content (headers, body, attachments, etc.) |
| **Trait** | ⚠️ **downloads email content** (partial fetches are possible) |

**Example**:
```python
# Fetch the full email
status, data = imap.fetch(uid, 'RFC822')  # downloads the full email (may be large)

# Fetch headers only
status, data = imap.fetch(uid, 'RFC822.HEADER')  # downloads headers only (small)

# Fetch the structure
status, data = imap.fetch(uid, 'BODYSTRUCTURE')  # downloads structure info only (tiny)

# Batch-fetch basic info
status, data = imap.fetch(uids, '(UID FLAGS INTERNALDATE RFC822.SIZE)')  # metadata only
```

**Data you can fetch**:
- `RFC822` - full email
- `RFC822.HEADER` - headers
- `RFC822.SIZE` - email size
- `BODYSTRUCTURE` - email structure
- `UID` - unique id
- `FLAGS` - flags (read, deleted, etc.)
- `INTERNALDATE` - internal date

See: `imap-fetch-items.md`

---

## Key differences

| Aspect | SEARCH | FETCH |
|--------|--------|-------|
| **Purpose** | Search/filter email | Fetch email data |
| **Returns** | UID list | Email content |
| **Downloads content** | ❌ No | ✅ Yes |
| **Speed** | ⚡ Fast | 🐌 Slow (depends on data size) |
| **Search capability** | ✅ Yes | ❌ No |
| **Batch** | ✅ Returns multiple UIDs | ✅ Batch fetching is possible |

---

## ✅ Best practice: use SEARCH + FETCH together

### Wrong approach ❌

```python
# ❌ Wrong: FETCH cannot search
status, data = imap.fetch(None, 'SUBJECT "test"')  # this is wrong!

# ❌ Wrong: iterating over all emails directly
status, messages = imap.search(None, 'ALL')  # returns 10,000 UIDs
uids = messages[0].split()

for uid in uids:
    status, data = imap.fetch(uid, 'RFC822')  # downloads the full email!
    # parse the date, decide whether it's within the last 10 days...
```

**Problems**:
- 🐌 Downloads 10,000 full emails (possibly 10GB+)
- 🐌 Must parse every email to judge the date
- 💥 **Performance disaster** (may take several minutes)

---

### Right approach ✅

```python
# ✅ Correct: SEARCH first, then FETCH
since_date = "13-May-2026"

# Step 1: SEARCH (server-side filtering)
status, messages = imap.search(None, f'SINCE "{since_date}"')
uids = messages[0].split()
print(f"Found {len(uids)} emails")

# Step 2: FETCH (only the parts you need)
uids_str = ','.join([uid.decode() for uid in uids])

# Metadata only (recommended)
status, data = imap.fetch(uids_str, '(UID FLAGS INTERNALDATE RFC822.SIZE)')

# Or headers only (no body or attachments)
status, data = imap.fetch(uids_str, 'RFC822.HEADER')

# Or structure only (to check for attachments)
status, data = imap.fetch(uids_str, 'BODYSTRUCTURE')
```

**Advantages**:
- ⚡ Downloads only the matching UIDs (a few KB)
- ⚡ Fetches only metadata (a few KB)
- 💚 **Super fast** (a few seconds)

---

## 📊 Performance comparison

| Approach | Data volume | Time | Scenario |
|------|--------|------|------|
| ❌ Directly FETCH RFC822 for all email | 10GB | ~30 min | **Disaster** |
| ❌ FETCH all email then filter | 10GB | ~30 min | **Wasteful** |
| ✅ SEARCH + FETCH metadata | 50KB | ~3 s | **Recommended** |

**Performance gain: 100x!** ⚡

---

## 💡 Practical example

### List email from the last 10 days (metadata only)

```python
import imaplib
import datetime
from email.utils import parsedate_to_datetime

# Connect
imap = imaplib.IMAP4_SSL('imap.example.com', 993)
imap.login('user@example.com', 'password')
imap.select('INBOX')

# Step 1: SEARCH (last 10 days)
since_date = (datetime.date.today() - datetime.timedelta(days=10)).strftime("%d-%b-%Y")
status, messages = imap.search(None, f'SINCE "{since_date}"')
uids = messages[0].split()

print(f"Found {len(uids)} emails")

# Step 2: FETCH (metadata only)
uids_str = ','.join([uid.decode() for uid in uids])
status, data = imap.fetch(uids_str, '(UID FLAGS INTERNALDATE RFC822.SIZE)')

# Parse the results
for response in data:
    if isinstance(response, bytes):
        raw_data = response.decode()
        # Extract fields with regex
        import re
        uid_match = re.search(r'UID\s+(\d+)', raw_data)
        date_match = re.search(r'INTERNALDATE\s+"([^"]+)"', raw_data)
        size_match = re.search(r'RFC822\.SIZE\s+(\d+)', raw_data)

        if uid_match and date_match and size_match:
            uid = uid_match.group(1)
            date_str = date_match.group(1)
            size = int(size_match.group(1))

            print(f"UID: {uid}, Date: {date_str}, Size: {size} bytes")

imap.close()
imap.logout()
```

**Full script**: `scripts/list_recent_emails.py`

---

## 🎯 Summary

### Q: Does imap's fetch have search capability?

**A: ❌ No!**

- The **SEARCH** command searches/filters email
- The **FETCH** command fetches email data
- There is **no** `FETCH ... SUBJECT "xxx"` usage

### Correct usage:

```python
# ❌ Wrong: FETCH cannot search
status, data = imap.fetch(None, 'SUBJECT "test"')  # this is wrong!

# ✅ Correct: SEARCH first, then FETCH
status, messages = imap.search(None, 'SUBJECT "test"')  # search
uid_list = messages[0].split()
status, data = imap.fetch(uid_list, 'RFC822.HEADER')  # fetch
```

---

**Remember: the IMAP FETCH command has no search capability — you must first use SEARCH to filter out the UIDs, then use FETCH to retrieve the data!** ⭐
