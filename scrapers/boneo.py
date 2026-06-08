"""
Boneo — boneo.se
Search URL: /sv/till_salu/bostadsratt/stockholm/stockholm
Individual listings: /bostad/id-[ID]-bostadsratt-[rooms]rum-[location]
Images: files.boneo.se/target_styles/properties/
Status: "På G" tab = upcoming
"""
import re
import logging
from urllib.parse import urljoin

from .base import BaseScraper

logger = logging.getLogger(__name__)

BASE = 'https://www.boneo.se'
SEARCH_URL = f'{BASE}/sv/till_salu/bostadsratt/stockholm/stockholm'
UPCOMING_URL = f'{BASE}/sv/till_salu/bostadsratt/stockholm/stockholm?status=upcoming'


class Boneo(BaseScraper):
    broker_name = 'Boneo'
    broker_slug = 'boneo'

    def scrape(self):
        results = []
        seen = set()

        for url, status in [(SEARCH_URL, 'active'), (UPCOMING_URL, 'upcoming')]:
            resp = self.get(url)
            if not resp:
                continue

            soup = self.soup(resp.text)

            for item in soup.find_all('a', href=re.compile(r'/bostad/id-')):
                try:
                    data = self._parse_card(item, default_status=status)
                    if data and data['external_id'] not in seen:
                        seen.add(data['external_id'])
                        results.append(data)
                except Exception as e:
                    logger.debug(f'[{self.broker_name}] parse error: {e}')

        return results

    def _parse_card(self, item, default_status='active'):
        href = item.get('href', '')
        if not href:
            return None

        url = urljoin(BASE, href)
        full_text = item.get_text(' ', strip=True)
        full_lower = full_text.lower()

        if 'såld' in full_lower:
            return None
        if not self.is_in_target_area(full_text):
            return None

        # Address in h3 or first heading
        heading = item.find(['h3', 'h2', 'h4'])
        address = heading.get_text(strip=True) if heading else ''

        # Area from secondary text
        area = ''
        for a in ['mariatorget', 'mariaberget', 'mosebacke', 'södermalm']:
            if a in full_lower:
                area = a.title()
                if a != 'södermalm':
                    break

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

        # ID from URL pattern: /bostad/id-[ID]-bostadsratt-...
        id_match = re.search(r'/bostad/id-(\d+)-', href)
        listing_id = id_match.group(1) if id_match else re.sub(r'[^\w]', '_', href)

        status_in_text = any(w in full_lower for w in ['på g', 'kommande', 'snart'])
        status = 'upcoming' if (status_in_text or default_status == 'upcoming') else 'active'

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
            'status': status,
        }
