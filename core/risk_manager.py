"""Advanced risk management for aggressive perpetual trading."""

import numpy as np
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from models.market_data import MarketSnapshot
from core.feature_engineering import MarketFeatures
from utils.config import get_config
from utils.logger import get_logger


class RiskLevel(Enum):
    """Risk level classifications."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    HALT = "halt"
    UNKNOWN = "unknown"  # Added for error handling


@dataclass
class PositionRisk:
    """Risk metrics for a single position."""
    symbol: str
    size: float
    entry_price: float
    current_price: float
    leverage: float
    
    # P&L
    unrealized_pnl: float
    unrealized_pnl_pct: float
    
    # Risk metrics
    position_value: float
    margin_used: float
    stop_loss_price: float
    take_profit_price: float
    max_loss_amount: float
    risk_reward_ratio: float
    
    # Time metrics
    duration_minutes: float
    funding_paid: float


@dataclass
class AccountRisk:
    """Account-level risk metrics."""
    timestamp: datetime
    
    # Capital metrics
    total_equity: float
    free_margin: float
    margin_used: float
    margin_ratio: float
    
    # Leverage
    current_leverage: float
    target_leverage: float
    max_allowed_leverage: float
    
    # P&L metrics
    daily_pnl: float
    daily_pnl_pct: float
    max_daily_drawdown: float
    current_drawdown: float
    
    # Risk metrics
    var_1h: float  # Value at Risk
    cvar_1h: float  # Conditional VaR
    kelly_fraction: float
    sharpe_ratio_24h: float
    
    # Exposure
    total_exposure: float
    position_count: int
    concentration_risk: float  # Max position % of equity
    
    # Status
    risk_level: RiskLevel
    circuit_breaker_active: bool = False
    halt_reasons: List[str] = field(default_factory=list)


class RiskManager:
    """Hierarchical risk management system."""
    
    def __init__(self, exchange=None):
        """Initialize risk manager."""
        self.config = get_config()
        self.logger = get_logger(self.__class__.__name__)
        self.exchange = exchange
        
        # Risk parameters from config
        self.base_leverage = self.config.base_leverage
        self.max_leverage = self.config.max_leverage
        self.daily_drawdown_limit = self.config.daily_drawdown_limit
        self.position_stop_loss = self.config.position_stop_loss
        self.position_take_profit = self.config.position_take_profit
        self.max_position_size_pct = self.config.max_position_size_pct
        
        # Dynamic parameters
        self.current_leverage = self.base_leverage
        self.volatility_target = 0.20  # 20% annualized vol target
        
        # Account state - Initialize based on trading mode
        self.total_equity = self._initialize_equity()
        self.starting_equity = self.total_equity
        self.daily_starting_equity = self.total_equity
        self.positions: Dict[str, PositionRisk] = {}
        
        # Risk tracking
        self.daily_trades = []
        self.pnl_history = []
        self.max_drawdown_today = 0.0
        self.circuit_breaker_active = False
        self.halt_until = None
        
        # Performance tracking
        self.sharpe_window = 24 * 60  # 24 hours in minutes
        self.var_confidence = 0.99  # 99% VaR
        
        self.logger.info("Risk manager initialized with aggressive parameters")
        self.logger.info(f"Base leverage: {self.base_leverage}x, Max: {self.max_leverage}x")
    
    def check_pre_trade_risk(self, symbol: str, side: str, size: float, 
                           price: float, features: MarketFeatures) -> Tuple[bool, List[str]]:
        """
        Check if a trade is allowed based on risk rules.
        
        Returns:
            Tuple of (allowed, reasons) where reasons list why trade was rejected
        """
        reasons = []
        
        # Check circuit breaker
        if self.circuit_breaker_active:
            if self.halt_until and datetime.now() < self.halt_until:
                reasons.append(f"Circuit breaker active until {self.halt_until}")
                return False, reasons
            else:
                self.circuit_breaker_active = False
                self.halt_until = None
        
        # Check daily drawdown
        if self.current_drawdown >= self.daily_drawdown_limit:
            reasons.append(f"Daily drawdown limit reached: {self.current_drawdown:.2%}")
            self._activate_circuit_breaker("daily_drawdown_limit", hours=24)
            return False, reasons
        
        # Check funding rate
        if features.funding_rate > self.config.max_funding_rate:
            reasons.append(f"Funding rate too high: {features.funding_rate:.4%}")
            return False, reasons
        
        # Check position sizing
        position_value = size * price
        position_pct = position_value / self.total_equity
        
        if position_pct > self.max_position_size_pct:
            reasons.append(f"Position too large: {position_pct:.2%} of equity")
            return False, reasons
        
        # Check leverage
        new_exposure = self._calculate_total_exposure() + position_value
        new_leverage = new_exposure / self.total_equity
        
        if new_leverage > self.current_leverage:
            reasons.append(f"Would exceed leverage limit: {new_leverage:.1f}x > {self.current_leverage:.1f}x")
            return False, reasons
        
        # Check volatility conditions
        if features.realized_vol_5m > 1.0:  # 100% annualized vol
            reasons.append(f"Market too volatile: {features.realized_vol_5m:.1%} annualized")
            return False, reasons
        
        # Check number of positions
        if len(self.positions) >= 5:
            reasons.append("Maximum number of positions reached (5)")
            return False, reasons
        
        # Kelly criterion check
        kelly_size = self._calculate_kelly_position_size(features)
        if size > kelly_size * 1.5:  # Allow 50% more than Kelly
            reasons.append(f"Position exceeds Kelly criterion: {size:.4f} > {kelly_size * 1.5:.4f}")
            return False, reasons
        
        # If all checks pass
        if not reasons:
            self.logger.info(f"Pre-trade risk checks PASSED for {symbol} {side} {size}")
            return True, []
        else:
            self.logger.warning(f"Pre-trade risk checks FAILED: {', '.join(reasons)}")
            return False, reasons
    
    def calculate_position_size(self, symbol: str, features: MarketFeatures,
                              signal_strength: float) -> float:
        """
        Calculate optimal position size based on risk parameters.
        
        Args:
            symbol: Trading symbol
            features: Current market features
            signal_strength: Signal strength from strategy (0-1)
            
        Returns:
            Position size in base currency
        """
        # Base position from Kelly criterion
        kelly_size = self._calculate_kelly_position_size(features)
        
        # Adjust for signal strength
        base_size = kelly_size * signal_strength
        
        # Volatility adjustment
        vol_scalar = self._calculate_volatility_scalar(features)
        adjusted_size = base_size * vol_scalar
        
        # Apply position limits
        max_size = self.total_equity * self.max_position_size_pct / features.price
        final_size = min(adjusted_size, max_size)
        
        # Round to exchange precision
        final_size = round(final_size, 8)
        
        self.logger.info(
            f"Position size calculation: Kelly={kelly_size:.4f}, "
            f"Adjusted={adjusted_size:.4f}, Final={final_size:.4f}"
        )
        
        return final_size
    
    def update_leverage(self, features: MarketFeatures, performance_metrics: Dict[str, float]):
        """
        Dynamically update leverage based on market conditions and performance.
        
        Args:
            features: Current market features
            performance_metrics: Recent performance metrics
        """
        sharpe = performance_metrics.get('sharpe_ratio_24h', 0)
        
        # Scale up leverage if Sharpe > 2 (as per requirements)
        if sharpe > 2.0:
            # Gradually increase leverage
            leverage_boost = min((sharpe - 2.0) * 2, 5.0)  # Max +5x boost
            new_leverage = self.base_leverage + leverage_boost
            self.current_leverage = min(new_leverage, self.max_leverage)
            self.logger.info(f"Leverage increased to {self.current_leverage:.1f}x (Sharpe: {sharpe:.2f})")
        else:
            # Reduce leverage in poor conditions
            if sharpe < 0:
                self.current_leverage = max(self.base_leverage * 0.5, 1.0)
                self.logger.warning(f"Leverage reduced to {self.current_leverage:.1f}x (Sharpe: {sharpe:.2f})")
            else:
                self.current_leverage = self.base_leverage
        
        # Volatility-based adjustment
        if features.realized_vol_1h > 0.5:  # 50% annualized
            vol_reduction = min(features.realized_vol_1h * 2, 0.8)
            self.current_leverage *= (1 - vol_reduction)
            self.logger.info(f"Leverage reduced by volatility to {self.current_leverage:.1f}x")
        
        # Auto-deleverage on drawdown
        if self.current_drawdown > 0.03:  # 3% drawdown
            self.current_leverage = max(self.current_leverage * 0.5, 1.0)
            self.logger.warning(f"Auto-deleveraging to {self.current_leverage:.1f}x due to drawdown")
    
    def get_stop_loss_price(self, entry_price: float, side: str) -> float:
        """Calculate stop loss price for a position."""
        if side == 'buy':
            return entry_price * (1 - self.position_stop_loss)
        else:
            return entry_price * (1 + self.position_stop_loss)
    
    def get_take_profit_price(self, entry_price: float, side: str) -> float:
        """Calculate take profit price for a position."""
        if side == 'buy':
            return entry_price * (1 + self.position_take_profit)
        else:
            return entry_price * (1 - self.position_take_profit)
    
    def should_trail_stop(self, position: PositionRisk) -> Tuple[bool, Optional[float]]:
        """
        Check if stop loss should be trailed (after +1R).
        
        Returns:
            Tuple of (should_trail, new_stop_price)
        """
        if position.unrealized_pnl_pct >= self.position_take_profit:
            # Price has moved +1R, trail the stop
            if position.size > 0:  # Long position
                new_stop = position.current_price * (1 - self.position_stop_loss * 0.5)
                if new_stop > position.stop_loss_price:
                    return True, new_stop
            else:  # Short position
                new_stop = position.current_price * (1 + self.position_stop_loss * 0.5)
                if new_stop < position.stop_loss_price:
                    return True, new_stop
        
        return False, None
    
    def calculate_var(self, returns: List[float], confidence: float = 0.99) -> float:
        """Calculate Value at Risk."""
        if not returns:
            return 0.0
        
        sorted_returns = sorted(returns)
        index = int(len(sorted_returns) * (1 - confidence))
        return abs(sorted_returns[index]) if index < len(sorted_returns) else 0.0
    
    def calculate_cvar(self, returns: List[float], confidence: float = 0.99) -> float:
        """Calculate Conditional Value at Risk (Expected Shortfall)."""
        if not returns:
            return 0.0
        
        sorted_returns = sorted(returns)
        index = int(len(sorted_returns) * (1 - confidence))
        tail_returns = sorted_returns[:index] if index > 0 else sorted_returns[:1]
        return abs(np.mean(tail_returns)) if tail_returns else 0.0
    
    def get_account_risk_snapshot(self) -> AccountRisk:
        """Get current account risk metrics."""
        # Calculate current metrics
        total_exposure = self._calculate_total_exposure()
        margin_used = total_exposure / self.current_leverage if self.current_leverage > 0 else 0
        free_margin = self.total_equity - margin_used
        
        # Calculate P&L metrics
        daily_pnl = self.total_equity - self.daily_starting_equity
        daily_pnl_pct = daily_pnl / self.daily_starting_equity
        
        # Get recent returns for risk metrics
        recent_returns = self._get_recent_returns(60)  # Last hour
        var_1h = self.calculate_var(recent_returns) * self.total_equity
        cvar_1h = self.calculate_cvar(recent_returns) * self.total_equity
        
        # Calculate Sharpe ratio
        sharpe = self._calculate_sharpe_ratio()
        
        # Determine risk level
        risk_level = self._determine_risk_level(daily_pnl_pct, var_1h / self.total_equity)
        
        # Debug log the risk level
        self.logger.info(f"Current risk level: {risk_level.name} ({risk_level.value})")
        
        return AccountRisk(
            timestamp=datetime.now(),
            total_equity=self.total_equity,
            free_margin=free_margin,
            margin_used=margin_used,
            margin_ratio=margin_used / self.total_equity if self.total_equity > 0 else 0,
            current_leverage=total_exposure / self.total_equity if self.total_equity > 0 else 0,
            target_leverage=self.current_leverage,
            max_allowed_leverage=self.max_leverage,
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            max_daily_drawdown=self.max_drawdown_today,
            current_drawdown=self.current_drawdown,
            var_1h=var_1h,
            cvar_1h=cvar_1h,
            kelly_fraction=0.25,  # Conservative Kelly
            sharpe_ratio_24h=sharpe,
            total_exposure=total_exposure,
            position_count=len(self.positions),
            concentration_risk=self._calculate_concentration_risk(),
            risk_level=risk_level,
            circuit_breaker_active=self.circuit_breaker_active,
            halt_reasons=self._get_halt_reasons()
        )
    
    def _initialize_equity(self) -> float:
        """
        Initialize equity based on trading mode.
        
        For live trading, it stores the exchange reference for later async balance fetch.
        For paper trading, it uses the configured paper trading balance.
        
        Returns:
            Initial equity value
        """
        try:
            if self.config.is_live_trading and self.exchange is not None:
                # In live mode with exchange available, but we can't make async calls here
                # We'll store exchange reference and use it later
                self.logger.info("Live trading mode: Will fetch balance from exchange when initialized")
                # Return paper balance initially, will update in first run
                return self.config.paper_trading_balance
            
            # Fallback to paper trading balance
            self.logger.info(f"Using paper trading balance: ${self.config.paper_trading_balance:.2f}")
            return self.config.paper_trading_balance
        
        except Exception as e:
            self.logger.error(f"Error initializing equity: {e}")
            self.logger.info(f"Falling back to paper trading balance: ${self.config.paper_trading_balance:.2f}")
            return self.config.paper_trading_balance
    
    def _calculate_kelly_position_size(self, features: MarketFeatures) -> float:
        """Calculate position size using Kelly criterion."""
        # Simplified Kelly for high-frequency trading
        # f = (p * b - q) / b
        # where p = win prob, b = win/loss ratio, q = 1-p
        
        # Estimate from recent performance or use defaults
        win_rate = 0.55  # Target 55% win rate
        avg_win = self.position_take_profit
        avg_loss = self.position_stop_loss
        
        b = avg_win / avg_loss  # Risk/reward ratio
        kelly_fraction = (win_rate * b - (1 - win_rate)) / b
        
        # Apply Kelly with safety factor
        kelly_fraction = max(0, min(kelly_fraction * 0.25, 0.25))  # Max 25% of capital
        
        position_value = self.total_equity * kelly_fraction
        position_size = position_value / features.price
        
        return position_size
    
    def _calculate_volatility_scalar(self, features: MarketFeatures) -> float:
        """Calculate position size scalar based on volatility."""
        # Scale position inversely with volatility
        target_vol = self.volatility_target
        current_vol = features.realized_vol_1h
        
        if current_vol > 0:
            scalar = min(target_vol / current_vol, 2.0)  # Max 2x scaling
            return max(scalar, 0.2)  # Min 0.2x scaling
        
        return 1.0
    
    def _calculate_total_exposure(self) -> float:
        """Calculate total market exposure across all positions."""
        return sum(abs(pos.position_value) for pos in self.positions.values())
    
    def _calculate_concentration_risk(self) -> float:
        """Calculate maximum position concentration."""
        if not self.positions or self.total_equity == 0:
            return 0.0
        
        max_position_value = max(abs(pos.position_value) for pos in self.positions.values())
        return max_position_value / self.total_equity
    
    def _calculate_sharpe_ratio(self) -> float:
        """Calculate rolling 24-hour Sharpe ratio."""
        if len(self.pnl_history) < 2:
            return 0.0
        
        returns = []
        for i in range(1, min(len(self.pnl_history), self.sharpe_window)):
            ret = (self.pnl_history[i] - self.pnl_history[i-1]) / self.pnl_history[i-1]
            returns.append(ret)
        
        if not returns:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize (assuming 5-minute returns)
        periods_per_year = 252 * 24 * 12
        sharpe = np.sqrt(periods_per_year) * mean_return / std_return
        
        return sharpe
    
    def _get_recent_returns(self, periods: int) -> List[float]:
        """Get recent returns for risk calculations."""
        returns = []
        
        if len(self.pnl_history) < 2:
            return returns
        
        for i in range(1, min(len(self.pnl_history), periods + 1)):
            if self.pnl_history[i-1] > 0:
                ret = (self.pnl_history[i] - self.pnl_history[i-1]) / self.pnl_history[i-1]
                returns.append(ret)
        
        return returns
    
    def _determine_risk_level(self, daily_pnl_pct: float, var_pct: float) -> RiskLevel:
        """Determine current risk level based on metrics."""
        try:
            self.logger.debug(f"Determining risk level - PnL: {daily_pnl_pct:.2%}, VaR: {var_pct:.2%}")
            
            if self.circuit_breaker_active:
                self.logger.info("Risk level: HALT (circuit breaker active)")
                return RiskLevel.HALT
            
            if daily_pnl_pct < -0.04 or var_pct > 0.05:
                self.logger.info(f"Risk level: CRITICAL (PnL: {daily_pnl_pct:.2%}, VaR: {var_pct:.2%})")
                return RiskLevel.CRITICAL
            
            if daily_pnl_pct < -0.02 or var_pct > 0.03:
                self.logger.info(f"Risk level: HIGH (PnL: {daily_pnl_pct:.2%}, VaR: {var_pct:.2%})")
                return RiskLevel.HIGH
            
            if daily_pnl_pct < -0.01 or var_pct > 0.02:
                self.logger.info(f"Risk level: MODERATE (PnL: {daily_pnl_pct:.2%}, VaR: {var_pct:.2%})")
                return RiskLevel.MODERATE
            
            self.logger.info(f"Risk level: LOW (PnL: {daily_pnl_pct:.2%}, VaR: {var_pct:.2%})")
            return RiskLevel.LOW
            
        except Exception as e:
            self.logger.error(f"Error determining risk level: {e}", exc_info=True)
            return RiskLevel.UNKNOWN  # Add UNKNOWN to the RiskLevel enum if not already there
    
    def _activate_circuit_breaker(self, reason: str, hours: int = 1):
        """Activate circuit breaker to halt trading."""
        self.circuit_breaker_active = True
        self.halt_until = datetime.now() + timedelta(hours=hours)
        self.logger.critical(f"CIRCUIT BREAKER ACTIVATED: {reason}. Halting until {self.halt_until}")
    
    def _get_halt_reasons(self) -> List[str]:
        """Get list of reasons for trading halt."""
        reasons = []
        
        if self.circuit_breaker_active:
            reasons.append("Circuit breaker active")
        
        if self.current_drawdown >= self.daily_drawdown_limit:
            reasons.append(f"Daily drawdown limit exceeded: {self.current_drawdown:.2%}")
        
        if self.total_equity < self.starting_equity * 0.5:
            reasons.append("Account equity below 50% of starting capital")
        
        return reasons
    
    @property
    def current_drawdown(self) -> float:
        """Calculate current drawdown from daily high."""
        if self.daily_starting_equity == 0:
            return 0.0
        
        drawdown = (self.daily_starting_equity - self.total_equity) / self.daily_starting_equity
        self.max_drawdown_today = max(self.max_drawdown_today, drawdown)
        return drawdown
    
    def reset_daily_metrics(self):
        """Reset daily metrics at start of new trading day."""
        self.daily_starting_equity = self.total_equity
        self.max_drawdown_today = 0.0
        self.daily_trades.clear()
        self.logger.info(f"Daily metrics reset. Starting equity: ${self.total_equity:,.2f}")
    
    async def update_equity_from_exchange(self):
        """
        Update equity by fetching actual balance from exchange.
        This method should be called periodically in live trading mode.
        """
        if not self.config.is_live_trading or self.exchange is None:
            return
        
        try:
            self.logger.debug("Fetching balance from exchange...")
            balance = await self.exchange.fetch_balance()
            
            # Debug: Log the entire balance response structure
            self.logger.info(f"Exchange balance response: {balance}")
            
            # Check for USDT balance
            if balance and 'total' in balance:
                self.logger.info(f"Available currencies in balance: {list(balance['total'].keys())}")
                
                # Try multiple currency variations
                usdt_balance = None
                for currency in ['USDT', 'USD', 'USDC']:
                    if currency in balance['total'] and balance['total'][currency] > 0:
                        usdt_balance = float(balance['total'][currency])
                        self.logger.info(f"Found {currency} balance: ${usdt_balance:.2f}")
                        break
                
                if usdt_balance is not None:
                    # Check if this is the first real balance update (still has paper trading balance)
                    is_first_update = abs(self.total_equity - self.config.paper_trading_balance) < 0.01
                    
                    # Update equity
                    old_equity = self.total_equity
                    self.total_equity = usdt_balance
                    
                    # If this is the first update from paper balance to real balance,
                    # update starting equity values to prevent false P&L calculations
                    if is_first_update:
                        self.starting_equity = usdt_balance
                        self.daily_starting_equity = usdt_balance
                        self.logger.info(f"First-time equity initialization: Starting equity set to ${usdt_balance:.2f}")
                        self.logger.info(f"Equity updated from paper balance ${old_equity:.2f} to real balance ${usdt_balance:.2f}")
                    else:
                        self.logger.info(f"Equity updated from ${old_equity:.2f} to ${usdt_balance:.2f}")
                    
                    # Update PnL history for metrics
                    self.pnl_history.append(usdt_balance)
                    
                    # Trim history to prevent memory issues
                    if len(self.pnl_history) > self.sharpe_window:
                        self.pnl_history = self.pnl_history[-self.sharpe_window:]
                else:
                    self.logger.warning(f"No USDT/USD/USDC balance found. Available: {balance.get('total', {})}")
            else:
                self.logger.warning("Invalid balance response from exchange")
        
        except Exception as e:
            self.logger.error(f"Error updating equity from exchange: {e}", exc_info=True)
