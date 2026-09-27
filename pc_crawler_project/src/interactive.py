"""Read existing local prices interactively; querying never crawls retailers."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'forge_backend_server'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'forge_backend_server.settings')
import django
django.setup()
from django.db.models import OuterRef, Subquery
from core.models import Product, PriceHistory

if __name__ == '__main__':
    print('電腦零件查詢：讀取既有資料庫，每次最多 20 筆；q 離開。')
    while True:
        try:
            keyword = input('關鍵字：').strip()[:200]
        except (EOFError, KeyboardInterrupt):
            break
        if keyword.lower() == 'q':
            break
        if not keyword:
            continue
        latest = PriceHistory.objects.filter(product_id=OuterRef('pk')).order_by('-crawled_at', '-pk')
        products = Product.objects.filter(is_active=True, name__icontains=keyword).annotate(
            price=Subquery(latest.values('price')[:1]))[:20]
        for product in products:
            print(f'{product.source} | {product.name} | NT$ {product.price if product.price is not None else "尚無報價"}')
