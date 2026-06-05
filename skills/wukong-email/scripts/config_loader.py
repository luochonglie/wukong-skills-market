#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wukong Email Configuration Loader (简化版)
===========================================
只从 ~/.wukong-email/.env 文件加载配置，不需要 config.yaml

优先级顺序：
1. 系统环境变量
2. ~/.wukong-email/.env 文件
3. 代码默认值

Usage:
    from config_loader import load_config

    config = load_config()
    print(config['email'])
    print(config['smtp_host'])
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import re

# 模块级缓存
_cached_config: Optional[Dict[str, Any]] = None
CONFIG_DIR = Path.home() / '.wukong-email'
ENV_FILE = CONFIG_DIR / '.env'


def find_env_file() -> Optional[Path]:
    """
    查找用户级 .env 文件
    返回 Path 对象，如果未找到返回 None
    """
    return ENV_FILE if ENV_FILE.exists() else None


def load_dotenv(env_path: Optional[Path] = None) -> Dict[str, str]:
    """
    加载 .env 文件并返回字典
    简单实现（不需要 python-dotenv）

    Args:
        env_path: .env 文件路径。如果为 None，使用 ~/.wukong-email/.env

    Returns:
        环境变量字典
    """
    if env_path is None:
        env_path = find_env_file()

    if env_path is None or not env_path.exists():
        return {}

    env_vars = {}
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 跳过注释和空行
            if not line or line.startswith('#'):
                continue

            # 解析 KEY=VALUE 或 KEY="VALUE"
            match = re.match(r'^([A-Z_][A-Z0-9_]*)=(.*)$', line)
            if match:
                key, value = match.groups()
                # 移除引号（如果有）
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                env_vars[key] = value

    return env_vars


def str_to_bool(value: str) -> bool:
    """将字符串转换为布尔值"""
    return value.lower() in ('true', 'yes', '1', 'on')


PLACEHOLDER_VALUES = {
    'your-email@example.com',
    'your-password',
    'yourpassword',
    'your name',
    'smtp.example.com',
    'imap.example.com',
}


def is_unset_or_placeholder(value: str) -> bool:
    """判断配置是否为空或仍是模板占位值"""
    return not value or value.strip().lower() in PLACEHOLDER_VALUES


def load_config(
    email: Optional[str] = None,
    password: Optional[str] = None,
    smtp_host: Optional[str] = None,
    smtp_port: Optional[int] = None,
    imap_host: Optional[str] = None,
    imap_port: Optional[int] = None,
    force_reload: bool = False
) -> Dict[str, Any]:
    """
    加载配置（从环境变量或 ~/.wukong-email/.env 文件）

    Args:
        email: 邮箱地址（可选，覆盖配置）
        password: 邮箱密码（可选，覆盖配置）
        smtp_host: SMTP 服务器（可选，覆盖配置）
        smtp_port: SMTP 端口（可选，覆盖配置）
        imap_host: IMAP 服务器（可选，覆盖配置）
        imap_port: IMAP 端口（可选，覆盖配置）
        force_reload: 强制重新加载（忽略缓存）

    Returns:
        配置字典
    """
    global _cached_config

    # 使用缓存（如果存在且未强制重新加载）
    if _cached_config is not None and not force_reload:
        # 应用参数覆盖
        if email:
            _cached_config['email'] = email
        if password:
            _cached_config['email_password'] = password
        if smtp_host:
            _cached_config['smtp_host'] = smtp_host
        if smtp_port:
            _cached_config['smtp_port'] = smtp_port
        if imap_host:
            _cached_config['imap_host'] = imap_host
        if imap_port:
            _cached_config['imap_port'] = imap_port
        return _cached_config

    # 1. 从用户级 .env 文件加载
    env_vars = load_dotenv()

    # 2. 优先级：环境变量 > ~/.wukong-email/.env > 默认值（仅非敏感字段）
    config = {
        # 邮箱凭据（必填，无默认值）
        'email': os.getenv('EMAIL_ADDRESS') or env_vars.get('EMAIL_ADDRESS', ''),
        'email_password': os.getenv('EMAIL_PASSWORD') or env_vars.get('EMAIL_PASSWORD', ''),

        # SMTP 配置（必填，无默认值）
        'smtp_host': os.getenv('EMAIL_SMTP_HOST') or env_vars.get('EMAIL_SMTP_HOST', ''),
        'smtp_port': int(os.getenv('EMAIL_SMTP_PORT') or env_vars.get('EMAIL_SMTP_PORT', '465')),
        'smtp_use_ssl': str_to_bool(os.getenv('EMAIL_SMTP_USE_SSL') or env_vars.get('EMAIL_SMTP_USE_SSL', 'true')),
        'smtp_ssl_verify': str_to_bool(os.getenv('EMAIL_SMTP_SSL_VERIFY') or env_vars.get('EMAIL_SMTP_SSL_VERIFY', 'false')),
        'smtp_ssl_ciphers': os.getenv('EMAIL_SMTP_SSL_CIPHERS') or env_vars.get('EMAIL_SMTP_SSL_CIPHERS',
            'ECDHE-RSA-AES256-GCM-SHA384:AES256-GCM-SHA384'),

        # IMAP 配置（必填，无默认值）
        'imap_host': os.getenv('EMAIL_IMAP_HOST') or env_vars.get('EMAIL_IMAP_HOST', ''),
        'imap_port': int(os.getenv('EMAIL_IMAP_PORT') or env_vars.get('EMAIL_IMAP_PORT', '993')),
        'imap_use_ssl': str_to_bool(os.getenv('EMAIL_IMAP_USE_SSL') or env_vars.get('EMAIL_IMAP_USE_SSL', 'true')),
        'imap_ssl_verify': str_to_bool(os.getenv('EMAIL_IMAP_SSL_VERIFY') or env_vars.get('EMAIL_IMAP_SSL_VERIFY', 'false')),
        'imap_ssl_ciphers': os.getenv('EMAIL_IMAP_SSL_CIPHERS') or env_vars.get('EMAIL_IMAP_SSL_CIPHERS',
            'ECDHE-RSA-AES256-GCM-SHA384:AES256-GCM-SHA384'),

        # 可选：发件人显示名称
        'from_name': os.getenv('EMAIL_FROM_NAME') or env_vars.get('EMAIL_FROM_NAME', ''),

        # 已发送文件夹配置
        'enable_save_to_sent': str_to_bool(os.getenv('EMAIL_ENABLE_SAVE_TO_SENT') or env_vars.get('EMAIL_ENABLE_SAVE_TO_SENT', 'true')),
        'sent_folder': os.getenv('EMAIL_SENT_FOLDER') or env_vars.get('EMAIL_SENT_FOLDER', 'Sent'),
        
        # 附件下载目录配置
        'attachments_dir': os.getenv('EMAIL_ATTACHMENTS_DIR') or env_vars.get('EMAIL_ATTACHMENTS_DIR', '~/.wukong-email/attachments'),
    }

    # 3. 参数覆盖（优先级最高）
    if email:
        config['email'] = email
    if password:
        config['email_password'] = password
    if smtp_host:
        config['smtp_host'] = smtp_host
    if smtp_port:
        config['smtp_port'] = smtp_port
    if imap_host:
        config['imap_host'] = imap_host
    if imap_port:
        config['imap_port'] = imap_port

    # 4. 验证必填配置（缺失时抛出异常）
    required_fields = {
        'EMAIL_ADDRESS': config['email'],
        'EMAIL_PASSWORD': config['email_password'],
        'EMAIL_SMTP_HOST': config['smtp_host'],
        'EMAIL_IMAP_HOST': config['imap_host'],
    }

    missing_fields = [field for field, value in required_fields.items() if is_unset_or_placeholder(value)]

    if missing_fields:
        print("❌ 错误: 缺少必填配置项，或配置仍是模板占位值！")
        print(f"   需要修改: {', '.join(missing_fields)}")
        print()
        print("📝 请在 ~/.wukong-email/.env 中配置以下内容：")
        print()
        print("   # 邮箱凭据（必填）")
        print("   EMAIL_ADDRESS=your-email@example.com")
        print("   EMAIL_PASSWORD=your-password")
        print()
        print("   # SMTP 配置（必填）")
        print("   EMAIL_SMTP_HOST=smtp.example.com")
        print()
        print("   # IMAP 配置（必填）")
        print("   EMAIL_IMAP_HOST=imap.example.com")
        print()
        raise SystemExit(1)

    # 5. 缓存配置
    _cached_config = config

    return config


def get_config(key: str, default: Any = None) -> Any:
    """
    获取单个配置项

    Args:
        key: 配置键名
        default: 默认值

    Returns:
        配置值，如果不存在返回默认值
    """
    config = load_config()
    return config.get(key, default)


def mask_password(password: str) -> str:
    """密码脱敏

    - 长度 >= 5: 前2位 + *** + 后2位（如：Yt***11）
    - 长度 < 5: ***
    """
    if len(password) < 5:
        return "***"
    return f"{password[:2]}***{password[-2:]}"


def print_config():
    """打印当前配置（隐藏密码）"""
    config = load_config()

    print("═══════════════════════════════════════════════════════════")
    print("📧 悟空邮件工具包 - 当前配置")
    print("═══════════════════════════════════════════════════════════")

    print(f"📮 邮箱地址: {config['email']}")
    password = config['email_password']
    if password:
        masked = mask_password(password)
        print(f"🔑 邮箱密码: {masked}")
    else:
        print(f"🔑 邮箱密码: (未配置)")

    print()
    print("📤 SMTP 配置:")
    print(f"   服务器: {config['smtp_host']}:{config['smtp_port']}")
    print(f"   SSL: {'启用' if config['smtp_use_ssl'] else '禁用'}")
    print(f"   验证证书: {'是' if config['smtp_ssl_verify'] else '否（适用于自签名或私有 CA 证书）'}")
    print(f"   加密套件: {config['smtp_ssl_ciphers']}")

    print()
    print("📥 IMAP 配置:")
    print(f"   服务器: {config['imap_host']}:{config['imap_port']}")
    print(f"   SSL: {'启用' if config['imap_use_ssl'] else '禁用'}")
    print(f"   验证证书: {'是' if config['imap_ssl_verify'] else '否（适用于自签名或私有 CA 证书）'}")
    print(f"   加密套件: {config['imap_ssl_ciphers']}")

    if config['from_name']:
        print(f"   发件人名称: {config['from_name']}")

    print("═══════════════════════════════════════════════════════════")


# 命令行测试
if __name__ == '__main__':
    print_config()
