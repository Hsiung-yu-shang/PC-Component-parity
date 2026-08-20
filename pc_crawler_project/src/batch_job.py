import os
import sys
import django
from pathlib import Path
from datetime import datetime
from pchome_core import PChomeSpider

# === 1. 設定 Django 環境 ===
# 以這個檔案的位置為基準，自動推算出 forge_backend_server 的路徑，
# 這樣不管在哪台機器、哪個帳號底下 clone 這個 repo 都能正常運作。
PROJECT_PATH = Path(__file__).resolve().parent.parent / 'forge_backend_server'
sys.path.append(str(PROJECT_PATH))

# 指定 Django 設定檔
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'forge_backend_server.settings')

# 啟動 Django
try:
    django.setup()
except Exception as e:
    print(f"[Error] Django Setup Failed: {e}")
    sys.exit(1)

# === 2. 匯入 Models ===
from core.models import Product, PriceHistory

# === 3. 設定監控清單 ===
WATCH_LIST = [
    "RTX4090", "RTX4080", "RTX4070", "RTX4060",
    "Intel i9-14900K", "Intel i7-14700K","Intel",
    "AMD Ryzen 9", "AMD Ryzen 7","AMD",
    "Z790", "B760",
    "DDR5 64G", "DDR5 32G","DDR",
    "SSD 2TB", "SSD 4TB","SSD",
    "850W 金牌", "1000W 電源", "海韻 850W", "振華 750W","電源供應器",
    "HDD 4TB","HDD 6TB","HDD","Seagate 8TB","WD 8TB"
]

def save_to_django(products_list):
    """使用 Django ORM 寫入資料庫"""
    print(f"  [DB] 正在寫入 {len(products_list)} 筆資料...", end="")
    
    count_new = 0
    count_history = 0
    
    for item in products_list:
        # 1. 處理商品主檔 (Update or Create)
        # 這裡增加了 category 和 specs 的寫入
        prod_obj, created = Product.objects.update_or_create(
            id=item['id'],
            defaults={
                'name': item['name'],
                'pic_url': item['picS'],
                'description': item['describe'],
                
                # === [新增] 寫入分類與規格 ===
                # 使用 .get() 避免舊版爬蟲沒回傳這些欄位時報錯
                'category': item.get('category', 'OTHER'),
                'specs': item.get('specs', {}) 
            }
        )
        if created:
            count_new += 1
        
        # 2. 新增價格歷史紀錄 (Insert)
        PriceHistory.objects.create(
            product=prod_obj,
            price=item['price']
        )
        count_history += 1
        
    print(f" 完成！ (新增商品: {count_new}, 新增價格紀錄: {count_history})")

if __name__ == "__main__":
    print(f"=== 排程開始: {datetime.now()} ===")
    spider = PChomeSpider()
    
    for keyword in WATCH_LIST:
        print(f"正在爬取: {keyword} ...")
        products = []
        
        # 每個關鍵字爬取前 2 頁
        for p in spider.run(keyword, max_pages=2):
            products.append(p)
        
        if products:
            save_to_django(products)
        else:
            print(f"  {keyword}: 無符合資料 (可能被過濾或無庫存)")
            
    print(f"=== 排程結束: {datetime.now()} ===")