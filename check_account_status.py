#!/usr/bin/env python3
"""
Check account status - positions, orders, and detailed balance
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_config
import ccxt


def check_account_status():
    """Check detailed account status"""
    config = get_config()
    
    try:
        print("🔍 DETAILED ACCOUNT STATUS CHECK")
        print("=" * 50)
        
        # Initialize exchange
        exchange_config = config.to_ccxt_config(sandbox=False)
        exchange = ccxt.bybit(exchange_config)
        exchange.load_markets()
        
        # Get detailed balance
        balance = exchange.fetch_balance()
        print("💰 BALANCE DETAILS:")
        for currency, info in balance.items():
            if isinstance(info, dict) and (info.get('free', 0) > 0 or info.get('used', 0) > 0):
                free = info.get('free', 0)
                used = info.get('used', 0)
                total = info.get('total', 0)
                print(f"  {currency}: Free: ${free:.4f} | Used: ${used:.4f} | Total: ${total:.4f}")
        
        print("\n📊 OPEN POSITIONS:")
        try:
            positions = exchange.fetch_positions()
            open_positions = [pos for pos in positions if pos['contracts'] > 0]
            
            if open_positions:
                for pos in open_positions:
                    print(f"  {pos['symbol']}: {pos['side']} {pos['contracts']} contracts")
                    print(f"    Entry: ${pos['entryPrice']:.2f} | Mark: ${pos['markPrice']:.2f}")
                    print(f"    PnL: ${pos['unrealizedPnl']:.2f} | Margin: ${pos['initialMargin']:.2f}")
            else:
                print("  No open positions")
        except Exception as e:
            print(f"  Error fetching positions: {e}")
        
        print("\n📋 OPEN ORDERS:")
        try:
            orders = exchange.fetch_open_orders('BTC/USDT:USDT')
            
            if orders:
                for order in orders:
                    print(f"  {order['id']}: {order['side']} {order['amount']} @ ${order['price']:.2f}")
                    print(f"    Status: {order['status']} | Type: {order['type']}")
            else:
                print("  No open orders")
        except Exception as e:
            print(f"  Error fetching orders: {e}")
        
        print("\n🎯 MARGIN REQUIREMENTS:")
        try:
            # Try to get margin info
            account_info = exchange.fetch_account()
            print(f"  Account info available: {bool(account_info)}")
            
            # Check leverage settings
            try:
                leverage_info = exchange.fetch_leverage('BTC/USDT:USDT')
                print(f"  Current leverage setting: {leverage_info}")
            except:
                print("  Could not fetch leverage info")
                
        except Exception as e:
            print(f"  Error fetching margin info: {e}")
        
        # Test minimum order with exact Bybit format
        print("\n🧪 TESTING MINIMUM ORDER FORMAT:")
        
        ticker = exchange.fetch_ticker('BTC/USDT:USDT')
        current_price = ticker['last']
        print(f"Current BTC price: ${current_price:.2f}")
        
        # Test with absolute minimum requirements
        test_size = 0.001  # Minimum BTC
        
        print(f"Testing order parameters:")
        print(f"  Symbol: BTC/USDT:USDT")
        print(f"  Size: {test_size} BTC")
        print(f"  Value: ${test_size * current_price:.2f}")
        
        # Check if we can set leverage first
        try:
            print(f"\n🔧 SETTING LEVERAGE TO 75x...")
            leverage_result = exchange.set_leverage(75, 'BTC/USDT:USDT')
            print(f"Leverage set result: {leverage_result}")
        except Exception as e:
            print(f"Error setting leverage: {e}")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    check_account_status()
