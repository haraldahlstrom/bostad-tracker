"""
Mäklarhuset — maklarhuset.se
Search URL: /bostad/sverige/stockholms-lan/stockholm-kommun/sodermalm?view=list&sortby=datepublished-desc
Card: div.mh-object containing two a.mh-card (image + text)
  Text card has: div.mh-card-header-title, div.mh-card-title-small, div.mh-card-subtitle-small
Status: "Kommande försäljning" badge = upcoming
"""
import re
import logging
from urllib.parse import urljoin

from .base import BaseScraper

logger = logging.getLogger(__name__)

BASE = 'https://www.maklarhuset.se'
SEARCH_URL = (
    f'{BASE}/bostad/sverige/stockholms-lan/stockholm-kommun/sodermalm'
    '?page=0&view=list&sortby=datepublished-desc'
)


class Maklarhuset(BaseScraper):
    broker_name = 'Mäklarhuset'
    broker_slug = 'maklarhuset'

    def scrape(self):
        resp = self.get(SEARCH_URL)
        if not resp:
            return []

        soup = self.soup(resp.text)
        results = []
        seen = set()

        for obj in soup.find_all('div', class_='mh-object'):
            try:
                data = self._parse_card(obj)
                if data and data['external_id'] not in seen:
                    seen.add(data['external_id'])
                    results.append(data)
            except Exception as e:
                logger.debug(f'[{self.broker_name}] parse error: {e}')

        return results

    def _parse_card(self, obj):
        # Second mh-card link contains text data
        links = obj.find_all('a', class_='mh-card')
        text_link = links[-1] if len(links) >= 2 else (links[0] if links else None)
        if not text_link:
            return None

        href = text_link.get('href', '')
        if not href:
            return None

        url = urljoin(BASE, href)

        # Address
        addr_el = obj.find('div', class_='mh-card-title-small')
        address = addr_el.get_text(strip=True) if addr_el else ''

        # City/area from header
        header_el = obj.find('div', class_='mh-card-header-title')
        area = header_el.get_text(' ', strip=True) if header_el else ''
        area = re.sub(r'\s+', ' ', area).strip()

        if not address:
            # Fallback: from img alt
            img = obj.find('img')
            if img:
                address = img.get('alt', '').split(',')[0].strip()

        if not address:
            return None

        if not self.is_in_target_area(address, area):
            return None

        # Stats: spans in mh-card-subtitle-small
        sub_el = obj.find('div', class_='mh-card-subtitle-small')
        price = size = rooms = None
        if sub_el:
            for span in sub_el.find_all('span'):
                text = span.get_text(strip=True)
                if 'kr' in text and price is None:
                    price = self.normalize_price(text)
                elif ('rum' in text.lower() or 'rok' in text.lower()) and rooms is None:
                    rooms = self.normalize_rooms(text)
                elif 'kvm' in text.lower() and size is None:
                    size = self.normalize_size(text)

        # Image from first mh-card
        img_link = links[0] if links else None
        image_url = ''
        if img_link:
            img = img_link.find('img')
            if img:
                image_url = img.get('src') or img.get('data-src') or ''

        # Status: badge text
        badge = obj.find('div', class_='uk-badge')
        badge_text = badge.get_text(strip=True).lower() if badge else ''
        status = 'upcoming' if any(w in badge_text for w in ['kommande', 'förberedd']) else 'active'

        # Sold check
        if 'såld' in obj.get_text().lower():
            return None

        # Extract numeric ID from URL
        id_match = re.search(r'/(\d+)$', href.rstrip('/'))
        listing_id = id_match.group(1) if id_match else re.sub(r'[^\w]', '_', href)

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
