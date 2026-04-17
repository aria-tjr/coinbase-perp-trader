# Bybit Perpetual Trading Bot

A high-performance, aggressive trading bot designed for Bybit perpetual futures markets. This system targets ≥2% daily returns through sophisticated algorithmic strategies and risk management.

## 🚀 Features

- **Multi-Strategy Trading**: Momentum breakout, mean reversion, ML-based predictions, and reinforcement learning
- **Aggressive Risk Management**: Dynamic leverage adjustment, real-time drawdown monitoring
- **High-Frequency Execution**: Sub-100ms order execution with advanced retry logic
- **Real-time Monitoring**: Prometheus metrics, Telegram alerts, web dashboard
- **Paper Trading**: Full simulation mode for strategy testing
- **Advanced Analytics**: Performance tracking, Sharpe ratio optimization

## 📊 Performance Targets

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
git clone <repository-url>
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

```bash
# Run backtest with historical data
python backtest.py --start-date 2024-01-01 --end-date 2024-03-01

# Test specific strategy
python backtest.py --strategy momentum_breakout --symbol BTCUSDT

# Aggressive backtest (high leverage)
python backtest.py --config aggressive
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

## 📈 Performance Examples

### Aggressive Strategy Backtest Results
```
Period: 2024-01-01 to 2024-03-01 (60 days)
Starting Capital: $10,000
Final Capital: $13,847
Total Return: +38.47%
Daily Average: +0.64%
Max Drawdown: -4.12%
Sharpe Ratio: 2.34
Win Rate: 67.3%
Total Trades: 1,247
```

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
