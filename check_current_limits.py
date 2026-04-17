#!/usr/bin/env python3
"""
Check what's actually possible with current balance
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_config
import ccxt


def check_current_limits():
    """Check what orders are actually possible with current balance"""
    config = get_config()
    
    try:
        print("🧪 CHECKING CURRENT BALANCE LIMITS")
        print("=" * 50)
        
        # Initialize exchange
        exchange_config = config.to_ccxt_config(sandbox=False)
        exchange = ccxt.bybit(exchange_config)
        exchange.load_markets()
        
        # Get balance
        balance = exchange.fetch_balance()
        usdt_balance = balance.get('USDT', {})
        available_usdt = usdt_balance.get('free', 0)
        
        print(f"Available USDT: ${available_usdt:.2f}")
        
        # Get current price
        ticker = exchange.fetch_ticker('BTC/USDT:USDT')
        current_price = ticker['last']
        print(f"Current BTC price: ${current_price:.2f}")
        
        # Calculate maximum possible position sizes at different leverages
        print(f"\nMaximum possible positions:")
        
        for leverage in [75, 50, 25, 20, 10, 5]:
            # Calculate max position size
            max_position_value = available_usdt * leverage * 0.9  # 90% safety margin
            max_btc_size = max_position_value / current_price
            
            print(f"  At {leverage:2d}x leverage: {max_btc_size:.6f} BTC (${max_position_value:.2f} position)")
            
            # Check if meets minimum
            if max_btc_size >= 0.001:
                print(f"    ✅ Meets 0.001 BTC minimum requirement")
            else:
                print(f"    ❌ Below 0.001 BTC minimum requirement")
        
        # Calculate minimum balance needed for 0.001 BTC at different leverages
        print(f"\nMinimum balance needed for 0.001 BTC:")
        min_btc = 0.001
        position_value = min_btc * current_price
        
        for leverage in [75, 50, 25, 20, 10, 5]:
            required_margin = position_value / leverage
            required_balance = required_margin / 0.9  # Account for 90% usage
            
            print(f"  At {leverage:2d}x leverage: ${required_balance:.2f} USDT required")
            
            if required_balance <= available_usdt:
                print(f"    ✅ We have enough balance!")
                return True
            else:
                print(f"    ❌ Need ${required_balance - available_usdt:.2f} more USDT")
        
        print(f"\n💡 Recommendation:")
        print(f"   - Add more USDT to account, OR")
        print(f"   - Wait for any pending orders to settle")
        print(f"   - Current balance too low for minimum 0.001 BTC order")
        
        return False
        
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    check_current_limits()
