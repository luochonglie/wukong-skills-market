"""
测试 mark_read.py - 标记邮件已读

重点验证：
- 使用 uid('STORE') 而非 store()，确保按 UID 操作
- 使用 uid('SEARCH') 而非 search()，确保返回 UID 而非序号
- 分批标记逻辑
- 空结果处理
"""

from unittest.mock import MagicMock, patch, call

import pytest


class TestMarkReadUsesUID:
    """验证 mark_read 使用 UID 命令而非序号命令"""

    @patch('mark_read.load_config')
    @patch('mark_read.imaplib.IMAP4_SSL')
    def test_store_uses_uid_not_sequence(self, mock_imap_cls, mock_load_config, sample_config, mock_imap):
        """imap.store() 应替换为 imap.uid('STORE', ...)，按 UID 操作"""
        mock_load_config.return_value = sample_config
        mock_imap_cls.return_value = mock_imap
        mock_imap.uid.side_effect = [
            ('OK', [b'100 101']),  # uid SEARCH 验证
            ('OK', [b'']),          # uid STORE
        ]

        from mark_read import mark_read
        result = mark_read(sample_config, uids='100,101')

        # 必须调用 uid('STORE', ...) 而非 store()
        mock_imap.store.assert_not_called()
        mock_imap.uid.assert_any_call('STORE', '100,101', '+FLAGS', '\\Seen')
        assert result['success'] == 2

    @patch('mark_read.load_config')
    @patch('mark_read.imaplib.IMAP4_SSL')
    def test_search_uses_uid_search(self, mock_imap_cls, mock_load_config, sample_config, mock_imap):
        """搜索条件分支应使用 uid('SEARCH') 返回 UID"""
        mock_load_config.return_value = sample_config
        mock_imap_cls.return_value = mock_imap
        # uid('SEARCH', ...) 返回 UID
        mock_imap.uid.side_effect = [
            ('OK', [b'200 201 202']),  # uid SEARCH
            ('OK', [b'']),              # uid STORE batch 1
            ('OK', [b'']),              # uid STORE batch 2
        ]

        from mark_read import mark_read
        result = mark_read(sample_config, search_criteria='UNSEEN')

        # 必须调用 uid('SEARCH') 而非 search()
        mock_imap.search.assert_not_called()
        mock_imap.uid.assert_any_call('SEARCH', None, 'UNSEEN'.encode('utf-8'))
        assert result['total'] == 3

    @patch('mark_read.load_config')
    @patch('mark_read.imaplib.IMAP4_SSL')
    def test_uids_param_validates_existence(self, mock_imap_cls, mock_load_config, sample_config, mock_imap):
        """传入 --uids 时应通过 uid SEARCH 验证 UID 存在"""
        mock_load_config.return_value = sample_config
        mock_imap_cls.return_value = mock_imap
        mock_imap.uid.side_effect = [
            ('OK', [b'100']),  # uid SEARCH 验证，只有 100 存在
            ('OK', [b'']),     # uid STORE
        ]

        from mark_read import mark_read
        result = mark_read(sample_config, uids='100,999')

        # 只标记验证存在的 UID
        assert result['total'] == 1
        mock_imap.uid.assert_any_call('STORE', '100', '+FLAGS', '\\Seen')


class TestMarkReadBatch:
    """分批标记逻辑"""

    @patch('mark_read.load_config')
    @patch('mark_read.imaplib.IMAP4_SSL')
    def test_batch_split(self, mock_imap_cls, mock_load_config, sample_config, mock_imap):
        """超过 batch_size 时应分批调用"""
        mock_load_config.return_value = sample_config
        mock_imap_cls.return_value = mock_imap

        # 生成 5 个 UID，batch_size=2 应拆成 3 批
        uids = ','.join(str(i) for i in range(1, 6))
        mock_imap.uid.side_effect = [
            ('OK', [b'1 2 3 4 5']),  # uid SEARCH 验证
            ('OK', [b'']),            # batch 1: 1,2
            ('OK', [b'']),            # batch 2: 3,4
            ('OK', [b'']),            # batch 3: 5
        ]

        from mark_read import mark_read
        result = mark_read(sample_config, uids=uids, batch_size=2)

        assert result['success'] == 5
        store_calls = [c for c in mock_imap.uid.call_args_list
                       if c[0][0] == 'STORE']
        assert len(store_calls) == 3
        assert store_calls[0] == call('STORE', '1,2', '+FLAGS', '\\Seen')
        assert store_calls[1] == call('STORE', '3,4', '+FLAGS', '\\Seen')
        assert store_calls[2] == call('STORE', '5', '+FLAGS', '\\Seen')


class TestMarkReadEdgeCases:
    """边界情况"""

    @patch('mark_read.load_config')
    @patch('mark_read.imaplib.IMAP4_SSL')
    def test_empty_search_result(self, mock_imap_cls, mock_load_config, sample_config, mock_imap):
        """搜索无结果应返回全零"""
        mock_load_config.return_value = sample_config
        mock_imap_cls.return_value = mock_imap
        mock_imap.uid.return_value = ('OK', [b''])

        from mark_read import mark_read
        result = mark_read(sample_config, search_criteria='UNSEEN')

        assert result == {'success': 0, 'fail': 0, 'total': 0}

    @patch('mark_read.load_config')
    @patch('mark_read.imaplib.IMAP4_SSL')
    def test_store_failure_counted_as_fail(self, mock_imap_cls, mock_load_config, sample_config, mock_imap):
        """STORE 失败应计入 fail"""
        mock_load_config.return_value = sample_config
        mock_imap_cls.return_value = mock_imap
        mock_imap.uid.side_effect = [
            ('OK', [b'100 101']),  # uid SEARCH
            ('NO', [b'']),          # uid STORE 失败
        ]

        from mark_read import mark_read
        result = mark_read(sample_config, uids='100,101')

        assert result['fail'] == 2
        assert result['success'] == 0
