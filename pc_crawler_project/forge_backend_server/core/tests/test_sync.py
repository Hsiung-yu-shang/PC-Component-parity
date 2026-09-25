import tempfile
import time
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient
from core.coolpc import CoolPCSpider, SourceUnavailable
from core.sync_state import reserve_sync, read_state, write_state, sync_status, SyncBusy


class SyncTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.override = override_settings(SYNC_STATE_DIR=self.directory.name, SYNC_API_TOKEN='correct-token')
        self.override.enable()
        self.addCleanup(self.override.disable)

    def response(self, code=200, body=b'', headers=None):
        response = MagicMock(status_code=code, headers=headers or {})
        response.__enter__.return_value = response
        response.iter_content.return_value = [body]
        return response

    def seed_robots(self):
        write_state('coolpc.json', {'robots': 'User-agent: *\nAllow: /', 'robots_expires': time.time() + 3600})

    def test_overlap_and_cooldown(self):
        with reserve_sync():
            with self.assertRaises(SyncBusy):
                reserve_sync()
        with self.assertRaises(SyncBusy):
            reserve_sync()

    def test_unauthorized_sync_and_unicode_token(self):
        client = APIClient()
        for token in ('', 'wrong', 'ＸＸＸＸ'):
            self.assertEqual(client.post('/api/sync/', HTTP_X_SYNC_TOKEN=token).status_code, 403)
        with reserve_sync():
            self.assertEqual(client.post('/api/sync/', HTTP_X_SYNC_TOKEN='correct-token').status_code, 429)

    def test_status_shared(self):
        write_state('sync.json', {'state': 'done', 'summary': {'scanned': 10}})
        response = APIClient().get('/api/sync/status/', HTTP_X_SYNC_TOKEN='correct-token')
        self.assertEqual(response.data['summary']['scanned'], 10)

    def test_interrupted_worker_status_recovers(self):
        with reserve_sync():
            self.assertEqual(sync_status()['state'], 'running')
        self.assertEqual(sync_status()['state'], 'error')

    def test_retry_after_http_date(self):
        from email.utils import formatdate
        self.seed_robots()
        session = MagicMock()
        session.get.return_value = self.response(503, headers={'Retry-After': formatdate(time.time() + 200000, usegmt=True)})
        with self.assertRaises(SourceUnavailable):
            list(CoolPCSpider(session).run())
        self.assertGreater(read_state('coolpc.json')['next_allowed'], time.time() + 199990)

    def test_redirect_does_not_follow_to_new_host(self):
        self.seed_robots()
        session = MagicMock()
        session.get.return_value = self.response(302, headers={'Location': 'https://other.test/'})
        with self.assertRaises(SourceUnavailable):
            list(CoolPCSpider(session).run())
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])

    def test_429_honors_retry_after_without_retry(self):
        self.seed_robots()
        session = MagicMock()
        session.get.return_value = self.response(429, headers={'Retry-After': '172800'})
        with self.assertRaises(SourceUnavailable):
            list(CoolPCSpider(session).run())
        self.assertGreater(read_state('coolpc.json')['next_allowed'], time.time() + 172790)
        self.assertEqual(list(CoolPCSpider(session).run()), [])
        self.assertEqual(session.get.call_count, 1)

    def test_empty_response_preserves_database(self):
        self.seed_robots()
        session = MagicMock()
        session.get.return_value = self.response(body=b'<html>challenge</html>')
        with self.assertRaises(SourceUnavailable):
            list(CoolPCSpider(session).run())
        self.assertEqual(read_state('coolpc.json')['failures'], 1)

    def test_robots_disallow_never_fetches_page(self):
        session = MagicMock()
        session.get.return_value = self.response(body=b'User-agent: *\nDisallow: /evaluate.php')
        with self.assertRaises(SourceUnavailable):
            list(CoolPCSpider(session).run())
        self.assertEqual(session.get.call_count, 1)
        self.assertTrue(session.get.call_args.args[0].endswith('robots.txt'))

    def test_success_reuses_prices_during_cooldown(self):
        self.seed_robots()
        html = '<select name="n4">' + ''.join(f'<option value="{i}">AMD CPU {i}, $1000</option>' for i in range(1, 51)) + '</select>'
        session = MagicMock()
        session.get.return_value = self.response(body=html.encode())
        self.assertEqual(len(list(CoolPCSpider(session).run())), 50)
        spider = CoolPCSpider(session)
        self.assertEqual(list(spider.run()), [])
        self.assertTrue(spider.skipped)
        self.assertEqual(session.get.call_count, 1)

    def test_pchome_stops_requests_after_429(self):
        from core.crawler import PChomeSpider
        spider = PChomeSpider()
        spider.session = MagicMock()
        spider.session.get.return_value.status_code = 429
        self.assertEqual(list(spider.run('CPU')), [])
        self.assertEqual(list(spider.run('SSD')), [])
        self.assertEqual(spider.session.get.call_count, 1)
