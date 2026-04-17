#!/usr/bin/env python3
"""
Quick position monitor and closer.
This script allows you to quickly monitor and close positions during testing.
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path
from typing import List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_config
from utils.logger import get_logger
from core.execution_engine import ExecutionEngine
from core.risk_manager import RiskManager
from models.positions import Position
import ccxt


class QuickPositionManager:
    """Quick position monitoring and management tool."""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(self.__class__.__name__)
        self.exchange = None
        self.execution_engine = None
    
    async def initialize(self):
        """Initialize exchange and execution engine."""
        try:
            # Initialize exchange for MAINNET
            self.exchange = ccxt.bybit({
                'apiKey': self.config.bybit_api_key,
                'secret': self.config.bybit_api_secret,
                'sandbox': False,  # Use mainnet for real testing
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap'
                }
            })
            
            self.exchange.load_markets()
            
            risk_manager = RiskManager(exchange=self.exchange)
            self.execution_engine = ExecutionEngine(
                exchange=self.exchange,
                risk_manager=risk_manager
            )
            
            self.logger.info("Position manager initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}")
            raise
    
    async def show_positions(self) -> List[Position]:
        """Display all open positions."""
        try:
            positions = await self.execution_engine.get_open_positions()
            
            if not positions:
                print("\n📊 No open positions found")
                return []
            
            print(f"\n📊 Open Positions ({len(positions)}):")
            print("-" * 80)
            print(f"{'ID':<12} {'Symbol':<12} {'Side':<6} {'Size':<12} {'Entry':<10} {'Current':<10} {'P&L':<12} {'P&L%':<8}")
            print("-" * 80)
            
            for i, pos in enumerate(positions):
                print(f"{i+1:<12} {pos.symbol:<12} {pos.side.value:<6} "
                      f"{pos.current_size:<12.6f} ${pos.entry_price:<10.2f} "
                      f"${pos.current_price:<10.2f} ${pos.unrealized_pnl:<12.2f} "
                      f"{pos.unrealized_pnl_pct:<8.2f}%")
            
            print("-" * 80)
            return positions
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []
    
    async def close_position(self, position_id: str, reason: str = "MANUAL_CLOSE"):
        """Close a specific position."""
        try:
            success = await self.execution_engine.execute_position_exit(
                position_id=position_id,
                reason=reason
            )
            
            if success:
                print(f"✅ Position {position_id} closed successfully")
            else:
                print(f"❌ Failed to close position {position_id}")
                
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            print(f"❌ Error closing position: {e}")
    
    async def close_all_positions(self):
        """Close all open positions."""
        try:
            positions = await self.execution_engine.get_open_positions()
            
            if not positions:
                print("\n📊 No positions to close")
                return
            
            print(f"\n🔄 Closing {len(positions)} positions...")
            
            for pos in positions:
                await self.close_position(pos.position_id, "CLOSE_ALL")
                await asyncio.sleep(1)  # Small delay between closes
            
            print("✅ All positions closed")
            
        except Exception as e:
            self.logger.error(f"Error closing all positions: {e}")
            print(f"❌ Error closing all positions: {e}")
    
    async def interactive_menu(self):
        """Interactive menu for position management."""
        while True:
            try:
                print("\n" + "="*50)
                print("🎯 QUICK POSITION MANAGER")
                print("="*50)
                print("1. Show positions")
                print("2. Close specific position")
                print("3. Close all positions")
                print("4. Monitor positions (auto-refresh)")
                print("5. Exit")
                print("-" * 50)
                
                choice = input("Select option (1-5): ").strip()
                
                if choice == "1":
                    await self.show_positions()
                
                elif choice == "2":
                    positions = await self.show_positions()
                    if positions:
                        try:
                            idx = int(input("Enter position number to close: ")) - 1
                            if 0 <= idx < len(positions):
                                await self.close_position(positions[idx].position_id)
                            else:
                                print("❌ Invalid position number")
                        except ValueError:
                            print("❌ Invalid input")
                
                elif choice == "3":
                    confirm = input("⚠️  Close ALL positions? (y/N): ").strip().lower()
                    if confirm == 'y':
                        await self.close_all_positions()
                    else:
                        print("Cancelled")
                
                elif choice == "4":
                    print("📊 Monitoring positions (Press Ctrl+C to stop)")
                    try:
                        while True:
                            await self.show_positions()
                            await asyncio.sleep(5)
                    except KeyboardInterrupt:
                        print("\n⏹️  Monitoring stopped")
                
                elif choice == "5":
                    print("👋 Goodbye!")
                    break
                
                else:
                    print("❌ Invalid choice")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            if self.exchange:
                await self.exchange.close()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


async def main():
    """Main execution function."""
    manager = QuickPositionManager()
    
    try:
        await manager.initialize()
        await manager.interactive_menu()
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await manager.cleanup()


if __name__ == "__main__":
    print("🎯 Quick Position Manager")
    print("Manage your trading positions easily\n")
    
    asyncio.run(main())
