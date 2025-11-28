from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session
from app.api.dependencies.users import get_current_active_user
from app.models.user import User
from app.repositories.position_group import PositionGroupRepository
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.core.security import EncryptionService
from app.schemas.dashboard import DashboardOutput
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/account-summary", response_model=DashboardOutput)
async def get_account_summary(
    current_user: User = Depends(get_current_active_user)
):
    try:
        if not current_user.encrypted_api_keys:
            return {"tvl": 0.0, "free_usdt": 0.0}
            
        total_tvl = 0.0
        total_free_usdt = 0.0
        
        api_keys_to_process = {}
        
        if current_user.encrypted_api_keys:
            # Check if it's the legacy single-key format: {"encrypted_data": "..."}
            if isinstance(current_user.encrypted_api_keys, dict) and "encrypted_data" in current_user.encrypted_api_keys:
                exchange = current_user.exchange or "binance"
                api_keys_to_process[exchange] = current_user.encrypted_api_keys
            elif isinstance(current_user.encrypted_api_keys, dict):
                # Assume it's the new multi-key format: {"binance": {...}, "bybit": {...}}
                api_keys_to_process = current_user.encrypted_api_keys
            # else: current_user.encrypted_api_keys is not a dict or not in a recognized format, api_keys_to_process remains empty

        logger.info(f"API Keys to process: {api_keys_to_process}")

        if not api_keys_to_process:
             return {"tvl": 0.0, "free_usdt": 0.0}

        encryption_service = EncryptionService()
        
        # Iterate over all configured exchanges
        for exchange_name, encrypted_data in api_keys_to_process.items():
            logger.info(f"Processing exchange: {exchange_name}, Encrypted data keys: {encrypted_data.keys() if isinstance(encrypted_data, dict) else 'Not a dict'}")
            if not isinstance(encrypted_data, dict) or "encrypted_data" not in encrypted_data:
                continue

            connector = None
            try:
                # Decrypt keys
                api_key, secret_key = encryption_service.decrypt_keys(encrypted_data)
                
                # Connect to exchange
                try:
                    connector = get_exchange_connector(
                        exchange_type=exchange_name,
                        api_key=api_key,
                        secret_key=secret_key
                    )
                except Exception as e:
                    logger.warning(f"Skipping account summary for {exchange_name}: {e}")
                    continue
                
                # Fetch balance
                balances = await connector.fetch_balance()
                
                total_balances = {}
                if "total" in balances and isinstance(balances["total"], dict):
                    total_balances = balances["total"]
                else:
                    total_balances = balances
                
                free_balances = {}
                if "free" in balances and isinstance(balances["free"], dict):
                    free_balances = balances["free"]
                
                # Use 'free' balance for Free USDT display, fallback to total or 0
                exchange_free_usdt = free_balances.get("USDT", total_balances.get("USDT", 0.0))
                total_free_usdt += float(exchange_free_usdt)

                for asset, amount in total_balances.items():
                    if amount > 0 and asset != exchange_name:
                        if asset == "USDT":
                            total_tvl += amount
                        else:
                            # Convert other assets to USDT value
                            try:
                                # Assuming get_current_price can handle conversion to USDT
                                price_in_usdt = await connector.get_current_price(f"{asset}/USDT")
                                total_tvl += amount * price_in_usdt
                            except Exception as e:
                                error_msg = str(e)
                                if "does not have market symbol" in error_msg or "symbol not found" in error_msg.lower():
                                    logger.debug(f"Skipping TVL calculation for {asset}: No market symbol {asset}/USDT on {exchange_name}")
                                else:
                                    logger.warning(f"Could not fetch price for {asset}/USDT on {exchange_name}: {e}")
            except Exception as e:
                logger.error(f"Error processing account summary for {exchange_name}: {e}")
            finally:
                 # Cleanup connection
                if connector and hasattr(connector, 'exchange') and hasattr(connector.exchange, 'close'):
                     await connector.exchange.close()
            
        return {"tvl": float(total_tvl), "free_usdt": float(total_free_usdt)}

    except Exception as e:
        logger.error(f"Error calculating account summary: {e}")
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
    logger.debug(f"get_pnl: Found {len(active_groups)} active position groups for user {current_user.id}")
    
    if active_groups and current_user.encrypted_api_keys:
        logger.debug(f"get_pnl: User {current_user.id} has encrypted API keys. Attempting unrealized PnL calculation.")
        
        # Group positions by exchange
        groups_by_exchange = {}
        for group in active_groups:
            # Fallback to user.exchange if group.exchange is missing (though model enforces it)
            ex = group.exchange or current_user.exchange or "binance"
            if ex not in groups_by_exchange:
                groups_by_exchange[ex] = []
            groups_by_exchange[ex].append(group)
            
        # Normalize user keys
        api_keys_map = {}
        raw_keys = current_user.encrypted_api_keys
        if isinstance(raw_keys, dict):
            if "encrypted_data" in raw_keys:
                 exchange = current_user.exchange or "binance"
                 api_keys_map[exchange] = raw_keys
            else:
                 api_keys_map = raw_keys

        encryption_service = EncryptionService()

        # Iterate over exchanges that have active positions
        for exchange_name, groups in groups_by_exchange.items():
            if exchange_name not in api_keys_map:
                logger.warning(f"get_pnl: No API keys found for exchange '{exchange_name}' to price {len(groups)} positions.")
                continue
                
            encrypted_data = api_keys_map[exchange_name]
            connector = None
            try:
                api_key, secret_key = encryption_service.decrypt_keys(encrypted_data)
                
                try:
                    connector = get_exchange_connector(
                        exchange_type=exchange_name,
                        api_key=api_key,
                        secret_key=secret_key
                    )
                except Exception as e:
                    logger.warning(f"get_pnl: Could not create connector for {exchange_name}: {e}")
                    continue

                for group in groups:
                    logger.debug(f"get_pnl: Processing active group {group.id} (Symbol: {group.symbol}) on {exchange_name}")
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
                        logger.error(f"Error fetching price for {group.symbol} on {exchange_name}: {e}")
            
            except Exception as e:
                 logger.error(f"Error calculating PnL for exchange {exchange_name}: {e}")
            finally:
                if connector and hasattr(connector, 'exchange') and hasattr(connector.exchange, 'close'):
                        await connector.exchange.close()

    total_pnl = float(realized_pnl) + unrealized_pnl
    logger.debug(f"Total Realized PnL: {realized_pnl}, Total Unrealized PnL: {unrealized_pnl}, Total PnL: {total_pnl}")
    return {"pnl": total_pnl}

@router.get("/active-groups-count")
async def get_active_groups_count(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    repo = PositionGroupRepository(db)
    groups = await repo.get_active_position_groups_for_user(current_user.id)
    return {"count": len(groups)}
