#!/usr/bin/env python3
"""
Direct order placement test to isolate balance issues.
This script tests the minimum viable order with maximum leverage.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_config
from utils.logger import get_logger
import ccxt


def test_direct_order():
    """Test direct order placement with minimal requirements."""
    config = get_config()
    logger = get_logger("DirectOrderTest")
    
    try:
        print("🧪 DIRECT ORDER PLACEMENT TEST")
        print("="*50)
        
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
        
        # Test different position sizes and leverages
        test_cases = [
            {'size': 0.001, 'leverage': 75},
            {'size': 0.001, 'leverage': 50}, 
            {'size': 0.001, 'leverage': 25},
            {'size': 0.001, 'leverage': 10},
            {'size': 0.001, 'leverage': 5},
        ]
        
        for case in test_cases:
            size = case['size']
            leverage = case['leverage']
            
            # Calculate required margin
            position_value = size * current_price
            required_margin = position_value / leverage
            
            print(f"\n📊 Test Case: {size} BTC at {leverage}x leverage")
            print(f"   Position value: ${position_value:.2f}")
            print(f"   Required margin: ${required_margin:.2f}")
            print(f"   Balance available: ${available_usdt:.2f}")
            
            if required_margin <= available_usdt * 0.8:  # 80% safety margin
                print(f"   ✅ Should work - attempting order...")
                
                try:
                    # Set leverage first
                    exchange.set_leverage(leverage, 'BTC/USDT:USDT')
                    print(f"   ✅ Leverage set to {leverage}x")
                    
                    # Place a market buy order
                    order = exchange.create_market_buy_order(
                        'BTC/USDT:USDT',
                        size,
                        None,
                        None,
                        {
                            'type': 'market',
                            'side': 'buy'
                        }
                    )
                    
                    print(f"   🎉 ORDER PLACED SUCCESSFULLY!")
                    print(f"   Order ID: {order.get('id', 'Unknown')}")
                    print(f"   Status: {order.get('status', 'Unknown')}")
                    
                    # Immediately close the position
                    print(f"   🔄 Closing position immediately...")
                    close_order = exchange.create_market_sell_order(
                        'BTC/USDT:USDT',
                        size,
                        None,
                        None,
                        {
                            'type': 'market',
                            'side': 'sell',
                            'reduceOnly': True
                        }
                    )
                    print(f"   ✅ Position closed successfully!")
                    return True
                    
                except Exception as e:
                    print(f"   ❌ Order failed: {e}")
                    continue
            else:
                print(f"   ⚠️  Insufficient balance")
        
        print(f"\n❌ All test cases failed - balance too low for any orders")
        return False
        
    except Exception as e:
        logger.error(f"Direct order test failed: {e}")
        print(f"❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Testing direct order placement with various leverage levels")
    print("This will help identify the minimum balance requirements\n")
    
    success = test_direct_order()
    
    if success:
        print("\n🎉 SUCCESS! Order placement validated")
        print("The trading bot should work with these settings")
    else:
        print("\n❌ FAILED! Need more balance or different approach")
        print("Consider:")
        print("1. Adding more USDT to your account")
        print("2. Using a smaller position size")
        print("3. Checking Bybit's minimum requirements")
