from unittest.mock import patch
from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from core.comparison import identity, same_model, comparisons
from core.models import Product, PriceHistory
from core.coolpc import CoolPCSpider
import hashlib


class ComparisonTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_model_and_variant_matrix(self):
        cases = [
            ('CPU', 'AMD Ryzen 7 7800X3D 處理器', '{AMD R7 7800X3D}/8核', True),
            ('CPU', 'AMD Ryzen 5 7600', 'AMD R5 7600', True),
            ('CPU', 'Intel i7-14700K', 'Intel i7 14700K 處理器', True),
            ('CPU', 'Intel i7-14700K', 'Intel i7-14700KF', False),
            ('CPU', 'AMD Ryzen 7 7800X3D', 'AMD Ryzen 7 7800X', False),
            ('CPU', 'Intel i7-14700K', 'Intel i7-14700K 散裝', False),
            ('CPU', 'Intel i7-14700K', 'Intel i7-14700K + 主機板', False),
            ('GPU', 'ASUS RTX 4070 12GB', 'MSI RTX 4070 12GB', False),
            ('GPU', 'ASUS RTX 4070 12GB', 'ASUS RTX 4070 12GB', False),
            ('GPU', '技嘉 GV-N4070WF3OC-12GD 12GB', 'GIGABYTE GV-N4070WF3OC-12GD 12GB', True),
            ('SSD', '三星 990 PRO 2TB SSD', 'SAMSUNG 990 PRO 2TB', True),
            ('SSD', '三星 990 PRO 2TB SSD', 'SAMSUNG 990 PRO 1TB', False),
            ('SSD', 'WD SN850X 2TB SSD', 'WD SN850X 2TB 散熱片', False),
            ('SSD', 'WD SN850X SSD', 'WD SN850X SSD', False),
            ('MB', 'ASUS TUF B650-PLUS WIFI', '華碩 TUF B650-PLUS WIFI II', False),
            ('RAM', '金士頓 KF560C36BBEK2-32 DDR5 32GB', 'Kingston KF560C36BBEK2-32 DDR5 32GB', True),
            ('RAM', '金士頓 KF560C36BBEK2-32 DDR5 32GB', 'Kingston KF560C36BBEK2-32 DDR5 64GB', False),
            ('RAM', '記憶體 DDR5-6000 32GB', '不同型號 DDR5-6000 32GB', False),
            ('SSD', '固態硬碟 PCIe4.0 2TB', '不同固態硬碟 PCIe4.0 2TB', False),
            ('RAM', 'KF560C36BBEK2-32 16GB * 2', 'KF560C36BBEK2-32 16GB * 4', False),
        ]
        for cat, left, right, expected in cases:
            with self.subTest(left=left, right=right):
                self.assertEqual(same_model(identity(left, cat), identity(right, cat)), expected)

    def make_product(self, key, source, name, price, active=True):
        p = Product.objects.create(id=key, source=source, name=name, category='CPU', is_active=active)
        PriceHistory.objects.create(product=p, price=price)
        return p

    @patch('requests.sessions.Session.get', side_effect=AssertionError('Page view must not fetch retailers'))
    def test_both_directions_and_inactive_excluded(self, unused):
        a = self.make_product('a', 'pchome', 'AMD Ryzen 7 7800X3D', 12000)
        b = self.make_product('b', 'coolpc', '{AMD R7 7800X3D}', 11000)
        self.make_product('c', 'coolpc', 'AMD R7 7800X3D', 9000, active=False)
        self.assertEqual([x['id'] for x in comparisons(a)], ['b'])
        self.assertEqual(comparisons(a)[0]['channel'], '實體通路')
        self.assertEqual([x['id'] for x in comparisons(b)], ['a'])
        response = APIClient().get('/api/products/a/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('{', response.data['comparisons'][0]['name'])
        listing = APIClient().get('/api/products/?source=coolpc')
        self.assertNotIn('{', listing.data['results'][0]['name'])
        self.assertNotIn('comparisons', listing.data['results'][0])

    def test_brace_cleanup_preserves_legacy_id(self):
        name = '{AMD R7 7800X3D}'
        html = f'<select name="n4"><option value="1">{name}, $11000</option></select>'
        product = list(CoolPCSpider.parse_html(html))[0]
        expected = 'coolpc:' + hashlib.sha256(('CPU:' + name.casefold()).encode()).hexdigest()[:40]
        self.assertEqual(product['id'], expected)
        self.assertEqual(product['name'], 'AMD R7 7800X3D')

    def test_clean_sync_keeps_price_history(self):
        from core.services import _save_product
        html = '<select name="n4"><option value="1">{AMD R7 7800X3D}, $11000</option></select>'
        item = list(CoolPCSpider.parse_html(html))[0]
        old = self.make_product(item['id'], 'coolpc', '{AMD R7 7800X3D}', 12000)
        _save_product(item, set())
        old.refresh_from_db()
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(old.name, 'AMD R7 7800X3D')
        self.assertEqual(set(old.price_history.values_list('price', flat=True)), {11000, 12000})
