#!/usr/bin/env python3
"""
Ultra-aggressive backtesting framework for high-frequency trading
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


class AggressiveBacktestEngine:
    """Ultra-aggressive backtesting engine for high-frequency trading."""
    
    def __init__(self, config, initial_capital: float = 10000):
        self.config = config
        self.logger = get_logger("aggressive_backtest")
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
        
        # Market regime parameters - increased volatility for more opportunities
        volatility = 0.025  # 2.5% daily volatility (increased)
        trend_strength = 0.0002
        mean_reversion_factor = 0.08
        
        while current_time < end_date:
            # Generate realistic price movement with more volatility
            random_change = np.random.normal(0, volatility / 288)  # 5-minute intervals
            trend_component = trend_strength * np.random.choice([-1, 1])
            
            # Add volatility clustering
            if abs(random_change) > 0.015:
                random_change *= 1.2  # Amplify large moves
            
            # Add some mean reversion
            if abs(random_change) > 0.01:
                random_change *= (1 - mean_reversion_factor)
            
            price_change = current_price * Decimal(str(random_change + trend_component))
            new_price = current_price + price_change
            
            # Allow larger price swings
            if new_price < current_price * Decimal("0.92"):
                new_price = current_price * Decimal("0.92")
            elif new_price > current_price * Decimal("1.08"):
                new_price = current_price * Decimal("1.08")
            
            # Create OHLC data with higher wicks for more signals
            high = new_price * Decimal(str(1 + abs(np.random.normal(0, 0.003))))
            low = new_price * Decimal(str(1 - abs(np.random.normal(0, 0.003))))
            volume = Decimal(str(np.random.uniform(50, 500)))  # Higher volume
            
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
        
        self.logger.info(f"Generated {len(candles)} candles for aggressive backtesting")
        return candles
    
    def add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to DataFrame for backtesting."""
        # RSI with shorter period for more signals
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=9).rsi()
        
        # MACD with faster settings
        macd = ta.trend.MACD(close=df['close'], window_slow=20, window_fast=9, window_sign=6)
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_histogram'] = macd.macd_diff()
        
        # Bollinger Bands with tighter bands
        bb = ta.volatility.BollingerBands(close=df['close'], window=15, window_dev=1.5)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_width'] = bb.bollinger_wband()
        
        # Moving Averages
        df['sma_10'] = ta.trend.SMAIndicator(close=df['close'], window=10).sma_indicator()
        df['ema_8'] = ta.trend.EMAIndicator(close=df['close'], window=8).ema_indicator()
        df['ema_21'] = ta.trend.EMAIndicator(close=df['close'], window=21).ema_indicator()
        
        # ATR for dynamic stops
        df['atr'] = ta.volatility.AverageTrueRange(
            high=df['high'], low=df['low'], close=df['close'], window=10
        ).average_true_range()
        
        # Volume indicators
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # Price changes
        df['price_change_1'] = df['close'].pct_change(1)
        df['price_change_3'] = df['close'].pct_change(3)
        df['price_change_5'] = df['close'].pct_change(5)
        
        # Momentum indicators
        df['momentum'] = df['close'] - df['close'].shift(10)
        
        return df
    
    def calculate_aggressive_position_size(self, signal_strength: float, current_price: Decimal) -> Decimal:
        """Calculate aggressive position size with higher risk."""
        # Aggressive risk sizing - 3-5% risk per trade based on signal strength
        base_risk = Decimal("0.03")  # 3% base risk
        max_risk = Decimal("0.05")   # 5% max risk
        
        # Scale risk based on signal strength
        risk_multiplier = Decimal(str(signal_strength))
        risk_per_trade = base_risk + (max_risk - base_risk) * risk_multiplier
        position_risk = self.current_capital * risk_per_trade
        
        # Calculate position size based on dynamic stop loss
        stop_distance = current_price * Decimal("0.008")  # 0.8% stop (wider)
        position_size = position_risk / stop_distance
        
        # Apply aggressive leverage (10-25x based on signal)
        base_leverage = Decimal("10")
        max_leverage = Decimal("25")
        leverage = base_leverage + (max_leverage - base_leverage) * risk_multiplier
        leveraged_size = position_size * leverage
        
        # Allow up to 40% of capital per position for strong signals
        max_position_value = self.current_capital * (Decimal("0.2") + Decimal("0.2") * risk_multiplier)
        max_size = max_position_value / current_price
        
        return min(leveraged_size, max_size)
    
    def execute_aggressive_trade(self, signal_type: str, side: str, price: Decimal, 
                     signal_strength: float, timestamp: datetime) -> Optional[str]:
        """Execute a trade with aggressive parameters."""
        try:
            # Calculate aggressive position size
            size = self.calculate_aggressive_position_size(signal_strength, price)
            
            if size <= 0:
                return None
            
            # Dynamic stop loss and take profit based on ATR
            atr_multiplier = Decimal("1.5") - Decimal(str(signal_strength * 0.5))  # 1.0-1.5x ATR
            
            if side == "buy":
                stop_loss = price * Decimal("0.992")    # 0.8% stop loss
                take_profit = price * Decimal("1.015")  # 1.5% take profit (wider)
                position_side = PositionSide.LONG
            else:
                stop_loss = price * Decimal("1.008")
                take_profit = price * Decimal("0.985")
                position_side = PositionSide.SHORT
            
            # Determine leverage for this position
            leverage = float(10 + signal_strength * 15)  # 10-25x
            
            # Create position
            position = Position.create_new(
                symbol="BTC/USDT:USDT",
                side=side,
                size=size,
                entry_price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                leverage=leverage,
                strategy_name=signal_type,
                signal_strength=signal_strength
            )
            
            # Calculate fees (0.02% taker fee)
            fees = size * price * Decimal("0.0002")
            position.add_fees(fees)
            
            # Update capital
            margin_required = (size * price) / Decimal(str(leverage))
            self.current_capital -= (margin_required + fees)
            
            # Store position
            self.positions[position.position_id] = position
            
            # Log trade
            self.logger.info(f"⚡ {signal_type} {side.upper()} | Size: {size:.4f} | "
                           f"Price: ${price} | Leverage: {leverage:.1f}x | Signal: {signal_strength:.2f}")
            
            return position.position_id
            
        except Exception as e:
            self.logger.error(f"Aggressive trade execution failed: {e}")
            return None
    
    def check_aggressive_exits(self, current_price: Decimal, timestamp: datetime, 
                               df_row: pd.Series) -> List[str]:
        """Check for position exits with trailing stops and dynamic targets."""
        closed_positions = []
        
        for position_id, position in list(self.positions.items()):
            should_close = False
            exit_reason = ""
            
            # Update position price
            position.update_price(current_price)
            
            # Implement trailing stop loss for profitable positions
            if position.unrealized_pnl_pct > 0.5:  # If profitable by 0.5%+
                if position.is_long:
                    trailing_stop = current_price * Decimal("0.995")  # 0.5% trailing
                    if trailing_stop > position.stop_loss_price:
                        position.stop_loss_price = trailing_stop
                else:
                    trailing_stop = current_price * Decimal("1.005")
                    if trailing_stop < position.stop_loss_price:
                        position.stop_loss_price = trailing_stop
            
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
            
            # Time-based exit (max 12 hours for scalping)
            elif position.duration_minutes > 720:
                should_close = True
                exit_reason = "Time Exit"
            
            # Signal-based exit (exit on opposite signal)
            if not should_close and not pd.isna(df_row['rsi']):
                if position.is_long and df_row['rsi'] > 75:
                    should_close = True
                    exit_reason = "Signal Exit"
                elif position.is_short and df_row['rsi'] < 25:
                    should_close = True
                    exit_reason = "Signal Exit"
            
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
                    'return_pct': float(position.unrealized_pnl_pct),
                    'leverage': position.leverage
                }
                self.trades.append(trade_record)
                
                # Log exit
                emoji = "💰" if pnl > 0 else "💸"
                self.logger.info(f"{emoji} {exit_reason} | {position.side.value.upper()} | "
                               f"P&L: ${pnl:.2f} | Return: {position.unrealized_pnl_pct:.2f}%")
                
                closed_positions.append(position_id)
                del self.positions[position_id]
        
        return closed_positions
    
    async def run_aggressive_backtest(self, symbol: str, start_date: datetime, end_date: datetime):
        """Run the ultra-aggressive backtest."""
        self.logger.info("⚡ Starting ULTRA-AGGRESSIVE backtest...")
        self.logger.info(f"Symbol: {symbol}")
        self.logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        self.logger.info(f"Initial Capital: ${self.initial_capital}")
        self.logger.info("Strategy: High-frequency scalping with 10-25x leverage")
        
        # Generate market data with higher volatility
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
            
            # Skip first 30 candles for indicator warmup
            if i < 30:
                continue
            
            # Check exits first
            self.check_aggressive_exits(current_price, timestamp, row)
            
            # AGGRESSIVE SIGNAL GENERATION
            
            # Momentum signals (more lenient thresholds)
            momentum_signal = None
            if not pd.isna(row['rsi']) and not pd.isna(row['macd']) and not pd.isna(row['macd_signal']):
                # Strong momentum buy
                if row['rsi'] < 40 and row['macd'] > row['macd_signal'] and row['momentum'] > 0:
                    momentum_signal = {"action": "buy", "strength": min(0.9, (40 - row['rsi']) / 40)}
                # Strong momentum sell
                elif row['rsi'] > 60 and row['macd'] < row['macd_signal'] and row['momentum'] < 0:
                    momentum_signal = {"action": "sell", "strength": min(0.9, (row['rsi'] - 60) / 40)}
                # Extreme oversold bounce
                elif row['rsi'] < 25:
                    momentum_signal = {"action": "buy", "strength": 1.0}
                # Extreme overbought reversal
                elif row['rsi'] > 75:
                    momentum_signal = {"action": "sell", "strength": 1.0}
            
            # Mean reversion signals (tighter bands)
            mr_signal = None
            if not pd.isna(row['bb_upper']) and not pd.isna(row['bb_lower']):
                bb_position = (row['close'] - row['bb_lower']) / (row['bb_upper'] - row['bb_lower'])
                
                # Buy at lower band with volume confirmation
                if bb_position <= 0.1 and row.get('volume_ratio', 1) > 1.2:
                    mr_signal = {"action": "buy", "strength": min(0.95, 1.0 - bb_position)}
                # Sell at upper band with volume confirmation
                elif bb_position >= 0.9 and row.get('volume_ratio', 1) > 1.2:
                    mr_signal = {"action": "sell", "strength": min(0.95, bb_position)}
            
            # Breakout signals (new strategy)
            breakout_signal = None
            if i >= 50 and not pd.isna(row['atr']):
                # Check for volatility breakout
                recent_high = features_df['high'].iloc[i-20:i].max()
                recent_low = features_df['low'].iloc[i-20:i].min()
                
                if row['close'] > recent_high and row['volume_ratio'] > 1.5:
                    breakout_signal = {"action": "buy", "strength": 0.8}
                elif row['close'] < recent_low and row['volume_ratio'] > 1.5:
                    breakout_signal = {"action": "sell", "strength": 0.8}
            
            # Execute trades (allow up to 10 concurrent positions)
            max_positions = 10
            
            # Priority order: Breakout > Momentum > Mean Reversion
            if breakout_signal and len(self.positions) < max_positions:
                self.execute_aggressive_trade(
                    "Breakout", 
                    breakout_signal["action"], 
                    current_price,
                    breakout_signal["strength"],
                    timestamp
                )
            
            if momentum_signal and len(self.positions) < max_positions:
                self.execute_aggressive_trade(
                    "Momentum", 
                    momentum_signal["action"], 
                    current_price,
                    momentum_signal["strength"],
                    timestamp
                )
            
            if mr_signal and len(self.positions) < max_positions:
                self.execute_aggressive_trade(
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
            self.check_aggressive_exits(final_price, features_df.index[-1], features_df.iloc[-1])
        
        self.logger.success("✅ Aggressive backtest completed successfully!")
    
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
                'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else float('inf'),
                'trades_per_day': len(self.trades) / max(1, len(self.daily_returns))
            },
            'strategy_breakdown': self._strategy_breakdown(),
            'daily_metrics': {
                'avg_daily_return': np.mean(self.daily_returns) * 100 if self.daily_returns else 0,
                'daily_volatility': np.std(self.daily_returns) * 100 if self.daily_returns else 0,
                'best_day': max(self.daily_returns) * 100 if self.daily_returns else 0,
                'worst_day': min(self.daily_returns) * 100 if self.daily_returns else 0,
                'positive_days': sum(1 for r in self.daily_returns if r > 0) if self.daily_returns else 0,
                'negative_days': sum(1 for r in self.daily_returns if r < 0) if self.daily_returns else 0
            }
        }
        
        return report
    
    def _strategy_breakdown(self) -> Dict:
        """Break down performance by strategy."""
        momentum_trades = [t for t in self.trades if t['strategy'] == 'Momentum']
        mr_trades = [t for t in self.trades if t['strategy'] == 'MeanReversion']
        breakout_trades = [t for t in self.trades if t['strategy'] == 'Breakout']
        
        breakdown = {}
        
        for strategy_name, trades in [('Momentum', momentum_trades), 
                                     ('MeanReversion', mr_trades),
                                     ('Breakout', breakout_trades)]:
            if trades:
                winning = [t for t in trades if t['pnl'] > 0]
                total_pnl = sum(t['pnl'] for t in trades)
                
                breakdown[strategy_name] = {
                    'trades': len(trades),
                    'win_rate': len(winning) / len(trades) * 100,
                    'total_pnl': total_pnl,
                    'avg_return': np.mean([t['return_pct'] for t in trades]),
                    'avg_leverage': np.mean([t['leverage'] for t in trades])
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
    parser = argparse.ArgumentParser(description='Run aggressive backtest on trading strategies')
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
    
    # Create and run aggressive backtest
    engine = AggressiveBacktestEngine(config, args.initial_capital)
    
    try:
        await engine.run_aggressive_backtest(args.symbol, start_date, end_date)
        
        # Generate and display report
        report = engine.generate_report()
        
        print("\n" + "="*60)
        print("⚡ ULTRA-AGGRESSIVE BACKTEST RESULTS")
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
        print(f"Trades Per Day: {stats['trades_per_day']:.1f}")
        
        if 'daily_metrics' in report:
            print("\n📅 DAILY PERFORMANCE")
            print("-"*30)
            daily = report['daily_metrics']
            print(f"Avg Daily Return: {daily['avg_daily_return']:.2f}%")
            print(f"Daily Volatility: {daily['daily_volatility']:.2f}%")
            print(f"Best Day: {daily['best_day']:.2f}%")
            print(f"Worst Day: {daily['worst_day']:.2f}%")
            print(f"Positive Days: {daily['positive_days']}")
            print(f"Negative Days: {daily['negative_days']}")
        
        if 'strategy_breakdown' in report:
            print("\n🎯 STRATEGY BREAKDOWN")
            print("-"*30)
            for strategy, metrics in report['strategy_breakdown'].items():
                print(f"\n{strategy}:")
                print(f"  Trades: {metrics['trades']}")
                print(f"  Win Rate: {metrics['win_rate']:.1f}%")
                print(f"  Total P&L: ${metrics['total_pnl']:,.2f}")
                print(f"  Avg Return: {metrics['avg_return']:.2f}%")
                print(f"  Avg Leverage: {metrics['avg_leverage']:.1f}x")
        
        # Save results
        engine.save_results(args.output)
        
        print(f"\n✅ Complete results saved to: {args.output}")
        print("="*60)
        
        # Performance targets check
        target_daily = 2.0  # 2% daily target
        actual_daily = report.get('daily_metrics', {}).get('avg_daily_return', 0)
        
        if actual_daily >= target_daily:
            print(f"🎉 TARGET ACHIEVED! Daily return {actual_daily:.2f}% >= {target_daily:.2f}%")
        else:
            print(f"⚠️ Target missed. Daily return {actual_daily:.2f}% < {target_daily:.2f}%")
            print(f"📊 But achieved {stats['trades_per_day']:.1f} trades/day with {stats['win_rate']:.1f}% win rate")
            
    except Exception as e:
        print(f"❌ Backtest failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
