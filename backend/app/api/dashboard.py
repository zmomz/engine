from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session
from app.api.dependencies.users import get_current_active_user
from app.models.user import User
from app.repositories.position_group import PositionGroupRepository
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.core.security import EncryptionService

router = APIRouter()

@router.get("/tvl")
async def get_tvl(
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Decrypt keys
        if not current_user.encrypted_api_keys:
            return {"tvl": 0.0}
            
        # Handle new dictionary structure for multiple exchanges
        encrypted_data = current_user.encrypted_api_keys
        if isinstance(encrypted_data, dict) and current_user.exchange in encrypted_data:
             # Check if it's the new format {"exchange": {"encrypted_data": "..."}}
             # or legacy format {"encrypted_data": "..."} (though we just migrated, safety first)
             if "encrypted_data" in encrypted_data: 
                 # Legacy format (single key) - treat as valid if it matches expectation, 
                 # but based on our migration, it should be nested. 
                 # actually, if we just migrated, we should expect nesting.
                 # Let's assume the new format: keys are exchange names.
                 pass
             else:
                 # It is a dict of exchanges, get the specific one
                 encrypted_data = encrypted_data.get(current_user.exchange)

        if not encrypted_data:
             return {"tvl": 0.0}

        encryption_service = EncryptionService()
        api_key, secret_key = encryption_service.decrypt_keys(encrypted_data)
        
        # Connect to exchange
        connector = get_exchange_connector(
            exchange_type=current_user.exchange,
            api_key=api_key,
            secret_key=secret_key
        )
        
        # Fetch balance
        try:
            balances = await connector.fetch_balance()
            
            # Connectors usually return the 'total' dict directly (e.g. {'USDT': 100.0})
            # But standard CCXT structure is {'total': {'USDT': 100.0}, ...}
            # We handle both cases for robustness.
            if "total" in balances and isinstance(balances["total"], dict):
                total_balances = balances["total"]
            else:
                total_balances = balances
                
            tvl = total_balances.get("USDT", 0.0)
            
            return {"tvl": float(tvl)}
        finally:
             # Cleanup connection if possible
            if hasattr(connector, 'exchange') and hasattr(connector.exchange, 'close'):
                 await connector.exchange.close()

    except Exception as e:
        # In a real app, we should log this error
        print(f"Error fetching TVL: {e}")
        return {"tvl": 0.0}

@router.get("/pnl")
async def get_pnl(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    repo = PositionGroupRepository(db)
    total_pnl = await repo.get_total_pnl_for_user(current_user.id)
    return {"pnl": float(total_pnl)}

@router.get("/active-groups-count")
async def get_active_groups_count(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    repo = PositionGroupRepository(db)
    groups = await repo.get_active_position_groups_for_user(current_user.id)
    return {"count": len(groups)}
