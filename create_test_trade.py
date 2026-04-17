#!/usr/bin/env python3
"""
Test Trade Creator
This script will create a small test trade directly to verify trading functionality.
"""

import os
import sys
from pathlib import Path
import ccxt
from decimal import Decimal
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from multi_symbol_config import MultiSymbolConfig
except ImportError:
    print("Could not import MultiSymbolConfig. Make sure you're running from the project directory.")
    sys.exit(1)

def get_bybit_credentials():
    """Get Bybit credentials from environment or file."""
    api_key = os.getenv('BYBIT_API_KEY')
    api_secret = os.getenv('BYBIT_API_SECRET')
    
    if not api_key or not api_secret:
        # Try reading from .env file
        try:
            env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
            if os.path.exists(env_file):
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
    
    return api_key, api_secret

def create_test_trade(symbol, side, size=None, leverage=None, print_only=False):
    """Create a test trade with minimal size."""
    print(f"💼 Creating test trade for {symbol} {side}")
    print("=" * 60)
    
    # Get credentials
    api_key, api_secret = get_bybit_credentials()
    
    if not api_key or not api_secret:
        print("❌ API credentials not found. Cannot proceed.")
        return False
    
    try:
        # Initialize exchange
        exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True
        })
        
        # Get symbol config
        full_symbol = f"{symbol}/USDT:USDT"
        config = MultiSymbolConfig.get_symbol_config(full_symbol)
        if not config:
            print(f"❌ Symbol {symbol} not found in configuration.")
            return False
        
        # Fetch market info
        market = exchange.market(full_symbol)
        
        # Get account balance
        balance = exchange.fetch_balance()
        usdt_balance = float(balance.get('USDT', {}).get('free', 0))
        print(f"💰 Available balance: ${usdt_balance:.2f} USDT")
        
        # Get current price
        ticker = exchange.fetch_ticker(full_symbol)
        current_price = ticker['last']
        print(f"📊 Current price: ${current_price:.4f}")
        
        # Set leverage
        if leverage is None:
            leverage = config.get('base_leverage', 5)
        
        print(f"Setting leverage to {leverage}x...")
        if not print_only:
            exchange.set_leverage(leverage, full_symbol)
        
        # Calculate position size
        min_size = config.get('min_size', 0.001)
        if size is None:
            # Use minimum size or small % of balance
            size_from_balance = (usdt_balance * 0.01) / current_price / leverage
            size = max(min_size, size_from_balance)
        
        # Round to precision
        size_precision = config.get('size_precision', 3)
        size = float(Decimal(str(size)).quantize(Decimal('0.' + '0' * size_precision)))
        
        # Calculate USD value
        usd_value = size * current_price
        
        print(f"📏 Trade size: {size} {symbol} (${usd_value:.2f} with {leverage}x leverage)")
        
        if print_only:
            print("ℹ️ Print-only mode. No order will be placed.")
            return True
        
        # Create the order
        print(f"🚀 Creating {side} order...")
        
        order = exchange.create_market_order(
            symbol=full_symbol,
            side=side.lower(),
            amount=size,
            params={
                'leverage': leverage,
                'reduceOnly': False,
                'timeInForce': 'GoodTillCancel'
            }
        )
        
        print(f"✅ Order executed: {order['id']}")
        
        # Set stop loss and take profit
        stop_loss_pct = config.get('stop_loss', 0.01)
        take_profit_pct = config.get('take_profit', 0.015)
        
        if side.lower() == 'buy':
            stop_price = current_price * (1 - stop_loss_pct)
            take_profit_price = current_price * (1 + take_profit_pct)
        else:
            stop_price = current_price * (1 + stop_loss_pct)
            take_profit_price = current_price * (1 - take_profit_pct)
        
        # Round to price precision
        price_precision = config.get('price_precision', 2)
        stop_price = float(Decimal(str(stop_price)).quantize(Decimal('0.' + '0' * price_precision)))
        take_profit_price = float(Decimal(str(take_profit_price)).quantize(Decimal('0.' + '0' * price_precision)))
        
        print(f"🛑 Setting stop loss at ${stop_price:.4f}")
        print(f"💰 Setting take profit at ${take_profit_price:.4f}")
        
        # Create stop loss order
        sl_side = 'sell' if side.lower() == 'buy' else 'buy'
        
        try:
            sl_order = exchange.create_order(
                symbol=full_symbol,
                type='stop',
                side=sl_side,
                amount=size,
                price=stop_price,
                params={
                    'stopPrice': stop_price,
                    'reduceOnly': True,
                    'timeInForce': 'GoodTillCancel',
                    'triggerPrice': stop_price
                }
            )
            print(f"✅ Stop loss order created: {sl_order['id']}")
        except Exception as e:
            print(f"⚠️ Could not set stop loss: {e}")
        
        # Create take profit order
        try:
            tp_order = exchange.create_order(
                symbol=full_symbol,
                type='limit',
                side=sl_side,
                amount=size,
                price=take_profit_price,
                params={
                    'reduceOnly': True,
                    'timeInForce': 'GoodTillCancel'
                }
            )
            print(f"✅ Take profit order created: {tp_order['id']}")
        except Exception as e:
            print(f"⚠️ Could not set take profit: {e}")
        
        print("\n🎉 Test trade created successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error creating test trade: {e}")
        return False

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Create a test trade')
    parser.add_argument('symbol', help='Symbol to trade (e.g., BTC)')
    parser.add_argument('side', choices=['buy', 'sell'], help='Trade direction')
    parser.add_argument('--size', type=float, help='Position size (in base currency)')
    parser.add_argument('--leverage', type=int, help='Leverage to use')
    parser.add_argument('--print-only', action='store_true', help='Print order details without executing')
    
    args = parser.parse_args()
    
    # Print header
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║          Test Trade Creator                                   ║")
    print("║                                                               ║")
    print(f"║  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                               ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    
    create_test_trade(args.symbol, args.side, args.size, args.leverage, args.print_only)

if __name__ == "__main__":
    main()
