"""
Bjurfors — bjurfors.se
Only scrapes sodermalm-maria area.
Card structure:
  div.c-object-card
    img.c-object-card__image           (data-srcset has full image)
    span.c-object-card__city-area      (area text)
    span.c-object-card__address        (street address)
    li.c-object-card__meta             (size kvm / rooms)
    span.c-tag.flag-development        ("På förhand" = upcoming)
Individual URLs: /sv/tillsalu/stockholm/stockholm/sodermalm-maria/[slug]/
"""
import re
import logging
from urllib.parse import urljoin

from .base import BaseScraper

logger = logging.getLogger(__name__)


def _first_srcset_url(srcset: str) -> str:
    """Return the first URL from a srcset string.
    Splits by whitespace so Cloudflare CDN params (format=webp,width=640) don't break parsing."""
    for token in srcset.split():
        token = token.rstrip(',')
        if token.startswith('http') or (token.startswith('/') and '.' in token.split('/')[-1]):
            return token
    return ''


BASE = 'https://www.bjurfors.se'
AREA_URL = f'{BASE}/sv/tillsalu/stockholm/stockholm/sodermalm-maria/'


class Bjurfors(BaseScraper):
    broker_name = 'Bjurfors'
    broker_slug = 'bjurfors'

    def scrape(self):
        resp = self.get(AREA_URL)
        if not resp:
            logger.warning(f'[{self.broker_name}] Could not fetch {AREA_URL}')
            return []

        soup = self.soup(resp.text)
        results = []
        seen = set()

        for card in soup.find_all('div', class_='c-object-card'):
            try:
                data = self._parse_card(card)
                if data and data['external_id'] not in seen:
                    seen.add(data['external_id'])
                    results.append(data)
            except Exception as e:
                logger.debug(f'[{self.broker_name}] parse error: {e}')

        return results

    def _parse_card(self, card):
        link = card.find('a', class_='c-object-card__link')
        if not link:
            return None

        href = link.get('href', '')
        if not href or 'sodermalm-maria' not in href:
            return None

        url = urljoin(BASE, href)

        area_span = card.find('span', class_='c-object-card__city-area')
        addr_span = card.find('span', class_='c-object-card__address')
        area_text = area_span.get_text(strip=True) if area_span else 'Södermalm Maria'
        address = addr_span.get_text(strip=True) if addr_span else ''

        if not address:
            return None

        # Parse meta items (size, rooms)
        size = rooms = price = None
        for meta in card.find_all('li', class_='c-object-card__meta'):
            text = meta.get_text(strip=True)
            if ('kvm' in text or 'm²' in text) and size is None:
                size = self.normalize_size(text)
            elif ('rum' in text or 'rok' in text) and rooms is None:
                rooms = self.normalize_rooms(text)
            elif 'kr' in text and price is None:
                price = self.normalize_price(text)

        # Status
        tags = card.find_all('span', class_='c-tag')
        tag_texts = [t.get_text(strip=True).lower() for t in tags]
        status = 'upcoming' if any('på förhand' in t or 'kommande' in t for t in tag_texts) else 'active'

        # Sold check
        if any('såld' in t for t in tag_texts):
            return None

        # Image — extract original path from Cloudflare cdn-cgi transform URL
        # Cloudflare params contain commas (format=webp,width=640) so we cannot
        # split srcset by comma — split by whitespace instead and pick first URL.
        image_url = ''
        img = card.find('img', class_='c-object-card__image')
        if img:
            srcset = img.get('data-srcset') or img.get('srcset', '')
            if srcset:
                image_url = _first_srcset_url(srcset)
            if not image_url:
                image_url = img.get('data-src') or img.get('src', '')
        if not image_url:
            source = card.find('source', attrs={'data-srcset': True})
            if source:
                image_url = _first_srcset_url(source.get('data-srcset', ''))
        if image_url and not image_url.startswith('http'):
            image_url = BASE + image_url
        # Strip Cloudflare transformation: /cdn-cgi/image/[params]/[path] -> BASE/[path]
        cdn_match = re.search(r'/cdn-cgi/image/[^/]+/(.+)', image_url)
        if cdn_match:
            path = cdn_match.group(1)
            image_url = path if path.startswith('http') else BASE + '/' + path

        slug = href.rstrip('/').split('/')[-1]
        return {
            'external_id': self.make_external_id(slug),
            'broker': self.broker_name,
            'title': address,
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
