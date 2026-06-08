import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    DATABASE_URL = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{os.path.join(_BASE_DIR, "bostad.db")}',
    )
    # Railway returns postgres:// but SQLAlchemy needs postgresql://
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
    }

    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
    SCRAPE_INTERVAL_MINUTES = int(os.environ.get('SCRAPE_INTERVAL_MINUTES', '15'))
    NEW_LISTING_HOURS = int(os.environ.get('NEW_LISTING_HOURS', '24'))

    # Neighborhoods to track (used in post-scrape filtering)
    TARGET_AREAS = ['mariatorget', 'mariaberget', 'mosebacke']

    # Streets that are exclusively within the three target areas
    TARGET_STREETS = [
        'bastugatan',
        'blecktornsbacken',
        'bryggargränd',
        'urvädersgränd',
        'stigbergsgatan',
        'fiskarbacken',
        'pysslargränd',
        'mosebacke torg',
        'svartensgatan',
        'katarinavägen',
        'erstaviksbacken',
        'ivar los park',
    ]

    # Allowed image proxy domains (suffix match)
    ALLOWED_IMAGE_DOMAINS = [
        'sm.maklarobjekt.se',
        'bjurfors.se',
        'mp1.skm.quedro.com',
        'skm.quedro.com',
        'files.boneo.se',
        'fastighetsbyran.com',
        'maklarhuset.se',
        'skandiamaklarna.se',
        'sodermaklarna.se',
        'boneo.se',
        'svenskfast.se',
        'cloudfront.net',
        'imgix.net',
        'vitecfastighet.se',
        'maklarobjekt.se',
        'quedro.com',
    ]
