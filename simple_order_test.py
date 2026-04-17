#!/usr/bin/env python3
"""
Simple order test to check minimum requirements
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from utils.config import get_config
import ccxt

def main():
    print("🧪 SIMPLE ORDER TEST")
    print("="*40)
    
    # Initialize exchange
    config = get_config()
    exchange_config = config.to_ccxt_config(sandbox=False)
    exchange = ccxt.bybit(exchange_config)
    
    print("Loading markets...")
    exchange.load_markets()
    
    # Get balance
    print("Fetching balance...")
    balance = exchange.fetch_balance()
    usdt_balance = balance.get('USDT', {})
    available_usdt = usdt_balance.get('free', 0)
    
    print(f"Available USDT: ${available_usdt:.2f}")
    
    # Get current price
    print("Fetching BTC price...")
    ticker = exchange.fetch_ticker('BTC/USDT:USDT')
    current_price = ticker['last']
    print(f"Current BTC price: ${current_price:.2f}")
    
    # Test very small order
    test_size = 0.001  # 0.001 BTC
    test_leverage = 10  # Conservative leverage
    
    position_value = test_size * current_price
    required_margin = position_value / test_leverage
    
    print(f"\nTest parameters:")
    print(f"  Size: {test_size} BTC")
    print(f"  Leverage: {test_leverage}x")
    print(f"  Position value: ${position_value:.2f}")
    print(f"  Required margin: ${required_margin:.2f}")
    print(f"  Available balance: ${available_usdt:.2f}")
    
    if required_margin > available_usdt:
        print("❌ Insufficient balance even for this small order")
        return
    
    try:
        print(f"\nSetting leverage to {test_leverage}x...")
        exchange.set_leverage(test_leverage, 'BTC/USDT:USDT')
        print("✅ Leverage set successfully")
        
        print(f"\nPlacing market buy order for {test_size} BTC...")
        order = exchange.create_market_buy_order(
            'BTC/USDT:USDT',
            test_size,
            None,
            None,
            {}
        )
        
        print(f"🎉 ORDER PLACED!")
        print(f"Order ID: {order.get('id')}")
        print(f"Status: {order.get('status')}")
        print(f"Amount: {order.get('amount')}")
        print(f"Cost: ${order.get('cost', 0):.2f}")
        
        # Wait a moment then close
        print(f"\nClosing position...")
        close_order = exchange.create_market_sell_order(
            'BTC/USDT:USDT',
            test_size,
            None,
            None,
            {'reduceOnly': True}
        )
        print(f"✅ Position closed!")
        print(f"Close order ID: {close_order.get('id')}")
        
    except Exception as e:
        print(f"❌ Order failed: {e}")
        print(f"Error type: {type(e).__name__}")

if __name__ == "__main__":
    main()
