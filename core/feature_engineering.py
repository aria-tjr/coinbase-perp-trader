"""Feature engineering for trading signals."""

import numpy as np
import pandas as pd
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass

import ta
from ta.volatility import AverageTrueRange, BollingerBands
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, ADXIndicator, EMAIndicator, SMAIndicator
from ta.volume import OnBalanceVolumeIndicator, VolumeWeightedAveragePrice

from models.market_data import Candle, MarketSnapshot, OrderBook, Trade
from utils.logger import get_logger


@dataclass
class MarketFeatures:
    """Aggregated market features for trading decisions."""
    timestamp: pd.Timestamp
    symbol: str
    
    # Price features
    price: float
    price_change_1m: float
    price_change_5m: float
    log_return_1m: float
    
    # Technical indicators
    rsi: float
    macd: float
    macd_signal: float
    bb_upper: float
    bb_lower: float
    bb_width: float
    atr: float
    adx: float
    
    # Volatility features
    realized_vol_5m: float
    realized_vol_1h: float
    vol_ratio: float  # 5m/1h volatility ratio
    
    # Order flow features
    order_imbalance: float
    trade_flow_imbalance: float
    bid_ask_spread: float
    spread_percentage: float
    
    # Microstructure
    vwap: float
    vwap_deviation: float  # (price - vwap) / vwap
    trade_intensity: float  # trades per minute
    avg_trade_size: float
    
    # Funding
    funding_rate: float
    funding_pressure: float  # annualized rate / threshold


class FeatureEngineering:
    """Extract and compute trading features from market data."""
    
    def __init__(self, lookback_periods: Dict[str, int] = None):
        """
        Initialize feature engineering.
        
        Args:
            lookback_periods: Dictionary of lookback periods for indicators
        """
        self.logger = get_logger(self.__class__.__name__)
        
        # Default lookback periods
        self.lookback_periods = lookback_periods or {
            'rsi': 14,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'bb': 20,
            'atr': 14,
            'adx': 14,
            'volatility_short': 60,  # 5 minutes at 5s candles
            'volatility_long': 720,  # 1 hour at 5s candles
        }
        
        # Data storage
        self.candle_history: Dict[str, deque] = {}
        self.max_candles = 1000  # Keep last 1000 candles
        
        # Pre-computed features cache
        self.feature_cache: Dict[str, MarketFeatures] = {}
        
        self.logger.info("Feature engineering initialized")
    
    def update_candles(self, symbol: str, candle: Candle):
        """Update candle history for a symbol."""
        if symbol not in self.candle_history:
            self.candle_history[symbol] = deque(maxlen=self.max_candles)
        
        self.candle_history[symbol].append(candle)
    
    def compute_features(self, snapshot: MarketSnapshot) -> Optional[MarketFeatures]:
        """
        Compute all features from market snapshot.
        
        Args:
            snapshot: Current market snapshot
            
        Returns:
            MarketFeatures object or None if insufficient data
        """
        symbol = snapshot.symbol
        
        # Check if we have enough candle history
        if symbol not in self.candle_history or len(self.candle_history[symbol]) < 100:
            self.logger.debug(f"Insufficient candle history for {symbol}")
            return None
        
        try:
            # Convert candles to DataFrame
            candles = list(self.candle_history[symbol])
            df = self._candles_to_dataframe(candles)
            
            # Compute technical indicators
            tech_features = self._compute_technical_indicators(df)
            
            # Compute volatility features
            vol_features = self._compute_volatility_features(df)
            
            # Compute order flow features
            flow_features = self._compute_order_flow_features(snapshot)
            
            # Compute microstructure features
            micro_features = self._compute_microstructure_features(snapshot)
            
            # Get latest values
            latest_idx = len(df) - 1
            current_price = float(df['close'].iloc[-1])
            
            # Price changes
            price_1m_ago = float(df['close'].iloc[-12]) if len(df) > 12 else current_price
            price_5m_ago = float(df['close'].iloc[-60]) if len(df) > 60 else current_price
            
            # Create features object
            features = MarketFeatures(
                timestamp=pd.Timestamp.now(),
                symbol=symbol,
                
                # Price features
                price=current_price,
                price_change_1m=(current_price - price_1m_ago) / price_1m_ago * 100,
                price_change_5m=(current_price - price_5m_ago) / price_5m_ago * 100,
                log_return_1m=np.log(current_price / price_1m_ago),
                
                # Technical indicators
                rsi=tech_features['rsi'],
                macd=tech_features['macd'],
                macd_signal=tech_features['macd_signal'],
                bb_upper=tech_features['bb_upper'],
                bb_lower=tech_features['bb_lower'],
                bb_width=tech_features['bb_width'],
                atr=tech_features['atr'],
                adx=tech_features['adx'],
                
                # Volatility
                realized_vol_5m=vol_features['vol_5m'],
                realized_vol_1h=vol_features['vol_1h'],
                vol_ratio=vol_features['vol_ratio'],
                
                # Order flow
                order_imbalance=flow_features['order_imbalance'],
                trade_flow_imbalance=flow_features['trade_flow_imbalance'],
                bid_ask_spread=flow_features['spread'],
                spread_percentage=flow_features['spread_pct'],
                
                # Microstructure
                vwap=micro_features['vwap'],
                vwap_deviation=micro_features['vwap_deviation'],
                trade_intensity=micro_features['trade_intensity'],
                avg_trade_size=micro_features['avg_trade_size'],
                
                # Funding
                funding_rate=micro_features['funding_rate'],
                funding_pressure=micro_features['funding_pressure']
            )
            
            # Cache the features
            self.feature_cache[symbol] = features
            
            return features
            
        except Exception as e:
            self.logger.error(f"Error computing features: {e}", exc_info=True)
            return None
    
    def _candles_to_dataframe(self, candles: List[Candle]) -> pd.DataFrame:
        """Convert candle objects to pandas DataFrame."""
        data = []
        for candle in candles:
            data.append({
                'timestamp': candle.timestamp,
                'open': float(candle.open),
                'high': float(candle.high),
                'low': float(candle.low),
                'close': float(candle.close),
                'volume': float(candle.volume)
            })
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df
    
    def _compute_technical_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Compute technical indicators."""
        # RSI
        rsi = RSIIndicator(
            close=df['close'],
            window=self.lookback_periods['rsi']
        )
        rsi_values = rsi.rsi()
        
        # MACD
        macd = MACD(
            close=df['close'],
            window_slow=self.lookback_periods['macd_slow'],
            window_fast=self.lookback_periods['macd_fast'],
            window_sign=self.lookback_periods['macd_signal']
        )
        macd_line = macd.macd()
        macd_signal = macd.macd_signal()
        
        # Bollinger Bands
        bb = BollingerBands(
            close=df['close'],
            window=self.lookback_periods['bb'],
            window_dev=2
        )
        bb_upper = bb.bollinger_hband()
        bb_lower = bb.bollinger_lband()
        bb_width = bb.bollinger_wband()
        
        # ATR
        atr = AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=self.lookback_periods['atr']
        )
        atr_values = atr.average_true_range()
        
        # ADX
        adx = ADXIndicator(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=self.lookback_periods['adx']
        )
        adx_values = adx.adx()
        
        # Get latest values
        return {
            'rsi': float(rsi_values.iloc[-1]) if not rsi_values.empty else 50.0,
            'macd': float(macd_line.iloc[-1]) if not macd_line.empty else 0.0,
            'macd_signal': float(macd_signal.iloc[-1]) if not macd_signal.empty else 0.0,
            'bb_upper': float(bb_upper.iloc[-1]) if not bb_upper.empty else 0.0,
            'bb_lower': float(bb_lower.iloc[-1]) if not bb_lower.empty else 0.0,
            'bb_width': float(bb_width.iloc[-1]) if not bb_width.empty else 0.0,
            'atr': float(atr_values.iloc[-1]) if not atr_values.empty else 0.0,
            'adx': float(adx_values.iloc[-1]) if not adx_values.empty else 0.0,
        }
    
    def _compute_volatility_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Compute volatility-based features."""
        # Log returns
        log_returns = np.log(df['close'] / df['close'].shift(1)).dropna()
        
        # Short-term volatility (5 minutes)
        short_window = min(self.lookback_periods['volatility_short'], len(log_returns))
        vol_5m = log_returns.tail(short_window).std() * np.sqrt(252 * 24 * 12)  # Annualized
        
        # Long-term volatility (1 hour)
        long_window = min(self.lookback_periods['volatility_long'], len(log_returns))
        vol_1h = log_returns.tail(long_window).std() * np.sqrt(252 * 24)  # Annualized
        
        # Volatility ratio
        vol_ratio = vol_5m / vol_1h if vol_1h > 0 else 1.0
        
        return {
            'vol_5m': vol_5m,
            'vol_1h': vol_1h,
            'vol_ratio': vol_ratio
        }
    
    def _compute_order_flow_features(self, snapshot: MarketSnapshot) -> Dict[str, float]:
        """Compute order flow imbalance features."""
        features = {
            'order_imbalance': 0.0,
            'trade_flow_imbalance': 0.0,
            'spread': 0.0,
            'spread_pct': 0.0
        }
        
        # Order book imbalance
        if snapshot.orderbook:
            features['order_imbalance'] = float(snapshot.orderbook.get_order_imbalance())
            if snapshot.orderbook.spread:
                features['spread'] = float(snapshot.orderbook.spread)
            if snapshot.orderbook.spread_percentage:
                features['spread_pct'] = float(snapshot.orderbook.spread_percentage)
        
        # Trade flow imbalance
        features['trade_flow_imbalance'] = float(snapshot.get_trade_flow_imbalance())
        
        return features
    
    def _compute_microstructure_features(self, snapshot: MarketSnapshot) -> Dict[str, float]:
        """Compute market microstructure features."""
        features = {
            'vwap': 0.0,
            'vwap_deviation': 0.0,
            'trade_intensity': 0.0,
            'avg_trade_size': 0.0,
            'funding_rate': 0.0,
            'funding_pressure': 0.0
        }
        
        # VWAP
        vwap = snapshot.get_vwap()
        if vwap and snapshot.orderbook and snapshot.orderbook.mid_price:
            features['vwap'] = float(vwap)
            mid_price = float(snapshot.orderbook.mid_price)
            features['vwap_deviation'] = (mid_price - features['vwap']) / features['vwap']
        
        # Trade intensity and size
        if snapshot.recent_trades:
            # Trades per minute
            if len(snapshot.recent_trades) > 1:
                time_span = (snapshot.recent_trades[-1].timestamp - 
                           snapshot.recent_trades[0].timestamp).total_seconds()
                if time_span > 0:
                    features['trade_intensity'] = len(snapshot.recent_trades) / (time_span / 60)
            
            # Average trade size
            total_size = sum(float(t.size) for t in snapshot.recent_trades)
            features['avg_trade_size'] = total_size / len(snapshot.recent_trades)
        
        # Funding rate
        if snapshot.funding_rate:
            features['funding_rate'] = float(snapshot.funding_rate.rate)
            features['funding_pressure'] = float(snapshot.funding_rate.annualized_rate) / 0.25
        
        return features
    
    def get_feature_vector(self, features: MarketFeatures) -> np.ndarray:
        """Convert MarketFeatures to numpy array for ML models."""
        return np.array([
            features.price_change_1m,
            features.price_change_5m,
            features.log_return_1m,
            features.rsi,
            features.macd,
            features.macd_signal,
            features.bb_width,
            features.atr,
            features.adx,
            features.realized_vol_5m,
            features.realized_vol_1h,
            features.vol_ratio,
            features.order_imbalance,
            features.trade_flow_imbalance,
            features.spread_percentage,
            features.vwap_deviation,
            features.trade_intensity,
            features.funding_pressure
        ])
    
    def get_feature_names(self) -> List[str]:
        """Get feature names for ML models."""
        return [
            'price_change_1m', 'price_change_5m', 'log_return_1m',
            'rsi', 'macd', 'macd_signal', 'bb_width', 'atr', 'adx',
            'realized_vol_5m', 'realized_vol_1h', 'vol_ratio',
            'order_imbalance', 'trade_flow_imbalance', 'spread_percentage',
            'vwap_deviation', 'trade_intensity', 'funding_pressure'
        ]
