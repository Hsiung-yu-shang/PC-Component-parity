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


class ProductListSerializer(serializers.ModelSerializer):
    """
    列表用：輕量版，只帶最新價格，不巢狀塞入完整的
    price_history / reviews，避免商品一多列表 API 就肥大、變慢。
    """
    latest_price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'category', 'name', 'pic_url', 'specs',
            'latest_price', 'last_updated', 'is_active', 'delisted_at',
        ]

    def get_latest_price(self, obj):
        # 搭配 view 的 Prefetch(..., queryset=PriceHistory.objects.order_by('-crawled_at'))
        # 這裡取 all()[0] 不會再多打一次 DB
        latest = obj.price_history.all()
        return latest[0].price if latest else None


class ProductDetailSerializer(serializers.ModelSerializer):
    """
    詳情頁用：完整版，帶完整的歷史價格與評論。
    只有使用者點進單一商品時才會用到這份，不會拖累列表頁效能。
    """
    price_history = PriceHistorySerializer(many=True, read_only=True)
    reviews = ProductReviewSerializer(many=True, read_only=True)
    latest_price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'category', 'name', 'pic_url', 'specs', 'description',
            'latest_price', 'price_history', 'reviews', 'last_updated',
            'is_active', 'delisted_at',
        ]

    def get_latest_price(self, obj):
        latest = obj.price_history.order_by('-crawled_at').first()
        return latest.price if latest else None
