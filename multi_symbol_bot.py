"""
Multi-Symbol Trading Bot

Enhanced version of the main trading bot that supports multiple trading pairs simultaneously.
"""

import asyncio
import signal
import sys
import click
from datetime import datetime
from typing import Dict, List, Optional, Set
from decimal import Decimal

import ccxt.async_support as ccxt

from core import (
    MarketDataCollectorCCXT,
    FeatureEngineering,
    RiskManager,
    ExecutionEngine,
    StrategyCore
)
from infra.monitoring import start_monitoring_server
from infra.alerts import AlertManager
from utils import setup_logging, get_config
from utils.logger import log_performance_summary
from multi_symbol_config import MultiSymbolConfig


class MultiSymbolTradingBot:
    """Multi-symbol trading bot application."""
    
    def __init__(self, mode: str = 'paper', max_symbols: Optional[int] = None):
        """
        Initialize multi-symbol trading bot.
        
        Args:
            mode: Trading mode ('paper' or 'live')
            max_symbols: Maximum number of symbols to trade (None = use all configured)
        """
        self.mode = mode
        self.config = get_config()
        self.logger = setup_logging()
        self.multi_config = MultiSymbolConfig()
        
        # Override config trading mode
        self.config.trading_mode = mode
        
        # Get active symbols (limited by max_symbols if specified)
        self.active_symbols = self.multi_config.get_active_symbols()
        if max_symbols:
            self.active_symbols = self.active_symbols[:max_symbols]
        
        # Components
        self.exchange = None
        self.market_collectors: Dict[str, MarketDataCollectorCCXT] = {}
        self.feature_engines: Dict[str, FeatureEngineering] = {}
        self.risk_manager = None
        self.execution_engine = None
        self.strategy_cores: Dict[str, StrategyCore] = {}
        self.alert_manager = None
        
        # Multi-symbol state
        self.symbol_states: Dict[str, Dict] = {}
        self.position_allocations: Dict[str, Decimal] = {}
        self.last_rebalance = datetime.now()
        
        # Control flags
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        self.active_positions: Set[str] = set()
        
        self.logger.info(f"Multi-symbol trading bot initialized for {len(self.active_symbols)} symbols in {mode} mode")
        self.logger.info(f"Active symbols: {', '.join(self.active_symbols)}")
    
    async def initialize(self):
        """Initialize all trading components for multi-symbol trading."""
        try:
            # Validate configuration
            if not self.multi_config.validate_configuration():
                raise ValueError("Invalid multi-symbol configuration")
            
            # Initialize exchange
            self.logger.info("Initializing Bybit exchange connection...")
            exchange_class = getattr(ccxt, self.config.exchange_id)
            self.exchange = exchange_class(self.config.to_ccxt_config())
            await self.exchange.load_markets()
            
            # Verify all symbols exist
            missing_symbols = []
            for symbol in self.active_symbols:
                if symbol not in self.exchange.markets:
                    missing_symbols.append(symbol)
            
            if missing_symbols:
                self.logger.error(f"Missing symbols on exchange: {missing_symbols}")
                raise ValueError(f"Symbols not found: {missing_symbols}")
            
            # Initialize global risk manager
            self.logger.info("Initializing global risk manager...")
            self.risk_manager = RiskManager(exchange=self.exchange)
            
            # Initialize execution engine
            self.execution_engine = ExecutionEngine(self.exchange, self.risk_manager)
            
            # Initialize components for each symbol
            self.logger.info(f"Initializing components for {len(self.active_symbols)} symbols...")
            
            for symbol in self.active_symbols:
                symbol_config = self.multi_config.get_symbol_config(symbol)
                await self._initialize_symbol_components(symbol, symbol_config)
            
            # Initialize alert manager
            if self.config.telegram_bot_token:
                self.alert_manager = AlertManager(
                    self.config.telegram_bot_token,
                    self.config.telegram_chat_id
                )
                
                symbols_text = "\\n".join([f"• {symbol}: {self.multi_config.get_symbol_config(symbol)['name']}" 
                                         for symbol in self.active_symbols])
                
                await self.alert_manager.send_alert(
                    f"🚀 Multi-Symbol Bybit Bot Started\\n"
                    f"Mode: {self.mode}\\n"
                    f"Symbols ({len(self.active_symbols)}): \\n{symbols_text}\\n"
                    f"Total Allocation: {self.multi_config.get_total_position_allocation():.1%}"
                )
            
            self.logger.success("All multi-symbol components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize multi-symbol bot: {e}", exc_info=True)
            raise
    
    async def _initialize_symbol_components(self, symbol: str, symbol_config: Dict):
        """Initialize trading components for a specific symbol."""
        try:
            self.logger.info(f"Initializing components for {symbol}...")
            
            # Market data collector for this symbol
            market_collector = MarketDataCollectorCCXT([symbol])
            await market_collector.initialize()
            self.market_collectors[symbol] = market_collector
            
            # Feature engineering for this symbol
            feature_engine = FeatureEngineering()
            self.feature_engines[symbol] = feature_engine
            
            # Strategy core for this symbol (with symbol-specific config)
            strategy_core = StrategyCore(
                feature_engine,
                self.risk_manager,
                self.execution_engine
            )
            
            # Configure symbol-specific risk parameters
            strategy_core.configure_symbol_risk(
                symbol=symbol,
                max_position_size_pct=symbol_config.get('position_size_pct', 0.01),
                stop_loss_pct=symbol_config.get('stop_loss', 0.006),
                take_profit_pct=symbol_config.get('take_profit', 0.009),
                base_leverage=symbol_config.get('base_leverage', 5)
            )
            
            self.strategy_cores[symbol] = strategy_core
            
            # Initialize symbol state
            self.symbol_states[symbol] = {
                'last_update': datetime.now(),
                'last_signal': None,
                'position_size': Decimal('0'),
                'unrealized_pnl': Decimal('0'),
                'trade_count': 0,
                'config': symbol_config
            }
            
            # Set up market data callback for this symbol
            market_collector.add_callback('snapshot', 
                                        lambda snapshot, sym=symbol: self._on_symbol_market_update(sym, snapshot))
            
            self.logger.info(f"✅ {symbol} components initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize {symbol}: {e}")
            raise
    
    async def _on_symbol_market_update(self, symbol: str, snapshot):
        """Handle market update for a specific symbol."""
        try:
            # Update symbol state
            self.symbol_states[symbol]['last_update'] = datetime.now()
            
            # Check if we should process this symbol (avoid overloading)
            risk_config = self.multi_config.get_risk_config()
            max_concurrent = risk_config['max_concurrent_positions']
            
            # Skip if too many active positions and this symbol isn't active
            if len(self.active_positions) >= max_concurrent and symbol not in self.active_positions:
                return
            
            # Process through strategy core for this symbol
            strategy_core = self.strategy_cores[symbol]
            await strategy_core.process_market_update(snapshot)
            
            # Update equity from exchange if in live mode (less frequent)
            if self.mode == 'live' and len(self.active_positions) == 0:
                await self.risk_manager.update_equity_from_exchange()
            
            # Check position status
            await self._update_position_status(symbol)
            
            # Rebalance if needed
            await self._check_rebalance()
            
            # Check for multi-symbol risk alerts
            if self.alert_manager:
                await self._check_multi_symbol_alerts()
            
        except Exception as e:
            self.logger.error(f"Error processing {symbol} market update: {e}")
    
    async def _update_position_status(self, symbol: str):
        """Update position status for a symbol."""
        try:
            # Check if we have an open position for this symbol
            positions = await self.exchange.fetch_positions([symbol])
            
            symbol_position = None
            for pos in positions:
                if pos['symbol'] == symbol and abs(pos['contracts']) > 0:
                    symbol_position = pos
                    break
            
            # Update active positions tracking
            if symbol_position:
                self.active_positions.add(symbol)
                self.symbol_states[symbol]['position_size'] = Decimal(str(abs(symbol_position['contracts'])))
                self.symbol_states[symbol]['unrealized_pnl'] = Decimal(str(symbol_position.get('unrealizedPnl', 0)))
            else:
                self.active_positions.discard(symbol)
                self.symbol_states[symbol]['position_size'] = Decimal('0')
                self.symbol_states[symbol]['unrealized_pnl'] = Decimal('0')
                
        except Exception as e:
            self.logger.error(f"Error updating position status for {symbol}: {e}")
    
    async def _check_rebalance(self):
        """Check if portfolio rebalancing is needed."""
        try:
            risk_config = self.multi_config.get_risk_config()
            rebalance_interval = risk_config['rebalance_interval']
            
            # Check if it's time to rebalance
            time_since_rebalance = (datetime.now() - self.last_rebalance).seconds
            if time_since_rebalance < rebalance_interval:
                return
            
            # Calculate total exposure
            total_exposure = sum(
                float(state['position_size']) * float(state.get('current_price', 0))
                for state in self.symbol_states.values()
            )
            
            # Get account balance
            account_risk = self.risk_manager.get_account_risk_snapshot()
            total_equity = float(account_risk.total_equity)
            
            exposure_pct = total_exposure / total_equity if total_equity > 0 else 0
            max_exposure = risk_config['max_total_exposure']
            
            # Log rebalance check
            self.logger.info(f"Rebalance check - Exposure: {exposure_pct:.1%} / {max_exposure:.1%}, "
                           f"Active positions: {len(self.active_positions)}")
            
            # If over-exposed, consider closing least profitable positions
            if exposure_pct > max_exposure:
                await self._reduce_exposure()
            
            self.last_rebalance = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error in rebalance check: {e}")
    
    async def _reduce_exposure(self):
        """Reduce exposure by closing least profitable positions."""
        try:
            self.logger.warning("Over-exposed - considering position reduction")
            
            # Find positions with negative PnL to close first
            positions_by_pnl = []
            for symbol in self.active_positions:
                state = self.symbol_states[symbol]
                pnl = float(state['unrealized_pnl'])
                positions_by_pnl.append((symbol, pnl))
            
            # Sort by PnL (worst first)
            positions_by_pnl.sort(key=lambda x: x[1])
            
            # Close worst performing position
            if positions_by_pnl:
                symbol_to_close = positions_by_pnl[0][0]
                self.logger.warning(f"Closing position in {symbol_to_close} to reduce exposure")
                
                strategy_core = self.strategy_cores[symbol_to_close]
                await strategy_core.close_position(reason="Risk management - reducing exposure")
                
        except Exception as e:
            self.logger.error(f"Error reducing exposure: {e}")
    
    async def _check_multi_symbol_alerts(self):
        """Check for multi-symbol specific alerts."""
        try:
            # Calculate portfolio metrics
            total_pnl = sum(float(state['unrealized_pnl']) for state in self.symbol_states.values())
            active_count = len(self.active_positions)
            
            # Alert on significant portfolio events
            if total_pnl < -100:  # Alert if losing more than $100
                await self.alert_manager.send_alert(
                    f"⚠️ Portfolio Alert\\n"
                    f"Total Unrealized PnL: ${total_pnl:.2f}\\n"
                    f"Active Positions: {active_count}\\n"
                    f"Symbols: {', '.join(self.active_positions)}"
                )
            
        except Exception as e:
            self.logger.error(f"Error checking multi-symbol alerts: {e}")
    
    async def start_trading(self):
        """Start multi-symbol trading."""
        try:
            self.is_running = True
            self.logger.info("🚀 Starting multi-symbol trading...")
            
            # Start market data collection for all symbols
            tasks = []
            for symbol, collector in self.market_collectors.items():
                self.logger.info(f"Starting market data for {symbol}...")
                task = asyncio.create_task(collector.run())
                tasks.append(task)
            
            self.logger.success(f"Multi-symbol trading started for {len(self.active_symbols)} symbols")
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except Exception as e:
            self.logger.error(f"Error in multi-symbol trading: {e}")
            raise
        finally:
            await self.stop_trading()
    
    async def stop_trading(self):
        """Stop multi-symbol trading and cleanup."""
        if not self.is_running:
            return
        
        self.logger.info("Stopping multi-symbol trading...")
        self.is_running = False
        
        try:
            # Stop all market data collectors
            for symbol, collector in self.market_collectors.items():
                await collector.stop()
            
            # Close all open positions if in live mode
            if self.mode == 'live' and self.active_positions:
                self.logger.info(f"Closing {len(self.active_positions)} open positions...")
                for symbol in self.active_positions.copy():
                    strategy_core = self.strategy_cores[symbol]
                    await strategy_core.close_position(reason="Bot shutdown")
            
            # Close exchange connection
            if self.exchange:
                await self.exchange.close()
            
            # Send shutdown alert
            if self.alert_manager:
                await self.alert_manager.send_alert(
                    f"🛑 Multi-Symbol Bot Stopped\\n"
                    f"Final Active Positions: {len(self.active_positions)}\\n"
                    f"Total Symbols Traded: {len(self.active_symbols)}"
                )
            
            self.logger.success("Multi-symbol trading stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping multi-symbol bot: {e}")


async def run_multi_symbol_bot(bot_instance):
    """Run the multi-symbol trading bot."""
    try:
        await bot_instance.initialize()
        await bot_instance.start_trading()
    except KeyboardInterrupt:
        print("\\nBot stopped by user")
    except Exception as e:
        print(f"\\nBot error: {e}")
        raise


# Global bot instance for signal handling
bot_instance = None

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global bot_instance
    if bot_instance:
        print("\\nShutdown signal received...")
        bot_instance.shutdown_event.set()


@click.command()
@click.option('--mode', type=click.Choice(['paper', 'live']), default=None, 
              help='Trading mode (defaults to value from .env file)')
@click.option('--max-symbols', type=int, default=None,
              help='Maximum number of symbols to trade (default: all configured)')
@click.option('--symbols', type=str, default=None,
              help='Comma-separated list of specific symbols to trade')
def main(mode: Optional[str], max_symbols: Optional[int], symbols: Optional[str]):
    """Run the multi-symbol Bybit perpetual futures trading bot."""
    global bot_instance
    
    # Use default mode from config if not specified
    if mode is None:
        config = get_config()
        mode = config.trading_mode
    
    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║          Multi-Symbol Bybit Trading Bot                       ║
║                                                               ║
║  🎯 Multi-Asset High-Frequency Trading System                ║
║  📊 Symbols: Multiple pairs simultaneously                   ║
║  💼 Mode: {mode:<25}                         ║
║  🚀 Target: ≥2% Daily Returns per Symbol                     ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    if mode == 'live':
        response = input("\\n⚠️  WARNING: You are about to start LIVE MULTI-SYMBOL TRADING. "
                        "This involves REAL MONEY and HIGHER RISK.\\n"
                        "Type 'YES' to continue: ")
        if response != 'YES':
            print("Live trading cancelled.")
            return
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run bot
    bot_instance = MultiSymbolTradingBot(mode, max_symbols)
    
    # Override symbols if specified
    if symbols:
        custom_symbols = [s.strip() for s in symbols.split(',')]
        # Validate symbols are in configuration
        valid_symbols = []
        for symbol in custom_symbols:
            if symbol in MultiSymbolConfig.TRADING_PAIRS:
                valid_symbols.append(symbol)
            else:
                print(f"⚠️ Warning: {symbol} not in configuration, skipping")
        
        if valid_symbols:
            bot_instance.active_symbols = valid_symbols
            print(f"Using custom symbols: {', '.join(valid_symbols)}")
        else:
            print("No valid symbols specified, using default configuration")
    
    try:
        # Run async main
        asyncio.run(run_multi_symbol_bot(bot_instance))
    except KeyboardInterrupt:
        print("\\nBot stopped by user")
    except Exception as e:
        print(f"\\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
