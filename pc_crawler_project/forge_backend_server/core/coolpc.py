"""原價屋公開估價頁解析。價格為估價參考，實際售價以店家確認為準。"""
import hashlib
import re
import time
from email.utils import parsedate_to_datetime
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from .crawler import PChomeSpider
from .product_names import clean_name
from .sync_state import lock, read_state, write_state


class SourceUnavailable(Exception):
    pass


class CoolPCSpider:
    URL = 'https://www.coolpc.com.tw/evaluate.php'
    CATEGORIES = {
        'n4': 'CPU', 'n5': 'MB', 'n6': 'RAM', 'n7': 'SSD',
        'n8': 'HDD', 'n12': 'GPU', 'n14': 'CASE', 'n15': 'PSU',
    }

    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent': 'PCPartsPrice/1.0 (+https://github.com/Hsiung-yu-shang/PC-Component-parity)'})
        self.skipped = False

    @classmethod
    def parse_html(cls, html):
        soup = BeautifulSoup(html, 'html.parser')
        parser = PChomeSpider()
        seen = set()
        for select in soup.select('select[name]'):
            category = cls.CATEGORIES.get(select.get('name'))
            if not category:
                continue
            for option in select.select('option'):
                if option.has_attr('disabled') or option.get('value') in (None, '0'):
                    continue
                label = option.get_text(' ', strip=True)
                # The first $ amount is the current standalone cash price. Later amounts
                # describe bundle deals, coupons or previous prices.
                match = re.search(r',\s*\$\s*([\d,]+)', label)
                if not match:
                    continue
                price = int(match.group(1).replace(',', ''))
                name = label[:match.start()].strip()
                if not name or price <= 100:
                    continue
                name = parser.remove_emoji(name)[:255]
                _, specs = parser.analyze_specs(name, '')
                key = f'{category}:{re.sub(r"\s+", " ", name).casefold()}'
                product_id = 'coolpc:' + hashlib.sha256(key.encode('utf-8')).hexdigest()[:40]
                if product_id in seen:
                    continue
                seen.add(product_id)
                yield {
                    'id': product_id, 'source': 'coolpc', 'product_url': cls.URL,
                    'name': clean_name(name, 'coolpc'), 'price': price, 'picS': '', 'describe': '',
                    'category': category, 'specs': specs,
                }

    def run(self):
        # Persistent single-source lock and cooldown apply even to direct CLI calls.
        with lock('coolpc'):
            state = read_state('coolpc.json')
            now = time.time()
            if now < state.get('next_allowed', 0):
                self.skipped = True
                return
            # Reserve before network I/O, so a crash cannot cause an immediate retry.
            state['next_allowed'] = now + 6 * 3600
            write_state('coolpc.json', state)
            try:
                fetched_robots = now >= state.get('robots_expires', 0)
                if fetched_robots:
                    body = self._get('https://www.coolpc.com.tw/robots.txt', state, robots=True)
                    state['robots'] = body.decode('utf-8', errors='replace')
                    state['robots_expires'] = now + 24 * 3600
                    write_state('coolpc.json', state)
                rules = RobotFileParser()
                rules.parse(state.get('robots', '').splitlines())
                if not rules.can_fetch('PCPartsPrice', self.URL):
                    raise SourceUnavailable('原價屋 robots.txt 不允許存取估價頁。')
                if rules.crawl_delay('PCPartsPrice'):
                    state['next_allowed'] = max(state['next_allowed'], now + rules.crawl_delay('PCPartsPrice'))
                rate = rules.request_rate('PCPartsPrice')
                if rate and rate.requests:
                    state['next_allowed'] = max(state['next_allowed'], now + rate.seconds / rate.requests)
                if fetched_robots:
                    delay = max(2, rules.crawl_delay('PCPartsPrice') or 0,
                                rate.seconds / rate.requests if rate and rate.requests else 0)
                    if delay > 30:
                        self.skipped = True
                        return
                    time.sleep(delay)
                body = self._get(self.URL, state)
                items = list(self.parse_html(body.decode('big5', errors='replace')))
                if len(items) < 50:
                    raise SourceUnavailable('原價屋回傳資料不完整或驗證頁，保留舊資料並停止本次同步。')
                state['failures'] = 0
                state['last_success'] = now
            except (requests.RequestException, SourceUnavailable) as exc:
                state['failures'] = min(state.get('failures', 0) + 1, 5)
                delay = min(72 * 3600, 6 * 3600 * 2 ** state['failures'])
                state['next_allowed'] = max(state['next_allowed'], now + delay)
                raise SourceUnavailable('原價屋暫時無法同步；已退避並保留既有價格。') from exc
            finally:
                write_state('coolpc.json', state)
        yield from items

    def _get(self, url, state, robots=False):
        with self.session.get(url, timeout=(10, 30), allow_redirects=False, stream=True) as response:
            if response.status_code in (403, 429):
                state['next_allowed'] = max(state['next_allowed'], time.time() + 24 * 3600)
            retry = response.headers.get('Retry-After')
            if retry:
                try:
                    until = time.time() + int(retry) if retry.isdigit() else parsedate_to_datetime(retry).timestamp()
                    state['next_allowed'] = max(state['next_allowed'], until)
                except (ValueError, TypeError, OverflowError):
                    pass
            if robots and response.status_code == 404:
                return b''
            if response.status_code != 200:
                raise SourceUnavailable(f'來源回應 HTTP {response.status_code}')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > (256 * 1024 if robots else 8 * 1024 * 1024):
                    raise SourceUnavailable('來源內容超出大小限制。')
                chunks.append(chunk)
            return b''.join(chunks)
