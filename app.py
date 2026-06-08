import os
import logging
import threading
from urllib.parse import urlparse, unquote

import requests
from sqlalchemy import inspect, text
from flask import Flask, render_template, jsonify, request, Response, abort

from config import Config
from models import db, Listing, ScrapeLog

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)


def _migrate_add_geocols(db):
    try:
        cols = [c['name'] for c in inspect(db.engine).get_columns('listings')]
        with db.engine.connect() as conn:
            if 'lat' not in cols:
                conn.execute(text('ALTER TABLE listings ADD COLUMN lat FLOAT'))
            if 'lng' not in cols:
                conn.execute(text('ALTER TABLE listings ADD COLUMN lng FLOAT'))
            if 'published_at' not in cols:
                conn.execute(text('ALTER TABLE listings ADD COLUMN published_at TIMESTAMP'))
            conn.commit()
    except Exception:
        pass


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        _migrate_add_geocols(db)

    from scheduler import init_scheduler, run_all_scrapers
    init_scheduler(app)

    # ── Routes ──────────────────────────────────────────────────────────

    @app.route('/')
    def index():
        brokers = [r[0] for r in db.session.query(Listing.broker).distinct().order_by(Listing.broker).all()]
        return render_template('index.html', brokers=brokers)

    @app.route('/api/listings')
    def api_listings():
        q = Listing.query.filter_by(active=True)

        # Filters
        min_price = request.args.get('min_price', type=int)
        max_price = request.args.get('max_price', type=int)
        min_size = request.args.get('min_size', type=float)
        max_size = request.args.get('max_size', type=float)
        min_rooms = request.args.get('min_rooms', type=float)
        status = request.args.get('status')        # 'active', 'upcoming', or omitted for both
        broker = request.args.get('broker')
        sort = request.args.get('sort', 'newest')

        if min_price is not None:
            q = q.filter(Listing.price >= min_price)
        if max_price is not None:
            q = q.filter(Listing.price <= max_price)
        if min_size is not None:
            q = q.filter(Listing.size >= min_size)
        if max_size is not None:
            q = q.filter(Listing.size <= max_size)
        if min_rooms is not None:
            q = q.filter(Listing.rooms >= min_rooms)
        if status in ('active', 'upcoming'):
            q = q.filter(Listing.status == status)
        if broker:
            q = q.filter(Listing.broker == broker)

        if sort == 'price_asc':
            q = q.order_by(Listing.price.asc().nulls_last())
        elif sort == 'price_desc':
            q = q.order_by(Listing.price.desc().nulls_last())
        elif sort == 'size_asc':
            q = q.order_by(Listing.size.asc().nulls_last())
        elif sort == 'size_desc':
            q = q.order_by(Listing.size.desc().nulls_last())
        elif sort == 'published_desc':
            q = q.order_by(
                Listing.published_at.desc().nulls_last(),
                Listing.first_seen.desc(),
            )
        else:
            q = q.order_by(Listing.first_seen.desc())

        listings = q.limit(500).all()
        new_hours = app.config.get('NEW_LISTING_HOURS', 24)
        return jsonify([l.to_dict(new_hours) for l in listings])

    @app.route('/api/status')
    def api_status():
        total = Listing.query.filter_by(active=True).count()
        upcoming = Listing.query.filter_by(active=True, status='upcoming').count()
        last_log = ScrapeLog.query.order_by(ScrapeLog.started_at.desc()).first()
        return jsonify({
            'total': total,
            'upcoming': upcoming,
            'last_scrape': last_log.to_dict() if last_log else None,
        })

    @app.route('/api/scrape', methods=['POST'])
    def api_scrape():
        from scheduler import run_all_scrapers
        thread = threading.Thread(target=run_all_scrapers, args=[app], daemon=True)
        thread.start()
        return jsonify({'status': 'started'})

    @app.route('/api/proxy')
    def image_proxy():
        raw_url = request.args.get('url', '')
        if not raw_url:
            abort(400)

        url = unquote(raw_url)
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().lstrip('www.')
        except Exception:
            abort(400)

        allowed = app.config.get('ALLOWED_IMAGE_DOMAINS', [])
        if not any(domain == d or domain.endswith('.' + d) or d in domain for d in allowed):
            logger.warning(f'Proxy blocked domain: {domain}')
            abort(403)

        try:
            resp = requests.get(
                url,
                timeout=10,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; BostadTracker/1.0)',
                    'Referer': parsed.scheme + '://' + parsed.netloc + '/',
                },
                stream=True,
            )
            content_type = resp.headers.get('Content-Type', 'image/jpeg')
            if not content_type.startswith('image/'):
                abort(415)

            return Response(
                resp.content,
                content_type=content_type,
                headers={
                    'Cache-Control': 'public, max-age=3600',
                    'X-Content-Type-Options': 'nosniff',
                },
            )
        except requests.RequestException as e:
            logger.warning(f'Proxy fetch failed for {url}: {e}')
            abort(502)

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
