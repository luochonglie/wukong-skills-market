#!/usr/bin/env python3
"""
Wukong Email - 标记邮件已读
============================

支持多种方式标记邮件为已读：
  --before DATE    标记指定日期之前的邮件
  --from EMAIL     标记特定发件人的邮件
  --subject TEXT   标记主题包含文本的邮件
  --uids UID1,UID2 标记指定UID的邮件
  --days N         标记最近N天的邮件

默认输出 JSON（供 Agent 解析），--table 切换人类可读表格。
"""

import imaplib
import argparse
import json
import sys
import ssl
from pathlib import Path

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


def mark_read(config, search_criteria=None, uids=None, batch_size=200):
    """
    标记邮件为已读

    Args:
        config: 配置字典
        search_criteria: IMAP 搜索条件（与 uids 二选一）
        uids: 指定 UID 列表（与 search_criteria 二选一）
        batch_size: 批量标记每批数量

    Returns:
        dict: {success: int, fail: int, total: int}
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

        # 获取要标记的 UID
        if uids:
            # 指定 UID
            target_uids = [u.strip() for u in uids.split(',')]
        elif search_criteria:
            # 搜索条件
            status, messages = imap.search(None, search_criteria.encode('utf-8'))
            if status != 'OK':
                return {'success': 0, 'fail': 0, 'total': 0}
            target_uids = [uid.decode() if isinstance(uid, bytes) else str(uid)
                          for uid in messages[0].split()]
            if not target_uids or target_uids == ['']:
                return {'success': 0, 'fail': 0, 'total': 0}
        else:
            print("错误：必须指定搜索条件或 UID", file=sys.stderr)
            return {'success': 0, 'fail': 0, 'total': 0}

        total = len(target_uids)

        # 分批标记已读
        success = 0
        fail = 0
        for i in range(0, total, batch_size):
            batch = target_uids[i:i + batch_size]
            uids_str = ','.join(batch)
            status, _ = imap.store(uids_str, '+FLAGS', '\\Seen')
            if status == 'OK':
                success += len(batch)
            else:
                fail += len(batch)

        imap.close()
        imap.logout()

        return {'success': success, 'fail': fail, 'total': total}

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return {'success': 0, 'fail': 0, 'total': 0}


def build_search_criteria(args):
    """根据命令行参数构建 IMAP SEARCH 条件"""
    criteria = []

    if args.before:
        criteria.append(f'BEFORE "{args.before}"')

    if args.days:
        import datetime
        since_date = (datetime.date.today() - datetime.timedelta(days=args.days)).strftime("%d-%b-%Y")
        criteria.append(f'SINCE "{since_date}"')

    if args.from_sender:
        criteria.append(f'FROM "{args.from_sender}"')

    if args.subject:
        criteria.append(f'SUBJECT "{args.subject}"')

    if args.unread:
        criteria.append('UNSEEN')

    if not criteria:
        criteria.append('ALL')

    return ' '.join(criteria)


def main():
    parser = argparse.ArgumentParser(description='标记邮件已读')

    # 搜索条件
    parser.add_argument('--before', type=str,
                       help='标记此日期之前的邮件（格式: DD-Mon-YYYY，如 01-May-2026）')
    parser.add_argument('--days', type=int,
                       help='标记最近 N 天的邮件')
    parser.add_argument('--from', dest='from_sender', type=str,
                       help='标记特定发件人的邮件')
    parser.add_argument('--subject', type=str,
                       help='标记主题包含文本的邮件')
    parser.add_argument('--unread', action='store_true',
                       help='只标记未读邮件（推荐，避免重复标记）')
    parser.add_argument('--uids', type=str,
                       help='标记指定UID的邮件（逗号分隔）')

    # 输出控制
    parser.add_argument('--dry-run', action='store_true',
                       help='只预览，不实际标记')

    args = parser.parse_args()

    if not any([args.before, args.days, args.from_sender, args.subject, args.unread, args.uids]):
        print("错误：必须指定至少一个条件（--before/--days/--from/--subject/--unread/--uids）", file=sys.stderr)
        sys.exit(1)

    config = load_config()

    if args.dry_run:
        # 预览：先搜索看有多少封
        if args.uids:
            count = len(args.uids.split(','))
        else:
            search_criteria = build_search_criteria(args)
            try:
                if config['imap_port'] == 993:
                    imap = imaplib.IMAP4_SSL(config['imap_host'], config['imap_port'])
                else:
                    imap = imaplib.IMAP4(config['imap_host'], config['imap_port'])
                imap.login(config['email'], config['email_password'])
                imap.select('INBOX')
                status, messages = imap.search(None, search_criteria.encode('utf-8'))
                uids = messages[0].split()
                count = len(uids)
                imap.close()
                imap.logout()
            except Exception as e:
                print(f"错误: {e}", file=sys.stderr)
                sys.exit(1)

        result = {'action': 'preview', 'count': count, 'criteria': search_criteria if not args.uids else f'uids={args.uids}'}
        print(json.dumps(result, ensure_ascii=False))
    else:
        # 执行标记
        if args.uids:
            result = mark_read(config, uids=args.uids)
        else:
            search_criteria = build_search_criteria(args)
            result = mark_read(config, search_criteria=search_criteria)

        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
