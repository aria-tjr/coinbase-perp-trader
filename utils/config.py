"""Configuration management for the trading system."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class TradingConfig(BaseSettings):
    """Trading system configuration."""
    
    # API Credentials - Mainnet
    bybit_api_key: str = Field(..., env="BYBIT_API_KEY")
    bybit_api_secret: str = Field(..., env="BYBIT_API_SECRET")
    
    # API Credentials - Testnet
    bybit_testnet_api_key: Optional[str] = Field(None, env="BYBIT_TESTNET_API_KEY")
    bybit_testnet_api_secret: Optional[str] = Field(None, env="BYBIT_TESTNET_API_SECRET")
    
    # Exchange Settings
    exchange_id: str = Field(default="bybit", env="EXCHANGE_ID")
    exchange_type: str = Field(default="swap", env="EXCHANGE_TYPE")
    default_symbol: str = Field(default="BTCUSDT", env="DEFAULT_SYMBOL")
    
    # Risk Parameters
    base_leverage: int = Field(default=5, env="BASE_LEVERAGE")
    max_leverage: int = Field(default=25, env="MAX_LEVERAGE")  # Bybit allows higher leverage
    daily_drawdown_limit: float = Field(default=0.05, env="DAILY_DRAWDOWN_LIMIT")
    position_stop_loss: float = Field(default=0.006, env="POSITION_STOP_LOSS")
    position_take_profit: float = Field(default=0.009, env="POSITION_TAKE_PROFIT")
    max_position_size_pct: float = Field(default=0.01, env="MAX_POSITION_SIZE_PCT")
    
    # Database Configuration
    timescale_host: str = Field(default="localhost", env="TIMESCALE_HOST")
    timescale_port: int = Field(default=5432, env="TIMESCALE_PORT")
    timescale_db: str = Field(default="trading_db", env="TIMESCALE_DB")
    timescale_user: str = Field(default="trading_user", env="TIMESCALE_USER")
    timescale_password: str = Field(..., env="TIMESCALE_PASSWORD")
    
    # Kafka Configuration
    kafka_bootstrap_servers: str = Field(default="localhost:9092", env="KAFKA_BOOTSTRAP_SERVERS")
    kafka_topic_market_data: str = Field(default="market-data", env="KAFKA_TOPIC_MARKET_DATA")
    kafka_topic_signals: str = Field(default="trading-signals", env="KAFKA_TOPIC_SIGNALS")
    
    # Monitoring
    monitoring_port: int = Field(default=8000, env="MONITORING_PORT")
    prometheus_port: int = Field(default=9090, env="PROMETHEUS_PORT")
    
    # Alerts
    telegram_bot_token: Optional[str] = Field(None, env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(None, env="TELEGRAM_CHAT_ID")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/trading.log", env="LOG_FILE")
    
    # Trading Mode
    trading_mode: str = Field(default="paper", env="TRADING_MODE")
    paper_trading_balance: float = Field(default=10000, env="PAPER_TRADING_BALANCE")
    
    # ML Model Paths
    lstm_model_path: str = Field(default="models/lstm_predictor.pth", env="LSTM_MODEL_PATH")
    rl_policy_path: str = Field(default="models/rl_policy.pth", env="RL_POLICY_PATH")
    
    # Performance Thresholds
    target_daily_return: float = Field(default=0.02, env="TARGET_DAILY_RETURN")
    sharpe_threshold: float = Field(default=2.0, env="SHARPE_THRESHOLD")
    max_latency_ms: int = Field(default=100, env="MAX_LATENCY_MS")
    max_funding_rate: float = Field(default=0.0025, env="MAX_FUNDING_RATE")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @validator("trading_mode")
    def validate_trading_mode(cls, v):
        if v not in ["paper", "live"]:
            raise ValueError("trading_mode must be 'paper' or 'live'")
        return v
    
    @property
    def database_url(self) -> str:
        """Get database connection URL."""
        return (
            f"postgresql://{self.timescale_user}:{self.timescale_password}"
            f"@{self.timescale_host}:{self.timescale_port}/{self.timescale_db}"
        )
    
    @property
    def is_live_trading(self) -> bool:
        """Check if in live trading mode."""
        return self.trading_mode == "live"
    
    def to_ccxt_config(self, sandbox: bool = False) -> dict:
        """Convert config to CCXT exchange configuration.
        
        Args:
            sandbox: If True, use testnet endpoints and credentials
        """
        if sandbox:
            # Use testnet credentials and endpoints
            if not self.bybit_testnet_api_key or not self.bybit_testnet_api_secret:
                raise ValueError("Testnet API credentials not configured. Please set BYBIT_TESTNET_API_KEY and BYBIT_TESTNET_API_SECRET")
                
            config = {
                'apiKey': self.bybit_testnet_api_key,
                'secret': self.bybit_testnet_api_secret,
                'enableRateLimit': True,
                'sandbox': True,  # Enable sandbox mode
                'options': {
                    'defaultType': 'swap',  # For perpetual futures
                    'unified': True,  # Use Bybit unified trading account
                }
            }
        else:
            # Use mainnet credentials and endpoints
            config = {
                'apiKey': self.bybit_api_key,
                'secret': self.bybit_api_secret,
                'enableRateLimit': True,
                'sandbox': False,
                'options': {
                    'defaultType': 'swap',  # For perpetual futures
                    'unified': True,  # Use Bybit unified trading account
                }
            }
        
        return config
    
    def get_websocket_url(self, sandbox: bool = False) -> str:
        """Get Bybit WebSocket URL.
        
        Args:
            sandbox: If True, use testnet WebSocket endpoint
        """
        if sandbox:
            # Use testnet WebSocket for testing
            return "wss://stream-testnet.bybit.com/v5/public/linear"
        else:
            # Use mainnet WebSocket for real market data
            return "wss://stream.bybit.com/v5/public/linear"


def load_config(env_file: Optional[str] = None) -> TradingConfig:
    """Load configuration from environment variables."""
    if env_file:
        load_dotenv(env_file)
    else:
        # Try to find .env file
        env_path = Path(".env")
        if env_path.exists():
            load_dotenv(env_path)
    
    return TradingConfig()


# Global config instance
config = None


def get_config() -> TradingConfig:
    """Get global configuration instance."""
    global config
    if config is None:
        config = load_config()
    return config
