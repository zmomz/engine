from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session
from app.api.dependencies.users import get_current_active_user
from app.models.user import User
from app.repositories.position_group import PositionGroupRepository
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.core.security import EncryptionService
from app.schemas.dashboard import DashboardOutput

router = APIRouter()

@router.get("/account-summary", response_model=DashboardOutput)
async def get_account_summary(
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
            
            total_balances = {}
            if "total" in balances and isinstance(balances["total"], dict):
                total_balances = balances["total"]
            else:
                total_balances = balances
            
            free_balances = {}
            if "free" in balances and isinstance(balances["free"], dict):
                free_balances = balances["free"]
            
            tvl = 0.0
            # Use 'free' balance for Free USDT display, fallback to total or 0
            free_usdt = free_balances.get("USDT", total_balances.get("USDT", 0.0))

            for asset, amount in total_balances.items():
                if amount > 0:
                    if asset == "USDT":
                        tvl += amount
                    else:
                        # Convert other assets to USDT value
                        try:
                            # Assuming get_current_price can handle conversion to USDT
                            price_in_usdt = await connector.get_current_price(f"{asset}/USDT")
                            tvl += amount * price_in_usdt
                        except Exception as e:
                            print(f"Could not fetch price for {asset}/USDT: {e}")
                            # If price fetching fails, we might just skip this asset
                            # or log a warning. For now, we skip it for TVL calculation.
            
            return {"tvl": float(tvl), "free_usdt": float(free_usdt)}
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
    
    # 1. Get Realized PnL from DB (Historical)
    realized_pnl = await repo.get_total_realized_pnl_only(current_user.id)
    
    # 2. Calculate Unrealized PnL for active positions
    unrealized_pnl = 0.0
    active_groups = await repo.get_active_position_groups_for_user(current_user.id)
    
    if active_groups and current_user.encrypted_api_keys:
        try:
            encrypted_data = current_user.encrypted_api_keys
            target_data = None
            
            # Determine which key data to use
            if isinstance(encrypted_data, dict):
                 if current_user.exchange and current_user.exchange in encrypted_data:
                     target_data = encrypted_data[current_user.exchange]
                 elif "encrypted_data" in encrypted_data:
                     # Legacy format support
                     target_data = encrypted_data
            
            if target_data:
                encryption_service = EncryptionService()
                api_key, secret_key = encryption_service.decrypt_keys(target_data)
                
                connector = get_exchange_connector(
                    exchange_type=current_user.exchange or "binance",
                    api_key=api_key,
                    secret_key=secret_key
                )
                
                try:
                    for group in active_groups:
                        try:
                            current_price = await connector.get_current_price(group.symbol)
                            qty = float(group.total_filled_quantity)
                            avg_entry = float(group.weighted_avg_entry)
                            
                            if qty > 0:
                                if group.side == "long":
                                    pnl = (current_price - avg_entry) * qty
                                else:
                                    pnl = (avg_entry - current_price) * qty
                                unrealized_pnl += pnl
                        except Exception as e:
                            print(f"Error fetching price for {group.symbol}: {e}")
                finally:
                    if hasattr(connector, 'exchange') and hasattr(connector.exchange, 'close'):
                         await connector.exchange.close()
        except Exception as e:
            print(f"Error calculating unrealized PnL context: {e}")

    total_pnl = float(realized_pnl) + unrealized_pnl
    return {"pnl": total_pnl}

@router.get("/active-groups-count")
async def get_active_groups_count(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    repo = PositionGroupRepository(db)
    groups = await repo.get_active_position_groups_for_user(current_user.id)
    return {"count": len(groups)}
