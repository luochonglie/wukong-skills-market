#!/usr/bin/env python3
"""
Wukong Email - 列出邮件
========================

默认输出 JSON 格式（供 Agent 解析），使用 --table 切换为人类可读表格。

搜索条件:
  --days N          最近 N 天的邮件
  --unread          未读邮件
  --seen            已读邮件
  --from EMAIL      特定发件人
  --to EMAIL        特定收件人
  --subject TEXT    主题包含文本
  --larger N        大于 N 字节
  --smaller N       小于 N 字节
  --flagged         已标记
  --unflagged       未标记

输出格式:
  (默认)            JSON 数组，每封邮件一个对象
  --table           人类可读表格
  --output-uids     只输出 UID 列表（管道友好）

过滤:
  --only-with-attachments  只显示有附件的邮件
"""

import imaplib
import email
import email.utils
import datetime
import argparse
import json
import sys
import os
import re
import ssl
from pathlib import Path
from email.header import decode_header

scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from config_loader import load_config


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
    
    return context


def decode_header_value(value):
    """解码邮件头值（=?utf-8?b?...?= 格式）"""
    if value is None:
        return ''
    decoded_parts = []
    for part, encoding in decode_header(value):
        if isinstance(part, bytes):
            try:
                decoded_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
            except (LookupError, UnicodeDecodeError):
                decoded_parts.append(part.decode('utf-8', errors='ignore'))
        else:
            decoded_parts.append(str(part))
    return ''.join(decoded_parts)


def count_attachments_from_bodystructure(bodystructure):
    """从 BODYSTRUCTURE 解析附件数量"""
    if not bodystructure:
        return 0
    bs_str = bodystructure.decode('utf-8', errors='ignore') if isinstance(bodystructure, bytes) else str(bodystructure)
    attachment_count = bs_str.lower().count('attachment')
    filename_count = len(re.findall(r'filename\s*=\s*[^",)]+', bs_str, re.IGNORECASE))
    return max(attachment_count, filename_count)


def build_search_criteria(args):
    """根据命令行参数构建 IMAP SEARCH 条件"""
    criteria = []
    if args.days:
        since_date = (datetime.date.today() - datetime.timedelta(days=args.days)).strftime("%d-%b-%Y")
        criteria.append(f'SINCE "{since_date}"')
    if args.unread:
        criteria.append('UNSEEN')
    elif args.seen:
        criteria.append('SEEN')
    if args.from_sender:
        criteria.append(f'FROM "{args.from_sender}"')
    if args.to_recipient:
        criteria.append(f'TO "{args.to_recipient}"')
    if args.subject:
        criteria.append(f'SUBJECT "{args.subject}"')
    if args.larger:
        criteria.append(f'LARGER {args.larger}')
    if args.smaller:
        criteria.append(f'SMALLER {args.smaller}')
    if args.flagged:
        criteria.append('FLAGGED')
    elif args.unflagged:
        criteria.append('UNFLAGGED')
    if not criteria:
        criteria.append('ALL')
    return ' '.join(criteria)


def format_size(size_bytes):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def list_emails(config, search_criteria, limit=None, only_with_attachments=False):
    """
    列出符合条件的邮件，返回 email_list。

    Returns:
        list[dict]: 每封邮件 {uid, date, from, subject, size, attachments}
    """
    imap_host = config['imap_host']
    imap_port = config['imap_port']
    imap_user = config['email']
    imap_password = config['email_password']

    # 构建SSL配置
    ssl_config = {
        'verify': config.get('imap_ssl_verify', False),
        'check_hostname': config.get('imap_ssl_verify', False),
        'ciphers': config.get('imap_ssl_ciphers', '').split(':') if config.get('imap_ssl_ciphers') else []
    }

    try:
        if imap_port == 993:
            context = create_ssl_context(ssl_config)
            imap = imaplib.IMAP4_SSL(imap_host, imap_port, ssl_context=context)
        else:
            imap = imaplib.IMAP4(imap_host, imap_port)

        imap.login(imap_user, imap_password)
        imap.select('INBOX')

        # Step 1: SEARCH
        status, messages = imap.search(None, search_criteria.encode('utf-8'))
        if status != 'OK':
            return []

        uids = messages[0].split()
        if not uids:
            return []

        # 限制数量
        if limit:
            uids = uids[:limit]

        # Step 2: FETCH（UID + RFC822.SIZE + RFC822.HEADER + BODYSTRUCTURE）
        # 注意：批量获取时，UID/SIZE 返回 bytes 行，HEADER 返回 tuple
        uids_str = ','.join(uid.decode() if isinstance(uid, bytes) else str(uid) for uid in uids)
        status, data = imap.fetch(uids_str, '(UID RFC822.SIZE RFC822.HEADER BODYSTRUCTURE)')
        if status != 'OK':
            return []

        # 解析响应
        # 响应格式混合：
        #   bytes 行: b'2065 (UID 2471 RFC822.SIZE 7264 BODYSTRUCTURE ...)'
        #   tuple 行: (b'...BODYSTRUCTURE...', b'邮件头...')
        #   bytes 行: b')'  (分隔符)
        email_list = []

        # 第一遍：从 bytes 行提取 UID 和 SIZE，从 tuple 行提取 HEADER 和 BODYSTRUCTURE
        uid_size_map = {}   # seq_num -> {uid, size}
        header_bs_map = {}  # seq_num -> {header, bodystructure}

        i = 0
        current_seq = None
        while i < len(data):
            item = data[i]
            if isinstance(item, bytes):
                # 独立 bytes 行：可能包含 UID/SIZE/BODYSTRUCTURE
                seq_match = re.search(rb'^(\d+)\s+\(', item)
                if seq_match:
                    current_seq = seq_match.group(1).decode()
                    if current_seq not in uid_size_map:
                        uid_size_map[current_seq] = {'uid': '', 'size': 0}
                    uid_match = re.search(rb'UID\s+(\d+)', item)
                    if uid_match:
                        uid_size_map[current_seq]['uid'] = uid_match.group(1).decode()
                    size_match = re.search(rb'RFC822\.SIZE\s+(\d+)', item)
                    if size_match:
                        uid_size_map[current_seq]['size'] = int(size_match.group(1))
                    if b'BODYSTRUCTURE' in item:
                        header_bs_map.setdefault(current_seq, {'header': None, 'bodystructure': None})['bodystructure'] = item
            elif isinstance(item, tuple):
                # tuple: part[0] 包含 UID/BODYSTRUCTURE/SIZE，part[1] 包含邮件头
                for part in item:
                    if not isinstance(part, bytes):
                        continue
                    # 元数据行（包含序列号、UID、SIZE、BODYSTRUCTURE）
                    seq_match = re.search(rb'^(\d+)\s+\(', part)
                    if seq_match:
                        current_seq = seq_match.group(1).decode()
                        uid_size_map.setdefault(current_seq, {'uid': '', 'size': 0})
                        uid_match = re.search(rb'UID\s+(\d+)', part)
                        if uid_match:
                            uid_size_map[current_seq]['uid'] = uid_match.group(1).decode()
                        size_match = re.search(rb'RFC822\.SIZE\s+(\d+)', part)
                        if size_match:
                            uid_size_map[current_seq]['size'] = int(size_match.group(1))
                        if b'BODYSTRUCTURE' in part:
                            header_bs_map.setdefault(current_seq, {'header': None, 'bodystructure': None})['bodystructure'] = part
                    # 邮件头（通常是 tuple 的最后一个 part）
                    elif current_seq:
                        header_bs_map.setdefault(current_seq, {'header': None, 'bodystructure': None})['header'] = part
            i += 1

        # 第二遍：组装 email_list
        for seq_num in sorted(uid_size_map.keys(), key=lambda x: int(x)):
            info = uid_size_map[seq_num]
            email_data = {
                'uid': info['uid'],
                'date': '',
                'from': '',
                'subject': '',
                'size': info['size'],
                'attachments': 0,
            }

            hb = header_bs_map.get(seq_num, {})

            # 解析邮件头
            header_data = hb.get('header')
            if header_data:
                try:
                    msg = email.message_from_bytes(header_data)
                    date_str = msg.get('Date', '')
                    if date_str:
                        email_data['date'] = email.utils.parsedate_to_datetime(date_str).strftime("%Y-%m-%d %H:%M:%S")
                    from_str = msg.get('From', '')
                    if from_str:
                        email_data['from'] = decode_header_value(from_str)
                    subject_str = msg.get('Subject', '')
                    if subject_str:
                        email_data['subject'] = decode_header_value(subject_str)
                except Exception:
                    pass

            # 附件数量
            bs_data = hb.get('bodystructure')
            if bs_data:
                try:
                    email_data['attachments'] = count_attachments_from_bodystructure(bs_data)
                except Exception:
                    pass

            email_list.append(email_data)

        # 过滤有附件的
        if only_with_attachments:
            email_list = [e for e in email_list if e.get('attachments', 0) > 0]

        imap.close()
        imap.logout()
        return email_list

    except Exception as e:
        print(f"✗ 错误: {e}", file=sys.stderr)
        return []


def print_table(email_list):
    """打印人类可读表格"""
    if not email_list:
        print("没有找到符合条件的邮件")
        return
    print(f"{'UID':<10} {'时间':<20} {'发件人':<30} {'主题':<40} {'大小':<10} {'附件':<5}")
    print("-" * 115)
    for e in email_list:
        date_s = e['date'][:16] if e['date'] else ''
        from_s = (e['from'][:28] + '..') if len(e['from']) > 30 else e['from']
        subj_s = (e['subject'][:38] + '..') if len(e['subject']) > 40 else e['subject']
        size_s = format_size(e['size'])
        att_s = str(e['attachments']) if e['attachments'] > 0 else '-'
        print(f"{e['uid']:<10} {date_s:<20} {from_s:<30} {subj_s:<40} {size_s:<10} {att_s:<5}")
    print("-" * 115)
    print(f"总计: {len(email_list)} 封邮件")


def main():
    parser = argparse.ArgumentParser(description='列出邮件（高级过滤）')
    # 搜索条件
    parser.add_argument('--days', type=int, help='最近 N 天的邮件')
    parser.add_argument('--unread', action='store_true', help='未读邮件')
    parser.add_argument('--seen', action='store_true', help='已读邮件')
    parser.add_argument('--from', dest='from_sender', type=str, help='筛选发件人')
    parser.add_argument('--to', dest='to_recipient', type=str, help='筛选收件人')
    parser.add_argument('--subject', type=str, help='筛选主题')
    parser.add_argument('--larger', type=int, help='大于 N 字节')
    parser.add_argument('--smaller', type=int, help='小于 N 字节')
    parser.add_argument('--flagged', action='store_true', help='已标记')
    parser.add_argument('--unflagged', action='store_true', help='未标记')
    # 输出控制
    parser.add_argument('--limit', type=int, help='最多显示数量')
    parser.add_argument('--only-with-attachments', action='store_true', help='只显示有附件的邮件')
    parser.add_argument('--table', action='store_true', help='以表格格式输出（默认 JSON）')
    parser.add_argument('--output-uids', action='store_true', help='只输出 UID 列表')

    args = parser.parse_args()
    search_criteria = build_search_criteria(args)
    config = load_config()

    email_list = list_emails(
        config=config,
        search_criteria=search_criteria,
        limit=args.limit,
        only_with_attachments=args.only_with_attachments,
    )

    if args.output_uids:
        for e in email_list:
            print(e['uid'])
    elif args.table:
        print_table(email_list)
    else:
        # 默认 JSON 输出
        print(json.dumps(email_list, ensure_ascii=False))


if __name__ == '__main__':
    main()
