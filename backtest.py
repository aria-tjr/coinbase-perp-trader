#!/usr/bin/env python3
"""
Comprehensive backtesting framework for Bybit Trading Platform
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional
import json
import pandas as pd
import numpy as np
import ta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_config
from utils.logger import get_logger
from models.market_data import Candle, OrderSide
from models.positions import Position, PositionSide
from models.orders import Order, OrderType, OrderStatus
from core.risk_manager import RiskManager
from strategies.momentum_breakout import MomentumBreakoutStrategy
from strategies.mean_reversion import MeanReversionStrategy


class BacktestEngine:
    """Comprehensive backtesting engine with tick-level accuracy."""
    
    def __init__(self, config, initial_capital: float = 10000):
        self.config = config
        self.logger = get_logger("backtest")
        self.initial_capital = Decimal(str(initial_capital))
        self.current_capital = self.initial_capital
        self.equity_curve = []
        self.trades = []
        self.positions = {}
        self.daily_returns = []
        
        # Initialize components
        self.risk_manager = RiskManager()
        self.momentum_strategy = MomentumBreakoutStrategy(config)
        self.mean_reversion_strategy = MeanReversionStrategy(config)
        
        # Performance tracking
        self.daily_pnl = []
        self.max_drawdown = Decimal(0)
        self.peak_equity = self.initial_capital
        
    async def generate_synthetic_data(self, symbol: str, start_date: datetime, 
                                    end_date: datetime) -> List[Candle]:
        """Generate realistic synthetic market data for backtesting."""
        self.logger.info(f"Generating synthetic data for {symbol} from {start_date} to {end_date}")
        
        candles = []
        current_time = start_date
        current_price = Decimal("65000")  # Starting BTC price
        
        # Market regime parameters
        volatility = 0.02  # 2% daily volatility
        trend_strength = 0.0001
        mean_reversion_factor = 0.05
        
        while current_time < end_date:
            # Generate realistic price movement
            random_change = np.random.normal(0, volatility / 288)  # 5-minute intervals
            trend_component = trend_strength * np.random.choice([-1, 1])
            
            # Add some mean reversion
            if abs(random_change) > 0.01:
                random_change *= (1 - mean_reversion_factor)
            
            price_change = current_price * Decimal(str(random_change + trend_component))
            new_price = current_price + price_change
            
            # Ensure realistic bounds
            if new_price < current_price * Decimal("0.95"):
                new_price = current_price * Decimal("0.95")
            elif new_price > current_price * Decimal("1.05"):
                new_price = current_price * Decimal("1.05")
            
            # Create OHLC data
            high = new_price * Decimal(str(1 + abs(np.random.normal(0, 0.002))))
            low = new_price * Decimal(str(1 - abs(np.random.normal(0, 0.002))))
            volume = Decimal(str(np.random.uniform(10, 100)))
            
            candle = Candle(
                symbol=symbol,
                timestamp=current_time,
                open=current_price,
                high=max(current_price, new_price, high),
                low=min(current_price, new_price, low),
                close=new_price,
                volume=volume,
                timeframe="5m"
            )
            
            candles.append(candle)
            current_price = new_price
            current_time += timedelta(minutes=5)
        
        self.logger.info(f"Generated {len(candles)} candles for backtesting")
        return candles
    
    def add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to DataFrame for backtesting."""
        # RSI
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
        
        # MACD
        macd = ta.trend.MACD(close=df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_histogram'] = macd.macd_diff()
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(close=df['close'], window=20)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_width'] = bb.bollinger_wband()
        
        # Moving Averages
        df['sma_20'] = ta.trend.SMAIndicator(close=df['close'], window=20).sma_indicator()
        df['ema_12'] = ta.trend.EMAIndicator(close=df['close'], window=12).ema_indicator()
        df['ema_26'] = ta.trend.EMAIndicator(close=df['close'], window=26).ema_indicator()
        
        # ATR
        df['atr'] = ta.volatility.AverageTrueRange(
            high=df['high'], low=df['low'], close=df['close'], window=14
        ).average_true_range()
        
        # Volume indicators
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        
        # Price changes
        df['price_change_1'] = df['close'].pct_change(1)
        df['price_change_5'] = df['close'].pct_change(5)
        
        return df
    
    def calculate_position_size(self, signal_strength: float, current_price: Decimal) -> Decimal:
        """Calculate position size using Kelly criterion and risk management."""
        # Basic Kelly sizing with risk limits
        max_risk_per_trade = self.current_capital * Decimal("0.01")  # 1% risk per trade
        
        # Adjust for signal strength
        risk_multiplier = Decimal(str(signal_strength))
        position_risk = max_risk_per_trade * risk_multiplier
        
        # Calculate position size based on 0.6% stop loss
        stop_distance = current_price * Decimal("0.006")
        position_size = position_risk / stop_distance
        
        # Apply leverage
        leverage = Decimal(str(self.config.base_leverage))
        leveraged_size = position_size * leverage
        
        # Ensure we don't exceed available capital
        max_position_value = self.current_capital * Decimal("0.2")  # 20% max per position
        max_size = max_position_value / current_price
        
        return min(leveraged_size, max_size)
    
    def execute_trade(self, signal_type: str, side: str, price: Decimal, 
                     signal_strength: float, timestamp: datetime) -> Optional[str]:
        """Execute a trade based on strategy signal."""
        try:
            # Calculate position size
            size = self.calculate_position_size(signal_strength, price)
            
            if size <= 0:
                return None
            
            # Calculate stop loss and take profit
            if side == "buy":
                stop_loss = price * Decimal("0.994")  # 0.6% stop loss
                take_profit = price * Decimal("1.009")  # 0.9% take profit
                position_side = PositionSide.LONG
            else:
                stop_loss = price * Decimal("1.006")
                take_profit = price * Decimal("0.991")
                position_side = PositionSide.SHORT
            
            # Create position
            position = Position.create_new(
                symbol="BTC/USDT:USDT",
                side=side,
                size=size,
                entry_price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                leverage=float(self.config.base_leverage),
                strategy_name=signal_type,
                signal_strength=signal_strength
            )
            
            # Calculate fees (0.02% taker fee)
            fees = size * price * Decimal("0.0002")
            position.add_fees(fees)
            
            # Update capital
            margin_required = (size * price) / Decimal(str(self.config.base_leverage))
            self.current_capital -= (margin_required + fees)
            
            # Store position
            self.positions[position.position_id] = position
            
            # Log trade
            self.logger.info(f"📈 {signal_type} {side.upper()} | Size: {size:.4f} | "
                           f"Price: ${price} | Fees: ${fees:.2f}")
            
            return position.position_id
            
        except Exception as e:
            self.logger.error(f"Trade execution failed: {e}")
            return None
    
    def check_exits(self, current_price: Decimal, timestamp: datetime) -> List[str]:
        """Check for position exits (stop loss, take profit, or strategy signals)."""
        closed_positions = []
        
        for position_id, position in list(self.positions.items()):
            should_close = False
            exit_reason = ""
            
            # Update position price
            position.update_price(current_price)
            
            # Check stop loss
            if position.is_long and current_price <= position.stop_loss_price:
                should_close = True
                exit_reason = "Stop Loss"
            elif position.is_short and current_price >= position.stop_loss_price:
                should_close = True
                exit_reason = "Stop Loss"
            
            # Check take profit
            elif position.is_long and current_price >= position.take_profit_price:
                should_close = True
                exit_reason = "Take Profit"
            elif position.is_short and current_price <= position.take_profit_price:
                should_close = True
                exit_reason = "Take Profit"
            
            # Time-based exit (max 24 hours)
            elif position.duration_minutes > 1440:
                should_close = True
                exit_reason = "Time Exit"
            
            if should_close:
                # Calculate P&L
                pnl = position.reduce_position(position.current_size, current_price)
                
                # Calculate fees
                exit_fees = position.current_size * current_price * Decimal("0.0002")
                position.add_fees(exit_fees)
                
                # Return margin and add P&L
                margin_returned = (position.entry_size * position.entry_price) / Decimal(str(position.leverage))
                self.current_capital += margin_returned + pnl - exit_fees
                
                # Record trade
                trade_record = {
                    'timestamp': timestamp.isoformat(),
                    'symbol': position.symbol,
                    'side': position.side.value,
                    'entry_price': float(position.entry_price),
                    'exit_price': float(current_price),
                    'size': float(position.entry_size),
                    'pnl': float(pnl),
                    'fees': float(position.fees_paid),
                    'duration_minutes': position.duration_minutes,
                    'strategy': position.strategy_name,
                    'exit_reason': exit_reason,
                    'return_pct': float(position.unrealized_pnl_pct)
                }
                self.trades.append(trade_record)
                
                # Log exit
                self.logger.info(f"📉 {exit_reason} | {position.side.value.upper()} | "
                               f"P&L: ${pnl:.2f} | Return: {position.unrealized_pnl_pct:.2f}%")
                
                closed_positions.append(position_id)
                del self.positions[position_id]
        
        return closed_positions
    
    async def run_backtest(self, symbol: str, start_date: datetime, end_date: datetime):
        """Run the complete backtest."""
        self.logger.info("🚀 Starting comprehensive backtest...")
        self.logger.info(f"Symbol: {symbol}")
        self.logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        self.logger.info(f"Initial Capital: ${self.initial_capital}")
        
        # Generate market data
        candles = await self.generate_synthetic_data(symbol, start_date, end_date)
        
        if not candles:
            self.logger.error("No market data available for backtesting")
            return
        
        # Convert to DataFrame for analysis
        df_data = []
        for candle in candles:
            df_data.append({
                'timestamp': candle.timestamp,
                'open': float(candle.open),
                'high': float(candle.high),
                'low': float(candle.low),
                'close': float(candle.close),
                'volume': float(candle.volume)
            })
        
        df = pd.DataFrame(df_data)
        df.set_index('timestamp', inplace=True)
        
        # Add technical indicators
        features_df = self.add_technical_indicators(df)
        
        # Run backtest
        for i, (timestamp, row) in enumerate(features_df.iterrows()):
            current_price = Decimal(str(row['close']))
            
            # Skip first 50 candles for indicator warmup
            if i < 50:
                continue
            
            # Check exits first
            self.check_exits(current_price, timestamp)
            
            # Generate simple signals based on technical indicators
            # Momentum signal (RSI + MACD)
            momentum_signal = None
            if not pd.isna(row['rsi']) and not pd.isna(row['macd']) and not pd.isna(row['macd_signal']):
                if row['rsi'] < 30 and row['macd'] > row['macd_signal']:
                    momentum_signal = {"action": "buy", "strength": 0.8}
                elif row['rsi'] > 70 and row['macd'] < row['macd_signal']:
                    momentum_signal = {"action": "sell", "strength": 0.8}
            
            # Mean reversion signal (Bollinger Bands)
            mr_signal = None
            if not pd.isna(row['bb_upper']) and not pd.isna(row['bb_lower']):
                if row['close'] <= row['bb_lower']:
                    mr_signal = {"action": "buy", "strength": 0.7}
                elif row['close'] >= row['bb_upper']:
                    mr_signal = {"action": "sell", "strength": 0.7}
            
            # Execute momentum trades
            if momentum_signal and len(self.positions) < 3:  # Max 3 concurrent positions
                self.execute_trade(
                    "Momentum", 
                    momentum_signal["action"], 
                    current_price,
                    momentum_signal["strength"],
                    timestamp
                )
            
            # Execute mean reversion trades
            if mr_signal and len(self.positions) < 3:
                self.execute_trade(
                    "MeanReversion",
                    mr_signal["action"],
                    current_price, 
                    mr_signal["strength"],
                    timestamp
                )
            
            # Update equity curve
            unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
            current_equity = self.current_capital + unrealized_pnl
            
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': float(current_equity),
                'cash': float(self.current_capital),
                'unrealized_pnl': float(unrealized_pnl),
                'num_positions': len(self.positions)
            })
            
            # Track drawdown
            if current_equity > self.peak_equity:
                self.peak_equity = current_equity
            
            drawdown = (self.peak_equity - current_equity) / self.peak_equity
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown
            
            # Daily returns calculation
            if i % 288 == 0:  # Every 24 hours (288 * 5min)
                if len(self.equity_curve) >= 288:
                    prev_equity = Decimal(str(self.equity_curve[-288]['equity']))
                    daily_return = (current_equity - prev_equity) / prev_equity
                    self.daily_returns.append(float(daily_return))
        
        # Close remaining positions
        final_price = Decimal(str(features_df.iloc[-1]['close']))
        for position_id in list(self.positions.keys()):
            self.check_exits(final_price, features_df.index[-1])
        
        self.logger.success("✅ Backtest completed successfully!")
    
    def generate_report(self) -> Dict:
        """Generate comprehensive performance report."""
        if not self.trades:
            return {"error": "No trades executed during backtest"}
        
        # Calculate metrics
        final_equity = self.equity_curve[-1]['equity'] if self.equity_curve else float(self.initial_capital)
        total_return = (final_equity - float(self.initial_capital)) / float(self.initial_capital)
        
        # Trade statistics
        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] <= 0]
        
        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0
        
        # Risk metrics
        if self.daily_returns:
            daily_returns_np = np.array(self.daily_returns)
            sharpe_ratio = np.mean(daily_returns_np) / np.std(daily_returns_np) * np.sqrt(365) if np.std(daily_returns_np) > 0 else 0
            sortino_ratio = np.mean(daily_returns_np) / np.std(daily_returns_np[daily_returns_np < 0]) * np.sqrt(365) if len(daily_returns_np[daily_returns_np < 0]) > 0 else 0
        else:
            sharpe_ratio = 0
            sortino_ratio = 0
        
        report = {
            'summary': {
                'initial_capital': float(self.initial_capital),
                'final_equity': final_equity,
                'total_return': total_return * 100,
                'total_return_absolute': final_equity - float(self.initial_capital),
                'max_drawdown': float(self.max_drawdown) * 100,
                'sharpe_ratio': sharpe_ratio,
                'sortino_ratio': sortino_ratio
            },
            'trade_statistics': {
                'total_trades': len(self.trades),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': win_rate * 100,
                'average_win': avg_win,
                'average_loss': avg_loss,
                'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
            },
            'strategy_breakdown': self._strategy_breakdown(),
            'daily_metrics': {
                'avg_daily_return': np.mean(self.daily_returns) * 100 if self.daily_returns else 0,
                'daily_volatility': np.std(self.daily_returns) * 100 if self.daily_returns else 0,
                'best_day': max(self.daily_returns) * 100 if self.daily_returns else 0,
                'worst_day': min(self.daily_returns) * 100 if self.daily_returns else 0
            }
        }
        
        return report
    
    def _strategy_breakdown(self) -> Dict:
        """Break down performance by strategy."""
        momentum_trades = [t for t in self.trades if t['strategy'] == 'Momentum']
        mr_trades = [t for t in self.trades if t['strategy'] == 'MeanReversion']
        
        breakdown = {}
        
        for strategy_name, trades in [('Momentum', momentum_trades), ('MeanReversion', mr_trades)]:
            if trades:
                winning = [t for t in trades if t['pnl'] > 0]
                total_pnl = sum(t['pnl'] for t in trades)
                
                breakdown[strategy_name] = {
                    'trades': len(trades),
                    'win_rate': len(winning) / len(trades) * 100,
                    'total_pnl': total_pnl,
                    'avg_return': np.mean([t['return_pct'] for t in trades])
                }
        
        return breakdown
    
    def save_results(self, output_dir: str):
        """Save backtest results to files."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save report
        report = self.generate_report()
        with open(output_path / 'backtest_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        # Save trades
        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            trades_df.to_csv(output_path / 'trades.csv', index=False)
        
        # Save equity curve
        if self.equity_curve:
            equity_df = pd.DataFrame(self.equity_curve)
            equity_df.to_csv(output_path / 'equity_curve.csv', index=False)
        
        self.logger.info(f"Results saved to {output_path}")


async def main():
    """Main backtest execution function."""
    parser = argparse.ArgumentParser(description='Run backtest on trading strategies')
    parser.add_argument('--symbol', default='BTC/USDT:USDT', help='Trading symbol')
    parser.add_argument('--start-date', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--initial-capital', type=float, default=10000, help='Initial capital')
    parser.add_argument('--output', default='backtest_results/', help='Output directory')
    
    args = parser.parse_args()
    
    # Parse dates
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    
    # Load config
    config = get_config()
    
    # Create and run backtest
    engine = BacktestEngine(config, args.initial_capital)
    
    try:
        await engine.run_backtest(args.symbol, start_date, end_date)
        
        # Generate and display report
        report = engine.generate_report()
        
        print("\n" + "="*60)
        print("🏆 BYBIT BACKTEST RESULTS SUMMARY")
        print("="*60)
        
        if 'error' in report:
            print(f"❌ {report['error']}")
            return
        
        summary = report['summary']
        print(f"💰 Initial Capital: ${summary['initial_capital']:,.2f}")
        print(f"💰 Final Equity: ${summary['final_equity']:,.2f}")
        print(f"📈 Total Return: {summary['total_return']:.2f}%")
        print(f"💵 Absolute Profit: ${summary['total_return_absolute']:,.2f}")
        print(f"📉 Max Drawdown: {summary['max_drawdown']:.2f}%")
        print(f"⭐ Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
        print(f"🛡️ Sortino Ratio: {summary['sortino_ratio']:.2f}")
        
        print("\n📊 TRADE STATISTICS")
        print("-"*30)
        stats = report['trade_statistics']
        print(f"Total Trades: {stats['total_trades']}")
        print(f"Win Rate: {stats['win_rate']:.1f}%")
        print(f"Average Win: ${stats['average_win']:.2f}")
        print(f"Average Loss: ${stats['average_loss']:.2f}")
        print(f"Profit Factor: {stats['profit_factor']:.2f}")
        
        if 'daily_metrics' in report:
            print("\n📅 DAILY PERFORMANCE")
            print("-"*30)
            daily = report['daily_metrics']
            print(f"Avg Daily Return: {daily['avg_daily_return']:.2f}%")
            print(f"Daily Volatility: {daily['daily_volatility']:.2f}%")
            print(f"Best Day: {daily['best_day']:.2f}%")
            print(f"Worst Day: {daily['worst_day']:.2f}%")
        
        if 'strategy_breakdown' in report:
            print("\n🎯 STRATEGY BREAKDOWN")
            print("-"*30)
            for strategy, metrics in report['strategy_breakdown'].items():
                print(f"{strategy}:")
                print(f"  Trades: {metrics['trades']}")
                print(f"  Win Rate: {metrics['win_rate']:.1f}%")
                print(f"  Total P&L: ${metrics['total_pnl']:,.2f}")
                print(f"  Avg Return: {metrics['avg_return']:.2f}%")
        
        # Save results
        engine.save_results(args.output)
        
        print(f"\n✅ Complete results saved to: {args.output}")
        print("="*60)
        
        # Performance targets check
        target_daily = config.target_daily_return * 100  # 2%
        actual_daily = report.get('daily_metrics', {}).get('avg_daily_return', 0)
        
        if actual_daily >= target_daily:
            print(f"🎉 TARGET ACHIEVED! Daily return {actual_daily:.2f}% >= {target_daily:.2f}%")
        else:
            print(f"⚠️ Target missed. Daily return {actual_daily:.2f}% < {target_daily:.2f}%")
            
    except Exception as e:
        print(f"❌ Backtest failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
