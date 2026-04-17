#!/usr/bin/env python3
"""
Debug Trading Status
A more detailed status monitoring tool for multi-symbol trading
"""

import sys
from pathlib import Path
import ccxt
import pandas as pd
from datetime import datetime, timedelta
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_config
from multi_symbol_config import MultiSymbolConfig
from core.feature_engineering import FeatureEngineering


def clear_screen():
    """Clear terminal screen."""
    import os
    os.system('cls' if os.name == 'nt' else 'clear')


class TradingDebugger:
    """Detailed status monitoring for multi-symbol trading."""
    
    def __init__(self):
        """Initialize debugger."""
        self.config = get_config()
        self.exchange_config = self.config.to_ccxt_config(sandbox=False)
        self.exchange = ccxt.bybit(self.exchange_config)
        self.symbols = MultiSymbolConfig.get_active_symbols()
        
        # Initialize feature engineering for debugging
        self.feature_engine = FeatureEngineering()
    
    def check_strategy_criteria(self):
        """Check strategy criteria for all symbols."""
        results = []
        
        print("\n🔍 CHECKING STRATEGY ENTRY CRITERIA")
        print("=" * 60)
        
        for symbol in self.symbols:
            # Get OHLCV data
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe='1h', limit=60)
                
                # Convert to pandas dataframe
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Calculate basic indicators
                df['rsi'] = self.feature_engine._rsi(df['close'])
                df['atr'] = self.feature_engine._atr(df['high'], df['low'], df['close'])
                df['adx'] = self.feature_engine._adx(df['high'], df['low'], df['close'])
                df['vol_1h'] = self.feature_engine._realized_volatility(df['close'], window=24)
                df['macd'], df['macd_signal'], _ = self.feature_engine._macd(df['close'])
                
                # Current price data
                ticker = self.exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                
                # Calculate bands
                df['sma_20'] = df['close'].rolling(window=20).mean()
                df['std_20'] = df['close'].rolling(window=20).std()
                df['upper_band'] = df['sma_20'] + (2 * df['std_20'])
                df['lower_band'] = df['sma_20'] - (2 * df['std_20'])
                df['bb_width'] = (df['upper_band'] - df['lower_band']) / df['sma_20']
                
                # Get latest row
                latest = df.iloc[-1]
                
                # Check momentum criteria
                momentum_criteria = {
                    "price": current_price,
                    "adx": latest.adx,
                    "rsi": latest.rsi,
                    "macd": latest.macd > latest.macd_signal,
                    "volume": ticker['quoteVolume'] > df['volume'].mean() * 1.5,
                    "breakout_up": current_price > df['high'].rolling(window=20).max().iloc[-1],
                    "breakout_down": current_price < df['low'].rolling(window=20).min().iloc[-1],
                    "passes": (
                        latest.adx >= 25 and
                        ((latest.rsi > 45 and latest.macd > latest.macd_signal) or
                         (latest.rsi < 55 and latest.macd < latest.macd_signal))
                    )
                }
                
                # Check mean reversion criteria
                mean_reversion_criteria = {
                    "price": current_price,
                    "adx": latest.adx,
                    "rsi": latest.rsi,
                    "bb_width": latest.bb_width,
                    "overbought": latest.rsi > 70 and current_price > latest.upper_band,
                    "oversold": latest.rsi < 30 and current_price < latest.lower_band,
                    "passes": (
                        latest.adx < 25 and
                        latest.bb_width < 0.02 and latest.bb_width > 0.001 and
                        ((latest.rsi < 30 and current_price < latest.lower_band) or
                         (latest.rsi > 70 and current_price > latest.upper_band))
                    )
                }
                
                # Determine best strategy
                best_strategy = None
                if momentum_criteria["passes"] and not mean_reversion_criteria["passes"]:
                    best_strategy = "momentum"
                elif mean_reversion_criteria["passes"] and not momentum_criteria["passes"]:
                    best_strategy = "mean_reversion"
                elif momentum_criteria["passes"] and mean_reversion_criteria["passes"]:
                    best_strategy = "both" 
                
                # Entry direction
                entry_direction = "none"
                if momentum_criteria["passes"]:
                    if momentum_criteria["breakout_up"]:
                        entry_direction = "long"
                    elif momentum_criteria["breakout_down"]:
                        entry_direction = "short"
                elif mean_reversion_criteria["passes"]:
                    if mean_reversion_criteria["overbought"]:
                        entry_direction = "short"
                    elif mean_reversion_criteria["oversold"]:
                        entry_direction = "long"
                
                results.append({
                    "symbol": symbol.replace("/USDT:USDT", ""),
                    "price": current_price,
                    "adx": latest.adx,
                    "rsi": latest.rsi,
                    "bb_width": latest.bb_width,
                    "momentum": momentum_criteria["passes"],
                    "mean_reversion": mean_reversion_criteria["passes"],
                    "best_strategy": best_strategy,
                    "entry_direction": entry_direction
                })
                
            except Exception as e:
                print(f"Error processing {symbol}: {e}")
        
        # Display results
        print(f"{'SYMBOL':<8} {'PRICE':<10} {'ADX':<6} {'RSI':<6} {'BB %':<6} {'M.STRAT':<8} {'DIRECTION':<8}")
        print("-" * 60)
        
        for result in sorted(results, key=lambda x: (x['momentum'] or x['mean_reversion'], x['symbol']), reverse=True):
            momentum_icon = "✓" if result["momentum"] else " "
            mean_rev_icon = "✓" if result["mean_reversion"] else " "
            direction = result["entry_direction"].upper() if result["entry_direction"] != "none" else "-"
            
            strat = f"{momentum_icon}{mean_rev_icon}"
            print(f"{result['symbol']:<8} {result['price']:<10.2f} {result['adx']:<6.1f} {result['rsi']:<6.1f} "
                f"{result['bb_width']*100:<6.2f} {strat:<8} {direction:<8}")
        
        print("\nStrategy key: First column = Momentum, Second column = Mean Reversion")
    
    def check_account_status(self):
        """Check account status and positions."""
        try:
            # Get balance
            balance = self.exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {})
            
            print("\n💰 ACCOUNT STATUS")
            print("=" * 40)
            print(f"Free:  ${usdt_balance.get('free', 0):.2f} USDT")
            print(f"Used:  ${usdt_balance.get('used', 0):.2f} USDT")
            print(f"Total: ${usdt_balance.get('total', 0):.2f} USDT")
            
            # Get positions
            positions = self.exchange.fetch_positions()
            open_positions = [p for p in positions if float(p['contracts']) > 0]
            
            if open_positions:
                print("\n📊 OPEN POSITIONS")
                print("=" * 60)
                print(f"{'SYMBOL':<10} {'SIDE':<6} {'SIZE':<8} {'ENTRY':<10} {'PRICE':<10} {'PNL %':<8}")
                print("-" * 60)
                
                for pos in sorted(open_positions, key=lambda x: float(x['unrealizedPnl']), reverse=True):
                    symbol = pos['symbol'].replace('/USDT:USDT', '')
                    side = pos['side']
                    size = float(pos['contracts'])
                    entry = float(pos['entryPrice'])
                    price = float(pos['markPrice'])
                    pnl_pct = float(pos['percentage']) if pos['percentage'] else 0
                    
                    # Format color based on PNL
                    if pnl_pct > 0:
                        pnl_str = f"\033[92m{pnl_pct:.2f}%\033[0m"  # Green
                    else:
                        pnl_str = f"\033[91m{pnl_pct:.2f}%\033[0m"  # Red
                    
                    print(f"{symbol:<10} {side:<6} {size:<8.4f} ${entry:<9.2f} ${price:<9.2f} {pnl_str}")
            else:
                print("\nNo open positions")
            
            # Get recent orders
            try:
                orders = self.exchange.fetch_orders(limit=5)
                if orders:
                    print("\n🔄 RECENT ORDERS")
                    print("=" * 70)
                    print(f"{'SYMBOL':<10} {'TYPE':<8} {'SIDE':<6} {'SIZE':<8} {'PRICE':<10} {'STATUS':<10} {'TIME'}")
                    print("-" * 70)
                    
                    for order in sorted(orders, key=lambda x: x['timestamp'], reverse=True)[:5]:
                        symbol = order['symbol'].replace('/USDT:USDT', '')
                        order_type = order['type']
                        side = order['side']
                        size = float(order['amount'])
                        price = float(order['price']) if order['price'] else float(order.get('average', 0))
                        status = order['status']
                        order_time = datetime.fromtimestamp(order['timestamp']/1000).strftime('%H:%M:%S')
                        
                        status_color = ""
                        if status == 'closed':
                            status_color = "\033[92m"  # Green
                        elif status == 'canceled':
                            status_color = "\033[91m"  # Red
                        else:
                            status_color = "\033[93m"  # Yellow
                        
                        status_str = f"{status_color}{status}\033[0m"
                        print(f"{symbol:<10} {order_type:<8} {side:<6} {size:<8.4f} ${price:<9.2f} {status_str:<10} {order_time}")
            except Exception as e:
                print(f"Error fetching orders: {e}")
                    
        except Exception as e:
            print(f"Error: {e}")

    def run(self):
        """Run the debugger."""
        try:
            # Initial setup
            clear_screen()
            print("╔═══════════════════════════════════════════════════════════════╗")
            print("║          Multi-Symbol Trading Debugger                        ║")
            print("║                                                               ║")
            print(f"║  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                               ║")
            print(f"║  💰 Live Trading Debug                                       ║")
            print("╚═══════════════════════════════════════════════════════════════╝")
            
            # Check status
            self.check_account_status()
            
            # Check strategy criteria
            self.check_strategy_criteria()
            
            print("\n✅ Debug complete")
            
        except Exception as e:
            print(f"Error running debugger: {e}")


if __name__ == "__main__":
    debugger = TradingDebugger()
    debugger.run()
