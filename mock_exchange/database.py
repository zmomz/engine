"""
Database initialization and session management for mock exchange.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from models import Base, Symbol, APIKey, Balance

# Database path
DB_PATH = os.getenv("MOCK_EXCHANGE_DB", "mock_exchange.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database and create tables."""
    Base.metadata.create_all(bind=engine)

    # Seed default data
    with get_db_session() as db:
        _seed_default_symbols(db)
        _seed_default_api_key(db)


@contextmanager
def get_db_session() -> Session:
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    """Dependency for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _seed_default_symbols(db: Session):
    """Seed default trading symbols if none exist."""
    existing = db.query(Symbol).first()
    if existing:
        return

    default_symbols = [
        # Major pairs
        Symbol(
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            tick_size=0.01,
            step_size=0.001,
            min_qty=0.001,
            max_qty=1000.0,
            min_notional=10.0,
            current_price=95000.0,
            mark_price=95000.0,
            index_price=95000.0,
        ),
        Symbol(
            symbol="ETHUSDT",
            base_asset="ETH",
            quote_asset="USDT",
            tick_size=0.01,
            step_size=0.001,
            min_qty=0.001,
            max_qty=10000.0,
            min_notional=10.0,
            current_price=3400.0,
            mark_price=3400.0,
            index_price=3400.0,
        ),
        Symbol(
            symbol="SOLUSDT",
            base_asset="SOL",
            quote_asset="USDT",
            tick_size=0.001,
            step_size=0.01,
            min_qty=0.01,
            max_qty=100000.0,
            min_notional=5.0,
            current_price=190.0,
            mark_price=190.0,
            index_price=190.0,
        ),
        Symbol(
            symbol="ADAUSDT",
            base_asset="ADA",
            quote_asset="USDT",
            tick_size=0.0001,
            step_size=0.1,
            min_qty=1.0,
            max_qty=10000000.0,
            min_notional=5.0,
            current_price=0.90,
            mark_price=0.90,
            index_price=0.90,
        ),
        Symbol(
            symbol="XRPUSDT",
            base_asset="XRP",
            quote_asset="USDT",
            tick_size=0.0001,
            step_size=0.1,
            min_qty=1.0,
            max_qty=10000000.0,
            min_notional=5.0,
            current_price=2.30,
            mark_price=2.30,
            index_price=2.30,
        ),
        Symbol(
            symbol="DOGEUSDT",
            base_asset="DOGE",
            quote_asset="USDT",
            tick_size=0.00001,
            step_size=1.0,
            min_qty=1.0,
            max_qty=100000000.0,
            min_notional=5.0,
            current_price=0.32,
            mark_price=0.32,
            index_price=0.32,
        ),
        Symbol(
            symbol="LINKUSDT",
            base_asset="LINK",
            quote_asset="USDT",
            tick_size=0.001,
            step_size=0.01,
            min_qty=0.01,
            max_qty=100000.0,
            min_notional=5.0,
            current_price=14.50,
            mark_price=14.50,
            index_price=14.50,
        ),
        Symbol(
            symbol="TRXUSDT",
            base_asset="TRX",
            quote_asset="USDT",
            tick_size=0.00001,
            step_size=0.1,
            min_qty=1.0,
            max_qty=100000000.0,
            min_notional=5.0,
            current_price=0.26,
            mark_price=0.26,
            index_price=0.26,
        ),
        Symbol(
            symbol="LTCUSDT",
            base_asset="LTC",
            quote_asset="USDT",
            tick_size=0.01,
            step_size=0.001,
            min_qty=0.001,
            max_qty=10000.0,
            min_notional=5.0,
            current_price=105.0,
            mark_price=105.0,
            index_price=105.0,
        ),
        Symbol(
            symbol="AVAXUSDT",
            base_asset="AVAX",
            quote_asset="USDT",
            tick_size=0.001,
            step_size=0.01,
            min_qty=0.01,
            max_qty=100000.0,
            min_notional=5.0,
            current_price=38.0,
            mark_price=38.0,
            index_price=38.0,
        ),
    ]

    for symbol in default_symbols:
        db.add(symbol)
    db.commit()
    print(f"Seeded {len(default_symbols)} default symbols")


def _seed_default_api_key(db: Session):
    """Seed a default API key if none exist."""
    existing = db.query(APIKey).first()
    if existing:
        return

    # Create default API key (matches what we'll use in engine config)
    default_key = APIKey(
        api_key="mock_api_key_12345",
        api_secret="mock_api_secret_67890",
        label="Default Test Key",
        is_active=True,
        permissions="SPOT,FUTURES",
    )
    db.add(default_key)
    db.flush()

    # Add default USDT balance
    default_balance = Balance(
        api_key_id=default_key.id,
        asset="USDT",
        free=100000.0,  # 100k USDT for testing
        locked=0.0,
        total=100000.0,
    )
    db.add(default_balance)
    db.commit()
    print(f"Seeded default API key: {default_key.api_key}")
