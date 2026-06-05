#!/usr/bin/env python3
"""
Wukong Email - Enhanced Decoding Tool
================================
Correctly handles Chinese filenames in various email encoding formats
"""

import re
import urllib.parse
from email.header import decode_header
from email import header as email_header


def decode_rfc2231(s):
    """
    Decode an RFC 2231 formatted string.
    Format: UTF-8''%E4%B8%AD%E6%96%87.txt

    Args:
        s: RFC 2231 encoded string

    Returns:
        Decoded string
    """
    if not s or not isinstance(s, str):
        return s

    # Match RFC 2231 format: charset''urlencoded
    match = re.match(r"^([^']*)''(.+)$", s)
    if match:
        charset = match.group(1)
        urlencoded = match.group(2)

        try:
            # URL decode
            decoded = urllib.parse.unquote(urlencoded)

            # Charset conversion
            if charset.lower() == 'utf-8' or not charset:
                return decoded
            else:
                return decoded.encode(charset).decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"[Warning] RFC 2231 decode failed: {e}")
            return s

    return s


def decode_rfc2047(s):
    """
    Decode an RFC 2047 formatted string.
    Format: =?UTF-8?B?5rWL6K+V?=
    Format: =?UTF-8?Q?=E4=B8=AD=E6=96=87?=

    Args:
        s: RFC 2047 encoded string

    Returns:
        Decoded string
    """
    if not s or not isinstance(s, (str, bytes)):
        return str(s) if s else ""

    try:
        # Decode using email.header.decode_header
        decoded_parts = decode_header(s)
        result = []

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    # Try the specified encoding
                    if encoding:
                        result.append(part.decode(encoding))
                    else:
                        # Try common encodings
                        for enc in ['utf-8', 'gbk', 'gb2312', 'big5']:
                            try:
                                result.append(part.decode(enc))
                                break
                            except:
                                continue
                        else:
                            # All failed, use utf-8 and ignore errors
                            result.append(part.decode('utf-8', errors='ignore'))
                except Exception as e:
                    result.append(str(part))
            else:
                result.append(str(part))

        return ''.join(result)
    except Exception as e:
        print(f"[Warning] RFC 2047 decode failed: {e}")
        return str(s)


def decode_mime_filename(filename):
    """
    Decode a MIME-encoded filename (enhanced version).

    Supported encoding formats:
    1. RFC 2047: =?UTF-8?B?...?=
    2. RFC 2047: =?UTF-8?Q?...?=
    3. RFC 2231: UTF-8''%E4%B8%AD%E6%96%87.txt
    4. Combined: =?UTF-8?B?...?= mixed with other formats

    Args:
        filename: Encoded filename

    Returns:
        Decoded filename
    """
    if not filename:
        return ""

    # Convert to string (if bytes)
    if isinstance(filename, bytes):
        try:
            filename = filename.decode('utf-8')
        except:
            filename = filename.decode('latin-1')

    # 1. Handle RFC 2231 format
    if "''" in filename and '%' in filename:
        try:
            decoded = decode_rfc2231(filename)
            if decoded != filename:
                return decoded
        except:
            pass

    # 2. Handle RFC 2047 format
    if filename.startswith('=?'):
        try:
            decoded = decode_rfc2047(filename)
            # Check if decoding succeeded (no question marks means success)
            if '?' not in decoded or decoded == filename:
                return decoded
        except:
            pass

    # 3. Handle URL encoding
    if '%' in filename:
        try:
            decoded = urllib.parse.unquote(filename)
            if decoded != filename:
                return decoded
        except:
            pass

    # 4. Try various charset decodings
    for encoding in ['utf-8', 'gbk', 'gb2312', 'big5', 'iso-8859-1']:
        try:
            decoded = filename.encode('latin-1').decode(encoding)
            # Check for garbled characters
            if not any(ord(c) > 127 and c in '﻿�' for c in decoded):
                return decoded
        except:
            continue

    # All failed, return the original string
    return filename


def decode_header_value_enhanced(header_value):
    """
    Decode email header (enhanced version).

    Args:
        header_value: Email header value

    Returns:
        Decoded string
    """
    if header_value is None:
        return ""

    # If bytes, convert to string first
    if isinstance(header_value, bytes):
        try:
            header_value = header_value.decode('utf-8')
        except:
            header_value = header_value.decode('latin-1')

    # Handle multi-segment encoding
    parts = []
    current = ""
    i = 0

    while i < len(header_value):
        # Look for encoding start marker
        if header_value[i:i+2] == '=?':
            # Save preceding plain text
            if current:
                parts.append(current)
                current = ""

            # Look for encoding end marker
            end = header_value.find('?=', i)
            if end == -1:
                # No end marker found, treat the rest as plain text
                current = header_value[i:]
                break

            # Extract the encoded segment
            encoded_part = header_value[i:end+2]
            decoded = decode_rfc2047(encoded_part)
            parts.append(decoded)
            i = end + 2
        else:
            current += header_value[i]
            i += 1

    # Save remaining plain text
    if current:
        parts.append(current)

    # Combine all parts
    result = ''.join(parts)

    # Clean up abnormal sender address suffixes returned by some servers
    # Example: Sender <user@example.com>@extra-domain
    # Should display as: Sender <user@example.com>
    if '@' in result and result.count('@') > 1:
        # Remove the last @ and everything after it
        parts = result.rsplit('@', 1)
        if '>' in parts[0]:
            result = parts[0]
        else:
            # If no angle brackets, try to keep only the email part
            result = result.replace('@' + parts[-1], '')

    # Clean up possible garbled characters
    # Remove replacement characters
    result = result.replace('﻿', '').replace('�', '')

    return result


def test_decode_examples():
    """Test various encoding formats"""
    print("=" * 80)
    print("[Test] Testing various encoding formats")
    print("=" * 80)

    test_cases = [
        # RFC 2047 Base64
        ("=?UTF-8?B?5rWL6K+V?=", "中文"),
        ("=?gbk?B?1tDOxQ==?=", "测试"),

        # RFC 2047 Quoted-Printable
        ("=?UTF-8?Q?=E4=B8=AD=E6=96=87?=", "中文"),
        ("=?gbk?Q?0BC=E2=CA=D4?=", "测试"),

        # RFC 2231
        ("UTF-8''%E4%B8%AD%E6%96%87.txt", "中文.txt"),
        ("gbk''%B2%E2%CA%D4.txt", "测试.txt"),

        # URL encoding
        ("%E4%B8%AD%E6%96%87", "中文"),
        ("%E6%B5%8B%E8%AF%95.txt", "测试.txt"),

        # Mixed format
        ("=?UTF-8?B?5rWL6K+V?=_%E6%B5%8B%E8%AF%95", "中文_测试"),
    ]

    print("\nTest results:")
    print("-" * 80)

    all_passed = True
    for encoded, expected in test_cases:
        # Test decode_rfc2047
        if encoded.startswith('=?') or '?' in encoded:
            decoded = decode_rfc2047(encoded)
        elif "''" in encoded:
            decoded = decode_rfc2231(encoded)
        elif '%' in encoded:
            decoded = urllib.parse.unquote(encoded)
        else:
            decoded = encoded

        passed = decoded == expected
        status = "PASS" if passed else "FAIL"

        print(f"{status} Encoded: {encoded}")
        print(f"   Expected: {expected}")
        print(f"   Actual:   {decoded}")

        if not passed:
            all_passed = False

        print()

    if all_passed:
        print("[PASS] All tests passed!")
    else:
        print("[WARN] Some tests failed")

    print("=" * 80)


if __name__ == '__main__':
    test_decode_examples()
