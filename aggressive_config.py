#!/usr/bin/env python3
"""
Aggressive strategy configuration for testing order placement.
This temporarily overrides strategy parameters to be extremely aggressive.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import get_logger


class AggressiveStrategyConfig:
    """Configuration for extremely aggressive strategy parameters."""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.original_params = {}
    
    def apply_aggressive_momentum_params(self, strategy):
        """Apply aggressive parameters to momentum breakout strategy."""
        if hasattr(strategy, 'min_adx'):
            self.original_params['momentum'] = {
                'min_adx': strategy.min_adx,
                'volume_multiplier': strategy.volume_multiplier,
                'min_rsi_long': strategy.min_rsi_long,
                'max_rsi_short': strategy.max_rsi_short,
                'atr_multiplier': strategy.atr_multiplier,
                'lookback_period': strategy.lookback_period
            }
            
            # Make extremely aggressive
            strategy.min_adx = 15.0  # Much lower ADX requirement
            strategy.volume_multiplier = 1.1  # Lower volume requirement
            strategy.min_rsi_long = 30  # Much lower RSI for long
            strategy.max_rsi_short = 70  # Much higher RSI for short
            strategy.atr_multiplier = 1.0  # Smaller ATR multiplier
            strategy.lookback_period = 10  # Shorter lookback
            
            self.logger.warning("🔥 AGGRESSIVE momentum parameters applied:")
            self.logger.warning(f"  - ADX threshold: {strategy.min_adx}")
            self.logger.warning(f"  - Volume multiplier: {strategy.volume_multiplier}")
            self.logger.warning(f"  - RSI long threshold: {strategy.min_rsi_long}")
            self.logger.warning(f"  - RSI short threshold: {strategy.max_rsi_short}")
    
    def apply_aggressive_mean_reversion_params(self, strategy):
        """Apply aggressive parameters to mean reversion strategy."""
        if hasattr(strategy, 'z_score_threshold'):
            self.original_params['mean_reversion'] = {
                'z_score_threshold': strategy.z_score_threshold,
                'rsi_oversold': strategy.rsi_oversold,
                'rsi_overbought': strategy.rsi_overbought,
                'max_adx': strategy.max_adx,
                'min_bb_width': strategy.min_bb_width,
                'max_bb_width': strategy.max_bb_width
            }
            
            # Make extremely aggressive
            strategy.z_score_threshold = 0.5  # Much lower z-score threshold
            strategy.rsi_oversold = 40  # Higher RSI oversold
            strategy.rsi_overbought = 60  # Lower RSI overbought
            strategy.max_adx = 40  # Higher ADX allowed
            strategy.min_bb_width = 0.01  # Lower BB width requirement
            strategy.max_bb_width = 0.10  # Higher BB width allowed
            
            self.logger.warning("🔥 AGGRESSIVE mean reversion parameters applied:")
            self.logger.warning(f"  - Z-score threshold: {strategy.z_score_threshold}")
            self.logger.warning(f"  - RSI oversold: {strategy.rsi_oversold}")
            self.logger.warning(f"  - RSI overbought: {strategy.rsi_overbought}")
            self.logger.warning(f"  - Max ADX: {strategy.max_adx}")
    
    def apply_aggressive_risk_params(self, risk_manager):
        """Apply aggressive parameters to risk manager."""
        if hasattr(risk_manager, 'base_leverage'):
            self.original_params['risk'] = {
                'base_leverage': risk_manager.base_leverage,
                'current_leverage': risk_manager.current_leverage,
                'max_position_size_pct': risk_manager.max_position_size_pct,
                'position_stop_loss': risk_manager.position_stop_loss,
                'position_take_profit': risk_manager.position_take_profit,
                'daily_drawdown_limit': risk_manager.daily_drawdown_limit
            }
            
            # Make extremely aggressive
            risk_manager.base_leverage = 10
            risk_manager.current_leverage = 10.0
            risk_manager.max_position_size_pct = 0.10  # 10% per position
            risk_manager.position_stop_loss = 0.05  # 5% stop loss
            risk_manager.position_take_profit = 0.08  # 8% take profit
            risk_manager.daily_drawdown_limit = 0.20  # 20% daily drawdown
            
            self.logger.warning("🔥 AGGRESSIVE risk parameters applied:")
            self.logger.warning(f"  - Leverage: {risk_manager.current_leverage}x")
            self.logger.warning(f"  - Position size: {risk_manager.max_position_size_pct:.1%}")
            self.logger.warning(f"  - Stop loss: {risk_manager.position_stop_loss:.1%}")
            self.logger.warning(f"  - Take profit: {risk_manager.position_take_profit:.1%}")
    
    def restore_original_params(self, momentum_strategy=None, mean_reversion_strategy=None, risk_manager=None):
        """Restore original parameters."""
        self.logger.info("🔄 RESTORING ORIGINAL PARAMETERS")
        
        # Restore momentum strategy
        if momentum_strategy and 'momentum' in self.original_params:
            params = self.original_params['momentum']
            momentum_strategy.min_adx = params['min_adx']
            momentum_strategy.volume_multiplier = params['volume_multiplier']
            momentum_strategy.min_rsi_long = params['min_rsi_long']
            momentum_strategy.max_rsi_short = params['max_rsi_short']
            momentum_strategy.atr_multiplier = params['atr_multiplier']
            momentum_strategy.lookback_period = params['lookback_period']
            self.logger.info("✅ Momentum strategy parameters restored")
        
        # Restore mean reversion strategy
        if mean_reversion_strategy and 'mean_reversion' in self.original_params:
            params = self.original_params['mean_reversion']
            mean_reversion_strategy.z_score_threshold = params['z_score_threshold']
            mean_reversion_strategy.rsi_oversold = params['rsi_oversold']
            mean_reversion_strategy.rsi_overbought = params['rsi_overbought']
            mean_reversion_strategy.max_adx = params['max_adx']
            mean_reversion_strategy.min_bb_width = params['min_bb_width']
            mean_reversion_strategy.max_bb_width = params['max_bb_width']
            self.logger.info("✅ Mean reversion strategy parameters restored")
        
        # Restore risk manager
        if risk_manager and 'risk' in self.original_params:
            params = self.original_params['risk']
            risk_manager.base_leverage = params['base_leverage']
            risk_manager.current_leverage = params['current_leverage']
            risk_manager.max_position_size_pct = params['max_position_size_pct']
            risk_manager.position_stop_loss = params['position_stop_loss']
            risk_manager.position_take_profit = params['position_take_profit']
            risk_manager.daily_drawdown_limit = params['daily_drawdown_limit']
            self.logger.info("✅ Risk manager parameters restored")
        
        self.logger.success("All original parameters restored")
    
    def create_artificial_signal_conditions(self):
        """Create conditions that will trigger signals immediately."""
        return {
            'force_momentum_long': {
                'rsi': 35,  # Just above aggressive threshold
                'adx': 20,  # Just above aggressive threshold
                'macd_bullish': True,
                'volume_spike': True,
                'price_breakout': True
            },
            'force_momentum_short': {
                'rsi': 65,  # Just below aggressive threshold
                'adx': 20,  # Just above aggressive threshold
                'macd_bearish': True,
                'volume_spike': True,
                'price_breakdown': True
            },
            'force_mean_reversion_long': {
                'rsi': 35,  # Just below aggressive overbought
                'z_score': -0.8,  # Just below aggressive threshold
                'bb_position': 0.1,  # Near lower band
                'adx': 25  # Low trend strength
            },
            'force_mean_reversion_short': {
                'rsi': 65,  # Just above aggressive oversold
                'z_score': 0.8,  # Just above aggressive threshold
                'bb_position': 0.9,  # Near upper band
                'adx': 25  # Low trend strength
            }
        }


def print_aggressive_config_summary():
    """Print summary of aggressive configuration changes."""
    print("\n" + "="*60)
    print("🔥 AGGRESSIVE STRATEGY CONFIGURATION 🔥")
    print("="*60)
    print("MOMENTUM BREAKOUT CHANGES:")
    print("  • ADX threshold: 25 → 15 (easier trend detection)")
    print("  • Volume multiplier: 1.5x → 1.1x (lower volume requirement)")
    print("  • RSI long: 45 → 30 (more oversold entries)")
    print("  • RSI short: 55 → 70 (more overbought entries)")
    print("  • ATR multiplier: 2.0 → 1.0 (tighter breakouts)")
    print()
    print("MEAN REVERSION CHANGES:")
    print("  • Z-score threshold: 2.0 → 0.5 (easier mean reversion)")
    print("  • RSI oversold: 30 → 40 (higher oversold threshold)")
    print("  • RSI overbought: 70 → 60 (lower overbought threshold)")
    print("  • Max ADX: 30 → 40 (allow more trending markets)")
    print()
    print("RISK MANAGEMENT CHANGES:")
    print("  • Leverage: 5x → 10x (higher leverage)")
    print("  • Position size: 1% → 10% (larger positions)")
    print("  • Stop loss: 0.6% → 5% (wider stops)")
    print("  • Take profit: 0.9% → 8% (wider targets)")
    print("  • Daily drawdown: 5% → 20% (higher risk tolerance)")
    print("="*60)
    print("⚠️  WARNING: These are EXTREME test parameters!")
    print("⚠️  Use only for testing order placement functionality!")
    print("="*60)


if __name__ == "__main__":
    print_aggressive_config_summary()
