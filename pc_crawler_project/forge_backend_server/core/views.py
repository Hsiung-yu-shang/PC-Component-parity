from django.db.models import OuterRef, Subquery
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
from .sync_state import reserve_sync, sync_status, finish_sync, SyncBusy
from django.db import close_old_connections

logger = logging.getLogger(__name__)

def _run_sync_in_background(reservation):
    close_old_connections()
    try:
        services.sync_products(reservation=reservation)
    except Exception:
        logger.exception("商品同步失敗")
    finally:
        reservation.close()
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
    filterset_fields = ['category', 'source', 'is_active']
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
            latest = PriceHistory.objects.filter(product_id=OuterRef('pk')).order_by('-crawled_at', '-pk')
            queryset = queryset.annotate(latest_price_value=Subquery(latest.values('price')[:1]))
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
        try:
            reservation = reserve_sync()
        except SyncBusy as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS,
                            headers={'Retry-After': '900'})
        try:
            thread = threading.Thread(target=_run_sync_in_background, args=(reservation,), daemon=True)
            thread.start()
        except Exception:
            reservation.close()
            finish_sync(state='error', error='無法啟動同步，請管理員查看服務紀錄。')
            raise

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
        current = sync_status()
        return Response(current, status=status.HTTP_200_OK)
