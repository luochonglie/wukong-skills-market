# IMAP 批量 FETCH 响应解析

## 问题

使用 `imap.fetch(uids_str, '(UID RFC822.SIZE RFC822.HEADER BODYSTRUCTURE)')` 批量获取多封邮件时，返回的 `data` 列表是**混合格式**——既有 `bytes` 行，也有 `tuple` 行。

## 响应格式

```python
# 典型的 3 封邮件批量 FETCH 响应：
data = [
    # 邮件1: tuple — part[0] 含元数据，part[1] 含邮件头
    (b'2065 (UID 2471 BODYSTRUCTURE (...) RFC822.SIZE 7264 RFC822.HEADER {2459}',
     b'X-RM-TagInfo: ...\r\nFrom: ...\r\nSubject: ...\r\n\r\n'),
    # 分隔符
    b')',
    # 邮件2: 同上
    (b'2066 (UID 2472 BODYSTRUCTURE (...) RFC822.SIZE 14964 RFC822.HEADER {8726}',
     b'...邮件头...'),
    b')',
    # 邮件3
    (b'2067 ...',
     b'...邮件头...'),
    b')',
]
```

**关键发现**：
- 某些 IMAP 服务器会把所有数据都放在 **tuple** 里
- `part[0]`（tuple[0]）包含：序列号、UID、BODYSTRUCTURE、RFC822.SIZE、RFC822.HEADER 的 literal 大小 `{N}`
- `part[1]`（tuple[1]）包含：完整邮件头（N 字节）
- `b')'` 是每封邮件的分隔符

**其他服务器可能不同**：有些服务器 UID/SIZE 在独立 bytes 行，HEADER 在 tuple 里。必须兼容两种。

## 正确解析方法

```python
uid_size_map = {}   # seq_num -> {uid, size}
header_bs_map = {}  # seq_num -> {header, bodystructure}
current_seq = None

i = 0
while i < len(data):
    item = data[i]
    if isinstance(item, bytes):
        # 独立 bytes 行：可能含 UID/SIZE/BODYSTRUCTURE
        seq_match = re.search(rb'^(\d+)\s+\(', item)
        if seq_match:
            current_seq = seq_match.group(1).decode()
            uid_size_map.setdefault(current_seq, {'uid': '', 'size': 0})
            # 提取 UID
            uid_match = re.search(rb'UID\s+(\d+)', item)
            if uid_match:
                uid_size_map[current_seq]['uid'] = uid_match.group(1).decode()
            # 提取 SIZE
            size_match = re.search(rb'RFC822\.SIZE\s+(\d+)', item)
            if size_match:
                uid_size_map[current_seq]['size'] = int(size_match.group(1))
            # 提取 BODYSTRUCTURE
            if b'BODYSTRUCTURE' in item:
                header_bs_map.setdefault(current_seq, {'header': None, 'bodystructure': None})
                header_bs_map[current_seq]['bodystructure'] = item
    elif isinstance(item, tuple):
        # tuple: part[0] 含序列号+UID+SIZE+BODYSTRUCTURE, part[1] 含邮件头
        for part in item:
            if not isinstance(part, bytes):
                continue
            seq_match = re.search(rb'^(\d+)\s+\(', part)
            if seq_match:
                # 元数据行
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
                # 邮件头（tuple 的最后一个 part）
                header_bs_map.setdefault(current_seq, {'header': None, 'bodystructure': None})
                header_bs_map[current_seq]['header'] = part
    i += 1
```

## 错误做法

```python
# ❌ 只处理 tuple，忽略 bytes 行
while i < len(data):
    if isinstance(data[i], tuple):
        # 只在这里解析... 会漏掉独立 bytes 行的 UID/SIZE

# ❌ 假设 tuple 的 part[1] 一定是邮件头
# 有些服务器的 tuple 里 bodystructure 和 header 的顺序可能不同
# 应该用 re.search(rb'^(\d+)\s+\(', part) 判断是元数据行还是邮件头

# ❌ 用 header 长度估算邮件大小
email_data['size'] = len(header_data)  # 错误！应用 RFC822.SIZE
```

## 验证

```python
# 单独获取 RFC822.SIZE 验证
status, data = imap.fetch(uids_str, '(RFC822.SIZE)')
# bytes 行: b'2065 ( RFC822.SIZE 7264)'
```
