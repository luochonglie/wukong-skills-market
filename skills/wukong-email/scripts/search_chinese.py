#!/usr/bin/env python3
"""
Wukong Email - Chinese search test script
==========================================
Test different encoding methods for searching Chinese email subjects and bodies
"""

from imaplib import IMAP4_SSL
import email
from email.header import decode_header
import ssl
import argparse
import sys
from typing import List, Dict, Tuple

# Import config loader
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import load_config
from imap_utf7 import get_imap_folder_name


def create_ssl_context(ssl_config: dict = None):
    """Create SSL context"""
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
    """Decode email header"""
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
    Search emails using specified charset

    Args:
        imap: IMAP connection object
        charset: Charset (UTF-8, GBK, etc.)
        search_criteria: Search criteria

    Returns:
        (success, list of email IDs)
    """
    try:
        # Encode to specified charset
        encoded_criteria = search_criteria.encode(charset)
        status, messages = imap.search(f'CHARSET {charset}', encoded_criteria)
        if status == 'OK':
            email_ids = messages[0].split()
            return True, email_ids
        else:
            return False, []
    except Exception as e:
        print(f"  [ERROR] {charset} encoding failed: {e}")
        return False, []


def search_subject_utf8(imap: IMAP4_SSL, keyword: str) -> Tuple[bool, List[str]]:
    """Search subject using UTF-8 encoding"""
    criteria = f'SUBJECT "{keyword}"'
    return search_with_charset(imap, 'UTF-8', criteria)


def search_subject_gbk(imap: IMAP4_SSL, keyword: str) -> Tuple[bool, List[str]]:
    """Search subject using GBK encoding"""
    criteria = f'SUBJECT "{keyword}"'
    return search_with_charset(imap, 'GBK', criteria)


def search_body_utf8(imap: IMAP4_SSL, keyword: str) -> Tuple[bool, List[str]]:
    """Search body using UTF-8 encoding"""
    criteria = f'BODY "{keyword}"'
    return search_with_charset(imap, 'UTF-8', criteria)


def search_body_gbk(imap: IMAP4_SSL, keyword: str) -> Tuple[bool, List[str]]:
    """Search body using GBK encoding"""
    criteria = f'BODY "{keyword}"'
    return search_with_charset(imap, 'GBK', criteria)


def search_text_utf8(imap: IMAP4_SSL, keyword: str) -> Tuple[bool, List[str]]:
    """Search subject or body using UTF-8 encoding"""
    criteria = f'TEXT "{keyword}"'
    return search_with_charset(imap, 'UTF-8', criteria)


def search_text_gbk(imap: IMAP4_SSL, keyword: str) -> Tuple[bool, List[str]]:
    """Search subject or body using GBK encoding"""
    criteria = f'TEXT "{keyword}"'
    return search_with_charset(imap, 'GBK', criteria)


def search_emails_by_content(imap: IMAP4_SSL, keyword: str, limit: int = None) -> List[Dict]:
    """
    Search by email content (download emails then search)

    Args:
        imap: IMAP connection object
        keyword: Search keyword
        limit: Limit number of emails to search

    Returns:
        List of matched emails
    """
    matched_emails = []

    # Get the most recent emails first
    status, messages = imap.search(None, 'ALL')
    if status != 'OK':
        return matched_emails

    email_ids = messages[0].split()
    if limit:
        email_ids = email_ids[-limit:]

    print(f"[INFO] Searching content of {len(email_ids)} emails...")

    for i, email_id in enumerate(email_ids, 1):
        try:
            # Fetch email
            status, msg_data = imap.fetch(email_id, '(RFC822)')
            if status != 'OK':
                continue

            email_body = msg_data[0][1]
            email_message = email.message_from_bytes(email_body)

            # Check subject
            subject = decode_header_value(email_message.get('Subject', ''))
            if keyword in subject:
                matched_emails.append({
                    'id': email_id.decode(),
                    'from': decode_header_value(email_message.get('From', '')),
                    'subject': subject[:50],
                    'date': email_message.get('Date', '')[:20],
                    'match_type': 'Subject'
                })
                continue

            # Check body
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    if content_type == 'text/plain' or content_type == 'text/html':
                        payload = part.get_payload(decode=True)
                        if payload:
                            # Try multiple encodings
                            for encoding in ['utf-8', 'gbk', 'gb2312']:
                                try:
                                    text = payload.decode(encoding)
                                    if keyword in text:
                                        matched_emails.append({
                                            'id': email_id.decode(),
                                            'from': decode_header_value(email_message.get('From', '')),
                                            'subject': subject[:50],
                                            'date': email_message.get('Date', '')[:20],
                                            'match_type': f'Body ({encoding})'
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
                                    'match_type': f'Body ({encoding})'
                                })
                                break
                        except:
                            continue

        except Exception as e:
            print(f"  [WARN] Failed to parse email {email_id.decode()}: {e}")
            continue

    return matched_emails


def main():
    parser = argparse.ArgumentParser(
        description='Search Chinese emails (test different encoding methods)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('keyword',
                       help='Search keyword (Chinese)')
    parser.add_argument('--folder', default='INBOX',
                       help='Folder to search (default: INBOX)')
    parser.add_argument('--limit', type=int, default=100,
                       help='Limit number of emails to search (default: 100)')
    parser.add_argument('--method', choices=['imap', 'content', 'all'], default='all',
                       help='Search method: imap (IMAP search), content (content search), all (both)')

    args = parser.parse_args()

    # Load config
    config = load_config()

    if not config.get('imap_host'):
        print("[ERROR] IMAP configuration not found, please check ~/.wukong-email/.env file")
        sys.exit(1)

    # Create SSL context
    ssl_context = create_ssl_context(config.get('imap_ssl', {}))

    try:
        # Connect to IMAP server
        print(f"[INFO] Connecting to IMAP server: {config['imap_host']}:{config['imap_port']}")
        imap = IMAP4_SSL(config['imap_host'], config['imap_port'], ssl_context=ssl_context)

        # Login
        imap.login(config['email'], config['email_password'])
        print(f"[OK] Login successful: {config['email']}")

        # Select folder
        imap.select(args.folder)
        print(f"[INFO] Current folder: {args.folder}")

        keyword = args.keyword
        print(f"\n[INFO] Search keyword: {keyword}")
        print("="*60)

        all_matched = []

        # Method 1: IMAP search (different encodings)
        if args.method in ['imap', 'all']:
            print("\n[Method 1: IMAP search]")
            print("-"*60)

            tests = [
                ("Subject (UTF-8)", lambda: search_subject_utf8(imap, keyword)),
                ("Subject (GBK)", lambda: search_subject_gbk(imap, keyword)),
                ("Body (UTF-8)", lambda: search_body_utf8(imap, keyword)),
                ("Body (GBK)", lambda: search_body_gbk(imap, keyword)),
                ("Subject or Body (UTF-8)", lambda: search_text_utf8(imap, keyword)),
                ("Subject or Body (GBK)", lambda: search_text_gbk(imap, keyword)),
            ]

            for test_name, test_func in tests:
                success, email_ids = test_func()
                if success and email_ids:
                    print(f"[OK] {test_name}: Found {len(email_ids)} emails")
                    # Preview first 3
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
                    print(f"  [WARN] {test_name}: Not found")

        # Method 2: Content search (download emails then search)
        if args.method in ['content', 'all']:
            print("\n[Method 2: Content search]")
            print("-"*60)
            matched = search_emails_by_content(imap, keyword, args.limit)
            if matched:
                print(f"[OK] Content search: Found {len(matched)} emails")
                all_matched.extend(matched)
            else:
                print(f"  [WARN] Content search: Not found")

        # Display all matched emails
        if all_matched:
            print("\n" + "="*60)
            print(f"[INFO] Found {len(all_matched)} matched emails in total")
            print("="*60)

            # Deduplicate
            seen_ids = set()
            unique_emails = []
            for email_info in all_matched:
                if email_info['id'] not in seen_ids:
                    seen_ids.add(email_info['id'])
                    unique_emails.append(email_info)

            for i, info in enumerate(unique_emails[:20], 1):  # Show at most 20
                print(f"\n{i}. [{info['id']}] {info['date']}")
                print(f"   From: {info['from']}")
                print(f"   Subject: {info['subject']}")
                print(f"   Match: {info['match_type']}")

            if len(unique_emails) > 20:
                print(f"\n... {len(unique_emails) - 20} more emails not displayed")
        else:
            print("\n" + "="*60)
            print("[WARN] No matching emails found")
            print("="*60)

        imap.logout()
        print("\n[OK] Search complete!")

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
