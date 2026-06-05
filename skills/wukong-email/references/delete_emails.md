# delete_emails.py - 删除邮件

将邮件移动到"已删除"文件夹（可恢复）。

## 功能

- IMAP 搜索条件过滤邮件
- 移动到"已删除"文件夹（可从垃圾箱恢复）
- 支持预览和确认流程

## 参数

| 参数 | 说明 | 必填 |
|------|------|------|
| `--search CRITERIA` | IMAP 搜索条件 | ✅ |
| `--folder FOLDER` | 源文件夹（默认 INBOX） | - |
| `--deleted-folder FOLDER` | 目标文件夹（默认 已删除/Trash） | - |
| `--limit N` | 最多删除 N 封 | - |
| `--preview N` | 预览前 N 封（默认 10） | - |
| `--dry-run` | 预览模式，不执行删除 | - |
| `--yes` | 跳过确认，直接执行 | - |

## IMAP 搜索条件

| 条件 | 说明 | 示例 |
|------|------|------|
| `SINCE "DD-Mon-YYYY"` | 日期之后 | `SINCE "13-May-2026"` |
| `BEFORE "DD-Mon-YYYY"` | 日期之前 | `BEFORE "01-May-2026"` |
| `FROM "email"` | 发件人 | `FROM "spam@example.com"` |
| `SUBJECT "text"` | 主题包含 | `SUBJECT "广告"` |
| `TO "email"` | 收件人包含 | `TO "user@example.com"` |
| `UNSEEN` | 未读 | `UNSEEN` |
| `SEEN` | 已读 | `SEEN` |
| `FLAGGED` | 已标记 | `FLAGGED` |

可组合：`SINCE "13-May-2026" FROM "notifications"`

## 使用示例

```bash
# 预览（dry-run）
python3 scripts/delete_emails.py --search "SINCE 13-May-2026" --dry-run
python3 scripts/delete_emails.py --search 'FROM "spam@example.com"' --dry-run

# 预览数量限制
python3 scripts/delete_emails.py --search "UNSEEN" --preview 5 --dry-run

# 执行删除（先预览再确认）
python3 scripts/delete_emails.py --search "SINCE 13-May-2026" --yes

# 限数量
python3 scripts/delete_emails.py --search "UNSEEN" --limit 10 --yes

# 特定主题
python3 scripts/delete_emails.py --search 'SUBJECT "广告"' --yes
```

## 强制流程（Agent 必须遵守）

1. **先 `--dry-run` 预览** → 展示匹配的邮件列表
2. **等用户确认** → 用户明确说"删除"/"执行"
3. **加 `--yes` 执行** → 不可逆操作，切勿直接执行

```
❌ 错误：直接执行删除
python3 scripts/delete_emails.py --search "UNSEEN" --limit 10

✅ 正确：先预览 → 等确认 → 执行
# 第1步：预览
python3 scripts/delete_emails.py --search "UNSEEN" --limit 10 --dry-run
# 等用户确认...
# 第2步：执行
python3 scripts/delete_emails.py --search "UNSEEN" --limit 10 --yes
```

## 恢复已删除邮件

邮件移到"已删除"文件夹后，可在邮箱客户端从"已删除"文件夹移动回 INBOX。
