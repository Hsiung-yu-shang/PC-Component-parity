from rest_framework import serializers
from .models import Product, PriceHistory, ProductReview
from .product_names import clean_name
from .comparison import comparisons
from .sources import SOURCES
from .freshness import is_stale


class PriceHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceHistory
        fields = ['price', 'crawled_at']


class ProductReviewSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()  # 顯示使用者名稱而不是 ID

    class Meta:
        model = ProductReview
        fields = ['user', 'rating', 'comment', 'created_at']


class CleanProductSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['name'] = clean_name(data['name'], data['source'])
        source = SOURCES.get(data['source'])
        data['source_label'] = source.label if source else data['source']
        data['channel'] = source.channel if source else '其他通路'
        data['price_stale'] = is_stale(instance.last_updated)
        return data


class ProductListSerializer(CleanProductSerializer):
    """
    列表用：輕量版，只帶最新價格，不巢狀塞入完整的
    price_history / reviews，避免商品一多列表 API 就肥大、變慢。
    """
    latest_price = serializers.IntegerField(source='latest_price_value', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'source', 'product_url', 'category', 'name', 'pic_url', 'specs',
            'latest_price', 'last_updated', 'is_active', 'delisted_at',
        ]

class ProductDetailSerializer(CleanProductSerializer):
    """
    詳情頁預覽最近 100 筆歷史價格與評論；完整紀錄由分頁端點提供。
    只有使用者點進單一商品時才會用到這份，不會拖累列表頁效能。
    """
    comparisons = serializers.SerializerMethodField()
    price_history = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    latest_price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'source', 'product_url', 'category', 'name', 'pic_url', 'specs', 'description',
            'latest_price', 'price_history', 'reviews', 'last_updated',
            'is_active', 'delisted_at', 'comparisons',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['history_preview_limit'] = 100
        data['reviews_preview_limit'] = 100
        return data

    def get_comparisons(self, obj):
        return comparisons(obj)

    def get_price_history(self, obj):
        return PriceHistorySerializer(obj.price_history.order_by('-crawled_at', '-pk')[:100], many=True).data

    def get_reviews(self, obj):
        return ProductReviewSerializer(obj.reviews.select_related('user').order_by('-created_at', '-pk')[:100], many=True).data

    def get_latest_price(self, obj):
        latest = obj.price_history.order_by('-crawled_at', '-pk').first()
        return latest.price if latest else None
