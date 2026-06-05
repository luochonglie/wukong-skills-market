# fetch_emails.py - 获取邮件

根据 UID 获取邮件内容和下载附件。

## 功能

- 根据 UID 列表获取邮件内容
- 下载邮件附件（自动区分真实附件和内嵌图片）
- 支持中文文件名解码（RFC 2047 / RFC 2231 / URL 编码）

## 参数

| 参数 | 说明 | 必填 |
|------|------|------|
| `--uids UID1,UID2,...` | 邮件 UID 列表（逗号分隔） | ✅ |
| `--download-attachments` | 自动下载附件 | - |
| `--force-download` | 强制重新下载（覆盖已存在） | - |
| `--list` | 只列出邮件，不显示正文 | - |
| `--full` | 显示完整正文（默认只显示前 500 字符） | - |
| `--folder FOLDER` | 邮箱文件夹（默认 INBOX） | - |
| `--limit N` | 获取数量（默认 10） | - |

## 使用示例

```bash
# 列出邮件（不显示正文）
python3 scripts/fetch_emails.py --uids 2060,2061,2062 --list

# 获取完整邮件
python3 scripts/fetch_emails.py --uids 2060,2061 --full

# 下载附件
python3 scripts/fetch_emails.py --uids 2060,2061 --download-attachments

# 强制重新下载
python3 scripts/fetch_emails.py --uids 2060 --download-attachments --force-download
```

## 输出说明

### --list（仅列出）

```
=== 邮件 1/2 ===
UID: 2061
发件人: 发件人 <user@example.com>
主题: 测试邮件
时间: 2026-05-22 08:12:34
大小: 7264 bytes
附件: 1 个
  - 测试文档.pdf

=== 邮件 2/2 ===
...
```

### --download-attachments

```
正在获取邮件 UID: 2060, 2061
[2060] 主题: 测试邮件
  找到附件: 测试文档.pdf (23456 bytes)
  保存到: ~/.wukong-email/attachments/2060/测试文档.pdf
  保存 email_info.txt
[2061] 主题: 报表
  找到附件: 月度报表.xlsx (56789 bytes)
  保存到: ~/.wukong-email/attachments/2061/月度报表.xlsx
```

## 附件保存位置

```
EMAIL_ATTACHMENTS_DIR/
└── <UID>/
    ├── 文件名1.ext
    ├── 文件名2.ext
    └── email_info.txt  # 邮件元数据
```

## 重要提示

1. **必须先获取 UID**：先运行 `list_emails.py` 获取 UID，再传给 `fetch_emails.py`
2. **IMAP 没有搜索功能**：FETCH 只能获取数据，不能搜索。必须 SEARCH → FETCH 两步
3. **批量获取更快**：用逗号分隔 UID 一次获取，不要循环调用

详见：`references/imap-search-vs-fetch.md`
