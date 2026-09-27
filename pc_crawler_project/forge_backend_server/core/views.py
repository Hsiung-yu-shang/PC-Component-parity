from django.db.models import OuterRef, Subquery
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError
from django.db import DatabaseError
from .sources import SOURCES, enabled_sources, resolve_sources
from .serializers import PriceHistorySerializer, ProductReviewSerializer
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

def _run_sync_in_background(reservation, sources):
    close_old_connections()
    try:
        services.sync_products(reservation=reservation, sources=sources)
    except Exception:
        logger.exception("商品同步失敗")
    finally:
        reservation.close()
        close_old_connections()

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    提供商品資料的 API。

    - list（列表）用輕量版 Serializer，只帶最新價格。
    - retrieve（詳情）用完整版 Serializer，帶最近 100 筆歷史價格與評論。
    - 列表價格使用子查詢；評論使用 select_related，避免 N+1。
    """
    queryset = Product.objects.all().order_by('-last_updated', 'id')

    # === 設定過濾與搜尋功能 ===
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'source', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'last_updated']

    def get_queryset(self):
        if len(self.request.query_params.get('search', '')) > 200:
            raise ValidationError({'search': '搜尋字串最多 200 字。'})
        queryset = super().get_queryset()

        # 沒有明確指定 is_active 篩選時，預設只給「上架中」的商品，
        # 避免前台列表混入已下架商品。想看下架商品要顯式帶 ?is_active=false。
        if self.action == 'list' and 'is_active' not in self.request.query_params:
            queryset = queryset.filter(is_active=True)

        if self.action == 'list':
            # 列表只需要「最新一筆價格」，用 Subquery 排序後只取第一筆，
            # 避免整包歷史價格塞進 JSON，也避免每個商品多打一次 DB。
            latest = PriceHistory.objects.filter(product_id=OuterRef('pk')).order_by('-crawled_at', '-pk')
            queryset = queryset.annotate(latest_price_value=Subquery(latest.values('price')[:1]))

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductDetailSerializer

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        records = self.get_object().price_history.order_by('-crawled_at', '-pk')
        return self.get_paginated_response(PriceHistorySerializer(self.paginate_queryset(records), many=True).data)

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        records = self.get_object().reviews.select_related('user').order_by('-created_at', '-pk')
        return self.get_paginated_response(ProductReviewSerializer(self.paginate_queryset(records), many=True).data)


class SourceListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        enabled = enabled_sources()
        return Response([{'id': s.key, 'label': s.label, 'channel': s.channel,
                          'sync_enabled': s.key in enabled} for s in SOURCES.values()])


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            list(Product.objects.values_list('id', 'source')[:1])
            return Response({'status': 'ok'})
        except DatabaseError:
            return Response({'status': 'unavailable'}, status=503)


class SyncProductsView(APIView):
    """
    手動觸發一次商品同步（爬蟲 + 更新價格 + 標記下架商品）。

    POST /api/sync/
    Header: X-Sync-Token: <token>

    這支 API 會立刻回應「已開始」，實際爬蟲在背景執行，
    避免長時間等待造成 Proxy / Cloudflare 逾時（524）。
    請改用 GET /api/sync/status/ 查詢目前進度與結果。
    """
    authentication_classes = []
    permission_classes = [HasSyncToken]

    def post(self, request):
        if not isinstance(request.data, dict):
            raise ValidationError('請提供 JSON 物件。')
        try:
            sources = resolve_sources(request.data.get('sources'))
        except ValueError as exc:
            raise ValidationError({'sources': str(exc)}) from exc
        if not sources:
            raise ValidationError('所有來源已停用同步。')
        try:
            reservation = reserve_sync()
        except SyncBusy as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS,
                            headers={'Retry-After': '900'})
        try:
            thread = threading.Thread(target=_run_sync_in_background, args=(reservation, sources), daemon=True)
            thread.start()
        except Exception:
            finish_sync(state='error', error='無法啟動同步，請管理員查看服務紀錄。')
            reservation.close()
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
    authentication_classes = []
    permission_classes = [HasSyncToken]

    def get(self, request):
        current = sync_status()
        return Response(current, status=status.HTTP_200_OK)
