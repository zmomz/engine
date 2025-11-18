import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models import (
    DCAOrder,
    PositionGroup,
    Pyramid,
    QueuedSignal,
    RiskAction,
    User,
)


@pytest.mark.asyncio
async def test_create_position_group(db_session: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        username="testuser",
        email="test@example.com",
        hashed_password="hashedpassword",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    pg = PositionGroup(
        user_id=user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        total_dca_legs=5,
        base_entry_price=Decimal("50000.00"),
        weighted_avg_entry=Decimal("50000.00"),
        tp_mode="per_leg",
    )
    db_session.add(pg)
    await db_session.commit()
    await db_session.refresh(pg)

    assert pg.id is not None
    assert pg.user_id == user.id
    assert pg.status == "waiting"


@pytest.mark.asyncio
async def test_create_pyramid(db_session: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        username="testuser2",
        email="test2@example.com",
        hashed_password="hashedpassword",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    pg = PositionGroup(
        user_id=user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        total_dca_legs=5,
        base_entry_price=Decimal("50000.00"),
        weighted_avg_entry=Decimal("50000.00"),
        tp_mode="per_leg",
    )
    db_session.add(pg)
    await db_session.commit()
    await db_session.refresh(pg)
    pg_id = pg.id

    pyramid = Pyramid(
        group_id=pg_id,
        pyramid_index=0,
        entry_price=Decimal("51000.00"),
        entry_timestamp=datetime.utcnow(),
        dca_config=[{"gap_percent": -1, "weight_percent": 20, "tp_percent": 1}],
        status="pending",
    )
    db_session.add(pyramid)
    await db_session.commit()
    await db_session.refresh(pyramid)

    assert pyramid.id is not None
    assert pyramid.group_id == pg_id


@pytest.mark.asyncio
async def test_create_dca_order(db_session: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        username="testuser3",
        email="test3@example.com",
        hashed_password="hashedpassword",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    pg = PositionGroup(
        user_id=user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        total_dca_legs=5,
        base_entry_price=Decimal("50000.00"),
        weighted_avg_entry=Decimal("50000.00"),
        tp_mode="per_leg",
    )
    db_session.add(pg)
    await db_session.commit()
    await db_session.refresh(pg)

    pg_id = pg.id
    pyramid = Pyramid(
        group_id=pg_id,
        pyramid_index=0,
        entry_price=Decimal("51000.00"),
        entry_timestamp=datetime.utcnow(),
        dca_config=[{"gap_percent": -1, "weight_percent": 20, "tp_percent": 1}],
        status="pending",
    )
    db_session.add(pyramid)
    await db_session.commit()
    await db_session.refresh(pyramid)

    pyramid_id = pyramid.id
    dca_order = DCAOrder(
        group_id=pg_id,
        pyramid_id=pyramid_id,
        leg_index=0,
        symbol="BTCUSDT",
        side="buy",
        price=Decimal("49500.00"),
        quantity=Decimal("0.01"),
        gap_percent=Decimal("-1.0"),
        weight_percent=Decimal("20"),
        tp_percent=Decimal("1.0"),
        tp_price=Decimal("50000.00"),
        status="pending",
    )
    db_session.add(dca_order)
    await db_session.commit()
    await db_session.refresh(dca_order)

    assert dca_order.id is not None
    assert dca_order.group_id == pg_id
    assert dca_order.pyramid_id == pyramid_id
