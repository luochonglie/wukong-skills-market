#!/usr/bin/env python3
"""
Wukong Email - Delete Emails Script
====================================
Move emails to the "Deleted/Trash" folder (non-permanent delete, recoverable)

Safety features:
- Only moves to "Deleted/Trash" folder, does not permanently delete
- Supports preview mode (--dry-run)
- Interactive confirmation (shows matched email count)
- Supports friendly folder names
"""

from imaplib import IMAP4_SSL
import email
from email.header import decode_header
import ssl
import argparse
import sys
from typing import List, Dict, Tuple
import json

# Import config loader
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import load_config
from imap_utf7 import get_imap_folder_name


def create_ssl_context(ssl_config: dict = None):
    """
    Create SSL context

    Args:
        ssl_config: SSL config dict, containing verify, check_hostname, ciphers

    Returns:
        SSL context object
    """
    if ssl_config is None:
        ssl_config = {}

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    # Set SSL options based on config
    context.check_hostname = ssl_config.get('check_hostname', False)
    context.verify_mode = ssl.CERT_NONE if not ssl_config.get('verify', False) else ssl.CERT_REQUIRED

    # Set minimum TLS version
    context.minimum_version = ssl.TLSVersion.TLSv1_2

    # Set cipher suites
    ciphers = ssl_config.get('ciphers', [])
    if ciphers:
        context.set_ciphers(':'.join(ciphers))
    else:
        # Default cipher suites
        context.set_ciphers(
            'ECDHE-RSA-AES256-GCM-SHA384:'
            'ECDHE-ECDSA-AES256-GCM-SHA384:'
            'AES256-GCM-SHA384:'
            'AES256-SHA256'
        )

    return context


def decode_header_value(header_value: str) -> str:
    """
    Decode email header

    Args:
        header_value: Raw email header

    Returns:
        str: Decoded email header
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

    # Clean up extra domain suffixes in sender address
    if '@' in result and result.count('@') > 1:
        parts = result.rsplit('@', 1)
        if '>' in parts[0]:
            result = parts[0]
        else:
            result = result.replace('@' + parts[-1], '')

    return result


def find_deleted_folder(imap: IMAP4_SSL, folder_name: str = None) -> str:
    """
    Find the "Deleted/Trash" folder

    Args:
        imap: IMAP connection object
        folder_name: Configured folder name (friendly name or encoded name)

    Returns:
        str: IMAP-encoded folder name
    """
    # List all folders
    status, folders = imap.list()
    if status != 'OK':
        print("[ERROR] Unable to list folders")
        return None

    folder_list = []
    for folder in folders:
        # Parse folder name: folder is a byte string, format: b'(\\HasNoChildren) "/" "INBOX"'
        parts = folder.decode().split('"')
        if len(parts) >= 3:
            folder_name_decoded = parts[-2] if parts[-2] else parts[1]
            folder_list.append(folder_name_decoded)

    # Priority 1: Exact match of configured folder name
    if folder_name:
        # Try friendly name
        encoded = get_imap_folder_name(folder_name)
        if encoded in folder_list:
            return encoded
        # Direct match
        if folder_name in folder_list:
            return folder_name

    # Priority 2: Match common deleted folder names
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

    # Priority 3: Fuzzy match (via folder name)
    for folder in folder_list:
        folder_lower = folder.lower()
        if 'deleted' in folder_lower or 'trash' in folder_lower or '删除' in folder:
            return folder

    print("[WARN] Deleted/Trash folder not found, using default 'Trash'")
    return 'Trash'


def search_emails(imap: IMAP4_SSL, search_criteria: str, limit: int = None) -> List[str]:
    """
    Search emails

    Args:
        imap: IMAP connection object
        search_criteria: IMAP search criteria
        limit: Limit number of results

    Returns:
        List[str]: Email ID list
    """
    status, messages = imap.search(None, search_criteria)
    if status != 'OK':
        print(f"[ERROR] Search failed: {status}")
        return []

    email_ids = messages[0].split()

    # IMAP returns IDs sorted ascending, newest at the end
    if limit:
        email_ids = email_ids[-limit:]  # Take the most recent N emails

    return email_ids


def preview_emails(imap: IMAP4_SSL, email_ids: List[str], max_preview: int = 10) -> List[Dict]:
    """
    Preview emails (show only the first few)

    Args:
        imap: IMAP connection object
        email_ids: Email ID list
        max_preview: Maximum number to preview

    Returns:
        List[Dict]: Email info list
    """
    preview_list = []

    # Only show the most recent few (email IDs are ascending, larger at the end)
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
            print(f"[WARN] Failed to parse email {email_id}: {e}")

    return preview_list


def move_to_deleted_folder(
    imap: IMAP4_SSL,
    email_ids: List[str],
    deleted_folder: str,
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    Move emails to the "Deleted/Trash" folder

    Args:
        imap: IMAP connection object
        email_ids: Email ID list
        deleted_folder: Target folder (IMAP-encoded name)
        dry_run: Whether in preview/dry-run mode

    Returns:
        Tuple[int, int]: (success count, failure count)
    """
    success_count = 0
    fail_count = 0

    print(f"\n{'='*60}", file=sys.stderr)
    if dry_run:
        print(f"[INFO] [Preview mode] Will move {len(email_ids)} emails to '{deleted_folder}'", file=sys.stderr)
    else:
        print(f"[INFO] Moving {len(email_ids)} emails to '{deleted_folder}'...", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    for i, email_id in enumerate(email_ids, 1):
        try:
            if not dry_run:
                # 1. Copy to Deleted/Trash folder
                status = imap.copy(email_id, deleted_folder)
                if status[0] != 'OK':
                    print(f"[WARN] [{i}/{len(email_ids)}] Failed to copy email {email_id.decode()}: {status}", file=sys.stderr)
                    fail_count += 1
                    continue

                # 2. Mark as deleted (remove from original folder)
                status = imap.store(email_id, '+FLAGS', '\\\\Deleted')
                if status[0] != 'OK':
                    print(f"[WARN] [{i}/{len(email_ids)}] Failed to mark as deleted {email_id.decode()}: {status}", file=sys.stderr)
                    fail_count += 1
                    continue
            else:
                # Preview mode
                print(f"  [{i}/{len(email_ids)}] Will move email {email_id.decode()}", file=sys.stderr)

            success_count += 1

        except Exception as e:
            print(f"[WARN] [{i}/{len(email_ids)}] Exception processing email {email_id.decode()}: {e}", file=sys.stderr)
            fail_count += 1

    if not dry_run:
        # 3. Execute deletion (remove marked emails from current folder)
        try:
            imap.expunge()
            print(f"[OK] Successfully moved {success_count} emails to '{deleted_folder}'", file=sys.stderr)
        except Exception as e:
            print(f"[WARN] Expunge failed: {e}", file=sys.stderr)
    else:
        print(f"[INFO] [Preview mode] Will move {success_count} emails (not actually executed)", file=sys.stderr)

    return success_count, fail_count


def main():
    parser = argparse.ArgumentParser(
        description='Move emails to the "Deleted/Trash" folder (non-permanent delete)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Preview emails from the last 10 days (no deletion)
  python delete_emails.py --search "SINCE 13-May-2026" --dry-run

  # Delete emails from a specific sender
  python delete_emails.py --search 'FROM "spam@example.com"'

  # Delete emails containing a specific keyword
  python delete_emails.py --search 'SUBJECT "advertisement"'

  # Delete unread emails
  python delete_emails.py --search "UNSEEN" --dry-run

  # Combined search: last 7 days + specific sender
  python delete_emails.py --search 'SINCE 16-May-2026 FROM "newsletter@example.com"'
        '''
    )

    parser.add_argument('--search', required=True,
                       help='IMAP search criteria, e.g.: SINCE 13-May-2026, FROM "user@example.com", SUBJECT "keyword", UNSEEN')
    parser.add_argument('--folder', default='INBOX',
                       help='Folder to search (default: INBOX)')
    parser.add_argument('--deleted-folder',
                       help='Deleted/Trash folder name (friendly name, e.g. "Deleted Items")')
    parser.add_argument('--limit', type=int,
                       help='Limit number of emails to process (most recent N)')
    parser.add_argument('--preview', type=int, default=10,
                       help='Number of emails to preview (default: 10)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview mode: show matched emails without deleting')
    parser.add_argument('--yes', action='store_true',
                       help='Skip confirmation prompt (use with caution)')

    args = parser.parse_args()

    # Load config
    config = load_config()

    if not config.get('imap_host'):
        print("[ERROR] IMAP config not found, please check ~/.wukong-email/.env file")
        sys.exit(1)

    # Create SSL context
    ssl_context = create_ssl_context(config.get('imap_ssl', {}))

    try:
        # Connect to IMAP server
        imap = IMAP4_SSL(config['imap_host'], config['imap_port'], ssl_context=ssl_context)

        # Login
        imap.login(config['email'], config['email_password'])

        # Select folder
        imap.select(args.folder)

        # Search emails
        email_ids = search_emails(imap, args.search, args.limit)

        if not email_ids:
            imap.logout()
            print(json.dumps({'success': True, 'total': 0, 'moved': 0, 'failed': 0, 'search': args.search, 'dry_run': args.dry_run}, ensure_ascii=False))
            return

        # Find Deleted/Trash folder
        deleted_folder = find_deleted_folder(imap, args.deleted_folder)

        # Confirm execution
        if not args.yes and not args.dry_run:
            print(f"[WARN] About to move {len(email_ids)} emails to '{deleted_folder}', recoverable after move", file=sys.stderr)
            confirm = input("Confirm execution? (yes/no): ").strip().lower()
            if confirm not in ['yes', 'y']:
                imap.logout()
                print(json.dumps({'success': False, 'total': len(email_ids), 'moved': 0, 'failed': 0, 'cancelled': True, 'search': args.search}, ensure_ascii=False))
                return

        # Execute move
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
