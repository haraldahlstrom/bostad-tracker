import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from models import db, Listing, ScrapeLog
from scrapers import ALL_SCRAPERS

logger = logging.getLogger(__name__)

_scheduler = None


def run_all_scrapers(app):
    with app.app_context():
        log = ScrapeLog()
        db.session.add(log)
        db.session.commit()

        total_found = 0
        total_new = 0

        for scraper_cls in ALL_SCRAPERS:
            scraper = scraper_cls()
            listings = scraper.safe_scrape()

            for data in listings:
                found, is_new = save_listing(data)
                if found:
                    total_found += 1
                if is_new:
                    total_new += 1

        # Mark listings not seen in last 45 minutes as inactive
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=45)
        stale = Listing.query.filter(
            Listing.active == True,
            Listing.last_seen < cutoff,
        ).all()
        for listing in stale:
            listing.active = False
            logger.info(f'Marked inactive: {listing.address} ({listing.broker})')

        log.finished_at = datetime.now(timezone.utc)
        log.listings_found = total_found
        log.listings_new = total_new
        db.session.commit()

        logger.info(f'Scrape done: {total_found} found, {total_new} new, {len(stale)} deactivated')


def save_listing(data):
    """Upsert a listing. Returns (was_saved, is_new)."""
    external_id = data.get('external_id')
    if not external_id:
        return False, False

    existing = Listing.query.filter_by(external_id=external_id).first()

    if existing:
        existing.last_seen = datetime.now(timezone.utc)
        existing.price = data.get('price') or existing.price
        existing.status = data.get('status', existing.status)
        existing.image_url = data.get('image_url') or existing.image_url
        existing.active = True
        db.session.commit()
        return True, False
    else:
        listing = Listing(
            external_id=external_id,
            broker=data.get('broker', ''),
            title=data.get('title', ''),
            address=data.get('address', ''),
            area=data.get('area', ''),
            price=data.get('price'),
            size=data.get('size'),
            rooms=data.get('rooms'),
            floor=data.get('floor'),
            monthly_fee=data.get('monthly_fee'),
            url=data.get('url', ''),
            image_url=data.get('image_url', ''),
            status=data.get('status', 'active'),
            active=True,
        )
        db.session.add(listing)
        db.session.commit()
        logger.info(f'New listing: {listing.address} — {listing.broker} [{listing.status}]')
        return True, True


def init_scheduler(app):
    global _scheduler
    if _scheduler is not None:
        return

    from config import Config
    interval = Config.SCRAPE_INTERVAL_MINUTES

    _scheduler = BackgroundScheduler(timezone='UTC')
    _scheduler.add_job(
        func=run_all_scrapers,
        trigger=IntervalTrigger(minutes=interval),
        args=[app],
        id='scrape_all',
        name='Scrape all brokers',
        replace_existing=True,
        misfire_grace_time=60,
    )
    _scheduler.start()
    logger.info(f'Scheduler started — scraping every {interval} minutes')

    import atexit
    atexit.register(lambda: _scheduler.shutdown(wait=False))
