#!/usr/bin/env python3
"""
Wukong Email - 发送邮件脚本
============================
支持HTML/Markdown/纯文本邮件和附件
自动检测Markdown格式并转换为HTML
发送后自动保存到已发送文件夹

配置管理（遵循 12-Factor App 原则）：
1. 优先从 ~/.wukong-email/.env 文件加载配置（推荐方式）
2. 支持命令行参数覆盖
3. 自动检测邮箱域名并应用预设配置

使用方法：
    # 1. 复制 env.example 为 ~/.wukong-email/.env 并配置邮箱信息
    # 2. 直接运行（自动从配置加载）
    python send_email.py --to user@example.com --subject "测试" --body "你好"
    
    # 3. 或使用命令行参数（会覆盖配置文件）
    python send_email.py --to user@example.com --subject "测试" --body "你好" \\
        --server smtp.example.com --user me@example.com --password xxx
"""

import smtplib
import ssl
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from imaplib import IMAP4_SSL
import os
import argparse
import sys
from datetime import datetime
from pathlib import Path

# 导入配置加载器（同级目录）
try:
    from config_loader import load_config, get_config, print_config
except ImportError:
    print("[错误] 无法导入 config_loader，请确保 config_loader.py 在同一目录")
    sys.exit(1)

# 导入 IMAP UTF-7 编码工具
try:
    from imap_utf7 import get_imap_folder_name, COMMON_FOLDER_NAMES
except ImportError:
    # 如果导入失败，使用简单的映射
    COMMON_FOLDER_NAMES = {
        '已发送': '&XfJT0ZAB-',
        '草稿箱': '&g0l6P3ux-',
        '已删除': '&XfJSIJZk-',
        '垃圾邮件': '&V4NXPpCuTvY-',
        'Sent': 'Sent',
        'Drafts': 'Drafts',
    }

    def get_imap_folder_name(friendly_name: str) -> str:
        """简单的友好名称映射"""
        return COMMON_FOLDER_NAMES.get(friendly_name, friendly_name)


def create_ssl_context(ssl_config: dict) -> ssl.SSLContext:
    """
    根据配置创建 SSL 上下文
    
    Args:
        ssl_config: SSL 配置字典（从 ~/.wukong-email/.env 加载）
    
    Returns:
        SSL 上下文对象
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    
    # 根据配置设置 SSL 选项
    context.check_hostname = ssl_config.get('check_hostname', True)
    context.verify_mode = ssl.CERT_NONE if not ssl_config.get('verify', True) else ssl.CERT_REQUIRED
    
    # 设置最低 TLS 版本
    min_version = ssl_config.get('minimum_version', 'TLSv1_2')
    if min_version == 'TLSv1_2':
        context.minimum_version = ssl.TLSVersion.TLSv1_2
    elif min_version == 'TLSv1_1':
        context.minimum_version = ssl.TLSVersion.TLSv1_1
    else:
        context.minimum_version = ssl.TLSVersion.TLSv1
    
    # 设置加密套件
    ciphers = ssl_config.get('ciphers', [])
    if ciphers:
        context.set_ciphers(':'.join(ciphers))
    
    return context


def is_markdown(content: str) -> bool:
    """检测内容是否为Markdown格式"""
    markdown_indicators = [
        '# ', '## ', '### ',  # 标题
        '* ', '- ',           # 无序列表
        '1. ',                # 有序列表
        '```',                # 代码块
        '**', '__',           # 粗体
        '[',                  # 链接
        '|',                  # 表格
        '>',                  # 引用
    ]
    for indicator in markdown_indicators:
        if indicator in content:
            return True
    return False


def markdown_to_html(md_content: str, title: str = "邮件") -> tuple:
    """
    将Markdown转换为邮件友好的HTML（邮件客户端优化版）

    使用内联样式，确保在各种邮件客户端中正常显示

    Returns:
        tuple: (converted_content, is_html, converted_type)
            - converted_type: 'markdown'（成功转HTML）, 'text'（降级为纯文本）, 'html'（原始HTML）
    """
    try:
        import markdown as md_lib
        import re

        # 配置Markdown扩展
        md = md_lib.Markdown(extensions=[
            'extra', 'codehilite', 'tables', 'fenced_code', 'sane_lists'
        ])

        # 转换Markdown到HTML
        html_body = md.convert(md_content)

        # 应用内联样式（邮件客户端兼容性最好）
        styled_html = apply_inline_styles(html_body)

        # 创建完整的HTML文档
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif; line-height: 1.6; color: #333333; margin: 0; padding: 20px; background-color: #f5f5f5;">
    <div style="max-width: 800px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; padding: 40px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);">
        {styled_html}
    </div>
</body>
</html>"""

        return full_html, True, 'markdown'

    except ImportError:
        return md_content, False, 'text'


def apply_inline_styles(html: str) -> str:
    """
    为HTML标签添加内联样式（邮件客户端兼容性最好）
    """
    import re

    # 标题样式
    html = re.sub(
        r'<h1>(.*?)</h1>',
        r'<h1 style="font-size: 32px; color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; margin-top: 0; margin-bottom: 25px;">\1</h1>',
        html
    )
    html = re.sub(
        r'<h2>(.*?)</h2>',
        r'<h2 style="font-size: 26px; color: #34495e; border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; margin-top: 30px; margin-bottom: 20px;">\1</h2>',
        html
    )
    html = re.sub(
        r'<h3>(.*?)</h3>',
        r'<h3 style="font-size: 22px; color: #7f8c8d; margin-top: 25px; margin-bottom: 15px;">\1</h3>',
        html
    )

    # 段落样式
    html = re.sub(
        r'<p>(.*?)</p>',
        r'<p style="margin-bottom: 16px; font-size: 16px;">\1</p>',
        html
    )

    # 列表样式
    html = re.sub(
        r'<ul>',
        '<ul style="margin-bottom: 16px; padding-left: 30px;">',
        html
    )
    html = re.sub(
        r'<ol>',
        '<ol style="margin-bottom: 16px; padding-left: 30px;">',
        html
    )
    html = re.sub(
        r'<li>(.*?)</li>',
        r'<li style="margin-bottom: 8px; font-size: 16px;">\1</li>',
        html
    )

    # 代码样式
    html = re.sub(
        r'<code>(.*?)</code>',
        r'<code style="background-color: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-family: \'Courier New\', monospace; font-size: 14px; color: #e74c3c;">\1</code>',
        html
    )
    html = re.sub(
        r'<pre>(.*?)</pre>',
        r'<pre style="background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 16px; overflow-x: auto; margin-bottom: 16px;"><code style="background-color: transparent; padding: 0; color: #333;">\1</code></pre>',
        html
    )

    # 引用样式
    html = re.sub(
        r'<blockquote>(.*?)</blockquote>',
        r'<blockquote style="border-left: 4px solid #3498db; padding-left: 16px; margin: 20px 0; color: #7f8c8d; font-style: italic;">\1</blockquote>',
        html
    )

    # 表格样式
    html = re.sub(
        r'<table>',
        '<table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">',
        html
    )
    html = re.sub(
        r'<th>(.*?)</th>',
        r'<th style="border: 1px solid #dee2e6; padding: 12px; text-align: left; background-color: #f8f9fa; font-weight: bold;">\1</th>',
        html
    )
    html = re.sub(
        r'<td>(.*?)</td>',
        r'<td style="border: 1px solid #dee2e6; padding: 12px; text-align: left;">\1</td>',
        html
    )

    # 链接样式
    html = re.sub(
        r'<a href="(.*?)">(.*?)</a>',
        r'<a href="\1" style="color: #3498db; text-decoration: none;">\2</a>',
        html
    )

    # 水平线样式
    html = re.sub(
        r'<hr />',
        '<hr style="border: none; border-top: 2px solid #ecf0f1; margin: 30px 0;" />',
        html
    )

    # 粗体和斜体
    html = re.sub(
        r'<strong>(.*?)</strong>',
        r'<strong style="color: #e74c3c; font-weight: bold;">\1</strong>',
        html
    )
    html = re.sub(
        r'<em>(.*?)</em>',
        r'<em style="color: #9b59b6; font-style: italic;">\1</em>',
        html
    )

    return html


def auto_convert_content(body: str, subject: str) -> tuple:
    """
    自动检测内容格式并转换

    Returns:
        tuple: (converted_body, is_html, content_type)
    """
    # 检测是否为HTML
    if body.strip().startswith('<') and '</' in body:
        return body, True, 'html'

    # 检测是否为Markdown
    if is_markdown(body):
        converted, is_html, converted_type = markdown_to_html(body, subject)
        if not is_html:
            # markdown 库未安装，降级为纯文本
            skill_dir = Path(__file__).resolve().parents[1]
            requirements_txt = skill_dir / "requirements.txt"
            print("[⚠️ 警告] 未安装 markdown 库，Markdown 内容将作为纯文本发送！")
            print(f"[ACTION_REQUIRED] 请运行以下命令安装:")
            print(f"    pip install -r {requirements_txt}")
        return converted, is_html, converted_type

    # 纯文本
    return body, False, 'text'


def find_sent_folder(imap: IMAP4_SSL, config: dict) -> str | None:
    """
    智能查找已发送文件夹

    Args:
        imap: IMAP 连接对象
        config: 配置字典

    Returns:
        找到的文件夹名称，未找到返回 None
    """
    try:
        # 列出所有文件夹
        type, folders = imap.list()

        if not folders:
            return None

        # 获取配置的已发送文件夹名称（友好名称，如"已发送"）
        config_friendly_name = config.get('sent_folder', 'Sent')

        # 将友好名称转换为 IMAP 文件夹名称
        config_imap_name = get_imap_folder_name(config_friendly_name)

        print(f"[配置] 已发送文件夹: {config_friendly_name} → {config_imap_name}")

        # 常见的已发送文件夹名称（IMAP UTF-7 编码 + 英文）
        common_sent_names = [
            # IMAP UTF-7 编码（中文文件夹名）
            '&XfJT0ZAB-',      # 已发送
            '&XfJT0ZAB+0Zw-',  # 已发送邮件

            # 英文名称
            'Sent',
            'Sent Items',
            'Sent Messages',
            'Sent Mail',
        ]

        # 第一优先级：精确匹配配置的文件夹
        for folder_bytes in folders:
            folder_str = folder_bytes.decode()
            # 提取文件夹名称（处理 IMAP 格式）
            folder_name = extract_folder_name(folder_str)
            if folder_name == config_imap_name:
                print(f"[检测] 使用配置的已发送文件夹: {folder_name}")
                return folder_name

        # 第二优先级：匹配常见的已发送文件夹名称
        for folder_bytes in folders:
            folder_str = folder_bytes.decode()
            folder_name = extract_folder_name(folder_str)

            # 检查是否匹配任何已发送文件夹名称
            for common_name in common_sent_names:
                if folder_name == common_name:
                    print(f"[检测] 自动检测到已发送文件夹: {folder_name}")
                    return folder_name

        # 第三优先级：模糊匹配（包含 "Sent" 或标记的文件夹）
        for folder_bytes in folders:
            folder_str = folder_bytes.decode()
            folder_name = extract_folder_name(folder_str)

            # 检查是否包含标记 (\Sent)
            if r'\Sent' in folder_str:
                print(f"[检测] 通过标记检测到已发送文件夹: {folder_name}")
                return folder_name

            # 模糊匹配（不区分大小写）
            if 'sent' in folder_name.lower():
                print(f"[检测] 模糊匹配到已发送文件夹: {folder_name}")
                return folder_name

        # 未找到
        return None

    except Exception as e:
        print(f"[警告] 查找已发送文件夹失败: {e}")
        return None


def extract_folder_name(folder_str: str) -> str:
    """
    从 IMAP list() 返回的字符串中提取文件夹名称

    IMAP list() 返回格式示例：
    - () "/" "INBOX"
    - (\\Sent) "/" "&XfJT0ZAB-"
    - (\\Drafts) "/" "&g0l6P3ux-"

    Args:
        folder_str: IMAP list() 返回的文件夹字符串

    Returns:
        文件夹名称
    """
    try:
        # 移除 flags 部分（括号内容）
        if ')' in folder_str:
            folder_str = folder_str.split(')', 1)[1]

        # 提取引号中的内容
        if '"' in folder_str:
            parts = folder_str.split('"')
            # 最后一个引号中的内容通常是文件夹名称
            for i in range(len(parts) - 1, -1, -1):
                if parts[i].strip():
                    return parts[i].strip()

        # 如果没有引号，直接返回
        return folder_str.strip()

    except Exception:
        return folder_str.strip()


def save_to_sent_folder(config: dict, msg: MIMEMultipart, username: str, password: str) -> bool:
    """
    保存邮件到已发送文件夹（智能版本）

    Args:
        config: 配置字典
        msg: 邮件对象
        username: 用户名
        password: 密码

    Returns:
        bool: 是否保存成功
    """
    try:
        # 从配置中获取 IMAP 设置
        imap_server = config.get('imap_host')
        imap_port = config.get('imap_port', 993)

        # 创建 SSL 上下文
        ssl_verify = config.get('imap_ssl_verify', False)
        ssl_ciphers = config.get('imap_ssl_ciphers', '')

        context = ssl.create_default_context()

        if not ssl_verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        if ssl_ciphers:
            context.set_ciphers(ssl_ciphers)

        # 连接到 IMAP 服务器
        with IMAP4_SSL(imap_server, imap_port, ssl_context=context) as imap:
            imap.login(username, password)
            print(f"[保存] 正在保存到已发送文件夹...")

            # 智能查找已发送文件夹
            sent_folder = find_sent_folder(imap, config)

            if not sent_folder:
                # 如果找不到，尝试使用配置的文件夹名称并创建
                config_friendly_name = config.get('sent_folder', 'Sent')
                sent_folder = get_imap_folder_name(config_friendly_name)
                print(f"[提示] 未找到已发送文件夹，尝试创建: {sent_folder}")
                try:
                    imap.create(sent_folder)
                    print(f"[成功] 已创建文件夹: {sent_folder}")
                except Exception as e:
                    print(f"[警告] 创建文件夹失败: {e}")

            # 选择文件夹
            try:
                imap.select(sent_folder)
            except imap.error as e:
                print(f"[错误] 无法选择文件夹 {sent_folder}: {e}")
                return False

            # 将邮件添加到已发送文件夹
            # 使用空时间戳（IMAP 服务器会自动设置）
            imap.append(
                sent_folder,
                '',
                None,  # 让 IMAP 服务器自动设置时间
                msg.as_bytes()
            )

            print(f"[成功] 已保存到已发送文件夹: {sent_folder}")
            return True

    except Exception as e:
        print(f"[警告] 保存到已发送文件夹失败: {e}")
        return False


def send_email(
    config: dict,
    to_email: str,
    subject: str,
    body: str,
    html: bool = False,
    auto_convert: bool = True,
    attachment_path: str | None = None,
    cc: str | None = None,
    bcc: str | None = None
) -> bool:
    """
    发送邮件
    
    Args:
        config: 配置字典（从 load_config() 获取）
        to_email: 收件人邮箱
        subject: 邮件主题
        body: 邮件正文
        html: 是否为HTML格式
        auto_convert: 是否自动检测Markdown并转换
        attachment_path: 附件路径
        cc: 抄送
        bcc: 密送
    
    Returns:
        bool: 发送是否成功
    """
    
    # 从配置中获取 SMTP 设置
    smtp_server = config.get('smtp_host')
    smtp_port = config.get('smtp_port', 465)
    username = config.get('email')
    password = config.get('email_password')
    from_name = config.get('from_name', username)
    
    # 创建SSL上下文（SMTP专用配置）
    ssl_config = {
        'verify': config.get('smtp_ssl_verify', False),
        'check_hostname': config.get('smtp_ssl_verify', False),
        'ciphers': config.get('smtp_ssl_ciphers', '').split(':') if config.get('smtp_ssl_ciphers') else []
    }
    context = create_ssl_context(ssl_config)
    
    # 自动转换内容格式
    final_body = body
    final_html = html
    content_type = 'text'
    
    if auto_convert:
        converted_body, is_html, converted_type = auto_convert_content(body, subject)
        # 如果自动转换检测到 Markdown/HTML，优先使用转换结果
        if is_html:
            final_body = converted_body
            final_html = True
            content_type = converted_type
    
    # 创建邮件
    msg = MIMEMultipart()
    msg['From'] = f"{from_name} <{username}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    
    if cc:
        msg['Cc'] = cc
    if bcc:
        msg['Bcc'] = bcc
    
    # 添加正文
    content_type = 'html' if final_html else 'plain'
    msg.attach(MIMEText(final_body, content_type, 'utf-8'))
    
    # 添加附件
    if attachment_path and os.path.exists(attachment_path):
        filename = os.path.basename(attachment_path)
        with open(attachment_path, 'rb') as f:
            part = MIMEApplication(f.read())
        part.add_header(
            'Content-Disposition',
            'attachment',
            filename=filename
        )
        msg.attach(part)
        print(f"[信息] 已添加附件: {filename}")
    
    # 发送邮件
    try:
        print(f"[连接] 正在连接到 {smtp_server}:{smtp_port}...")
        
        # 显示内容类型
        if content_type == 'markdown':
            print(f"[转换] Markdown → HTML (自动转换)")
        elif content_type == 'html':
            print(f"[格式] HTML邮件")
        else:
            print(f"[格式] 纯文本邮件")
        
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as smtp:
            print("[认证] 正在登录...")
            smtp.login(username, password)
            print("[发送] 正在发送邮件...")
            
            # 构建收件人列表
            recipients = [to_email]
            if cc:
                recipients.append(cc)
            if bcc:
                recipients.append(bcc)
            
            smtp.send_message(msg)
            print("[成功] 邮件发送成功！")
            
            # 保存到已发送文件夹
            if config.get('enable_save_to_sent', True):
                save_to_sent_folder(
                    config=config,
                    msg=msg,
                    username=username,
                    password=password
                )
            
            return True
            
    except smtplib.SMTPAuthenticationError:
        print("[错误] 认证失败：用户名或密码错误")
        return False
        
    except smtplib.SMTPException as e:
        print(f"[错误] SMTP错误: {e}")
        return False
        
    except Exception as e:
        print(f"[错误] 发送失败: {e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='🐒 Wukong Email - 发送邮件工具 (支持Markdown自动转换)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 1. 发送纯文本邮件（从 ~/.wukong-email/.env 加载配置）
  python send_email.py --to user@example.com --subject "测试" --body "你好"

  # 2. 发送Markdown邮件（自动转换为HTML）
  python send_email.py --to user@example.com --subject "周报" --body "# 标题\n\n这是**粗体**文本"

  # 3. 发送HTML邮件
  python send_email.py --to user@example.com --subject "测试" --body "<h1>你好</h1>" --html

  # 4. 发送带附件的邮件
  python send_email.py --to user@example.com --subject "报告" --body "请查收" --attach report.pdf

  # 5. 禁用自动转换
  python send_email.py --to user@example.com --subject "测试" --body "# 标题" --no-auto-convert

  # 6. 使用命令行参数覆盖配置
  python send_email.py --to user@example.com --subject "测试" --body "你好" \\
      --server smtp.example.com --user me@example.com --password xxx

配置说明:
  配置文件优先级：环境变量 > ~/.wukong-email/.env > 默认值
  首次使用请复制 env.example 为 ~/.wukong-email/.env 并填写邮箱信息
        """
    )
    
    # 必需参数
    parser.add_argument('--to', required=True, help='收件人邮箱')
    parser.add_argument('--subject', required=True, help='邮件主题')
    parser.add_argument('--body', required=True, help='邮件正文')
    
    # 可选参数
    parser.add_argument('--html', action='store_true', help='HTML格式邮件')
    parser.add_argument('--no-auto-convert', action='store_true', help='禁用Markdown自动转换')
    parser.add_argument('--attach', help='附件路径')
    parser.add_argument('--cc', help='抄送')
    parser.add_argument('--bcc', help='密送')
    
    # 配置覆盖参数（可选）
    parser.add_argument('--server', help='SMTP服务器地址（覆盖配置）')
    parser.add_argument('--port', type=int, help='SMTP端口（覆盖配置）')
    parser.add_argument('--user', help='发件人邮箱（覆盖配置）')
    parser.add_argument('--password', help='邮箱密码（覆盖配置，不推荐）')
    parser.add_argument('--show-config', action='store_true', help='显示当前配置（调试用）')
    
    args = parser.parse_args()
    
    # 加载配置
    try:
        config = load_config()
        
        # 命令行参数覆盖配置
        if args.server:
            config['smtp_host'] = args.server
        if args.port:
            config['smtp_port'] = args.port
        if args.user:
            config['email'] = args.user
        if args.password:
            config['email_password'] = args.password
        
        # 验证必需字段
        if not all([config.get('smtp_host'), config.get('email'), config.get('email_password')]):
            print("[错误] 配置不完整，请设置以下参数：")
            print("  - EMAIL_ADDRESS (邮箱地址)")
            print("  - EMAIL_PASSWORD (邮箱密码)")
            print("  - EMAIL_SMTP_HOST (SMTP服务器)")
            print("\n提示: 复制 env.example 为 ~/.wukong-email/.env 并填写配置")
            sys.exit(1)
        
        # 显示配置摘要
        if args.show_config:
            print_config()
        
    except ValueError as e:
        print(f"[错误] {e}")
        sys.exit(1)
    
    # 发送邮件
    success = send_email(
        config=config,
        to_email=args.to,
        subject=args.subject,
        body=args.body,
        html=args.html,
        auto_convert=not args.no_auto_convert,
        attachment_path=args.attach,
        cc=args.cc,
        bcc=args.bcc
    )
    
    result = {
        'success': success,
        'to': args.to,
        'subject': args.subject,
        'html': args.html,
        'attachment': args.attach or None,
        'cc': args.cc or None,
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
