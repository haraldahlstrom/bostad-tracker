"""
Fastighetsbyrån — fastighetsbyran.com
Search URL: /sv/sverige/till-salu/stockholms-lan/stockholms-stad/
Card: a[href*=objektID]
  p.text-xl = address
  p.text-xs.uppercase = area/neighborhood ("Maria", "Mariatorget", etc.)
  span in div.font-sans = price, rooms, size
"På gång" badge = upcoming
"""
import re
import logging
from urllib.parse import urljoin, parse_qs, urlparse

from .base import BaseScraper

logger = logging.getLogger(__name__)

BASE = 'https://www.fastighetsbyran.com'
SEARCH_URL = f'{BASE}/sv/sverige/till-salu/stockholms-lan/stockholms-stad/'

# Fastighetsbyrån uses "Maria" as the area label for Södermalm Maria
FB_AREA_KEYWORDS = [
    'maria', 'mariatorget', 'mariaberget', 'mosebacke',
    'södermalm maria', 'sodermalm-maria',
]


class Fastighetsbyran(BaseScraper):
    broker_name = 'Fastighetsbyrån'
    broker_slug = 'fastighetsbyran'

    def scrape(self):
        resp = self.get(SEARCH_URL)
        if not resp:
            return []

        soup = self.soup(resp.text)
        results = []
        seen = set()

        for item in soup.find_all('a', href=re.compile(r'objektID=')):
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

        # Address: p with text-xl class
        addr_el = item.find('p', class_=lambda c: c and 'text-xl' in c)
        address = addr_el.get_text(strip=True) if addr_el else ''

        # Area: p with text-xs and uppercase classes
        area_el = item.find('p', class_=lambda c: c and 'text-xs' in c and 'uppercase' in c)
        area = area_el.get_text(strip=True) if area_el else ''

        if not address:
            return None

        # Area filter: check area field first (more precise), then address
        area_lower = area.lower()
        if not (any(kw == area_lower or kw in area_lower for kw in FB_AREA_KEYWORDS)
                or self.is_in_target_area(address, area)):
            return None

        # Price, rooms, size from spans in font-sans div
        price = size = rooms = None
        details_div = item.find('div', class_=lambda c: c and 'font-sans' in c)
        if details_div:
            for span in details_div.find_all('span'):
                text = span.get_text(strip=True)
                if 'kr' in text and price is None:
                    price = self.normalize_price(text)
                elif ('rum' in text.lower() or 'rok' in text.lower()) and rooms is None:
                    rooms = self.normalize_rooms(text)
                elif 'kvm' in text.lower() and size is None:
                    size = self.normalize_size(text)

        # Image: try any img tag inside the card (Next.js SSR sometimes includes them)
        image_url = ''
        for img_tag in item.find_all('img'):
            src = (img_tag.get('src') or img_tag.get('data-src')
                   or img_tag.get('data-lazy-src') or '')
            if src and src.startswith('http') and not src.endswith('.svg'):
                image_url = src
                break

        # Status
        full_text = item.get_text().lower()
        status = 'upcoming' if any(w in full_text for w in ['på gång', 'kommande']) else 'active'

        # ID from URL
        qs = parse_qs(urlparse(href).query)
        listing_id = qs.get('objektID', [re.sub(r'[^\w]', '_', href)])[0]

        return {
            'external_id': self.make_external_id(listing_id),
            'broker': self.broker_name,
            'title': address,
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
