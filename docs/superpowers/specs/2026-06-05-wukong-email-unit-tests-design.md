# Wukong-Email 单元测试设计

## 概述

为 wukong-email 技能的 10 个脚本编写 pytest 风格的单元测试，覆盖正常、异常和边界值。

同时进行一项重构：
1. 将 6 个脚本中重复的 `create_ssl_context` 抽取到新建的 `utils.py`
2. 4 个脚本中重复的 `decode_header_value` 改为使用 `decode_helper.decode_header_value_enhanced`（已有增强版，功能完全覆盖简单版）

## 前置重构

### 1. 新建 `skills/wukong-email/scripts/utils.py`

包含一个函数：

**`create_ssl_context(ssl_config: dict = None) -> ssl.SSLContext`**
- 来源：6 个脚本中重复定义，以 send_email.py 的增强版为统一实现（支持 TLS 版本配置）
- 其他 5 个脚本删除本地定义，改为 `from utils import create_ssl_context`

### 2. 邮件头解码统一到 decode_helper.py

4 个脚本中的 `decode_header_value`（简单版）改为使用 `decode_helper.decode_header_value_enhanced`（增强版，功能完全覆盖）。

### 受影响脚本

| 脚本 | 删除 create_ssl_context | 改用 decode_header_value_enhanced |
|------|------------------------|----------------------------------|
| fetch_emails.py | Y（改从 utils import） | Y（改从 decode_helper import） |
| delete_emails.py | Y | Y |
| list_emails.py | Y | Y |
| search_chinese.py | Y | Y |
| mark_read.py | Y | N（未使用该函数） |
| send_email.py | Y | N（未使用该函数） |

`decode_helper.py` 和 `imap_utf7.py` 保持独立。

## 目录结构

```
tests/skills/wukong-email/
├── conftest.py              # 共享 fixture
├── test_utils.py            # 公共工具测试
├── test_decode_helper.py    # MIME 解码测试
├── test_imap_utf7.py        # IMAP UTF-7 测试
├── test_config_loader.py    # 配置加载测试
├── test_init_config.py      # 初始化配置测试
├── test_list_emails.py      # 列出邮件测试
├── test_fetch_emails.py     # 收取邮件测试
├── test_delete_emails.py    # 删除邮件测试
├── test_mark_read.py        # 标记已读测试（重写现有）
├── test_search_chinese.py   # 中文搜索测试
└── test_send_email.py       # 发送邮件测试
```

## 测试风格

- pytest 风格：fixture 注入 mock、`@pytest.mark.parametrize` 参数化
- `@patch` 装饰器 mock 外部依赖
- 每个函数的正常/异常/边界用 parametrize 合并到同一测试
- 现有 `test_mark_read.py` 重写为 pytest 风格

## 共享 Fixture（conftest.py）

```python
@pytest.fixture
def sample_config() -> dict
    # 标准测试配置

@pytest.fixture
def mock_imap() -> MagicMock
    # IMAP 连接 mock（login/select/close/logout 预设）

@pytest.fixture
def mock_smtp() -> MagicMock
    # SMTP 连接 mock

@pytest.fixture
def tmp_env_file(tmp_path) -> Path
    # 临时 .env 文件

@pytest.fixture
def tmp_attachments_dir(tmp_path) -> str
    # 临时附件目录
```

## 各脚本测试用例

### test_utils.py — 公共工具

| 函数 | 正常 | 异常 | 边界 |
|------|------|------|------|
| create_ssl_context | 默认配置、verify=True、自定义 cipher | None 配置 | TLS 版本选择 |

### test_decode_helper.py — MIME 解码（纯函数，无 mock）

| 函数 | 正常 | 异常 | 边界 |
|------|------|------|------|
| decode_rfc2231 | UTF-8 URL 编码、GBK 编码 | None、空串、非字符串 | 无编码标记 |
| decode_rfc2047 | B 编码、Q 编码、多段 | 无效 Base64、空输入 | 嵌套 =?..?= |
| decode_mime_filename | RFC 2047/2231 文件名、URL 编码、bytes | None、空串 | 混合编码 |
| decode_header_value_enhanced | 多段编码、多 @ 清理、BOM 清理 | None、bytes | 超长字符串 |

### test_imap_utf7.py — IMAP UTF-7（纯函数，无 mock）

| 函数 | 正常 | 异常 | 边界 |
|------|------|------|------|
| encode_imap_utf7 | 中文（已发送、草稿箱、已删除）、混合 ASCII+中文 | 空串 | 纯 ASCII、& 转义、emoji |
| decode_imap_utf7 | IMAP UTF-7 编码串、&- 还原 | 空串 | 无效 base64 |
| get_imap_folder_name | 常见友好名映射表 | 未知名称走 encode | 空串 |

### test_config_loader.py — 配置加载（Mock 文件系统）

| 函数 | 正常 | 异常 | 边界 |
|------|------|------|------|
| load_dotenv | 标准 KEY=VALUE、引号值、注释跳过 | 缺失文件、空文件 | 键含下划线/数字 |
| str_to_bool | true/yes/1/on -> True | false/no/0/off -> False | 大小写混合、空串 |
| is_unset_or_placeholder | 占位值检测 | 正常值不误判 | 大小写变体 |
| load_config | 环境变量 > .env > 默认值、参数覆盖、缓存 | 缺必填字段抛 SystemExit | force_reload |
| mask_password | 长/短密码脱敏 | 空串 | 刚好 5 字符 |

### test_init_config.py — 初始化配置（Mock 文件系统 + subprocess）

| 函数 | 正常 | 异常 | 边界 |
|------|------|------|------|
| check_and_install_dependencies | 已安装、未安装自动安装 | 安装失败 | 权限错误 |
| init_config | 首次创建、已存在跳过 | 目录不可写 | .env 已存在 |

### test_list_emails.py — 列出邮件（Mock IMAP）

| 函数 | 正常 | 异常 | 边界 |
|------|------|------|------|
| build_search_criteria | days/unread/from/subject 组合 | 无参数返回空 | 全部条件同时 |
| count_attachments_from_bodystructure | 有附件、无附件 | None 输入 | 嵌套 multipart |
| format_size | B/KB/MB/GB 转换 | 0 字节 | 大数 |
| list_emails | 正常获取、limit 截断 | 连接失败、search 失败 | 空结果、only_with_attachments |

### test_fetch_emails.py — 收取邮件（Mock IMAP + 文件系统）

| 函数 | 正常 | 异常 | 边界 |
|------|------|------|------|
| get_email_body | multipart text/plain、单段、GBK | 空 msg | 纯 HTML 无 text |
| sanitize_filename | 替换非法字符 | 空串 | 全非法字符 |
| clean_email_address | 多 @ 清理、尖括号内多 @ | 空串 | 无 @ 的字符串 |
| download_attachments_from_email | 正常下载、跳过已存在 | 写入失败 | bytes UID、无附件 |
| fetch_emails | 正常收取、附件下载 | 连接失败 | only_with_attachments 过滤 |

### test_delete_emails.py — 删除邮件（Mock IMAP）

| 函数 | 正常 | 异常 | 边界 |
|------|------|------|------|
| find_deleted_folder | 精确匹配、常见名匹配、模糊匹配 | 无匹配返回 Trash | 中文文件夹名 |
| search_emails | 正常搜索、limit 截断 | search 失败 | 空结果 |
| preview_emails | 正常预览 | fetch 失败跳过 | max_preview 超过实际数量 |
| move_to_deleted_folder | 正常移动、dry-run | copy 失败跳过、store 失败跳过 | 空列表 |

### test_mark_read.py — 标记已读（重写，Mock IMAP）

| 函数 | 正常 | 异常 | 边界 |
|------|------|------|------|
| mark_read | UID 模式、search 模式、分批标记 | STORE 失败计 fail | 空 UID、空搜索结果 |
| build_search_criteria | 各种条件组合 | 无条件 | 全组合 |

### test_search_chinese.py — 中文搜索（Mock IMAP）

| 函数 | 正常 | 异常 | 边界 |
|------|------|------|------|
| search_with_charset | UTF-8 成功、GBK 降级 | 全部失败 | 空结果 |
| search_emails_by_content | 多方法搜索、去重 | 连接失败 | 空关键词 |

### test_send_email.py — 发送邮件（Mock SMTP + IMAP）

| 函数 | 正常 | 异常 | 边界 |
|------|------|------|------|
| is_markdown | 检测 Markdown 特征 | 纯文本、HTML | 空串 |
| auto_convert_content | Markdown->HTML、HTML 直传、纯文本 | 空 body | 长内容 |
| send_email | 正常发送、带附件、带 CC/BCC | SMTP 失败 | 超大附件 |
| save_to_sent_folder | 正常保存 | IMAP 失败 | 未找到 Sent 文件夹 |

## 预计测试用例数量

约 70-80 个测试用例，分布在 11 个测试文件中。

## Mock 策略

| 依赖 | Mock 方式 | 适用脚本 |
|------|----------|----------|
| IMAP 连接 | `@patch('module.imaplib.IMAP4_SSL')` + fixture | list/fetch/delete/mark_read/search |
| SMTP 连接 | `@patch('module.smtplib.SMTP_SSL')` + fixture | send_email |
| 配置加载 | `@patch('module.load_config')` | 所有 IMAP/SMTP 脚本 |
| 文件系统 | `tmp_path` fixture + `monkeypatch` | config_loader/init_config/fetch |
| subprocess | `@patch('module.subprocess.run')` | init_config |
| 环境变量 | `monkeypatch.setenv` / `monkeypatch.delenv` | config_loader |
