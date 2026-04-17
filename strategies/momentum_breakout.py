"""Momentum breakout strategy with ATR-based signals and pyramiding."""

import numpy as np
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.feature_engineering import MarketFeatures
from models.positions import Position
from utils.logger import get_logger


@dataclass
class BreakoutSignal:
    """Breakout signal information."""
    symbol: str
    direction: str  # 'long' or 'short'
    strength: float  # 0-1 signal strength
    entry_price: Decimal
    stop_price: Decimal
    target_price: Decimal
    atr: float
    breakout_level: Decimal
    volume_confirmation: bool
    reason: str


class MomentumBreakoutStrategy:
    """ATR-based momentum breakout strategy with dynamic pyramiding."""
    
    def __init__(self, atr_multiplier: float = 1.5, lookback_period: int = 15):
        """
        Initialize momentum breakout strategy.
        
        Args:
            atr_multiplier: Multiplier for ATR to determine breakout levels
            lookback_period: Period for calculating highs/lows
        """
        self.logger = get_logger(self.__class__.__name__)
        self.atr_multiplier = atr_multiplier
        self.lookback_period = lookback_period
        
        # Strategy parameters - MORE AGGRESSIVE SETTINGS
        self.min_adx = 20.0  # Reduced minimum ADX for trend strength
        self.volume_multiplier = 1.2  # Reduced volume requirement
        self.min_rsi_long = 40  # Lower minimum RSI for long entries
        self.max_rsi_short = 60  # Higher maximum RSI for short entries
        
        # Pyramiding parameters
        self.max_pyramids = 3
        self.pyramid_atr_distance = 1.0  # ATRs between pyramid entries
        self.pyramid_size_reduction = 0.5  # Each pyramid is 50% of previous
        
        # Tracking
        self.recent_highs: Dict[str, List[float]] = {}
        self.recent_lows: Dict[str, List[float]] = {}
        self.breakout_levels: Dict[str, Dict] = {}
        self.pyramid_levels: Dict[str, List[float]] = {}
        
        self.logger.info("Momentum breakout strategy initialized")
    
    def analyze(self, features: MarketFeatures, 
               current_positions: List[Position]) -> Optional[BreakoutSignal]:
        """
        Analyze market for breakout opportunities.
        
        Args:
            features: Current market features
            current_positions: Current open positions
            
        Returns:
            BreakoutSignal if opportunity found, None otherwise
        """
        symbol = features.symbol
        
        # Update price tracking
        self._update_price_history(symbol, features.price)
        
        # Check if we already have maximum positions
        symbol_positions = [p for p in current_positions if p.symbol == symbol]
        if len(symbol_positions) >= self.max_pyramids:
            return None
        
        # Check for existing pyramid opportunity
        if symbol_positions:
            pyramid_signal = self._check_pyramid_opportunity(features, symbol_positions[0])
            if pyramid_signal:
                return pyramid_signal
        
        # Check trend strength
        if features.adx < self.min_adx:
            return None  # No strong trend
        
        # Calculate breakout levels
        if symbol not in self.breakout_levels or self._should_recalculate_levels(symbol):
            self._calculate_breakout_levels(symbol, features)
        
        # Check for breakout
        levels = self.breakout_levels.get(symbol, {})
        if not levels:
            return None
        
        # Long breakout
        if (features.price > levels['resistance'] and 
            features.rsi > self.min_rsi_long and
            features.macd > features.macd_signal):
            
            # Volume confirmation
            volume_confirmed = self._check_volume_confirmation(features)
            
            # Calculate signal strength
            strength = self._calculate_signal_strength(
                features, 'long', volume_confirmed
            )
            
            if strength > 0.3:  # Minimum signal strength
                return BreakoutSignal(
                    symbol=symbol,
                    direction='long',
                    strength=strength,
                    entry_price=Decimal(str(features.price)),
                    stop_price=Decimal(str(features.price - features.atr * 1.5)),
                    target_price=Decimal(str(features.price + features.atr * 3)),
                    atr=features.atr,
                    breakout_level=Decimal(str(levels['resistance'])),
                    volume_confirmation=volume_confirmed,
                    reason=f"Breakout above resistance {levels['resistance']:.2f}"
                )
        
        # Short breakout
        elif (features.price < levels['support'] and 
              features.rsi < self.max_rsi_short and
              features.macd < features.macd_signal):
            
            # Volume confirmation
            volume_confirmed = self._check_volume_confirmation(features)
            
            # Calculate signal strength
            strength = self._calculate_signal_strength(
                features, 'short', volume_confirmed
            )
            
            if strength > 0.3:  # Minimum signal strength
                return BreakoutSignal(
                    symbol=symbol,
                    direction='short',
                    strength=strength,
                    entry_price=Decimal(str(features.price)),
                    stop_price=Decimal(str(features.price + features.atr * 1.5)),
                    target_price=Decimal(str(features.price - features.atr * 3)),
                    atr=features.atr,
                    breakout_level=Decimal(str(levels['support'])),
                    volume_confirmation=volume_confirmed,
                    reason=f"Breakout below support {levels['support']:.2f}"
                )
        
        return None
    
    def _update_price_history(self, symbol: str, price: float):
        """Update price history for breakout calculations."""
        if symbol not in self.recent_highs:
            self.recent_highs[symbol] = []
            self.recent_lows[symbol] = []
        
        self.recent_highs[symbol].append(price)
        self.recent_lows[symbol].append(price)
        
        # Keep only lookback period
        if len(self.recent_highs[symbol]) > self.lookback_period:
            self.recent_highs[symbol] = self.recent_highs[symbol][-self.lookback_period:]
            self.recent_lows[symbol] = self.recent_lows[symbol][-self.lookback_period:]
    
    def _calculate_breakout_levels(self, symbol: str, features: MarketFeatures):
        """Calculate dynamic breakout levels."""
        if symbol not in self.recent_highs or len(self.recent_highs[symbol]) < 10:
            return
        
        # Calculate recent high/low
        recent_high = max(self.recent_highs[symbol])
        recent_low = min(self.recent_lows[symbol])
        
        # Adjust levels with ATR
        atr_buffer = features.atr * self.atr_multiplier
        
        self.breakout_levels[symbol] = {
            'resistance': recent_high + atr_buffer * 0.5,  # Slight buffer above high
            'support': recent_low - atr_buffer * 0.5,      # Slight buffer below low
            'calculated_at': datetime.now(),
            'atr': features.atr
        }
        
        self.logger.debug(
            f"Breakout levels for {symbol}: "
            f"Resistance={self.breakout_levels[symbol]['resistance']:.2f}, "
            f"Support={self.breakout_levels[symbol]['support']:.2f}"
        )
    
    def _should_recalculate_levels(self, symbol: str) -> bool:
        """Check if breakout levels should be recalculated."""
        if symbol not in self.breakout_levels:
            return True
        
        # Recalculate every hour
        last_calc = self.breakout_levels[symbol].get('calculated_at')
        if last_calc and (datetime.now() - last_calc) > timedelta(hours=1):
            return True
        
        return False
    
    def _check_pyramid_opportunity(self, features: MarketFeatures, 
                                 base_position: Position) -> Optional[BreakoutSignal]:
        """Check if we should add to winning position (pyramid)."""
        # Position must be profitable
        if base_position.unrealized_pnl_pct < 0.5:  # At least 0.5% profit
            return None
        
        # Check pyramid levels
        if base_position.position_id not in self.pyramid_levels:
            self.pyramid_levels[base_position.position_id] = [float(base_position.entry_price)]
        
        pyramid_count = len(self.pyramid_levels[base_position.position_id]) - 1
        if pyramid_count >= self.max_pyramids - 1:
            return None
        
        # Calculate next pyramid level
        last_entry = self.pyramid_levels[base_position.position_id][-1]
        
        if base_position.is_long:
            next_level = last_entry + features.atr * self.pyramid_atr_distance
            
            if features.price >= next_level and features.rsi > 50:
                # Momentum still strong
                strength = min(0.8, features.adx / 100 + 0.3)
                
                return BreakoutSignal(
                    symbol=features.symbol,
                    direction='long',
                    strength=strength * (1 - pyramid_count * 0.2),  # Reduce strength for pyramids
                    entry_price=Decimal(str(features.price)),
                    stop_price=Decimal(str(features.price - features.atr * 1.2)),
                    target_price=Decimal(str(features.price + features.atr * 2)),
                    atr=features.atr,
                    breakout_level=Decimal(str(next_level)),
                    volume_confirmation=True,
                    reason=f"Pyramid entry #{pyramid_count + 1} at {next_level:.2f}"
                )
        
        else:  # Short position
            next_level = last_entry - features.atr * self.pyramid_atr_distance
            
            if features.price <= next_level and features.rsi < 50:
                # Momentum still strong
                strength = min(0.8, features.adx / 100 + 0.3)
                
                return BreakoutSignal(
                    symbol=features.symbol,
                    direction='short',
                    strength=strength * (1 - pyramid_count * 0.2),  # Reduce strength for pyramids
                    entry_price=Decimal(str(features.price)),
                    stop_price=Decimal(str(features.price + features.atr * 1.2)),
                    target_price=Decimal(str(features.price - features.atr * 2)),
                    atr=features.atr,
                    breakout_level=Decimal(str(next_level)),
                    volume_confirmation=True,
                    reason=f"Pyramid entry #{pyramid_count + 1} at {next_level:.2f}"
                )
        
        return None
    
    def _check_volume_confirmation(self, features: MarketFeatures) -> bool:
        """Check if volume confirms the breakout."""
        # Use trade intensity as proxy for volume
        # High trade intensity suggests increased activity
        return features.trade_intensity > 100  # More than 100 trades per minute
    
    def _calculate_signal_strength(self, features: MarketFeatures, 
                                 direction: str, volume_confirmed: bool) -> float:
        """Calculate breakout signal strength (0-1)."""
        strength = 0.0
        
        # ADX component (trend strength)
        adx_score = min(1.0, features.adx / 50)  # Max score at ADX 50
        strength += adx_score * 0.3
        
        # Momentum component
        if direction == 'long':
            # RSI momentum
            rsi_score = max(0, (features.rsi - 50) / 30)  # 0 at RSI 50, 1 at RSI 80
            strength += rsi_score * 0.2
            
            # MACD momentum
            if features.macd > features.macd_signal:
                macd_score = min(1.0, abs(features.macd - features.macd_signal) / features.atr)
                strength += macd_score * 0.2
        
        else:  # short
            # RSI momentum
            rsi_score = max(0, (50 - features.rsi) / 30)  # 0 at RSI 50, 1 at RSI 20
            strength += rsi_score * 0.2
            
            # MACD momentum
            if features.macd < features.macd_signal:
                macd_score = min(1.0, abs(features.macd_signal - features.macd) / features.atr)
                strength += macd_score * 0.2
        
        # Volume confirmation
        if volume_confirmed:
            strength += 0.15
        
        # Volatility component (prefer moderate volatility)
        if 0.15 < features.realized_vol_1h < 0.5:
            vol_score = 1.0 - abs(features.realized_vol_1h - 0.3) / 0.3
            strength += vol_score * 0.15
        
        return min(1.0, strength)
    
    def should_exit_position(self, position: Position, features: MarketFeatures) -> Tuple[bool, str]:
        """
        Check if position should be exited based on momentum loss.
        
        Returns:
            Tuple of (should_exit, reason)
        """
        # Check momentum exhaustion
        if position.is_long:
            # Exit if momentum turns bearish
            if (features.rsi < 30 or 
                features.macd < features.macd_signal * 0.8 or
                features.adx < 20):
                return True, "momentum_exhaustion"
            
            # Exit if price breaks below key level
            if position.position_id in self.pyramid_levels:
                first_entry = self.pyramid_levels[position.position_id][0]
                if features.price < first_entry - features.atr:
                    return True, "support_break"
        
        else:  # Short position
            # Exit if momentum turns bullish
            if (features.rsi > 70 or 
                features.macd > features.macd_signal * 1.2 or
                features.adx < 20):
                return True, "momentum_exhaustion"
            
            # Exit if price breaks above key level
            if position.position_id in self.pyramid_levels:
                first_entry = self.pyramid_levels[position.position_id][0]
                if features.price > first_entry + features.atr:
                    return True, "resistance_break"
        
        return False, ""
    
    def update_pyramid_tracking(self, position_id: str, entry_price: float):
        """Update pyramid level tracking for a position."""
        if position_id not in self.pyramid_levels:
            self.pyramid_levels[position_id] = []
        
        self.pyramid_levels[position_id].append(entry_price)
    
    def clear_position_tracking(self, position_id: str):
        """Clear tracking data for closed position."""
        if position_id in self.pyramid_levels:
            del self.pyramid_levels[position_id]
