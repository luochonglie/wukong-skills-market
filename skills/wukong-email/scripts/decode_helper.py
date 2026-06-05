#!/usr/bin/env python3
"""
Wukong Email - 增强版中文解码工具
================================
正确处理各种邮件编码格式的中文文件名
"""

import re
import urllib.parse
from email.header import decode_header
from email import header as email_header


def decode_rfc2231(s):
    """
    解码 RFC 2231 格式的字符串
    格式: UTF-8''%E4%B8%AD%E6%96%87.txt

    Args:
        s: RFC 2231 编码的字符串

    Returns:
        解码后的字符串
    """
    if not s or not isinstance(s, str):
        return s

    # 匹配 RFC 2231 格式: charset''urlencoded
    match = re.match(r"^([^']*)''(.+)$", s)
    if match:
        charset = match.group(1)
        urlencoded = match.group(2)

        try:
            # URL 解码
            decoded = urllib.parse.unquote(urlencoded)

            # 字符集转换
            if charset.lower() == 'utf-8' or not charset:
                return decoded
            else:
                return decoded.encode(charset).decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"[警告] RFC 2231 解码失败: {e}")
            return s

    return s


def decode_rfc2047(s):
    """
    解码 RFC 2047 格式的字符串
    格式: =?UTF-8?B?5rWL6K+V?=
    格式: =?UTF-8?Q?=E4=B8=AD=E6=96=87?=

    Args:
        s: RFC 2047 编码的字符串

    Returns:
        解码后的字符串
    """
    if not s or not isinstance(s, (str, bytes)):
        return str(s) if s else ""

    try:
        # 使用 email.header.decode_header 解码
        decoded_parts = decode_header(s)
        result = []

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    # 尝试指定的编码
                    if encoding:
                        result.append(part.decode(encoding))
                    else:
                        # 尝试常见编码
                        for enc in ['utf-8', 'gbk', 'gb2312', 'big5']:
                            try:
                                result.append(part.decode(enc))
                                break
                            except:
                                continue
                        else:
                            # 都失败了，用 utf-8 并忽略错误
                            result.append(part.decode('utf-8', errors='ignore'))
                except Exception as e:
                    result.append(str(part))
            else:
                result.append(str(part))

        return ''.join(result)
    except Exception as e:
        print(f"[警告] RFC 2047 解码失败: {e}")
        return str(s)


def decode_mime_filename(filename):
    """
    解码 MIME 编码的文件名（增强版）

    支持的编码格式：
    1. RFC 2047: =?UTF-8?B?...?=
    2. RFC 2047: =?UTF-8?Q?...?=
    3. RFC 2231: UTF-8''%E4%B8%AD%E6%96%87.txt
    4. 组合编码: =?UTF-8?B?...?= 和其他格式混合

    Args:
        filename: 编码的文件名

    Returns:
        解码后的文件名
    """
    if not filename:
        return ""

    # 转换为字符串（如果是 bytes）
    if isinstance(filename, bytes):
        try:
            filename = filename.decode('utf-8')
        except:
            filename = filename.decode('latin-1')

    # 1. 处理 RFC 2231 格式
    if "''" in filename and '%' in filename:
        try:
            decoded = decode_rfc2231(filename)
            if decoded != filename:
                return decoded
        except:
            pass

    # 2. 处理 RFC 2047 格式
    if filename.startswith('=?'):
        try:
            decoded = decode_rfc2047(filename)
            # 检查是否成功解码（如果没有问号了，说明成功）
            if '?' not in decoded or decoded == filename:
                return decoded
        except:
            pass

    # 3. 处理 URL 编码
    if '%' in filename:
        try:
            decoded = urllib.parse.unquote(filename)
            if decoded != filename:
                return decoded
        except:
            pass

    # 4. 尝试各种字符集解码
    for encoding in ['utf-8', 'gbk', 'gb2312', 'big5', 'iso-8859-1']:
        try:
            decoded = filename.encode('latin-1').decode(encoding)
            # 检查是否包含乱码字符
            if not any(ord(c) > 127 and c in 'ï¿½ï¿½' for c in decoded):
                return decoded
        except:
            continue

    # 都失败了，返回原始字符串
    return filename


def decode_header_value_enhanced(header_value):
    """
    解码邮件头（增强版）
    
    Args:
        header_value: 邮件头的值

    Returns:
        解码后的字符串
    """
    if header_value is None:
        return ""

    # 如果是 bytes，先转成字符串
    if isinstance(header_value, bytes):
        try:
            header_value = header_value.decode('utf-8')
        except:
            header_value = header_value.decode('latin-1')

    # 处理多段编码
    parts = []
    current = ""
    i = 0

    while i < len(header_value):
        # 查找编码开始的标记
        if header_value[i:i+2] == '=?':
            # 保存之前的普通文本
            if current:
                parts.append(current)
                current = ""

            # 查找编码结束的标记
            end = header_value.find('?=', i)
            if end == -1:
                # 没有找到结束标记，把剩余部分当作普通文本
                current = header_value[i:]
                break

            # 提取编码段
            encoded_part = header_value[i:end+2]
            decoded = decode_rfc2047(encoded_part)
            parts.append(decoded)
            i = end + 2
        else:
            current += header_value[i]
            i += 1

    # 保存剩余的普通文本
    if current:
        parts.append(current)

    # 合并所有部分
    result = ''.join(parts)
    
    # 清理少数服务器返回的异常发件人地址后缀
    # 例如：发件人 <user@example.com>@extra-domain
    # 应该显示为：发件人 <user@example.com>
    if '@' in result and result.count('@') > 1:
        # 移除最后一个 @ 及其后面的内容
        parts = result.rsplit('@', 1)
        if '>' in parts[0]:
            result = parts[0]
        else:
            # 如果没有尖括号，尝试只保留邮箱部分
            result = result.replace('@' + parts[-1], '')

    # 清理可能的乱码
    # 移除替换字符
    result = result.replace('ï¿½', '')

    return result


def test_decode_examples():
    """测试各种编码格式"""
    print("=" * 80)
    print("🧪 测试各种编码格式")
    print("=" * 80)

    test_cases = [
        # RFC 2047 Base64
        ("=?UTF-8?B?5rWL6K+V?=", "中文"),
        ("=?gbk?B?1tDOxQ==?=", "测试"),

        # RFC 2047 Quoted-Printable
        ("=?UTF-8?Q?=E4=B8=AD=E6=96=87?=", "中文"),
        ("=?gbk?Q=C2=E8=CA=D4?=", "测试"),

        # RFC 2231
        ("UTF-8''%E4%B8%AD%E6%96%87.txt", "中文.txt"),
        ("gbk''%B2%E2%CA%D4.txt", "测试.txt"),

        # URL 编码
        ("%E4%B8%AD%E6%96%87", "中文"),
        ("%E6%B5%8B%E8%AF%95.txt", "测试.txt"),

        # 混合格式
        ("=?UTF-8?B?5rWL6K+V?=_%E6%B5%8B%E8%AF%95", "中文_测试"),
    ]

    print("\n测试结果:")
    print("-" * 80)

    all_passed = True
    for encoded, expected in test_cases:
        # 测试 decode_rfc2047
        if encoded.startswith('=?') or '?' in encoded:
            decoded = decode_rfc2047(encoded)
        elif "''" in encoded:
            decoded = decode_rfc2231(encoded)
        elif '%' in encoded:
            decoded = urllib.parse.unquote(encoded)
        else:
            decoded = encoded

        passed = decoded == expected
        status = "✅" if passed else "❌"

        print(f"{status} 编码: {encoded}")
        print(f"   期望: {expected}")
        print(f"   实际: {decoded}")

        if not passed:
            all_passed = False

        print()

    if all_passed:
        print("✅ 所有测试通过！")
    else:
        print("⚠️  部分测试失败")

    print("=" * 80)


if __name__ == '__main__':
    test_decode_examples()
