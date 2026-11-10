from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import get_settings

DATABASE_URL = get_settings().database_url

# pool_pre_ping: Neon suspends after ~5 idle minutes and drops every open
# connection, but the API (kept warm by the /health pings) keeps them in its
# pool. Without this, the first request after a suspend got a dead
# connection and the page failed to load until a reload.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

class Base(DeclarativeBase):
    pass