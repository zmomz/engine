"""
SQLite models for the mock exchange.
Stores orders, positions, balances, prices, and API keys.
"""
from sqlalchemy import Column, String, Float, DateTime, Enum, ForeignKey, Boolean, Integer, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import enum
import uuid

Base = declarative_base()


class OrderStatus(str, enum.Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, enum.Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"


class PositionSide(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


class APIKey(Base):
    """API keys for authentication - mimics Binance API keys"""
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key = Column(String(64), unique=True, nullable=False, index=True)
    api_secret = Column(String(64), nullable=False)
    label = Column(String(100), default="Default")
    is_active = Column(Boolean, default=True)
    permissions = Column(String(200), default="SPOT,FUTURES")  # Comma-separated
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    balances = relationship("Balance", back_populates="api_key_ref", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="api_key_ref", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="api_key_ref", cascade="all, delete-orphan")


class Symbol(Base):
    """Trading pairs with precision rules - mimics Binance exchangeInfo"""
    __tablename__ = "symbols"

    symbol = Column(String(20), primary_key=True)  # e.g., "BTCUSDT"
    base_asset = Column(String(10), nullable=False)  # e.g., "BTC"
    quote_asset = Column(String(10), nullable=False)  # e.g., "USDT"
    status = Column(String(20), default="TRADING")

    # Precision rules (Binance-style)
    tick_size = Column(Float, default=0.01)  # Price precision
    step_size = Column(Float, default=0.001)  # Quantity precision
    min_qty = Column(Float, default=0.001)
    max_qty = Column(Float, default=9000.0)
    min_notional = Column(Float, default=10.0)  # Minimum order value

    # Contract info (for futures)
    contract_type = Column(String(20), default="PERPETUAL")
    margin_asset = Column(String(10), default="USDT")

    # Current price (updated manually or via admin)
    current_price = Column(Float, default=0.0)
    mark_price = Column(Float, default=0.0)
    index_price = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow)


class Balance(Base):
    """Account balances per API key"""
    __tablename__ = "balances"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False)
    asset = Column(String(10), nullable=False)  # e.g., "USDT", "BTC"
    free = Column(Float, default=0.0)  # Available balance
    locked = Column(Float, default=0.0)  # In open orders
    total = Column(Float, default=0.0)  # free + locked

    api_key_ref = relationship("APIKey", back_populates="balances")


class Order(Base):
    """Orders - mimics Binance order structure"""
    __tablename__ = "orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Binance-style numeric ID - use timestamp-based ID generation
    order_id = Column(Integer, unique=True, index=True)
    client_order_id = Column(String(36), default=lambda: str(uuid.uuid4()))

    @staticmethod
    def generate_order_id():
        """Generate a unique Binance-style order ID based on timestamp."""
        import time
        import random
        # Use timestamp in milliseconds + random component for uniqueness
        return int(time.time() * 1000) + random.randint(0, 999)
    api_key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False)

    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # BUY/SELL
    type = Column(String(20), nullable=False)  # LIMIT/MARKET/etc
    position_side = Column(String(10), default="BOTH")  # LONG/SHORT/BOTH

    price = Column(Float, default=0.0)  # Requested price
    quantity = Column(Float, nullable=False)  # Requested quantity
    executed_qty = Column(Float, default=0.0)  # Filled quantity
    avg_price = Column(Float, default=0.0)  # Average fill price
    cumulative_fee = Column(Float, default=0.0)  # Accumulated trading fees
    fee_currency = Column(String(10), default="USDT")  # Fee currency

    status = Column(String(20), default="NEW")
    time_in_force = Column(String(10), default="GTC")  # GTC, IOC, FOK
    reduce_only = Column(Boolean, default=False)
    close_position = Column(Boolean, default=False)

    # Stop/TP prices
    stop_price = Column(Float, default=0.0)
    activation_price = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    api_key_ref = relationship("APIKey", back_populates="orders")


class Position(Base):
    """Open positions - mimics Binance futures positions"""
    __tablename__ = "positions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False)

    symbol = Column(String(20), nullable=False)
    position_side = Column(String(10), default="BOTH")  # LONG/SHORT/BOTH

    entry_price = Column(Float, default=0.0)
    quantity = Column(Float, default=0.0)  # Position size (negative for short)
    leverage = Column(Integer, default=1)
    margin_type = Column(String(10), default="cross")  # cross/isolated

    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    liquidation_price = Column(Float, default=0.0)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    api_key_ref = relationship("APIKey", back_populates="positions")


class Trade(Base):
    """Trade history - records of filled orders"""
    __tablename__ = "trades"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trade_id = Column(Integer, autoincrement=True, unique=True)
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False)

    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    quote_qty = Column(Float, nullable=False)  # price * quantity
    commission = Column(Float, default=0.0)
    commission_asset = Column(String(10), default="USDT")
    realized_pnl = Column(Float, default=0.0)

    is_maker = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PriceHistory(Base):
    """Price history for charting"""
    __tablename__ = "price_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol = Column(String(20), nullable=False, index=True)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class WebhookLog(Base):
    """Log of webhooks sent to the engine (for debugging)"""
    __tablename__ = "webhook_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payload = Column(Text, nullable=False)
    response_status = Column(Integer)
    response_body = Column(Text)
    target_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)


# Database setup
def get_engine(db_path: str = "mock_exchange.db"):
    return create_engine(f"sqlite:///{db_path}", echo=False)


def create_tables(engine):
    Base.metadata.create_all(engine)


def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()
