"""Conservative, local-only model matching. Never fetch a retailer on a page view."""
import re
from django.core.cache import cache
from django.db.models import OuterRef, Subquery
from .models import Product, PriceHistory
from .product_names import clean_name, normalized

BRANDS = {
    'ASUS': ('ASUS', '華碩'), 'MSI': ('MSI', '微星'),
    'GIGABYTE': ('GIGABYTE', '技嘉'), 'ASROCK': ('ASROCK', '華擎'),
    'KINGSTON': ('KINGSTON', '金士頓'), 'CRUCIAL': ('CRUCIAL', '美光'),
    'SAMSUNG': ('SAMSUNG', '三星'), 'WD': ('WESTERN DIGITAL', 'WD', '威騰'),
    'SEAGATE': ('SEAGATE', '希捷'), 'ADATA': ('ADATA', '威剛'),
    'CORSAIR': ('CORSAIR', '海盜船'), 'GSKILL': ('G.SKILL', '芝奇'),
    'INTEL': ('INTEL', '英特爾'), 'AMD': ('AMD', '超微'),
    'SEASONIC': ('SEASONIC', '海韻'), 'FSP': ('FSP', '全漢'),
}


def identity(name, category):
    text = normalized(clean_name(name, 'coolpc'))
    # Packages, used goods and systems must not be presented as a standalone part.
    if re.search(r'組合|搭購|搭機|套裝|二手|福利品|整新|組裝|\+', text):
        return None
    brands = {brand for brand, aliases in BRANDS.items() if any(
        re.search(r'(?<![A-Z])' + re.escape(alias) + r'(?![A-Z])', text)
        for alias in aliases)}
    if category == 'CPU':
        match = re.search(r'\bI[3579][ -]*(\d{4,5}[A-Z]{0,3})\b', text)
        family = 'INTEL'
        if not match:
            match = re.search(r'\b(?:CORE\s*)?ULTRA\s*[3579][ -]+(\d{3}[A-Z]{0,2})\b', text)
            family = 'INTEL'
        if not match and ('AMD' in brands or 'RYZEN' in text):
            match = re.search(r'(?<![A-Z0-9])(\d{4}(?:X3D|XT|GE|X|G|F)?)(?![A-Z0-9])', text)
            family = 'AMD'
        if not match and 'INTEL' in brands:
            match = re.search(r'(?<![A-Z0-9])(1[0-9]\d{3}(?:KF|KS|K|F|T)?)(?![A-Z0-9])', text)
            family = 'INTEL'
        if not match:
            return None
        anchors = {family + ':' + match.group(1)}
    else:
        # Explicit part numbers, not a GPU chip, chipset, capacity or speed alone.
        tokens = re.findall(r'[A-Z0-9]+(?:[-./][A-Z0-9]+)*', text)
        anchors = {t for t in tokens if len(t) >= 7 and re.search('[A-Z]', t)
                   and re.search('[0-9]', t) and not re.fullmatch(
                       r'(?:RTX|GTX|RX|DDR|PCIE|LGA|CORE|RYZEN|WINDOWS|SATA|GDDR|USB)\d+[A-Z0-9]*|\d+(?:GB|TB|MHZ|MTS|MBPS)',
                       re.sub(r'[-./]', '', t))}
        if not anchors and category == 'SSD' and len(brands) == 1:
            model = re.search(r'\b(SN\d{3,4}[A-Z]*|KC\d{4}|NV[23]|T\d{3}|[89]\d{2}\s*(?:PRO|EVO(?:\s*PLUS)?))\b', text)
            if model:
                anchors = {next(iter(brands)) + ':' + re.sub(r'\s+', '', model.group(1))}
        if not anchors:
            return None
    # Different capacities, memory generations and physical/package variants conflict.
    capacities = {str(float(n) * (1024 if unit == 'T' else 1))
                  for n, unit in re.findall(r'(?<![A-Z0-9])(\d+(?:\.\d+)?)\s*([GT])(?:B)?\b', text)}
    if category in ('SSD', 'RAM') and not capacities:
        return None
    variants = set(re.findall(r'\b(?:DDR[345]|TI|SUPER|XTX|XT|OC|WIFI|WHITE|BLACK|II|III|V[234])\b', text))
    for label, pattern in [('TRAY', r'散裝|散片|TRAY'), ('WHITE', r'白色|白版'),
                           ('BLACK', r'黑色|黑版'), ('HEATSINK', r'散熱片|HEATSINK'),
                           ('KIT', r'\*\s*[248]|[X×]\s*[248]|雙通道|套件')]:
        if re.search(pattern, text):
            variants.add(label)
    kit = re.search(r'(?:GB?|TB?)\s*[*X×]\s*([248])\b', text)
    if kit:
        variants.add('KIT:' + kit.group(1))
    return {'anchors': anchors, 'brands': brands, 'capacities': capacities, 'variants': variants}


def same_model(left, right):
    if not left or not right or not left['anchors'].intersection(right['anchors']):
        return False
    if left['brands'] and right['brands'] and left['brands'] != right['brands']:
        return False
    return (left['capacities'] == right['capacities']
            and left['variants'] == right['variants']
            and left['anchors'] == right['anchors'])


def comparisons(product):
    signature = identity(product.name, product.category)
    if not signature or product.source not in ('pchome', 'coolpc'):
        return []
    other = 'coolpc' if product.source == 'pchome' else 'pchome'
    key = f'comparison-v1:{other}:{product.category}'
    candidates = cache.get(key)
    if candidates is None:
        latest = PriceHistory.objects.filter(product_id=OuterRef('pk')).order_by('-crawled_at', '-pk')
        candidates = list(Product.objects.filter(source=other, category=product.category, is_active=True)
            .annotate(latest_price=Subquery(latest.values('price')[:1]))
            .values('id', 'name', 'source', 'product_url', 'latest_price', 'last_updated'))
        for item in candidates:
            item['_identity'] = identity(item['name'], product.category)
        cache.set(key, candidates, 300)
    matches = []
    for candidate in candidates:
        if candidate['latest_price'] is None or not same_model(signature, candidate['_identity']):
            continue
        item = {k: v for k, v in candidate.items() if not k.startswith('_')}
        item['name'] = clean_name(item['name'], other)
        item['channel'] = '實體通路' if other == 'coolpc' else '線上購物'
        item['match_note'] = '型號與可辨識規格相符，購買前請核對包裝及保固。'
        matches.append(item)
    return sorted(matches, key=lambda item: (item['latest_price'], item['id']))[:10]
