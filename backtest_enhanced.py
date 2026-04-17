#!/usr/bin/env python3
"""
Enhanced backtesting framework with improved strategies and risk management
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import pandas as pd
import numpy as np
import ta
from enum import Enum

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


class MarketRegime(Enum):
    """Market regime types"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


class EnhancedBacktestEngine:
    """Enhanced backtesting engine with improved strategies"""
    
    def __init__(self, config, initial_capital: float = 10000):
        self.config = config
        self.logger = get_logger("enhanced_backtest")
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
        
        # Market regime tracking
        self.current_regime = MarketRegime.RANGING
        self.regime_history = []
        
        # Enhanced risk parameters
        self.base_risk_per_trade = Decimal("0.02")  # 2% base risk
        self.max_concurrent_positions = 8
        self.volatility_lookback = 50  # periods for volatility calculation
        
    async def generate_enhanced_synthetic_data(self, symbol: str, start_date: datetime, 
                                             end_date: datetime) -> List[Candle]:
        """Generate more realistic synthetic market data with various market conditions"""
        self.logger.info(f"Generating enhanced synthetic data for {symbol}")
        
        candles = []
        current_time = start_date
        current_price = Decimal("65000")  # Starting BTC price
        
        # Market state variables
        trend_direction = 0  # -1 down, 0 neutral, 1 up
        trend_strength = 0.0
        volatility_regime = "normal"
        
        while current_time < end_date:
            # Determine market regime (changes every 1-7 days)
            days_since_start = (current_time - start_date).days
            if days_since_start % np.random.randint(1, 8) == 0:
                # Change market regime
                regime_choice = np.random.choice(['trend_up', 'trend_down', 'ranging', 'volatile'])
                if regime_choice == 'trend_up':
                    trend_direction = 1
                    trend_strength = np.random.uniform(0.0003, 0.0008)
                    volatility_regime = "normal"
                elif regime_choice == 'trend_down':
                    trend_direction = -1
                    trend_strength = np.random.uniform(0.0003, 0.0008)
                    volatility_regime = "normal"
                elif regime_choice == 'ranging':
                    trend_direction = 0
                    trend_strength = 0.0
                    volatility_regime = "low"
                else:  # volatile
                    trend_direction = np.random.choice([-1, 0, 1])
                    trend_strength = np.random.uniform(0.0001, 0.0004)
                    volatility_regime = "high"
            
            # Set volatility based on regime
            if volatility_regime == "low":
                volatility = 0.015  # 1.5% daily
            elif volatility_regime == "normal":
                volatility = 0.025  # 2.5% daily
            else:  # high
                volatility = 0.04   # 4% daily
            
            # Generate price movement
            random_component = np.random.normal(0, volatility / 288)  # 5-minute intervals
            trend_component = trend_strength * trend_direction
            
            # Add momentum effect
            if len(candles) > 10:
                recent_returns = [(candles[-i].close - candles[-i-1].close) / candles[-i-1].close 
                                for i in range(1, min(6, len(candles)))]
                momentum = np.mean(recent_returns) if recent_returns else 0
                momentum_effect = float(momentum) * 0.2  # 20% momentum continuation
            else:
                momentum_effect = 0
            
            # Combine all effects
            total_change = random_component + trend_component + momentum_effect
            
            # Add mean reversion for extreme moves
            if abs(total_change) > 0.02:  # 2% move
                total_change *= 0.7  # Reduce by 30%
            
            price_change = current_price * Decimal(str(total_change))
            new_price = current_price + price_change
            
            # Create realistic OHLC with proper relationships
            if price_change > 0:
                open_price = current_price
                close_price = new_price
                high = close_price * Decimal(str(1 + abs(np.random.normal(0, 0.001))))
                low = open_price * Decimal(str(1 - abs(np.random.normal(0, 0.0005))))
            else:
                open_price = current_price
                close_price = new_price
                high = open_price * Decimal(str(1 + abs(np.random.normal(0, 0.0005))))
                low = close_price * Decimal(str(1 - abs(np.random.normal(0, 0.001))))
            
            # Volume based on volatility
            base_volume = 100
            volume_multiplier = 1 + abs(float(price_change / current_price)) * 10
            volume = Decimal(str(base_volume * volume_multiplier * np.random.uniform(0.8, 1.2)))
            
            candle = Candle(
                symbol=symbol,
                timestamp=current_time,
                open=open_price,
                high=high,
                low=low,
                close=close_price,
                volume=volume,
                timeframe="5m"
            )
            
            candles.append(candle)
            current_price = new_price
            current_time += timedelta(minutes=5)
        
        self.logger.info(f"Generated {len(candles)} enhanced candles for backtesting")
        return candles
    
    def detect_market_regime(self, df: pd.DataFrame, current_idx: int) -> MarketRegime:
        """Detect current market regime using multiple indicators"""
        if current_idx < 50:
            return MarketRegime.RANGING
        
        # Get recent data
        recent_data = df.iloc[max(0, current_idx-50):current_idx+1]
        
        # Calculate regime indicators
        # 1. Trend strength using ADX
        adx = ta.trend.ADXIndicator(
            high=recent_data['high'], 
            low=recent_data['low'], 
            close=recent_data['close'], 
            window=14
        ).adx()
        
        # 2. Trend direction using moving averages
        sma_short = recent_data['close'].rolling(10).mean()
        sma_long = recent_data['close'].rolling(30).mean()
        
        # 3. Volatility using ATR
        atr = ta.volatility.AverageTrueRange(
            high=recent_data['high'],
            low=recent_data['low'], 
            close=recent_data['close'],
            window=14
        ).average_true_range()
        
        # Get latest values
        latest_adx = adx.iloc[-1] if not adx.empty else 0
        latest_atr = atr.iloc[-1] if not atr.empty else 0
        latest_close = recent_data['close'].iloc[-1]
        latest_sma_short = sma_short.iloc[-1] if not sma_short.empty else latest_close
        latest_sma_long = sma_long.iloc[-1] if not sma_long.empty else latest_close
        
        # Normalize ATR as percentage
        atr_pct = (latest_atr / latest_close) * 100
        
        # Determine regime
        if atr_pct > 3:  # High volatility (>3% ATR)
            return MarketRegime.HIGH_VOLATILITY
        elif atr_pct < 1:  # Low volatility (<1% ATR)
            return MarketRegime.LOW_VOLATILITY
        elif latest_adx > 25:  # Strong trend
            if latest_sma_short > latest_sma_long * 1.002:  # 0.2% above
                return MarketRegime.TRENDING_UP
            elif latest_sma_short < latest_sma_long * 0.998:  # 0.2% below
                return MarketRegime.TRENDING_DOWN
        
        return MarketRegime.RANGING
    
    def calculate_dynamic_position_size(self, signal_strength: float, current_price: Decimal,
                                      volatility: float, regime: MarketRegime) -> Decimal:
        """Calculate position size with dynamic risk management"""
        # Base risk adjustment based on regime
        regime_risk_multipliers = {
            MarketRegime.TRENDING_UP: Decimal("1.2"),
            MarketRegime.TRENDING_DOWN: Decimal("1.2"),
            MarketRegime.RANGING: Decimal("0.8"),
            MarketRegime.HIGH_VOLATILITY: Decimal("0.6"),
            MarketRegime.LOW_VOLATILITY: Decimal("1.0")
        }
        
        regime_multiplier = regime_risk_multipliers.get(regime, Decimal("1.0"))
        
        # Adjust risk based on recent performance
        recent_trades = self.trades[-10:] if len(self.trades) >= 10 else self.trades
        if recent_trades:
            recent_win_rate = sum(1 for t in recent_trades if t['pnl'] > 0) / len(recent_trades)
            performance_multiplier = Decimal(str(0.5 + recent_win_rate))  # 0.5 to 1.5
        else:
            performance_multiplier = Decimal("1.0")
        
        # Calculate risk per trade
        risk_per_trade = self.base_risk_per_trade * regime_multiplier * performance_multiplier
        risk_per_trade = min(risk_per_trade, Decimal("0.04"))  # Max 4% risk
        
        # Position sizing based on volatility-adjusted stop loss
        volatility_multiplier = Decimal(str(max(1.0, min(2.5, volatility / 0.02))))
        stop_distance = current_price * Decimal("0.008") * volatility_multiplier
        
        position_risk = self.current_capital * risk_per_trade
        position_size = position_risk / stop_distance
        
        # Dynamic leverage based on signal strength and regime
        if regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            base_leverage = Decimal("15")
            max_leverage = Decimal("25")
        elif regime == MarketRegime.HIGH_VOLATILITY:
            base_leverage = Decimal("5")
            max_leverage = Decimal("10")
        else:
            base_leverage = Decimal("10")
            max_leverage = Decimal("20")
        
        leverage = base_leverage + (max_leverage - base_leverage) * Decimal(str(signal_strength))
        leveraged_size = position_size * leverage
        
        # Position limits based on available capital
        max_position_value = self.current_capital * Decimal("0.25")
        max_size = max_position_value / current_price
        
        return min(leveraged_size, max_size)
    
    def generate_enhanced_signals(self, df: pd.DataFrame, idx: int, 
                                regime: MarketRegime) -> List[Dict]:
        """Generate trading signals based on market regime"""
        if idx < 50:
            return []
        
        signals = []
        row = df.iloc[idx]
        
        # Get current values
        rsi = row.get('rsi', 50)
        macd = row.get('macd', 0)
        macd_signal = row.get('macd_signal', 0)
        bb_position = row.get('bb_position', 0.5)
        volume_ratio = row.get('volume_ratio', 1)
        atr = row.get('atr', 0)
        price_momentum = row.get('momentum_10', 0)
        
        # Trend following signals (for trending regimes)
        if regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            # Momentum continuation
            if regime == MarketRegime.TRENDING_UP:
                if (rsi > 40 and rsi < 70 and 
                    macd > macd_signal and 
                    price_momentum > 0 and
                    volume_ratio > 1.1):
                    strength = min(0.9, 0.5 + (rsi - 40) / 60)
                    signals.append({
                        "strategy": "TrendFollowing",
                        "action": "buy",
                        "strength": strength,
                        "reason": "Trend continuation up"
                    })
            else:  # TRENDING_DOWN
                if (rsi < 60 and rsi > 30 and 
                    macd < macd_signal and 
                    price_momentum < 0 and
                    volume_ratio > 1.1):
                    strength = min(0.9, 0.5 + (60 - rsi) / 60)
                    signals.append({
                        "strategy": "TrendFollowing",
                        "action": "sell",
                        "strength": strength,
                        "reason": "Trend continuation down"
                    })
        
        # Mean reversion signals (for ranging markets)
        elif regime == MarketRegime.RANGING:
            # Oversold bounce
            if bb_position < 0.1 and rsi < 35 and volume_ratio > 1.2:
                strength = min(0.95, (35 - rsi) / 35 + (0.1 - bb_position))
                signals.append({
                    "strategy": "MeanReversion",
                    "action": "buy",
                    "strength": strength,
                    "reason": "Oversold bounce"
                })
            # Overbought reversal
            elif bb_position > 0.9 and rsi > 65 and volume_ratio > 1.2:
                strength = min(0.95, (rsi - 65) / 35 + (bb_position - 0.9))
                signals.append({
                    "strategy": "MeanReversion",
                    "action": "sell",
                    "strength": strength,
                    "reason": "Overbought reversal"
                })
        
        # Volatility breakout signals
        if regime == MarketRegime.HIGH_VOLATILITY:
            # Check for volatility breakout
            recent_high = df['high'].iloc[idx-20:idx].max()
            recent_low = df['low'].iloc[idx-20:idx].min()
            
            if row['close'] > recent_high and volume_ratio > 1.5:
                strength = min(0.85, 0.6 + volume_ratio / 10)
                signals.append({
                    "strategy": "VolatilityBreakout",
                    "action": "buy",
                    "strength": strength,
                    "reason": "Upside volatility breakout"
                })
            elif row['close'] < recent_low and volume_ratio > 1.5:
                strength = min(0.85, 0.6 + volume_ratio / 10)
                signals.append({
                    "strategy": "VolatilityBreakout",
                    "action": "sell",
                    "strength": strength,
                    "reason": "Downside volatility breakout"
                })
        
        # Divergence signals (work in all regimes)
        if idx >= 14:
            # RSI divergence
            price_higher = row['close'] > df.iloc[idx-14]['close']
            rsi_lower = rsi < df.iloc[idx-14].get('rsi', 50)
            
            if price_higher and rsi_lower and rsi < 50:
                signals.append({
                    "strategy": "Divergence",
                    "action": "sell",
                    "strength": 0.7,
                    "reason": "Bearish RSI divergence"
                })
            elif not price_higher and not rsi_lower and rsi > 50:
                signals.append({
                    "strategy": "Divergence", 
                    "action": "buy",
                    "strength": 0.7,
                    "reason": "Bullish RSI divergence"
                })
        
        return signals
    
    def calculate_dynamic_stops(self, entry_price: Decimal, side: str, atr: float,
                              regime: MarketRegime) -> Tuple[Decimal, Decimal]:
        """Calculate dynamic stop loss and take profit based on ATR and regime"""
        # Base multipliers
        if regime == MarketRegime.HIGH_VOLATILITY:
            sl_multiplier = 1.5  # Wider stops in volatile markets
            tp_multiplier = 2.5
        elif regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            sl_multiplier = 1.2
            tp_multiplier = 3.0  # Let profits run in trends
        else:
            sl_multiplier = 1.0
            tp_multiplier = 1.8
        
        # Calculate distances
        atr_decimal = Decimal(str(atr))
        sl_distance = atr_decimal * Decimal(str(sl_multiplier))
        tp_distance = atr_decimal * Decimal(str(tp_multiplier))
        
        # Minimum distances
        min_sl = entry_price * Decimal("0.005")  # 0.5% minimum
        min_tp = entry_price * Decimal("0.008")  # 0.8% minimum
        
        sl_distance = max(sl_distance, min_sl)
        tp_distance = max(tp_distance, min_tp)
        
        # Calculate prices
        if side == "buy":
            stop_loss = entry_price - sl_distance
            take_profit = entry_price + tp_distance
        else:
            stop_loss = entry_price + sl_distance
            take_profit = entry_price - tp_distance
        
        return stop_loss, take_profit
    
    def execute_enhanced_trade(self, signal: Dict, price: Decimal, timestamp: datetime,
                             atr: float, regime: MarketRegime) -> Optional[str]:
        """Execute trade with enhanced risk management"""
        try:
            # Check position limits
            if len(self.positions) >= self.max_concurrent_positions:
                return None
            
            # Check if we already have a position in this direction
            existing_positions = [p for p in self.positions.values() 
                                if p.side.value == signal["action"]]
            if len(existing_positions) >= 3:  # Max 3 positions per direction
                return None
            
            # Calculate volatility
            # Ensure both operands float for division
            volatility = atr / float(price) if atr > 0 else 0.02
            
            # Calculate position size
            size = self.calculate_dynamic_position_size(
                signal["strength"], price, volatility, regime
            )
            
            if size <= 0:
                return None
            
            # Calculate dynamic stops
            stop_loss, take_profit = self.calculate_dynamic_stops(
                price, signal["action"], atr, regime
            )
            
            # Determine leverage
            if regime == MarketRegime.HIGH_VOLATILITY:
                leverage = float(5 + signal["strength"] * 5)  # 5-10x
            elif regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
                leverage = float(15 + signal["strength"] * 10)  # 15-25x
            else:
                leverage = float(10 + signal["strength"] * 10)  # 10-20x
            
            # Create position
            position = Position.create_new(
                symbol="BTC/USDT:USDT",
                side=signal["action"],
                size=size,
                entry_price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                leverage=leverage,
                strategy_name=signal["strategy"],
                signal_strength=signal["strength"]
            )
            
            # Calculate fees
            fees = size * price * Decimal("0.0002")
            position.add_fees(fees)
            
            # Update capital
            margin_required = (size * price) / Decimal(str(leverage))
            self.current_capital -= (margin_required + fees)
            
            # Store position with metadata
            position.metadata = {
                "regime": regime.value,
                "entry_reason": signal["reason"],
                "entry_atr": float(atr),
                "entry_volatility": volatility
            }
            self.positions[position.position_id] = position
            
            # Log trade
            self.logger.info(f"📊 {signal['strategy']} {signal['action'].upper()} | "
                           f"Size: {size:.4f} | Price: ${price} | "
                           f"Leverage: {leverage:.1f}x | Regime: {regime.value}")
            
            return position.position_id
            
        except Exception as e:
            self.logger.error(f"Enhanced trade execution failed: {e}")
            return None
    
    def check_enhanced_exits(self, current_price: Decimal, timestamp: datetime,
                           df_row: pd.Series, atr: float) -> List[str]:
        """Check for position exits with enhanced logic"""
        closed_positions = []
        
        for position_id, position in list(self.positions.items()):
            should_close = False
            exit_reason = ""
            
            # Update position price
            position.update_price(current_price)
            
            # Trailing stop implementation
            if position.unrealized_pnl_pct > 1.0:  # 1%+ profit
                if position.is_long:
                    # Trail stop to break even + 0.2%
                    breakeven_plus = position.entry_price * Decimal("1.002")
                    if position.stop_loss_price < breakeven_plus:
                        position.stop_loss_price = breakeven_plus
                    
                    # Dynamic trailing based on profit level
                    if position.unrealized_pnl_pct > 2.0:
                        trail_distance = current_price * Decimal("0.01")  # 1% trail
                        trailing_stop = current_price - trail_distance
                        if trailing_stop > position.stop_loss_price:
                            position.stop_loss_price = trailing_stop
                else:  # Short position
                    breakeven_minus = position.entry_price * Decimal("0.998")
                    if position.stop_loss_price > breakeven_minus:
                        position.stop_loss_price = breakeven_minus
                    
                    if position.unrealized_pnl_pct > 2.0:
                        trail_distance = current_price * Decimal("0.01")
                        trailing_stop = current_price + trail_distance
                        if trailing_stop < position.stop_loss_price:
                            position.stop_loss_price = trailing_stop
            
            # Check stop loss
            if position.is_long and current_price <= position.stop_loss_price:
                should_close = True
                exit_reason = "Stop Loss" if position.unrealized_pnl < 0 else "Trailing Stop"
            elif position.is_short and current_price >= position.stop_loss_price:
                should_close = True
                exit_reason = "Stop Loss" if position.unrealized_pnl < 0 else "Trailing Stop"
            
            # Check take profit
            elif position.is_long and current_price >= position.take_profit_price:
                should_close = True
                exit_reason = "Take Profit"
            elif position.is_short and current_price <= position.take_profit_price:
                should_close = True
                exit_reason = "Take Profit"
            
            # Time-based exit (max 8 hours for scalping, 24 hours for trends)
            max_duration = 480 if hasattr(position, 'metadata') and \
                          position.metadata.get('regime') in ['trending_up', 'trending_down'] else 240
            if position.duration_minutes > max_duration:
                should_close = True
                exit_reason = "Time Exit"
            
            # Exit on regime change
            if hasattr(position, 'metadata'):
                entry_regime = position.metadata.get('regime')
                if entry_regime == 'trending_up' and df_row.get('rsi', 50) > 75:
                    should_close = True
                    exit_reason = "Trend Exhaustion"
                elif entry_regime == 'trending_down' and df_row.get('rsi', 50) < 25:
                    should_close = True
                    exit_reason = "Trend Exhaustion"
            
            # Volatility-based exit
            if atr > 0 and hasattr(position, 'metadata'):
                entry_atr = position.metadata.get('entry_atr', atr)
                if atr > entry_atr * 1.5:  # 50% increase in volatility
                    should_close = True
                    exit_reason = "Volatility Spike"
            
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
                    'leverage': position.leverage,
                    'regime': position.metadata.get('regime', 'unknown') if hasattr(position, 'metadata') else 'unknown'
                }
                self.trades.append(trade_record)
                
                # Log exit
                emoji = "💰" if pnl > 0 else "💸"
                self.logger.info(f"{emoji} {exit_reason} | {position.side.value.upper()} | "
                               f"P&L: ${pnl:.2f} | Return: {position.unrealized_pnl_pct:.2f}%")
                
                closed_positions.append(position_id)
                del self.positions[position_id]
        
        return closed_positions
    
    def add_enhanced_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add enhanced technical indicators"""
        # Standard indicators
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
        
        # MACD
        macd = ta.trend.MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_histogram'] = macd.macd_diff()
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_width'] = bb.bollinger_wband()
        
        # BB position (0-1)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        df['bb_position'] = df['bb_position'].fillna(0.5)
        
        # Moving Averages
        df['sma_10'] = ta.trend.SMAIndicator(close=df['close'], window=10).sma_indicator()
        df['sma_20'] = ta.trend.SMAIndicator(close=df['close'], window=20).sma_indicator()
        df['sma_50'] = ta.trend.SMAIndicator(close=df['close'], window=50).sma_indicator()
        df['ema_12'] = ta.trend.EMAIndicator(close=df['close'], window=12).ema_indicator()
        df['ema_26'] = ta.trend.EMAIndicator(close=df['close'], window=26).ema_indicator()
        
        # ATR for volatility
        df['atr'] = ta.volatility.AverageTrueRange(
            high=df['high'], low=df['low'], close=df['close'], window=14
        ).average_true_range()
        
        # Volume analysis
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
        
        # Price momentum
        df['momentum_5'] = df['close'] - df['close'].shift(5)
        df['momentum_10'] = df['close'] - df['close'].shift(10)
        
        # Stochastic RSI
        stoch_rsi = ta.momentum.StochRSIIndicator(close=df['close'], window=14)
        df['stoch_rsi'] = stoch_rsi.stochrsi()
        df['stoch_rsi_k'] = stoch_rsi.stochrsi_k()
        df['stoch_rsi_d'] = stoch_rsi.stochrsi_d()
        
        return df
    
    async def run_enhanced_backtest(self, symbol: str, start_date: datetime, end_date: datetime):
        """Run the enhanced backtest with improved strategies"""
        self.logger.info("🚀 Starting ENHANCED backtest with dynamic strategies...")
        self.logger.info(f"Symbol: {symbol}")
        self.logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        self.logger.info(f"Initial Capital: ${self.initial_capital}")
        
        # Generate enhanced market data
        candles = await self.generate_enhanced_synthetic_data(symbol, start_date, end_date)
        
        if not candles:
            self.logger.error("No market data available for backtesting")
            return
        
        # Convert to DataFrame
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
        
        # Add enhanced indicators
        features_df = self.add_enhanced_indicators(df)
        
        # Run backtest
        for i, (timestamp, row) in enumerate(features_df.iterrows()):
            current_price = Decimal(str(row['close']))
            current_atr = row.get('atr', 0)
            
            # Skip warmup period
            if i < 50:
                continue
            
            # Detect market regime
            self.current_regime = self.detect_market_regime(features_df, i)
            self.regime_history.append({
                'timestamp': timestamp,
                'regime': self.current_regime.value
            })
            
            # Check exits first
            self.check_enhanced_exits(current_price, timestamp, row, current_atr)
            
            # Generate signals based on regime
            signals = self.generate_enhanced_signals(features_df, i, self.current_regime)
            
            # Execute trades
            for signal in signals:
                if len(self.positions) < self.max_concurrent_positions:
                    self.execute_enhanced_trade(
                        signal, current_price, timestamp, 
                        current_atr, self.current_regime
                    )
            
            # Update equity curve
            unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
            current_equity = self.current_capital + unrealized_pnl
            
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': float(current_equity),
                'cash': float(self.current_capital),
                'unrealized_pnl': float(unrealized_pnl),
                'num_positions': len(self.positions),
                'regime': self.current_regime.value
            })
            
            # Track drawdown
            if current_equity > self.peak_equity:
                self.peak_equity = current_equity
            
            drawdown = (self.peak_equity - current_equity) / self.peak_equity
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown
            
            # Daily returns calculation
            if i % 288 == 0:  # Every 24 hours
                if len(self.equity_curve) >= 288:
                    prev_equity = Decimal(str(self.equity_curve[-288]['equity']))
                    daily_return = (current_equity - prev_equity) / prev_equity
                    self.daily_returns.append(float(daily_return))
        
        # Close remaining positions
        final_price = Decimal(str(features_df.iloc[-1]['close']))
        final_atr = features_df.iloc[-1].get('atr', 0)
        for position_id in list(self.positions.keys()):
            self.check_enhanced_exits(final_price, features_df.index[-1], 
                                    features_df.iloc[-1], final_atr)
        
        self.logger.success("✅ Enhanced backtest completed successfully!")
    
    def generate_report(self) -> Dict:
        """Generate comprehensive performance report"""
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
            'regime_analysis': self._regime_analysis(),
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
        """Break down performance by strategy"""
        strategies = {}
        for trade in self.trades:
            strategy = trade['strategy']
            if strategy not in strategies:
                strategies[strategy] = []
            strategies[strategy].append(trade)
        
        breakdown = {}
        for strategy_name, trades in strategies.items():
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
    
    def _regime_analysis(self) -> Dict:
        """Analyze performance by market regime"""
        regime_trades = {}
        for trade in self.trades:
            regime = trade.get('regime', 'unknown')
            if regime not in regime_trades:
                regime_trades[regime] = []
            regime_trades[regime].append(trade)
        
        analysis = {}
        for regime, trades in regime_trades.items():
            if trades:
                winning = [t for t in trades if t['pnl'] > 0]
                total_pnl = sum(t['pnl'] for t in trades)
                
                analysis[regime] = {
                    'trades': len(trades),
                    'win_rate': len(winning) / len(trades) * 100,
                    'total_pnl': total_pnl,
                    'avg_return': np.mean([t['return_pct'] for t in trades])
                }
        
        return analysis
    
    def save_results(self, output_dir: str):
        """Save backtest results to files"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save report
        report = self.generate_report()
        with open(output_path / 'enhanced_backtest_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        # Save trades
        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            trades_df.to_csv(output_path / 'enhanced_trades.csv', index=False)
        
        # Save equity curve
        if self.equity_curve:
            equity_df = pd.DataFrame(self.equity_curve)
            equity_df.to_csv(output_path / 'enhanced_equity_curve.csv', index=False)
        
        # Save regime history
        if self.regime_history:
            regime_df = pd.DataFrame(self.regime_history)
            regime_df.to_csv(output_path / 'regime_history.csv', index=False)
        
        self.logger.info(f"Enhanced results saved to {output_path}")


async def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Run enhanced backtest with dynamic strategies')
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
    
    # Create and run enhanced backtest
    engine = EnhancedBacktestEngine(config, args.initial_capital)
    
    try:
        await engine.run_enhanced_backtest(args.symbol, start_date, end_date)
        
        # Generate and display report
        report = engine.generate_report()
        
        print("\n" + "="*60)
        print("🚀 ENHANCED BACKTEST RESULTS")
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
        
        if 'regime_analysis' in report:
            print("\n📈 REGIME ANALYSIS")
            print("-"*30)
            for regime, metrics in report['regime_analysis'].items():
                print(f"\n{regime}:")
                print(f"  Trades: {metrics['trades']}")
                print(f"  Win Rate: {metrics['win_rate']:.1f}%")
                print(f"  Total P&L: ${metrics['total_pnl']:,.2f}")
                print(f"  Avg Return: {metrics['avg_return']:.2f}%")
        
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
            print(f"📊 Progress: Daily return {actual_daily:.2f}% (Target: {target_daily:.2f}%)")
            print(f"💡 Win rate: {stats['win_rate']:.1f}% | Profit factor: {stats['profit_factor']:.2f}")
            
    except Exception as e:
        print(f"❌ Enhanced backtest failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
