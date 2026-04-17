#!/usr/bin/env python3
"""
Trading Bot Monitor
A lightweight status monitor for the multi-symbol trading bot.
"""

import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime
import ccxt
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_config
from utils.logger import get_logger
from multi_symbol_config import MultiSymbolConfig


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """Print monitor header."""
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║          Multi-Symbol Trading Monitor                         ║")
    print("║                                                               ║")
    print(f"║  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                               ║")
    print(f"║  💰 Live Trading with {len(MultiSymbolConfig.get_active_symbols())} Symbols             ║")
    print("╚═══════════════════════════════════════════════════════════════╝")


def format_color(value, threshold=0):
    """Format text color based on value."""
    if value > threshold:
        return f"\033[92m{value}\033[0m"  # Green
    elif value < threshold:
        return f"\033[91m{value}\033[0m"  # Red
    else:
        return f"{value}"


async def monitor_trading():
    """Monitor trading activity."""
    config = get_config()
    exchange_config = config.to_ccxt_config(sandbox=False)
    exchange = ccxt.bybit(exchange_config)
    
    # Initial state
    starting_balance = None
    last_update = datetime.now()
    refresh_interval = 5  # seconds
    
    while True:
        try:
            # Clear screen and print header
            clear_screen()
            print_header()
            
            # Fetch current data
            balance = exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {})
            positions = exchange.fetch_positions()
            open_positions = [p for p in positions if float(p['contracts']) > 0]
            
            # Store initial balance for tracking
            if starting_balance is None:
                starting_balance = usdt_balance.get('total', 0)
            
            # Print account info
            print("\n📊 ACCOUNT BALANCE")
            print("-" * 50)
            print(f"Starting: ${starting_balance:.2f} USDT")
            print(f"Current:  ${usdt_balance.get('total', 0):.2f} USDT")
            print(f"Free:     ${usdt_balance.get('free', 0):.2f} USDT")
            print(f"Used:     ${usdt_balance.get('used', 0):.2f} USDT")
            
            # Calculate change
            change = usdt_balance.get('total', 0) - starting_balance
            change_pct = (change / starting_balance) * 100 if starting_balance else 0
            
            print(f"Change:   {format_color(change, 0):.2f} USDT ({format_color(change_pct, 0):.2f}%)")
            
            # Print positions
            print("\n📈 OPEN POSITIONS")
            print("-" * 50)
            if open_positions:
                print(f"{'SYMBOL':<12} {'SIDE':<6} {'SIZE':<10} {'ENTRY':<10} {'MARK':<10} {'PNL':<10} {'PNL %':<8}")
                print("-" * 70)
                
                total_pnl = 0
                for pos in open_positions:
                    symbol = pos['symbol'].replace('/USDT:USDT', '')
                    side = pos['side']
                    size = float(pos['contracts'])
                    entry_price = float(pos['entryPrice'])
                    mark_price = float(pos['markPrice'])
                    unrealized_pnl = float(pos['unrealizedPnl'])
                    pnl_percentage = float(pos['percentage']) if pos['percentage'] else 0
                    
                    total_pnl += unrealized_pnl
                    
                    print(f"{symbol:<12} {side:<6} {size:<10.4f} ${entry_price:<9.2f} ${mark_price:<9.2f} "
                          f"{format_color(unrealized_pnl, 0):<9.2f} {format_color(pnl_percentage, 0):<7.2f}%")
                
                print("-" * 70)
                print(f"TOTAL PNL: {format_color(total_pnl, 0):.2f} USDT")
            else:
                print("No open positions. Waiting for trading signals...")
                
            # Print recent trades
            print("\n🔄 RECENT TRADES")
            print("-" * 50)
            try:
                trades = exchange.fetch_my_trades(limit=5)
                if trades:
                    print(f"{'SYMBOL':<12} {'SIDE':<6} {'SIZE':<10} {'PRICE':<10} {'FEE':<8} {'TIME'}")
                    print("-" * 70)
                    
                    for trade in sorted(trades, key=lambda x: x['timestamp'], reverse=True)[:5]:
                        symbol = trade['symbol'].replace('/USDT:USDT', '')
                        side = trade['side']
                        size = float(trade['amount'])
                        price = float(trade['price'])
                        fee = float(trade['fee']['cost']) if trade['fee'] else 0
                        trade_time = datetime.fromtimestamp(trade['timestamp']/1000).strftime('%H:%M:%S')
                        
                        print(f"{symbol:<12} {side:<6} {size:<10.4f} ${price:<9.2f} "
                              f"${fee:<7.2f} {trade_time}")
                else:
                    print("No recent trades found.")
            except Exception as e:
                print(f"Error fetching trades: {str(e)}")
            
            # Print active trading pairs
            print("\n📋 ACTIVE TRADING PAIRS")
            print("-" * 50)
            symbols = MultiSymbolConfig.get_active_symbols()
            symbol_grid = []
            for i in range(0, len(symbols), 4):
                row = symbols[i:i+4]
                symbol_grid.append([s.replace('/USDT:USDT', '') for s in row])
            
            for row in symbol_grid:
                print(' | '.join(f"{s:<6}" for s in row))
            
            # Print monitor info
            print("\n🔍 MONITOR INFO")
            print("-" * 50)
            print(f"Auto-refresh: {refresh_interval} seconds")
            print(f"Last update:  {datetime.now().strftime('%H:%M:%S')}")
            print(f"Trading mode: LIVE")
            print("\nPress Ctrl+C to exit...")
            
            # Update last update time
            last_update = datetime.now()
            
            # Wait for next refresh
            await asyncio.sleep(refresh_interval)
            
        except KeyboardInterrupt:
            print("\n\nMonitor stopped by user. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {str(e)}")
            print("Retrying in 10 seconds...")
            await asyncio.sleep(10)


async def main():
    """Main function."""
    try:
        await monitor_trading()
    except KeyboardInterrupt:
        print("\nMonitor stopped by user.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMonitor stopped by user.")
