from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Product
from .serializers import ProductSerializer

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    提供商品資料的 API
    """
    queryset = Product.objects.all().order_by('-last_updated')
    serializer_class = ProductSerializer
    # === 設定過濾與搜尋功能 ===
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # 1. 精確過濾：網址可用 ?category=GPU
    filterset_fields = ['category']
    # 2. 模糊搜尋：網址可用 ?search=RTX4090
    search_fields = ['name', 'description']
    # 3. 排序：網址可用 ?ordering=name
    ordering_fields = ['name', 'last_updated']
