"""Test script for MarketDataCollector."""

import asyncio
import signal
import sys
from datetime import datetime

from core import MarketDataCollector
from utils import setup_logging


# Global flag for graceful shutdown
shutdown_flag = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global shutdown_flag
    print("\nShutdown signal received. Closing connections...")
    shutdown_flag = True


async def on_orderbook(orderbook):
    """Handle orderbook updates."""
    print(f"\n📊 ORDERBOOK UPDATE - {orderbook.symbol}")
    print(f"   Best Bid: ${orderbook.best_bid.price:.2f} ({orderbook.best_bid.size:.4f})")
    print(f"   Best Ask: ${orderbook.best_ask.price:.2f} ({orderbook.best_ask.size:.4f})")
    print(f"   Spread: ${orderbook.spread:.2f} ({orderbook.spread_percentage:.3f}%)")
    print(f"   Imbalance: {orderbook.get_order_imbalance():.3f}")


async def on_trade(trade):
    """Handle trade updates."""
    side_emoji = "🟢" if trade.side.value == "buy" else "🔴"
    print(f"\n{side_emoji} TRADE - {trade.symbol}: ${trade.price:.2f} x {trade.size:.4f} = ${trade.value:.2f}")


async def on_ticker(ticker):
    """Handle ticker updates."""
    change_emoji = "📈" if ticker.price_change_24h > 0 else "📉"
    print(f"\n{change_emoji} TICKER - {ticker.symbol}")
    print(f"   Price: ${ticker.last_price:.2f} ({ticker.price_change_percentage_24h:+.2f}%)")
    print(f"   24h Volume: {ticker.volume_24h:.2f}")
    print(f"   24h Range: ${ticker.low_24h:.2f} - ${ticker.high_24h:.2f}")


async def on_funding(funding):
    """Handle funding rate updates."""
    print(f"\n💰 FUNDING - {funding.symbol}")
    print(f"   Rate: {funding.rate:.4%} (Annualized: {funding.annualized_rate:.2%})")
    print(f"   Next: {funding.next_funding_time}")


async def on_snapshot(snapshot):
    """Handle complete market snapshot."""
    print(f"\n🔄 MARKET SNAPSHOT - {snapshot.symbol} @ {snapshot.timestamp.strftime('%H:%M:%S')}")
    if snapshot.orderbook:
        print(f"   Mid Price: ${snapshot.orderbook.mid_price:.2f}")
    if snapshot.ticker:
        print(f"   Last Price: ${snapshot.ticker.last_price:.2f}")
    print(f"   Trade Flow Imbalance (60s): {snapshot.get_trade_flow_imbalance():.3f}")
    vwap = snapshot.get_vwap()
    if vwap:
        print(f"   VWAP (5m): ${vwap:.2f}")


async def main():
    """Main test function."""
    # Setup logging
    logger = setup_logging()
    logger.info("Starting MarketDataCollector test...")
    
    # Test symbol - using BTC perpetual
    symbols = ["BTC-USD-PERP", "BTC-USDC-PERP"]  # Try different symbol formats
    
    # Create collector
    collector = MarketDataCollector(symbols)
    
    # Add callbacks
    collector.add_callback('orderbook', on_orderbook)
    collector.add_callback('trade', on_trade)
    collector.add_callback('ticker', on_ticker)
    collector.add_callback('funding', on_funding)
    collector.add_callback('snapshot', on_snapshot)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create tasks
    tasks = []
    
    # Start collector
    collector_task = asyncio.create_task(collector.run())
    tasks.append(collector_task)
    
    # Status monitoring task
    async def monitor_status():
        while not shutdown_flag:
            await asyncio.sleep(30)
            if collector.is_connected:
                avg_latency = collector.get_average_latency()
                msg_rate = collector.get_message_rate()
                logger.info(f"📊 Status - Connected: ✅ | Latency: {avg_latency:.1f}ms | Rate: {msg_rate:.1f} msg/s")
            else:
                logger.warning("📊 Status - Connected: ❌")
    
    monitor_task = asyncio.create_task(monitor_status())
    tasks.append(monitor_task)
    
    # Wait for shutdown
    while not shutdown_flag:
        await asyncio.sleep(1)
    
    # Cleanup
    logger.info("Shutting down...")
    await collector.disconnect()
    
    # Cancel tasks
    for task in tasks:
        task.cancel()
    
    # Wait for tasks to complete
    await asyncio.gather(*tasks, return_exceptions=True)
    
    logger.info("Test completed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
