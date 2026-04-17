"""Execution engine for order placement and management."""

import asyncio
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import time

import ccxt.async_support as ccxt

from models.orders import Order, OrderStatus, OrderType, OrderManager
from models.positions import Position, PositionManager, PositionStatus
from core.risk_manager import RiskManager
from utils.config import get_config
from utils.logger import get_logger


class ExecutionEngine:
    """Handles order execution and position management."""
    
    def __init__(self, exchange: ccxt.Exchange, risk_manager: RiskManager):
        """
        Initialize execution engine.
        
        Args:
            exchange: CCXT exchange instance
            risk_manager: Risk management instance
        """
        self.config = get_config()
        self.logger = get_logger(self.__class__.__name__)
        self.exchange = exchange
        self.risk_manager = risk_manager
        
        # Managers
        self.order_manager = OrderManager()
        self.position_manager = PositionManager()
        
        # Execution settings
        self.max_retries = 3
        self.retry_delay = 0.5  # seconds
        self.slippage_tolerance = 0.002  # 0.2%
        
        # Performance tracking
        self.execution_stats = {
            'total_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'total_slippage': Decimal(0),
            'avg_execution_time': 0.0
        }
        
        # Order monitoring
        self.monitoring_active = False
        self.monitor_interval = 1.0  # seconds
        
        self.logger.info("Execution engine initialized")
    
    async def execute_order(self, order: Order) -> Tuple[bool, Optional[str]]:
        """
        Execute an order with retry logic.
        
        Returns:
            Tuple of (success, error_message)
        """
        self.execution_stats['total_orders'] += 1
        
        # Add to order manager
        self.order_manager.add_order(order)
        
        # Attempt execution with retries
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                
                # Submit order to exchange
                if self.config.is_live_trading:
                    response = await self._submit_order_to_exchange(order)
                else:
                    response = await self._simulate_order_execution(order)
                
                # Update order with exchange response
                if response and 'id' in response:
                    order.exchange_order_id = response['id']
                    self.order_manager.update_exchange_id(order.order_id, response['id'])
                    order.update_status(OrderStatus.SUBMITTED, response)
                    
                    # Log successful submission
                    execution_time = time.time() - start_time
                    self.logger.trade(
                        action="ORDER_SUBMITTED",
                        symbol=order.symbol,
                        side=order.side.value,
                        amount=float(order.size),
                        price=float(order.price) if order.price else 0,
                        order_id=order.client_order_id,
                        execution_time=f"{execution_time:.3f}s"
                    )
                    
                    self.execution_stats['successful_orders'] += 1
                    return True, None
                else:
                    raise Exception("Invalid exchange response")
                    
            except Exception as e:
                error_msg = f"Order execution failed (attempt {attempt + 1}/{self.max_retries}): {str(e)}"
                self.logger.error(error_msg)
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    order.update_status(OrderStatus.REJECTED, {'error': str(e)})
                    self.execution_stats['failed_orders'] += 1
                    return False, error_msg
        
        return False, "Max retries exceeded"
    
    async def execute_position_entry(self, symbol: str, side: str, size: Decimal,
                                   current_price: Decimal, strategy_name: str,
                                   signal_strength: float) -> Optional[Position]:
        """
        Execute a complete position entry with stop loss and take profit.
        
        Returns:
            Position object if successful, None otherwise
        """
        try:
            # Calculate stop loss and take profit prices
            stop_loss = self.risk_manager.get_stop_loss_price(float(current_price), side)
            take_profit = self.risk_manager.get_take_profit_price(float(current_price), side)
            
            # Create position
            position = Position.create_new(
                symbol=symbol,
                side=side,
                size=size,
                entry_price=current_price,
                stop_loss=Decimal(str(stop_loss)),
                take_profit=Decimal(str(take_profit)),
                leverage=self.risk_manager.current_leverage,
                strategy_name=strategy_name,
                signal_strength=signal_strength
            )
            
            # Add to position manager
            self.position_manager.add_position(position)
            
            # Create entry order
            entry_order = Order.create_market_order(
                symbol=symbol,
                side=side,
                size=size,
                position_id=position.position_id,
                strategy_name=strategy_name,
                reason="position_entry"
            )
            
            # Execute entry order
            success, error = await self.execute_order(entry_order)
            
            if success:
                position.entry_order_ids.append(entry_order.order_id)
                position.status = PositionStatus.OPEN
                
                # Place stop loss order
                stop_side = 'sell' if side == 'buy' else 'buy'
                stop_order = Order.create_stop_order(
                    symbol=symbol,
                    side=stop_side,
                    size=size,
                    stop_price=Decimal(str(stop_loss)),
                    position_id=position.position_id,
                    strategy_name=strategy_name,
                    reason="stop_loss"
                )
                
                # Execute stop loss order
                stop_success, _ = await self.execute_order(stop_order)
                if stop_success:
                    position.exit_order_ids.append(stop_order.order_id)
                
                # Place take profit order
                tp_order = Order.create_limit_order(
                    symbol=symbol,
                    side=stop_side,
                    size=size,
                    price=Decimal(str(take_profit)),
                    reduce_only=True,
                    position_id=position.position_id,
                    strategy_name=strategy_name,
                    reason="take_profit"
                )
                
                # Execute take profit order
                tp_success, _ = await self.execute_order(tp_order)
                if tp_success:
                    position.exit_order_ids.append(tp_order.order_id)
                
                self.logger.success(
                    f"Position opened: {symbol} {side} {size} @ {current_price} | "
                    f"SL: {stop_loss:.2f} | TP: {take_profit:.2f}"
                )
                
                return position
                
            else:
                # Failed to enter position
                position.status = PositionStatus.CLOSED
                self.logger.error(f"Failed to open position: {error}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error executing position entry: {e}", exc_info=True)
            return None
    
    async def execute_position_exit(self, position_id: str, reason: str = "manual") -> bool:
        """
        Execute position exit.
        
        Returns:
            True if successful, False otherwise
        """
        position = self.position_manager.get_position(position_id)
        if not position:
            self.logger.error(f"Position {position_id} not found")
            return False
        
        try:
            # Cancel existing exit orders
            cancelled = self.order_manager.cancel_position_orders(position_id)
            for order in cancelled:
                if self.config.is_live_trading:
                    await self._cancel_order_on_exchange(order)
            
            # Create market exit order
            exit_side = 'sell' if position.is_long else 'buy'
            exit_order = Order.create_market_order(
                symbol=position.symbol,
                side=exit_side,
                size=position.current_size,
                reduce_only=True,
                position_id=position_id,
                strategy_name=position.strategy_name,
                reason=f"exit_{reason}"
            )
            
            # Execute exit
            success, error = await self.execute_order(exit_order)
            
            if success:
                position.exit_order_ids.append(exit_order.order_id)
                position.status = PositionStatus.CLOSING
                
                self.logger.success(
                    f"Position exit initiated: {position.symbol} | "
                    f"Size: {position.current_size} | Reason: {reason}"
                )
                return True
            else:
                self.logger.error(f"Failed to exit position: {error}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error executing position exit: {e}", exc_info=True)
            return False
    
    async def trail_stop_loss(self, position_id: str, new_stop_price: Decimal) -> bool:
        """
        Update trailing stop loss for a position.
        
        Returns:
            True if successful, False otherwise
        """
        position = self.position_manager.get_position(position_id)
        if not position:
            return False
        
        try:
            # Find and cancel existing stop loss order
            stop_orders = [o for o in self.order_manager.get_position_orders(position_id)
                          if o.type == OrderType.STOP and o.is_active]
            
            for order in stop_orders:
                # Cancel old stop
                if self.config.is_live_trading:
                    await self._cancel_order_on_exchange(order)
                self.order_manager.update_order_status(order.order_id, OrderStatus.CANCELLED)
            
            # Create new stop loss order
            stop_side = 'sell' if position.is_long else 'buy'
            new_stop_order = Order.create_stop_order(
                symbol=position.symbol,
                side=stop_side,
                size=position.current_size,
                stop_price=new_stop_price,
                position_id=position_id,
                strategy_name=position.strategy_name,
                reason="trailing_stop"
            )
            
            # Execute new stop
            success, _ = await self.execute_order(new_stop_order)
            
            if success:
                position.update_stop_loss(new_stop_price)
                position.exit_order_ids.append(new_stop_order.order_id)
                
                self.logger.info(
                    f"Trailing stop updated: {position.symbol} | "
                    f"New stop: {new_stop_price:.2f}"
                )
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error trailing stop loss: {e}", exc_info=True)
            return False
    
    async def monitor_orders(self):
        """Monitor active orders and update their status."""
        self.monitoring_active = True
        
        while self.monitoring_active:
            try:
                active_orders = self.order_manager.get_active_orders()
                
                for order in active_orders:
                    if order.exchange_order_id and self.config.is_live_trading:
                        # Fetch order status from exchange
                        try:
                            exchange_order = await self.exchange.fetch_order(
                                order.exchange_order_id,
                                order.symbol
                            )
                            
                            # Update order status
                            await self._update_order_from_exchange(order, exchange_order)
                            
                        except Exception as e:
                            self.logger.error(f"Error fetching order {order.client_order_id}: {e}")
                    
                    elif not self.config.is_live_trading:
                        # Simulate order fills in paper trading
                        await self._simulate_order_update(order)
                
                await asyncio.sleep(self.monitor_interval)
                
            except Exception as e:
                self.logger.error(f"Error in order monitoring: {e}", exc_info=True)
                await asyncio.sleep(self.monitor_interval * 2)
    
    async def _submit_order_to_exchange(self, order: Order) -> Dict[str, Any]:
        """Submit order to the exchange."""
        try:
            params = {}
            
            # Add client order ID (Bybit uses orderLinkId)
            params['orderLinkId'] = order.client_order_id
            
            # Handle different order types
            if order.type == OrderType.MARKET:
                response = await self.exchange.create_market_order(
                    symbol=order.symbol,
                    side=order.side.value,
                    amount=float(order.size),
                    params=params
                )
            
            elif order.type == OrderType.LIMIT:
                response = await self.exchange.create_limit_order(
                    symbol=order.symbol,
                    side=order.side.value,
                    amount=float(order.size),
                    price=float(order.price),
                    params=params
                )
            
            elif order.type == OrderType.STOP:
                params['stopPrice'] = float(order.stop_price)
                params['type'] = 'stop_market'
                params['reduceOnly'] = order.reduce_only
                
                response = await self.exchange.create_order(
                    symbol=order.symbol,
                    type='market',
                    side=order.side.value,
                    amount=float(order.size),
                    price=None,
                    params=params
                )
            
            else:
                raise ValueError(f"Unsupported order type: {order.type}")
            
            return response
            
        except Exception as e:
            self.logger.error(f"Exchange order submission failed: {e}")
            raise
    
    async def _cancel_order_on_exchange(self, order: Order) -> bool:
        """Cancel order on the exchange."""
        try:
            if order.exchange_order_id:
                await self.exchange.cancel_order(
                    order.exchange_order_id,
                    order.symbol
                )
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order.client_order_id}: {e}")
            return False
    
    async def _simulate_order_execution(self, order: Order) -> Dict[str, Any]:
        """Simulate order execution for paper trading."""
        # Simulate immediate fill for market orders
        if order.type == OrderType.MARKET:
            await asyncio.sleep(0.1)  # Simulate latency
            return {
                'id': f"SIM-{order.client_order_id}",
                'symbol': order.symbol,
                'side': order.side.value,
                'type': order.type.value,
                'amount': float(order.size),
                'status': 'closed',
                'filled': float(order.size),
                'remaining': 0,
                'average': float(order.price) if order.price else 0,
                'fee': {'cost': float(order.size) * 0.0002, 'currency': 'USDC'}
            }
        else:
            # Limit and stop orders remain open
            return {
                'id': f"SIM-{order.client_order_id}",
                'symbol': order.symbol,
                'side': order.side.value,
                'type': order.type.value,
                'amount': float(order.size),
                'price': float(order.price) if order.price else None,
                'stopPrice': float(order.stop_price) if order.stop_price else None,
                'status': 'open',
                'filled': 0,
                'remaining': float(order.size)
            }
    
    async def _simulate_order_update(self, order: Order):
        """Simulate order updates for paper trading."""
        # Simulate fills based on current market price
        # This is a simplified simulation
        if order.type == OrderType.MARKET and order.status == OrderStatus.SUBMITTED:
            # Simulate market order fill
            order.update_fill(
                filled_size=order.size,
                average_price=order.price or Decimal("50000"),  # Mock price
                fee=order.size * Decimal("0.0002")
            )
            self.order_manager.update_order_status(order.order_id, OrderStatus.FILLED)
    
    async def _update_order_from_exchange(self, order: Order, exchange_order: Dict[str, Any]):
        """Update order from exchange response."""
        try:
            # Map exchange status to our status
            exchange_status = exchange_order.get('status', '').lower()
            
            if exchange_status == 'closed' or exchange_status == 'filled':
                new_status = OrderStatus.FILLED
            elif exchange_status == 'canceled' or exchange_status == 'cancelled':
                new_status = OrderStatus.CANCELLED
            elif exchange_status == 'expired':
                new_status = OrderStatus.EXPIRED
            elif exchange_status == 'rejected':
                new_status = OrderStatus.REJECTED
            elif exchange_status == 'open' and exchange_order.get('filled', 0) > 0:
                new_status = OrderStatus.PARTIAL
            elif exchange_status == 'open':
                new_status = OrderStatus.SUBMITTED
            else:
                return  # Unknown status
            
            # Update fill information
            if exchange_order.get('filled'):
                order.update_fill(
                    filled_size=Decimal(str(exchange_order['filled'])),
                    average_price=Decimal(str(exchange_order.get('average', 0))),
                    fee=Decimal(str(exchange_order.get('fee', {}).get('cost', 0))),
                    fee_currency=exchange_order.get('fee', {}).get('currency', 'USDC')
                )
            
            # Update order status
            if new_status != order.status:
                self.order_manager.update_order_status(order.order_id, new_status, exchange_order)
                
                # Update position if order is filled
                if new_status == OrderStatus.FILLED and order.position_id:
                    await self._update_position_on_fill(order)
                    
        except Exception as e:
            self.logger.error(f"Error updating order from exchange: {e}", exc_info=True)
    
    async def _update_position_on_fill(self, order: Order):
        """Update position when an order is filled."""
        position = self.position_manager.get_position(order.position_id)
        if not position:
            return
        
        try:
            # Handle position entry
            if order.reason == "position_entry":
                position.entry_price = order.average_fill_price
                position.add_fees(order.fee)
                self.logger.trade(
                    action="POSITION_OPENED",
                    symbol=position.symbol,
                    side=position.side.value,
                    amount=float(position.entry_size),
                    price=float(position.entry_price),
                    position_id=position.position_id
                )
            
            # Handle position exit
            elif order.reason.startswith("exit_") or order.reason in ["stop_loss", "take_profit"]:
                pnl = position.reduce_position(order.filled_size, order.average_fill_price)
                position.add_fees(order.fee)
                
                # Update risk manager equity
                self.risk_manager.total_equity += float(pnl)
                
                self.logger.trade(
                    action="POSITION_CLOSED",
                    symbol=position.symbol,
                    side=position.side.value,
                    amount=float(order.filled_size),
                    price=float(order.average_fill_price),
                    pnl=float(pnl),
                    reason=order.reason
                )
                
                # Close position if fully exited
                if position.current_size == 0:
                    self.position_manager.close_position(position.position_id, order.average_fill_price)
                    
        except Exception as e:
            self.logger.error(f"Error updating position on fill: {e}", exc_info=True)
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        avg_slippage = 0.0
        if self.execution_stats['successful_orders'] > 0:
            avg_slippage = float(
                self.execution_stats['total_slippage'] / 
                self.execution_stats['successful_orders']
            )
        
        return {
            'total_orders': self.execution_stats['total_orders'],
            'successful_orders': self.execution_stats['successful_orders'],
            'failed_orders': self.execution_stats['failed_orders'],
            'success_rate': (
                self.execution_stats['successful_orders'] / 
                self.execution_stats['total_orders'] * 100
                if self.execution_stats['total_orders'] > 0 else 0
            ),
            'average_slippage': avg_slippage,
            'average_execution_time': self.execution_stats['avg_execution_time']
        }
    
    def stop_monitoring(self):
        """Stop order monitoring."""
        self.monitoring_active = False
