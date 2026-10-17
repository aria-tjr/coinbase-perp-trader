# Bybit Perpetual Trading Bot

> **Note on the name:** despite the repository name `coinbase-perp-trader`, this is a **Bybit** USDT-perpetual bot (via `ccxt`). It started as a Coinbase International project and was moved to Bybit; some older docs (e.g. `PROJECT_SUMMARY.md`) still mention Coinbase.

An experimental, aggressive trading bot for Bybit perpetual futures. Its design goal is ≥2% daily return; that is a **target, not a measured result**.

## ⚠️ Project status (read first)

- **The `models/` package is missing from the repository.** `core/`, `strategies/`, `backtest*.py` and `position_manager.py` import `models.market_data`, `models.positions` and `models.orders`, so the bot and the backtests **do not run as published** until that package is restored.
- **ML and RL strategies are planned, not implemented:** `strategies/ml_predictor.py` and `strategies/rl_policy.py` are empty files. Only `momentum_breakout.py` and `mean_reversion.py` contain strategy code.
- **All backtest figures in this repo come from synthetic data.** `backtest.py` (and the aggressive/enhanced variants) generate random-walk candles with `generate_synthetic_data()`; there is no real-market backtest yet.

## 🚀 Features

- **Multi-Strategy Trading**: Momentum breakout and mean reversion (ML-based prediction and reinforcement learning are planned; the files are empty)
- **Aggressive Risk Management**: Dynamic leverage adjustment, real-time drawdown monitoring
- **High-Frequency Execution**: Sub-100ms order execution with advanced retry logic
- **Real-time Monitoring**: Prometheus metrics, Telegram alerts, web dashboard
- **Paper Trading**: Full simulation mode for strategy testing
- **Advanced Analytics**: Performance tracking, Sharpe ratio optimization

## 📊 Performance Targets (design goals, not achieved results)

- **Daily Return**: ≥2%
- **Sharpe Ratio**: ≥2.0
- **Max Drawdown**: <5% daily
- **Order Latency**: <100ms
- **Success Rate**: >90%

## 🛠️ Installation

### Prerequisites

- Python 3.11+
- PostgreSQL (TimescaleDB recommended)
- Redis (optional, for caching)
- Kafka (optional, for streaming)

### Quick Setup

```bash
# Clone the repository
git clone https://github.com/aria-tjr/coinbase-perp-trader.git
cd coinbase-perp-trader

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your Bybit API credentials
nano .env
```

### Environment Configuration

Update `.env` with your Bybit API credentials:

```bash
# Bybit API Configuration
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here

# Trading Configuration
EXCHANGE_ID=bybit
DEFAULT_SYMBOL=BTCUSDT
TRADING_MODE=paper  # or 'live'

# Risk Management
BASE_LEVERAGE=5
MAX_LEVERAGE=25
DAILY_DRAWDOWN_LIMIT=0.05
```

## 🎯 Quick Start

### Paper Trading (Recommended for testing)

```bash
# Start with default BTC/USDT paper trading
python main.py --symbol BTCUSDT --mode paper

# Test with different symbol
python main.py --symbol ETHUSDT --mode paper
```

### Live Trading

⚠️ **DANGER ZONE**: Live trading involves real money and risk!

```bash
# Ensure you've tested thoroughly in paper mode first
python main.py --symbol BTCUSDT --mode live
```

## 📈 Trading Strategies

### 1. Momentum Breakout
- Detects strong price momentum with volume confirmation
- Uses dynamic stop-losses and trailing profits
- Optimized for trending markets

### 2. Mean Reversion
- Identifies oversold/overbought conditions
- RSI and Bollinger Band based entries
- Quick scalping approach

### 3. ML Predictor
- LSTM neural network for price prediction
- Multi-timeframe feature engineering
- Continuously retrained on recent data

### 4. Reinforcement Learning
- Deep Q-Network (DQN) for optimal action selection
- Learns from historical performance
- Adapts to changing market conditions

## 🔧 Configuration

### Risk Parameters

```python
BASE_LEVERAGE = 5           # Starting leverage
MAX_LEVERAGE = 25           # Maximum allowed leverage (Bybit limit)
DAILY_DRAWDOWN_LIMIT = 0.05 # 5% daily drawdown limit
POSITION_STOP_LOSS = 0.006  # 0.6% stop loss per position
POSITION_TAKE_PROFIT = 0.009 # 0.9% take profit per position
```

### Performance Tuning

```python
TARGET_DAILY_RETURN = 0.02  # 2% daily target
SHARPE_THRESHOLD = 2.0      # Minimum Sharpe ratio
MAX_LATENCY_MS = 100        # Maximum order latency
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Layer    │    │  Strategy Core  │    │ Execution Layer │
│                 │    │                 │    │                 │
│ • Market Data   │───▶│ • Signal Gen    │───▶│ • Order Mgmt    │
│ • WebSocket     │    │ • Risk Mgmt     │    │ • Position Mgmt │
│ • TimescaleDB   │    │ • ML Models     │    │ • Bybit API     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Monitoring     │    │   Alerting      │    │   Logging       │
│                 │    │                 │    │                 │
│ • Prometheus    │    │ • Telegram      │    │ • Structured    │
│ • Grafana       │    │ • Email         │    │ • Performance   │
│ • Web Dashboard │    │ • Webhooks      │    │ • Error Tracking│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📊 Monitoring & Analytics

### Real-time Dashboard
Access the monitoring dashboard at http://localhost:8000

- Live P&L tracking
- Position management
- Risk metrics
- Performance analytics

### Telegram Alerts
Set up instant notifications:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Prometheus Metrics
Key metrics exported:

- `bybit_bot_pnl_total`: Total P&L
- `bybit_bot_positions_open`: Open positions count
- `bybit_bot_orders_total`: Total orders placed
- `bybit_bot_latency_seconds`: Order execution latency

## 🧪 Backtesting

> ⚠️ `backtest.py` runs on **synthetic random-walk candles** (`generate_synthetic_data()`), not historical data, and needs the missing `models/` package.

```bash
# Options: --symbol, --start-date, --end-date (required), --initial-capital, --output
python backtest.py --start-date 2024-01-01 --end-date 2024-03-01 --symbol BTC/USDT:USDT

# Aggressive variant
python backtest_aggressive.py --start-date 2024-01-01 --end-date 2024-03-01
```

## 🚨 Risk Management

### Built-in Safeguards

1. **Daily Drawdown Limits**: Automatic halt at 5% daily loss
2. **Position Size Controls**: Max 1% of equity per position
3. **Leverage Limits**: Dynamic adjustment based on volatility
4. **Emergency Stop**: Instant position closure on critical errors
5. **Connection Monitoring**: Automatic reconnection handling

### Safety Features

- Real-time risk calculation
- Automatic position sizing
- Stop-loss on every trade
- Funding rate monitoring
- Slippage protection

## 🔍 Troubleshooting

### Common Issues

**Connection Errors**
```bash
# Check API credentials
python validate_system.py

# Test connection
python -c "import ccxt; exchange = ccxt.bybit({'apiKey': 'key', 'secret': 'secret'}); print(exchange.fetch_ticker('BTCUSDT'))"
```

**Performance Issues**
```bash
# Monitor system resources
python -c "import psutil; print(f'CPU: {psutil.cpu_percent()}%, RAM: {psutil.virtual_memory().percent}%')"

# Check database performance
psql -d trading_db -c "SELECT count(*) FROM market_data WHERE timestamp > NOW() - INTERVAL '1 hour';"
```

## 📈 Performance

No verified performance results yet. An earlier version of this README showed an "aggressive strategy backtest" (+38.47% in 60 days); that figure cannot be reproduced from anything in this repo, and every backtest script here uses synthetic data, so it was removed. `BACKTEST_RESULTS.md` and `ULTRA_AGGRESSIVE_BACKTEST.md` are likewise synthetic-data simulations.

## ⚠️ Disclaimers

- **High Risk**: This bot uses aggressive strategies with significant risk
- **No Guarantees**: Past performance doesn't guarantee future results
- **Test First**: Always test thoroughly in paper mode
- **Monitor Closely**: Never leave the bot unattended in live mode
- **Capital Risk**: Only trade with money you can afford to lose

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- Documentation: [Wiki](wiki-url)
- Issues: [GitHub Issues](issues-url)
- Telegram: [Support Group](telegram-url)
- Email: support@example.com

---

**⚡ Ready to start aggressive trading on Bybit? Follow the Quick Start guide!**

## ⚠️ Disclaimer

This software is provided **for educational and research purposes only** and is **not** financial advice. Perpetual futures trading is extremely high risk — aggressive strategies targeting outsized daily returns can produce outsized losses, including total loss of capital and negative balances under leverage. Past backtest or validation results do **not** guarantee future results. The author assumes no liability for losses. Use testnet for exploration and only operate on mainnet with capital you can afford to lose.
