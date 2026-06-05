#!/usr/bin/env python3
"""
Wukong Email - 中文搜索测试脚本
==============================
测试不同编码方式搜索中文邮件主题和正文
"""

from imaplib import IMAP4_SSL
import email
from email.header import decode_header
import ssl
import argparse
import sys
from typing import List, Dict, Tuple

# 导入配置加载器
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import load_config
from imap_utf7 import get_imap_folder_name


def create_ssl_context(ssl_config: dict = None):
    """创建SSL上下文"""
    if ssl_config is None:
        ssl_config = {}
    
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = ssl_config.get('check_hostname', False)
    context.verify_mode = ssl.CERT_NONE if not ssl_config.get('verify', False) else ssl.CERT_REQUIRED
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    
    ciphers = ssl_config.get('ciphers', [])
    if ciphers:
        context.set_ciphers(':'.join(ciphers))
    else:
        context.set_ciphers(
            'ECDHE-RSA-AES256-GCM-SHA384:'
            'ECDHE-ECDSA-AES256-GCM-SHA384:'
            'AES256-GCM-SHA384:'
            'AES256-SHA256'
        )
    
    return context


def decode_header_value(header_value: str) -> str:
    """解码邮件头"""
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
    
    if '@' in result and result.count('@') > 1:
        parts = result.rsplit('@', 1)
        if '>' in parts[0]:
            result = parts[0]
        else:
            result = result.replace('@' + parts[-1], '')
    
    return result


def search_with_charset(imap: IMAP4_SSL, charset: str, search_criteria: str) -> Tuple[bool, List[str]]:
    """
    使用指定字符集搜索邮件
    
    Args:
        imap: IMAP连接对象
        charset: 字符集（UTF-8, GBK, etc.）
        search_criteria: 搜索条件
    
    Returns:
        (是否成功, 邮件ID列表)
    """
    try:
        # 转换为指定编码
        encoded_criteria = search_criteria.encode(charset)
        status, messages = imap.search(f'CHARSET {charset}', encoded_criteria)
        if status == 'OK':
            email_ids = messages[0].split()
            return True, email_ids
        else:
            return False, []
    except Exception as e:
        print(f"  ❌ {charset} 编码失败: {e}")
        return False, []


def search_subject_utf8(imap: IMAP4_SSL, keyword: str) -> Tuple[bool, List[str]]:
    """使用 UTF-8 编码搜索主题"""
    criteria = f'SUBJECT "{keyword}"'
    return search_with_charset(imap, 'UTF-8', criteria)


def search_subject_gbk(imap: IMAP4_SSL, keyword: str) -> Tuple[bool, List[str]]:
    """使用 GBK 编码搜索主题"""
    criteria = f'SUBJECT "{keyword}"'
    return search_with_charset(imap, 'GBK', criteria)


def search_body_utf8(imap: IMAP4_SSL, keyword: str) -> Tuple[bool, List[str]]:
    """使用 UTF-8 编码搜索正文"""
    criteria = f'BODY "{keyword}"'
    return search_with_charset(imap, 'UTF-8', criteria)


def search_body_gbk(imap: IMAP4_SSL, keyword: str) -> Tuple[bool, List[str]]:
    """使用 GBK 编码搜索正文"""
    criteria = f'BODY "{keyword}"'
    return search_with_charset(imap, 'GBK', criteria)


def search_text_utf8(imap: IMAP4_SSL, keyword: str) -> Tuple[bool, List[str]]:
    """使用 UTF-8 编码搜索主题或正文"""
    criteria = f'TEXT "{keyword}"'
    return search_with_charset(imap, 'UTF-8', criteria)


def search_text_gbk(imap: IMAP4_SSL, keyword: str) -> Tuple[bool, List[str]]:
    """使用 GBK 编码搜索主题或正文"""
    criteria = f'TEXT "{keyword}"'
    return search_with_charset(imap, 'GBK', criteria)


def search_emails_by_content(imap: IMAP4_SSL, keyword: str, limit: int = None) -> List[Dict]:
    """
    通过邮件内容搜索（下载邮件后搜索）
    
    Args:
        imap: IMAP连接对象
        keyword: 搜索关键词
        limit: 限制搜索邮件数量
    
    Returns:
        匹配的邮件列表
    """
    matched_emails = []
    
    # 先获取最近的邮件
    status, messages = imap.search(None, 'ALL')
    if status != 'OK':
        return matched_emails
    
    email_ids = messages[0].split()
    if limit:
        email_ids = email_ids[-limit:]
    
    print(f"📥 正在搜索 {len(email_ids)} 封邮件的内容...")
    
    for i, email_id in enumerate(email_ids, 1):
        try:
            # 获取邮件
            status, msg_data = imap.fetch(email_id, '(RFC822)')
            if status != 'OK':
                continue
            
            email_body = msg_data[0][1]
            email_message = email.message_from_bytes(email_body)
            
            # 检查主题
            subject = decode_header_value(email_message.get('Subject', ''))
            if keyword in subject:
                matched_emails.append({
                    'id': email_id.decode(),
                    'from': decode_header_value(email_message.get('From', '')),
                    'subject': subject[:50],
                    'date': email_message.get('Date', '')[:20],
                    'match_type': '主题'
                })
                continue
            
            # 检查正文
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    if content_type == 'text/plain' or content_type == 'text/html':
                        payload = part.get_payload(decode=True)
                        if payload:
                            # 尝试多种编码
                            for encoding in ['utf-8', 'gbk', 'gb2312']:
                                try:
                                    text = payload.decode(encoding)
                                    if keyword in text:
                                        matched_emails.append({
                                            'id': email_id.decode(),
                                            'from': decode_header_value(email_message.get('From', '')),
                                            'subject': subject[:50],
                                            'date': email_message.get('Date', '')[:20],
                                            'match_type': f'正文 ({encoding})'
                                        })
                                        break
                                except:
                                    continue
                            if matched_emails and matched_emails[-1]['id'] == email_id.decode():
                                break
            else:
                payload = email_message.get_payload(decode=True)
                if payload:
                    for encoding in ['utf-8', 'gbk', 'gb2312']:
                        try:
                            text = payload.decode(encoding)
                            if keyword in text:
                                matched_emails.append({
                                    'id': email_id.decode(),
                                    'from': decode_header_value(email_message.get('From', '')),
                                    'subject': subject[:50],
                                    'date': email_message.get('Date', '')[:20],
                                    'match_type': f'正文 ({encoding})'
                                })
                                break
                        except:
                            continue
            
        except Exception as e:
            print(f"  ⚠️  解析邮件 {email_id.decode()} 失败: {e}")
            continue
    
    return matched_emails


def main():
    parser = argparse.ArgumentParser(
        description='搜索中文邮件（测试不同编码方式）',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('keyword', 
                       help='搜索关键词（中文）')
    parser.add_argument('--folder', default='INBOX',
                       help='要搜索的文件夹（默认: INBOX）')
    parser.add_argument('--limit', type=int, default=100,
                       help='限制搜索的邮件数量（默认: 100）')
    parser.add_argument('--method', choices=['imap', 'content', 'all'], default='all',
                       help='搜索方法: imap（IMAP搜索）, content（内容搜索）, all（两者都用）')
    
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
        print(f"🔌 连接到 IMAP 服务器: {config['imap_host']}:{config['imap_port']}")
        imap = IMAP4_SSL(config['imap_host'], config['imap_port'], ssl_context=ssl_context)
        
        # 登录
        imap.login(config['email'], config['email_password'])
        print(f"✅ 登录成功: {config['email']}")
        
        # 选择文件夹
        imap.select(args.folder)
        print(f"📁 当前文件夹: {args.folder}")
        
        keyword = args.keyword
        print(f"\n🔍 搜索关键词: {keyword}")
        print("="*60)
        
        all_matched = []
        
        # 方法1: IMAP 搜索（不同编码）
        if args.method in ['imap', 'all']:
            print("\n【方法1: IMAP 搜索】")
            print("-"*60)
            
            tests = [
                ("主题 (UTF-8)", lambda: search_subject_utf8(imap, keyword)),
                ("主题 (GBK)", lambda: search_subject_gbk(imap, keyword)),
                ("正文 (UTF-8)", lambda: search_body_utf8(imap, keyword)),
                ("正文 (GBK)", lambda: search_body_gbk(imap, keyword)),
                ("主题或正文 (UTF-8)", lambda: search_text_utf8(imap, keyword)),
                ("主题或正文 (GBK)", lambda: search_text_gbk(imap, keyword)),
            ]
            
            for test_name, test_func in tests:
                success, email_ids = test_func()
                if success and email_ids:
                    print(f"✅ {test_name}: 找到 {len(email_ids)} 封邮件")
                    # 预览前3封
                    for email_id in email_ids[:3]:
                        try:
                            status, msg_data = imap.fetch(email_id, '(RFC822)')
                            if status == 'OK':
                                email_message = email.message_from_bytes(msg_data[0][1])
                                email_info = {
                                    'id': email_id.decode(),
                                    'from': decode_header_value(email_message.get('From', '')),
                                    'subject': decode_header_value(email_message.get('Subject', ''))[:50],
                                    'date': email_message.get('Date', '')[:20],
                                    'match_type': test_name
                                }
                                all_matched.append(email_info)
                        except:
                            pass
                else:
                    print(f"  ❌ {test_name}: 未找到")
        
        # 方法2: 内容搜索（下载邮件后搜索）
        if args.method in ['content', 'all']:
            print("\n【方法2: 内容搜索】")
            print("-"*60)
            matched = search_emails_by_content(imap, keyword, args.limit)
            if matched:
                print(f"✅ 内容搜索: 找到 {len(matched)} 封邮件")
                all_matched.extend(matched)
            else:
                print(f"  ❌ 内容搜索: 未找到")
        
        # 显示所有匹配的邮件
        if all_matched:
            print("\n" + "="*60)
            print(f"📧 共找到 {len(all_matched)} 封匹配的邮件")
            print("="*60)
            
            # 去重
            seen_ids = set()
            unique_emails = []
            for email_info in all_matched:
                if email_info['id'] not in seen_ids:
                    seen_ids.add(email_info['id'])
                    unique_emails.append(email_info)
            
            for i, info in enumerate(unique_emails[:20], 1):  # 最多显示20封
                print(f"\n{i}. [{info['id']}] {info['date']}")
                print(f"   从: {info['from']}")
                print(f"   主题: {info['subject']}")
                print(f"   匹配: {info['match_type']}")
            
            if len(unique_emails) > 20:
                print(f"\n... 还有 {len(unique_emails) - 20} 封邮件未显示")
        else:
            print("\n" + "="*60)
            print("❌ 未找到匹配的邮件")
            print("="*60)
        
        imap.logout()
        print("\n✅ 搜索完成！")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
