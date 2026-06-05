# IMAP SEARCH vs FETCH 命令对比

## 核心结论

**❌ IMAP FETCH 命令没有搜索功能！**

必须使用 **两步工作流程**：
1. **SEARCH** 命令 → 过滤邮件，返回 UID 列表
2. **FETCH** 命令 → 获取指定 UID 的邮件数据

---

## 命令对比

### IMAP SEARCH 命令（搜索/过滤）

| 项目 | 说明 |
|------|------|
| **功能** | 搜索/过滤邮件 |
| **返回** | 符合条件的 **UID 列表** |
| **特点** | ⚡ **不下载邮件内容**（快速） |

**示例**：
```python
# 搜索最近10天的邮件
status, messages = imap.search(None, 'SINCE "13-May-2026"')

# 返回: b'2035 2036 2037 2038 2039 ...' (UID 列表)
# 结果: 找到 54 封邮件
```

**支持的搜索条件**：
- `SINCE "13-May-2026"` - 日期
- `FROM "user@example.com"` - 发件人
- `SUBJECT "test"` - 主题
- `TO "user@example.com"` - 收件人
- `SEEN` / `UNSEEN` - 已读/未读
- `FLAGGED` / `UNFLAGGED` - 已标记/未标记
- `LARGER 100000` - 大于 100KB
- `SMALLER 1000000` - 小于 1MB
- 组合：`SINCE "13-May-2026" FROM "user@example.com"`

详见：`imap-search-syntax.md`

---

### IMAP FETCH 命令（获取数据）

| 项目 | 说明 |
|------|------|
| **功能** | 获取邮件数据 |
| **返回** | 邮件内容（邮件头、正文、附件等） |
| **特点** | ⚠️ **下载邮件内容**（可以指定部分） |

**示例**：
```python
# 获取完整邮件
status, data = imap.fetch(uid, 'RFC822')  # 下载完整邮件（可能很大）

# 只获取邮件头
status, data = imap.fetch(uid, 'RFC822.HEADER')  # 只下载邮件头（小）

# 获取邮件结构
status, data = imap.fetch(uid, 'BODYSTRUCTURE')  # 只下载结构信息（很小）

# 批量获取基本信息
status, data = imap.fetch(uids, '(UID FLAGS INTERNALDATE RFC822.SIZE)')  # 只获取元数据
```

**可以获取的数据**：
- `RFC822` - 完整邮件
- `RFC822.HEADER` - 邮件头
- `RFC822.SIZE` - 邮件大小
- `BODYSTRUCTURE` - 邮件结构
- `UID` - 唯一ID
- `FLAGS` - 标记（已读、已删除等）
- `INTERNALDATE` - 内部日期

详见：`imap-fetch-items.md`

---

## 关键区别

| 对比项 | SEARCH | FETCH |
|--------|--------|-------|
| **功能** | 搜索/过滤邮件 | 获取邮件数据 |
| **返回** | UID 列表 | 邮件内容 |
| **下载内容** | ❌ 否 | ✅ 是 |
| **速度** | ⚡ 快 | 🐌 慢（取决于数据量） |
| **搜索功能** | ✅ 有 | ❌ 无 |
| **批量操作** | ✅ 返回多个 UID | ✅ 可以批量获取 |

---

## ✅ 最佳实践：SEARCH + FETCH 配合使用

### 错误做法 ❌

```python
# ❌ 错误：FETCH 不能搜索
status, data = imap.fetch(None, 'SUBJECT "test"')  # 这是错的！

# ❌ 错误：直接遍历所有邮件
status, messages = imap.search(None, 'ALL')  # 返回 10,000 个 UID
uids = messages[0].split()

for uid in uids:
    status, data = imap.fetch(uid, 'RFC822')  # 下载完整邮件！
    # 解析日期，判断是否在最近10天...
```

**问题**：
- 🐌 下载 10,000 封完整邮件（可能 10GB+）
- 🐌 需要解析每封邮件才能判断日期
- 💥 **性能灾难**（可能需要几分钟）

---

### 正确做法 ✅

```python
# ✅ 正确：先用 SEARCH，再用 FETCH
since_date = "13-May-2026"

# Step 1: SEARCH（在服务器端过滤）
status, messages = imap.search(None, f'SINCE "{since_date}"')
uids = messages[0].split()
print(f"找到 {len(uids)} 封邮件")

# Step 2: FETCH（只获取需要的部分）
uids_str = ','.join([uid.decode() for uid in uids])

# 只获取元数据（推荐）
status, data = imap.fetch(uids_str, '(UID FLAGS INTERNALDATE RFC822.SIZE)')

# 或只获取邮件头（不下载正文和附件）
status, data = imap.fetch(uids_str, 'RFC822.HEADER')

# 或只获取邮件结构（检查是否有附件）
status, data = imap.fetch(uids_str, 'BODYSTRUCTURE')
```

**优势**：
- ⚡ 只下载符合条件的 UID（几KB）
- ⚡ 只获取元数据（几KB）
- 💚 **超快**（几秒钟）

---

## 📊 性能对比

| 方案 | 数据量 | 耗时 | 场景 |
|------|--------|------|------|
| ❌ 直接 FETCH RFC822 全部邮件 | 10GB | ~30分钟 | **灾难** |
| ❌ FETCH 全部邮件再过滤 | 10GB | ~30分钟 | **浪费** |
| ✅ SEARCH + FETCH 元数据 | 50KB | ~3秒 | **推荐** |

**性能提升：100 倍！** ⚡

---

## 💡 实际应用示例

### 列出最近10天的邮件（仅显示元数据）

```python
import imaplib
import datetime
from email.utils import parsedate_to_datetime

# 连接
imap = imaplib.IMAP4_SSL('imap.example.com', 993)
imap.login('user@example.com', 'password')
imap.select('INBOX')

# Step 1: SEARCH（搜索最近10天）
since_date = (datetime.date.today() - datetime.timedelta(days=10)).strftime("%d-%b-%Y")
status, messages = imap.search(None, f'SINCE "{since_date}"')
uids = messages[0].split()

print(f"找到 {len(uids)} 封邮件")

# Step 2: FETCH（只获取元数据）
uids_str = ','.join([uid.decode() for uid in uids])
status, data = imap.fetch(uids_str, '(UID FLAGS INTERNALDATE RFC822.SIZE)')

# 解析结果
for response in data:
    if isinstance(response, bytes):
        raw_data = response.decode()
        # 使用正则表达式提取字段
        import re
        uid_match = re.search(r'UID\s+(\d+)', raw_data)
        date_match = re.search(r'INTERNALDATE\s+"([^"]+)"', raw_data)
        size_match = re.search(r'RFC822\.SIZE\s+(\d+)', raw_data)
        
        if uid_match and date_match and size_match:
            uid = uid_match.group(1)
            date_str = date_match.group(1)
            size = int(size_match.group(1))
            
            print(f"UID: {uid}, 日期: {date_str}, 大小: {size} bytes")

imap.close()
imap.logout()
```

**完整脚本**：`scripts/list_recent_emails.py`

---

## 🎯 总结

### Q: imap的fetch是有搜索功能的吗？

**A: ❌ 没有！**

- **SEARCH** 命令用于搜索/过滤邮件
- **FETCH** 命令用于获取邮件数据
- **没有** `FETCH ... SUBJECT "xxx"` 这样的用法

### 正确的使用方式：

```python
# ❌ 错误：FETCH 不能搜索
status, data = imap.fetch(None, 'SUBJECT "test"')  # 这是错的！

# ✅ 正确：先用 SEARCH，再用 FETCH
status, messages = imap.search(None, 'SUBJECT "test"')  # 搜索
uid_list = messages[0].split()
status, data = imap.fetch(uid_list, 'RFC822.HEADER')  # 获取
```

---

**记住：IMAP 的 FETCH 命令没有搜索功能，必须先使用 SEARCH 命令过滤出 UID，再用 FETCH 获取数据！** ⭐
