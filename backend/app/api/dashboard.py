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

# Minimum balance threshold in USD to consider for TVL calculation
# This helps skip "dust" balances that would slow down the dashboard
MIN_BALANCE_THRESHOLD = 0.10  # $0.10 USD

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
        if current_user.encrypted_api_keys and isinstance(current_user.encrypted_api_keys, dict):
            api_keys_to_process = current_user.encrypted_api_keys

        logger.info(f"API Keys to process: {api_keys_to_process}")

        if not api_keys_to_process:
             return {"tvl": 0.0, "free_usdt": 0.0}

        encryption_service = EncryptionService()
        
        # Iterate over all configured exchanges
        for exchange_name, encrypted_data_raw in api_keys_to_process.items():
            exchange_config = {}
            if isinstance(encrypted_data_raw, str):
                # Legacy format: encrypted string directly
                exchange_config = {"encrypted_data": encrypted_data_raw}
            elif isinstance(encrypted_data_raw, dict):
                # New format: dictionary with 'encrypted_data' key and potentially 'testnet', 'account_type'
                exchange_config = encrypted_data_raw
            else:
                logger.warning(f"Skipping account summary for {exchange_name}: Unexpected API key data type: {type(encrypted_data_raw)}")
                continue

            logger.info(f"Processing exchange: {exchange_name}, Exchange config keys: {exchange_config.keys() if isinstance(exchange_config, dict) else 'Not a dict'}")
            if "encrypted_data" not in exchange_config:
                logger.warning(f"Skipping account summary for {exchange_name}: 'encrypted_data' key not found in exchange configuration.")
                continue
            
            connector = None
            try:
                # The factory will now handle decryption and parameter extraction
                try:
                    connector = get_exchange_connector(
                        exchange_type=exchange_name,
                        exchange_config=exchange_config # This now contains testnet, account_type, etc.
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

                # Fetch ALL tickers once
                all_tickers = {}
                try:
                    all_tickers = await connector.get_all_tickers()
                    logger.info(f"Fetched {len(all_tickers)} tickers from {exchange_name}")
                except Exception as e:
                    logger.warning(f"Could not fetch all tickers from {exchange_name}: {e}. Falling back to individual fetches.")
                
                # Helper to get price from cache or fetch individually
                async def get_price(symbol):
                    # Try direct match
                    if symbol in all_tickers:
                        return float(all_tickers[symbol]['last'])
                    
                    # Try common variations if needed (e.g. BTC/USDT vs BTCUSDT)
                    # CCXT usually unifies to BTC/USDT, but let's be safe
                    if symbol.replace('/', '') in all_tickers:
                         return float(all_tickers[symbol.replace('/', '')]['last'])
                         
                    # Fallback to individual fetch
                    return await connector.get_current_price(symbol)

                for asset, amount in total_balances.items():
                    # Skip assets with zero or negative amounts
                    if amount <= 0:
                        continue
                    
                    # Skip the exchange's native token if it appears as a balance key
                    if asset == exchange_name:
                        continue
                        
                    if asset == "USDT":
                        total_tvl += amount
                    else:
                        # Skip dust balances to avoid slow price lookups
                        # For non-USDT assets, we estimate: if the asset had a price of $0.10,
                        # would the balance be worth at least MIN_BALANCE_THRESHOLD?
                        if amount < (MIN_BALANCE_THRESHOLD / 0.10):  # ~1 unit minimum
                            # logger.debug(f"Skipping dust balance for {asset}: {amount} (below threshold)")
                            continue
                            
                        # Convert other assets to USDT value
                        try:
                            # Assuming get_current_price can handle conversion to USDT
                            symbol = f"{asset}/USDT"
                            price_in_usdt = await get_price(symbol)
                            
                            asset_value = amount * price_in_usdt
                            
                            # Final check: skip if the actual USD value is below threshold
                            if asset_value < MIN_BALANCE_THRESHOLD:
                                # logger.debug(f"Skipping low-value balance for {asset}: ${asset_value:.4f}")
                                continue
                                
                            total_tvl += asset_value
                        except Exception as e:
                            # error_msg = str(e)
                            # if "does not have market symbol" in error_msg or "symbol not found" in error_msg.lower():
                            #     logger.debug(f"Skipping TVL calculation for {asset}: No market symbol {asset}/USDT on {exchange_name}")
                            # else:
                            #     logger.warning(f"Could not fetch price for {asset}/USDT on {exchange_name}: {e}")
                            pass # Skip silently to reduce log noise for non-USDT pairs
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
        if current_user.encrypted_api_keys and isinstance(current_user.encrypted_api_keys, dict):
            api_keys_map = current_user.encrypted_api_keys

        encryption_service = EncryptionService()

        # Iterate over exchanges that have active positions
        logger.debug(f"get_pnl: API Keys map for PnL calculation: {api_keys_map}")
        for exchange_name, groups in groups_by_exchange.items():
            lookup_key = exchange_name.lower()
            if lookup_key not in api_keys_map:
                logger.warning(f"get_pnl: No API keys found for exchange '{exchange_name}' (lookup: '{lookup_key}') to price {len(groups)} positions.")
                continue
                
            encrypted_data_raw = api_keys_map[lookup_key]
            exchange_config = {}
            if isinstance(encrypted_data_raw, str):
                # Legacy format: encrypted string directly
                exchange_config = {"encrypted_data": encrypted_data_raw}
            elif isinstance(encrypted_data_raw, dict):
                exchange_config = encrypted_data_raw
            else:
                logger.warning(f"get_pnl: Skipping exchange {exchange_name}: Unexpected API key data type: {type(encrypted_data_raw)}")
                continue

            if "encrypted_data" not in exchange_config:
                logger.warning(f"get_pnl: Skipping exchange {exchange_name}: 'encrypted_data' key not found in configuration.")
                continue

            connector = None
            try:
                # The factory will now handle decryption and parameter extraction
                try:
                    connector = get_exchange_connector(
                        exchange_type=exchange_name,
                        exchange_config=exchange_config
                    )
                except Exception as e:
                    logger.warning(f"get_pnl: Could not create connector for {exchange_name}: {e}")
                    continue

                # Fetch ALL tickers once
                all_tickers = {}
                try:
                    all_tickers = await connector.get_all_tickers()
                    logger.info(f"get_pnl: Fetched {len(all_tickers)} tickers from {exchange_name}")
                except Exception as e:
                    logger.warning(f"get_pnl: Could not fetch all tickers from {exchange_name}: {e}. Falling back to individual fetches.")

                # Helper to get price from cache or fetch individually
                async def get_price(symbol):
                    # Try direct match
                    if symbol in all_tickers:
                        return float(all_tickers[symbol]['last'])
                    
                    # Try common variations if needed
                    if symbol.replace('/', '') in all_tickers:
                         return float(all_tickers[symbol.replace('/', '')]['last'])
                         
                    # Fallback to individual fetch
                    return await connector.get_current_price(symbol)

                for group in groups:
                    logger.debug(f"get_pnl: Processing active group {group.id} (Symbol: {group.symbol}) on {exchange_name}")
                    try:
                        current_price = await get_price(group.symbol)
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
    return {
        "pnl": total_pnl,
        "realized_pnl": float(realized_pnl),
        "unrealized_pnl": unrealized_pnl
    }

@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    repo = PositionGroupRepository(db)
    closed_groups = await repo.get_closed_by_user(current_user.id)
    
    total_trades = len(closed_groups)
    wins = 0
    losses = 0
    
    for group in closed_groups:
        if group.realized_pnl_usd > 0:
            wins += 1
        else:
            losses += 1
            
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    
    return {
        "total_trades": total_trades,
        "total_winning_trades": wins,
        "total_losing_trades": losses,
        "win_rate": win_rate
    }

@router.get("/active-groups-count")
async def get_active_groups_count(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    repo = PositionGroupRepository(db)
    groups = await repo.get_active_position_groups_for_user(current_user.id)
    return {"count": len(groups)}
