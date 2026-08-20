from django.db.models import Prefetch
from rest_framework import viewsets, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Product, PriceHistory
from .serializers import ProductListSerializer, ProductDetailSerializer
from .permissions import HasSyncToken
from . import services


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    提供商品資料的 API。

    - list（列表）用輕量版 Serializer，只帶最新價格。
    - retrieve（詳情）用完整版 Serializer，帶完整歷史價格與評論。
    - 兩邊都依情況做 prefetch_related，避免 N+1 query。
    """
    queryset = Product.objects.all().order_by('-last_updated')

    # === 設定過濾與搜尋功能 ===
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'last_updated']

    def get_queryset(self):
        queryset = super().get_queryset()

        # 沒有明確指定 is_active 篩選時，預設只給「上架中」的商品，
        # 避免前台列表混入已下架商品。想看下架商品要顯式帶 ?is_active=false。
        if 'is_active' not in self.request.query_params:
            queryset = queryset.filter(is_active=True)

        if self.action == 'list':
            # 列表只需要「最新一筆價格」，用 Prefetch 排序後只取第一筆，
            # 避免整包歷史價格塞進 JSON，也避免每個商品多打一次 DB。
            queryset = queryset.prefetch_related(
                Prefetch(
                    'price_history',
                    queryset=PriceHistory.objects.order_by('-crawled_at')
                )
            )
        else:
            # 詳情頁才把完整歷史價格 + reviews 一起帶出來
            queryset = queryset.prefetch_related('price_history', 'reviews')

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductDetailSerializer


class SyncProductsView(APIView):
    """
    手動觸發一次商品同步（爬蟲 + 更新價格 + 標記下架商品）。

    POST /api/sync/
    Header: X-Sync-Token: <token>

    這支 API 會「同步等待」直到整個爬蟲跑完才回應，
    依關鍵字數量，實際耗時可能是幾十秒到幾分鐘，請前端做好 loading 提示。
    """
    permission_classes = [HasSyncToken]

    def post(self, request):
        try:
            summary = services.sync_products()
        except Exception as e:
            return Response(
                {'error': f'同步過程發生錯誤：{e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(summary, status=status.HTTP_200_OK)
