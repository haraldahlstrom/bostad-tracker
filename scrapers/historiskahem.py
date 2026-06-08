"""
Historiska Hem — historiskahem.se
Static WordPress/Kowboy CMS. Cards are <a href="/object/..."> elements.

Structure:
  div.object-image > span.object-badge       ("Snart till salu", "Budgivning pågår", …)
  div.object-image > img.wp-post-image       listing image
  div.object-info  > h2.hh_header            neighborhood
  div.object-info  > ul.object-meta > li     [address, rooms, size, price]
"""
import re
import logging
from urllib.parse import urljoin

from .base import BaseScraper

logger = logging.getLogger(__name__)

BASE = 'https://www.historiskahem.se'
URLS = [
    f'{BASE}/till-salu/',
    f'{BASE}/kommande/',
]


class Historiskahem(BaseScraper):
    broker_name = 'Historiska Hem'
    broker_slug = 'historiskahem'

    def scrape(self):
        results = []
        seen = set()
        for url in URLS:
            resp = self.get(url)
            if not resp:
                continue
            soup = self.soup(resp.text)
            for card in soup.find_all('a', href=lambda h: h and '/object/' in h):
                try:
                    data = self._parse_card(card)
                    if data and data['external_id'] not in seen:
                        seen.add(data['external_id'])
                        results.append(data)
                except Exception as e:
                    logger.debug(f'[{self.broker_name}] parse error: {e}')
        return results

    def _parse_card(self, card):
        href = card.get('href', '')
        if not href:
            return None

        url = href if href.startswith('http') else urljoin(BASE, href)

        # Area from h2 inside object-info
        info_div = card.find('div', class_='object-info')
        area_h2 = info_div.find('h2') if info_div else None
        area = area_h2.get_text(strip=True) if area_h2 else ''

        # Details from ul.object-meta > li
        meta = card.find('ul', class_='object-meta')
        items = [li.get_text(strip=True) for li in meta.find_all('li')] if meta else []

        address = items[0] if len(items) > 0 else ''
        if not address:
            return None

        if not self.is_in_target_area(address, area, href):
            return None

        rooms = self.normalize_rooms(items[1]) if len(items) > 1 else None
        size = self.normalize_size(items[2]) if len(items) > 2 else None
        price = self.normalize_price(items[3]) if len(items) > 3 else None

        # Image: wp-post-image inside object-image div
        image_url = ''
        img = card.find('img', class_='wp-post-image')
        if img:
            image_url = img.get('src') or img.get('data-src') or ''
        if not image_url:
            img2 = card.find('img')
            if img2:
                image_url = img2.get('src') or img2.get('data-src') or ''

        # Status from badge
        badge = card.find('span', class_='object-badge')
        badge_text = badge.get_text(strip=True).lower() if badge else ''
        if any(w in badge_text for w in ['snart', 'kommande', 'förhand']):
            status = 'upcoming'
        else:
            status = 'active'

        # External ID: extract OBJ… part from URL slug
        obj_match = re.search(r'(OBJ[A-Z0-9]+)', href.upper())
        ext_id = obj_match.group(1).lower() if obj_match else href.rstrip('/').split('/')[-1]

        return {
            'external_id': self.make_external_id(ext_id),
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
