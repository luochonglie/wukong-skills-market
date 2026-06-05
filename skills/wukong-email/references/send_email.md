# send_email.py - 发送邮件

发送纯文本、HTML 或 Markdown 邮件，支持附件，发送后自动保存到已发送文件夹。

## 功能

- **纯文本**：直接发送
- **HTML**：直接发送 HTML 格式
- **Markdown**：自动检测并转换为 HTML（带内联样式，邮件客户端兼容）
- **附件**：支持多个附件
- **自动保存**：发送后自动保存到已发送文件夹

## 参数

| 参数 | 说明 | 必填 |
|------|------|------|
| `--to` | 收件人（多个用逗号分隔） | ✅ |
| `--subject` | 邮件主题 | ✅ |
| `--body` | 邮件正文 | ✅ |
| `--html` | 强制 HTML 格式（Markdown 自动检测时也可强制） | - |
| `--attach FILE` | 附件路径（可多次使用） | - |
| `--cc` | 抄送 | - |
| `--bcc` | 密送 | - |

## Markdown 自动转换

脚本自动检测 Markdown 语法（标题、列表、粗体、代码块、表格等），并转换为带内联样式的 HTML。

**依赖**：`python3-markdown`（`sudo apt install python3-markdown`）

未安装时降级为纯文本发送，并显示警告。

## 使用示例

```bash
# 纯文本
python3 scripts/send_email.py --to user@example.com --subject "Hello" --body "World"

# 自动检测 Markdown（推荐）
python3 scripts/send_email.py --to user@example.com --subject "报告" --body "
# 今日总结

## 完成事项
- [x] 任务 A
- [x] 任务 B

## 待办
1. 任务 C
2. 任务 D
"

# 强制 HTML
python3 scripts/send_email.py --to user@example.com --subject "HTML邮件" --html --body "<h1>标题</h1><p>内容</p>"

# 带附件
python3 scripts/send_email.py --to user@example.com --subject "请查收" --body "附件已发送" --attach report.pdf

# 多附件
python3 scripts/send_email.py --to user@example.com --subject "多附件" --body "请查收" --attach a.pdf --attach b.pdf

# 多收件人 + 抄送
python3 scripts/send_email.py --to a@example.com,b@example.com --cc c@example.com --subject "群发" --body "内容"
```

## 已发送文件夹

发送后自动保存到已发送文件夹。智能检测逻辑：

1. **精确匹配**：配置 `EMAIL_SENT_FOLDER=已发送` → 匹配 UTF-7 编码 `&XfJT0ZAB-`
2. **常见名称**：Sent / Sent Items / Sent Mail
3. **标记检测**：通过 `\Sent` 标记识别

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| Markdown 未转 HTML | 未加 `--html` 参数 | 加 `--html` 或让脚本自动检测 |
| 发送失败 | SSL 验证失败 | 检查 `EMAIL_SMTP_SSL_VERIFY=false` |