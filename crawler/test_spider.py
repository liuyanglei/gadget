import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crawler import spider


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'news.json'
        self.article = {'id': 'old', 'title': '企业公告', 'category': 'A股公告',
                        'source': '上海证券交易所', 'content': '正文' * 100,
                        'published_at': '2026-09-24T12:00:00+08:00', 'attachment_stats': {'pages': 1}}
        self.old_time = '2026-09-24T04:00:00Z'
        self.output.write_text(json.dumps({'articles': [self.article], 'updated_at': self.old_time}), encoding='utf-8')

    def run_collector(self, entries, extracted):
        with patch.object(spider, 'OUTPUT', self.output), \
             patch.object(spider, 'discover_sse', return_value=entries), \
             patch.object(spider, 'extract_sse', return_value=extracted), \
             patch.object(spider, 'discover_miit', return_value=['https://example.org/old']), \
             patch.object(spider, 'extract_miit', return_value=None):
            spider.main()

    def test_no_change_preserves_content_timestamp(self):
        self.run_collector([], None)
        payload = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(payload['updated_at'], self.old_time)
        self.assertEqual(payload['new_articles'], 0)
        self.assertTrue(payload['last_successful_check_at'])

    def test_all_new_pdf_fail_reports_failure_and_keeps_old_data(self):
        with self.assertRaises(RuntimeError):
            self.run_collector([{'id': 'new'}], None)
        payload = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(payload['articles'], [self.article])
        self.assertEqual(payload['updated_at'], self.old_time)
        self.assertEqual(payload['source_status']['sse']['status'], 'failed')

    def test_success_counts_new_article(self):
        article = dict(self.article, id='new', title='新增企业公告')
        self.run_collector([{'id': 'new'}], article)
        payload = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(payload['new_articles'], 1)
        self.assertNotEqual(payload['updated_at'], self.old_time)


if __name__ == '__main__':
    unittest.main()
