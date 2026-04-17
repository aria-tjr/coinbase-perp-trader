#!/usr/bin/env python3
"""
Market Conditions Scanner
This script checks current market conditions across major crypto exchanges
to identify potential trading opportunities.
"""

import sys
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
import time

# Technical analysis functions
def calculate_rsi(closes, periods=14):
    """Calculate RSI."""
    closes = pd.Series(closes)
    delta = closes.diff()
    gain = delta.where(delta > 0, 0).rolling(window=periods).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=periods).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50

def calculate_bb_width(closes, periods=20, std_dev=2):
    """Calculate Bollinger Band width."""
    closes = pd.Series(closes)
    sma = closes.rolling(window=periods).mean().iloc[-1]
    std = closes.rolling(window=periods).std().iloc[-1]
    
    if pd.isna(sma) or pd.isna(std):
        return 0
    
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    
    return (upper - lower) / sma * 100  # As percentage

def calculate_volatility(closes, periods=14):
    """Calculate historical volatility."""
    closes = pd.Series(closes)
    log_returns = np.log(closes / closes.shift(1))
    return log_returns.rolling(window=periods).std().iloc[-1] * np.sqrt(365) * 100  # Annualized %

def main():
    """Main function."""
    print("=" * 70)
    print("CRYPTO MARKET CONDITIONS SCANNER")
    print(f"Scan time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Define symbols we're interested in
    symbols = [
        "BTC/USDT", 
        "ETH/USDT",
        "SOL/USDT",
        "ADA/USDT",
        "LTC/USDT",
        "LINK/USDT",
        "AVAX/USDT",
        "DOT/USDT",
        "ATOM/USDT",
        "UNI/USDT",
        "NEAR/USDT",
        "XRP/USDT",
        "ALGO/USDT"
    ]
    
    # Initialize exchange
    exchange = ccxt.bybit()
    
    results = []
    for symbol in symbols:
        try:
            # Fetch OHLCV data
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=25)
            
            # Convert to dataframe
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Calculate indicators
            rsi = calculate_rsi(df['close'])
            bb_width = calculate_bb_width(df['close'])
            volatility = calculate_volatility(df['close'])
            
            # Trend detection (simple approach)
            sma_20 = df['close'].rolling(window=20).mean().iloc[-1]
            sma_10 = df['close'].rolling(window=10).mean().iloc[-1]
            current_price = df['close'].iloc[-1]
            
            if current_price > sma_10 > sma_20:
                trend = "↗️ UPTREND"
            elif current_price < sma_10 < sma_20:
                trend = "↘️ DOWNTREND"
            else:
                trend = "↔️ SIDEWAYS"
                
            # Recent momentum
            change_1h = (df['close'].iloc[-1] / df['close'].iloc[-2] - 1) * 100
            change_3h = (df['close'].iloc[-1] / df['close'].iloc[-4] - 1) * 100
                
            # Trading opportunity score (0-100)
            opportunity_score = 50
            
            # Adjust for RSI (extreme values indicate potential reversal)
            if rsi < 30:  # Oversold
                opportunity_score += 20
            elif rsi > 70:  # Overbought
                opportunity_score += 10
                
            # Adjust for volatility (higher volatility = more opportunities)
            if volatility > 80:
                opportunity_score += 15
            elif volatility > 50:
                opportunity_score += 10
            elif volatility < 30:
                opportunity_score -= 10
                
            # Adjust for BB width (narrower bands can signal upcoming breakout)
            if bb_width < 1.5:
                opportunity_score += 15
                
            # Adjust for recent momentum
            if abs(change_1h) > 2:
                opportunity_score += 10
                
            # Get ticker for current price
            ticker = exchange.fetch_ticker(symbol)
                
            # Store results
            results.append({
                "symbol": symbol.replace("/USDT", ""),
                "price": ticker['last'],
                "change_1h": change_1h,
                "change_3h": change_3h,
                "rsi": rsi,
                "volatility": volatility,
                "bb_width": bb_width,
                "trend": trend,
                "opportunity": min(100, max(0, int(opportunity_score)))
            })
                
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
    
    # Sort by opportunity score
    results = sorted(results, key=lambda x: x['opportunity'], reverse=True)
    
    # Print results
    print("\nCRYPTO MARKET OPPORTUNITIES")
    print(f"{'SYMBOL':<8} {'PRICE':<10} {'CHG 1H':<8} {'RSI':<6} {'VOL%':<6} {'TREND':<12} {'SCORE'}")
    print("-" * 70)
    
    for r in results:
        # Format change with color and direction
        if r['change_1h'] > 0:
            change_str = f"\033[92m+{r['change_1h']:.2f}%\033[0m"
        else:
            change_str = f"\033[91m{r['change_1h']:.2f}%\033[0m"
            
        # Format opportunity score with color
        if r['opportunity'] >= 80:
            score_str = f"\033[92m{r['opportunity']}\033[0m"  # Green
        elif r['opportunity'] >= 60:
            score_str = f"\033[93m{r['opportunity']}\033[0m"  # Yellow
        else:
            score_str = f"{r['opportunity']}"
            
        print(f"{r['symbol']:<8} {r['price']:<10.2f} {change_str:<8} {r['rsi']:<6.1f} "
              f"{r['volatility']:<6.1f} {r['trend']:<12} {score_str}")
    
    print("\nPOTENTIAL ENTRY SIGNALS")
    print("-" * 70)
    
    # Check for potential entry signals
    for r in results:
        signals = []
        
        # RSI signals
        if r['rsi'] < 30:
            signals.append(f"Oversold (RSI={r['rsi']:.1f})")
        elif r['rsi'] > 70:
            signals.append(f"Overbought (RSI={r['rsi']:.1f})")
            
        # Volatility signals
        if r['volatility'] < 30 and r['bb_width'] < 1.5:
            signals.append("Low volatility + narrow bands (potential breakout)")
        
        # Momentum signals
        if abs(r['change_1h']) > 3:
            direction = "bullish" if r['change_1h'] > 0 else "bearish"
            signals.append(f"Strong {direction} momentum ({r['change_1h']:.2f}%)")
            
        if signals:
            print(f"{r['symbol']}: {' | '.join(signals)}")
    
    print("\nSCAN COMPLETE")
    
if __name__ == "__main__":
    main()
