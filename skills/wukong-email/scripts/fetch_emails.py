#!/usr/bin/env python3
"""
Wukong Email - 收取邮件脚本（增强版）
====================================
支持自动下载附件
"""

from imaplib import IMAP4_SSL
import email
from email.header import decode_header
import ssl
import argparse
import sys
from typing import List, Dict, Tuple
from datetime import datetime
from pathlib import Path

# 导入配置加载器和辅助工具
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import load_config
from decode_helper import decode_mime_filename, decode_header_value_enhanced as decode_str
from imap_utf7 import get_imap_folder_name


def create_ssl_context(ssl_config: dict = None):
    """
    创建SSL上下文

    Args:
        ssl_config: SSL配置字典，包含 verify, check_hostname, ciphers

    Returns:
        SSL上下文对象
    """
    if ssl_config is None:
        ssl_config = {}

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    # 根据配置设置SSL选项
    context.check_hostname = ssl_config.get('check_hostname', False)
    context.verify_mode = ssl.CERT_NONE if not ssl_config.get('verify', False) else ssl.CERT_REQUIRED

    # 设置最低TLS版本
    context.minimum_version = ssl.TLSVersion.TLSv1_2

    # 设置加密套件
    ciphers = ssl_config.get('ciphers', [])
    if ciphers:
        context.set_ciphers(':'.join(ciphers))
    else:
        # 默认加密套件
        context.set_ciphers(
            'ECDHE-RSA-AES256-GCM-SHA384:'
            'ECDHE-ECDSA-AES256-GCM-SHA384:'
            'AES256-GCM-SHA384:'
            'AES256-SHA256'
        )

    return context


def decode_header_value(header_value: str) -> str:
    """
    解码邮件头
    
    Args:
        header_value: 原始邮件头
        
    Returns:
        str: 解码后的邮件头
    """
    if header_value is None:
        return ""
    
    decoded_parts = []
    for part, encoding in decode_header(header_value):
        if isinstance(part, bytes):
            try:
                decoded_parts.append(part.decode(encoding or 'utf-8'))
            except:
                decoded_parts.append(part.decode('utf-8', errors='ignore'))
        else:
            decoded_parts.append(str(part))
    
    result = ''.join(decoded_parts)
    
    # 清理少数服务器返回的异常发件人地址后缀
    # 例如：发件人 <user@example.com>@extra-domain
    # 应该显示为：发件人 <user@example.com>
    if '@' in result and result.count('@') > 1:
        # 移除最后一个 @ 及其后面的内容
        parts = result.rsplit('@', 1)
        if '>' in parts[0]:
            result = parts[0]
        else:
            # 如果没有尖括号，尝试只保留邮箱部分
            result = result.replace('@' + parts[-1], '')
    
    return result


def clean_email_address(email_str: str) -> str:
    """
    清理邮箱地址，移除多余的域名后缀
    
    Args:
        email_str: 原始邮箱字符串
        
    Returns:
        str: 清理后的邮箱字符串
    """
    if not email_str:
        return ""
    
    # 如果有多个 @ 符号，移除最后一个
    if email_str.count('@') > 1:
        # 找到最后一个 @ 的位置
        last_at = email_str.rfind('@')
        
        # 检查是否在尖括号外
        if '>' in email_str[:last_at]:
            # 有尖括号，移除最后的 @xxx
            return email_str[:last_at].rstrip()
        else:
            # 没有尖括号，尝试智能清理
            # 例如：user@example.com@extra-domain
            # 应该变成：user@example.com
            parts = email_str.split('@')
            # 保留前两部分（名称和真实域名）
            if len(parts) >= 2:
                # 找到有效的邮箱格式（通常第一个 @ 后面的部分是真实域名）
                for i in range(1, len(parts)):
                    potential_email = '@'.join(parts[:i+1])
                    # 简单验证：真实域名通常包含点号
                    if '.' in parts[i]:
                        return potential_email
            
            # 如果无法判断，返回原字符串
            return email_str
    
    return email_str


def get_email_body(msg) -> str:
    """提取邮件正文"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    try:
                        body = part.get_payload(decode=True).decode('gbk', errors='ignore')
                    except:
                        pass
                if body:
                    break
    else:
        try:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except:
            try:
                body = msg.get_payload(decode=True).decode('gbk', errors='ignore')
            except:
                body = str(msg.get_payload())
    
    return body


def get_attachments_dir() -> str:
    """获取附件下载目录"""
    config = load_config()
    attachments_dir = config.get('attachments_dir', '~/.wukong-email/attachments')
    
    # 展开路径中的 ~
    attachments_dir = os.path.expanduser(attachments_dir)
    
    # 创建目录（如果不存在）
    os.makedirs(attachments_dir, exist_ok=True)
    
    return attachments_dir


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符"""
    # 替换 Windows/Linux 不允许的字符
    illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in illegal_chars:
        filename = filename.replace(char, '_')
    return filename


def is_attachment_downloaded(email_dir: str, filename: str) -> bool:
    """检查附件是否已下载"""
    file_path = os.path.join(email_dir, filename)
    return os.path.exists(file_path)


def download_attachments_from_email(imap, email_uid, msg, attachments_dir: str, force: bool = False) -> Tuple[int, int, int]:
    """
    从单封邮件下载所有附件
    
    参数：
        imap: IMAP 连接对象
        email_uid: 邮件 UID
        msg: 邮件消息对象
        attachments_dir: 附件保存根目录
        force: 是否强制重新下载（覆盖已存在文件）
    
    返回：
        (success_count, skip_count, error_count)
    """
    # 为这封邮件创建子目录（使用 UID）
    # 确保 UID 是字符串类型
    if isinstance(email_uid, bytes):
        email_uid = email_uid.decode('utf-8')
    
    email_dir = os.path.join(attachments_dir, str(email_uid))
    os.makedirs(email_dir, exist_ok=True)
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    # 遍历邮件的所有部分
    for part in msg.walk():
        # 跳过非附件部分
        content_disposition = str(part.get("Content-Disposition", ""))
        if "attachment" not in content_disposition.lower():
            continue
        
        # 获取附件信息
        filename = part.get_filename()
        if not filename:
            continue
        
        # 解码文件名
        decoded_filename = decode_mime_filename(filename)
        if not decoded_filename:
            decoded_filename = filename
        
        # 清理文件名
        safe_filename = sanitize_filename(decoded_filename)
        file_path = os.path.join(email_dir, safe_filename)
        
        # 检查是否已下载
        if not force and is_attachment_downloaded(email_dir, safe_filename):
            print(f"  ⏭️  跳过已存在: {safe_filename}")
            skip_count += 1
            continue
        
        # 下载附件
        try:
            with open(file_path, 'wb') as f:
                f.write(part.get_payload(decode=True))
            
            file_size = os.path.getsize(file_path)
            print(f"  ✅ 下载成功: {safe_filename} ({file_size:,} bytes)")
            success_count += 1
            
        except Exception as e:
            print(f"  ❌ 下载失败: {safe_filename} - {e}")
            error_count += 1
    
    # 创建邮件信息文件（记录邮件元数据）
    info_file = os.path.join(email_dir, 'email_info.txt')
    if not os.path.exists(info_file):
        try:
            with open(info_file, 'w', encoding='utf-8') as f:
                f.write(f"邮件 UID: {email_uid}\n")
                f.write(f"主题: {decode_str(msg.get('Subject', ''))}\n")
                f.write(f"发件人: {decode_str(msg.get('From', ''))}\n")
                f.write(f"日期: {msg.get('Date', '')}\n")
                f.write(f"下载时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        except Exception as e:
            print(f"  ⚠️  创建信息文件失败: {e}")
    
    return success_count, skip_count, error_count


def fetch_emails(
    imap_server: str,
    imap_port: int,
    username: str,
    password: str,
    folder: str = "INBOX",
    limit: int = 10,
    search_criteria: str = "ALL",
    ssl_config: dict = None,
    download_attachments: bool = False,
    attachments_dir: str = None,
    force_download: bool = False,
    only_with_attachments: bool = False
) -> List[Dict]:
    """
    收取邮件（支持自动下载附件、只获取有附件的邮件）

    Args:
        imap_server: IMAP服务器地址
        imap_port: IMAP端口
        username: 邮箱用户名
        password: 邮箱密码
        folder: 文件夹名称 (默认: INBOX)
        limit: 获取邮件数量 (默认: 10)
        search_criteria: 搜索条件 (默认: ALL)
        ssl_config: SSL配置字典 (可选)
        download_attachments: 是否自动下载附件
        attachments_dir: 附件保存目录
        force_download: 是否强制重新下载附件
        only_with_attachments: 只获取有附件的邮件

    Returns:
        List[Dict]: 邮件列表
    """

    # 创建SSL上下文（IMAP专用配置）
    if ssl_config is None:
        ssl_config = {}
    context = create_ssl_context(ssl_config)
    
    imap = None
    try:
        print(f"[连接] 正在连接到 {imap_server}:{imap_port}...")
        imap = IMAP4_SSL(imap_server, imap_port, ssl_context=context)
        
        print("[认证] 正在登录...")
        imap.login(username, password)
        
        # 使用 imap_utf7 支持中文文件夹名
        folder_name = get_imap_folder_name(folder)
        print(f"[选择] 正在选择文件夹: {folder}...")
        imap.select(folder_name)
        
        print(f"[搜索] 搜索条件: {search_criteria}...")
        status, messages = imap.search(None, search_criteria)
        
        if status != 'OK':
            print(f"[错误] 搜索失败: {status}")
            return []
        
        email_ids = messages[0].split()
        total_count = len(email_ids)
        
        print(f"[信息] 找到 {total_count} 封邮件")
        
        # 获取最新的N封邮件
        email_ids = email_ids[-limit:] if total_count > limit else email_ids
        
        print(f"[收取] 正在获取最新的 {len(email_ids)} 封邮件...")
        if download_attachments:
            print(f"[附件] 自动下载附件到: {attachments_dir}")
        
        emails = []
        total_success = 0
        total_skip = 0
        total_error = 0
        
        for idx, email_id in enumerate(email_ids, 1):
            _, msg_data = imap.fetch(email_id, '(RFC822)')
            if not msg_data or not msg_data[0]:
                continue
                
            raw_email = msg_data[0][1]
            if not isinstance(raw_email, bytes):
                continue
                
            msg = email.message_from_bytes(raw_email)
            
            from_header = msg.get('From') or ""
            to_header = msg.get('To') or ""
            subject_header = msg.get('Subject') or ""
            
            # 解码并清理邮箱地址
            from_clean = decode_header_value(from_header)
            to_clean = decode_header_value(to_header)
            subject_clean = decode_header_value(subject_header)
            
            email_info = {
                'id': email_id.decode(),
                'from': from_clean,
                'to': to_clean,
                'subject': subject_clean,
                'date': msg.get('Date', ''),
                'body': get_email_body(msg),
                'msg': msg  # 保留原始消息对象用于下载附件
            }
            emails.append(email_info)
            print(f"  [{idx}/{len(email_ids)}] {email_info['subject'][:50]}...")
            
            # 自动下载附件
            if download_attachments:
                success, skip, error = download_attachments_from_email(
                    imap, email_id, msg, attachments_dir, force_download
                )
                total_success += success
                total_skip += skip
                total_error += error
                
                # 如果只获取有附件的邮件，跳过没有附件的
                if only_with_attachments and (success + skip + error) == 0:
                    emails.pop()  # 移除这封邮件
                    continue
        
        print(f"[成功] 已获取 {len(emails)} 封邮件")
        if download_attachments:
            print(f"[附件统计] 成功: {total_success}, 跳过: {total_skip}, 失败: {total_error}")
        
        return emails
        
    except Exception as e:
        print(f"[错误] 收取邮件失败: {e}")
        return []
        
    finally:
        if imap:
            try:
                imap.close()
                imap.logout()
            except:
                pass


def display_email(email_info: Dict):
    """显示邮件详情"""
    print("=" * 70)
    print(f"邮件ID: {email_info['id']}")
    print(f"发件人: {email_info['from']}")
    print(f"收件人: {email_info['to']}")
    print(f"主题: {email_info['subject']}")
    print(f"日期: {email_info['date']}")
    print("=" * 70)
    print("正文:")
    print(email_info['body'][:500])
    if len(email_info['body']) > 500:
        print("... (内容过长，已截断)")
    print()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Wukong Email - 收取邮件工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 获取最新10封邮件
  python fetch_emails.py

  # 获取最新20封邮件
  python fetch_emails.py --limit 20

  # 搜索特定发件人的邮件
  python fetch_emails.py --search 'FROM "user@example.com"'

  # 搜索特定主题的邮件
  python fetch_emails.py --search 'SUBJECT "测试"'

  # 显示完整邮件正文
  python fetch_emails.py --full
        """
    )
    
    parser.add_argument('--config', help='配置文件路径 (已弃用，请使用 ~/.wukong-email/.env)')
    parser.add_argument('--server', help='IMAP服务器地址')
    parser.add_argument('--port', type=int, default=993, help='IMAP端口 (默认: 993)')
    parser.add_argument('--user', help='邮箱用户名')
    parser.add_argument('--password', help='邮箱密码')
    parser.add_argument('--folder', default='INBOX', help='文件夹 (默认: INBOX)')
    parser.add_argument('--limit', type=int, default=10, help='获取邮件数量 (默认: 10)')
    parser.add_argument('--uids', required=True, help='邮件UID列表（逗号分隔），例如：2060,2061,2062')
    parser.add_argument('--download-attachments', action='store_true', help='自动下载附件')
    parser.add_argument('--force-download', action='store_true', help='强制重新下载附件（覆盖已存在文件）')
    parser.add_argument('--list', action='store_true', help='仅列出邮件，不显示正文')
    parser.add_argument('--full', action='store_true', help='显示完整正文')

    args = parser.parse_args()
    
    # 使用配置加载器
    imap_server = args.server
    imap_port = args.port
    username = args.user
    password = args.password
    if not all([imap_server, username, password]):
        if args.config:
            print("[警告] --config 参数已弃用，请使用 config_loader 和 ~/.wukong-email/.env 文件")
        
        # 使用配置加载器
        config = load_config()
        imap_server = config['imap_host']
        imap_port = config['imap_port']
        username = config['email']
        password = config['email_password']
        
        print(f"[配置] 使用预设: {config.get('preset_name', 'default')}")
        print(f"[配置] IMAP: {imap_server}:{imap_port}")
        print(f"[配置] 用户: {username}")

    # 收取邮件
    # 构建 IMAP SSL 配置
    imap_ssl_config = {
        'verify': config['imap_ssl_verify'],
        'check_hostname': config['imap_ssl_verify'],
        'ciphers': config['imap_ssl_ciphers'].split(':') if config.get('imap_ssl_ciphers') else []
    }
    
    # 获取附件目录（如果需要下载附件）
    attachments_dir = None
    if args.download_attachments:
        attachments_dir = get_attachments_dir()

    # 从 --uids 参数构建搜索条件
    search_criteria = f'UID {args.uids}'
    
    emails = fetch_emails(
        imap_server=imap_server,
        imap_port=imap_port,
        username=username,
        password=password,
        folder=args.folder,
        limit=9999,  # 不限制数量
        search_criteria=search_criteria,
        ssl_config=imap_ssl_config,
        download_attachments=args.download_attachments,
        attachments_dir=attachments_dir,
        force_download=args.force_download,
        only_with_attachments=False
    )

    if not emails:
        print("[信息] 没有找到邮件")
        sys.exit(0)
    
    # 如果下载了附件，显示附件清单
    if args.download_attachments:
        print("\n" + "=" * 70)
        print("附件清单")
        print("=" * 70)
        
        for idx, email_info in enumerate(emails, 1):
            email_uid = email_info['id']
            email_dir = os.path.join(attachments_dir, email_uid)
            
            # 列出这封邮件的所有附件
            if os.path.exists(email_dir):
                attachments = []
                for file in os.listdir(email_dir):
                    if file == 'email_info.txt':
                        continue
                    file_path = os.path.join(email_dir, file)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        attachments.append((file, file_size))
                
                if attachments:
                    print(f"\n{idx}. UID: {email_uid} - {email_info['subject'][:50]}")
                    for filename, size in attachments:
                        size_mb = size / (1024 * 1024)
                        if size_mb >= 1:
                            size_str = f"{size_mb:.2f} MB"
                        else:
                            size_str = f"{size / 1024:.2f} KB"
                        print(f"   📎 {filename} ({size_str})")
                        print(f"      路径: {email_dir}/{filename}")
        
        print("\n" + "=" * 70)
        print(f"总计: {len(emails)} 封邮件")
        print(f"附件保存目录: {attachments_dir}")
        print("=" * 70)
        sys.exit(0)
    
    # 显示邮件
    if args.list:
        # 仅列出邮件
        print("\n" + "=" * 70)
        print("邮件列表")
        print("=" * 70)
        for idx, email_info in enumerate(emails, 1):
            print(f"{idx}. {email_info['subject'][:60]}")
            print(f"   发件人: {email_info['from'][:50]}")
            print(f"   日期: {email_info['date']}")
            print()
    else:
        # 显示完整邮件
        for email_info in emails:
            display_email(email_info)
            if not args.full:
                # 如果不是显示完整模式，只显示第一封
                break


if __name__ == '__main__':
    main()
