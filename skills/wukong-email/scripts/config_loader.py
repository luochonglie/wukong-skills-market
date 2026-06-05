#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wukong Email Config Loader (Simplified)
========================================
Loads config from ~/.wukong-email/.env file only; does not need config.yaml

Priority order:
1. System environment variables
2. ~/.wukong-email/.env file
3. Code defaults

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

# Module-level cache
_cached_config: Optional[Dict[str, Any]] = None
CONFIG_DIR = Path.home() / '.wukong-email'
ENV_FILE = CONFIG_DIR / '.env'


def find_env_file() -> Optional[Path]:
    """
    Find user-level .env file.
    Returns Path object, or None if not found.
    """
    return ENV_FILE if ENV_FILE.exists() else None


def load_dotenv(env_path: Optional[Path] = None) -> Dict[str, str]:
    """
    Load .env file and return a dict.
    Simple implementation (does not require python-dotenv).

    Args:
        env_path: Path to .env file. If None, uses ~/.wukong-email/.env

    Returns:
        Environment variable dict
    """
    if env_path is None:
        env_path = find_env_file()

    if env_path is None or not env_path.exists():
        return {}

    env_vars = {}
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and blank lines
            if not line or line.startswith('#'):
                continue

            # Parse KEY=VALUE or KEY="VALUE"
            match = re.match(r'^([A-Z_][A-Z0-9_]*)=(.*)$', line)
            if match:
                key, value = match.groups()
                # Remove quotes (if any)
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                env_vars[key] = value

    return env_vars


def str_to_bool(value: str) -> bool:
    """Convert string to boolean value"""
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
    """Check if config is empty or still a template placeholder value"""
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
    Load config (from environment variables or ~/.wukong-email/.env file)

    Args:
        email: Email address (optional, overrides config)
        password: Email password (optional, overrides config)
        smtp_host: SMTP server (optional, overrides config)
        smtp_port: SMTP port (optional, overrides config)
        imap_host: IMAP server (optional, overrides config)
        imap_port: IMAP port (optional, overrides config)
        force_reload: Force reload (ignores cache)

    Returns:
        Config dict
    """
    global _cached_config

    # Use cache (if present and not forced to reload)
    if _cached_config is not None and not force_reload:
        # Apply parameter overrides
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

    # 1. Load from user-level .env file
    env_vars = load_dotenv()

    # 2. Priority: env vars > ~/.wukong-email/.env > defaults (non-sensitive fields only)
    config = {
        # Email credentials (required, no default)
        'email': os.getenv('EMAIL_ADDRESS') or env_vars.get('EMAIL_ADDRESS', ''),
        'email_password': os.getenv('EMAIL_PASSWORD') or env_vars.get('EMAIL_PASSWORD', ''),

        # SMTP config (required, no default)
        'smtp_host': os.getenv('EMAIL_SMTP_HOST') or env_vars.get('EMAIL_SMTP_HOST', ''),
        'smtp_port': int(os.getenv('EMAIL_SMTP_PORT') or env_vars.get('EMAIL_SMTP_PORT', '465')),
        'smtp_use_ssl': str_to_bool(os.getenv('EMAIL_SMTP_USE_SSL') or env_vars.get('EMAIL_SMTP_USE_SSL', 'true')),
        'smtp_ssl_verify': str_to_bool(os.getenv('EMAIL_SMTP_SSL_VERIFY') or env_vars.get('EMAIL_SMTP_SSL_VERIFY', 'false')),
        'smtp_ssl_ciphers': os.getenv('EMAIL_SMTP_SSL_CIPHERS') or env_vars.get('EMAIL_SMTP_SSL_CIPHERS',
            'ECDHE-RSA-AES256-GCM-SHA384:AES256-GCM-SHA384'),

        # IMAP config (required, no default)
        'imap_host': os.getenv('EMAIL_IMAP_HOST') or env_vars.get('EMAIL_IMAP_HOST', ''),
        'imap_port': int(os.getenv('EMAIL_IMAP_PORT') or env_vars.get('EMAIL_IMAP_PORT', '993')),
        'imap_use_ssl': str_to_bool(os.getenv('EMAIL_IMAP_USE_SSL') or env_vars.get('EMAIL_IMAP_USE_SSL', 'true')),
        'imap_ssl_verify': str_to_bool(os.getenv('EMAIL_IMAP_SSL_VERIFY') or env_vars.get('EMAIL_IMAP_SSL_VERIFY', 'false')),
        'imap_ssl_ciphers': os.getenv('EMAIL_IMAP_SSL_CIPHERS') or env_vars.get('EMAIL_IMAP_SSL_CIPHERS',
            'ECDHE-RSA-AES256-GCM-SHA384:AES256-GCM-SHA384'),

        # Optional: sender display name
        'from_name': os.getenv('EMAIL_FROM_NAME') or env_vars.get('EMAIL_FROM_NAME', ''),

        # Sent folder config
        'enable_save_to_sent': str_to_bool(os.getenv('EMAIL_ENABLE_SAVE_TO_SENT') or env_vars.get('EMAIL_ENABLE_SAVE_TO_SENT', 'true')),
        'sent_folder': os.getenv('EMAIL_SENT_FOLDER') or env_vars.get('EMAIL_SENT_FOLDER', 'Sent'),

        # Attachment download directory config
        'attachments_dir': os.getenv('EMAIL_ATTACHMENTS_DIR') or env_vars.get('EMAIL_ATTACHMENTS_DIR', '~/.wukong-email/attachments'),
    }

    # 3. Parameter overrides (highest priority)
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

    # 4. Validate required config (raise on missing)
    required_fields = {
        'EMAIL_ADDRESS': config['email'],
        'EMAIL_PASSWORD': config['email_password'],
        'EMAIL_SMTP_HOST': config['smtp_host'],
        'EMAIL_IMAP_HOST': config['imap_host'],
    }

    missing_fields = [field for field, value in required_fields.items() if is_unset_or_placeholder(value)]

    if missing_fields:
        print("Error: Missing required config fields, or config still has template placeholder values!")
        print(f"   Need to update: {', '.join(missing_fields)}")
        print()
        print("Please configure the following in ~/.wukong-email/.env:")
        print()
        print("   # Email credentials (required)")
        print("   EMAIL_ADDRESS=your-email@example.com")
        print("   EMAIL_PASSWORD=your-password")
        print()
        print("   # SMTP config (required)")
        print("   EMAIL_SMTP_HOST=smtp.example.com")
        print()
        print("   # IMAP config (required)")
        print("   EMAIL_IMAP_HOST=imap.example.com")
        print()
        raise SystemExit(1)

    # 5. Cache config
    _cached_config = config

    return config


def get_config(key: str, default: Any = None) -> Any:
    """
    Get a single config item

    Args:
        key: Config key name
        default: Default value

    Returns:
        Config value, or default if not found
    """
    config = load_config()
    return config.get(key, default)


def mask_password(password: str) -> str:
    """Mask password for display

    - Length >= 5: first 2 chars + *** + last 2 chars (e.g. Yt***11)
    - Length < 5: ***
    """
    if len(password) < 5:
        return "***"
    return f"{password[:2]}***{password[-2:]}"


def print_config():
    """Print current config (with password masked)"""
    config = load_config()

    print("===========================================================")
    print("Wukong Email Toolkit - Current config")
    print("===========================================================")

    print(f"Email address: {config['email']}")
    password = config['email_password']
    if password:
        masked = mask_password(password)
        print(f"Email password: {masked}")
    else:
        print("Email password: (not configured)")

    print()
    print("SMTP config:")
    print(f"   Server: {config['smtp_host']}:{config['smtp_port']}")
    print(f"   SSL: {'Enabled' if config['smtp_use_ssl'] else 'Disabled'}")
    print(f"   Verify certificate: {'Yes' if config['smtp_ssl_verify'] else 'No (for self-signed or private CA certificates)'}")
    print(f"   Cipher suite: {config['smtp_ssl_ciphers']}")

    print()
    print("IMAP config:")
    print(f"   Server: {config['imap_host']}:{config['imap_port']}")
    print(f"   SSL: {'Enabled' if config['imap_use_ssl'] else 'Disabled'}")
    print(f"   Verify certificate: {'Yes' if config['imap_ssl_verify'] else 'No (for self-signed or private CA certificates)'}")
    print(f"   Cipher suite: {config['imap_ssl_ciphers']}")

    if config['from_name']:
        print(f"   Sender name: {config['from_name']}")

    print("===========================================================")


# CLI test
if __name__ == '__main__':
    print_config()
