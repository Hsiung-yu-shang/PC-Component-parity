from rest_framework import serializers
from .models import Product, PriceHistory, ProductReview

class PriceHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceHistory
        fields = ['price', 'crawled_at']

class ProductReviewSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()  # 顯示使用者名稱而不是 ID
    class Meta:
        model = ProductReview
        fields = ['user', 'rating', 'comment', 'created_at']

class ProductSerializer(serializers.ModelSerializer):
    # 巢狀顯示：把該商品的歷史價格和評論也一起包進去
    price_history = PriceHistorySerializer(many=True, read_only=True)
    reviews = ProductReviewSerializer(many=True, read_only=True)
    
    # 增加一個欄位顯示「最新價格」，方便前端列表顯示
    latest_price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'category', 'name', 'pic_url', 'specs', 'description', 'latest_price', 'price_history', 'reviews', 'last_updated']

    def get_latest_price(self, obj):
        # 取出最新的一筆價格
        latest = obj.price_history.order_by('-crawled_at').first()
        return latest.price if latest else None
