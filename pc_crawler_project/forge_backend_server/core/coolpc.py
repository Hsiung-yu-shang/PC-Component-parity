"""原價屋公開估價頁解析。價格為估價參考，實際售價以店家確認為準。"""
import hashlib
import re

import requests
from bs4 import BeautifulSoup

from .crawler import PChomeSpider


class CoolPCSpider:
    URL = 'https://www.coolpc.com.tw/evaluate.php'
    CATEGORIES = {
        'n4': 'CPU', 'n5': 'MB', 'n6': 'RAM', 'n7': 'SSD',
        'n8': 'HDD', 'n12': 'GPU', 'n14': 'CASE', 'n15': 'PSU',
    }

    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; PCPartsPrice/1.0)'})
        self.spec_parser = PChomeSpider()

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
                    'name': name, 'price': price, 'picS': '', 'describe': '',
                    'category': category, 'specs': specs,
                }

    def run(self):
        response = self.session.get(self.URL, timeout=30)
        response.raise_for_status()
        # The source page is Big5 even when the server omits or misstates charset.
        html = response.content.decode('big5', errors='replace')
        yield from self.parse_html(html)
