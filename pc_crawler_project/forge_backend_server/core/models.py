from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

class Product(models.Model):
    """商品主檔 (對應 products 表)"""
    id = models.CharField(max_length=64, primary_key=True, verbose_name="PChome ID")
    
    # 優化 1: 移除 db_index=True，因為下面 Meta 已經有 indexes 定義了，避免重複
    name = models.CharField(max_length=255, verbose_name="商品名稱")
    
    pic_url = models.URLField(max_length=512, blank=True, null=True, verbose_name="圖片連結")
    description = models.TextField(blank=True, null=True, verbose_name="商品描述")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="最後更新時間")

    # === [補回] 智慧規格分析欄位 ===
    CATEGORY_CHOICES = [
        ('MB', '主機板'),
        ('CPU', '處理器'),
        ('RAM', '記憶體'),
        ('GPU', '顯示卡'),
        ('SSD', '固態硬碟'),    # 改個名字比較清楚
        ('HDD', '傳統硬碟'),    # <--- 新增這個
        ('PSU', '電源供應器'),  # <--- 新增這個
        ('CASE', '機殼'),      # (選用) 順便加個機殼，未來可以用
        ('OTHER', '其他'),
    ]
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='OTHER', verbose_name="零件分類")
    
    # JSON 欄位：用來存 {"memory": "DDR5", "socket": "LGA1700"}
    specs = models.JSONField(default=dict, blank=True, verbose_name="規格參數 (JSON)")

    # === 上下架狀態 ===
    # 爬蟲同步時，如果 PChome 已經找不到這個商品，就把 is_active 設 False，
    # 而不是直接刪除，這樣歷史價格紀錄跟評論才不會跟著消失。
    is_active = models.BooleanField(default=True, verbose_name="是否仍在架上")
    delisted_at = models.DateTimeField(null=True, blank=True, verbose_name="下架時間")

    class Meta:
        db_table = 'products'
        verbose_name = "電腦零件"
        verbose_name_plural = "電腦零件列表"
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']), # 這裡定義索引就夠了
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"[{self.get_category_display()}] {self.name}"

class PriceHistory(models.Model):
    """價格歷史 (對應 price_history 表)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_history')
    price = models.PositiveIntegerField(verbose_name="價格")
    crawled_at = models.DateTimeField(auto_now_add=True, verbose_name="爬取時間")

    class Meta:
        db_table = 'price_history'
        verbose_name = "價格紀錄"
        verbose_name_plural = "價格紀錄表"
        ordering = ['-crawled_at']
        indexes = [
            models.Index(fields=['product', 'crawled_at']),
        ]

    def __str__(self):
        return f"{self.product.name} - ${self.price}"

class ProductReview(models.Model):
    """
    商品評價系統 (對應 評分機制)
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews', verbose_name="商品")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="使用者")
    
    RATING_CHOICES = [
        (1, '★☆☆☆☆ (1分)'),
        (2, '★★☆☆☆ (2分)'),
        (3, '★★★☆☆ (3分)'),
        (4, '★★★★☆ (4分)'),
        (5, '★★★★★ (5分)'),
    ]
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES,
        default=5,
        verbose_name="評分",
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    comment = models.TextField(blank=True, verbose_name="評論內容")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="評論時間")

    class Meta:
        db_table = 'product_reviews'
        verbose_name = "商品評價"
        verbose_name_plural = "商品評價列表"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({self.rating}星)"