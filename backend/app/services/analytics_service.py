"""
Analytics Service - Comprehensive dashboard metrics calculation
Optimized for performance with minimal database and exchange queries
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models.position_group import PositionGroup
from app.models.queued_signal import QueuedSignal
from app.models.user import User
from app.repositories.position_group import PositionGroupRepository
from app.services.exchange_abstraction.factory import get_exchange_connector

logger = logging.getLogger(__name__)

MIN_BALANCE_THRESHOLD = 0.10  # $0.10 USD


class AnalyticsService:
    def __init__(self, session: AsyncSession, user: User):
        self.session = session
        self.user = user
        self.position_repo = PositionGroupRepository(session)

    async def get_comprehensive_dashboard_data(self) -> Dict:
        """
        Single optimized call to get all dashboard data
        """
        logger.info(f"Fetching comprehensive dashboard data for user {self.user.id}")

        # Fetch all database metrics in parallel
        (
            active_positions,
            closed_positions,
            queued_signals_count,
            last_webhook_time
        ) = await self._fetch_database_metrics()

        # Fetch exchange data once
        exchange_data = await self._fetch_exchange_data_optimized(active_positions)

        # Calculate all metrics
        live_dashboard = self._calculate_live_dashboard(
            active_positions,
            closed_positions,
            queued_signals_count,
            last_webhook_time,
            exchange_data
        )

        performance_dashboard = self._calculate_performance_dashboard(
            closed_positions,
            active_positions,
            exchange_data
        )

        return {
            "live_dashboard": live_dashboard,
            "performance_dashboard": performance_dashboard,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _fetch_database_metrics(self) -> Tuple:
        """Fetch all database metrics in parallel"""
        # Get all positions
        active_positions = await self.position_repo.get_active_position_groups_for_user(self.user.id)
        closed_positions = await self.position_repo.get_closed_by_user(self.user.id)

        # Get queued signals count
        queued_result = await self.session.execute(
            select(func.count(QueuedSignal.id))
            .where(and_(
                QueuedSignal.user_id == self.user.id,
                QueuedSignal.status == 'queued'
            ))
        )
        queued_signals_count = queued_result.scalar() or 0

        # Get last webhook time (from most recent position or signal)
        last_webhook_time = None
        if active_positions:
            last_webhook_time = max(
                (p.created_at for p in active_positions if p.created_at),
                default=None
            )

        return active_positions, closed_positions, queued_signals_count, last_webhook_time

    async def _fetch_exchange_data_optimized(self, active_positions: List[PositionGroup]) -> Dict:
        """
        Fetch exchange data (balances + prices) once per exchange
        """
        exchange_data = {}

        if not self.user.encrypted_api_keys:
            return exchange_data

        api_keys_map = self.user.encrypted_api_keys if isinstance(self.user.encrypted_api_keys, dict) else {}

        # Group positions by exchange
        exchanges_needed = set()
        for pos in active_positions:
            exchanges_needed.add(pos.exchange or self.user.exchange or "binance")

        # Add all configured exchanges for balance fetching
        exchanges_needed.update(api_keys_map.keys())

        for exchange_name in exchanges_needed:
            lookup_key = exchange_name.lower()
            if lookup_key not in api_keys_map:
                continue

            encrypted_data_raw = api_keys_map[lookup_key]
            exchange_config = {}

            if isinstance(encrypted_data_raw, str):
                exchange_config = {"encrypted_data": encrypted_data_raw}
            elif isinstance(encrypted_data_raw, dict):
                exchange_config = encrypted_data_raw
            else:
                continue

            if "encrypted_data" not in exchange_config:
                continue

            connector = None
            try:
                connector = get_exchange_connector(
                    exchange_type=exchange_name,
                    exchange_config=exchange_config
                )

                # Fetch balance
                balances = await connector.fetch_balance()

                # Fetch all tickers once
                all_tickers = {}
                try:
                    all_tickers = await connector.get_all_tickers()
                except Exception as e:
                    logger.warning(f"Could not fetch tickers from {exchange_name}: {e}")

                exchange_data[exchange_name] = {
                    "balances": balances,
                    "tickers": all_tickers
                }

            except Exception as e:
                logger.error(f"Error fetching data from {exchange_name}: {e}")
            finally:
                if connector and hasattr(connector, 'exchange') and hasattr(connector.exchange, 'close'):
                    await connector.exchange.close()

        return exchange_data

    def _calculate_live_dashboard(
        self,
        active_positions: List[PositionGroup],
        closed_positions: List[PositionGroup],
        queued_signals_count: int,
        last_webhook_time: Optional[datetime],
        exchange_data: Dict
    ) -> Dict:
        """Calculate live dashboard metrics"""

        # Count active position groups (not pyramids/legs)
        total_active_groups = len(active_positions)

        # Calculate unrealized PnL from active positions
        total_unrealized_pnl = 0.0
        for group in active_positions:
            ex = group.exchange or self.user.exchange or "binance"
            if ex in exchange_data:
                try:
                    current_price = self._get_price_from_cache(
                        group.symbol,
                        exchange_data[ex]['tickers']
                    )
                    if current_price and group.total_filled_quantity and group.weighted_avg_entry:
                        qty = float(group.total_filled_quantity)
                        avg_entry = float(group.weighted_avg_entry)
                        if qty > 0:
                            if group.side == "long":
                                pnl = (current_price - avg_entry) * qty
                            else:
                                pnl = (avg_entry - current_price) * qty
                            total_unrealized_pnl += pnl
                except Exception as e:
                    logger.error(f"Error calculating PnL for {group.symbol}: {e}")

        # Calculate realized PnL from closed positions
        total_realized_pnl = 0.0
        now = datetime.utcnow()
        pnl_today = 0.0
        total_trades = len(closed_positions)
        wins = 0
        losses = 0

        for group in closed_positions:
            pnl = float(group.realized_pnl_usd) if group.realized_pnl_usd else 0.0
            total_realized_pnl += pnl

            # Win/Loss tracking
            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1

            # Today's PnL
            if group.closed_at and group.closed_at >= now - timedelta(days=1):
                pnl_today += pnl

        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

        # Calculate TVL and free USDT
        total_tvl = 0.0
        total_free_usdt = 0.0

        for exchange_name, data in exchange_data.items():
            balances = data['balances']
            tickers = data['tickers']

            total_balances = balances.get('total', balances)
            free_balances = balances.get('free', {})

            exchange_free_usdt = float(free_balances.get("USDT", total_balances.get("USDT", Decimal(0))))
            total_free_usdt += exchange_free_usdt

            for asset, amount_decimal in total_balances.items():
                amount = float(amount_decimal) if isinstance(amount_decimal, Decimal) else float(amount_decimal)

                if amount <= 0 or asset == exchange_name:
                    continue

                if asset == "USDT":
                    total_tvl += amount
                else:
                    symbol = f"{asset}/USDT"
                    price = self._get_price_from_cache(symbol, tickers)
                    if price:
                        asset_value = amount * price
                        if asset_value >= MIN_BALANCE_THRESHOLD:
                            total_tvl += asset_value

        return {
            "total_active_position_groups": total_active_groups,
            "queued_signals_count": queued_signals_count,
            "total_pnl_usd": total_realized_pnl + total_unrealized_pnl,
            "realized_pnl_usd": total_realized_pnl,
            "unrealized_pnl_usd": total_unrealized_pnl,
            "pnl_today": pnl_today,
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "tvl": total_tvl,
            "free_usdt": total_free_usdt,
            "last_webhook_timestamp": last_webhook_time.isoformat() if last_webhook_time else None,
            "engine_status": "running",  # TODO: Get from actual engine status
            "risk_engine_status": "active"  # TODO: Get from risk engine
        }

    def _calculate_performance_dashboard(
        self,
        closed_positions: List[PositionGroup],
        active_positions: List[PositionGroup],
        exchange_data: Dict
    ) -> Dict:
        """Calculate performance metrics"""

        # Calculate unrealized PnL for open positions
        total_unrealized_pnl = 0.0
        for group in active_positions:
            ex = group.exchange or self.user.exchange or "binance"
            if ex in exchange_data:
                try:
                    current_price = self._get_price_from_cache(
                        group.symbol,
                        exchange_data[ex]['tickers']
                    )
                    if current_price and group.total_filled_quantity and group.weighted_avg_entry:
                        qty = float(group.total_filled_quantity)
                        avg_entry = float(group.weighted_avg_entry)
                        if qty > 0:
                            if group.side == "long":
                                pnl = (current_price - avg_entry) * qty
                            else:
                                pnl = (avg_entry - current_price) * qty
                            total_unrealized_pnl += pnl
                except Exception:
                    pass

        # Process closed positions for performance metrics
        total_realized_pnl = 0.0
        wins = 0
        losses = 0
        win_amounts = []
        loss_amounts = []
        pnl_by_pair = defaultdict(float)
        pnl_by_timeframe = defaultdict(float)
        trade_returns = []

        # Time-based PnL
        now = datetime.utcnow()
        pnl_today = 0.0
        pnl_week = 0.0
        pnl_month = 0.0

        for group in closed_positions:
            pnl = float(group.realized_pnl_usd) if group.realized_pnl_usd else 0.0
            total_realized_pnl += pnl
            trade_returns.append(pnl)

            # Win/Loss tracking
            if pnl > 0:
                wins += 1
                win_amounts.append(pnl)
            else:
                losses += 1
                loss_amounts.append(abs(pnl))

            # By pair
            if group.symbol:
                pnl_by_pair[group.symbol] += pnl

            # By timeframe
            if group.timeframe:
                pnl_by_timeframe[str(group.timeframe)] += pnl

            # Time-based
            if group.closed_at:
                if group.closed_at >= now - timedelta(days=1):
                    pnl_today += pnl
                if group.closed_at >= now - timedelta(days=7):
                    pnl_week += pnl
                if group.closed_at >= now - timedelta(days=30):
                    pnl_month += pnl

        total_trades = len(closed_positions)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

        avg_win = sum(win_amounts) / len(win_amounts) if win_amounts else 0.0
        avg_loss = sum(loss_amounts) / len(loss_amounts) if loss_amounts else 0.0
        rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0

        # Calculate drawdown
        equity_curve = []
        running_equity = 0.0
        peak_equity = 0.0
        max_drawdown = 0.0
        current_drawdown = 0.0

        for group in sorted(closed_positions, key=lambda x: x.closed_at or datetime.min):
            pnl = float(group.realized_pnl_usd) if group.realized_pnl_usd else 0.0
            running_equity += pnl
            equity_curve.append({
                "timestamp": group.closed_at.isoformat() if group.closed_at else None,
                "equity": running_equity
            })

            if running_equity > peak_equity:
                peak_equity = running_equity

            drawdown = peak_equity - running_equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        current_drawdown = peak_equity - running_equity if peak_equity > 0 else 0.0

        # Best and worst trades
        sorted_trades = sorted(
            [(g.symbol, float(g.realized_pnl_usd) if g.realized_pnl_usd else 0.0) for g in closed_positions],
            key=lambda x: x[1]
        )
        worst_trades = sorted_trades[:10]
        best_trades = sorted_trades[-10:][::-1]

        # Profit factor
        total_wins = sum(win_amounts)
        total_losses = sum(loss_amounts)
        profit_factor = total_wins / total_losses if total_losses > 0 else 0.0

        # Sharpe/Sortino (simplified)
        if trade_returns:
            avg_return = sum(trade_returns) / len(trade_returns)
            variance = sum((r - avg_return) ** 2 for r in trade_returns) / len(trade_returns)
            std_dev = variance ** 0.5
            sharpe_ratio = avg_return / std_dev if std_dev > 0 else 0.0

            negative_returns = [r for r in trade_returns if r < 0]
            if negative_returns:
                downside_variance = sum((r - avg_return) ** 2 for r in negative_returns) / len(negative_returns)
                downside_dev = downside_variance ** 0.5
                sortino_ratio = avg_return / downside_dev if downside_dev > 0 else 0.0
            else:
                sortino_ratio = 0.0
        else:
            sharpe_ratio = 0.0
            sortino_ratio = 0.0

        return {
            "pnl_metrics": {
                "realized_pnl": total_realized_pnl,
                "unrealized_pnl": total_unrealized_pnl,
                "total_pnl": total_realized_pnl + total_unrealized_pnl,
                "pnl_today": pnl_today,
                "pnl_week": pnl_week,
                "pnl_month": pnl_month,
                "pnl_all_time": total_realized_pnl,
                "pnl_by_pair": dict(pnl_by_pair),
                "pnl_by_timeframe": dict(pnl_by_timeframe)
            },
            "equity_curve": equity_curve,
            "win_loss_stats": {
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "rr_ratio": rr_ratio
            },
            "trade_distribution": {
                "returns": trade_returns,
                "best_trades": best_trades,
                "worst_trades": worst_trades
            },
            "risk_metrics": {
                "max_drawdown": max_drawdown,
                "current_drawdown": current_drawdown,
                "sharpe_ratio": sharpe_ratio,
                "sortino_ratio": sortino_ratio,
                "profit_factor": profit_factor
            }
        }

    def _get_price_from_cache(self, symbol: str, tickers: Dict) -> Optional[float]:
        """Get price from ticker cache"""
        if symbol in tickers:
            last_price = tickers[symbol].get('last')
            if last_price is not None:
                return float(last_price)

        normalized_symbol = symbol.replace('/', '')
        if normalized_symbol in tickers:
            last_price = tickers[normalized_symbol].get('last')
            if last_price is not None:
                return float(last_price)

        return None
