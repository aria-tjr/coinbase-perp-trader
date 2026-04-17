#!/usr/bin/env python3
"""
Patch script to make trading more aggressive.
This will modify strategy parameters to find more trading opportunities.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from strategies.momentum_breakout import MomentumBreakoutStrategy
from strategies.mean_reversion import MeanReversionStrategy

print("🔧 PATCHING STRATEGY PARAMETERS FOR MORE AGGRESSIVE TRADING")
print("=" * 70)

# Modify momentum breakout strategy
print("Updating MomentumBreakoutStrategy parameters...")
MomentumBreakoutStrategy.atr_multiplier = 1.5
MomentumBreakoutStrategy.lookback_period = 15
MomentumBreakoutStrategy.min_adx = 20.0
MomentumBreakoutStrategy.volume_multiplier = 1.2
MomentumBreakoutStrategy.min_rsi_long = 40
MomentumBreakoutStrategy.max_rsi_short = 60
print("✓ MomentumBreakoutStrategy updated")

# Modify mean reversion strategy
print("Updating MeanReversionStrategy parameters...")
MeanReversionStrategy.lookback_period = 15
MeanReversionStrategy.z_score_threshold = 1.8
MeanReversionStrategy.max_adx = 30.0
MeanReversionStrategy.min_bb_width = 0.0008
MeanReversionStrategy.max_bb_width = 0.025
MeanReversionStrategy.rsi_oversold = 35
MeanReversionStrategy.rsi_overbought = 65
print("✓ MeanReversionStrategy updated")

print("\n💥 Strategy parameters successfully patched!")
print("Bot should now find more trading opportunities")
print("\nRestart the bot to apply changes")
