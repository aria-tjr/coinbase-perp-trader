"""Logging configuration for the trading system."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

from utils.config import get_config


# Custom theme for rich console
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red bold",
    "success": "green bold",
    "debug": "dim white",
})

console = Console(theme=custom_theme)


class TradingLogger:
    """Custom logger for trading system with rich formatting."""
    
    def __init__(self, name: str, log_file: Optional[str] = None):
        self.name = name
        self.logger = logging.getLogger(name)
        self.config = get_config()
        
        # Set log level from config
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        self.logger.setLevel(log_level)
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # Console handler with rich formatting
        console_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True,
            log_time_format="[%Y-%m-%d %H:%M:%S]"
        )
        console_handler.setLevel(log_level)
        
        # File handler
        if log_file is None:
            log_file = self.config.log_file
        
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        
        # Formatter for file handler
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        # Add handlers
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, extra=kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Log error message."""
        self.logger.error(message, exc_info=exc_info, extra=kwargs)
    
    def critical(self, message: str, exc_info: bool = True, **kwargs):
        """Log critical message."""
        self.logger.critical(message, exc_info=exc_info, extra=kwargs)
    
    def success(self, message: str, **kwargs):
        """Log success message (info level with green color)."""
        self.logger.info(f"[success]{message}[/success]", extra=kwargs)
    
    def trade(self, action: str, symbol: str, side: str, amount: float, 
              price: float, **kwargs):
        """Log trade execution."""
        message = (
            f"[bold cyan]TRADE[/bold cyan] {action} | "
            f"{symbol} | {side} | Amount: {amount:.8f} | Price: {price:.2f}"
        )
        if kwargs:
            details = " | ".join(f"{k}: {v}" for k, v in kwargs.items())
            message += f" | {details}"
        self.logger.info(message)
    
    def risk_event(self, event_type: str, message: str, **kwargs):
        """Log risk management event."""
        prefix = f"[bold yellow]RISK[/bold yellow] {event_type}"
        self.logger.warning(f"{prefix} | {message}", extra=kwargs)
    
    def performance(self, metric: str, value: float, **kwargs):
        """Log performance metric."""
        message = f"[bold green]PERFORMANCE[/bold green] {metric}: {value:.4f}"
        if kwargs:
            details = " | ".join(f"{k}: {v}" for k, v in kwargs.items())
            message += f" | {details}"
        self.logger.info(message)


# Global logger instances
_loggers = {}


def get_logger(name: str, log_file: Optional[str] = None) -> TradingLogger:
    """Get or create a logger instance."""
    if name not in _loggers:
        _loggers[name] = TradingLogger(name, log_file)
    return _loggers[name]


def setup_logging():
    """Setup global logging configuration."""
    # Set up root logger to capture third-party logs
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    
    # Add handler for third-party logs
    handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        markup=True
    )
    handler.setLevel(logging.WARNING)
    root_logger.addHandler(handler)
    
    # Suppress noisy loggers
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("ccxt").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    
    # Create main logger
    main_logger = get_logger("main")
    main_logger.info("Logging system initialized")
    
    return main_logger


# Convenience function for quick logging
def log_performance_summary(logger: TradingLogger, metrics: dict):
    """Log a comprehensive performance summary."""
    logger.info("[bold cyan]═══ Performance Summary ═══[/bold cyan]")
    
    for metric, value in metrics.items():
        if isinstance(value, float):
            if "return" in metric.lower() or "%" in metric:
                logger.performance(metric, value * 100, unit="%")
            else:
                logger.performance(metric, value)
        else:
            logger.info(f"{metric}: {value}")
    
    logger.info("[bold cyan]═════════════════════════[/bold cyan]")
