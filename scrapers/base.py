import re
import time
import random
import logging
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TARGET_AREAS = [
    'mariatorget', 'mariaberget', 'mosebacke',
    # Standard broker designations for the Maria parish area
    'södermalm maria', 'sodermalm maria', 'sodermalm-maria',
    'maria magdalena',
]
TARGET_STREETS = [
    # Mariaberget cliff area
    'bastugatan', 'blecktornsbacken', 'bryggargränd', 'urvädersgränd',
    'stigbergsgatan', 'fiskarbacken', 'pysslargränd',
    # Mosebacke area
    'mosebacke', 'svartensgatan', 'katarinavägen', 'erstaviksbacken',
    'fjällgatan',
    # Mariatorget area streets
    'repslagargatan', 'bellmansgatan', 'torkel knutssonsgatan',
    'tavastgatan', 'mariagatan', 'leksaksgatan',
    # Shared area streets (careful — these are long streets, but included for coverage)
    'wollmar yxkullsgatan', 'wollmar-yxkullsgatan',
    'hornsgatan 2', 'hornsgatan 3', 'hornsgatan 4',  # lower Hornsgatan = Mariatorget
]


class BaseScraper:
    broker_name = 'Unknown'
    broker_slug = 'unknown'

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'DNT': '1',
        })

    def get(self, url, retries=3, **kwargs):
        for attempt in range(retries):
            try:
                time.sleep(random.uniform(0.8, 2.0))
                resp = self.session.get(url, timeout=30, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                logger.warning(f'[{self.broker_name}] Attempt {attempt+1}/{retries} failed for {url}: {e}')
                if attempt < retries - 1:
                    time.sleep(2 ** attempt * 2)
        return None

    def soup(self, html):
        return BeautifulSoup(html, 'lxml')

    def is_in_target_area(self, *texts):
        combined = ' '.join(t.lower() for t in texts if t)
        if any(area in combined for area in TARGET_AREAS):
            return True
        if any(street in combined for street in TARGET_STREETS):
            return True
        return False

    def normalize_price(self, text):
        if not text:
            return None
        digits = re.sub(r'[^\d]', '', str(text))
        return int(digits) if digits else None

    def normalize_size(self, text):
        if not text:
            return None
        m = re.search(r'(\d+)[,.]?(\d*)\s*(?:kvm|m²|m2)', str(text).replace(',', '.'), re.IGNORECASE)
        if m:
            val = m.group(1) + ('.' + m.group(2) if m.group(2) else '')
            return float(val)
        return None

    def normalize_rooms(self, text):
        if not text:
            return None
        m = re.search(r'(\d+)[,.]?(\d*)\s*(?:rok|rum|r)', str(text).replace(',', '.'), re.IGNORECASE)
        if m:
            val = m.group(1) + ('.' + m.group(2) if m.group(2) else '')
            return float(val)
        return None

    def normalize_fee(self, text):
        if not text:
            return None
        if any(w in text.lower() for w in ['avgift', 'kr/mån', 'kr/man', 'månads']):
            digits = re.sub(r'[^\d]', '', str(text))
            return int(digits) if digits else None
        return None

    def make_external_id(self, suffix):
        clean = re.sub(r'[^\w-]', '_', str(suffix))
        return f'{self.broker_slug}_{clean}'

    def scrape(self):
        raise NotImplementedError

    def safe_scrape(self):
        try:
            results = self.scrape()
            logger.info(f'[{self.broker_name}] Found {len(results)} listings in target area')
            return results
        except Exception as e:
            logger.error(f'[{self.broker_name}] Scrape failed: {e}', exc_info=True)
            return []
