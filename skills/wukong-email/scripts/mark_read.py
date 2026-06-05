#!/usr/bin/env python3
"""
Wukong Email - Mark Emails as Read
===================================

Mark emails as read using various criteria:
  --before DATE    Mark emails before the specified date
  --from EMAIL     Mark emails from a specific sender
  --subject TEXT   Mark emails whose subject contains text
  --uids UID1,UID2 Mark emails with specified UIDs
  --days N         Mark emails from the last N days

Default output is JSON (for Agent parsing).
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
    """Create SSL context with the given configuration."""
    if ssl_config is None:
        ssl_config = {}

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = ssl_config.get('check_hostname', False)
    context.verify_mode = ssl.CERT_NONE if not ssl_config.get('verify', False) else ssl.CERT_REQUIRED
    context.minimum_version = ssl.TLSVersion.TLSv1_2

    ciphers = ssl_config.get('ciphers', [])
    if ciphers:
        context.set_ciphers(':'.join(ciphers))

    return context


def mark_read(config, search_criteria=None, uids=None, batch_size=200):
    """
    Mark emails as read.

    Args:
        config: Configuration dict
        search_criteria: IMAP search criteria (mutually exclusive with uids)
        uids: Comma-separated UID list (mutually exclusive with search_criteria)
        batch_size: Number of emails per batch

    Returns:
        dict: {success: int, fail: int, total: int}
    """
    imap_host = config['imap_host']
    imap_port = config['imap_port']
    imap_user = config['email']
    imap_password = config['email_password']

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

        if uids:
            status, messages = imap.uid('SEARCH', None, 'UID', uids.replace(' ', ''))
            if status != 'OK':
                return {'success': 0, 'fail': 0, 'total': 0}
            target_uids = [uid.decode() if isinstance(uid, bytes) else str(uid)
                          for uid in messages[0].split()]
            if not target_uids or target_uids == ['']:
                return {'success': 0, 'fail': 0, 'total': 0}
        elif search_criteria:
            status, messages = imap.uid('SEARCH', None, search_criteria.encode('utf-8'))
            if status != 'OK':
                return {'success': 0, 'fail': 0, 'total': 0}
            target_uids = [uid.decode() if isinstance(uid, bytes) else str(uid)
                          for uid in messages[0].split()]
            if not target_uids or target_uids == ['']:
                return {'success': 0, 'fail': 0, 'total': 0}
        else:
            print("Error: search criteria or UIDs required", file=sys.stderr)
            return {'success': 0, 'fail': 0, 'total': 0}

        total = len(target_uids)

        success = 0
        fail = 0
        for i in range(0, total, batch_size):
            batch = target_uids[i:i + batch_size]
            uids_str = ','.join(batch)
            status, _ = imap.uid('STORE', uids_str, '+FLAGS', '\\Seen')
            if status == 'OK':
                success += len(batch)
            else:
                fail += len(batch)

        imap.close()
        imap.logout()

        return {'success': success, 'fail': fail, 'total': total}

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return {'success': 0, 'fail': 0, 'total': 0}


def build_search_criteria(args):
    """Build IMAP SEARCH criteria from command-line arguments."""
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
    parser = argparse.ArgumentParser(description='Mark emails as read')

    parser.add_argument('--before', type=str,
                       help='Mark emails before this date (format: DD-Mon-YYYY, e.g. 01-May-2026)')
    parser.add_argument('--days', type=int,
                       help='Mark emails from the last N days')
    parser.add_argument('--from', dest='from_sender', type=str,
                       help='Mark emails from a specific sender')
    parser.add_argument('--subject', type=str,
                       help='Mark emails whose subject contains text')
    parser.add_argument('--unread', action='store_true',
                       help='Only mark unread emails (recommended)')
    parser.add_argument('--uids', type=str,
                       help='Mark emails with specified UIDs (comma-separated)')

    parser.add_argument('--dry-run', action='store_true',
                       help='Preview only, do not mark')

    args = parser.parse_args()

    if not any([args.before, args.days, args.from_sender, args.subject, args.unread, args.uids]):
        print("Error: at least one condition required (--before/--days/--from/--subject/--unread/--uids)", file=sys.stderr)
        sys.exit(1)

    config = load_config()

    if args.dry_run:
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
                status, messages = imap.uid('SEARCH', None, search_criteria.encode('utf-8'))
                uids = messages[0].split()
                count = len(uids)
                imap.close()
                imap.logout()
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)

        result = {'action': 'preview', 'count': count, 'criteria': search_criteria if not args.uids else f'uids={args.uids}'}
        print(json.dumps(result, ensure_ascii=False))
    else:
        if args.uids:
            result = mark_read(config, uids=args.uids)
        else:
            search_criteria = build_search_criteria(args)
            result = mark_read(config, search_criteria=search_criteria)

        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
