"""Market data collection using CCXT for Bybit exchange."""

import asyncio
import time
from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

import ccxt.async_support as ccxt

from models.market_data import (
    FundingRate, OrderBook, OrderBookLevel, OrderSide, 
    Trade, Ticker, MarketSnapshot
)
from utils.config import get_config
from utils.logger import get_logger


class MarketDataCollectorCCXT:
    """Collects real-time market data using CCXT library."""
    
    def __init__(self, symbols: List[str], max_trade_history: int = 1000):
        """
        Initialize market data collector.
        
        Args:
            symbols: List of perpetual symbols (e.g., ['BTC/USDT:USDT'])
            max_trade_history: Maximum number of trades to keep in memory
        """
        self.config = get_config()
        self.logger = get_logger(self.__class__.__name__)
        self.symbols = symbols
        self.max_trade_history = max_trade_history
        
        # Initialize exchange
        self.exchange: Optional[ccxt.Exchange] = None
        
        # Data storage
        self.orderbooks: Dict[str, OrderBook] = {}
        self.trades: Dict[str, deque] = {
            symbol: deque(maxlen=max_trade_history) for symbol in symbols
        }
        self.tickers: Dict[str, Ticker] = {}
        self.funding_rates: Dict[str, FundingRate] = {}
        
        # State
        self.is_running = False
        self.update_interval = 0.1  # 100ms updates
        
        # Callbacks
        self.callbacks: Dict[str, List[Callable]] = {
            'orderbook': [],
            'trade': [],
            'ticker': [],
            'funding': [],
            'snapshot': []
        }
        
        # Performance tracking
        self.update_count = 0
        self.last_update_time = time.time()
        self.latency_samples = deque(maxlen=100)
    
    async def initialize(self):
        """Initialize the exchange connection."""
        try:
            # Create exchange instance
            exchange_class = getattr(ccxt, self.config.exchange_id)
            self.exchange = exchange_class(self.config.to_ccxt_config())
            
            # Load markets
            await self.exchange.load_markets()
            self.logger.success(f"Connected to {self.config.exchange_id}")
            
            # Verify symbols
            for symbol in self.symbols:
                if symbol not in self.exchange.markets:
                    self.logger.warning(f"Symbol {symbol} not found in exchange markets")
                else:
                    market = self.exchange.markets[symbol]
                    self.logger.info(f"Loaded market: {symbol} - {market['type']}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize exchange: {e}", exc_info=True)
            raise
    
    def add_callback(self, event_type: str, callback: Callable):
        """Add callback for specific event type."""
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
    
    async def run(self):
        """Main loop to fetch and process market data."""
        if not self.exchange:
            await self.initialize()
        
        self.is_running = True
        self.logger.info("Starting market data collection...")
        
        # Create update tasks
        tasks = [
            asyncio.create_task(self._update_orderbooks()),
            asyncio.create_task(self._update_trades()),
            asyncio.create_task(self._update_tickers()),
            asyncio.create_task(self._update_funding_rates()),
        ]
        
        try:
            # Run all update tasks concurrently
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.logger.info("Market data collection cancelled")
        except Exception as e:
            self.logger.error(f"Error in market data collection: {e}", exc_info=True)
        finally:
            self.is_running = False
            await self.close()
    
    async def _update_orderbooks(self):
        """Continuously update order books."""
        while self.is_running:
            try:
                start_time = time.time()
                
                for symbol in self.symbols:
                    # Fetch order book
                    raw_orderbook = await self.exchange.fetch_order_book(symbol, limit=25)
                    
                    # Convert to our model
                    orderbook = self._convert_orderbook(symbol, raw_orderbook)
                    self.orderbooks[symbol] = orderbook
                    
                    # Trigger callbacks
                    await self._trigger_callbacks('orderbook', orderbook)
                    await self._check_and_emit_snapshot(symbol)
                
                # Track latency
                latency = (time.time() - start_time) * 1000
                self.latency_samples.append(latency)
                
                # Rate limiting
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                self.logger.error(f"Error updating orderbooks: {e}")
                await asyncio.sleep(1)  # Back off on error
    
    async def _update_trades(self):
        """Continuously update recent trades."""
        # Track last trade IDs to avoid duplicates
        last_trade_ids = {symbol: None for symbol in self.symbols}
        
        while self.is_running:
            try:
                for symbol in self.symbols:
                    # Fetch recent trades
                    raw_trades = await self.exchange.fetch_trades(symbol, limit=50)
                    
                    # Process new trades
                    for raw_trade in raw_trades:
                        trade_id = raw_trade['id']
                        
                        # Skip if we've seen this trade
                        if last_trade_ids[symbol] and trade_id <= last_trade_ids[symbol]:
                            continue
                        
                        # Convert to our model
                        trade = self._convert_trade(symbol, raw_trade)
                        self.trades[symbol].append(trade)
                        
                        # Trigger callbacks
                        await self._trigger_callbacks('trade', trade)
                    
                    # Update last trade ID
                    if raw_trades:
                        last_trade_ids[symbol] = raw_trades[-1]['id']
                
                await asyncio.sleep(0.5)  # Update trades every 500ms
                
            except Exception as e:
                self.logger.error(f"Error updating trades: {e}")
                await asyncio.sleep(1)
    
    async def _update_tickers(self):
        """Continuously update tickers."""
        while self.is_running:
            try:
                for symbol in self.symbols:
                    # Fetch ticker
                    raw_ticker = await self.exchange.fetch_ticker(symbol)
                    
                    # Convert to our model
                    ticker = self._convert_ticker(symbol, raw_ticker)
                    self.tickers[symbol] = ticker
                    
                    # Trigger callbacks
                    await self._trigger_callbacks('ticker', ticker)
                
                await asyncio.sleep(1)  # Update tickers every second
                
            except Exception as e:
                self.logger.error(f"Error updating tickers: {e}")
                await asyncio.sleep(2)
    
    async def _update_funding_rates(self):
        """Continuously update funding rates."""
        while self.is_running:
            try:
                for symbol in self.symbols:
                    market = self.exchange.markets.get(symbol)
                    if market and market.get('swap', False) and self.exchange.has['fetchFundingRate']:
                        try:
                            # Fetch funding rate
                            raw_funding = await self.exchange.fetch_funding_rate(symbol)
                            
                            # Convert to our model
                            funding = self._convert_funding_rate(symbol, raw_funding)
                            if funding:
                                self.funding_rates[symbol] = funding
                                
                                # Trigger callbacks
                                await self._trigger_callbacks('funding', funding)
                        except Exception as e:
                            self.logger.error(f"Error fetching funding rate for {symbol}: {e}")
                
                # Funding rates update less frequently
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Error updating funding rates: {e}")
                await asyncio.sleep(60)
    
    def _convert_orderbook(self, symbol: str, raw_orderbook: dict) -> OrderBook:
        """Convert CCXT orderbook to our model."""
        bids = []
        for bid in raw_orderbook['bids'][:25]:  # Top 25 levels
            bids.append(OrderBookLevel(
                price=Decimal(str(bid[0])),
                size=Decimal(str(bid[1]))
            ))
        
        asks = []
        for ask in raw_orderbook['asks'][:25]:  # Top 25 levels
            asks.append(OrderBookLevel(
                price=Decimal(str(ask[0])),
                size=Decimal(str(ask[1]))
            ))
        
        return OrderBook(
            symbol=symbol,
            timestamp=datetime.fromtimestamp(raw_orderbook['timestamp'] / 1000),
            bids=bids,
            asks=asks
        )
    
    def _convert_trade(self, symbol: str, raw_trade: dict) -> Trade:
        """Convert CCXT trade to our model."""
        return Trade(
            symbol=symbol,
            timestamp=datetime.fromtimestamp(raw_trade['timestamp'] / 1000),
            trade_id=str(raw_trade['id']),
            price=Decimal(str(raw_trade['price'])),
            size=Decimal(str(raw_trade['amount'])),
            side=OrderSide.BUY if raw_trade['side'] == 'buy' else OrderSide.SELL
        )
    
    def _convert_ticker(self, symbol: str, raw_ticker: dict) -> Ticker:
        """Convert CCXT ticker to our model."""
        return Ticker(
            symbol=symbol,
            timestamp=datetime.fromtimestamp((raw_ticker.get('timestamp') or time.time()*1000) / 1000),
            last_price=Decimal(str(raw_ticker.get('last', 0))),
            best_bid=Decimal(str(raw_ticker['bid'])),
            best_ask=Decimal(str(raw_ticker['ask'])),
            volume_24h=Decimal(str(raw_ticker['baseVolume'])),
            open_24h=Decimal(str(raw_ticker['open'])),
            high_24h=Decimal(str(raw_ticker['high'])),
            low_24h=Decimal(str(raw_ticker['low']))
        )
    
    def _convert_funding_rate(self, symbol: str, raw_funding: dict) -> Optional[FundingRate]:
        """Convert CCXT funding rate to our model."""
        if not raw_funding:
            return None
        
        # Handle different types of timestamp values
        timestamp = raw_funding.get('timestamp', time.time() * 1000)
        if isinstance(timestamp, str):
            try:
                timestamp = float(timestamp)
            except (ValueError, TypeError):
                timestamp = time.time() * 1000
                
        # Handle funding datetime value
        funding_datetime = raw_funding.get('fundingDatetime', time.time() * 1000)
        if isinstance(funding_datetime, str):
            try:
                # If it's already a formatted datetime string, convert directly
                if 'T' in funding_datetime:
                    funding_datetime = datetime.fromisoformat(funding_datetime.replace('Z', '+00:00'))
                    next_funding_time = funding_datetime
                else:
                    funding_datetime = float(funding_datetime)
                    next_funding_time = datetime.fromtimestamp(funding_datetime / 1000)
            except (ValueError, TypeError):
                funding_datetime = time.time() * 1000
                next_funding_time = datetime.fromtimestamp(funding_datetime / 1000)
        else:
            next_funding_time = datetime.fromtimestamp(funding_datetime / 1000)
            
        # Handle funding rate value
        funding_rate = raw_funding.get('fundingRate', 0)
        if isinstance(funding_rate, str):
            try:
                funding_rate = float(funding_rate)
            except (ValueError, TypeError):
                funding_rate = 0
                
        return FundingRate(
            symbol=symbol,
            timestamp=datetime.fromtimestamp(timestamp / 1000),
            rate=Decimal(str(funding_rate)),
            next_funding_time=next_funding_time
        )
    
    async def _check_and_emit_snapshot(self, symbol: str):
        """Check if we have complete data and emit market snapshot."""
        if symbol in self.orderbooks:
            snapshot = MarketSnapshot(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                orderbook=self.orderbooks.get(symbol),
                recent_trades=list(self.trades.get(symbol, [])),
                ticker=self.tickers.get(symbol),
                funding_rate=self.funding_rates.get(symbol)
            )
            await self._trigger_callbacks('snapshot', snapshot)
    
    async def _trigger_callbacks(self, event_type: str, data: Any):
        """Trigger all callbacks for an event type."""
        self.update_count += 1
        
        for callback in self.callbacks.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                self.logger.error(f"Error in callback: {e}", exc_info=True)
    
    async def close(self):
        """Close exchange connection."""
        if self.exchange:
            await self.exchange.close()
            self.logger.info("Exchange connection closed")
    
    def get_market_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        """Get current market snapshot for a symbol."""
        if symbol not in self.symbols:
            return None
        
        return MarketSnapshot(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            orderbook=self.orderbooks.get(symbol),
            recent_trades=list(self.trades.get(symbol, [])),
            ticker=self.tickers.get(symbol),
            funding_rate=self.funding_rates.get(symbol)
        )
    
    def get_average_latency(self) -> float:
        """Get average update latency in milliseconds."""
        if not self.latency_samples:
            return 0.0
        return sum(self.latency_samples) / len(self.latency_samples)
    
    def get_update_rate(self) -> float:
        """Get current update rate per second."""
        elapsed = time.time() - self.last_update_time
        if elapsed == 0:
            return 0.0
        return self.update_count / elapsed
    
    def stop(self):
        """Stop the market data collection."""
        self.is_running = False
