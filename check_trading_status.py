#!/usr/bin/env python3
"""
Trading Status Checker
A simple script to check the current trading status, balance, and positions.
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime
import ccxt

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_config
from utils.logger import get_logger


async def check_trading_status():
    """Check current trading status, balance, and positions."""
    config = get_config()
    logger = get_logger("StatusChecker")
    
    try:
        # Initialize exchange with mainnet
        exchange_config = config.to_ccxt_config(sandbox=False)
        exchange = ccxt.bybit(exchange_config)
        
        print("╔═══════════════════════════════════════════════════════════════╗")
        print("║          Multi-Symbol Trading Status Check                    ║")
        print("║                                                               ║")
        print("║  🔍 Live Status Check for Multi-Symbol Trading Bot           ║")
        print(f"║  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                               ║")
        print("╚═══════════════════════════════════════════════════════════════╝")
        print("\n📊 ACCOUNT STATUS")
        print("=" * 50)
        
        # Get account balance
        account = exchange.fetch_balance()
        usdt_balance = account.get('USDT', {})
        free_usdt = usdt_balance.get('free', 0)
        used_usdt = usdt_balance.get('used', 0)
        total_usdt = usdt_balance.get('total', 0)
        
        print(f"USDT Balance:")
        print(f"  Free:  ${free_usdt:.2f} USDT")
        print(f"  Used:  ${used_usdt:.2f} USDT")
        print(f"  Total: ${total_usdt:.2f} USDT")
        
        # Get open positions
        print("\n📈 OPEN POSITIONS")
        print("=" * 50)
        positions = exchange.fetch_positions()
        open_positions = [pos for pos in positions if float(pos['contracts']) > 0]
        
        if open_positions:
            print(f"Found {len(open_positions)} open positions:\n")
            
            # Print header
            print(f"{'SYMBOL':<12} {'SIDE':<6} {'SIZE':<10} {'ENTRY':<10} {'MARK':<10} {'PNL':<10} {'PNL %':<8}")
            print("-" * 70)
            
            # Print positions
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
                
                # Format colors with ANSI codes
                side_color = '\033[92m' if side == 'long' else '\033[91m'  # Green for long, red for short
                pnl_color = '\033[92m' if unrealized_pnl >= 0 else '\033[91m'  # Green for profit, red for loss
                reset = '\033[0m'  # Reset color
                
                print(f"{symbol:<12} {side_color}{side:<6}{reset} {size:<10.4f} ${entry_price:<9.2f} ${mark_price:<9.2f} "
                      f"{pnl_color}${unrealized_pnl:<9.2f}{reset} {pnl_color}{pnl_percentage:<7.2f}%{reset}")
            
            # Print total PNL
            print("-" * 70)
            total_color = '\033[92m' if total_pnl >= 0 else '\033[91m'
            print(f"TOTAL PNL: {total_color}${total_pnl:.2f}{reset}")
            
        else:
            print("No open positions found.")
            
        # Check recent orders
        print("\n🔄 RECENT ORDERS")
        print("=" * 50)
        
        try:
            orders = exchange.fetch_orders(limit=5)
            if orders:
                print(f"Last {min(len(orders), 5)} orders:\n")
                print(f"{'SYMBOL':<12} {'TYPE':<8} {'SIDE':<6} {'AMOUNT':<10} {'PRICE':<10} {'STATUS':<10} {'TIME'}")
                print("-" * 80)
                
                for order in sorted(orders, key=lambda x: x['timestamp'], reverse=True)[:5]:
                    symbol = order['symbol'].replace('/USDT:USDT', '')
                    order_type = order['type']
                    side = order['side']
                    amount = float(order['amount'])
                    price = float(order['price']) if order['price'] else 0
                    status = order['status']
                    order_time = datetime.fromtimestamp(order['timestamp']/1000).strftime('%H:%M:%S')
                    
                    # Format colors
                    side_color = '\033[92m' if side == 'buy' else '\033[91m'
                    status_color = '\033[92m' if status == 'closed' else '\033[93m'
                    
                    print(f"{symbol:<12} {order_type:<8} {side_color}{side:<6}{reset} {amount:<10.4f} "
                          f"${price:<9.2f} {status_color}{status:<10}{reset} {order_time}")
            else:
                print("No recent orders found.")
        except Exception as e:
            print(f"Error fetching orders: {e}")
        
        # Get current market data for top symbols
        print("\n💹 CURRENT MARKET DATA")
        print("=" * 50)
        top_symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT']
        
        for symbol in top_symbols:
            try:
                ticker = exchange.fetch_ticker(symbol)
                symbol_display = symbol.replace('/USDT:USDT', '')
                last_price = ticker['last']
                change_pct = ticker['percentage'] if 'percentage' in ticker else 0
                
                # Format color
                price_color = '\033[92m' if change_pct >= 0 else '\033[91m'
                
                print(f"{symbol_display}: {price_color}${last_price:,.2f} ({change_pct:+.2f}%){reset}")
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")
                
        # Check if there are any USDT profits realized today
        print("\n💲 PROFIT SUMMARY")
        print("=" * 50)
        
        try:
            # This is a placeholder - actual profit calculation would depend on your specific implementation
            # You might need to implement a proper profit tracking in your bot
            print("Current Total PnL: " + (f"{total_color}${total_pnl:.2f}{reset}" if 'total_pnl' in locals() else "$0.00"))
            print("Note: For detailed profit analysis, check the trading logs")
        except Exception as e:
            print(f"Error getting profit summary: {e}")
            
        print("\n✅ Status check completed successfully!")
        
        return True
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        print(f"\n❌ STATUS CHECK FAILED: {e}")
        
        if "API key" in str(e).lower():
            print("\n💡 Check your API credentials in .env file")
        elif "permission" in str(e).lower():
            print("\n💡 Check your API key permissions on Bybit")
        elif "network" in str(e).lower():
            print("\n💡 Check your internet connection")
        
        return False


async def main():
    """Main function to run status check."""
    print("🔍 MULTI-SYMBOL TRADING STATUS CHECK")
    print("This will check your current trading status, balance, and positions")
    print("-" * 60)
    
    try:
        await check_trading_status()
    except KeyboardInterrupt:
        print("\n⚠️  Status check cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
