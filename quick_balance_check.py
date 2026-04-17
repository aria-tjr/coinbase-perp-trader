#!/usr/bin/env python3
"""
Simple balance check
"""

import sys
from pathlib import Path
import signal

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_config
import ccxt


def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")


def quick_balance_check():
    """Quick balance check with timeout"""
    config = get_config()
    
    try:
        # Set timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)  # 10 second timeout
        
        print("🔍 Quick Balance Check")
        print("=" * 25)
        
        # Initialize exchange
        exchange_config = config.to_ccxt_config(sandbox=False)
        exchange = ccxt.bybit(exchange_config)
        
        print("Connecting to exchange...")
        markets = exchange.load_markets()
        print(f"✅ Connected - {len(markets)} markets loaded")
        
        print("Fetching balance...")
        balance = exchange.fetch_balance()
        
        usdt_info = balance.get('USDT', {})
        free_usdt = usdt_info.get('free', 0)
        used_usdt = usdt_info.get('used', 0)
        total_usdt = usdt_info.get('total', 0)
        
        print(f"USDT Balance:")
        print(f"  Free: ${free_usdt:.4f}")
        print(f"  Used: ${used_usdt:.4f}")
        print(f"  Total: ${total_usdt:.4f}")
        
        signal.alarm(0)  # Cancel timeout
        
        return free_usdt
        
    except TimeoutError:
        print("❌ Operation timed out")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None
    finally:
        signal.alarm(0)  # Cancel timeout


if __name__ == "__main__":
    balance = quick_balance_check()
    
    if balance is not None:
        if balance >= 4.0:  # Need about $4 for 0.001 BTC at current prices
            print(f"\n✅ Balance sufficient for testing")
        else:
            print(f"\n⚠️  Balance too low - need to add more USDT")
            print(f"   Current: ${balance:.2f}")
            print(f"   Recommended: $10+ USDT for comfortable testing")
    else:
        print(f"\n❌ Could not check balance - API issues")
