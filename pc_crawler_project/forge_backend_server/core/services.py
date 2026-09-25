"""
商品同步服務。

這支模組是「手動同步 API」與「排程爬蟲指令」共用的核心邏輯，
兩邊都呼叫 sync_products()，避免同一套規則要維護兩份程式碼。

同步邏輯：
1. 依 WATCH_LIST 呼叫 PChomeSpider，並讀取原價屋公開估價頁。
2. 商品主檔用 update_or_create 寫入/更新（名稱、圖片、規格等）。
3. 價格只有在跟「上一筆歷史價格」不同時才新增一筆 PriceHistory，
   避免同一個價格每次爬蟲都重複塞一筆一樣的紀錄。
4. 這次同步範圍內「有抓到」的商品，一律確保 is_active=True（重新上架）。
5. 原價屋完整抓取且數量未大幅下降時，將缺席商品標記下架。
   PChome 是關鍵字與頁數取樣，無法安全推斷商品已下架。
"""
import logging
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from django.db import transaction
from django.utils import timezone

from .crawler import PChomeSpider
from .coolpc import CoolPCSpider, SourceUnavailable
from .sync_state import reserve_sync, finish_sync
from django.core.cache import cache
from .models import Product, PriceHistory

logger = logging.getLogger(__name__)

# 預設監控關鍵字清單（原本 batch_job.py 裡的 WATCH_LIST）
DEFAULT_WATCH_LIST = [
    "RTX4090", "RTX4080", "RTX4070", "RTX4060",
    "Intel i9-14900K", "Intel i7-14700K", "Intel",
    "AMD Ryzen 9", "AMD Ryzen 7", "AMD",
    "Z790", "B760",
    "DDR5 64G", "DDR5 32G", "DDR",
    "SSD 2TB", "SSD 4TB", "SSD",
    "850W 金牌", "1000W 電源", "海韻 850W", "振華 750W", "電源供應器",
    "HDD 4TB", "HDD 6TB", "HDD", "Seagate 8TB", "WD 8TB",
]


@transaction.atomic
def _save_product(item: Dict, seen_ids: set) -> str:
    """
    寫入單一商品，回傳這筆商品的處理結果：
    'new'（新商品）/ 'price_updated'（價格變動）/ 'unchanged'（沒變化，但確認仍上架）

    用 @transaction.atomic 包住「更新商品主檔」+「寫入價格歷史」這兩步，
    確保這兩個寫入是同進同出，不會只成功一半。
    """
    prod_obj, created = Product.objects.update_or_create(
        id=item['id'],
        defaults={
            'name': item['name'],
            'source': item.get('source', 'pchome'),
            'product_url': item.get('product_url', ''),
            'pic_url': item['picS'],
            'description': item['describe'],
            'category': item.get('category', 'OTHER'),
            'specs': item.get('specs', {}),
            'is_active': True,       # 這次爬蟲有抓到 = 確定還在架上
            'delisted_at': None,     # 如果之前被標記下架過，重新上架就清空下架時間
        }
    )
    seen_ids.add(prod_obj.id)

    latest = prod_obj.price_history.order_by('-crawled_at').first()
    if latest is None or latest.price != item['price']:
        PriceHistory.objects.create(product=prod_obj, price=item['price'])
        return 'new' if created else 'price_updated'

    return 'unchanged'


def _sync_products(keywords: Optional[Iterable[str]] = None, max_pages: int = 2,
                  sources: Optional[Iterable[str]] = None) -> Dict:
    """
    執行一次完整同步。

    keywords: 要爬取的關鍵字清單，預設用 DEFAULT_WATCH_LIST。
    max_pages: 每個關鍵字抓幾頁。

    回傳同步結果摘要 dict，方便 API / 指令列印或回傳給前端。
    """
    started_at = timezone.now()
    keyword_list = list(keywords) if keywords is not None else DEFAULT_WATCH_LIST

    enabled_sources = set(sources or ('pchome', 'coolpc'))
    if not enabled_sources or enabled_sources - {'pchome', 'coolpc'}:
        raise ValueError('sources 必須為 pchome 或 coolpc')
    stats = {'new': 0, 'price_updated': 0, 'unchanged': 0, 'scanned': 0}
    source_stats = {}

    for source in ('pchome', 'coolpc'):
        if source not in enabled_sources:
            continue
        seen_ids = set()
        if source == 'pchome':
            spider = PChomeSpider()
            items = (item for keyword in keyword_list
                     for item in spider.run(keyword, max_pages=max_pages))
        else:
            spider = CoolPCSpider()
            items = spider.run()
        try:
            for item in items:
                result = _save_product(item, seen_ids)
                stats[result] += 1
                stats['scanned'] += 1
        except SourceUnavailable:
            logger.warning('原價屋同步已暫停，保留既有資料。', exc_info=True)
            source_stats[source] = {'scanned': 0, 'delisted': 0, 'state': 'backoff'}
            continue
        # A failed/empty scrape must never delist a complete source. A limited
        # keyword sync is also not evidence that all other products disappeared.
        delisted = 0
        existing_count = Product.objects.filter(source=source, is_active=True).count()
        if (source == 'coolpc' and len(seen_ids) >= 50
                and (existing_count == 0 or len(seen_ids) >= existing_count * 0.8)):
            delisted = Product.objects.filter(source=source, is_active=True).exclude(
                id__in=seen_ids).update(is_active=False, delisted_at=timezone.now())
        source_stats[source] = {'scanned': len(seen_ids), 'delisted': delisted,
                                'state': 'cached' if getattr(spider, 'skipped', False) else 'updated'}
        for category, _ in Product.CATEGORY_CHOICES:
            cache.delete(f'comparison-v1:{source}:{category}')

    finished_at = timezone.now()
    summary = {
        'started_at': started_at.isoformat(),
        'finished_at': finished_at.isoformat(),
        'duration_seconds': round((finished_at - started_at).total_seconds(), 1),
        'keywords_synced': len(keyword_list),
        'scanned': stats['scanned'],
        'new_products': stats['new'],
        'price_updated': stats['price_updated'],
        'unchanged': stats['unchanged'],
        'delisted': sum(value['delisted'] for value in source_stats.values()),
        'sources': source_stats,
    }
    logger.info("[sync_products] %s", summary)
    return summary


def sync_products(keywords=None, max_pages=2, sources=None, reservation=None):
    handle = reservation if reservation is not None else reserve_sync()
    with handle:
        try:
            summary = _sync_products(keywords, max_pages, sources)
            finish_sync(state='done', summary=summary)
            return summary
        except Exception:
            finish_sync(state='error', error='同步失敗，請管理員查看服務紀錄。')
            raise
