"""Legacy import: use the maintained adapter and the shared synchronization guard.

New integrations should call manage.py sync_products instead.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'forge_backend_server'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'forge_backend_server.settings')
import django
django.setup()
from core.crawler import PChomeSpider as MaintainedSpider
from core.sync_state import reserve_sync, finish_sync


class PChomeSpider(MaintainedSpider):
    def run(self, keyword, max_pages=1):
        if not 1 <= max_pages <= 5:
            raise ValueError('max_pages must be between 1 and 5')
        with reserve_sync():
            try:
                yield from super().run(keyword, max_pages)
                finish_sync(state='done', summary={'scanned': 0, 'price_updated': 0, 'sources': {}})
            except BaseException:
                finish_sync(state='error', error='舊版命令列查詢中斷。')
                raise
