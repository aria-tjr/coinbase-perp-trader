"""Main trading application for Bybit perpetual futures."""

import asyncio
import signal
import sys
import click
from datetime import datetime
from typing import Optional

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


class TradingBot:
    """Main trading bot application."""
    
    def __init__(self, symbol: str, mode: str = 'paper'):
        """
        Initialize trading bot.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            mode: Trading mode ('paper' or 'live')
        """
        self.symbol = symbol
        self.mode = mode
        self.config = get_config()
        self.logger = setup_logging()
        
        # Override config trading mode
        self.config.trading_mode = mode
        
        # Components
        self.exchange = None
        self.market_collector = None
        self.feature_engine = None
        self.risk_manager = None
        self.execution_engine = None
        self.strategy_core = None
        self.alert_manager = None
        
        # Control flags
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        self.logger.info(f"Trading bot initialized for {symbol} in {mode} mode")
    
    async def initialize(self):
        """Initialize all trading components."""
        try:
            # Initialize exchange
            self.logger.info("Initializing Bybit exchange connection...")
            exchange_class = getattr(ccxt, self.config.exchange_id)
            self.exchange = exchange_class(self.config.to_ccxt_config())
            await self.exchange.load_markets()
            
            # Normalize symbol formatting (insert slash for exchange markets)
            if self.symbol not in self.exchange.markets:
                if '/' not in self.symbol and len(self.symbol) > 4:
                    base = self.symbol[:-4]
                    quote = self.symbol[-4:]
                    alt_symbol = f"{base}/{quote}"
                    if alt_symbol in self.exchange.markets:
                        self.logger.info(f"Using market symbol {alt_symbol}")
                        self.symbol = alt_symbol
            # Verify symbol exists
            if self.symbol not in self.exchange.markets:
                raise ValueError(f"Symbol {self.symbol} not found on {self.config.exchange_id}")
            
            # Initialize components
            self.logger.info("Initializing trading components...")
            
            # Market data collector
            self.market_collector = MarketDataCollectorCCXT([self.symbol])
            await self.market_collector.initialize()
            
            # Feature engineering
            self.feature_engine = FeatureEngineering()
            
            # Risk manager
            self.risk_manager = RiskManager(exchange=self.exchange)
            
            # Execution engine
            self.execution_engine = ExecutionEngine(self.exchange, self.risk_manager)
            
            # Strategy core
            self.strategy_core = StrategyCore(
                self.feature_engine,
                self.risk_manager,
                self.execution_engine
            )
            
            # Alert manager
            if self.config.telegram_bot_token:
                self.alert_manager = AlertManager(
                    self.config.telegram_bot_token,
                    self.config.telegram_chat_id
                )
                await self.alert_manager.send_alert(
                    f"🚀 Bybit Trading bot started\n"
                    f"Symbol: {self.symbol}\n"
                    f"Mode: {self.mode}\n"
                    f"Leverage: {self.risk_manager.current_leverage}x"
                )
            
            # Set up market data callbacks
            self.market_collector.add_callback('snapshot', self._on_market_snapshot)
            
            self.logger.success("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}", exc_info=True)
            raise
    
    async def _on_market_snapshot(self, snapshot):
        """Handle market snapshot updates."""
        try:
            # Process through strategy core
            await self.strategy_core.process_market_update(snapshot)
            
            # Update equity from exchange if in live mode
            if self.mode == 'live':
                await self.risk_manager.update_equity_from_exchange()
            
            # Update risk metrics
            account_risk = self.risk_manager.get_account_risk_snapshot()
            
            # Get strategy status to ensure market regime is updated
            strategy_status = self.strategy_core.get_strategy_status()
            
            # Debug log market regime and risk level to verify they're properly populated
            risk_level = account_risk.risk_level.value if hasattr(account_risk.risk_level, 'value') else str(account_risk.risk_level)
            market_regime = strategy_status.get('current_regime', 'unknown')
            self.logger.debug(f"Current risk level: {risk_level}, Market regime: {market_regime}")
            
            # Check for alerts
            if self.alert_manager:
                await self._check_risk_alerts(account_risk)
            
        except Exception as e:
            self.logger.error(f"Error processing market snapshot: {e}", exc_info=True)
    
    async def _check_risk_alerts(self, account_risk):
        """Check and send risk-based alerts."""
        # Daily P&L alert
        if abs(account_risk.daily_pnl_pct) > 0.01:  # 1% change
            emoji = "📈" if account_risk.daily_pnl_pct > 0 else "📉"
            await self.alert_manager.send_alert(
                f"{emoji} Daily P&L: {account_risk.daily_pnl_pct:.2%}\n"
                f"Equity: ${account_risk.total_equity:,.2f}"
            )
        
        # Risk level alert
        if account_risk.risk_level.value in ['high', 'critical', 'halt']:
            await self.alert_manager.send_alert(
                f"⚠️ Risk Level: {account_risk.risk_level.value.upper()}\n"
                f"Drawdown: {account_risk.current_drawdown:.2%}\n"
                f"Reasons: {', '.join(account_risk.halt_reasons)}"
            )
    
    async def run(self):
        """Run the main trading loop."""
        self.is_running = True
        
        try:
            # Start market data collection
            market_task = asyncio.create_task(self.market_collector.run())
            
            # Start order monitoring
            order_monitor_task = asyncio.create_task(
                self.execution_engine.monitor_orders()
            )
            
            # Start monitoring server
            monitoring_task = asyncio.create_task(
                start_monitoring_server(self)
            )
            
            # Performance reporting loop
            performance_task = asyncio.create_task(self._performance_loop())
            
            # Wait for shutdown
            await self.shutdown_event.wait()
            
            # Stop components
            self.logger.info("Shutting down trading bot...")
            self.market_collector.stop()
            self.execution_engine.stop_monitoring()
            
            # Cancel tasks
            for task in [market_task, order_monitor_task, monitoring_task, performance_task]:
                task.cancel()
            
            await asyncio.gather(*[market_task, order_monitor_task, monitoring_task, performance_task], 
                               return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            self.is_running = False
            await self.cleanup()
    
    async def _performance_loop(self):
        """Periodically log performance metrics."""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                # Get performance metrics
                account_risk = self.risk_manager.get_account_risk_snapshot()
                strategy_status = self.strategy_core.get_strategy_status()
                execution_stats = self.execution_engine.get_execution_stats()
                
                # Ensure risk level and market regime are properly extracted
                risk_level = account_risk.risk_level.value if hasattr(account_risk.risk_level, 'value') else str(account_risk.risk_level)
                market_regime = strategy_status.get('current_regime', 'unknown')
                
                # Log summary
                metrics = {
                    'Daily P&L': account_risk.daily_pnl_pct,
                    'Total Equity': account_risk.total_equity,
                    'Current Leverage': account_risk.current_leverage,
                    'Sharpe Ratio': account_risk.sharpe_ratio_24h,
                    'Open Positions': account_risk.position_count,
                    'Risk Level': risk_level,
                    'Market Regime': market_regime,
                    'Order Success Rate': execution_stats['success_rate']
                }
                
                log_performance_summary(self.logger, metrics)
                
            except Exception as e:
                self.logger.error(f"Error in performance loop: {e}", exc_info=True)
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            # Close all positions if in live mode and shutting down
            if self.mode == 'live' and self.execution_engine:
                open_positions = self.execution_engine.position_manager.get_open_positions()
                for position in open_positions:
                    await self.execution_engine.execute_position_exit(
                        position.position_id, 
                        "system_shutdown"
                    )
            
            # Close exchange connection
            if self.exchange:
                await self.exchange.close()
            
            # Send shutdown alert
            if self.alert_manager:
                await self.alert_manager.send_alert(
                    f"🛑 Trading bot stopped\n"
                    f"Final equity: ${self.risk_manager.total_equity:,.2f}"
                )
            
            self.logger.info("Cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def shutdown(self):
        """Signal shutdown to the bot."""
        self.logger.info("Shutdown signal received")
        self.shutdown_event.set()


# Global bot instance for signal handling
bot_instance: Optional[TradingBot] = None


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print("\nShutdown signal received...")
    if bot_instance:
        bot_instance.shutdown()


@click.command()
@click.option('--symbol', default='BTCUSDT', help='Trading symbol')
@click.option('--mode', type=click.Choice(['paper', 'live']), default=None, 
              help='Trading mode (defaults to value from .env file)')
def main(symbol: str, mode: Optional[str]):
    """Run the Bybit perpetual futures trading bot."""
    global bot_instance
    
    # Use default mode from config if not specified
    if mode is None:
        config = get_config()
        mode = config.trading_mode
    
    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║             Bybit Perpetual Trading Bot                       ║
║                                                               ║
║  ⚡ Aggressive High-Frequency Trading System                  ║
║  🎯 Target: ≥2% Daily Returns                                 ║
║  📊 Symbol: {symbol:<25}                         ║
║  💼 Mode: {mode:<27}                            ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    if mode == 'live':
        response = input("\n⚠️  WARNING: You are about to start LIVE TRADING on Bybit. "
                        "This involves REAL MONEY and RISK.\n"
                        "Type 'YES' to continue: ")
        if response != 'YES':
            print("Live trading cancelled.")
            return
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run bot
    bot_instance = TradingBot(symbol, mode)
    
    try:
        # Run async main
        asyncio.run(run_bot(bot_instance))
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


async def run_bot(bot: TradingBot):
    """Async wrapper to run the bot."""
    try:
        await bot.initialize()
        await bot.run()
    except Exception as e:
        bot.logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
