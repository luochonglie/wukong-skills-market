# mark_read.py - 标记已读

标记邮件为已读/未读状态。

## 功能

- 搜索符合条件的邮件
- 批量标记为已读/未读
- 支持预览模式

## 参数

| 参数 | 说明 | 必填 |
|------|------|------|
| `--before DATE` | 日期之前（DD-Mon-YYYY） | - |
| `--days N` | 最近 N 天 | - |
| `--from TEXT` | 发件人包含 | - |
| `--subject TEXT` | 主题包含 | - |
| `--unread` | 标记为未读（默认已读） | - |
| `--uids UID1,UID2` | 指定 UID（逗号分隔） | - |
| `--dry-run` | 预览模式，不执行 | - |

## 使用示例

```bash
# 预览（推荐先看有多少封）
python3 scripts/mark_read.py --before 01-May-2026 --unread --dry-run
python3 scripts/mark_read.py --from "notifications" --unread --dry-run

# 执行标记
python3 scripts/mark_read.py --before 01-May-2026 --unread   # 5月1日前未读
python3 scripts/mark_read.py --from "notifications" --unread  # 通知类邮件
python3 scripts/mark_read.py --days 7 --unread                # 最近7天未读
python3 scripts/mark_read.py --uids 2296,2297,2298            # 指定 UID
```

## 工作流程

```
# 第1步：预览（查看影响多少封）
python3 scripts/mark_read.py --days 30 --unread --dry-run

# 第2步：确认后执行
python3 scripts/mark_read.py --days 30 --unread
```
