#!/usr/bin/env python3
"""
Wukong Email - List Emails
===========================

Default JSON output (for Agent parsing), use --table to switch to human-readable table.

Search criteria:
  --days N          Emails from the last N days
  --unread          Unread emails
  --seen            Read emails
  --from EMAIL      Specific sender
  --to EMAIL        Specific recipient
  --subject TEXT    Subject contains text
  --larger N        Larger than N bytes
  --smaller N       Smaller than N bytes
  --flagged         Flagged
  --unflagged       Unflagged

Output format:
  (default)         JSON array, one object per email
  --table           Human-readable table
  --output-uids     Only output UID list (pipe-friendly)

Filter:
  --only-with-attachments  Only show emails with attachments
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
    Create SSL context

    Args:
        ssl_config: SSL configuration dict, containing verify, check_hostname, ciphers

    Returns:
        SSL context object
    """
    if ssl_config is None:
        ssl_config = {}

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    # Set SSL options based on configuration
    context.check_hostname = ssl_config.get('check_hostname', False)
    context.verify_mode = ssl.CERT_NONE if not ssl_config.get('verify', False) else ssl.CERT_REQUIRED

    # Set minimum TLS version
    context.minimum_version = ssl.TLSVersion.TLSv1_2

    # Set cipher suites
    ciphers = ssl_config.get('ciphers', [])
    if ciphers:
        context.set_ciphers(':'.join(ciphers))

    return context


def decode_header_value(value):
    """Decode email header value (=?utf-8?b?...?= format)"""
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
    """Parse attachment count from BODYSTRUCTURE"""
    if not bodystructure:
        return 0
    bs_str = bodystructure.decode('utf-8', errors='ignore') if isinstance(bodystructure, bytes) else str(bodystructure)
    attachment_count = bs_str.lower().count('attachment')
    filename_count = len(re.findall(r'filename\s*=\s*[^",)]+', bs_str, re.IGNORECASE))
    return max(attachment_count, filename_count)


def build_search_criteria(args):
    """Build IMAP SEARCH criteria from command-line arguments"""
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
    """Format file size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def list_emails(config, search_criteria, limit=None, only_with_attachments=False):
    """
    List emails matching the criteria and return email_list.

    Returns:
        list[dict]: Each email {uid, date, from, subject, size, attachments}
    """
    imap_host = config['imap_host']
    imap_port = config['imap_port']
    imap_user = config['email']
    imap_password = config['email_password']

    # Build SSL configuration
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

        # Apply limit
        if limit:
            uids = uids[:limit]

        # Step 2: FETCH (UID + RFC822.SIZE + RFC822.HEADER + BODYSTRUCTURE)
        # Note: When fetching in batch, UID/SIZE return bytes lines, HEADER returns tuples
        uids_str = ','.join(uid.decode() if isinstance(uid, bytes) else str(uid) for uid in uids)
        status, data = imap.fetch(uids_str, '(UID RFC822.SIZE RFC822.HEADER BODYSTRUCTURE)')
        if status != 'OK':
            return []

        # Parse response
        # Response format is mixed:
        #   bytes line: b'2065 (UID 2471 RFC822.SIZE 7264 BODYSTRUCTURE ...)'
        #   tuple line: (b'...BODYSTRUCTURE...', b'email headers...')
        #   bytes line: b')'  (separator)
        email_list = []

        # First pass: extract UID and SIZE from bytes lines, HEADER and BODYSTRUCTURE from tuple lines
        uid_size_map = {}   # seq_num -> {uid, size}
        header_bs_map = {}  # seq_num -> {header, bodystructure}

        i = 0
        current_seq = None
        while i < len(data):
            item = data[i]
            if isinstance(item, bytes):
                # Standalone bytes line: may contain UID/SIZE/BODYSTRUCTURE
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
                # tuple: part[0] contains UID/BODYSTRUCTURE/SIZE, part[1] contains email headers
                for part in item:
                    if not isinstance(part, bytes):
                        continue
                    # Metadata line (contains sequence number, UID, SIZE, BODYSTRUCTURE)
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
                    # Email headers (usually the last part in the tuple)
                    elif current_seq:
                        header_bs_map.setdefault(current_seq, {'header': None, 'bodystructure': None})['header'] = part
            i += 1

        # Second pass: assemble email_list
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

            # Parse email headers
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

            # Attachment count
            bs_data = hb.get('bodystructure')
            if bs_data:
                try:
                    email_data['attachments'] = count_attachments_from_bodystructure(bs_data)
                except Exception:
                    pass

            email_list.append(email_data)

        # Filter for emails with attachments
        if only_with_attachments:
            email_list = [e for e in email_list if e.get('attachments', 0) > 0]

        imap.close()
        imap.logout()
        return email_list

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return []


def print_table(email_list):
    """Print human-readable table"""
    if not email_list:
        print("No emails found matching criteria")
        return
    print(f"{'UID':<10} {'Date/Time':<20} {'From':<30} {'Subject':<40} {'Size':<10} {'Attachments':<5}")
    print("-" * 115)
    for e in email_list:
        date_s = e['date'][:16] if e['date'] else ''
        from_s = (e['from'][:28] + '..') if len(e['from']) > 30 else e['from']
        subj_s = (e['subject'][:38] + '..') if len(e['subject']) > 40 else e['subject']
        size_s = format_size(e['size'])
        att_s = str(e['attachments']) if e['attachments'] > 0 else '-'
        print(f"{e['uid']:<10} {date_s:<20} {from_s:<30} {subj_s:<40} {size_s:<10} {att_s:<5}")
    print("-" * 115)
    print(f"Total: {len(email_list)} emails")


def main():
    parser = argparse.ArgumentParser(description='List emails (advanced filtering)')
    # Search criteria
    parser.add_argument('--days', type=int, help='Emails from the last N days')
    parser.add_argument('--unread', action='store_true', help='Unread emails')
    parser.add_argument('--seen', action='store_true', help='Read emails')
    parser.add_argument('--from', dest='from_sender', type=str, help='Specific sender')
    parser.add_argument('--to', dest='to_recipient', type=str, help='Specific recipient')
    parser.add_argument('--subject', type=str, help='Subject contains text')
    parser.add_argument('--larger', type=int, help='Larger than N bytes')
    parser.add_argument('--smaller', type=int, help='Smaller than N bytes')
    parser.add_argument('--flagged', action='store_true', help='Flagged')
    parser.add_argument('--unflagged', action='store_true', help='Unflagged')
    # Output control
    parser.add_argument('--limit', type=int, help='Maximum display count')
    parser.add_argument('--only-with-attachments', action='store_true', help='Only show emails with attachments')
    parser.add_argument('--table', action='store_true', help='Output in table format (default JSON)')
    parser.add_argument('--output-uids', action='store_true', help='Only output UID list')

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
        # Default JSON output
        print(json.dumps(email_list, ensure_ascii=False))


if __name__ == '__main__':
    main()
