"""
Multi-Symbol Trading Configuration

Defines trading pairs and their specific configurations for multi-symbol trading.
"""

from typing import Dict, List, Optional
from decimal import Decimal


class MultiSymbolConfig:
    """Configuration for multi-symbol trading."""
    
    # Trading pairs configuration
    TRADING_PAIRS = {
        "BTC/USDT:USDT": {
            "name": "Bitcoin",
            "min_size": 0.001,
            "size_precision": 3,
            "price_precision": 2,
            "base_leverage": 20,  # Increased from 5x to 20x
            "max_leverage": 50,
            "position_size_pct": 0.012,  # 1.2% of balance per symbol
            "stop_loss": 0.006,  # 0.6%
            "take_profit": 0.009,  # 0.9%
            "priority": 1,  # Higher priority = more allocation
        },
        "ETH/USDT:USDT": {
            "name": "Ethereum", 
            "min_size": 0.01,
            "size_precision": 2,
            "price_precision": 2,
            "base_leverage": 20,  # Increased from 5x to 20x
            "max_leverage": 50,
            "position_size_pct": 0.009,  # 0.9% of balance per symbol
            "stop_loss": 0.007,  # 0.7%
            "take_profit": 0.01,  # 1.0%
            "priority": 2,
        },
        "SOL/USDT:USDT": {
            "name": "Solana",
            "min_size": 0.1,
            "size_precision": 1,
            "price_precision": 3,
            "base_leverage": 15,  # Increased from 4x to 15x
            "max_leverage": 40,
            "position_size_pct": 0.006,  # 0.6% of balance per symbol
            "stop_loss": 0.008,  # 0.8%
            "take_profit": 0.012,  # 1.2%
            "priority": 3,
        },
        "ADA/USDT:USDT": {
            "name": "Cardano",
            "min_size": 1.0,
            "size_precision": 0,
            "price_precision": 4,
            "base_leverage": 15,  # Increased from 4x to 15x
            "max_leverage": 40,
            "position_size_pct": 0.005,  # 0.5% of balance per symbol
            "stop_loss": 0.01,  # 1.0%
            "take_profit": 0.015,  # 1.5%
            "priority": 4,
        },
        "LTC/USDT:USDT": {
            "name": "Litecoin",
            "min_size": 0.01,
            "size_precision": 2,
            "price_precision": 2,
            "base_leverage": 10,  # 10x leverage
            "max_leverage": 30,
            "position_size_pct": 0.004,  # 0.4% of balance per symbol
            "stop_loss": 0.012,  # 1.2%
            "take_profit": 0.018,  # 1.8%
            "priority": 5,
        },
        "LINK/USDT:USDT": {
            "name": "Chainlink",
            "min_size": 0.1,
            "size_precision": 1,
            "price_precision": 3,
            "base_leverage": 15,  # Increased from 4x to 15x
            "max_leverage": 40,
            "position_size_pct": 0.005,  # 0.5% of balance per symbol
            "stop_loss": 0.009,  # 0.9%
            "take_profit": 0.013,  # 1.3%
            "priority": 6,
        },
        "AVAX/USDT:USDT": {
            "name": "Avalanche",
            "min_size": 0.01,
            "size_precision": 2,
            "price_precision": 3,
            "base_leverage": 12,  # Increased from 4x to 12x
            "max_leverage": 35,
            "position_size_pct": 0.004,  # 0.4% of balance per symbol
            "stop_loss": 0.01,  # 1.0%
            "take_profit": 0.015,  # 1.5%
            "priority": 7,
        },
        "DOT/USDT:USDT": {
            "name": "Polkadot",
            "min_size": 0.1,
            "size_precision": 1,
            "price_precision": 3,
            "base_leverage": 12,  # Increased from 4x to 12x
            "max_leverage": 35,
            "position_size_pct": 0.003,  # 0.3% of balance per symbol
            "stop_loss": 0.01,  # 1.0%
            "take_profit": 0.015,  # 1.5%
            "priority": 8,
        },
        "ATOM/USDT:USDT": {
            "name": "Cosmos",
            "min_size": 0.1,
            "size_precision": 1,
            "price_precision": 3,
            "base_leverage": 10,  # Increased from 3x to 10x
            "max_leverage": 30,
            "position_size_pct": 0.003,  # 0.3% of balance per symbol
            "stop_loss": 0.011,  # 1.1%
            "take_profit": 0.016,  # 1.6%
            "priority": 9,
        },
        "UNI/USDT:USDT": {
            "name": "Uniswap",
            "min_size": 0.1,
            "size_precision": 1,
            "price_precision": 3,
            "base_leverage": 10,  # Increased from 3x to 10x
            "max_leverage": 30,
            "position_size_pct": 0.003,  # 0.3% of balance per symbol
            "stop_loss": 0.012,  # 1.2%
            "take_profit": 0.018,  # 1.8%
            "priority": 10,
        },
        "NEAR/USDT:USDT": {
            "name": "Near Protocol",
            "min_size": 0.1,
            "size_precision": 1,
            "price_precision": 3,
            "base_leverage": 8,  # Increased from 3x to 8x
            "max_leverage": 25,
            "position_size_pct": 0.002,  # 0.2% of balance per symbol
            "stop_loss": 0.013,  # 1.3%
            "take_profit": 0.02,  # 2.0%
            "priority": 11,
        },
        "XRP/USDT:USDT": {
            "name": "Ripple",
            "min_size": 1.0,
            "size_precision": 0,
            "price_precision": 4,
            "base_leverage": 8,  # 8x leverage
            "max_leverage": 25,
            "position_size_pct": 0.002,  # 0.2% of balance per symbol
            "stop_loss": 0.014,  # 1.4%
            "take_profit": 0.021,  # 2.1%
            "priority": 12,
        },
        "ALGO/USDT:USDT": {
            "name": "Algorand",
            "min_size": 1.0,
            "size_precision": 0,
            "price_precision": 4,
            "base_leverage": 8,  # Increased from 3x to 8x
            "max_leverage": 25,
            "position_size_pct": 0.002,  # 0.2% of balance per symbol
            "stop_loss": 0.015,  # 1.5%
            "take_profit": 0.022,  # 2.2%
            "priority": 13,
        }
    }
    
    # Risk management for multi-symbol trading
    MULTI_SYMBOL_RISK_CONFIG = {
        "max_total_exposure": 0.06,  # Maximum 6% of balance across all symbols
        "max_concurrent_positions": 5,  # Maximum 5 positions open at once
        "correlation_limit": 0.7,  # Don't open highly correlated positions
        "rebalance_interval": 300,  # Rebalance every 5 minutes
        "max_symbols_active": 8,  # Maximum symbols to trade simultaneously
        "tier_allocation": {
            # Tier 1: Major coins (higher allocation)
            "tier_1": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
            "tier_1_max_allocation": 0.018,  # 1.8% max per tier 1 symbol
            # Tier 2: Large caps (medium allocation)  
            "tier_2": ["SOL/USDT:USDT", "ADA/USDT:USDT", "LINK/USDT:USDT", "AVAX/USDT:USDT"],
            "tier_2_max_allocation": 0.01,  # 1.0% max per tier 2 symbol
            # Tier 3: Mid caps (lower allocation)
            "tier_3": ["LTC/USDT:USDT", "DOT/USDT:USDT", "ATOM/USDT:USDT", "UNI/USDT:USDT", "NEAR/USDT:USDT", "XRP/USDT:USDT", "ALGO/USDT:USDT"],
            "tier_3_max_allocation": 0.005,  # 0.5% max per tier 3 symbol
        }
    }
    
    @classmethod
    def get_active_symbols(cls) -> List[str]:
        """Get list of active trading symbols ordered by priority."""
        symbols = list(cls.TRADING_PAIRS.keys())
        # Sort by priority (lower number = higher priority)
        symbols.sort(key=lambda x: cls.TRADING_PAIRS[x]["priority"])
        return symbols
    
    @classmethod
    def get_symbol_config(cls, symbol: str) -> Dict:
        """Get configuration for a specific symbol."""
        return cls.TRADING_PAIRS.get(symbol, {})
    
    @classmethod
    def get_total_position_allocation(cls) -> float:
        """Get total position allocation across all symbols."""
        return sum(config["position_size_pct"] for config in cls.TRADING_PAIRS.values())
    
    @classmethod
    def validate_configuration(cls) -> bool:
        """Validate multi-symbol configuration."""
        total_allocation = cls.get_total_position_allocation()
        max_exposure = cls.MULTI_SYMBOL_RISK_CONFIG["max_total_exposure"]
        
        if total_allocation > max_exposure:
            print(f"⚠️ Warning: Total allocation ({total_allocation:.1%}) exceeds max exposure ({max_exposure:.1%})")
            return False
        
        print(f"✅ Configuration valid - Total allocation: {total_allocation:.1%}")
        return True
    
    @classmethod
    def get_risk_config(cls) -> Dict:
        """Get multi-symbol risk configuration."""
        return cls.MULTI_SYMBOL_RISK_CONFIG.copy()
    
    @classmethod
    def get_symbol_tier(cls, symbol: str) -> str:
        """Get the tier classification for a symbol."""
        risk_config = cls.get_risk_config()
        
        if symbol in risk_config["tier_allocation"]["tier_1"]:
            return "tier_1"
        elif symbol in risk_config["tier_allocation"]["tier_2"]:
            return "tier_2"
        elif symbol in risk_config["tier_allocation"]["tier_3"]:
            return "tier_3"
        else:
            return "unknown"
    
    @classmethod
    def get_tier_max_allocation(cls, symbol: str) -> float:
        """Get maximum allocation for a symbol based on its tier."""
        tier = cls.get_symbol_tier(symbol)
        risk_config = cls.get_risk_config()
        
        tier_key = f"{tier}_max_allocation"
        return risk_config["tier_allocation"].get(tier_key, 0.005)  # Default 0.5%
    
    @classmethod
    def get_symbols_by_tier(cls, tier: str) -> List[str]:
        """Get all symbols in a specific tier."""
        risk_config = cls.get_risk_config()
        return risk_config["tier_allocation"].get(tier, [])
    
    @classmethod
    def validate_tier_allocations(cls) -> bool:
        """Validate that symbol allocations don't exceed tier limits."""
        warnings = []
        
        for symbol, config in cls.TRADING_PAIRS.items():
            current_allocation = config["position_size_pct"]
            max_allocation = cls.get_tier_max_allocation(symbol)
            tier = cls.get_symbol_tier(symbol)
            
            if current_allocation > max_allocation:
                warnings.append(
                    f"⚠️ {symbol} ({tier}): {current_allocation:.1%} > {max_allocation:.1%} limit"
                )
        
        if warnings:
            print("\n".join(warnings))
            return False
        
        return True


if __name__ == "__main__":
    # Test configuration
    print("🔧 Multi-Symbol Trading Configuration")
    print("=" * 50)
    
    config = MultiSymbolConfig()
    
    print(f"Active symbols: {len(config.get_active_symbols())} pairs")
    print(f"Total allocation: {config.get_total_position_allocation():.1%}")
    print(f"Max exposure: {config.get_risk_config()['max_total_exposure']:.1%}")
    
    print("\n📊 Symbol Details by Tier:")
    
    # Display by tiers
    for tier_name in ["tier_1", "tier_2", "tier_3"]:
        symbols = config.get_symbols_by_tier(tier_name)
        if symbols:
            print(f"\n{tier_name.upper()} (Max {config.get_risk_config()['tier_allocation'][f'{tier_name}_max_allocation']:.1%} each):")
            for symbol in symbols:
                if symbol in config.TRADING_PAIRS:
                    details = config.get_symbol_config(symbol)
                    print(f"  {symbol}: {details['name']} - {details['position_size_pct']:.1%} allocation")
    
    print(f"\n✅ Configuration valid: {config.validate_configuration()}")
    print(f"✅ Tier allocations valid: {config.validate_tier_allocations()}")
    
    print(f"\n🎯 Risk Settings:")
    risk_config = config.get_risk_config()
    print(f"  Max concurrent positions: {risk_config['max_concurrent_positions']}")
    print(f"  Max active symbols: {risk_config['max_symbols_active']}")
    print(f"  Correlation limit: {risk_config['correlation_limit']}")
    print(f"  Rebalance interval: {risk_config['rebalance_interval']}s")
