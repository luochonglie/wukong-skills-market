# Parsing batch IMAP FETCH responses

## The problem

When batch-fetching multiple emails with `imap.fetch(uids_str, '(UID RFC822.SIZE RFC822.HEADER BODYSTRUCTURE)')`, the returned `data` list is a **mixed format** — some rows are `bytes`, some are `tuple`.

## Response format

```python
# A typical batch FETCH response for 3 emails:
data = [
    # Email 1: tuple — part[0] holds metadata, part[1] holds the headers
    (b'2065 (UID 2471 BODYSTRUCTURE (...) RFC822.SIZE 7264 RFC822.HEADER {2459}',
     b'X-RM-TagInfo: ...\r\nFrom: ...\r\nSubject: ...\r\n\r\n'),
    # Separator
    b')',
    # Email 2: same shape
    (b'2066 (UID 2472 BODYSTRUCTURE (...) RFC822.SIZE 14964 RFC822.HEADER {8726}',
     b'...headers...'),
    b')',
    # Email 3
    (b'2067 ...',
     b'...headers...'),
    b')',
]
```

**Key findings**:
- Some IMAP servers put all the data inside the **tuple**
- `part[0]` (tuple[0]) contains: sequence number, UID, BODYSTRUCTURE, RFC822.SIZE, and the literal size `{N}` of RFC822.HEADER
- `part[1]` (tuple[1]) contains: the full headers (N bytes)
- `b')'` is the per-email separator

**Other servers differ**: some put UID/SIZE on a standalone `bytes` row and the HEADER inside the tuple. You must handle both.

## Correct parsing

```python
uid_size_map = {}   # seq_num -> {uid, size}
header_bs_map = {}  # seq_num -> {header, bodystructure}
current_seq = None

i = 0
while i < len(data):
    item = data[i]
    if isinstance(item, bytes):
        # Standalone bytes row: may contain UID/SIZE/BODYSTRUCTURE
        seq_match = re.search(rb'^(\d+)\s+\(', item)
        if seq_match:
            current_seq = seq_match.group(1).decode()
            uid_size_map.setdefault(current_seq, {'uid': '', 'size': 0})
            # Extract UID
            uid_match = re.search(rb'UID\s+(\d+)', item)
            if uid_match:
                uid_size_map[current_seq]['uid'] = uid_match.group(1).decode()
            # Extract SIZE
            size_match = re.search(rb'RFC822\.SIZE\s+(\d+)', item)
            if size_match:
                uid_size_map[current_seq]['size'] = int(size_match.group(1))
            # Extract BODYSTRUCTURE
            if b'BODYSTRUCTURE' in item:
                header_bs_map.setdefault(current_seq, {'header': None, 'bodystructure': None})
                header_bs_map[current_seq]['bodystructure'] = item
    elif isinstance(item, tuple):
        # tuple: part[0] holds seq+UID+SIZE+BODYSTRUCTURE, part[1] holds the headers
        for part in item:
            if not isinstance(part, bytes):
                continue
            seq_match = re.search(rb'^(\d+)\s+\(', part)
            if seq_match:
                # Metadata row
                current_seq = seq_match.group(1).decode()
                uid_size_map.setdefault(current_seq, {'uid': '', 'size': 0})
                uid_match = re.search(rb'UID\s+(\d+)', part)
                if uid_match:
                    uid_size_map[current_seq]['uid'] = uid_match.group(1).decode()
                size_match = re.search(rb'RFC822\.SIZE\s+(\d+)', part)
                if size_match:
                    uid_size_map[current_seq]['size'] = int(size_match.group(1))
                if b'BODYSTRUCTURE' in part:
                    header_bs_map.setdefault(current_seq, {'header': None, 'bodystructure': None})
                    header_bs_map[current_seq]['bodystructure'] = part
            elif current_seq:
                # Headers (the last part of the tuple)
                header_bs_map.setdefault(current_seq, {'header': None, 'bodystructure': None})
                header_bs_map[current_seq]['header'] = part
    i += 1
```

## Wrong approaches

```python
# ❌ Only handling tuple, ignoring bytes rows
while i < len(data):
    if isinstance(data[i], tuple):
        # Only parse here... you'll miss the UID/SIZE on standalone bytes rows

# ❌ Assuming tuple's part[1] is always the headers
# On some servers the bodystructure and header order inside the tuple may differ
# Use re.search(rb'^(\d+)\s+\(', part) to decide whether it's a metadata row or a header

# ❌ Estimating email size from header length
email_data['size'] = len(header_data)  # Wrong! Use RFC822.SIZE
```

## Verification

```python
# Fetch RFC822.SIZE separately to verify
status, data = imap.fetch(uids_str, '(RFC822.SIZE)')
# bytes row: b'2065 ( RFC822.SIZE 7264)'
```
