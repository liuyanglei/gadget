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
             patch.object(spider, 'extract_miit', return_value=None), \
             patch.object(spider, 'collect_official_sources', return_value=([], {})):
            spider.main()

    def test_no_change_preserves_content_timestamp(self):
        self.run_collector([], None)
        payload = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(payload['updated_at'], self.old_time)
        self.assertEqual(payload['new_articles'], 0)
        self.assertTrue(payload['last_successful_check_at'])

    def test_unreadable_pdf_is_rejected_without_losing_old_data(self):
        self.run_collector([{'id': 'new'}], None)
        payload = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(payload['articles'], [self.article])
        self.assertEqual(payload['updated_at'], self.old_time)
        self.assertEqual(payload['source_status']['sse']['status'], 'ok')
        self.assertEqual(payload['source_status']['sse']['rejected'], 1)

    def test_success_counts_new_article(self):
        article = dict(self.article, id='new', title='新增企业公告')
        self.run_collector([{'id': 'new'}], article)
        payload = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(payload['new_articles'], 1)
        self.assertNotEqual(payload['updated_at'], self.old_time)

    def test_official_backfill_categories_survive_next_run(self):
        sources = [
            ('国家统计局', '宏观数据'),
            ('中国证监会', '监管动态'),
            ('中国证监会', '政策解读'),
            ('中华人民共和国财政部', '政策解读'),
        ]
        articles = [dict(self.article, id=str(index), source=source, category=category,
                         title=f'官方材料{index}', attachment_stats={'attachments': 0})
                    for index, (source, category) in enumerate(sources)]
        self.output.write_text(json.dumps({'articles': articles}), encoding='utf-8')
        with patch.object(spider, 'OUTPUT', self.output):
            loaded = spider.load_previous()
        self.assertEqual([item['category'] for item in loaded], [category for _, category in sources])


if __name__ == '__main__':
    unittest.main()
