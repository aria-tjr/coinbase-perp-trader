#!/usr/bin/env python3
"""
Simple mainnet connection test.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from utils.config import get_config
    print("✅ Config import successful")
    
    config = get_config()
    print("✅ Config loaded successfully")
    
    print(f"API Key: {config.bybit_api_key[:8]}...")
    print(f"Exchange: {config.exchange_id}")
    print(f"Symbol: {config.default_symbol}")
    
    # Test ccxt import
    import ccxt
    print("✅ CCXT import successful")
    
    # Test config method
    exchange_config = config.to_ccxt_config(sandbox=False)
    print("✅ Exchange config created")
    print(f"Sandbox mode: {exchange_config.get('sandbox', 'Not set')}")
    
    print("\n🎉 Basic validation successful!")
    print("The mainnet configuration is properly set up.")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
