#!/usr/bin/env python3
"""
Wukong Email - 删除邮件脚本
============================
将邮件移动到"已删除"文件夹（非永久删除，可恢复）

安全特性：
- 只移动到"已删除"文件夹，不执行永久删除
- 支持预览模式（--dry-run）
- 交互式确认（显示匹配邮件数量）
- 支持友好文件夹名称（中文"已删除"）
"""

from imaplib import IMAP4_SSL
import email
from email.header import decode_header
import ssl
import argparse
import sys
from typing import List, Dict, Tuple
import json

# 导入配置加载器
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import load_config
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
    
    # 清理发件人地址中的多余域名后缀
    if '@' in result and result.count('@') > 1:
        parts = result.rsplit('@', 1)
        if '>' in parts[0]:
            result = parts[0]
        else:
            result = result.replace('@' + parts[-1], '')
    
    return result


def find_deleted_folder(imap: IMAP4_SSL, folder_name: str = None) -> str:
    """
    查找"已删除"文件夹
    
    Args:
        imap: IMAP连接对象
        folder_name: 配置的文件夹名称（友好名称或编码名称）
    
    Returns:
        str: 文件夹的IMAP编码名称
    """
    # 列出所有文件夹
    status, folders = imap.list()
    if status != 'OK':
        print("❌ 无法列出文件夹")
        return None
    
    folder_list = []
    for folder in folders:
        # 解析文件夹名称：folder 是字节串，格式：b'(\\HasNoChildren) "/" "INBOX"'
        parts = folder.decode().split('"')
        if len(parts) >= 3:
            folder_name_decoded = parts[-2] if parts[-2] else parts[1]
            folder_list.append(folder_name_decoded)
    
    # 优先级1：精确匹配配置的文件夹名称
    if folder_name:
        # 尝试友好名称
        encoded = get_imap_folder_name(folder_name)
        if encoded in folder_list:
            return encoded
        # 直接匹配
        if folder_name in folder_list:
            return folder_name
    
    # 优先级2：匹配常见已删除文件夹名称
    common_names = [
        get_imap_folder_name('已删除'),
        get_imap_folder_name('Deleted Items'),
        get_imap_folder_name('Trash'),
        'Deleted',
        'Trash',
        'INBOX.Trash'
    ]
    
    for name in common_names:
        if name in folder_list:
            return name
    
    # 优先级3：模糊匹配（通过IMAP标记）
    for folder in folder_list:
        folder_lower = folder.lower()
        if 'deleted' in folder_lower or 'trash' in folder_lower or '删除' in folder:
            return folder
    
    print("⚠️  警告：未找到'已删除'文件夹，将使用默认 'Trash'")
    return 'Trash'


def search_emails(imap: IMAP4_SSL, search_criteria: str, limit: int = None) -> List[str]:
    """
    搜索邮件
    
    Args:
        imap: IMAP连接对象
        search_criteria: IMAP搜索条件
        limit: 限制返回数量
    
    Returns:
        List[str]: 邮件ID列表
    """
    status, messages = imap.search(None, search_criteria)
    if status != 'OK':
        print(f"❌ 搜索失败: {status}")
        return []
    
    email_ids = messages[0].split()
    
    # IMAP返回的是按ID排序的，最新的在最后
    if limit:
        email_ids = email_ids[-limit:]  # 取最近的N封
    
    return email_ids


def preview_emails(imap: IMAP4_SSL, email_ids: List[str], max_preview: int = 10) -> List[Dict]:
    """
    预览邮件（只显示前几封）
    
    Args:
        imap: IMAP连接对象
        email_ids: 邮件ID列表
        max_preview: 最多显示几封
    
    Returns:
        List[Dict]: 邮件信息列表
    """
    preview_list = []
    
    # 只显示最新的几封（邮件ID是升序，大的在后面）
    preview_ids = email_ids[-max_preview:] if len(email_ids) > max_preview else email_ids
    
    for email_id in preview_ids:
        try:
            status, msg_data = imap.fetch(email_id, '(RFC822)')
            if status == 'OK':
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                email_info = {
                    'id': email_id.decode(),
                    'from': decode_header_value(email_message.get('From', '')),
                    'subject': decode_header_value(email_message.get('Subject', ''))[:50],
                    'date': email_message.get('Date', '')[:20]
                }
                preview_list.append(email_info)
        except Exception as e:
            print(f"⚠️  解析邮件 {email_id} 失败: {e}")
    
    return preview_list


def move_to_deleted_folder(
    imap: IMAP4_SSL,
    email_ids: List[str],
    deleted_folder: str,
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    将邮件移动到"已删除"文件夹
    
    Args:
        imap: IMAP连接对象
        email_ids: 邮件ID列表
        deleted_folder: 目标文件夹（IMAP编码名称）
        dry_run: 是否为预览模式
    
    Returns:
        Tuple[int, int]: (成功数量, 失败数量)
    """
    success_count = 0
    fail_count = 0
    
    print(f"\n{'='*60}", file=sys.stderr)
    if dry_run:
        print(f"🔍 [预览模式] 将移动 {len(email_ids)} 封邮件到 '{deleted_folder}'", file=sys.stderr)
    else:
        print(f"🗑️  正在移动 {len(email_ids)} 封邮件到 '{deleted_folder}'...", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)
    
    for i, email_id in enumerate(email_ids, 1):
        try:
            if not dry_run:
                # 1. 复制到已删除文件夹
                status = imap.copy(email_id, deleted_folder)
                if status[0] != 'OK':
                    print(f"⚠️  [{i}/{len(email_ids)}] 复制邮件 {email_id.decode()} 失败: {status}", file=sys.stderr)
                    fail_count += 1
                    continue
                
                # 2. 标记为删除（从原文件夹移除）
                status = imap.store(email_id, '+FLAGS', '\\\\Deleted')
                if status[0] != 'OK':
                    print(f"⚠️  [{i}/{len(email_ids)}] 标记删除 {email_id.decode()} 失败: {status}", file=sys.stderr)
                    fail_count += 1
                    continue
            else:
                # 预览模式
                print(f"  [{i}/{len(email_ids)}] 将移动邮件 {email_id.decode()}", file=sys.stderr)
            
            success_count += 1
            
        except Exception as e:
            print(f"⚠️  [{i}/{len(email_ids)}] 处理邮件 {email_id.decode()} 异常: {e}", file=sys.stderr)
            fail_count += 1
    
    if not dry_run:
        # 3. 执行删除（从当前文件夹移除已标记的邮件）
        try:
            imap.expunge()
            print(f"✅ 成功移动 {success_count} 封邮件到 '{deleted_folder}'", file=sys.stderr)
        except Exception as e:
            print(f"⚠️  expunge 失败: {e}", file=sys.stderr)
    else:
        print(f"🔍 [预览模式] 将移动 {success_count} 封邮件（未实际执行）", file=sys.stderr)
    
    return success_count, fail_count


def main():
    parser = argparse.ArgumentParser(
        description='将邮件移动到"已删除"文件夹（非永久删除）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 预览最近10天的邮件（不删除）
  python delete_emails.py --search "SINCE 13-May-2026" --dry-run
  
  # 删除特定发件人的邮件
  python delete_emails.py --search 'FROM "spam@example.com"'
  
  # 删除包含特定关键词的邮件
  python delete_emails.py --search 'SUBJECT "广告"'
  
  # 删除未读邮件
  python delete_emails.py --search "UNSEEN" --dry-run
  
  # 组合搜索：最近7天 + 特定发件人
  python delete_emails.py --search 'SINCE 16-May-2026 FROM "newsletter@example.com"'
        '''
    )
    
    parser.add_argument('--search', required=True, 
                       help='IMAP搜索条件，例如：SINCE 13-May-2026, FROM "user@example.com", SUBJECT "关键词", UNSEEN')
    parser.add_argument('--folder', default='INBOX',
                       help='要搜索的文件夹（默认: INBOX）')
    parser.add_argument('--deleted-folder', 
                       help='"已删除"文件夹名称（友好名称，如"已删除"）')
    parser.add_argument('--limit', type=int,
                       help='限制处理的邮件数量（最近的N封）')
    parser.add_argument('--preview', type=int, default=10,
                       help='预览时显示的邮件数量（默认: 10）')
    parser.add_argument('--dry-run', action='store_true',
                       help='预览模式：只显示匹配的邮件，不执行删除')
    parser.add_argument('--yes', action='store_true',
                       help='跳过确认提示，直接执行（谨慎使用）')
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_config()
    
    if not config.get('imap_host'):
        print("❌ IMAP配置未找到，请检查 ~/.wukong-email/.env 文件")
        sys.exit(1)
    
    # 创建SSL上下文
    ssl_context = create_ssl_context(config.get('imap_ssl', {}))
    
    try:
        # 连接到IMAP服务器
        imap = IMAP4_SSL(config['imap_host'], config['imap_port'], ssl_context=ssl_context)
        
        # 登录
        imap.login(config['email'], config['email_password'])
        
        # 选择文件夹
        imap.select(args.folder)
        
        # 搜索邮件
        email_ids = search_emails(imap, args.search, args.limit)
        
        if not email_ids:
            imap.logout()
            print(json.dumps({'success': True, 'total': 0, 'moved': 0, 'failed': 0, 'search': args.search, 'dry_run': args.dry_run}, ensure_ascii=False))
            return
        
        # 查找"已删除"文件夹
        deleted_folder = find_deleted_folder(imap, args.deleted_folder)
        
        # 确认执行
        if not args.yes and not args.dry_run:
            print(f"⚠️  即将移动 {len(email_ids)} 封邮件到 '{deleted_folder}'，移动后可恢复", file=sys.stderr)
            confirm = input("确认执行？(yes/no): ").strip().lower()
            if confirm not in ['yes', 'y']:
                imap.logout()
                print(json.dumps({'success': False, 'total': len(email_ids), 'moved': 0, 'failed': 0, 'cancelled': True, 'search': args.search}, ensure_ascii=False))
                return
        
        # 执行移动
        success, fail = move_to_deleted_folder(imap, email_ids, deleted_folder, args.dry_run)
        
        imap.logout()
        
        print(json.dumps({
            'success': True,
            'total': len(email_ids),
            'moved': success,
            'failed': fail,
            'search': args.search,
            'dry_run': args.dry_run,
        }, ensure_ascii=False))
        
    except Exception as e:
        print(json.dumps({'success': False, 'error': str(e), 'search': args.search}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
