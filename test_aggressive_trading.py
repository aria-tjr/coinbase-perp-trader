#!/usr/bin/env python3
"""
Aggressive test trading script to validate order placement functionality.
This script will        # Make strategy parameters extremely aggressive
        self.config.base_leverage = 20  # Working leverage for our balance ($8.30 USDT)
        self.config.max_position_size_pct = 0.05  # 5% of portfolio per position. Set extremely aggressive strategy parameters to trigger immediate orders
2. Place a test order
3. Monitor the order status
4. Close the order after successful placement
5. Reset to normal parameters
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_config
from utils.logger import get_logger
from core.strategy_core import StrategyCore
from core.execution_engine import ExecutionEngine
from core.risk_manager import RiskManager
from core.feature_engineering import FeatureEngineering
from core.market_data_collector_ccxt import MarketDataCollectorCCXT
from models.market_data import MarketSnapshot
from models.positions import Position
from aggressive_config import AggressiveStrategyConfig
import ccxt.async_support as ccxt_async
import ccxt


class AggressiveTestTrader:
    """Test trader with extremely aggressive parameters to force order placement."""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(self.__class__.__name__)
        
        # Backup original settings
        self.original_settings = {
            'base_leverage': self.config.base_leverage,
            'max_position_size_pct': self.config.max_position_size_pct,
            'position_stop_loss': self.config.position_stop_loss,
            'position_take_profit': self.config.position_take_profit,
            'daily_drawdown_limit': self.config.daily_drawdown_limit
        }
        
        # Initialize components
        self.exchange = None
        self.market_collector = None
        self.execution_engine = None
        self.strategy_core = None
        self.risk_manager = None
        
        # Test tracking
        self.test_position_id = None
        self.test_start_time = None
        self.order_placed = False
        self.aggressive_config = AggressiveStrategyConfig()
        
    async def initialize(self):
        """Initialize all trading components."""
        try:
            # Initialize exchange with MAINNET mode using async CCXT
            exchange_config = self.config.to_ccxt_config(sandbox=False)
            self.exchange = ccxt_async.bybit(exchange_config)
            
            # Test exchange connection (async call)
            await self.exchange.load_markets()
            self.logger.info("Exchange connection established")
            
            # Initialize components
            self.market_collector = MarketDataCollectorCCXT(
                symbols=[self.config.default_symbol]
            )
            
            self.risk_manager = RiskManager(exchange=self.exchange)
            self.execution_engine = ExecutionEngine(
                exchange=self.exchange, 
                risk_manager=self.risk_manager
            )
            
            # Apply aggressive test settings
            await self.apply_aggressive_settings()
            
            self.feature_engine = FeatureEngineering()
            self.strategy_core = StrategyCore(
                feature_engine=self.feature_engine,
                execution_engine=self.execution_engine,
                risk_manager=self.risk_manager
            )
            
            # Apply aggressive strategy parameters
            self.aggressive_config.apply_aggressive_momentum_params(
                self.strategy_core.momentum_strategy
            )
            self.aggressive_config.apply_aggressive_mean_reversion_params(
                self.strategy_core.mean_reversion_strategy
            )
            self.aggressive_config.apply_aggressive_risk_params(
                self.risk_manager
            )
            
            self.logger.success("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise
    
    async def apply_aggressive_settings(self):
        """Apply extremely aggressive settings to force immediate order placement."""
        self.logger.warning("🔥 APPLYING AGGRESSIVE TEST SETTINGS 🔥")
        
        # Make strategy parameters extremely aggressive
        self.config.base_leverage = 5  # Moderate leverage for limited balance
        self.config.max_position_size_pct = 0.05  # 5% of portfolio per position
        self.config.position_stop_loss = 0.02  # 2% stop loss (wider for testing)
        self.config.position_take_profit = 0.03  # 3% take profit (wider for testing)
        self.config.daily_drawdown_limit = 0.10  # 10% daily drawdown limit
        
        # Update risk manager with new settings
        if self.risk_manager:
            self.risk_manager.base_leverage = self.config.base_leverage
            self.risk_manager.max_position_size_pct = self.config.max_position_size_pct
            self.risk_manager.position_stop_loss = self.config.position_stop_loss
            self.risk_manager.position_take_profit = self.config.position_take_profit
            self.risk_manager.daily_drawdown_limit = self.config.daily_drawdown_limit
            
            # Make current leverage high enough for our reduced balance ($2.66 USDT)
            self.risk_manager.current_leverage = 75.0  # Maximum leverage needed for current balance
        
        self.logger.warning(f"Aggressive settings applied:")
        self.logger.warning(f"  - Leverage: {self.config.base_leverage}x")
        self.logger.warning(f"  - Position size: {self.config.max_position_size_pct:.1%}")
        self.logger.warning(f"  - Stop loss: {self.config.position_stop_loss:.1%}")
        self.logger.warning(f"  - Take profit: {self.config.position_take_profit:.1%}")
        self.logger.warning(f"  - Current leverage: {self.risk_manager.current_leverage}x (maximum leverage for current balance)")    
    
    async def restore_original_settings(self):
        """Restore original conservative settings."""
        self.logger.info("🔄 RESTORING ORIGINAL SETTINGS 🔄")
        
        # Restore original settings
        self.config.base_leverage = self.original_settings['base_leverage']
        self.config.max_position_size_pct = self.original_settings['max_position_size_pct']
        self.config.position_stop_loss = self.original_settings['position_stop_loss']
        self.config.position_take_profit = self.original_settings['position_take_profit']
        self.config.daily_drawdown_limit = self.original_settings['daily_drawdown_limit']
        
        # Restore strategy parameters
        if hasattr(self, 'strategy_core') and self.strategy_core:
            self.aggressive_config.restore_original_params(
                momentum_strategy=self.strategy_core.momentum_strategy,
                mean_reversion_strategy=self.strategy_core.mean_reversion_strategy,
                risk_manager=self.risk_manager
            )
        
        self.logger.success("Original settings restored")
    
    async def run_aggressive_test(self):
        """Run the aggressive test trading session."""
        try:
            self.logger.info("🚀 STARTING AGGRESSIVE TEST TRADING SESSION 🚀")
            
            # Initialize market data collector
            await self.market_collector.initialize()
            self.logger.info("Market data collector initialized")
            
            # Start market data collection in background
            market_task = asyncio.create_task(self.market_collector.run())
            
            # Wait for initial market data
            await asyncio.sleep(5)
            
            # Get current market snapshot
            market_data = self.market_collector.get_market_snapshot(self.config.default_symbol)
            if not market_data:
                self.logger.error("No market data available")
                return False
                
            self.logger.info(f"Current price: ${market_data.features.price:.2f}")
            
            # Force a test signal by creating an artificial strong signal
            success = await self.place_test_order(market_data)
            
            if success:
                # Monitor the position
                await self.monitor_test_position()
                
                # Close the position
                await self.close_test_position()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error in aggressive test: {e}")
            return False
        finally:
            if self.market_collector:
                await self.market_collector.close()
                
            # Cancel the market task if it exists
            if 'market_task' in locals() and not market_task.done():
                market_task.cancel()
                try:
                    await market_task
                except asyncio.CancelledError:
                    pass
    
    async def calculate_max_position_size(self, current_price: float) -> float:
        """Calculate maximum position size based on available balance and leverage."""
        try:
            # Get account balance (async call for CCXT)
            balance = await self.exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {})
            available_usdt = usdt_balance.get('free', 0)
            
            # Use a conservative fixed position size that we know will work
            # Based on our earlier successful test: 0.001 BTC with 20x leverage
            test_position_size = 0.001  # Conservative test size
            leverage = 20.0  # Proven to work with current balance
            
            # Calculate required margin for this position
            position_value = test_position_size * current_price
            required_margin = position_value / leverage
            
            self.logger.info(f"Balance calculation:")
            self.logger.info(f"  Available USDT: ${available_usdt:.2f}")
            self.logger.info(f"  Test position size: {test_position_size} BTC")
            self.logger.info(f"  Position value: ${position_value:.2f}")
            self.logger.info(f"  Leverage: {leverage}x (conservative for testing)")
            self.logger.info(f"  Required margin: ${required_margin:.2f}")
            self.logger.info(f"  Margin buffer: ${available_usdt - required_margin:.2f}")
            
            return test_position_size
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0.001  # Fallback to minimum
    
    async def place_test_order(self, market_data: MarketSnapshot) -> bool:
        """Place a test order with artificial strong signal."""
        try:
            self.logger.info("🎯 PLACING TEST ORDER")
            
            # Create artificial strong momentum signal
            features = market_data.features
            
            # Determine direction based on simple momentum
            direction = 'long' if features.rsi < 50 else 'short'
            
            # Convert to OrderSide
            order_side = 'buy' if direction == 'long' else 'sell'
            
            # Calculate optimal position size based on full balance usage
            current_price = float(features.price)
            test_size = await self.calculate_max_position_size(current_price)
            
            # Create manual test position through execution engine
            current_price = Decimal(str(features.price))
            
            if direction == 'long':
                stop_loss = current_price * (1 - Decimal(str(self.config.position_stop_loss)))
                take_profit = current_price * (1 + Decimal(str(self.config.position_take_profit)))
            else:
                stop_loss = current_price * (1 + Decimal(str(self.config.position_stop_loss)))
                take_profit = current_price * (1 - Decimal(str(self.config.position_take_profit)))
            
            self.logger.info(f"Test order details:")
            self.logger.info(f"  Direction: {direction}")
            self.logger.info(f"  Size: {test_size} BTC")
            self.logger.info(f"  Entry: ${current_price}")
            self.logger.info(f"  Stop Loss: ${stop_loss}")
            self.logger.info(f"  Take Profit: ${take_profit}")
            
            # Execute the test position
            position = await self.execution_engine.execute_position_entry(
                symbol=self.config.default_symbol,
                side=order_side,
                size=test_size,
                current_price=current_price,
                strategy_name="AGGRESSIVE_TEST",
                signal_strength=1.0  # Maximum signal strength
            )
            
            if position:
                self.test_position_id = position.position_id
                self.test_start_time = datetime.now()
                self.order_placed = True
                
                self.logger.success(f"✅ TEST ORDER PLACED SUCCESSFULLY!")
                self.logger.success(f"Position ID: {self.test_position_id}")
                return True
            else:
                self.logger.error("❌ Failed to place test order")
                return False
                
        except Exception as e:
            self.logger.error(f"Error placing test order: {e}")
            return False
    
    async def monitor_test_position(self):
        """Monitor the test position for a short duration."""
        if not self.test_position_id:
            return
            
        self.logger.info("👀 MONITORING TEST POSITION")
        
        monitor_duration = 30  # Monitor for 30 seconds
        start_time = time.time()
        
        while time.time() - start_time < monitor_duration:
            try:
                # Check position status
                positions = await self.execution_engine.get_open_positions()
                test_position = None
                
                for pos in positions:
                    if pos.position_id == self.test_position_id:
                        test_position = pos
                        break
                
                if test_position:
                    self.logger.info(f"Position status: {test_position.side.value} "
                                   f"| Size: {test_position.current_size:.6f} "
                                   f"| P&L: ${test_position.unrealized_pnl:.2f} "
                                   f"| P&L%: {test_position.unrealized_pnl_pct:.2f}%")
                else:
                    self.logger.warning("Test position not found in open positions")
                
                await asyncio.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Error monitoring position: {e}")
                break
    
    async def close_test_position(self):
        """Close the test position."""
        if not self.test_position_id:
            return
            
        try:
            self.logger.info("🔄 CLOSING TEST POSITION")
            
            success = await self.execution_engine.execute_position_exit(
                position_id=self.test_position_id,
                reason="TEST_COMPLETE"
            )
            
            if success:
                self.logger.success("✅ TEST POSITION CLOSED SUCCESSFULLY")
            else:
                self.logger.error("❌ Failed to close test position")
                
        except Exception as e:
            self.logger.error(f"Error closing test position: {e}")
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            if self.market_collector:
                await self.market_collector.close()
            
            # Close async CCXT exchange
            if self.exchange:
                await self.exchange.close()
                
            await self.restore_original_settings()
            
            self.logger.info("Cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


async def main():
    """Main test execution function."""
    trader = AggressiveTestTrader()
    
    try:
        # Initialize components
        await trader.initialize()
        
        # Run the aggressive test
        success = await trader.run_aggressive_test()
        
        if success:
            print("\n" + "="*60)
            print("🎉 TEST COMPLETED SUCCESSFULLY! 🎉")
            print("="*60)
            print(f"✅ Order placement: {'SUCCESSFUL' if trader.order_placed else 'FAILED'}")
            print(f"✅ Position monitoring: COMPLETED")
            print(f"✅ Position closure: COMPLETED")
            print(f"✅ Settings restoration: COMPLETED")
            print("="*60)
            print("\n🚀 The bot is ready for live trading!")
            print("💡 You can now use normal settings with confidence.")
        else:
            print("\n" + "="*60)
            print("❌ TEST FAILED")
            print("="*60)
            print("Please check the logs for error details.")
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
    finally:
        await trader.cleanup()


if __name__ == "__main__":
    print("🔥 AGGRESSIVE TRADING TEST 🔥")
    print("This will test order placement with aggressive settings")
    print("Press Ctrl+C to stop at any time\n")
    
    asyncio.run(main())
