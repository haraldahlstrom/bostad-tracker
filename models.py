from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Listing(db.Model):
    __tablename__ = 'listings'

    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(500), unique=True, nullable=False, index=True)
    broker = db.Column(db.String(100), nullable=False, index=True)
    title = db.Column(db.String(500))
    address = db.Column(db.String(500))
    area = db.Column(db.String(200))
    price = db.Column(db.BigInteger)
    size = db.Column(db.Float)
    rooms = db.Column(db.Float)
    floor = db.Column(db.String(50))
    monthly_fee = db.Column(db.Integer)
    url = db.Column(db.String(2000))
    image_url = db.Column(db.String(2000))
    status = db.Column(db.String(50), default='active', index=True)
    first_seen = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    active = db.Column(db.Boolean, default=True, index=True)

    def is_new(self, hours=24):
        if not self.first_seen:
            return False
        now = datetime.now(timezone.utc)
        first = self.first_seen.replace(tzinfo=timezone.utc) if self.first_seen.tzinfo is None else self.first_seen
        return (now - first).total_seconds() < hours * 3600

    def to_dict(self, new_hours=24):
        return {
            'id': self.id,
            'external_id': self.external_id,
            'broker': self.broker,
            'title': self.title,
            'address': self.address,
            'area': self.area,
            'price': self.price,
            'size': self.size,
            'rooms': self.rooms,
            'floor': self.floor,
            'monthly_fee': self.monthly_fee,
            'url': self.url,
            'image_url': self.image_url,
            'status': self.status,
            'is_new': self.is_new(new_hours),
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'active': self.active,
        }


class ScrapeLog(db.Model):
    __tablename__ = 'scrape_logs'

    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = db.Column(db.DateTime)
    listings_found = db.Column(db.Integer, default=0)
    listings_new = db.Column(db.Integer, default=0)
    error = db.Column(db.Text)

    def to_dict(self):
        return {
            'id': self.id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'listings_found': self.listings_found,
            'listings_new': self.listings_new,
            'error': self.error,
        }
