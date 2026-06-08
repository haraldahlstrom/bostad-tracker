"""
Svensk Fastighetsförmedling — svenskfast.se
Search URL: /bostad/lagenhet/till-salu/stockholm/sodermalm/
Individual listings: /bostad/lagenhet/[id]/[slug]/
"""
import re
import logging
from urllib.parse import urljoin

from .base import BaseScraper

logger = logging.getLogger(__name__)

BASE = 'https://www.svenskfast.se'
SEARCH_URLS = [
    f'{BASE}/bostad/lagenhet/till-salu/stockholm/sodermalm/',
    f'{BASE}/bostad/till-salu/?types=bostadsratt&municipality=0180&q=mariatorget',
]


class Svenskfast(BaseScraper):
    broker_name = 'Svensk Fastighetsförmedling'
    broker_slug = 'svenskfast'

    def scrape(self):
        results = []
        seen = set()

        for search_url in SEARCH_URLS:
            resp = self.get(search_url)
            if not resp:
                logger.warning(f'[{self.broker_name}] Could not fetch {search_url}')
                continue

            soup = self.soup(resp.text)
            found_any = False

            # Try to find listing links
            patterns = [
                re.compile(r'/bostad/(lagenhet|bostadsratt)/\d+/'),
                re.compile(r'/bostad/\d+/'),
                re.compile(r'/till-salu/.+/\d+'),
            ]

            for pattern in patterns:
                for item in soup.find_all('a', href=pattern):
                    try:
                        data = self._parse_card(item)
                        if data and data['external_id'] not in seen:
                            seen.add(data['external_id'])
                            results.append(data)
                            found_any = True
                    except Exception as e:
                        logger.debug(f'[{self.broker_name}] parse error: {e}')
                if found_any:
                    break

        return results

    def _parse_card(self, item):
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

        heading = item.find(['h2', 'h3', 'h4'])
        address = heading.get_text(strip=True) if heading else ''

        area = ''
        for a in ['mariatorget', 'mariaberget', 'mosebacke']:
            if a in full_lower:
                area = a.title()
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

        id_match = re.search(r'/(\d+)/', href)
        listing_id = id_match.group(1) if id_match else re.sub(r'[^\w]', '_', href)

        status = 'upcoming' if any(w in full_lower for w in ['kommande', 'på gång', 'snart']) else 'active'

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
