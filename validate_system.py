#!/usr/bin/env python3
"""System validation script for Bybit trading bot."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

import ccxt.async_support as ccxt
from utils.config import get_config
from utils.logger import setup_logging


class SystemValidator:
    """Validates all system components."""
    
    def __init__(self):
        self.config = get_config()
        self.logger = setup_logging()
        self.results = []
    
    def log_result(self, component: str, status: bool, message: str):
        """Log validation result."""
        icon = "✅" if status else "❌"
        print(f"{icon} {component}: {message}")
        self.results.append((component, status, message))
    
    async def validate_bybit_connection(self):
        """Test Bybit API connection."""
        try:
            # Initialize Bybit exchange
            exchange = ccxt.bybit(self.config.to_ccxt_config())
            
            # Test connection by fetching markets
            markets = await exchange.load_markets()
            
            # Test specific symbol
            symbol = self.config.default_symbol
            if symbol in markets:
                # Fetch ticker to test API access
                ticker = await exchange.fetch_ticker(symbol)
                
                self.log_result(
                    "Bybit Connection", 
                    True, 
                    f"Successfully connected to {'testnet' if self.config.trading_mode == 'paper' else 'mainnet'}"
                )
                
                self.log_result(
                    "Symbol Access",
                    True,
                    f"{symbol} price: ${ticker['last']:,.2f}"
                )
                
                # Test account balance (if live mode)
                if self.config.trading_mode == 'live':
                    try:
                        balance = await exchange.fetch_balance()
                        usdt_balance = balance.get('USDT', {}).get('free', 0)
                        self.log_result(
                            "Account Balance",
                            usdt_balance > 0,
                            f"USDT Balance: ${usdt_balance:,.2f}"
                        )
                    except Exception as e:
                        self.log_result(
                            "Account Balance",
                            False,
                            f"Could not fetch balance: {str(e)}"
                        )
                else:
                    self.log_result(
                        "Paper Trading Mode",
                        True,
                        f"Using simulated balance: ${self.config.paper_trading_balance:,.2f}"
                    )
                
            else:
                self.log_result(
                    "Symbol Access",
                    False,
                    f"Symbol {symbol} not found in markets"
                )
            
            await exchange.close()
            
        except Exception as e:
            self.log_result(
                "Bybit Connection",
                False,
                f"Connection failed: {str(e)}"
            )
    
    def validate_environment(self):
        """Validate environment configuration."""
        # Check required API credentials
        if hasattr(self.config, 'bybit_api_key') and self.config.bybit_api_key:
            self.log_result(
                "API Key",
                True,
                f"API Key configured (ends with: ...{self.config.bybit_api_key[-6:]})"
            )
        else:
            self.log_result(
                "API Key",
                False,
                "BYBIT_API_KEY not configured in .env"
            )
        
        if hasattr(self.config, 'bybit_api_secret') and self.config.bybit_api_secret:
            self.log_result(
                "API Secret",
                True,
                f"API Secret configured (length: {len(self.config.bybit_api_secret)})"
            )
        else:
            self.log_result(
                "API Secret",
                False,
                "BYBIT_API_SECRET not configured in .env"
            )
        
        # Check exchange configuration
        self.log_result(
            "Exchange ID",
            self.config.exchange_id == "bybit",
            f"Exchange: {self.config.exchange_id}"
        )
        
        # Check trading mode
        self.log_result(
            "Trading Mode",
            self.config.trading_mode in ["paper", "live"],
            f"Mode: {self.config.trading_mode}"
        )
        
        # Check risk parameters
        self.log_result(
            "Risk Configuration",
            self.config.max_leverage <= 100,  # Bybit max
            f"Max Leverage: {self.config.max_leverage}x"
        )
    
    def validate_dependencies(self):
        """Check required dependencies."""
        try:
            import ccxt
            self.log_result(
                "CCXT Library",
                True,
                f"Version: {ccxt.__version__}"
            )
        except ImportError:
            self.log_result(
                "CCXT Library",
                False,
                "ccxt not installed"
            )
        
        try:
            import asyncio
            self.log_result(
                "AsyncIO Support",
                True,
                "Available"
            )
        except ImportError:
            self.log_result(
                "AsyncIO Support",
                False,
                "Not available"
            )
        
        try:
            import pandas as pd
            self.log_result(
                "Pandas",
                True,
                f"Version: {pd.__version__}"
            )
        except ImportError:
            self.log_result(
                "Pandas",
                False,
                "pandas not installed"
            )
        
        try:
            import numpy as np
            self.log_result(
                "NumPy",
                True,
                f"Version: {np.__version__}"
            )
        except ImportError:
            self.log_result(
                "NumPy",
                False,
                "numpy not installed"
            )
    
    def validate_file_structure(self):
        """Check if all required files exist."""
        required_files = [
            "main.py",
            "utils/config.py",
            "core/execution_engine.py",
            "core/risk_manager.py",
            "core/strategy_core.py",
            "models/orders.py",
            "models/positions.py"
        ]
        
        for file_path in required_files:
            path = Path(file_path)
            self.log_result(
                f"File: {file_path}",
                path.exists(),
                "Found" if path.exists() else "Missing"
            )
    
    async def run_validation(self):
        """Run complete system validation."""
        print("🔍 Validating Bybit Trading Bot System...")
        print("=" * 50)
        
        # Environment validation
        print("\n📋 Environment Configuration:")
        self.validate_environment()
        
        # Dependencies validation
        print("\n📦 Dependencies:")
        self.validate_dependencies()
        
        # File structure validation
        print("\n📁 File Structure:")
        self.validate_file_structure()
        
        # Bybit connection validation
        print("\n🌐 Bybit Connection:")
        await self.validate_bybit_connection()
        
        # Summary
        print("\n" + "=" * 50)
        total_checks = len(self.results)
        passed_checks = sum(1 for _, status, _ in self.results if status)
        
        if passed_checks == total_checks:
            print(f"🎉 All {total_checks} validation checks passed!")
            print("✅ System is ready for trading!")
            
            if self.config.trading_mode == 'paper':
                print("\n💡 Recommendation: Start with paper trading to test strategies")
                print("   Command: python main.py --symbol BTCUSDT --mode paper")
            else:
                print("\n⚠️  WARNING: Live trading mode detected!")
                print("   Make sure you've tested thoroughly in paper mode first")
            
            return True
        else:
            print(f"❌ {total_checks - passed_checks} validation checks failed!")
            print("🔧 Please fix the issues above before starting the bot")
            
            # Show failed checks
            print("\nFailed checks:")
            for component, status, message in self.results:
                if not status:
                    print(f"  ❌ {component}: {message}")
            
            return False


async def main():
    """Main validation function."""
    validator = SystemValidator()
    
    try:
        success = await validator.run_validation()
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Validation interrupted by user")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n\n💥 Validation failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
