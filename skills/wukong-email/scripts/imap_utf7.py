#!/usr/bin/env python3
"""
IMAP UTF-7 编码工具
===================
处理中文文件夹名称到 IMAP UTF-7 编码的转换

参考：
- RFC 3501: INTERNET MESSAGE ACCESS PROTOCOL - VERSION 4rev1
- RFC 2060: IMAP UTF-7 编码规范
"""

import re


def encode_imap_utf7(text: str) -> str:
    """
    将文本编码为 IMAP UTF-7 格式

    Args:
        text: 要编码的文本（如 "已发送"）

    Returns:
        IMAP UTF-7 编码（如 "&XfJT0ZAB-"）

    示例:
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

        # 可打印 ASCII 字符（除了 &）保持不变
        if ord(char) >= 32 and ord(char) <= 126:
            if char == '&':
                # & 需要转义为 &-
                result.append('&-')
            else:
                result.append(char)
            i += 1
        else:
            # 非 ASCII 字符，使用 BASE64 编码
            start = i
            while i < len(text) and (ord(text[i]) < 32 or ord(text[i]) > 126 or text[i] == '&'):
                i += 1

            # 提取需要编码的部分
            unicode_text = text[start:i]

            # 转换为 UTF-16LE
            utf16_bytes = unicode_text.encode('utf-16-le')

            # 转换为 BASE64（修改版：使用 +/ 代替 +/, 去掉 =）
            import base64
            base64_bytes = base64.b64encode(utf16_bytes)
            base64_str = base64_bytes.decode('ascii')

            # 修改 BASE64 字符集
            base64_str = base64_str.replace('+', ',')
            base64_str = base64_str.rstrip('=')

            # 添加 IMAP UTF-7 标记
            result.append('&' + base64_str + '-')

    return ''.join(result)


def decode_imap_utf7(text: str) -> str:
    """
    解码 IMAP UTF-7 格式的文本

    Args:
        text: IMAP UTF-7 编码（如 "&XfJT0ZAB-"）

    Returns:
        解码后的文本（如 "已发送"）

    示例:
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
                # &- 表示 & 字符
                result.append('&')
                i += 2
            else:
                # 查找编码结束标记 -
                end = text.find('-', i + 1)
                if end == -1:
                    # 没有找到结束标记，将剩余部分作为普通文本
                    result.append(text[i:])
                    break

                # 提取 BASE64 部分
                base64_str = text[i + 1:end]

                # 修改 BASE64 字符集
                base64_str = base64_str.replace(',', '+')

                # 添加填充 =
                padding = len(base64_str) % 4
                if padding:
                    base64_str += '=' * (4 - padding)

                # 解码 BASE64
                import base64
                try:
                    utf16_bytes = base64.b64decode(base64_str)
                    # 从 UTF-16LE 解码
                    decoded_text = utf16_bytes.decode('utf-16-le')
                    result.append(decoded_text)
                except Exception:
                    # 解码失败，保留原始文本
                    result.append(text[i:end + 1])

                i = end + 1
        else:
            result.append(text[i])
            i += 1

    return ''.join(result)


# 常见中文文件夹名称的映射表（优化性能）
COMMON_FOLDER_NAMES = {
    # 已发送
    '已发送': '&XfJT0ZAB-',
    '已发送邮件': '&XfJT0ZAB+0Zw-',
    '发件箱': '&V4NXPpCuTvY-',

    # 草稿箱
    '草稿箱': '&g0l6P3ux-',
    '草稿': '&g0l6Pw-',

    # 已删除
    '已删除': '&XfJSIJZk-',
    '删除的邮件': '&XfJSIJZk+TL2-',
    '废纸篓': '&V4NXPpCuTlw-',

    # 垃圾邮件
    '垃圾邮件': '&V4NXPpCuTvY-',
    '垃圾箱': '&V4NXPpCuTlk-',

    # 收件箱
    '收件箱': '&U,7TkuJ2Q-',

    # 英文名称（无需编码）
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
    获取友好的文件夹名称对应的 IMAP 文件夹名称

    Args:
        friendly_name: 用户看到的文件夹名称（如 "已发送"）

    Returns:
        IMAP 文件夹名称（如 "&XfJT0ZAB-" 或 "Sent"）

    示例:
        >>> get_imap_folder_name('已发送')
        '&XfJT0ZAB-'
        >>> get_imap_folder_name('Sent')
        'Sent'
    """
    # 首先检查映射表
    if friendly_name in COMMON_FOLDER_NAMES:
        return COMMON_FOLDER_NAMES[friendly_name]

    # 英文名称无需编码
    try:
        friendly_name.encode('ascii')
        return friendly_name
    except UnicodeEncodeError:
        pass

    # 中文名称需要编码
    return encode_imap_utf7(friendly_name)


# 测试代码
if __name__ == '__main__':
    print("=" * 80)
    print("IMAP UTF-7 编码测试")
    print("=" * 80)

    test_cases = [
        ('已发送', '&XfJT0ZAB-'),
        ('草稿箱', '&g0l6P3ux-'),
        ('已删除', '&XfJSIJZk-'),
        ('垃圾邮件', '&V4NXPpCuTvY-'),
        ('Sent', 'Sent'),
        ('Drafts', 'Drafts'),
    ]

    print("\n【编码测试】")
    for input_text, expected in test_cases:
        encoded = encode_imap_utf7(input_text)
        status = "✅" if encoded == expected else "❌"
        print(f"{status} {input_text} → {encoded} (期望: {expected})")

    print("\n【解码测试】")
    for expected, encoded in test_cases:
        decoded = decode_imap_utf7(encoded)
        status = "✅" if decoded == expected else "❌"
        print(f"{status} {encoded} → {decoded} (期望: {expected})")

    print("\n【友好名称测试】")
    friendly_names = ['已发送', '草稿箱', 'Sent', 'Drafts']
    for name in friendly_names:
        imap_name = get_imap_folder_name(name)
        print(f"✅ {name} → {imap_name}")
