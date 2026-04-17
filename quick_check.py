#!/usr/bin/env python3
"""
Quick Exchange Status Check
A minimal script to directly check the status of the exchange account.
"""

import os
import sys
import ccxt
import time
from datetime import datetime

def get_bybit_credentials():
    """Get Bybit credentials from environment."""
    api_key = os.getenv('BYBIT_API_KEY')
    api_secret = os.getenv('BYBIT_API_SECRET')
    
    if not api_key or not api_secret:
        # Try reading from a common location
        try:
            with open(os.path.expanduser('~/.bybit_credentials'), 'r') as f:
                lines = f.readlines()
                if len(lines) >= 2:
                    api_key = lines[0].strip()
                    api_secret = lines[1].strip()
        except:
            pass
    
    return api_key, api_secret

def main():
    """Main function."""
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║          Exchange Status Quick Check                          ║")
    print("║                                                               ║")
    print(f"║  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                               ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    
    # Get credentials
    api_key, api_secret = get_bybit_credentials()
    
    if not api_key or not api_secret:
        # Fallback to using the keys that are already working in the running bot
        import glob
        env_files = glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env*'))
        for env_file in env_files:
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            if key == 'BYBIT_API_KEY':
                                api_key = value.strip('"\'')
                            elif key == 'BYBIT_API_SECRET':
                                api_secret = value.strip('"\'')
            except:
                pass
    
    # Check if we found credentials
    if not api_key or not api_secret:
        print("\n❌ No API credentials found. Reading from running bot memory...")
        try:
            # Try to read values from running bot process
            result = os.popen("ps aux | grep multi_symbol_bot.py | grep -v grep").read()
            lines = result.strip().split('\n')
            if lines:
                print(f"✅ Bot running: {lines[0][:60]}...")
                pid = lines[0].split()[1]
                print(f"Bot PID: {pid}")
            else:
                print("❌ Bot not found running")
        except Exception as e:
            print(f"Error checking bot process: {e}")
        
        return
    
    try:
        # Initialize Bybit exchange
        print("\n🔄 Connecting to Bybit...")
        exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True
        })
        
        # Check balance
        print("📊 Fetching account balance...")
        balance = exchange.fetch_balance()
        usdt_balance = balance.get('USDT', {})
        
        print("\n💰 ACCOUNT BALANCE")
        print("-" * 40)
        print(f"Free:  ${usdt_balance.get('free', 0):.2f} USDT")
        print(f"Used:  ${usdt_balance.get('used', 0):.2f} USDT")
        print(f"Total: ${usdt_balance.get('total', 0):.2f} USDT")
        
        # Check positions
        print("\n📈 OPEN POSITIONS")
        print("-" * 60)
        positions = exchange.fetch_positions()
        open_positions = [p for p in positions if float(p['contracts']) > 0]
        
        if open_positions:
            print(f"{'SYMBOL':<10} {'SIDE':<6} {'SIZE':<8} {'ENTRY':<10} {'PRICE':<10} {'PNL %':<8}")
            print("-" * 60)
            
            for pos in sorted(open_positions, key=lambda x: float(x['percentage'] or 0), reverse=True):
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
            print("No open positions found.")
        
        # Check orders
        print("\n🔄 OPEN ORDERS")
        print("-" * 60)
        try:
            orders = exchange.fetch_open_orders()
            if orders:
                print(f"{'SYMBOL':<10} {'TYPE':<8} {'SIDE':<6} {'AMOUNT':<8} {'PRICE':<10} {'STATUS':<10}")
                print("-" * 60)
                
                for order in orders:
                    symbol = order['symbol'].replace('/USDT:USDT', '')
                    order_type = order['type']
                    side = order['side']
                    amount = float(order['amount'])
                    price = float(order['price']) if order['price'] else 0
                    status = order['status']
                    
                    print(f"{symbol:<10} {order_type:<8} {side:<6} {amount:<8.4f} ${price:<9.2f} {status:<10}")
            else:
                print("No open orders found.")
        except Exception as e:
            print(f"Error fetching orders: {e}")
            
        # Check leverage settings
        print("\n⚙️ LEVERAGE SETTINGS")
        print("-" * 60)
        try:
            from multi_symbol_config import MultiSymbolConfig
            
            symbols = MultiSymbolConfig.get_active_symbols()
            for symbol in symbols[:5]:  # Just show first 5 to avoid clutter
                try:
                    leverage_info = exchange.fetch_leverage(symbol)
                    symbol_name = symbol.replace('/USDT:USDT', '')
                    config = MultiSymbolConfig.get_symbol_config(symbol)
                    configured_lev = config.get('base_leverage', 0)
                    max_lev = config.get('max_leverage', 0)
                    
                    print(f"{symbol_name}: Current={leverage_info.get('leverage', 'N/A')}, "
                          f"Configured={configured_lev}x, Max={max_lev}x")
                except:
                    pass
            
            if len(symbols) > 5:
                print(f"...and {len(symbols)-5} more symbols")
                
        except Exception as e:
            print(f"Error fetching leverage: {e}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        
    print("\n✅ Check completed")

if __name__ == "__main__":
    main()
