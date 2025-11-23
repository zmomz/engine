import pytest
from httpx import AsyncClient
import uuid
from decimal import Decimal
from datetime import datetime
from sqlalchemy import text
import json
from app.main import app
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.schemas.position_group import TPMode
from app.models.queued_signal import QueuedSignal, QueueStatus
from app.db.database import get_db_session, AsyncSession
from app.repositories.position_group import PositionGroupRepository
from app.repositories.queued_signal import QueuedSignalRepository
from app.core.security import create_access_token
from app.models.user import User

# --- Fixtures for repositories ---

@pytest.fixture
async def position_group_repo(db_session: AsyncSession):
    return PositionGroupRepository(db_session)

@pytest.fixture
async def queued_signal_repo(db_session: AsyncSession):
    return QueuedSignalRepository(db_session)

# --- Helper for auth headers ---
def get_auth_headers(user: User):
    token = create_access_token(data={"sub": user.username})
    return {"Authorization": f"Bearer {token}"}

# --- Tests for /positions endpoints ---

@pytest.mark.asyncio
async def test_get_all_positions_integration(position_group_repo: PositionGroupRepository, db_session: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        username="testuser_positions",
        email="test_positions@example.com",
        hashed_password="hashedpassword",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create some position groups directly in the database
    pg1 = PositionGroup(
        id=uuid.uuid4(),
        user_id=user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        pyramid_count=1,
        max_pyramids=5,
        replacement_count=0,
        total_dca_legs=5,
        filled_dca_legs=1,
        base_entry_price=Decimal("50000.00"),
        weighted_avg_entry=Decimal("50000.00"),
        total_invested_usd=Decimal("1000"),
        total_filled_quantity=Decimal("0.02"),
        unrealized_pnl_usd=Decimal("0"),
        unrealized_pnl_percent=Decimal("0"),
        realized_pnl_usd=Decimal("0"),
        tp_mode=TPMode.PER_LEG,
        risk_eligible=False,
        risk_blocked=False,
        risk_skip_once=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    pg2 = PositionGroup(
        id=uuid.uuid4(),
        user_id=user.id,
        exchange="bybit",
        symbol="ETHUSDT",
        timeframe=60,
        side="short",
        status=PositionGroupStatus.ACTIVE,
        pyramid_count=1,
        max_pyramids=5,
        replacement_count=0,
        total_dca_legs=3,
        filled_dca_legs=1,
        base_entry_price=Decimal("3000.00"),
        weighted_avg_entry=Decimal("3000.00"),
        total_invested_usd=Decimal("500"),
        total_filled_quantity=Decimal("0.1"),
        unrealized_pnl_usd=Decimal("0"),
        unrealized_pnl_percent=Decimal("0"),
        realized_pnl_usd=Decimal("0"),
        tp_mode=TPMode.AGGREGATE,
        risk_eligible=False,
        risk_blocked=False,
        risk_skip_once=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await position_group_repo.create(pg1)
    await position_group_repo.create(pg2)
    await db_session.commit()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/positions/{user.id}", headers=get_auth_headers(user))

    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2
    assert response_data[0]["symbol"] == "BTCUSDT"
    assert response_data[1]["symbol"] == "ETHUSDT"

@pytest.mark.asyncio
async def test_get_position_group_integration(position_group_repo: PositionGroupRepository, db_session: AsyncSession):
    user_id = uuid.uuid4()
    group_id = uuid.uuid4()
    
    # Create user directly in database
    user = User(
        id=user_id, 
        username="testuser_group", 
        email="test_group@example.com", 
        hashed_password="hashedpassword",
        exchange="binance",
        webhook_secret="secret",
        risk_config={},
        dca_grid_config=[]
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create position group using repository
    pg = PositionGroup(
        id=group_id,
        user_id=user_id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        pyramid_count=1,
        max_pyramids=5,
        replacement_count=0,
        total_dca_legs=5,
        filled_dca_legs=1,
        base_entry_price=Decimal("50000.00"),
        weighted_avg_entry=Decimal("50000.00"),
        total_invested_usd=Decimal("1000"),
        total_filled_quantity=Decimal("0.02"),
        unrealized_pnl_usd=Decimal("0"),
        unrealized_pnl_percent=Decimal("0"),
        realized_pnl_usd=Decimal("0"),
        tp_mode=TPMode.PER_LEG,
        risk_eligible=False,
        risk_blocked=False,
        risk_skip_once=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await position_group_repo.create(pg)
    await db_session.commit()

    # Test the endpoint
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/positions/{user_id}/{group_id}", headers=get_auth_headers(user))

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(group_id)
    assert response_data["symbol"] == "BTCUSDT"

@pytest.mark.asyncio
async def test_get_position_group_not_found_integration(db_session: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        username="testuser_notfound",
        email="test_notfound@example.com",
        hashed_password="hashedpassword",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    user_id = user.id
    group_id = uuid.uuid4()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/positions/{user_id}/{group_id}", headers=get_auth_headers(user))

    assert response.status_code == 404
    assert response.json() == {"detail": "Position group not found."} 

# --- Tests for /queue endpoints ---

@pytest.mark.asyncio
async def test_get_all_queued_signals_integration(queued_signal_repo: QueuedSignalRepository, db_session: AsyncSession, test_user: User):
    user_id = test_user.id
    # Create some queued signals directly in the database
    qs1 = QueuedSignal(
        id=uuid.uuid4(),
        user_id=user_id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        entry_price=Decimal("50000.00"),
        signal_payload={"key": "value1"},
        queued_at=datetime.utcnow(),
        replacement_count=0,
        priority_score=Decimal("0.0"),
        is_pyramid_continuation=False,
        status=QueueStatus.QUEUED,
    )
    qs2 = QueuedSignal(
        id=uuid.uuid4(),
        user_id=user_id,
        exchange="bybit",
        symbol="ETHUSDT",
        timeframe=60,
        side="short",
        entry_price=Decimal("3000.00"),
        signal_payload={"key": "value2"},
        queued_at=datetime.utcnow(),
        replacement_count=0,
        priority_score=Decimal("0.0"),
        is_pyramid_continuation=False,
        status=QueueStatus.QUEUED,
    )
    await queued_signal_repo.create(qs1)
    await queued_signal_repo.create(qs2)
    await db_session.commit()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Need to auth as test_user
        response = await ac.get(f"/api/v1/queue/", headers=get_auth_headers(test_user))

    assert response.status_code == 200
    response_data = response.json()
    # Filtering by user might be active? If endpoints return all queue, it's fine.
    # Assuming endpoint returns queue for current user or all if admin.
    # Let's assume user isolation.
    assert len(response_data) >= 2 # might have others from other tests? No, DB isolation per test usually.
    symbols = [x["symbol"] for x in response_data]
    assert "BTCUSDT" in symbols
    assert "ETHUSDT" in symbols

@pytest.mark.asyncio
async def test_remove_queued_signal_integration(queued_signal_repo: QueuedSignalRepository, db_session: AsyncSession, test_user: User):
    user_id = test_user.id
    signal_id = uuid.uuid4()
    qs = QueuedSignal(
        id=signal_id,
        user_id=user_id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        entry_price=Decimal("50000.00"),
        signal_payload={"key": "value1"},
        queued_at=datetime.utcnow(),
        replacement_count=0,
        priority_score=Decimal("0.0"),
        is_pyramid_continuation=False,
        status=QueueStatus.QUEUED,
    )
    await queued_signal_repo.create(qs)
    await db_session.commit()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.delete(f"/api/v1/queue/{signal_id}", headers=get_auth_headers(test_user))

    assert response.status_code == 200
    assert response.json() == {"message": "Queued signal removed successfully."}

    # Verify it's actually removed from the database
    # We need to use a NEW session or refresh to see changes if we are checking via repo
    # But repo uses db_session passed in.
    # db_session should reflect changes made by API if API used same DB.
    # The API uses get_db_session which is overridden to return db_session.
    # So they share the session transaction.
    # Wait, if API commits, and test session is nested...
    # It should be fine.
    
    # Re-fetch
    async with db_session.begin(): # New transaction context?
         removed_signal = await queued_signal_repo.get(signal_id)
    
    # Or just use the repo as is, assuming session is still valid
    removed_signal = await queued_signal_repo.get(signal_id)
    assert removed_signal is None

@pytest.mark.asyncio
async def test_remove_queued_signal_not_found_integration(db_session: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        username="testuser_remove_queue_notfound",
        email="test_remove_queue_notfound@example.com",
        hashed_password="hashedpassword",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    signal_id = uuid.uuid4()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.delete(f"/api/v1/queue/{signal_id}", headers=get_auth_headers(user))

    assert response.status_code == 404
    assert response.json() == {"detail": "Queued signal not found."}

# --- Tests for /risk endpoints ---

@pytest.mark.asyncio
async def test_block_risk_for_group_integration(position_group_repo: PositionGroupRepository, db_session: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        username="testuser_block_risk",
        email="test_block_risk@example.com",
        hashed_password="hashedpassword",
        exchange="mock",
        webhook_secret="secret",
        encrypted_api_keys={"data": "dummy"}
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    user_id = user.id
    group_id = uuid.uuid4()
    pg = PositionGroup(
        id=group_id,
        user_id=user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        pyramid_count=1,
        max_pyramids=5,
        replacement_count=0,
        total_dca_legs=5,
        filled_dca_legs=1,
        base_entry_price=Decimal("50000.00"),
        weighted_avg_entry=Decimal("50000.00"),
        total_invested_usd=Decimal("1000"),
        total_filled_quantity=Decimal("0.02"),
        unrealized_pnl_usd=Decimal("0"),
        unrealized_pnl_percent=Decimal("0"),
        realized_pnl_usd=Decimal("0"),
        tp_mode=TPMode.PER_LEG,
        risk_eligible=False,
        risk_blocked=False,
        risk_skip_once=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await position_group_repo.create(pg)
    await db_session.commit()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(f"/api/v1/risk/{group_id}/block", headers=get_auth_headers(user))

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(group_id)
    assert response_data["risk_blocked"] is True

    # Verify in database
    updated_pg = await position_group_repo.get(group_id)
    assert updated_pg.risk_blocked is True

@pytest.mark.asyncio
async def test_unblock_risk_for_group_integration(position_group_repo: PositionGroupRepository, db_session: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        username="testuser_unblock_risk",
        email="test_unblock_risk@example.com",
        hashed_password="hashedpassword",
        exchange="mock",
        webhook_secret="secret",
        encrypted_api_keys={"data": "dummy"}
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    user_id = user.id
    group_id = uuid.uuid4()
    pg = PositionGroup(
        id=group_id,
        user_id=user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        pyramid_count=1,
        max_pyramids=5,
        replacement_count=0,
        total_dca_legs=5,
        filled_dca_legs=1,
        base_entry_price=Decimal("50000.00"),
        weighted_avg_entry=Decimal("50000.00"),
        total_invested_usd=Decimal("1000"),
        total_filled_quantity=Decimal("0.02"),
        unrealized_pnl_usd=Decimal("0"),
        unrealized_pnl_percent=Decimal("0"),
        realized_pnl_usd=Decimal("0"),
        tp_mode=TPMode.PER_LEG,
        risk_eligible=False,
        risk_blocked=True,
        risk_skip_once=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await position_group_repo.create(pg)
    await db_session.commit()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(f"/api/v1/risk/{group_id}/unblock", headers=get_auth_headers(user))

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(group_id)
    assert response_data["risk_blocked"] is False

    # Verify in database
    updated_pg = await position_group_repo.get(group_id)
    assert updated_pg.risk_blocked is False

@pytest.mark.asyncio
async def test_skip_next_risk_evaluation_integration(position_group_repo: PositionGroupRepository, db_session: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        username="testuser_skip_risk",
        email="test_skip_risk@example.com",
        hashed_password="hashedpassword",
        exchange="mock",
        webhook_secret="secret",
        encrypted_api_keys={"data": "dummy"}
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    user_id = user.id
    group_id = uuid.uuid4()
    pg = PositionGroup(
        id=group_id,
        user_id=user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        pyramid_count=1,
        max_pyramids=5,
        replacement_count=0,
        total_dca_legs=5,
        filled_dca_legs=1,
        base_entry_price=Decimal("50000.00"),
        weighted_avg_entry=Decimal("50000.00"),
        total_invested_usd=Decimal("1000"),
        total_filled_quantity=Decimal("0.02"),
        unrealized_pnl_usd=Decimal("0"),
        unrealized_pnl_percent=Decimal("0"),
        realized_pnl_usd=Decimal("0"),
        tp_mode=TPMode.PER_LEG,
        risk_eligible=False,
        risk_blocked=False,
        risk_skip_once=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await position_group_repo.create(pg)
    await db_session.commit()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(f"/api/v1/risk/{group_id}/skip", headers=get_auth_headers(user))

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(group_id)
    assert response_data["risk_skip_once"] is True

    # Verify in database
    updated_pg = await position_group_repo.get(group_id)
    assert updated_pg.risk_skip_once is True