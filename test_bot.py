#!/usr/bin/env python3
"""
Comprehensive bot testing script.
This script provides multiple test modes for validating the trading bot functionality.
"""

import asyncio
import argparse
import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from test_aggressive_trading import AggressiveTestTrader
from position_manager import QuickPositionManager
from aggressive_config import print_aggressive_config_summary


class BotTester:
    """Comprehensive bot testing framework."""
    
    def __init__(self):
        self.test_results = {
            'order_placement': False,
            'position_monitoring': False,
            'position_closure': False,
            'config_restoration': False
        }
    
    async def run_quick_order_test(self):
        """Run a quick order placement test."""
        print("\n🚀 QUICK ORDER PLACEMENT TEST")
        print("="*50)
        
        trader = AggressiveTestTrader()
        
        try:
            await trader.initialize()
            success = await trader.run_aggressive_test()
            
            self.test_results['order_placement'] = trader.order_placed
            self.test_results['position_monitoring'] = success
            self.test_results['position_closure'] = success
            self.test_results['config_restoration'] = True
            
            return success
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            return False
        finally:
            await trader.cleanup()
    
    async def run_position_manager(self):
        """Run the position manager tool."""
        print("\n🎯 POSITION MANAGER")
        print("="*50)
        
        manager = QuickPositionManager()
        
        try:
            await manager.initialize()
            await manager.interactive_menu()
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            await manager.cleanup()
    
    def print_test_results(self):
        """Print comprehensive test results."""
        print("\n" + "="*60)
        print("📊 TEST RESULTS SUMMARY")
        print("="*60)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{test_name.replace('_', ' ').title():<25} {status}")
        
        print("="*60)
        
        all_passed = all(self.test_results.values())
        if all_passed:
            print("🎉 ALL TESTS PASSED! Bot is ready for trading!")
        else:
            print("⚠️  Some tests failed. Please review the logs.")
        
        print("="*60)
    
    def show_help(self):
        """Show help information."""
        print("\n" + "="*60)
        print("🤖 BOT TESTING TOOLKIT")
        print("="*60)
        print("Available test modes:")
        print()
        print("1. Quick Test (--quick)")
        print("   • Places a test order with aggressive settings")
        print("   • Monitors the position for 30 seconds")
        print("   • Closes the position automatically")
        print("   • Restores original settings")
        print()
        print("2. Position Manager (--positions)")
        print("   • Interactive tool to monitor positions")
        print("   • Can close individual or all positions")
        print("   • Real-time position monitoring")
        print()
        print("3. Config Info (--config)")
        print("   • Shows aggressive configuration details")
        print("   • Explains parameter changes")
        print()
        print("4. Help (--help)")
        print("   • Shows this help information")
        print()
        print("USAGE EXAMPLES:")
        print("  python test_bot.py --quick           # Quick order test")
        print("  python test_bot.py --positions       # Position manager")
        print("  python test_bot.py --config          # Show config info")
        print()
        print("SAFETY NOTES:")
        print("  • All tests use Bybit testnet (sandbox mode)")
        print("  • Test positions are small (0.001 BTC)")
        print("  • Aggressive settings are temporary")
        print("  • Original settings are always restored")
        print("="*60)


async def main():
    """Main test execution function."""
    parser = argparse.ArgumentParser(description="Bot Testing Toolkit")
    parser.add_argument("--quick", action="store_true", help="Run quick order placement test")
    parser.add_argument("--positions", action="store_true", help="Run position manager")
    parser.add_argument("--config", action="store_true", help="Show aggressive config info")
    
    args = parser.parse_args()
    
    tester = BotTester()
    
    if args.quick:
        print("🔥 Starting Quick Order Placement Test...")
        print("This will test the bot's ability to place and manage orders")
        print("Press Ctrl+C to stop at any time\n")
        
        success = await tester.run_quick_order_test()
        tester.print_test_results()
        
        if success:
            print("\n💡 Next steps:")
            print("  1. Bot is ready for normal trading")
            print("  2. Use 'python test_bot.py --positions' to monitor positions")
            print("  3. Review logs for detailed information")
        
    elif args.positions:
        await tester.run_position_manager()
        
    elif args.config:
        print_aggressive_config_summary()
        
    else:
        tester.show_help()


if __name__ == "__main__":
    print("🤖 Trading Bot Test Suite")
    print("Testing order placement and position management\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        sys.exit(1)
