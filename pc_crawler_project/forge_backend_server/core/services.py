"""
商品同步服務。

這支模組是「手動同步 API」與「排程爬蟲指令」共用的核心邏輯，
兩邊都呼叫 sync_products()，避免同一套規則要維護兩份程式碼。

同步邏輯：
1. 依 WATCH_LIST 逐一關鍵字呼叫 PChomeSpider 抓取。
2. 商品主檔用 update_or_create 寫入/更新（名稱、圖片、規格等）。
3. 價格只有在跟「上一筆歷史價格」不同時才新增一筆 PriceHistory，
   避免同一個價格每次爬蟲都重複塞一筆一樣的紀錄。
4. 這次同步範圍內「有抓到」的商品，一律確保 is_active=True（重新上架）。
5. 這次同步範圍內，資料庫裡「原本是上架狀態、但這次沒抓到」的商品，
   視為下架：is_active=False，並記錄 delisted_at 時間。
   （不會真的刪除，歷史價格與評論都會保留。）
"""
import logging
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from django.db import transaction
from django.utils import timezone

from .crawler import PChomeSpider
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


def sync_products(keywords: Optional[Iterable[str]] = None, max_pages: int = 2) -> Dict:
    """
    執行一次完整同步。

    keywords: 要爬取的關鍵字清單，預設用 DEFAULT_WATCH_LIST。
    max_pages: 每個關鍵字抓幾頁。

    回傳同步結果摘要 dict，方便 API / 指令列印或回傳給前端。
    """
    started_at = timezone.now()
    keyword_list = list(keywords) if keywords is not None else DEFAULT_WATCH_LIST

    spider = PChomeSpider()
    seen_ids = set()
    stats = {'new': 0, 'price_updated': 0, 'unchanged': 0, 'scanned': 0}

    for keyword in keyword_list:
        for item in spider.run(keyword, max_pages=max_pages):
            result = _save_product(item, seen_ids)
            stats[result] += 1
            stats['scanned'] += 1

    # 這次同步範圍內，原本上架、但這次完全沒抓到的商品 → 標記下架
    delisted_qs = Product.objects.filter(is_active=True).exclude(id__in=seen_ids)
    delisted_count = delisted_qs.update(is_active=False, delisted_at=timezone.now())

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
        'delisted': delisted_count,
    }
    logger.info("[sync_products] %s", summary)
    return summary
