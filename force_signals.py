#!/usr/bin/env python3
"""
Force Trading Signal Detection

This script will check for opportunities on the markets that look most promising
and try to force the bot to reevaluate them for trading signals.
"""

import os
import sys
import time
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime
import ccxt

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from strategies.momentum_breakout import MomentumBreakoutStrategy
    from strategies.mean_reversion import MeanReversionStrategy
    from core.feature_engineering import FeatureEngineering
    from models.market_data import MarketSnapshot
    from multi_symbol_config import MultiSymbolConfig
except ImportError:
    print("Could not import required modules. Make sure you're running from the project directory.")
    sys.exit(1)

class SignalForcer:
    """Force evaluation of trading signals."""
    
    def __init__(self):
        """Initialize signal forcer."""
        self.exchange = ccxt.bybit({'enableRateLimit': True})
        self.feature_engine = FeatureEngineering()
        self.momentum_strategy = MomentumBreakoutStrategy()
        self.mean_reversion_strategy = MeanReversionStrategy()
        self.symbols = MultiSymbolConfig.get_active_symbols()
    
    def calculate_features(self, symbol, ohlcv_data):
        """Calculate technical features from OHLCV data."""
        if not ohlcv_data or len(ohlcv_data) < 30:
            print(f"Not enough data for {symbol}")
            return None
        
        df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Calculate common indicators
        try:
            class Features:
                def __init__(self):
                    self.symbol = symbol
                    self.price = df['close'].iloc[-1]
                    self.volume = df['volume'].iloc[-1]
                    self.timestamp = df['timestamp'].iloc[-1]
                    
                    # RSI
                    delta = df['close'].diff()
                    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
                    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
                    rs = gain / loss
                    self.rsi = 100 - (100 / (1 + rs)).iloc[-1]
                    
                    # ATR
                    high_low = df['high'] - df['low']
                    high_close = np.abs(df['high'] - df['close'].shift())
                    low_close = np.abs(df['low'] - df['close'].shift())
                    ranges = pd.concat([high_low, high_close, low_close], axis=1)
                    true_range = np.max(ranges, axis=1)
                    self.atr = true_range.rolling(14).mean().iloc[-1]
                    
                    # ADX
                    plus_dm = np.zeros(len(df))
                    minus_dm = np.zeros(len(df))
                    tr = true_range
                    
                    for i in range(1, len(df)):
                        plus_dm[i] = df['high'].iloc[i] - df['high'].iloc[i-1] if df['high'].iloc[i] - df['high'].iloc[i-1] > df['low'].iloc[i-1] - df['low'].iloc[i] and df['high'].iloc[i] - df['high'].iloc[i-1] > 0 else 0
                        minus_dm[i] = df['low'].iloc[i-1] - df['low'].iloc[i] if df['low'].iloc[i-1] - df['low'].iloc[i] > df['high'].iloc[i] - df['high'].iloc[i-1] and df['low'].iloc[i-1] - df['low'].iloc[i] > 0 else 0
                    
                    plus_di = 100 * pd.Series(plus_dm).rolling(window=14).mean() / tr.rolling(window=14).mean()
                    minus_di = 100 * pd.Series(minus_dm).rolling(window=14).mean() / tr.rolling(window=14).mean()
                    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
                    self.adx = dx.rolling(window=14).mean().iloc[-1]
                    
                    # MACD
                    ema12 = df['close'].ewm(span=12, adjust=False).mean()
                    ema26 = df['close'].ewm(span=26, adjust=False).mean()
                    self.macd = ema12.iloc[-1] - ema26.iloc[-1]
                    self.macd_signal = df['close'].ewm(span=9, adjust=False).mean().iloc[-1]
                    
                    # Bollinger Bands
                    sma20 = df['close'].rolling(window=20).mean()
                    std20 = df['close'].rolling(window=20).std()
                    upper_band = sma20 + (std20 * 2)
                    lower_band = sma20 - (std20 * 2)
                    self.bb_width = (upper_band - lower_band).iloc[-1]
                    self.upper_band = upper_band.iloc[-1]
                    self.lower_band = lower_band.iloc[-1]
                    
                    # Volatility
                    returns = np.log(df['close'] / df['close'].shift(1))
                    self.realized_vol_1h = returns.rolling(window=24).std().iloc[-1] * np.sqrt(365 * 24)
                    self.realized_vol_5m = returns.rolling(window=12).std().iloc[-1] * np.sqrt(365 * 24 * 12)
                    
            return Features()
        except Exception as e:
            print(f"Error calculating features for {symbol}: {e}")
            return None
    
    def check_for_signals(self):
        """Check for trading signals on active symbols."""
        print("╔═══════════════════════════════════════════════════════════════╗")
        print("║          Trading Signal Detector                              ║")
        print("║                                                               ║")
        print(f"║  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                               ║")
        print("╚═══════════════════════════════════════════════════════════════╝")
        
        print("\n🔍 CHECKING FOR TRADING SIGNALS")
        print("=" * 70)
        
        signals = []
        
        for symbol in self.symbols:
            print(f"Analyzing {symbol}...")
            try:
                # Fetch OHLCV data
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
                
                # Calculate features
                features = self.calculate_features(symbol, ohlcv)
                if not features:
                    continue
                    
                # Check for momentum signals
                momentum_signal = self.momentum_strategy.analyze(features, [])
                
                # Check for mean reversion signals
                mean_rev_signal = self.mean_reversion_strategy.analyze(features, [])
                
                # Store signal data
                symbol_data = {
                    'symbol': symbol.replace('/USDT:USDT', ''),
                    'price': features.price,
                    'rsi': features.rsi,
                    'adx': features.adx,
                    'momentum_signal': momentum_signal,
                    'mean_rev_signal': mean_rev_signal,
                    'signal_type': None,
                    'direction': None,
                    'strength': 0
                }
                
                if momentum_signal:
                    symbol_data['signal_type'] = 'Momentum'
                    symbol_data['direction'] = momentum_signal.direction
                    symbol_data['strength'] = momentum_signal.strength
                    symbol_data['reason'] = momentum_signal.reason
                    signals.append(symbol_data)
                    print(f"✅ MOMENTUM SIGNAL: {symbol} {momentum_signal.direction} ({momentum_signal.strength:.2f})")
                    print(f"   Reason: {momentum_signal.reason}")
                    print(f"   Entry: ${float(momentum_signal.entry_price):.2f}, " +
                          f"Stop: ${float(momentum_signal.stop_price):.2f}, " +
                          f"Target: ${float(momentum_signal.target_price):.2f}")
                elif mean_rev_signal:
                    symbol_data['signal_type'] = 'Mean Reversion'
                    symbol_data['direction'] = mean_rev_signal.direction
                    symbol_data['strength'] = mean_rev_signal.strength
                    symbol_data['reason'] = mean_rev_signal.reason
                    signals.append(symbol_data)
                    print(f"✅ MEAN REVERSION SIGNAL: {symbol} {mean_rev_signal.direction} ({mean_rev_signal.strength:.2f})")
                    print(f"   Reason: {mean_rev_signal.reason}")
                    print(f"   Entry: ${float(mean_rev_signal.entry_price):.2f}, " +
                          f"Stop: ${float(mean_rev_signal.stop_price):.2f}, " +
                          f"Target: ${float(mean_rev_signal.target_price):.2f}")
                else:
                    print(f"❌ No signals for {symbol}")
                    print(f"   RSI: {features.rsi:.1f}, ADX: {features.adx:.1f}")
                    
                    # Check why no signal was generated
                    if features.adx < 20 and features.rsi > 35 and features.rsi < 65:
                        print(f"   No momentum: ADX too low ({features.adx:.1f}), RSI not extreme ({features.rsi:.1f})")
                    elif features.adx >= 20 and (features.rsi < 40 or features.rsi > 60):
                        print(f"   Near momentum signal! ADX={features.adx:.1f}, RSI={features.rsi:.1f}")
                        if features.rsi < 40:
                            print("   Potential short signal forming")
                        else:
                            print("   Potential long signal forming")
                    
                    if features.adx > 30:
                        print(f"   No mean reversion: ADX too high ({features.adx:.1f})")
                    elif features.rsi > 35 and features.rsi < 65:
                        print(f"   No mean reversion: RSI not extreme ({features.rsi:.1f})")
                
                print("-" * 40)
                
            except Exception as e:
                print(f"Error analyzing {symbol}: {e}")
                print("-" * 40)
        
        # Summary
        print("\n📊 SIGNAL SUMMARY")
        print("=" * 70)
        
        if signals:
            print(f"Found {len(signals)} trading signals:")
            for sig in signals:
                print(f"- {sig['symbol']}: {sig['signal_type']} {sig['direction'].upper()} " +
                      f"(Strength: {sig['strength']:.2f})")
        else:
            print("No trading signals detected.")
            
        # Near signals - symbols close to generating signals
        print("\n⚠️ NEAR SIGNAL SYMBOLS")
        print("=" * 70)
        
        near_signals = []
        for symbol in self.symbols:
            try:
                # Get current price data
                ticker = self.exchange.fetch_ticker(symbol)
                
                # Get 1h OHLCV
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe='1h', limit=30)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                # Calculate RSI
                delta = df['close'].diff()
                gain = delta.where(delta > 0, 0).rolling(window=14).mean()
                loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs)).iloc[-1]
                
                # Add to near signals if close to thresholds
                if 30 <= rsi <= 35 or 65 <= rsi <= 70:
                    near_signals.append({
                        'symbol': symbol.replace('/USDT:USDT', ''),
                        'price': ticker['last'],
                        'rsi': rsi,
                        'direction': 'long' if rsi <= 35 else 'short'
                    })
            except:
                pass
        
        if near_signals:
            print(f"Found {len(near_signals)} symbols close to generating signals:")
            for sig in near_signals:
                direction_str = "LONG" if sig['direction'] == 'long' else "SHORT"
                print(f"- {sig['symbol']}: Price=${sig['price']:.2f}, RSI={sig['rsi']:.1f} " +
                      f"(Potential {direction_str})")
        else:
            print("No symbols close to generating signals.")
        
        print("\n✅ Signal detection complete.")


if __name__ == "__main__":
    detector = SignalForcer()
    detector.check_for_signals()
