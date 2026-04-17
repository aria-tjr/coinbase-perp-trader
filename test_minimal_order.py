#!/usr/bin/env python3
"""
Direct minimal order test - try to place the smallest possible order
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_config
import ccxt


def test_minimal_order():
    """Test the smallest possible order that should work"""
    config = get_config()
    
    try:
        print("🧪 MINIMAL ORDER TEST")
        print("=" * 30)
        
        # Initialize exchange
        exchange_config = config.to_ccxt_config(sandbox=False)
        exchange = ccxt.bybit(exchange_config)
        exchange.load_markets()
        
        # Get balance
        balance = exchange.fetch_balance()
        usdt_balance = balance.get('USDT', {})
        available_usdt = usdt_balance.get('free', 0)
        
        print(f"Available USDT: ${available_usdt:.4f}")
        
        # Get current price
        ticker = exchange.fetch_ticker('BTC/USDT:USDT')
        current_price = ticker['last']
        print(f"Current BTC price: ${current_price:.2f}")
        
        # Set maximum leverage
        print(f"Setting leverage to 75x...")
        try:
            exchange.set_leverage(75, 'BTC/USDT:USDT')
            print("✅ Leverage set to 75x")
        except Exception as e:
            print(f"❌ Error setting leverage: {e}")
            return False
        
        # Calculate exactly what we can afford
        safety_margin = 0.95  # Use 95% of balance
        usable_balance = available_usdt * safety_margin
        max_position_value = usable_balance * 75  # 75x leverage
        max_btc_size = max_position_value / current_price
        
        print(f"\nCalculated limits:")
        print(f"  Usable balance: ${usable_balance:.4f}")
        print(f"  Max position value: ${max_position_value:.2f}")
        print(f"  Max BTC size: {max_btc_size:.6f}")
        
        # Use slightly less than max to be safe
        test_size = min(max_btc_size * 0.9, 0.001)  # Either 90% of max or 0.001, whichever is smaller
        test_size = max(test_size, 0.001)  # But at least 0.001 (minimum)
        
        print(f"\nTesting with:")
        print(f"  Size: {test_size:.6f} BTC")
        print(f"  Value: ${test_size * current_price:.2f}")
        print(f"  Required margin: ${(test_size * current_price) / 75:.2f}")
        
        # Try to place the order
        print(f"\n🎯 PLACING MINIMAL TEST ORDER...")
        
        try:
            order = exchange.create_market_buy_order(
                'BTC/USDT:USDT',
                test_size,
                None,
                None,
                {
                    'type': 'market',
                    'side': 'buy'
                }
            )
            
            print(f"🎉 ORDER PLACED SUCCESSFULLY!")
            print(f"Order ID: {order.get('id', 'Unknown')}")
            print(f"Status: {order.get('status', 'Unknown')}")
            print(f"Amount: {order.get('amount', 'Unknown')}")
            
            # Immediately close the position
            print(f"\n🔄 Closing position immediately...")
            
            close_order = exchange.create_market_sell_order(
                'BTC/USDT:USDT',
                test_size,
                None,
                None,
                {
                    'type': 'market',
                    'side': 'sell',
                    'reduceOnly': True
                }
            )
            
            print(f"✅ POSITION CLOSED!")
            print(f"Close order ID: {close_order.get('id', 'Unknown')}")
            
            return True
            
        except Exception as e:
            print(f"❌ ORDER FAILED: {e}")
            return False
        
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    success = test_minimal_order()
    
    if success:
        print(f"\n🎉 SUCCESS! The trading system should work!")
    else:
        print(f"\n❌ FAILED! Need to investigate further")
