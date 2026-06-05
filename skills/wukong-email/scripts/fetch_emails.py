#!/usr/bin/env python3
"""
Wukong Email - Fetch Emails (Enhanced)
=======================================
Supports automatic attachment downloads.
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

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import load_config
from decode_helper import decode_mime_filename, decode_header_value_enhanced as decode_str
from imap_utf7 import get_imap_folder_name


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
    else:
        context.set_ciphers(
            'ECDHE-RSA-AES256-GCM-SHA384:'
            'ECDHE-ECDSA-AES256-GCM-SHA384:'
            'AES256-GCM-SHA384:'
            'AES256-SHA256'
        )

    return context


def decode_header_value(header_value: str) -> str:
    """Decode email header value."""
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

    # Clean up extra domain suffixes returned by some servers
    # e.g.: Sender <user@example.com>@extra-domain -> Sender <user@example.com>
    if '@' in result and result.count('@') > 1:
        parts = result.rsplit('@', 1)
        if '>' in parts[0]:
            result = parts[0]
        else:
            result = result.replace('@' + parts[-1], '')

    return result


def clean_email_address(email_str: str) -> str:
    """Clean email address by removing extra domain suffixes."""
    if not email_str:
        return ""

    if email_str.count('@') > 1:
        last_at = email_str.rfind('@')

        if '>' in email_str[:last_at]:
            return email_str[:last_at].rstrip()
        else:
            parts = email_str.split('@')
            if len(parts) >= 2:
                for i in range(1, len(parts)):
                    potential_email = '@'.join(parts[:i+1])
                    if '.' in parts[i]:
                        return potential_email

            return email_str

    return email_str


def get_email_body(msg) -> str:
    """Extract email body text."""
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
    """Get attachment download directory."""
    config = load_config()
    attachments_dir = config.get('attachments_dir', '~/.wukong-email/attachments')
    attachments_dir = os.path.expanduser(attachments_dir)
    os.makedirs(attachments_dir, exist_ok=True)
    return attachments_dir


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing illegal characters."""
    illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in illegal_chars:
        filename = filename.replace(char, '_')
    return filename


def is_attachment_downloaded(email_dir: str, filename: str) -> bool:
    """Check if attachment has already been downloaded."""
    file_path = os.path.join(email_dir, filename)
    return os.path.exists(file_path)


def download_attachments_from_email(imap, email_uid, msg, attachments_dir: str, force: bool = False) -> Tuple[int, int, int]:
    """
    Download all attachments from a single email.

    Returns:
        (success_count, skip_count, error_count)
    """
    if isinstance(email_uid, bytes):
        email_uid = email_uid.decode('utf-8')

    email_dir = os.path.join(attachments_dir, str(email_uid))
    os.makedirs(email_dir, exist_ok=True)

    success_count = 0
    skip_count = 0
    error_count = 0

    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        if "attachment" not in content_disposition.lower():
            continue

        filename = part.get_filename()
        if not filename:
            continue

        decoded_filename = decode_mime_filename(filename)
        if not decoded_filename:
            decoded_filename = filename

        safe_filename = sanitize_filename(decoded_filename)
        file_path = os.path.join(email_dir, safe_filename)

        if not force and is_attachment_downloaded(email_dir, safe_filename):
            print(f"  [SKIP] Already exists: {safe_filename}")
            skip_count += 1
            continue

        try:
            with open(file_path, 'wb') as f:
                f.write(part.get_payload(decode=True))

            file_size = os.path.getsize(file_path)
            print(f"  [OK] Downloaded: {safe_filename} ({file_size:,} bytes)")
            success_count += 1

        except Exception as e:
            print(f"  [ERROR] Download failed: {safe_filename} - {e}")
            error_count += 1

    # Create email info file
    info_file = os.path.join(email_dir, 'email_info.txt')
    if not os.path.exists(info_file):
        try:
            with open(info_file, 'w', encoding='utf-8') as f:
                f.write(f"Email UID: {email_uid}\n")
                f.write(f"Subject: {decode_str(msg.get('Subject', ''))}\n")
                f.write(f"From: {decode_str(msg.get('From', ''))}\n")
                f.write(f"Date: {msg.get('Date', '')}\n")
                f.write(f"Downloaded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        except Exception as e:
            print(f"  [WARN] Failed to create info file: {e}")

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
    Fetch emails with optional attachment download and filtering.

    Returns:
        List[Dict]: List of email info dicts.
    """
    if ssl_config is None:
        ssl_config = {}
    context = create_ssl_context(ssl_config)

    imap = None
    try:
        print(f"[INFO] Connecting to {imap_server}:{imap_port}...")
        imap = IMAP4_SSL(imap_server, imap_port, ssl_context=context)

        print("[INFO] Logging in...")
        imap.login(username, password)

        folder_name = get_imap_folder_name(folder)
        print(f"[INFO] Selecting folder: {folder}...")
        imap.select(folder_name)

        print(f"[INFO] Search criteria: {search_criteria}...")
        status, messages = imap.search(None, search_criteria)

        if status != 'OK':
            print(f"[ERROR] Search failed: {status}")
            return []

        email_ids = messages[0].split()
        total_count = len(email_ids)

        print(f"[INFO] Found {total_count} emails")

        email_ids = email_ids[-limit:] if total_count > limit else email_ids

        print(f"[INFO] Fetching latest {len(email_ids)} emails...")
        if download_attachments:
            print(f"[INFO] Auto-downloading attachments to: {attachments_dir}")

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
                'msg': msg
            }
            emails.append(email_info)
            print(f"  [{idx}/{len(email_ids)}] {email_info['subject'][:50]}...")

            if download_attachments:
                success, skip, error = download_attachments_from_email(
                    imap, email_id, msg, attachments_dir, force_download
                )
                total_success += success
                total_skip += skip
                total_error += error

                if only_with_attachments and (success + skip + error) == 0:
                    emails.pop()
                    continue

        print(f"[OK] Fetched {len(emails)} emails")
        if download_attachments:
            print(f"[INFO] Attachments: downloaded={total_success}, skipped={total_skip}, failed={total_error}")

        return emails

    except Exception as e:
        print(f"[ERROR] Fetch failed: {e}")
        return []

    finally:
        if imap:
            try:
                imap.close()
                imap.logout()
            except:
                pass


def display_email(email_info: Dict):
    """Display email details."""
    print("=" * 70)
    print(f"Email ID: {email_info['id']}")
    print(f"From: {email_info['from']}")
    print(f"To: {email_info['to']}")
    print(f"Subject: {email_info['subject']}")
    print(f"Date: {email_info['date']}")
    print("=" * 70)
    print("Body:")
    print(email_info['body'][:500])
    if len(email_info['body']) > 500:
        print("... (content truncated)")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Wukong Email - Fetch Emails',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch latest 10 emails
  python fetch_emails.py

  # Fetch latest 20 emails
  python fetch_emails.py --limit 20

  # Search emails from a specific sender
  python fetch_emails.py --search 'FROM "user@example.com"'

  # Search emails by subject
  python fetch_emails.py --search 'SUBJECT "test"'

  # Show full email body
  python fetch_emails.py --full
        """
    )

    parser.add_argument('--config', help='Config file path (deprecated, use ~/.wukong-email/.env)')
    parser.add_argument('--server', help='IMAP server address')
    parser.add_argument('--port', type=int, default=993, help='IMAP port (default: 993)')
    parser.add_argument('--user', help='Email username')
    parser.add_argument('--password', help='Email password')
    parser.add_argument('--folder', default='INBOX', help='Folder (default: INBOX)')
    parser.add_argument('--limit', type=int, default=10, help='Number of emails to fetch (default: 10)')
    parser.add_argument('--uids', required=True, help='Email UID list (comma-separated), e.g.: 2060,2061,2062')
    parser.add_argument('--download-attachments', action='store_true', help='Auto-download attachments')
    parser.add_argument('--force-download', action='store_true', help='Force re-download attachments (overwrite existing)')
    parser.add_argument('--list', action='store_true', help='List emails only, do not show body')
    parser.add_argument('--full', action='store_true', help='Show full body')

    args = parser.parse_args()

    imap_server = args.server
    imap_port = args.port
    username = args.user
    password = args.password
    if not all([imap_server, username, password]):
        if args.config:
            print("[WARN] --config is deprecated, use config_loader and ~/.wukong-email/.env")

        config = load_config()
        imap_server = config['imap_host']
        imap_port = config['imap_port']
        username = config['email']
        password = config['email_password']

        print(f"[INFO] Using preset: {config.get('preset_name', 'default')}")
        print(f"[INFO] IMAP: {imap_server}:{imap_port}")
        print(f"[INFO] User: {username}")

    imap_ssl_config = {
        'verify': config['imap_ssl_verify'],
        'check_hostname': config['imap_ssl_verify'],
        'ciphers': config['imap_ssl_ciphers'].split(':') if config.get('imap_ssl_ciphers') else []
    }

    attachments_dir = None
    if args.download_attachments:
        attachments_dir = get_attachments_dir()

    search_criteria = f'UID {args.uids}'

    emails = fetch_emails(
        imap_server=imap_server,
        imap_port=imap_port,
        username=username,
        password=password,
        folder=args.folder,
        limit=9999,
        search_criteria=search_criteria,
        ssl_config=imap_ssl_config,
        download_attachments=args.download_attachments,
        attachments_dir=attachments_dir,
        force_download=args.force_download,
        only_with_attachments=False
    )

    if not emails:
        print("[INFO] No emails found")
        sys.exit(0)

    if args.download_attachments:
        print("\n" + "=" * 70)
        print("Attachment List")
        print("=" * 70)

        for idx, email_info in enumerate(emails, 1):
            email_uid = email_info['id']
            email_dir = os.path.join(attachments_dir, email_uid)

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
                        print(f"   {filename} ({size_str})")
                        print(f"      Path: {email_dir}/{filename}")

        print("\n" + "=" * 70)
        print(f"Total: {len(emails)} emails")
        print(f"Attachment directory: {attachments_dir}")
        print("=" * 70)
        sys.exit(0)

    if args.list:
        print("\n" + "=" * 70)
        print("Email List")
        print("=" * 70)
        for idx, email_info in enumerate(emails, 1):
            print(f"{idx}. {email_info['subject'][:60]}")
            print(f"   From: {email_info['from'][:50]}")
            print(f"   Date: {email_info['date']}")
            print()
    else:
        for email_info in emails:
            display_email(email_info)
            if not args.full:
                break


if __name__ == '__main__':
    main()
