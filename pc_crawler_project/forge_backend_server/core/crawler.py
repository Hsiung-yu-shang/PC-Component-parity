import requests
import time
import random
import re
from typing import Dict, List, Generator

class PChomeSpider:
    def __init__(self):
        self.base_url = "https://ecshweb.pchome.com.tw/search/v3.3/all/results"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://24h.pchome.com.tw/"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

        # Blocklist
        self.exclude_keywords = [
            "筆電", "筆記型", "NB", "Laptop", "商用電腦", "套裝機", "迷你電腦", "AIO", "DIY電腦",
            "滑鼠", "鍵盤", "Mouse", "Keyboard", "鍵鼠組", "手寫板", "簡報筆",
            "螢幕", "顯示器", "Monitor", "耳機", "麥克風", "喇叭", "Speaker",
            "轉接頭", "包包", "散熱墊", "保護貼", "支架", "線材", "傳輸線",
            "手機", "平板", "Watch", "耳塞", "行動電源", "充電器",
            "Switch", "PlayStation", "Xbox", "遊戲機", "遊戲片", "禮物卡",
        ]

    def fetch_data(self, keyword: str, page: int) -> List[Dict]:
        try:
            response = self.session.get(
                self.base_url, 
                params={'q': keyword, 'page': page, 'sort': 'sale/dc'}, 
                timeout=10
            )
            response.raise_for_status()
            return response.json().get('prods', [])
        except Exception as e:
            print(f"[Error] {keyword} Page {page}: {e}")
            return []

    def analyze_specs(self, name: str, describe: str) -> (str, Dict):
        """
        [智慧分析 v3.2] 針對 HDD 與企業級硬碟強化識別
        """
        name_upper = name.upper()
        desc_upper = describe.upper()
        full_text = name_upper + " " + desc_upper
        
        specs = {}
        category = 'OTHER'

        # 先判斷是否為 SSD (這很重要，用來排除)
        is_ssd = 'SSD' in name_upper or '固態' in full_text

        # === 1. 判斷分類 (Category) ===
        
        # --- 電源供應器 (PSU) ---
        if '電源供應器' in full_text or ('POWER' in name_upper and 'W' in name_upper and 'USB' not in name_upper):
            category = 'PSU'
            watt_match = re.search(r'(\d{3,4})\s*W', full_text)
            if watt_match: specs['wattage'] = f"{watt_match.group(1)}W"
            if 'GOLD' in full_text or '金牌' in full_text: specs['80plus'] = 'Gold'

        # --- 傳統硬碟 (HDD) ---
        # 邏輯更新：只要不是 SSD，且包含 HDD 特徵詞，就歸類為 HDD
        elif not is_ssd and (
            'HDD' in name_upper or 
            '機械式' in full_text or 
            '傳統硬碟' in full_text or
            '3.5吋' in full_text or 
            '3.5' in full_text or
            '7200轉' in full_text or 
            '5400轉' in full_text or 
            'RPM' in name_upper or
            'NAS' in name_upper or 
            '監控' in full_text or 
            '企業級' in full_text or 
            '資料中心' in full_text or
            'EXOS' in name_upper or       # Seagate 企業
            'IRONWOLF' in name_upper or   # Seagate NAS
            'SKYHAWK' in name_upper or    # Seagate 監控
            'WD RED' in name_upper or     # WD 紅標
            'WD PURPLE' in name_upper or  # WD 紫標
            'WD GOLD' in name_upper       # WD 金標
        ):
            category = 'HDD'
            specs['type'] = 'HDD'
            
            # [HDD 規格] 轉速
            if '7200' in full_text: specs['rpm'] = '7200RPM'
            elif '5400' in full_text: specs['rpm'] = '5400RPM'
            
            # [HDD 規格] 尺寸
            if '3.5' in full_text or '3.5"' in full_text: specs['size'] = '3.5吋'
            elif '2.5' in full_text or '2.5"' in full_text: specs['size'] = '2.5吋'

        # --- 固態硬碟 (SSD) ---
        elif is_ssd:
            category = 'SSD'
            specs['type'] = 'SSD'
            if 'M.2' in full_text:
                specs['interface'] = 'M.2'
                if 'GEN5' in full_text: specs['pcie_ver'] = 'Gen5'
                elif 'GEN4' in full_text: specs['pcie_ver'] = 'Gen4'
            elif 'SATA' in full_text:
                specs['interface'] = 'SATA'

        # --- 顯示卡 ---
        elif '顯示卡' in full_text or 'RTX' in name_upper or 'GTX' in name_upper or 'RADEON' in name_upper:
            category = 'GPU'

        # --- 主機板 ---
        elif '主機板' in full_text or 'MB' in name_upper: 
            category = 'MB'
        
        # --- 處理器 ---
        elif '處理器' in full_text or 'CPU' in name_upper or 'RYZEN' in name_upper or 'Ryzen' in name_upper or 'INTEL' in name_upper or 'CORE' in name_upper:
            category = 'CPU'
            
        # --- 記憶體 ---
        elif '記憶體' in full_text or 'RAM' in name_upper: 
            category = 'RAM'


        # === 2. 共用規格解析 ===
        if 'DDR5' in full_text: specs['memory_type'] = 'DDR5'
        elif 'DDR4' in full_text: specs['memory_type'] = 'DDR4'

        if 'LGA1700' in full_text: specs['socket'] = 'LGA1700'
        elif 'AM5' in full_text: specs['socket'] = 'AM5'
        elif 'AM4' in full_text: specs['socket'] = 'AM4'
        elif 'LGA1851' in full_text: specs['socket'] = 'LGA1851'

        # === 5. 顯卡型號提取 ===
        gpu_pattern = r'(RTX|GTX|RX)\s*(\d{3,4})\s*(TI\s*SUPER|TI|SUPER|XTX|XT)?\s*(\d{1,2}G[B]?)?'
        match = re.search(gpu_pattern, full_text)
        if match:
            parts = [g for g in match.groups() if g]
            gpu_model_str = " ".join(parts).upper()
            specs['gpu_model'] = gpu_model_str
            if category == 'OTHER': category = 'GPU'
        
        return category, specs

    def remove_emoji(self, text):
        if not text: return ''
        return "".join(c for c in text if c <= "\uFFFF")

    def parse_product(self, raw_data: Dict) -> Dict:
        raw_name = raw_data.get('name', '').strip()
        raw_describe = raw_data.get('describe', '')
        
        clean_name = self.remove_emoji(raw_name)
        clean_describe = self.remove_emoji(raw_describe)
        
        category, specs = self.analyze_specs(clean_name, clean_describe)

        return {
            "id": raw_data.get('Id'),
            "name": clean_name,
            "price": int(raw_data.get('price', 0)),
            "picS": f"https://cs-a.ecimg.tw{raw_data.get('picS')}" if raw_data.get('picS') else "",
            "describe": clean_describe,
            "category": category,
            "specs": specs
        }

    def is_valid(self, product: Dict) -> bool:
        if not product['id'] or product['price'] <= 100:
            return False

        prod_name = product['name'].upper()
        for kw in self.exclude_keywords:
            if kw.upper() in prod_name:
                return False
                
        return True

    def run(self, keyword: str, max_pages: int = 1) -> Generator[Dict, None, None]:
        for page in range(1, max_pages + 1):
            raw_products = self.fetch_data(keyword, page)
            if not raw_products:
                break

            for raw_prod in raw_products:
                clean_prod = self.parse_product(raw_prod)
                if self.is_valid(clean_prod):
                    yield clean_prod
            
            time.sleep(random.uniform(1, 2))