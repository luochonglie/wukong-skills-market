"""
Wukong Email 测试共享 fixtures
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 将 skill scripts 目录加入 path，以便导入模块
SKILL_DIR = Path(__file__).parent.parent.parent.parent / "skills" / "wukong-email" / "scripts"
sys.path.insert(0, str(SKILL_DIR))


@pytest.fixture
def sample_config():
    """标准测试配置"""
    return {
        'email': 'test@example.com',
        'email_password': 'testpass',
        'imap_host': 'imap.example.com',
        'imap_port': 993,
        'imap_ssl_verify': False,
    }


@pytest.fixture
def mock_imap():
    """
    模拟 IMAP 连接对象。

    使用方式：在测试中 patch IMAP4_SSL 返回此 mock，或直接注入。
    """
    imap = MagicMock()
    imap.login.return_value = ('OK', [b'Logged in'])
    imap.select.return_value = ('OK', [b'1'])
    imap.close.return_value = ('OK', [b''])
    imap.logout.return_value = ('OK', [b''])
    return imap
