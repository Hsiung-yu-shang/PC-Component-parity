from django.db.models import Prefetch
from rest_framework import viewsets, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Product, PriceHistory
from .serializers import ProductListSerializer, ProductDetailSerializer
from .permissions import HasSyncToken
from . import services
import threading
import logging
from django.core.cache import cache
from django.db import close_old_connections

logger = logging.getLogger(__name__)

SYNC_STATUS_KEY = 'sync_products_status'

def _run_sync_in_background():
    close_old_connections()
    try:
        cache.set(SYNC_STATUS_KEY, {'state': 'running'}, timeout=None)
        summary = services.sync_products()
        cache.set(SYNC_STATUS_KEY, {'state': 'done', 'summary': summary}, timeout=3600)
    except Exception as e:
        logger.exception("[sync_products] 背景執行失敗")
        cache.set(SYNC_STATUS_KEY, {'state': 'error', 'error': str(e)}, timeout=3600)
    finally:
        close_old_connections()

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

    這支 API 會立刻回應「已開始」，實際爬蟲在背景執行，
    避免長時間等待造成 Proxy / Cloudflare 逾時（524）。
    請改用 GET /api/sync/status/ 查詢目前進度與結果。
    """
    permission_classes = [HasSyncToken]

    def post(self, request):
        current = cache.get(SYNC_STATUS_KEY)
        if current and current.get('state') == 'running':
            return Response(
                {'status': 'running', 'message': '同步作業已在進行中，請稍後查詢結果'},
                status=status.HTTP_202_ACCEPTED,
            )

        thread = threading.Thread(target=_run_sync_in_background, daemon=True)
        thread.start()

        return Response(
            {'status': 'started', 'message': '同步已開始，請稍後查詢 /api/sync/status/ 取得結果'},
            status=status.HTTP_202_ACCEPTED,
        )


class SyncStatusView(APIView):
    """
    GET /api/sync/status/
    查詢最近一次（或正在進行的）同步狀態。
    """
    permission_classes = [HasSyncToken]

    def get(self, request):
        current = cache.get(SYNC_STATUS_KEY, {'state': 'idle'})
        return Response(current, status=status.HTTP_200_OK)

    def post(self, request):
        try:
            summary = services.sync_products()
        except Exception as e:
            return Response(
                {'error': f'同步過程發生錯誤：{e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(summary, status=status.HTTP_200_OK)
