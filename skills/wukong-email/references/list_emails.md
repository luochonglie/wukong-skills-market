# list_emails.py - 搜索邮件

根据条件搜索邮件，返回 UID 列表（默认 JSON 格式）。

## 功能

- **SEARCH**：服务器端过滤，返回符合条件的所有 UID
- **FETCH**：只获取元数据（UID、日期、发件人、主题、大小、附件数量）

## 工作流

```
list_emails.py (搜索) → 获取 UID 列表 → fetch_emails.py (获取完整内容)
```

## 参数

### 搜索条件

| 参数 | 说明 | 示例 |
|------|------|------|
| `--days N` | 最近 N 天 | `--days 10` |
| `--unread` | 未读邮件 | `--unread` |
| `--seen` | 已读邮件 | `--seen` |
| `--from TEXT` | 发件人包含 | `--from "notifications"` |
| `--to TEXT` | 收件人包含 | `--to "user@example.com"` |
| `--subject TEXT` | 主题包含 | `--subject "通知"` |
| `--larger N` | 大于 N 字节 | `--larger 1048576` |
| `--smaller N` | 小于 N 字节 | `--smaller 10000` |
| `--flagged` | 已标记 | `--flagged` |
| `--unflagged` | 未标记 | `--unflagged` |

### 输出控制

| 参数 | 说明 |
|------|------|
| （默认） | JSON 数组，供 Agent 解析 |
| `--table` | 人类可读表格 |
| `--output-uids` | 只输出 UID（每行一个） |
| `--only-with-attachments` | 只显示有附件的 |
| `--limit N` | 最多 N 封 |

## 输出格式

### JSON（默认）

```json
[
  {"uid": "2471", "date": "2026-05-22 08:12:34", "from": "发件人 <sender@...>", "subject": "测试邮件", "size": 7264, "attachments": 1},
  {"uid": "2470", "date": "2026-05-21 15:30:00", "from": "Notifications <no-reply@example.com>", "subject": "任务提醒", "size": 4521, "attachments": 0}
]
```

### 表格（--table）

```
UID        时间                  发件人                         主题                                   大小       附件
-------------------------------------------------------------------------------------------------------------------
2471       2026-05-22 08:12:34   发件人 <sender@...>              测试邮件                               7.1 KB    1
2470       2026-05-21 15:30:00   Notifications <no-reply@example.com> 任务提醒                               4.4 KB    -
-------------------------------------------------------------------------------------------------------------------
总计: 2 封邮件
```

## 使用示例

```bash
# 最近10天所有邮件（JSON）
python3 scripts/list_emails.py --days 10

# 最近30天未读邮件（表格）
python3 scripts/list_emails.py --days 30 --unread --table

# 特定发件人
python3 scripts/list_emails.py --days 7 --from "notifications"

# 只看有附件的
python3 scripts/list_emails.py --days 30 --only-with-attachments --table

# 只输出 UID（管道操作）
python3 scripts/list_emails.py --days 10 --only-with-attachments --output-uids

# 限制数量
python3 scripts/list_emails.py --days 30 --limit 50 --table
```

## 管道操作

获取有附件的邮件并下载：

```bash
# 获取 UID 列表
UIDS=$(python3 scripts/list_emails.py --days 10 --only-with-attachments --output-uids | tr '\n' ',' | sed 's/,$//')

# 下载附件
python3 scripts/fetch_emails.py --uids "$UIDS" --download-attachments
```

## Agent 使用注意

**⚠️ JSON 输出是给 Agent 解析的！**

- 用户看不到终端原始输出
- Agent 必须把结果格式化为可读表格/列表展示给用户
- 不要只丢原始 JSON 给用户看

## 性能说明

- `list_emails.py`：SEARCH + FETCH 元数据（~50KB）
- 直接下载全部邮件：~10GB
- **100 倍性能提升**

详见：`references/imap-search-vs-fetch.md`
