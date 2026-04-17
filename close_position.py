#!/usr/bin/env python3
"""
Close existing positions to free up balance for testing
"""

import ccxt
import os
from dotenv import load_dotenv

def main():
    load_dotenv()
    
    # Initialize exchange with correct credential names
    exchange = ccxt.bybit({
        'apiKey': os.getenv('BYBIT_API_KEY'),
        'secret': os.getenv('BYBIT_API_SECRET'),  # Note: using BYBIT_API_SECRET
        'sandbox': False,
        'enableRateLimit': True,
    })
    
    print("🔄 Fetching current positions...")
    
    try:
        # Fetch all positions
        positions = exchange.fetch_positions(['BTC/USDT:USDT'])
        
        open_positions = [pos for pos in positions if abs(pos['contracts']) > 0]
        
        if not open_positions:
            print("✅ No open positions found")
            return
            
        print(f"📊 Found {len(open_positions)} open position(s)")
        
        for pos in open_positions:
            symbol = pos['symbol']
            side = pos['side']
            size = abs(pos['contracts'])
            
            print(f"  - {symbol}: {side} {size} contracts")
            
            # Close position with market order
            close_side = 'buy' if side == 'short' else 'sell'
            
            print(f"🔄 Closing {side} position with {close_side} order...")
            
            order = exchange.create_market_order(
                symbol=symbol,
                side=close_side,
                amount=size,
                params={'reduceOnly': True}
            )
            
            print(f"✅ Position closed successfully!")
            print(f"   Order ID: {order['id']}")
            print(f"   Status: {order['status']}")
            
        print("\n🎉 All positions closed successfully!")
        
    except Exception as e:
        print(f"❌ Error closing positions: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
