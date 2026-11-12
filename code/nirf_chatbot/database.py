"""
Database engine for the NIRF chatbot.

Creates a single SQLAlchemy engine using the DATABASE_URL from settings.
All other modules import ``engine`` from here.
"""

from sqlalchemy import create_engine
from nirf_chatbot.Settings import database_url

engine = create_engine(
    database_url(),
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
)
