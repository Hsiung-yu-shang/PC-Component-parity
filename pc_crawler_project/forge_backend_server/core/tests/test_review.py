from django.test import SimpleTestCase
from core.comparison import identity, same_model

class ReviewRegressions(SimpleTestCase):
    def test_marketing_year_is_not_cpu_model(self):
        self.assertFalse(same_model(identity('2026 AMD R7 7800X3D', 'CPU'),
                                    identity('2026 AMD R7 9700X', 'CPU')))

    def test_non_cpu_model_cannot_cross_unknown_manufacturers(self):
        self.assertFalse(same_model(identity('MSI ABC12345 12GB', 'GPU'),
                                    identity('ASUS ABC12345 12GB', 'GPU')))

from datetime import timedelta
from unittest.mock import MagicMock, patch
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient
from core.models import Product, PriceHistory, ProductReview
from core.services import _sync_products
from core.sources import Source, resolve_sources
from core.source_errors import SourceUnavailable
from core.crawler import PChomeSpider
from core.checks import source_configuration


class SourceConfigurationTests(SimpleTestCase):
    @override_settings(SYNC_SOURCES=['coolpc'])
    def test_only_enabled_sources_can_be_requested(self):
        self.assertEqual(resolve_sources(), ('coolpc',))
        for value in (['pchome'], [], 'coolpc', [None], {'coolpc': True}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_sources(value)
        self.assertEqual(resolve_sources(['coolpc', 'coolpc']), ('coolpc',))

    @override_settings(SYNC_SOURCES=['unknown'], SYNC_MAX_PAGES=6)
    def test_invalid_env_is_detected_before_deployment(self):
        self.assertEqual({error.id for error in source_configuration(None)}, {'core.E001', 'core.E002'})

    def test_malformed_pchome_records_do_not_abort_good_records(self):
        spider = PChomeSpider()
        with patch.object(spider, 'fetch_data', return_value=[None, {'name': None},
                    {'Id': 'good', 'name': 'AMD Ryzen 7 7800X3D', 'price': 10000, 'describe': None}]):
            self.assertEqual([p['id'] for p in spider.run('CPU')], ['good'])


class DatabaseReviewTests(TestCase):
    def setUp(self):
        cache.clear()

    def item(self, key):
        return {'id': key, 'name': 'AMD Ryzen 7 7800X3D', 'price': 10000,
                'picS': '', 'describe': '', 'category': 'CPU'}

    @override_settings(PCHOME_KEYWORDS=['CPU'], SYNC_MAX_PAGES=1)
    def test_source_failure_does_not_block_other_source(self):
        bad = MagicMock()
        bad.run.side_effect = SourceUnavailable('blocked')
        good = MagicMock(skipped=False)
        good.run.return_value = iter([self.item('good')])
        with patch.object(Source, 'spider', side_effect=[bad, good]):
            result = _sync_products()
        self.assertEqual(result['sources']['pchome']['state'], 'backoff')
        self.assertEqual(result['sources']['coolpc']['state'], 'updated')
        self.assertTrue(Product.objects.filter(pk='good', source='coolpc').exists())

    @override_settings(PCHOME_KEYWORDS=['one', 'two'], SYNC_MAX_PAGES=3)
    def test_keywords_pages_and_deduplication(self):
        spider = MagicMock(skipped=False)
        spider.run.side_effect = lambda *args, **kwargs: iter([self.item('same')])
        with patch.object(Source, 'spider', return_value=spider):
            result = _sync_products(sources=['pchome'])
        self.assertEqual(result['scanned'], 1)
        self.assertEqual(PriceHistory.objects.count(), 1)
        self.assertEqual(spider.run.call_args_list[0].kwargs, {'max_pages': 3})
        self.assertEqual(spider.run.call_count, 2)

    def test_partial_catalog_never_delists_old_products(self):
        Product.objects.bulk_create([Product(id=f'old{i}', source='coolpc', name='CPU') for i in range(100)])
        spider = MagicMock(skipped=False)
        spider.run.return_value = iter([self.item(f'new{i}') for i in range(50)])
        with patch.object(Source, 'spider', return_value=spider):
            result = _sync_products(sources=['coolpc'])
        self.assertEqual(result['delisted'], 0)
        self.assertEqual(Product.objects.filter(is_active=True).count(), 150)

    def test_detail_bounded_history_paginated_and_inactive_accessible(self):
        product = Product.objects.create(id='old', name='old', is_active=False)
        PriceHistory.objects.bulk_create([PriceHistory(product=product, price=i) for i in range(105)])
        user = get_user_model().objects.create_user(username='reader')
        ProductReview.objects.bulk_create([ProductReview(product=product, user=user) for _ in range(105)])
        client = APIClient()
        with self.assertNumQueries(4):
            response = client.get('/api/products/old/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['price_history']), 100)
        self.assertEqual(len(response.data['reviews']), 100)
        history = client.get('/api/products/old/history/')
        self.assertEqual(history.data['count'], 105)
        self.assertEqual(len(history.data['results']), 20)
        self.assertEqual(client.get('/api/products/').data['count'], 0)

    @override_settings(SYNC_SOURCES=['coolpc'], PRICE_STALE_HOURS=48)
    def test_source_metadata_and_stale_prices(self):
        Product.objects.create(id='stale', source='coolpc', name='{CPU}')
        Product.objects.filter(pk='stale').update(last_updated=timezone.now() - timedelta(days=3))
        client = APIClient()
        row = client.get('/api/products/').data['results'][0]
        self.assertEqual(row['channel'], '實體通路')
        self.assertTrue(row['price_stale'])
        self.assertIsNone(row['latest_price'])
        sources = client.get('/api/sources/').data
        self.assertFalse(next(s for s in sources if s['id'] == 'pchome')['sync_enabled'])

    @override_settings(SYNC_API_TOKEN='correct-token')
    def test_admin_session_does_not_interfere_with_sync_token(self):
        client = APIClient(enforce_csrf_checks=True)
        user = get_user_model().objects.create_user(username='admin', is_staff=True)
        client.force_login(user)
        with patch('core.views.reserve_sync') as reserve, patch('core.views.threading.Thread'):
            self.assertEqual(client.post('/api/sync/', {}, format='json', HTTP_X_SYNC_TOKEN='correct-token').status_code, 202)
            self.assertEqual(client.post('/api/sync/', {}, format='json').status_code, 403)
            self.assertEqual(reserve.call_count, 1)

    def test_health_detects_database_failure_without_details(self):
        from django.db import OperationalError
        self.assertEqual(APIClient().get('/api/health/').status_code, 200)
        with patch('core.views.Product.objects.values_list', side_effect=OperationalError('secret details')):
            response = APIClient().get('/api/health/')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret', str(response.data))

class InputBoundaryTests(SimpleTestCase):
    def test_pchome_rejects_foreign_namespace_and_oversize_price(self):
        spider = PChomeSpider()
        for raw in ({'Id': 'coolpc:foreign', 'name': 'CPU', 'price': 1000},
                    {'Id': 'normal', 'name': 'CPU', 'price': 2147483648}):
            self.assertFalse(spider.is_valid(spider.parse_product(raw)))
        parsed = spider.parse_product({'Id': 'normal', 'name': 'CPU', 'price': 1000,
                                       'picS': '.evil.test/image.jpg'})
        self.assertEqual(parsed['picS'], '')
