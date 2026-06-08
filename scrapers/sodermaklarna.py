"""
Södermäklarna — sodermaklarna.se
Vitec-based platform. Card structure (a.oc-link):
  data-address, data-area, data-livingarea, data-price attributes
  h2.oc-sub-title = neighborhood
  span.address-heading = street address
  div.oc-fact = size/rooms/price
  div.oc-tag.kommande = upcoming status
  img.src = image (sm.maklarobjekt.se)
"""
import re
import logging
from urllib.parse import urljoin

from .base import BaseScraper

logger = logging.getLogger(__name__)

BASE = 'https://www.sodermaklarna.se'


class Sodermaklarna(BaseScraper):
    broker_name = 'Södermäklarna'
    broker_slug = 'sodermaklarna'

    def scrape(self):
        resp = self.get(f'{BASE}/till-salu/')
        if not resp:
            return []

        soup = self.soup(resp.text)
        results = []
        seen = set()

        # Cards are <a class="oc-link card mix forsale ...">
        for item in soup.find_all('a', class_='oc-link'):
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
        if not href or '/bostad/' not in href:
            return None

        url = href if href.startswith('http') else urljoin(BASE, href)

        # Use data attributes when available (fast and reliable)
        address = item.get('data-address', '')
        area_text = item.get('data-area', '')
        price_raw = item.get('data-price', '')
        size_raw = item.get('data-livingarea', '')

        # Fallback to DOM elements
        if not address:
            addr_el = item.find('span', class_='address-heading')
            address = addr_el.get_text(strip=True) if addr_el else ''
        if not area_text:
            area_el = item.find('h2', class_='oc-sub-title')
            area_text = area_el.get_text(strip=True) if area_el else ''

        if not address and not area_text:
            return None

        if not self.is_in_target_area(address, area_text):
            return None

        # Price and size
        price = int(price_raw) if price_raw and price_raw.isdigit() else None
        size = float(size_raw) if size_raw else None

        if price is None or size is None:
            for fact in item.find_all('div', class_='oc-fact'):
                text = fact.get_text(strip=True)
                if 'kr' in text and price is None:
                    price = self.normalize_price(text)
                elif ('kvm' in text or 'm²' in text) and size is None:
                    size = self.normalize_size(text)

        # Rooms from facts
        rooms = None
        for fact in item.find_all('div', class_='oc-fact'):
            text = fact.get_text(strip=True)
            if ('rum' in text or 'rok' in text) and rooms is None:
                rooms = self.normalize_rooms(text)

        # Image
        img = item.find('img')
        image_url = (img.get('src') or img.get('data-src') or '') if img else ''
        if image_url.startswith('//'):
            image_url = 'https:' + image_url

        # Status
        tags = item.find_all('div', class_='oc-tag')
        tag_classes = ' '.join(' '.join(t.get('class', [])) for t in tags).lower()
        tag_texts = ' '.join(t.get_text(strip=True).lower() for t in tags)

        if 'såld' in tag_texts or 'sold' in tag_classes:
            return None
        status = 'upcoming' if 'kommande' in tag_classes or 'snart' in tag_texts else 'active'

        # External ID from URL slug
        slug = href.rstrip('/').split('/')[-1]
        return {
            'external_id': self.make_external_id(slug),
            'broker': self.broker_name,
            'title': address or area_text,
            'address': address,
            'area': area_text,
            'price': price,
            'size': size,
            'rooms': rooms,
            'floor': None,
            'monthly_fee': None,
            'url': url,
            'image_url': image_url,
            'status': status,
        }
