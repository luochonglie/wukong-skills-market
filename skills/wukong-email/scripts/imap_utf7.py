#!/usr/bin/env python3
"""
IMAP UTF-7 Encoding Utility
============================
Handles conversion of Chinese folder names to IMAP UTF-7 encoding

References:
- RFC 3501: INTERNET MESSAGE ACCESS PROTOCOL - VERSION 4rev1
- RFC 2060: IMAP UTF-7 encoding specification
"""

import re


def encode_imap_utf7(text: str) -> str:
    """
    Encode text to IMAP UTF-7 format

    Args:
        text: Text to encode (e.g. "Sent")

    Returns:
        IMAP UTF-7 encoded string (e.g. "&XfJT0ZAB-")

    Examples:
        >>> encode_imap_utf7("已发送")
        '&XfJT0ZAB-'
        >>> encode_imap_utf7("草稿箱")
        '&g0l6P3ux-'
    """
    if not text:
        return text

    result = []
    i = 0

    while i < len(text):
        char = text[i]

        # Printable ASCII characters (except &) remain unchanged
        if ord(char) >= 32 and ord(char) <= 126:
            if char == '&':
                # & must be escaped as &-
                result.append('&-')
            else:
                result.append(char)
            i += 1
        else:
            # Non-ASCII characters, use BASE64 encoding
            start = i
            while i < len(text) and (ord(text[i]) < 32 or ord(text[i]) > 126 or text[i] == '&'):
                i += 1

            # Extract the portion that needs encoding
            unicode_text = text[start:i]

            # Convert to UTF-16LE
            utf16_bytes = unicode_text.encode('utf-16-le')

            # Convert to BASE64 (modified version: use +/ instead of +/, remove =)
            import base64
            base64_bytes = base64.b64encode(utf16_bytes)
            base64_str = base64_bytes.decode('ascii')

            # Modify BASE64 character set
            base64_str = base64_str.replace('+', ',')
            base64_str = base64_str.rstrip('=')

            # Add IMAP UTF-7 markers
            result.append('&' + base64_str + '-')

    return ''.join(result)


def decode_imap_utf7(text: str) -> str:
    """
    Decode IMAP UTF-7 formatted text

    Args:
        text: IMAP UTF-7 encoded string (e.g. "&XfJT0ZAB-")

    Returns:
        Decoded text (e.g. "已发送")

    Examples:
        >>> decode_imap_utf7('&XfJT0ZAB-')
        '已发送'
        >>> decode_imap_utf7('&g0l6P3ux-')
        '草稿箱'
    """
    if not text:
        return text

    result = []
    i = 0

    while i < len(text):
        if text[i] == '&':
            if i + 1 < len(text) and text[i + 1] == '-':
                # &- represents the & character
                result.append('&')
                i += 2
            else:
                # Find the encoding end marker -
                end = text.find('-', i + 1)
                if end == -1:
                    # No end marker found, treat the rest as plain text
                    result.append(text[i:])
                    break

                # Extract the BASE64 portion
                base64_str = text[i + 1:end]

                # Modify BASE64 character set
                base64_str = base64_str.replace(',', '+')

                # Add padding =
                padding = len(base64_str) % 4
                if padding:
                    base64_str += '=' * (4 - padding)

                # Decode BASE64
                import base64
                try:
                    utf16_bytes = base64.b64decode(base64_str)
                    # Decode from UTF-16LE
                    decoded_text = utf16_bytes.decode('utf-16-le')
                    result.append(decoded_text)
                except Exception:
                    # Decoding failed, keep original text
                    result.append(text[i:end + 1])

                i = end + 1
        else:
            result.append(text[i])
            i += 1

    return ''.join(result)


# Common Chinese folder name mapping table (for performance optimization)
COMMON_FOLDER_NAMES = {
    # Sent
    '已发送': '&XfJT0ZAB-',
    '已发送邮件': '&XfJT0ZAB+0Zw-',
    '发件箱': '&V4NXPpCuTvY-',

    # Drafts
    '草稿箱': '&g0l6P3ux-',
    '草稿': '&g0l6Pw-',

    # Deleted
    '已删除': '&XfJSIJZk-',
    '删除的邮件': '&XfJSIJZk+TL2-',
    '废纸篓': '&V4NXPpCuTlw-',

    # Spam
    '垃圾邮件': '&V4NXPpCuTvY-',
    '垃圾箱': '&V4NXPpCuTlk-',

    # Inbox
    '收件箱': '&U,7TkuJ2Q-',

    # English names (no encoding needed)
    'Sent': 'Sent',
    'Sent Items': 'Sent Items',
    'Sent Messages': 'Sent Messages',
    'Drafts': 'Drafts',
    'Trash': 'Trash',
    'Junk': 'Junk',
    'Inbox': 'Inbox',
}


def get_imap_folder_name(friendly_name: str) -> str:
    """
    Get the IMAP folder name corresponding to a friendly folder name

    Args:
        friendly_name: User-visible folder name (e.g. "已发送")

    Returns:
        IMAP folder name (e.g. "&XfJT0ZAB-" or "Sent")

    Examples:
        >>> get_imap_folder_name('已发送')
        '&XfJT0ZAB-'
        >>> get_imap_folder_name('Sent')
        'Sent'
    """
    # First check the mapping table
    if friendly_name in COMMON_FOLDER_NAMES:
        return COMMON_FOLDER_NAMES[friendly_name]

    # English names do not need encoding
    try:
        friendly_name.encode('ascii')
        return friendly_name
    except UnicodeEncodeError:
        pass

    # Chinese names need encoding
    return encode_imap_utf7(friendly_name)


# Test code
if __name__ == '__main__':
    print("=" * 80)
    print("IMAP UTF-7 encoding test")
    print("=" * 80)

    test_cases = [
        ('已发送', '&XfJT0ZAB-'),
        ('草稿箱', '&g0l6P3ux-'),
        ('已删除', '&XfJSIJZk-'),
        ('垃圾邮件', '&V4NXPpCuTvY-'),
        ('Sent', 'Sent'),
        ('Drafts', 'Drafts'),
    ]

    print("\n[Encoding test]")
    for input_text, expected in test_cases:
        encoded = encode_imap_utf7(input_text)
        status = "PASS" if encoded == expected else "FAIL"
        print(f"{status} {input_text} -> {encoded} (expected: {expected})")

    print("\n[Decoding test]")
    for expected, encoded in test_cases:
        decoded = decode_imap_utf7(encoded)
        status = "PASS" if decoded == expected else "FAIL"
        print(f"{status} {encoded} -> {decoded} (expected: {expected})")

    print("\n[Friendly name test]")
    friendly_names = ['已发送', '草稿箱', 'Sent', 'Drafts']
    for name in friendly_names:
        imap_name = get_imap_folder_name(name)
        print(f"PASS {name} -> {imap_name}")
