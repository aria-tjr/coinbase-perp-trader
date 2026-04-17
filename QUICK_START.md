# 🚀 Bybit Trading Bot - Quick Start Guide

Get your Bybit perpetual futures trading bot up and running in under 10 minutes!

## ⚡ Prerequisites

- Python 3.11+
- Bybit account with API access
- $100+ in USDT (for live trading)

## 🔧 Setup Steps

### 1. Get Bybit API Credentials

1. Log into [Bybit](https://www.bybit.com)
2. Go to **API Management** → **Create New Key**
3. Enable **Contract Trading** permissions
4. **Important**: For testing, enable **Unified Trading (Testnet)**
5. Save your API Key and Secret

### 2. Install & Configure

```bash
# Clone and setup
git clone <repository-url>
cd coinbase-perp-trader
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

### 3. Edit Configuration

Open `.env` and update:

```bash
# Bybit API (REQUIRED)
BYBIT_API_KEY=your_actual_api_key_here
BYBIT_API_SECRET=your_actual_secret_here

# Basic Settings
EXCHANGE_ID=bybit
DEFAULT_SYMBOL=BTCUSDT
TRADING_MODE=paper  # Start with paper trading!

# Risk Management
BASE_LEVERAGE=5
MAX_LEVERAGE=25
DAILY_DRAWDOWN_LIMIT=0.05
```

### 4. Test Connection

```bash
# Validate your setup
python validate_system.py

# Should see: ✅ Bybit connection successful
```

### 5. Start Paper Trading

```bash
# Safe mode - no real money!
python main.py --symbol BTCUSDT --mode paper
```

You should see:
```
╔═══════════════════════════════════════════════════════════════╗
║             Bybit Perpetual Trading Bot                       ║
║                                                               ║
║  ⚡ Aggressive High-Frequency Trading System                  ║
║  🎯 Target: ≥2% Daily Returns                                 ║
║  📊 Symbol: BTCUSDT                                          ║
║  💼 Mode: paper                                              ║
╚═══════════════════════════════════════════════════════════════╝

✅ Bybit exchange connection successful
✅ All components initialized successfully
🚀 Trading bot started - monitoring BTCUSDT
```

## 🎯 Trading Symbols

Popular Bybit perpetual futures:

```bash
# Major cryptocurrencies
python main.py --symbol BTCUSDT --mode paper    # Bitcoin
python main.py --symbol ETHUSDT --mode paper    # Ethereum
python main.py --symbol SOLUSDT --mode paper    # Solana
python main.py --symbol ADAUSDT --mode paper    # Cardano

# High volatility (higher risk/reward)
python main.py --symbol DOGEUSDT --mode paper   # Dogecoin
python main.py --symbol SHIBUSDT --mode paper   # Shiba Inu
```

## 📊 Monitor Performance

### Real-time Dashboard
Open http://localhost:8000 to see:
- Live P&L tracking
- Open positions
- Trade history
- Risk metrics

### Telegram Alerts (Optional)
1. Create a Telegram bot via @BotFather
2. Get your chat ID from @userinfobot
3. Add to `.env`:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## ⚠️ Going Live

**ONLY after successful paper trading!**

```bash
# Double-check your API permissions
# Ensure you have sufficient USDT balance
# Start with small amounts

python main.py --symbol BTCUSDT --mode live
```

**You'll be prompted to type 'YES' to confirm live trading.**

## 🛑 Emergency Stop

To stop the bot safely:
- Press `Ctrl+C` in terminal
- Bot will close all positions and exit cleanly

## 📈 Quick Performance Check

After running for 1 hour, check:
- Total P&L should be positive
- No risk level alerts
- Order success rate > 90%
- Average latency < 100ms

## 🔍 Troubleshooting

### Common Issues

**"Connection failed"**
```bash
# Check API credentials
echo $BYBIT_API_KEY  # Should show your key
python -c "import ccxt; print(ccxt.bybit().describe())"
```

**"Symbol not found"**
```bash
# List available symbols
python -c "
import ccxt
exchange = ccxt.bybit()
markets = exchange.load_markets()
futures = [k for k in markets.keys() if 'USDT' in k and markets[k]['swap']]
print('Available symbols:', futures[:10])
"
```

**"Insufficient balance"**
- Ensure you have USDT in your Bybit Unified Trading Account
- For testnet: Get test USDT from Bybit testnet faucet

## 🚨 Important Warnings

1. **Start with paper trading** - Test all strategies first
2. **Use small amounts** - Start with $100-500 for live trading
3. **Monitor closely** - Never leave the bot unattended initially
4. **Understand risks** - Futures trading involves significant risk
5. **Test thoroughly** - Run paper trading for at least 24 hours

## 📞 Need Help?

- Check the [full README](README.md) for detailed docs
- Review [backtest results](BACKTEST_RESULTS.md) for performance examples
- Join our Telegram support group
- Create a GitHub issue for bugs

---

**🎯 Ready to trade? Start with paper mode and work your way up!**

Remember: The goal is ≥2% daily returns, but risk management comes first! 🛡️
