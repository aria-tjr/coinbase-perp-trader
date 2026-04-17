#!/usr/bin/env python3
"""
Mainnet connection validation script.
This script validates that we can connect to Bybit mainnet and retrieve basic account info.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_config
from utils.logger import get_logger
import ccxt


async def validate_mainnet_connection():
    """Validate mainnet connection and account access."""
    config = get_config()
    logger = get_logger("MainnetValidator")
    
    try:
        print("🔗 VALIDATING MAINNET CONNECTION")
        print("="*50)
        
        # Initialize exchange with mainnet
        exchange_config = config.to_ccxt_config(sandbox=False)
        exchange = ccxt.bybit(exchange_config)
        
        # Test connection
        print("1. Testing exchange connection...")
        exchange.load_markets()
        print("   ✅ Exchange connection successful")
        
        # Test authentication
        print("2. Testing authentication...")
        account = exchange.fetch_balance()
        print("   ✅ Authentication successful")
        
        # Display account summary
        print("\n📊 ACCOUNT SUMMARY (MAINNET)")
        print("-" * 40)
        
        # USDT balance
        usdt_balance = account.get('USDT', {})
        free_usdt = usdt_balance.get('free', 0)
        used_usdt = usdt_balance.get('used', 0)
        total_usdt = usdt_balance.get('total', 0)
        
        print(f"USDT Balance:")
        print(f"  Free: {free_usdt:.2f} USDT")
        print(f"  Used: {used_usdt:.2f} USDT")
        print(f"  Total: {total_usdt:.2f} USDT")
        
        # Current BTC price
        print("\n3. Testing market data access...")
        ticker = exchange.fetch_ticker('BTC/USDT:USDT')
        btc_price = ticker['last']
        print(f"   ✅ Market data access successful")
        print(f"   Current BTC Price: ${btc_price:,.2f}")
        
        # Test order size calculations
        print("\n📏 TEST ORDER CALCULATIONS")
        print("-" * 40)
        test_size = 0.001  # BTC
        test_value = test_size * btc_price
        print(f"Test position size: {test_size} BTC")
        print(f"Test position value: ${test_value:.2f}")
        
        # Check if we have enough balance
        if total_usdt >= test_value * 2:  # 2x for margin
            print("   ✅ Sufficient balance for test orders")
        else:
            print(f"   ⚠️  Low balance - need ${test_value * 2:.2f} for safe testing")
        
        # Test position checking
        print("\n4. Testing position access...")
        positions = exchange.fetch_positions()
        open_positions = [pos for pos in positions if pos['contracts'] > 0]
        print(f"   ✅ Position access successful")
        print(f"   Open positions: {len(open_positions)}")
        
        if open_positions:
            print("\n   Current Open Positions:")
            for pos in open_positions:
                print(f"   - {pos['symbol']}: {pos['side']} {pos['contracts']} contracts")
        
        # No need to close synchronous exchange
        
        print("\n🎉 MAINNET VALIDATION COMPLETE!")
        print("="*50)
        print("✅ Connection: SUCCESS")
        print("✅ Authentication: SUCCESS") 
        print("✅ Market Data: SUCCESS")
        print("✅ Account Access: SUCCESS")
        print("✅ Position Access: SUCCESS")
        print("\n🚀 Ready for aggressive testing!")
        
        return True
        
    except Exception as e:
        logger.error(f"Mainnet validation failed: {e}")
        print(f"\n❌ VALIDATION FAILED: {e}")
        
        if "API key" in str(e).lower():
            print("\n💡 Check your API credentials in .env file")
        elif "permission" in str(e).lower():
            print("\n💡 Check your API key permissions on Bybit")
        elif "network" in str(e).lower():
            print("\n💡 Check your internet connection")
        
        if 'exchange' in locals():
            pass  # No need to close sync exchange
        
        return False


async def main():
    """Main validation function."""
    print("🔍 BYBIT MAINNET VALIDATION")
    print("This will test your mainnet connection and credentials")
    print("Press Ctrl+C to cancel\n")
    
    try:
        success = await validate_mainnet_connection()
        if success:
            print("\n✨ You're ready to run the aggressive test!")
            print("Run: python test_aggressive_trading.py")
        else:
            print("\n❌ Fix the issues above before testing")
            
    except KeyboardInterrupt:
        print("\n⚠️  Validation cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
