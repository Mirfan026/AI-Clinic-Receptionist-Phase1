from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.config.settings import get_settings
from .models import Base

def get_engine():
    url = get_settings().database_url
    engine = create_engine(url, future=True, pool_pre_ping=True)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
    return engine

def get_session_factory(engine=None):
    return sessionmaker(bind=engine or get_engine(), autoflush=False, expire_on_commit=False, future=True)

def initialize_database(engine=None):
    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    return engine
