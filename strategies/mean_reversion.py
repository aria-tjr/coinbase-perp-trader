"""Mean reversion micro-scalping strategy for consolidation zones."""

import numpy as np
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timedelta

from core.feature_engineering import MarketFeatures
from models.positions import Position
from utils.logger import get_logger


@dataclass
class MeanReversionSignal:
    """Mean reversion signal information."""
    symbol: str
    direction: str  # 'long' or 'short'
    strength: float  # 0-1 signal strength
    entry_price: Decimal
    stop_price: Decimal
    target_price: Decimal
    deviation_score: float
    consolidation_strength: float
    reason: str


class MeanReversionStrategy:
    """Micro-scalping strategy for range-bound markets."""
    
    def __init__(self, lookback_period: int = 15, z_score_threshold: float = 1.8):
        """
        Initialize mean reversion strategy.
        
        Args:
            lookback_period: Period for calculating mean and standard deviation
            z_score_threshold: Z-score threshold for entry signals
        """
        self.logger = get_logger(self.__class__.__name__)
        self.lookback_period = lookback_period
        self.z_score_threshold = z_score_threshold
        
        # Strategy parameters - MORE AGGRESSIVE SETTINGS
        self.max_adx = 30.0  # Increased max ADX to catch more opportunities 
        self.min_bb_width = 0.0008  # Lower minimum Bollinger Band width (0.08%)
        self.max_bb_width = 0.025   # Increased maximum Bollinger Band width (2.5%)
        self.rsi_oversold = 35      # Less extreme oversold level
        self.rsi_overbought = 65    # Less extreme overbought level
        
        # Micro-scalp parameters
        self.target_profit_pct = 0.003  # 0.3% target per trade
        self.stop_loss_pct = 0.002      # 0.2% stop loss
        self.max_hold_minutes = 30      # Maximum holding time
        
        # Market structure tracking
        self.price_history: Dict[str, deque] = {}
        self.support_resistance: Dict[str, Dict] = {}
        self.consolidation_scores: Dict[str, float] = {}
        
        self.logger.info("Mean reversion strategy initialized")
    
    def analyze(self, features: MarketFeatures, 
               current_positions: List[Position]) -> Optional[MeanReversionSignal]:
        """
        Analyze market for mean reversion opportunities.
        
        Args:
            features: Current market features
            current_positions: Current open positions
            
        Returns:
            MeanReversionSignal if opportunity found, None otherwise
        """
        symbol = features.symbol
        
        # Update price history
        self._update_price_history(symbol, features.price)
        
        # Check if we already have a position in this symbol
        if any(p.symbol == symbol for p in current_positions):
            return None
        
        # Check for consolidation (low ADX)
        if features.adx > self.max_adx:
            return None  # Trending market, not suitable for mean reversion
        
        # Check Bollinger Band width
        bb_width_pct = features.bb_width / features.price
        if bb_width_pct < self.min_bb_width or bb_width_pct > self.max_bb_width:
            return None
        
        # Calculate consolidation score
        consolidation_score = self._calculate_consolidation_score(features)
        if consolidation_score < 0.5:
            return None
        
        # Calculate z-score
        z_score = self._calculate_z_score(symbol, features.price)
        if abs(z_score) < self.z_score_threshold:
            return None
        
        # Long signal (oversold in consolidation)
        if (z_score < -self.z_score_threshold and 
            features.price < features.bb_lower and
            features.rsi < self.rsi_oversold and
            features.order_imbalance > 0.1):  # Positive order imbalance
            
            # Calculate precise entry based on order book
            entry_price = self._calculate_precise_entry(features, 'long')
            
            # Calculate signal strength
            strength = self._calculate_signal_strength(
                features, z_score, consolidation_score, 'long'
            )
            
            if strength > 0.4:  # Minimum signal strength
                return MeanReversionSignal(
                    symbol=symbol,
                    direction='long',
                    strength=strength,
                    entry_price=entry_price,
                    stop_price=entry_price * Decimal(str(1 - self.stop_loss_pct)),
                    target_price=entry_price * Decimal(str(1 + self.target_profit_pct)),
                    deviation_score=abs(z_score),
                    consolidation_strength=consolidation_score,
                    reason=f"Oversold bounce: Z-score={z_score:.2f}, RSI={features.rsi:.0f}"
                )
        
        # Short signal (overbought in consolidation)
        elif (z_score > self.z_score_threshold and 
              features.price > features.bb_upper and
              features.rsi > self.rsi_overbought and
              features.order_imbalance < -0.1):  # Negative order imbalance
            
            # Calculate precise entry based on order book
            entry_price = self._calculate_precise_entry(features, 'short')
            
            # Calculate signal strength
            strength = self._calculate_signal_strength(
                features, z_score, consolidation_score, 'short'
            )
            
            if strength > 0.4:  # Minimum signal strength
                return MeanReversionSignal(
                    symbol=symbol,
                    direction='short',
                    strength=strength,
                    entry_price=entry_price,
                    stop_price=entry_price * Decimal(str(1 + self.stop_loss_pct)),
                    target_price=entry_price * Decimal(str(1 - self.target_profit_pct)),
                    deviation_score=abs(z_score),
                    consolidation_strength=consolidation_score,
                    reason=f"Overbought fade: Z-score={z_score:.2f}, RSI={features.rsi:.0f}"
                )
        
        return None
    
    def _update_price_history(self, symbol: str, price: float):
        """Update price history for calculations."""
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.lookback_period * 2)
        
        self.price_history[symbol].append(price)
    
    def _calculate_z_score(self, symbol: str, current_price: float) -> float:
        """Calculate z-score of current price."""
        if symbol not in self.price_history or len(self.price_history[symbol]) < self.lookback_period:
            return 0.0
        
        prices = list(self.price_history[symbol])[-self.lookback_period:]
        mean_price = np.mean(prices)
        std_price = np.std(prices)
        
        if std_price == 0:
            return 0.0
        
        return (current_price - mean_price) / std_price
    
    def _calculate_consolidation_score(self, features: MarketFeatures) -> float:
        """Calculate how strongly the market is consolidating (0-1)."""
        score = 0.0
        
        # Low ADX indicates consolidation
        adx_score = 1.0 - min(features.adx / 40, 1.0)  # Score 1 at ADX 0, 0 at ADX 40+
        score += adx_score * 0.3
        
        # Narrow Bollinger Bands
        bb_width_pct = features.bb_width / features.price
        if bb_width_pct < 0.01:  # Less than 1% width
            bb_score = 1.0 - (bb_width_pct / 0.01)
            score += bb_score * 0.3
        
        # Low volatility
        if features.realized_vol_5m < 0.2:  # Less than 20% annualized
            vol_score = 1.0 - (features.realized_vol_5m / 0.2)
            score += vol_score * 0.2
        
        # RSI near 50 (neutral)
        rsi_distance = abs(features.rsi - 50) / 50
        rsi_score = 1.0 - rsi_distance
        score += rsi_score * 0.2
        
        return min(score, 1.0)
    
    def _calculate_precise_entry(self, features: MarketFeatures, direction: str) -> Decimal:
        """Calculate precise entry price based on order book dynamics."""
        # Use VWAP deviation and spread for micro-optimization
        base_price = Decimal(str(features.price))
        
        if direction == 'long':
            # For longs, try to enter slightly below current price
            # Consider spread and order imbalance
            if features.order_imbalance > 0:
                # Strong buy pressure, enter at market
                entry = base_price
            else:
                # Try to get better fill
                entry = base_price - Decimal(str(features.bid_ask_spread * 0.25))
        
        else:  # short
            # For shorts, try to enter slightly above current price
            if features.order_imbalance < 0:
                # Strong sell pressure, enter at market
                entry = base_price
            else:
                # Try to get better fill
                entry = base_price + Decimal(str(features.bid_ask_spread * 0.25))
        
        return entry
    
    def _calculate_signal_strength(self, features: MarketFeatures, z_score: float,
                                 consolidation_score: float, direction: str) -> float:
        """Calculate mean reversion signal strength (0-1)."""
        strength = 0.0
        
        # Z-score component (stronger deviation = stronger signal)
        z_score_normalized = min(abs(z_score) / 3, 1.0)  # Normalize to 0-1
        strength += z_score_normalized * 0.3
        
        # Consolidation strength
        strength += consolidation_score * 0.25
        
        # RSI extreme component
        if direction == 'long':
            if features.rsi < 20:
                rsi_score = 1.0
            elif features.rsi < 30:
                rsi_score = (30 - features.rsi) / 10
            else:
                rsi_score = 0
        else:  # short
            if features.rsi > 80:
                rsi_score = 1.0
            elif features.rsi > 70:
                rsi_score = (features.rsi - 70) / 10
            else:
                rsi_score = 0
        
        strength += rsi_score * 0.2
        
        # Order flow confirmation
        if direction == 'long' and features.order_imbalance > 0:
            strength += min(features.order_imbalance, 0.5) * 0.15
        elif direction == 'short' and features.order_imbalance < 0:
            strength += min(abs(features.order_imbalance), 0.5) * 0.15
        
        # Spread consideration (tighter spread = better for scalping)
        if features.spread_percentage < 0.05:  # Less than 0.05%
            spread_score = 1.0 - (features.spread_percentage / 0.05)
            strength += spread_score * 0.1
        
        return min(strength, 1.0)
    
    def should_exit_position(self, position: Position, features: MarketFeatures) -> Tuple[bool, str]:
        """
        Check if position should be exited (time-based or mean reversion complete).
        
        Returns:
            Tuple of (should_exit, reason)
        """
        # Check time-based exit
        if position.duration_minutes >= self.max_hold_minutes:
            return True, "max_hold_time"
        
        # Check if mean reversion is complete
        z_score = self._calculate_z_score(position.symbol, features.price)
        
        if position.is_long:
            # Exit long if price returns to mean or goes overbought
            if z_score >= 0 or features.rsi > 60:
                return True, "mean_reversion_complete"
            
            # Exit if consolidation breaks (trending starts)
            if features.adx > 30:
                return True, "consolidation_break"
        
        else:  # Short position
            # Exit short if price returns to mean or goes oversold
            if z_score <= 0 or features.rsi < 40:
                return True, "mean_reversion_complete"
            
            # Exit if consolidation breaks (trending starts)
            if features.adx > 30:
                return True, "consolidation_break"
        
        # Check adverse move (beyond stop but not triggered)
        if position.is_long and features.price < float(position.entry_price) * 0.997:
            return True, "adverse_move"
        elif position.is_short and features.price > float(position.entry_price) * 1.003:
            return True, "adverse_move"
        
        return False, ""
    
    def update_support_resistance(self, symbol: str, features: MarketFeatures):
        """Update support and resistance levels for the symbol."""
        if symbol not in self.support_resistance:
            self.support_resistance[symbol] = {
                'support': features.price,
                'resistance': features.price,
                'last_update': datetime.now()
            }
        
        # Update every 5 minutes
        last_update = self.support_resistance[symbol]['last_update']
        if (datetime.now() - last_update) > timedelta(minutes=5):
            # Simple support/resistance based on recent price action
            if len(self.price_history[symbol]) >= self.lookback_period:
                prices = list(self.price_history[symbol])[-self.lookback_period:]
                self.support_resistance[symbol].update({
                    'support': np.percentile(prices, 20),
                    'resistance': np.percentile(prices, 80),
                    'last_update': datetime.now()
                })
    
    def get_position_sizing_multiplier(self, features: MarketFeatures) -> float:
        """
        Get position sizing multiplier based on market conditions.
        
        Returns:
            Multiplier for position size (0.5-1.5)
        """
        multiplier = 1.0
        
        # Increase size in strong consolidation
        consolidation_score = self._calculate_consolidation_score(features)
        if consolidation_score > 0.7:
            multiplier *= 1.2
        
        # Increase size with tight spreads
        if features.spread_percentage < 0.02:  # Less than 0.02%
            multiplier *= 1.1
        
        # Decrease size in high volatility
        if features.realized_vol_5m > 0.5:  # More than 50% annualized
            multiplier *= 0.7
        
        return max(0.5, min(multiplier, 1.5))
