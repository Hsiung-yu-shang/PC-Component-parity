from django.core.management.base import BaseCommand
from core import services


class Command(BaseCommand):
    help = "同步商品資料：抓取 PChome 最新資料、更新價格、標記下架商品。"

    def add_arguments(self, parser):
        parser.add_argument(
            '--keyword', action='append', dest='keywords',
            help='只同步指定關鍵字，可重複帶多次 --keyword。不帶則使用預設監控清單。'
        )
        parser.add_argument(
            '--max-pages', type=int, default=2,
            help='每個關鍵字抓幾頁，預設 2。'
        )

    def handle(self, *args, **options):
        keywords = options.get('keywords')
        max_pages = options.get('max_pages')

        self.stdout.write(self.style.NOTICE(
            f"=== 開始同步：{len(keywords) if keywords else '預設監控清單'} ==="
        ))

        summary = services.sync_products(keywords=keywords, max_pages=max_pages)

        self.stdout.write(self.style.SUCCESS(
            "同步完成："
            f"掃描 {summary['scanned']} 筆、"
            f"新增 {summary['new_products']}、"
            f"價格更新 {summary['price_updated']}、"
            f"下架 {summary['delisted']}、"
            f"耗時 {summary['duration_seconds']} 秒"
        ))
