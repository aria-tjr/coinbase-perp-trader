"""Alert system for trading notifications."""

import asyncio
from datetime import datetime
from typing import List, Optional
import aiohttp

from utils.logger import get_logger


class AlertManager:
    """Manages alerts and notifications."""
    
    def __init__(self, telegram_token: str, chat_id: str):
        """
        Initialize alert manager.
        
        Args:
            telegram_token: Telegram bot token
            chat_id: Telegram chat ID for notifications
        """
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.logger = get_logger(self.__class__.__name__)
        
        # Rate limiting
        self.last_alert_time = {}
        self.min_alert_interval = 60  # seconds
        
        # Alert queue for batching
        self.alert_queue: List[str] = []
        self.queue_lock = asyncio.Lock()
        
        self.logger.info("Alert manager initialized")
    
    async def send_alert(self, message: str, priority: str = 'normal'):
        """
        Send alert via Telegram.
        
        Args:
            message: Alert message
            priority: Alert priority ('high', 'normal', 'low')
        """
        try:
            # Rate limiting check
            alert_key = f"{priority}:{message[:50]}"
            now = datetime.now()
            
            if alert_key in self.last_alert_time:
                time_since_last = (now - self.last_alert_time[alert_key]).total_seconds()
                if time_since_last < self.min_alert_interval and priority != 'high':
                    return  # Skip duplicate alerts
            
            # Format message with timestamp
            formatted_message = f"🕐 {now.strftime('%H:%M:%S')}\n{message}"
            
            # Send via Telegram
            await self._send_telegram_message(formatted_message)
            
            # Update rate limiting
            self.last_alert_time[alert_key] = now
            
        except Exception as e:
            self.logger.error(f"Failed to send alert: {e}")
    
    async def _send_telegram_message(self, message: str):
        """Send message via Telegram API."""
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Telegram API error: {error_text}")
    
    async def send_trade_alert(self, action: str, symbol: str, side: str, 
                              size: float, price: float, pnl: Optional[float] = None):
        """Send trade-specific alert."""
        emoji = "🟢" if side.lower() == 'buy' else "🔴"
        
        message = f"{emoji} <b>{action}</b>\n"
        message += f"Symbol: {symbol}\n"
        message += f"Side: {side}\n"
        message += f"Size: {size:.4f}\n"
        message += f"Price: ${price:,.2f}"
        
        if pnl is not None:
            pnl_emoji = "💰" if pnl > 0 else "💸"
            message += f"\nP&L: {pnl_emoji} ${pnl:,.2f}"
        
        await self.send_alert(message, priority='high')
    
    async def send_risk_alert(self, risk_level: str, metrics: dict):
        """Send risk management alert."""
        emoji_map = {
            'low': '🟢',
            'moderate': '🟡',
            'high': '🟠',
            'critical': '🔴',
            'halt': '🛑'
        }
        
        emoji = emoji_map.get(risk_level, '⚠️')
        
        message = f"{emoji} <b>RISK ALERT: {risk_level.upper()}</b>\n"
        
        for key, value in metrics.items():
            if isinstance(value, float):
                if 'pct' in key.lower() or 'rate' in key.lower():
                    message += f"{key}: {value:.2%}\n"
                else:
                    message += f"{key}: {value:.2f}\n"
            else:
                message += f"{key}: {value}\n"
        
        priority = 'high' if risk_level in ['critical', 'halt'] else 'normal'
        await self.send_alert(message, priority=priority)
    
    async def send_performance_summary(self, metrics: dict):
        """Send daily performance summary."""
        pnl = metrics.get('daily_pnl_pct', 0)
        emoji = "📈" if pnl > 0 else "📉" if pnl < 0 else "➖"
        
        message = f"{emoji} <b>Daily Performance Summary</b>\n"
        message += f"━━━━━━━━━━━━━━━━━━━━\n"
        
        # Format metrics
        if 'daily_pnl_pct' in metrics:
            message += f"Daily P&L: {metrics['daily_pnl_pct']:.2%}\n"
        
        if 'total_equity' in metrics:
            message += f"Total Equity: ${metrics['total_equity']:,.2f}\n"
        
        if 'sharpe_ratio' in metrics:
            message += f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}\n"
        
        if 'win_rate' in metrics:
            message += f"Win Rate: {metrics['win_rate']:.1f}%\n"
        
        if 'total_trades' in metrics:
            message += f"Total Trades: {metrics['total_trades']}\n"
        
        if 'max_drawdown' in metrics:
            message += f"Max Drawdown: {metrics['max_drawdown']:.2%}\n"
        
        await self.send_alert(message, priority='normal')
    
    async def queue_alert(self, message: str):
        """Queue alert for batch sending."""
        async with self.queue_lock:
            self.alert_queue.append(message)
    
    async def flush_alert_queue(self):
        """Send all queued alerts as a batch."""
        async with self.queue_lock:
            if not self.alert_queue:
                return
            
            # Combine messages
            batch_message = "\n━━━━━━━━━━━━━━━━━━━━\n".join(self.alert_queue)
            self.alert_queue.clear()
        
        await self.send_alert(batch_message)
