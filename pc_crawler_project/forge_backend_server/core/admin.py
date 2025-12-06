from django.contrib import admin
from .models import Product, PriceHistory, ProductReview

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # === [關鍵修改] 在列表顯示分類 ===
    list_display = ('id', 'category', 'name', 'last_updated')
    
    # 增加過濾器：可以用「分類」來篩選 (例如只看主機板)
    list_filter = ('category', 'last_updated')
    
    search_fields = ('name', 'id')
    ordering = ('name',)

@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'price', 'crawled_at')
    list_filter = ('crawled_at',)
    search_fields = ('product__name',)

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('product__name', 'user__username', 'comment')