"""Central strategy orchestration for hybrid trading approach."""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import pandas as pd
import numpy as np

from core.feature_engineering import FeatureEngineering, MarketFeatures
from core.risk_manager import RiskManager
from core.execution_engine import ExecutionEngine
from strategies.momentum_breakout import MomentumBreakoutStrategy, BreakoutSignal
from strategies.mean_reversion import MeanReversionStrategy, MeanReversionSignal
from models.positions import Position
from models.market_data import MarketSnapshot
from utils.logger import get_logger


class MarketRegime(Enum):
    """Market regime classification."""
    TRENDING = "trending"
    CONSOLIDATING = "consolidating"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


class StrategyCore:
    """Orchestrates multiple trading strategies with regime detection."""
    
    def __init__(self, 
                 feature_engine: FeatureEngineering,
                 risk_manager: RiskManager,
                 execution_engine: ExecutionEngine):
        """
        Initialize strategy core.
        
        Args:
            feature_engine: Feature engineering instance
            risk_manager: Risk management instance
            execution_engine: Execution engine instance
        """
        self.logger = get_logger(self.__class__.__name__)
        self.feature_engine = feature_engine
        self.risk_manager = risk_manager
        self.execution_engine = execution_engine
        
        # Initialize strategies
        self.momentum_strategy = MomentumBreakoutStrategy()
        self.mean_reversion_strategy = MeanReversionStrategy()
        
        # Strategy weights based on market regime
        self.strategy_weights = {
            MarketRegime.TRENDING: {'momentum': 0.8, 'mean_reversion': 0.2},
            MarketRegime.CONSOLIDATING: {'momentum': 0.2, 'mean_reversion': 0.8},
            MarketRegime.VOLATILE: {'momentum': 0.5, 'mean_reversion': 0.5},
            MarketRegime.UNKNOWN: {'momentum': 0.5, 'mean_reversion': 0.5}
        }
        
        # Performance tracking
        self.strategy_performance = {
            'momentum': {'trades': 0, 'wins': 0, 'total_pnl': 0.0},
            'mean_reversion': {'trades': 0, 'wins': 0, 'total_pnl': 0.0}
        }
        
        # Signal tracking
        self.active_signals: Dict[str, Any] = {}
        self.signal_history: List[Dict] = []
        
        # Market regime tracking
        self.current_regime = MarketRegime.UNKNOWN
        self.regime_history: List[Tuple[datetime, MarketRegime]] = []
        
        self.logger.info("Strategy core initialized with hybrid approach")
    
    def configure_symbol_risk(self, 
                             symbol: str,
                             max_position_size_pct: float,
                             stop_loss_pct: float,
                             take_profit_pct: float,
                             base_leverage: int = 5):
        """
        Configure symbol-specific risk parameters for multi-symbol trading.
        
        Args:
            symbol: Trading symbol (e.g., 'BTC/USDT')
            max_position_size_pct: Maximum position size as percentage of portfolio (0.01 = 1%)
            stop_loss_pct: Stop loss percentage (0.006 = 0.6%)
            take_profit_pct: Take profit percentage (0.009 = 0.9%)
            base_leverage: Base leverage to use for this symbol
        """
        # Store symbol-specific risk parameters
        if not hasattr(self, 'symbol_risk_configs'):
            self.symbol_risk_configs = {}
        
        self.symbol_risk_configs[symbol] = {
            'max_position_size_pct': max_position_size_pct,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
            'base_leverage': base_leverage
        }
        
        self.logger.info(f"Configured risk parameters for {symbol}: "
                        f"max_pos={max_position_size_pct:.2%}, "
                        f"stop_loss={stop_loss_pct:.2%}, "
                        f"take_profit={take_profit_pct:.2%}, "
                        f"leverage={base_leverage}x")
    
    def get_symbol_risk_config(self, symbol: str) -> Optional[Dict]:
        """
        Get risk configuration for a specific symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Risk configuration dictionary or None if not configured
        """
        if hasattr(self, 'symbol_risk_configs'):
            return self.symbol_risk_configs.get(symbol)
        return None
    
    async def process_market_update(self, snapshot: MarketSnapshot):
        """
        Process market update and generate trading signals.
        
        Args:
            snapshot: Current market snapshot
        """
        try:
            # Update candle data for feature engineering
            # Note: In production, you'd get candles from database or another source
            
            # Compute features
            features = self.feature_engine.compute_features(snapshot)
            if not features:
                return
            
            # Detect market regime
            regime = self._detect_market_regime(features)
            if regime != self.current_regime:
                self.logger.info(f"Market regime changed: {self.current_regime} -> {regime}")
                self.current_regime = regime
                self.regime_history.append((datetime.now(), regime))
            
            # Get current positions
            open_positions = self.execution_engine.position_manager.get_open_positions()
            
            # Check existing positions for exit signals
            await self._check_exit_signals(features, open_positions)
            
            # Check for new entry signals
            await self._check_entry_signals(features, open_positions)
            
            # Update position prices
            self._update_position_prices(snapshot, open_positions)
            
            # Check for trailing stops
            await self._check_trailing_stops(features, open_positions)
            
        except Exception as e:
            self.logger.error(f"Error processing market update: {e}", exc_info=True)
    
    def _detect_market_regime(self, features: MarketFeatures) -> MarketRegime:
        """Detect current market regime based on features."""
        try:
            # Get indicator values with safe defaults, ensuring we log what we're working with
            # Use safe formatting to handle potential NaN values
            adx_raw = features.adx if hasattr(features, 'adx') else 0
            rsi_raw = features.rsi if hasattr(features, 'rsi') else 50
            price_raw = features.price if hasattr(features, 'price') else 1.0
            bb_width_raw = features.bb_width if hasattr(features, 'bb_width') else 0
            vol_5m_raw = features.realized_vol_5m if hasattr(features, 'realized_vol_5m') else 0
            vol_1h_raw = features.realized_vol_1h if hasattr(features, 'realized_vol_1h') else 0

            # Safe string formatting for logging
            adx_str = f"{adx_raw:.2f}" if not pd.isna(adx_raw) else "N/A"
            rsi_str = f"{rsi_raw:.2f}" if not pd.isna(rsi_raw) else "N/A"
            vol_5m_str = f"{vol_5m_raw:.2f}" if not pd.isna(vol_5m_raw) else "N/A"
            vol_1h_str = f"{vol_1h_raw:.2f}" if not pd.isna(vol_1h_raw) else "N/A"
            
            # Calculate BB width percentage safely
            if not pd.isna(bb_width_raw) and not pd.isna(price_raw) and price_raw > 0:
                bb_width_pct = bb_width_raw / price_raw * 100
                bb_width_str = f"{bb_width_pct:.2f}%"
            else:
                bb_width_pct = 1.0  # Default value
                bb_width_str = "N/A"
            
            self.logger.info(f"Detecting market regime: ADX={adx_str}, RSI={rsi_str}, "
                             f"Vol_5m={vol_5m_str}, Vol_1h={vol_1h_str}, BB_width%={bb_width_str}")
            
            # Normalize all indicators with strong defaults to avoid NaN issues
            adx = float(adx_raw) if not pd.isna(adx_raw) and float(adx_raw) > 0 else 15.0
            rsi = float(rsi_raw) if not pd.isna(rsi_raw) and 0 <= float(rsi_raw) <= 100 else 50.0
            vol_5m = float(vol_5m_raw) if not pd.isna(vol_5m_raw) and float(vol_5m_raw) >= 0 else 0.3
            vol_1h = float(vol_1h_raw) if not pd.isna(vol_1h_raw) and float(vol_1h_raw) >= 0 else 0.25
            
            # Detect regimes using robust conditional logic
            # Add logging for each decision point
            
            # Check for trending market first - ADX is the primary indicator
            if adx >= 25:  # Strong trend
                if vol_1h >= 0.4:  # High volatility with trend
                    self.logger.info(f"✓ VOLATILE regime detected (high ADX={adx:.2f} with volatility={vol_1h:.2f})")
                    return MarketRegime.VOLATILE
                else:
                    self.logger.info(f"✓ TRENDING regime detected (ADX={adx:.2f})")
                    return MarketRegime.TRENDING
            
            # Next check for higher volatility regardless of trend
            elif vol_5m >= 0.4 or vol_1h >= 0.35:
                self.logger.info(f"✓ VOLATILE regime detected (vol_5m={vol_5m:.2f}, vol_1h={vol_1h:.2f})")
                return MarketRegime.VOLATILE
            
            # Check for consolidation - low ADX and tight Bollinger Bands
            elif adx < 25 and bb_width_pct < 2.0:
                self.logger.info(f"✓ CONSOLIDATING regime detected (ADX={adx:.2f}, BB width %={bb_width_pct:.2f}%)")
                return MarketRegime.CONSOLIDATING
            
            # Use RSI to detect potential trends
            elif rsi >= 70 or rsi <= 30:
                self.logger.info(f"✓ TRENDING regime detected (extreme RSI={rsi:.2f})")
                return MarketRegime.TRENDING
            
            # Default to consolidating for moderate markets
            else:
                self.logger.info("✓ CONSOLIDATING regime detected (default - moderate indicators)")
                return MarketRegime.CONSOLIDATING
                
        except Exception as e:
            self.logger.error(f"Error detecting market regime: {e}", exc_info=True)
            # In case of error, default to CONSOLIDATING for safer trading
            # Never return UNKNOWN, as this causes display issues
            self.logger.warning("Defaulting to CONSOLIDATING regime due to error")
            return MarketRegime.CONSOLIDATING
    
    async def _check_entry_signals(self, features: MarketFeatures, 
                                  open_positions: List[Position]):
        """Check for new entry signals from strategies."""
        # Get risk assessment
        account_risk = self.risk_manager.get_account_risk_snapshot()
        
        # Skip if circuit breaker is active
        if account_risk.circuit_breaker_active:
            return
        
        # Get strategy weights for current regime
        weights = self.strategy_weights[self.current_regime]
        
        # Check momentum strategy
        if weights['momentum'] > 0:
            momentum_signal = self.momentum_strategy.analyze(features, open_positions)
            if momentum_signal:
                await self._process_signal(
                    momentum_signal, 
                    'momentum',
                    weights['momentum'],
                    features
                )
        
        # Check mean reversion strategy
        if weights['mean_reversion'] > 0:
            mean_rev_signal = self.mean_reversion_strategy.analyze(features, open_positions)
            if mean_rev_signal:
                await self._process_signal(
                    mean_rev_signal,
                    'mean_reversion',
                    weights['mean_reversion'],
                    features
                )
    
    async def _process_signal(self, signal: Any, strategy_name: str, 
                            weight: float, features: MarketFeatures):
        """Process a trading signal."""
        try:
            # Adjust signal strength by strategy weight
            adjusted_strength = signal.strength * weight
            
            # Skip weak signals
            if adjusted_strength < 0.3:
                return
            
            # Calculate position size
            base_size = self.risk_manager.calculate_position_size(
                signal.symbol,
                features,
                adjusted_strength
            )
            
            # Apply strategy-specific sizing
            if strategy_name == 'mean_reversion':
                # Adjust size for mean reversion
                size_multiplier = self.mean_reversion_strategy.get_position_sizing_multiplier(features)
                final_size = Decimal(str(base_size * size_multiplier))
            else:
                final_size = Decimal(str(base_size))
            
            # Pre-trade risk check
            allowed, reasons = self.risk_manager.check_pre_trade_risk(
                signal.symbol,
                signal.direction,
                float(final_size),
                float(signal.entry_price),
                features
            )
            
            if not allowed:
                self.logger.warning(f"Signal rejected by risk manager: {reasons}")
                return
            
            # Execute position entry
            position = await self.execution_engine.execute_position_entry(
                symbol=signal.symbol,
                side=signal.direction,
                size=final_size,
                current_price=signal.entry_price,
                strategy_name=strategy_name,
                signal_strength=adjusted_strength
            )
            
            if position:
                # Track signal
                self.active_signals[position.position_id] = {
                    'signal': signal,
                    'strategy': strategy_name,
                    'features': features.to_dict() if hasattr(features, 'to_dict') else {},
                    'timestamp': datetime.now()
                }
                
                # Update strategy tracking
                if strategy_name == 'momentum' and hasattr(signal, 'breakout_level'):
                    self.momentum_strategy.update_pyramid_tracking(
                        position.position_id, 
                        float(position.entry_price)
                    )
                
                self.logger.success(
                    f"Position opened via {strategy_name}: {signal.symbol} "
                    f"{signal.direction} | Reason: {signal.reason}"
                )
        
        except Exception as e:
            self.logger.error(f"Error processing signal: {e}", exc_info=True)
    
    async def _check_exit_signals(self, features: MarketFeatures, 
                                 open_positions: List[Position]):
        """Check if any positions should be exited."""
        for position in open_positions:
            try:
                # Get original signal info
                signal_info = self.active_signals.get(position.position_id)
                if not signal_info:
                    continue
                
                strategy_name = signal_info['strategy']
                should_exit = False
                exit_reason = ""
                
                # Check strategy-specific exit conditions
                if strategy_name == 'momentum':
                    should_exit, exit_reason = self.momentum_strategy.should_exit_position(
                        position, features
                    )
                elif strategy_name == 'mean_reversion':
                    should_exit, exit_reason = self.mean_reversion_strategy.should_exit_position(
                        position, features
                    )
                
                # Execute exit if needed
                if should_exit:
                    success = await self.execution_engine.execute_position_exit(
                        position.position_id, exit_reason
                    )
                    
                    if success:
                        # Update performance tracking
                        self._update_strategy_performance(position, strategy_name)
                        
                        # Clean up tracking
                        if position.position_id in self.active_signals:
                            del self.active_signals[position.position_id]
                        
                        if strategy_name == 'momentum':
                            self.momentum_strategy.clear_position_tracking(position.position_id)
                        
                        self.logger.info(
                            f"Position exited: {position.symbol} | "
                            f"Reason: {exit_reason} | P&L: {position.total_pnl:.2f}"
                        )
            
            except Exception as e:
                self.logger.error(f"Error checking exit signals: {e}", exc_info=True)
    
    async def _check_trailing_stops(self, features: MarketFeatures, 
                                   open_positions: List[Position]):
        """Check and update trailing stops for positions."""
        for position in open_positions:
            try:
                # Check if stop should be trailed
                should_trail, new_stop = self.risk_manager.should_trail_stop(position)
                
                if should_trail and new_stop:
                    success = await self.execution_engine.trail_stop_loss(
                        position.position_id,
                        Decimal(str(new_stop))
                    )
                    
                    if success:
                        self.logger.info(
                            f"Trailing stop updated for {position.symbol}: "
                            f"{position.stop_loss_price:.2f} -> {new_stop:.2f}"
                        )
            
            except Exception as e:
                self.logger.error(f"Error updating trailing stop: {e}", exc_info=True)
    
    def _update_position_prices(self, snapshot: MarketSnapshot, 
                              open_positions: List[Position]):
        """Update current prices for all positions."""
        if not snapshot.orderbook or not snapshot.orderbook.mid_price:
            return
        
        current_price = snapshot.orderbook.mid_price
        
        for position in open_positions:
            if position.symbol == snapshot.symbol:
                position.update_price(current_price)
    
    def _update_strategy_performance(self, position: Position, strategy_name: str):
        """Update strategy performance metrics."""
        if strategy_name in self.strategy_performance:
            stats = self.strategy_performance[strategy_name]
            stats['trades'] += 1
            
            if position.total_pnl > 0:
                stats['wins'] += 1
            
            stats['total_pnl'] += float(position.total_pnl)
            
            # Log performance
            win_rate = stats['wins'] / stats['trades'] * 100 if stats['trades'] > 0 else 0
            self.logger.info(
                f"{strategy_name} performance: "
                f"Trades={stats['trades']}, "
                f"Win Rate={win_rate:.1f}%, "
                f"Total P&L={stats['total_pnl']:.2f}"
            )
    
    def get_strategy_status(self) -> Dict[str, Any]:
        """Get current strategy status and performance."""
        try:
            # Ensure we have a valid regime
            if self.current_regime is None or self.current_regime == MarketRegime.UNKNOWN:
                # If regime is None or UNKNOWN, force it to be CONSOLIDATING
                self.current_regime = MarketRegime.CONSOLIDATING
                self.logger.warning("Market regime was None or UNKNOWN, setting to CONSOLIDATING")
            
            # Extract the value properly for serialization
            regime_value = None
            regime_name = None
            
            if hasattr(self.current_regime, 'value'):
                regime_value = self.current_regime.value
                regime_name = self.current_regime.name
            else:
                # Handle non-enum values by converting to string
                regime_value = str(self.current_regime)
                regime_name = regime_value.upper()
            
            self.logger.info(f"Current market regime: {regime_name} ({regime_value})")
            
            # Format regime history with careful handling of enum values
            regime_history = []
            for t, r in self.regime_history[-5:]:
                if r is None:
                    regime_history.append({'time': t.isoformat(), 'regime': 'consolidating'})
                elif hasattr(r, 'value'):
                    regime_history.append({'time': t.isoformat(), 'regime': r.value})
                else:
                    regime_history.append({'time': t.isoformat(), 'regime': str(r)})
            
            # Build the status object
            status = {
                'current_regime': regime_value,
                'active_signals': len(self.active_signals),
                'strategy_performance': self.strategy_performance,
                'regime_weights': self.strategy_weights[self.current_regime],
                'recent_regime_changes': regime_history
            }
            
            self.logger.debug(f"Strategy status data: {status}")
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting strategy status: {e}", exc_info=True)
            # Never return 'unknown' as the regime value
            return {
                'current_regime': 'consolidating',  # Default to a valid regime value
                'active_signals': 0,
                'strategy_performance': {},
                'regime_weights': {'momentum': 0.5, 'mean_reversion': 0.5},
                'recent_regime_changes': []
            }
    
    def update_strategy_weights(self, regime: MarketRegime, weights: Dict[str, float]):
        """Update strategy weights for a specific regime."""
        if sum(weights.values()) != 1.0:
            raise ValueError("Strategy weights must sum to 1.0")
        
        self.strategy_weights[regime] = weights
        self.logger.info(f"Updated weights for {regime}: {weights}")
