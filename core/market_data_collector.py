"""Market data collection via Coinbase International WebSocket."""

import asyncio
import json
import time
from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Set

import websockets
from websockets.client import WebSocketClientProtocol

from models.market_data import (
    FundingRate, OrderBook, OrderBookLevel, OrderSide, 
    Trade, Ticker, MarketSnapshot, WSSubscription
)
from utils.config import get_config
from utils.logger import get_logger


class MarketDataCollector:
    """Collects real-time market data from Coinbase International Exchange."""
    
    # Coinbase International WebSocket URL
    WS_URL = "wss://stream.bybit.com/v5/public/linear"
    
    def __init__(self, symbols: List[str], max_trade_history: int = 1000):
        """
        Initialize market data collector.
        
        Args:
            symbols: List of perpetual symbols to subscribe to
            max_trade_history: Maximum number of trades to keep in memory
        """
        self.config = get_config()
        self.logger = get_logger(self.__class__.__name__)
        self.symbols = symbols
        self.max_trade_history = max_trade_history
        
        # Data storage
        self.orderbooks: Dict[str, OrderBook] = {}
        self.trades: Dict[str, deque] = {
            symbol: deque(maxlen=max_trade_history) for symbol in symbols
        }
        self.tickers: Dict[str, Ticker] = {}
        self.funding_rates: Dict[str, FundingRate] = {}
        
        # WebSocket state
        self.ws: Optional[WebSocketClientProtocol] = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5  # seconds
        
        # Callbacks
        self.callbacks: Dict[str, List[Callable]] = {
            'orderbook': [],
            'trade': [],
            'ticker': [],
            'funding': [],
            'snapshot': []
        }
        
        # Performance tracking
        self.message_count = 0
        self.last_message_time = time.time()
        self.latency_samples = deque(maxlen=100)
    
    def add_callback(self, event_type: str, callback: Callable):
        """Add callback for specific event type."""
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
    
    async def connect(self):
        """Connect to WebSocket and subscribe to channels."""
        try:
            self.logger.info(f"Connecting to Coinbase International WebSocket: {self.WS_URL}")
            
            # Create WebSocket connection
            self.ws = await websockets.connect(
                self.WS_URL,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.is_connected = True
            self.reconnect_attempts = 0
            self.logger.success("WebSocket connection established")
            
            # Subscribe to channels
            await self._subscribe()
            
        except Exception as e:
            self.logger.error(f"Failed to connect: {e}", exc_info=True)
            raise
    
    async def _subscribe(self):
        """Subscribe to required channels for each symbol."""
        # Coinbase International uses different channel names
        channels = [
            "level2_batch",  # Order book updates
            "matches",       # Trades
            "ticker_batch",  # Ticker updates
            "status"         # System status
        ]
        
        # Create subscription message
        sub_msg = {
            "type": "subscribe",
            "product_ids": self.symbols,
            "channels": channels
        }
        
        # Add authentication if available
        if self.config.coinbase_api_key:
            # Note: Coinbase International may require different auth format
            sub_msg["signature"] = self._generate_signature()
            sub_msg["key"] = self.config.coinbase_api_key
            sub_msg["passphrase"] = self.config.coinbase_api_passphrase
            sub_msg["timestamp"] = str(int(time.time()))
        
        await self.ws.send(json.dumps(sub_msg))
        self.logger.info(f"Subscribed to channels: {channels} for symbols: {self.symbols}")
    
    def _generate_signature(self) -> str:
        """Generate authentication signature for WebSocket."""
        # TODO: Implement proper signature generation for Coinbase International
        # This is a placeholder - actual implementation depends on API docs
        return ""
    
    async def disconnect(self):
        """Disconnect from WebSocket."""
        if self.ws and not self.ws.closed:
            await self.ws.close()
        self.is_connected = False
        self.logger.info("WebSocket connection closed")
    
    async def run(self):
        """Main loop to receive and process WebSocket messages."""
        while True:
            try:
                if not self.is_connected:
                    await self.connect()
                
                await self._receive_messages()
                
            except websockets.exceptions.ConnectionClosed:
                self.logger.warning("WebSocket connection closed")
                self.is_connected = False
                await self._handle_reconnect()
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                self.is_connected = False
                await self._handle_reconnect()
    
    async def _receive_messages(self):
        """Receive and process WebSocket messages."""
        async for message in self.ws:
            try:
                # Track message timing
                receive_time = time.time()
                self.message_count += 1
                
                # Parse message
                data = json.loads(message)
                
                # Calculate latency if timestamp available
                if 'time' in data:
                    msg_time = datetime.fromisoformat(data['time'].replace('Z', '+00:00'))
                    latency = (datetime.utcnow() - msg_time).total_seconds() * 1000
                    self.latency_samples.append(latency)
                
                # Process message by type
                msg_type = data.get('type', '')
                
                if msg_type == 'snapshot':
                    await self._handle_snapshot(data)
                elif msg_type == 'l2update':
                    await self._handle_l2_update(data)
                elif msg_type == 'match':
                    await self._handle_trade(data)
                elif msg_type == 'ticker':
                    await self._handle_ticker(data)
                elif msg_type == 'status':
                    await self._handle_status(data)
                elif msg_type == 'error':
                    self.logger.error(f"Error message: {data}")
                elif msg_type == 'subscriptions':
                    self.logger.info(f"Active subscriptions: {data}")
                else:
                    self.logger.debug(f"Unknown message type: {msg_type}")
                
                # Track processing time
                process_time = (time.time() - receive_time) * 1000
                if process_time > self.config.max_latency_ms:
                    self.logger.warning(
                        f"Slow message processing: {process_time:.2f}ms for {msg_type}"
                    )
                
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse message: {e}")
            except Exception as e:
                self.logger.error(f"Error processing message: {e}", exc_info=True)
    
    async def _handle_snapshot(self, data: dict):
        """Handle order book snapshot message."""
        try:
            symbol = data['product_id']
            
            # Parse bids and asks
            bids = []
            for bid in data.get('bids', []):
                bids.append(OrderBookLevel(
                    price=Decimal(bid[0]),
                    size=Decimal(bid[1])
                ))
            
            asks = []
            for ask in data.get('asks', []):
                asks.append(OrderBookLevel(
                    price=Decimal(ask[0]),
                    size=Decimal(ask[1])
                ))
            
            # Create order book
            orderbook = OrderBook(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                bids=sorted(bids, key=lambda x: x.price, reverse=True),
                asks=sorted(asks, key=lambda x: x.price),
                sequence=data.get('sequence')
            )
            
            self.orderbooks[symbol] = orderbook
            
            # Trigger callbacks
            await self._trigger_callbacks('orderbook', orderbook)
            await self._check_and_emit_snapshot(symbol)
            
        except Exception as e:
            self.logger.error(f"Error handling snapshot: {e}", exc_info=True)
    
    async def _handle_l2_update(self, data: dict):
        """Handle incremental order book update."""
        try:
            symbol = data['product_id']
            
            if symbol not in self.orderbooks:
                self.logger.warning(f"Received update for unknown orderbook: {symbol}")
                return
            
            orderbook = self.orderbooks[symbol]
            changes = data.get('changes', [])
            
            for change in changes:
                side, price_str, size_str = change
                price = Decimal(price_str)
                size = Decimal(size_str)
                
                if side == 'buy':
                    self._update_orderbook_side(orderbook.bids, price, size)
                    orderbook.bids.sort(key=lambda x: x.price, reverse=True)
                else:
                    self._update_orderbook_side(orderbook.asks, price, size)
                    orderbook.asks.sort(key=lambda x: x.price)
            
            orderbook.timestamp = datetime.utcnow()
            orderbook.sequence = data.get('sequence')
            
            # Trigger callbacks
            await self._trigger_callbacks('orderbook', orderbook)
            await self._check_and_emit_snapshot(symbol)
            
        except Exception as e:
            self.logger.error(f"Error handling L2 update: {e}", exc_info=True)
    
    def _update_orderbook_side(self, levels: List[OrderBookLevel], 
                               price: Decimal, size: Decimal):
        """Update order book side with new price level."""
        # Remove level if size is 0
        if size == 0:
            levels[:] = [lvl for lvl in levels if lvl.price != price]
        else:
            # Update existing or add new level
            for i, level in enumerate(levels):
                if level.price == price:
                    levels[i] = OrderBookLevel(price, size)
                    return
            levels.append(OrderBookLevel(price, size))
    
    async def _handle_trade(self, data: dict):
        """Handle trade/match message."""
        try:
            symbol = data['product_id']
            
            trade = Trade(
                symbol=symbol,
                timestamp=datetime.fromisoformat(data['time'].replace('Z', '+00:00')),
                trade_id=data['trade_id'],
                price=Decimal(data['price']),
                size=Decimal(data['size']),
                side=OrderSide.BUY if data['side'] == 'buy' else OrderSide.SELL,
                sequence=data.get('sequence')
            )
            
            self.trades[symbol].append(trade)
            
            # Trigger callbacks
            await self._trigger_callbacks('trade', trade)
            await self._check_and_emit_snapshot(symbol)
            
        except Exception as e:
            self.logger.error(f"Error handling trade: {e}", exc_info=True)
    
    async def _handle_ticker(self, data: dict):
        """Handle ticker update message."""
        try:
            symbol = data['product_id']
            
            ticker = Ticker(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                last_price=Decimal(data['price']),
                best_bid=Decimal(data['best_bid']),
                best_ask=Decimal(data['best_ask']),
                volume_24h=Decimal(data['volume_24h']),
                open_24h=Decimal(data['open_24h']),
                high_24h=Decimal(data['high_24h']),
                low_24h=Decimal(data['low_24h'])
            )
            
            self.tickers[symbol] = ticker
            
            # Trigger callbacks
            await self._trigger_callbacks('ticker', ticker)
            
        except Exception as e:
            self.logger.error(f"Error handling ticker: {e}", exc_info=True)
    
    async def _handle_status(self, data: dict):
        """Handle status message (funding rates for perpetuals)."""
        try:
            # Extract funding rate if available
            if 'products' in data:
                for product in data['products']:
                    if 'funding_rate' in product:
                        symbol = product['id']
                        funding = FundingRate(
                            symbol=symbol,
                            timestamp=datetime.utcnow(),
                            rate=Decimal(product['funding_rate']),
                            next_funding_time=datetime.fromisoformat(
                                product.get('next_funding_time', '').replace('Z', '+00:00')
                            )
                        )
                        self.funding_rates[symbol] = funding
                        await self._trigger_callbacks('funding', funding)
        
        except Exception as e:
            self.logger.error(f"Error handling status: {e}", exc_info=True)
    
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
        for callback in self.callbacks.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                self.logger.error(f"Error in callback: {e}", exc_info=True)
    
    async def _handle_reconnect(self):
        """Handle reconnection logic."""
        self.reconnect_attempts += 1
        
        if self.reconnect_attempts > self.max_reconnect_attempts:
            self.logger.error("Max reconnection attempts reached. Giving up.")
            raise Exception("Failed to reconnect to WebSocket")
        
        delay = self.reconnect_delay * self.reconnect_attempts
        self.logger.info(f"Reconnecting in {delay} seconds... (attempt {self.reconnect_attempts})")
        await asyncio.sleep(delay)
    
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
        """Get average WebSocket message latency in milliseconds."""
        if not self.latency_samples:
            return 0.0
        return sum(self.latency_samples) / len(self.latency_samples)
    
    def get_message_rate(self) -> float:
        """Get current message rate per second."""
        elapsed = time.time() - self.last_message_time
        if elapsed == 0:
            return 0.0
        return self.message_count / elapsed
