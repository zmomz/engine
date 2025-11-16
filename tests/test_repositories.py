import uuid
from decimal import Decimal
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models import PositionGroup, Pyramid, DCAOrder, QueuedSignal, RiskAction
from app.repositories import (
    PositionGroupRepository,
    PyramidRepository,
    DCAOrderRepository,
    QueuedSignalRepository,
    RiskActionRepository,
)


@pytest.mark.asyncio
async def test_position_group_repository(db_session: AsyncSession):
    repo = PositionGroupRepository(db_session)
    user_id = uuid.uuid4()
    pg = PositionGroup(
        user_id=user_id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        total_dca_legs=5,
        base_entry_price=Decimal("50000.00"),
        weighted_avg_entry=Decimal("50000.00"),
        tp_mode="per_leg",
    )
    created_pg = await repo.create(pg)

    assert created_pg.id is not None
    assert created_pg.user_id == user_id

    fetched_pg = await repo.get(created_pg.id)
    assert fetched_pg == created_pg

    await repo.delete(created_pg.id)
    deleted_pg = await repo.get(created_pg.id)
    assert deleted_pg is None


@pytest.mark.asyncio
async def test_pyramid_repository(db_session: AsyncSession):
    pg_repo = PositionGroupRepository(db_session)
    user_id = uuid.uuid4()
    pg = PositionGroup(
        user_id=user_id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        total_dca_legs=5,
        base_entry_price=Decimal("50000.00"),
        weighted_avg_entry=Decimal("50000.00"),
        tp_mode="per_leg",
    )
    created_pg = await pg_repo.create(pg)

    pyramid_repo = PyramidRepository(db_session)
    pyramid = Pyramid(
        group_id=created_pg.id,
        pyramid_index=0,
        entry_price=Decimal("51000.00"),
        entry_timestamp=datetime.utcnow(),
        dca_config=[{"gap_percent": -1, "weight_percent": 20, "tp_percent": 1}],
        status="pending",
    )
    created_pyramid = await pyramid_repo.create(pyramid)

    assert created_pyramid.id is not None
    assert created_pyramid.group_id == created_pg.id

    fetched_pyramid = await pyramid_repo.get(created_pyramid.id)
    assert fetched_pyramid == created_pyramid

    await pyramid_repo.delete(created_pyramid.id)
    deleted_pyramid = await pyramid_repo.get(created_pyramid.id)
    assert deleted_pyramid is None


@pytest.mark.asyncio
async def test_dca_order_repository(db_session: AsyncSession):
    pg_repo = PositionGroupRepository(db_session)
    user_id = uuid.uuid4()
    pg = PositionGroup(
        user_id=user_id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        total_dca_legs=5,
        base_entry_price=Decimal("50000.00"),
        weighted_avg_entry=Decimal("50000.00"),
        tp_mode="per_leg",
    )
    created_pg = await pg_repo.create(pg)

    pyramid_repo = PyramidRepository(db_session)
    pyramid = Pyramid(
        group_id=created_pg.id,
        pyramid_index=0,
        entry_price=Decimal("51000.00"),
        entry_timestamp=datetime.utcnow(),
        dca_config=[{"gap_percent": -1, "weight_percent": 20, "tp_percent": 1}],
        status="pending",
    )
    created_pyramid = await pyramid_repo.create(pyramid)

    dca_repo = DCAOrderRepository(db_session)
    dca_order = DCAOrder(
        group_id=created_pg.id,
        pyramid_id=created_pyramid.id,
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
    created_dca = await dca_repo.create(dca_order)

    assert created_dca.id is not None
    assert created_dca.group_id == created_pg.id
    assert created_dca.pyramid_id == created_pyramid.id

    fetched_dca = await dca_repo.get(created_dca.id)
    assert fetched_dca == created_dca

    await dca_repo.delete(created_dca.id)
    deleted_dca = await dca_repo.get(created_dca.id)
    assert deleted_dca is None


@pytest.mark.asyncio
async def test_queued_signal_repository(db_session: AsyncSession):
    repo = QueuedSignalRepository(db_session)
    user_id = uuid.uuid4()
    queued_signal = QueuedSignal(
        user_id=user_id,
        exchange="binance",
        symbol="ETHUSDT",
        timeframe=60,
        side="short",
        entry_price=Decimal("3000.00"),
        signal_payload={},
        status="queued",
    )
    created_signal = await repo.create(queued_signal)

    assert created_signal.id is not None
    assert created_signal.user_id == user_id

    fetched_signal = await repo.get(created_signal.id)
    assert fetched_signal == created_signal

    await repo.delete(created_signal.id)
    deleted_signal = await repo.get(created_signal.id)
    assert deleted_signal is None


@pytest.mark.asyncio
async def test_risk_action_repository(db_session: AsyncSession):
    pg_repo = PositionGroupRepository(db_session)
    user_id = uuid.uuid4()
    pg = PositionGroup(
        user_id=user_id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        total_dca_legs=5,
        base_entry_price=Decimal("50000.00"),
        weighted_avg_entry=Decimal("50000.00"),
        tp_mode="per_leg",
    )
    created_pg = await pg_repo.create(pg)

    risk_repo = RiskActionRepository(db_session)
    risk_action = RiskAction(
        group_id=created_pg.id,
        action_type="offset_loss",
        loser_group_id=created_pg.id,
        loser_pnl_usd=Decimal("-100.00"),
    )
    created_action = await risk_repo.create(risk_action)

    assert created_action.id is not None
    assert created_action.group_id == created_pg.id

    fetched_action = await risk_repo.get(created_action.id)
    assert fetched_action == created_action

    await risk_repo.delete(created_action.id)
    deleted_action = await risk_repo.get(created_action.id)
    assert deleted_action is None
