from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from app.db.database import get_db_session
from app.api.dependencies.users import get_current_active_user
from app.models.user import User
from app.repositories.position_group import PositionGroupRepository
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.core.security import EncryptionService
from app.core.cache import get_cache
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
    if not current_user.encrypted_api_keys:
        return {"tvl": 0.0, "free_usdt": 0.0}

    # Try to get cached dashboard data first
    cache = await get_cache()
    user_id_str = str(current_user.id)
    cached_data = await cache.get_dashboard(user_id_str, "account-summary")
    if cached_data:
        logger.debug(f"Returning cached account summary for user {user_id_str}")
        return cached_data

    total_tvl = 0.0
    total_free_usdt = 0.0

    api_keys_to_process = {}
    if current_user.encrypted_api_keys and isinstance(current_user.encrypted_api_keys, dict):
        api_keys_to_process = current_user.encrypted_api_keys

    logger.info(f"API Keys to process: {api_keys_to_process}")

    if not api_keys_to_process:
        return {"tvl": 0.0, "free_usdt": 0.0}

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
                    exchange_config=exchange_config
                )
            except Exception as e:
                logger.warning(f"Skipping account summary for {exchange_name}: {e}")
                continue

            # Try to get cached balance first
            cached_balance = await cache.get_balance(user_id_str, exchange_name)
            if cached_balance:
                logger.debug(f"Using cached balance for {exchange_name}")
                balances = cached_balance
            else:
                # Fetch balance from exchange
                balances = await connector.fetch_balance()
                # Cache the balance (5 min TTL)
                await cache.set_balance(user_id_str, exchange_name, balances)

            total_balances = {}
            if "total" in balances and isinstance(balances["total"], dict):
                total_balances = balances["total"]
            else:
                total_balances = balances

            free_balances = {}
            if "free" in balances and isinstance(balances["free"], dict):
                free_balances = balances["free"]

            # Use 'free' balance for Free USDT display, fallback to total or 0
            exchange_free_usdt = float(free_balances.get("USDT", total_balances.get("USDT", Decimal(0))))
            total_free_usdt += exchange_free_usdt

            # Try to get cached tickers first
            cached_tickers = await cache.get_tickers(exchange_name)
            if cached_tickers:
                logger.debug(f"Using cached tickers for {exchange_name}")
                all_tickers = cached_tickers
            else:
                # Fetch ALL tickers once
                all_tickers = {}
                try:
                    all_tickers = await connector.get_all_tickers()
                    logger.info(f"Fetched {len(all_tickers)} tickers from {exchange_name}")
                    # Cache tickers (1 min TTL)
                    await cache.set_tickers(exchange_name, all_tickers)
                except Exception as e:
                    logger.warning(f"Could not fetch all tickers from {exchange_name}: {e}. Falling back to individual fetches.")

            # Helper to get price from cache or fetch individually
            async def get_price(symbol):
                # Try direct match
                if symbol in all_tickers:
                    return float(all_tickers[symbol]['last'])

                # Try common variations if needed (e.g. BTC/USDT vs BTCUSDT)
                if symbol.replace('/', '') in all_tickers:
                        return float(all_tickers[symbol.replace('/', '')]['last'])

                # Fallback to individual fetch
                return await connector.get_current_price(symbol)

            for asset, amount_decimal in total_balances.items():
                amount = float(amount_decimal) if isinstance(amount_decimal, Decimal) else float(amount_decimal)
                logger.debug(f"Processing asset: {asset}, amount: {amount}, current total_tvl: {total_tvl}")

                if amount <= 0:
                    continue

                if asset == exchange_name:
                    continue

                if asset == "USDT":
                    total_tvl += amount
                    logger.debug(f"Added USDT to TVL. New total_tvl: {total_tvl}")
                else:
                    symbol = f"{asset}/USDT"
                    price_in_usdt = await get_price(symbol)
                    logger.debug(f"Price for {symbol}: {price_in_usdt}")

                    asset_value = amount * price_in_usdt
                    logger.debug(f"Value for {asset}: {asset_value}")

                    if asset_value < MIN_BALANCE_THRESHOLD:
                        continue

                    total_tvl += asset_value
                    logger.debug(f"Added {asset_value} ({asset}) to TVL. New total_tvl: {total_tvl}")
        except Exception as e:
            logger.error(f"Error processing account summary for {exchange_name}: {e}")
            continue
        finally:
            if connector and hasattr(connector, 'exchange') and hasattr(connector.exchange, 'close'):
                    await connector.exchange.close()

    result = {"tvl": float(total_tvl), "free_usdt": float(total_free_usdt)}

    # Cache the dashboard result (1 min TTL)
    await cache.set_dashboard(user_id_str, "account-summary", result)

    return result

@router.get("/pnl")
async def get_pnl(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    # Try to get cached PnL data first
    cache = await get_cache()
    user_id_str = str(current_user.id)
    cached_data = await cache.get_dashboard(user_id_str, "pnl")
    if cached_data:
        logger.debug(f"Returning cached PnL data for user {user_id_str}")
        return cached_data

    repo = PositionGroupRepository(db)

    realized_pnl = await repo.get_total_realized_pnl_only(current_user.id)

    unrealized_pnl = 0.0
    active_groups = await repo.get_active_position_groups_for_user(current_user.id)
    logger.debug(f"get_pnl: Found {len(active_groups)} active position groups for user {current_user.id}")

    if active_groups and current_user.encrypted_api_keys:
        logger.debug(f"get_pnl: User {current_user.id} has encrypted API keys. Attempting unrealized PnL calculation.")

        groups_by_exchange = {}
        for group in active_groups:
            ex = group.exchange or current_user.exchange or "binance"
            if ex not in groups_by_exchange:
                groups_by_exchange[ex] = []
            groups_by_exchange[ex].append(group)

        api_keys_map = {}
        if current_user.encrypted_api_keys and isinstance(current_user.encrypted_api_keys, dict):
            api_keys_map = current_user.encrypted_api_keys

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
                try:
                    connector = get_exchange_connector(
                        exchange_type=exchange_name,
                        exchange_config=exchange_config
                    )
                except Exception as e:
                    logger.warning(f"get_pnl: Could not create connector for {exchange_name}: {e}")
                    continue

                # Try to get cached tickers first
                all_tickers = await cache.get_tickers(exchange_name)
                if not all_tickers:
                    try:
                        all_tickers = await connector.get_all_tickers()
                        logger.info(f"get_pnl: Fetched {len(all_tickers)} tickers from {exchange_name}")
                        # Cache tickers (1 min TTL)
                        await cache.set_tickers(exchange_name, all_tickers)
                    except Exception as e:
                        logger.warning(f"get_pnl: Could not fetch all tickers from {exchange_name}: {e}. Falling back to individual fetches.")
                        all_tickers = {}
                else:
                    logger.debug(f"get_pnl: Using cached tickers for {exchange_name}")

                async def get_price(symbol):
                    if symbol in all_tickers:
                        return float(all_tickers[symbol]['last'])

                    if symbol.replace('/', '') in all_tickers:
                         return float(all_tickers[symbol.replace('/', '')]['last'])

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

    result = {
        "pnl": total_pnl,
        "realized_pnl": float(realized_pnl),
        "unrealized_pnl": unrealized_pnl
    }

    # Cache the PnL result (1 min TTL)
    await cache.set_dashboard(user_id_str, "pnl", result)

    return result

@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    repo = PositionGroupRepository(db)
    # Stats endpoint needs all closed positions for win/loss calculation
    closed_groups = await repo.get_closed_by_user_all(current_user.id)

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

@router.get("/analytics")
async def get_comprehensive_analytics(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Single optimized endpoint for all dashboard data.
    Returns both live dashboard and performance dashboard metrics.
    """
    from app.services.analytics_service import AnalyticsService

    analytics = AnalyticsService(db, current_user)
    data = await analytics.get_comprehensive_dashboard_data()
    return data