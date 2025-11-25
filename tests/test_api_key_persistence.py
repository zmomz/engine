
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.repositories.user import UserRepository
from app.api.settings import update_settings
from app.schemas.user import UserUpdate

@pytest.mark.asyncio
async def test_api_key_persistence(db_session: AsyncSession):
    # 1. Create a test user
    repo = UserRepository(db_session)
    user_in = User(
        username="test_persistence",
        email="test_p@example.com",
        hashed_password="hashed_secret",
        exchange="binance"
    )
    db_session.add(user_in)
    await db_session.commit()
    await db_session.refresh(user_in)
    
    assert user_in.encrypted_api_keys is None

    # 2. Simulate the update logic from the API endpoint
    # We want to add keys for "binance"
    update_payload = UserUpdate(
        exchange="binance", # Active exchange
        key_target_exchange="binance",
        api_key="test_api_key",
        secret_key="test_secret_key"
    )
    
    # We need to mimic what the endpoint does:
    # It calls update_settings, which depends on 'current_user' and 'db'
    
    # Let's manually invoke the logic from the endpoint to isolate it
    # logic copy-paste from backend/app/api/settings.py
    
    from app.core.security import EncryptionService
    encryption_service = EncryptionService()
    
    if update_payload.api_key and update_payload.secret_key:
        new_encrypted_keys = encryption_service.encrypt_keys(update_payload.api_key, update_payload.secret_key)
        
        current_keys = dict(user_in.encrypted_api_keys or {})
        target_exchange = update_payload.key_target_exchange or update_payload.exchange or user_in.exchange
        current_keys[target_exchange] = new_encrypted_keys
        
        # This is where we simulate the update_data preparation
        # In the actual API, it uses user_update.dict(exclude_unset=True)
        # But here we just manually set the field
        user_in.encrypted_api_keys = current_keys
        
    # Now we call repo.update
    updated_user = await repo.update(user_in)
    await db_session.commit()
    
    # 3. Verify immediate return
    assert updated_user.encrypted_api_keys is not None
    assert "binance" in updated_user.encrypted_api_keys
    
    # 4. Verify persistence by fetching a fresh instance
    # Capture ID before expiring
    user_id = user_in.id
    
    # clear session to ensure we fetch from DB
    db_session.expire_all() 
    
    fetched_user = await repo.get_by_id(user_id)
    assert fetched_user.encrypted_api_keys is not None
    assert "binance" in fetched_user.encrypted_api_keys
    
    print("First update successful.")
    
    # 5. Add a SECOND exchange key (e.g. 'bybit')
    update_payload_2 = UserUpdate(
        key_target_exchange="bybit",
        api_key="bybit_key",
        secret_key="bybit_secret"
    )
    
    if update_payload_2.api_key and update_payload_2.secret_key:
        new_encrypted_keys_2 = encryption_service.encrypt_keys(update_payload_2.api_key, update_payload_2.secret_key)
        
        # CRITICAL: We must fetch the latest state from the object
        current_keys = dict(fetched_user.encrypted_api_keys or {})
        target_exchange = update_payload_2.key_target_exchange
        current_keys[target_exchange] = new_encrypted_keys_2
        
        fetched_user.encrypted_api_keys = current_keys
        
    updated_user_2 = await repo.update(fetched_user)
    await db_session.commit()
    
    # 6. Verify second persistence
    db_session.expire_all()
    final_user = await repo.get_by_id(user_id)
    
    assert "binance" in final_user.encrypted_api_keys
    assert "bybit" in final_user.encrypted_api_keys
    print("Second update successful.")
