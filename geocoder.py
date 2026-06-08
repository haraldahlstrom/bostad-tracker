import time
import logging
import requests

logger = logging.getLogger(__name__)

_NOMINATIM = 'https://nominatim.openstreetmap.org/search'
_HEADERS = {
    'User-Agent': 'BostadTracker/1.0 (haraldahlstrom@gmail.com)',
    'Accept-Language': 'sv',
}
_last_request = 0.0


def geocode(address: str) -> tuple[float, float] | None:
    """Return (lat, lng) for a Swedish address, or None on failure.
    Respects Nominatim's 1 req/s policy.
    """
    global _last_request
    wait = 1.1 - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)

    query = address if 'stockholm' in address.lower() else address + ', Stockholm, Sverige'
    try:
        resp = requests.get(
            _NOMINATIM,
            params={'q': query, 'format': 'json', 'limit': 1, 'countrycodes': 'se'},
            headers=_HEADERS,
            timeout=10,
        )
        _last_request = time.monotonic()
        resp.raise_for_status()
        results = resp.json()
        if results:
            return float(results[0]['lat']), float(results[0]['lon'])
    except Exception as e:
        logger.debug(f'Geocode failed for "{address}": {e}')
    return None
