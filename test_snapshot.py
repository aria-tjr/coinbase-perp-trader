#!/usr/bin/env python3
"""
Quick test to check market snapshot structure
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from utils.config import get_config
    from core.market_data_collector_ccxt import MarketDataCollectorCCXT
    import asyncio
    
    async def test_market_snapshot():
        config = get_config()
        print(f"Using symbol: {config.default_symbol}")
        
        collector = MarketDataCollectorCCXT(symbols=[config.default_symbol])
        await collector.initialize()
        
        # Start collection briefly
        task = asyncio.create_task(collector.run())
        
        # Wait a bit for data
        await asyncio.sleep(3)
        
        # Get snapshot
        snapshot = collector.get_market_snapshot(config.default_symbol)
        
        if snapshot:
            print(f"Snapshot type: {type(snapshot)}")
            print(f"Snapshot attributes: {dir(snapshot)}")
            print(f"Symbol: {snapshot.symbol}")
            print(f"Timestamp: {snapshot.timestamp}")
            
            # Check if it has ticker
            if hasattr(snapshot, 'ticker') and snapshot.ticker:
                print(f"Ticker price: {snapshot.ticker.price}")
        else:
            print("No snapshot available")
        
        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        await collector.close()

    asyncio.run(test_market_snapshot())
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
