"""
SkandiaMäklarna — skandiamaklarna.se (powered by quedro.com)
Fetches the general Södermalm page and filters by area keywords.
Individual listing URLs: /hitta-hem/[type]/[municipality]/[area]/[id]/
Images: mp1.skm.quedro.com
"""
import re
import logging
from urllib.parse import urljoin

from .base import BaseScraper

logger = logging.getLogger(__name__)

BASE = 'https://www.skandiamaklarna.se'
SEARCH_URL = f'{BASE}/hitta-hem/lagenhet/stockholm/sodermalm/'


class Skandiamaklarna(BaseScraper):
    broker_name = 'SkandiaMäklarna'
    broker_slug = 'skandiamaklarna'

    def scrape(self):
        resp = self.get(SEARCH_URL)
        if not resp:
            return []

        soup = self.soup(resp.text)
        results = []
        seen = set()

        # Listing links: /hitta-hem/[type]/[municipality]/[area]/[id]/
        for item in soup.find_all('a', href=re.compile(r'/hitta-hem/[^/]+/[^/]+/[^/]+/\d+')):
            try:
                data = self._parse_card(item)
                if data and data['external_id'] not in seen:
                    seen.add(data['external_id'])
                    results.append(data)
            except Exception as e:
                logger.debug(f'[{self.broker_name}] parse error: {e}')

        return results

    def _parse_card(self, item):
        href = item.get('href', '')
        if not href:
            return None

        url = href if href.startswith('http') else urljoin(BASE, href)

        full_text = item.get_text(' ', strip=True)
        full_lower = full_text.lower()

        # Filter: only keep target areas
        if not self.is_in_target_area(full_text):
            # Also check URL path for area names
            if not self.is_in_target_area(href):
                return None

        if 'såld' in full_lower:
            return None

        heading = item.find(['h3', 'h2'])
        address = heading.get_text(strip=True) if heading else ''

        # Area from URL path: /hitta-hem/[type]/[municipality]/[area-slug]/
        parts = href.rstrip('/').split('/')
        area = parts[-2].replace('-', ' ').title() if len(parts) >= 3 else ''

        price = None
        m = re.search(r'(\d[\d\s]{3,})\s*kr', full_text)
        if m:
            price = self.normalize_price(m.group(0))

        size = self.normalize_size(full_text)
        rooms = self.normalize_rooms(full_text)

        img = item.find('img')
        image_url = (img.get('src') or img.get('data-src') or '') if img else ''
        if image_url.startswith('//'):
            image_url = 'https:' + image_url

        id_match = re.search(r'/(\d+)/?$', href)
        listing_id = id_match.group(1) if id_match else re.sub(r'[^\w]', '_', href)

        return {
            'external_id': self.make_external_id(listing_id),
            'broker': self.broker_name,
            'title': address or full_text[:60],
            'address': address,
            'area': area,
            'price': price,
            'size': size,
            'rooms': rooms,
            'floor': None,
            'monthly_fee': None,
            'url': url,
            'image_url': image_url,
            'status': 'active',
        }
