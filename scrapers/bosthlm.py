"""
BOSTHLM — bosthlm.se
Stockholm/Södermalm boutique broker.
Listing data is embedded in the page as:
  var listings = JSON.parse("{...}");
Fields: fasad_id, address, district, rooms_text, area_text, price_text,
        current, upcoming, websiteUrl, image.srcset
"""
import re
import json
import logging

from .base import BaseScraper

logger = logging.getLogger(__name__)

BASE = 'https://www.bosthlm.se'
LISTINGS_URL = f'{BASE}/till-salu/'


class Bosthlm(BaseScraper):
    broker_name = 'BOSTHLM'
    broker_slug = 'bosthlm'

    def scrape(self):
        resp = self.get(LISTINGS_URL)
        if not resp:
            return []

        match = re.search(r'var listings\s*=\s*JSON\.parse\("(.+?)"\);', resp.text, re.DOTALL)
        if not match:
            logger.warning(f'[{self.broker_name}] listings JSON not found in page')
            return []

        try:
            inner_str = json.loads('"' + match.group(1) + '"')
            data = json.loads(inner_str)
        except Exception as e:
            logger.warning(f'[{self.broker_name}] JSON parse error: {e}')
            return []

        results = []
        seen = set()
        for item in data.get('listings', []):
            try:
                d = self._parse_item(item)
                if d and d['external_id'] not in seen:
                    seen.add(d['external_id'])
                    results.append(d)
            except Exception as e:
                logger.debug(f'[{self.broker_name}] item error: {e}')

        return results

    def _parse_item(self, item):
        address = item.get('address', '').strip()
        district = item.get('district', '').strip()

        if not address:
            return None

        if not self.is_in_target_area(address, district):
            return None

        fasad_id = item.get('fasad_id')
        website_url = item.get('websiteUrl', '')
        url = BASE + website_url if website_url else BASE

        price = self.normalize_price(item.get('price_text', ''))
        size = self.normalize_size(item.get('area_text', ''))
        rooms = self.normalize_rooms(item.get('rooms_text', ''))

        # Image: pick highest-res from srcset
        image_url = ''
        srcset = item.get('image', {}).get('srcset', '')
        if srcset:
            parts = [s.strip().split(' ')[0] for s in srcset.split(',') if s.strip()]
            if parts:
                last = parts[-1]
                image_url = BASE + last if last.startswith('/') else last

        status = 'upcoming' if item.get('upcoming') else 'active'

        return {
            'external_id': self.make_external_id(str(fasad_id)),
            'broker': self.broker_name,
            'title': address,
            'address': address,
            'area': district,
            'price': price,
            'size': size,
            'rooms': rooms,
            'floor': None,
            'monthly_fee': None,
            'url': url,
            'image_url': image_url,
            'status': status,
        }
