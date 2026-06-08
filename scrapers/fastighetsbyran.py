"""
Fastighetsbyrån — fastighetsbyran.com
Next.js site. Primary strategy: parse __NEXT_DATA__ JSON which contains all SSR
listing data including images and publication dates. HTML card fallback if JSON fails.

HTML card structure (fallback):
  a[href*=objektID]
    p.text-xl = address
    p.text-xs.uppercase = area/neighborhood
    span in div.font-sans = price, rooms, size
  "På gång" badge = upcoming
"""
import re
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin, parse_qs, urlparse

from .base import BaseScraper

logger = logging.getLogger(__name__)

BASE = 'https://www.fastighetsbyran.com'
SEARCH_URL = f'{BASE}/sv/sverige/till-salu/stockholms-lan/stockholms-stad/'

FB_AREA_KEYWORDS = [
    'maria', 'mariatorget', 'mariaberget', 'mosebacke',
    'södermalm maria', 'sodermalm maria', 'sodermalm-maria',
    'maria magdalena',
]


class Fastighetsbyran(BaseScraper):
    broker_name = 'Fastighetsbyrån'
    broker_slug = 'fastighetsbyran'

    def scrape(self):
        resp = self.get(SEARCH_URL)
        if not resp:
            return []

        soup = self.soup(resp.text)

        # Primary: __NEXT_DATA__ contains full SSR props including images + dates
        next_script = soup.find('script', id='__NEXT_DATA__')
        if next_script and next_script.string:
            try:
                results = self._parse_next_data(next_script.string)
                if results:
                    logger.info(f'[{self.broker_name}] Got {len(results)} via __NEXT_DATA__')
                    return results
            except Exception as e:
                logger.warning(f'[{self.broker_name}] __NEXT_DATA__ parse failed: {e}')

        # Fallback: HTML cards
        return self._parse_html(soup)

    # ── __NEXT_DATA__ path ────────────────────────────────────────────────

    def _parse_next_data(self, json_str):
        data = json.loads(json_str)
        page_props = data.get('props', {}).get('pageProps', {})

        # Try common field names for listing arrays
        raw = None
        search_targets = [page_props] + list(
            v for v in page_props.values() if isinstance(v, dict)
        )
        for container in search_targets:
            for key in ('listings', 'objects', 'estates', 'items', 'results',
                        'searchResult', 'hits'):
                candidate = container.get(key)
                if isinstance(candidate, list) and candidate:
                    raw = candidate
                    break
                if isinstance(candidate, dict):
                    for sub in ('listings', 'objects', 'items', 'results', 'hits'):
                        if isinstance(candidate.get(sub), list) and candidate[sub]:
                            raw = candidate[sub]
                            break
                if raw:
                    break
            if raw:
                break

        if not raw:
            return []

        results = []
        seen = set()
        for item in raw:
            try:
                d = self._parse_next_item(item)
                if d and d['external_id'] not in seen:
                    seen.add(d['external_id'])
                    results.append(d)
            except Exception as e:
                logger.debug(f'[{self.broker_name}] next_data item: {e}')
        return results

    def _parse_next_item(self, item):
        address = (item.get('address') or item.get('streetAddress') or
                   item.get('street') or '').strip()
        area = (item.get('area') or item.get('district') or
                item.get('neighborhood') or item.get('municipality') or '').strip()

        if not address:
            return None

        area_lower = area.lower()
        if not (any(kw in area_lower for kw in FB_AREA_KEYWORDS)
                or self.is_in_target_area(address, area)):
            return None

        # Price
        price_raw = (item.get('price') or item.get('askingPrice') or
                     item.get('startingPrice') or 0)
        price = self.normalize_price(str(price_raw)) if price_raw else None

        size = self.normalize_size(str(item.get('livingArea') or item.get('size') or ''))
        rooms = self.normalize_rooms(str(item.get('rooms') or item.get('numberOfRooms') or ''))

        # Image: check images array or single image field
        image_url = ''
        images = item.get('images') or item.get('photos') or []
        if isinstance(images, list) and images:
            first = images[0]
            image_url = (first.get('url') or first.get('src') or first.get('href') or ''
                         if isinstance(first, dict) else str(first))
        if not image_url:
            img_field = item.get('image') or item.get('imageUrl') or item.get('mainImage') or ''
            if isinstance(img_field, dict):
                image_url = img_field.get('url') or img_field.get('src') or ''
            elif isinstance(img_field, str):
                image_url = img_field
        if image_url and not image_url.startswith('http'):
            image_url = BASE + image_url

        # ID and URL
        obj_id = str(item.get('objektID') or item.get('id') or item.get('estateId') or '')
        if not obj_id:
            return None
        listing_url = f'{SEARCH_URL}?objektID={obj_id}'

        # Status
        status_raw = str(item.get('status') or item.get('saleStatus') or '').lower()
        status = ('upcoming' if any(w in status_raw for w in ['coming', 'kommande', 'upcoming'])
                  else 'active')

        # Publication date
        published_at = None
        date_raw = (item.get('publishedDate') or item.get('publishDate') or
                    item.get('listingDate') or item.get('createdAt') or
                    item.get('publishedAt') or '')
        if date_raw:
            try:
                dt = datetime.fromisoformat(str(date_raw).replace('Z', '+00:00'))
                published_at = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
            except Exception:
                pass

        return {
            'external_id': self.make_external_id(obj_id),
            'broker': self.broker_name,
            'title': address,
            'address': address,
            'area': area,
            'price': price,
            'size': size,
            'rooms': rooms,
            'floor': None,
            'monthly_fee': None,
            'url': listing_url,
            'image_url': image_url,
            'status': status,
            'published_at': published_at,
        }

    # ── HTML fallback ─────────────────────────────────────────────────────

    def _parse_html(self, soup):
        results = []
        seen = set()
        for item in soup.find_all('a', href=re.compile(r'objektID=')):
            try:
                data = self._parse_card(item)
                if data and data['external_id'] not in seen:
                    seen.add(data['external_id'])
                    results.append(data)
            except Exception as e:
                logger.debug(f'[{self.broker_name}] html card: {e}')
        return results

    def _parse_card(self, item):
        href = item.get('href', '')
        if not href:
            return None

        url = href if href.startswith('http') else urljoin(BASE, href)

        addr_el = item.find('p', class_=lambda c: c and 'text-xl' in c)
        address = addr_el.get_text(strip=True) if addr_el else ''

        area_el = item.find('p', class_=lambda c: c and 'text-xs' in c and 'uppercase' in c)
        area = area_el.get_text(strip=True) if area_el else ''

        if not address:
            return None

        area_lower = area.lower()
        if not (any(kw == area_lower or kw in area_lower for kw in FB_AREA_KEYWORDS)
                or self.is_in_target_area(address, area)):
            return None

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

        # Try any img tag (sometimes present in SSR)
        image_url = ''
        for img_tag in item.find_all('img'):
            src = (img_tag.get('src') or img_tag.get('data-src')
                   or img_tag.get('data-lazy-src') or '')
            if src and src.startswith('http') and not src.endswith('.svg'):
                image_url = src
                break

        full_text = item.get_text().lower()
        status = 'upcoming' if any(w in full_text for w in ['på gång', 'kommande']) else 'active'

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
            'published_at': None,
        }
