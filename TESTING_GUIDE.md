# 🧪 Trading Bot Testing Toolkit

This directory contains comprehensive testing tools to validate the trading bot's order placement and position management capabilities using **MAINNET** with real but small orders.

## ⚠️ IMPORTANT: MAINNET TESTING

These scripts use **MAINNET** (not testnet) to validate real order placement functionality. Safety features:
- Small test orders (0.001 BTC ≈ $30-60)
- Auto-close positions after 30 seconds
- Automatic settings restoration
- Real-time monitoring

## 🚀 Quick Start

### 1. Validate Mainnet Connection (Recommended First)
```bash
python validate_mainnet.py
```
This will:
- Test your mainnet API connection
- Verify account access and balance
- Check current BTC price
- Validate sufficient funds for testing

### 2. Test Order Placement (Main Test)
```bash
python test_bot.py --quick
```
This will:
- Apply aggressive strategy settings temporarily
- Place a small test order (0.001 BTC) on **MAINNET**
- Monitor the position for 30 seconds
- Close the position automatically
- Restore original settings

### Monitor & Manage Positions
```bash
python test_bot.py --positions
```
Interactive tool to:
- View all open positions
- Close individual positions
- Close all positions at once
- Monitor positions in real-time

### View Configuration Details
```bash
python test_bot.py --config
```
Shows how the aggressive test parameters differ from normal settings.

## 📁 Test Files

### Core Testing Scripts
- **`test_bot.py`** - Main testing interface with multiple modes
- **`test_aggressive_trading.py`** - Aggressive order placement test
- **`position_manager.py`** - Interactive position management tool
- **`aggressive_config.py`** - Aggressive strategy parameter overrides

## 🔧 How It Works

### Aggressive Strategy Parameters

The testing toolkit temporarily applies these aggressive settings to force signal generation:

#### Momentum Breakout Strategy
```python
# Normal → Aggressive
min_adx: 25 → 15        # Easier trend detection
volume_multiplier: 1.5x → 1.1x   # Lower volume requirement
rsi_long: 45 → 30       # More oversold entries
rsi_short: 55 → 70      # More overbought entries
atr_multiplier: 2.0 → 1.0       # Tighter breakouts
```

#### Mean Reversion Strategy
```python
# Normal → Aggressive
z_score_threshold: 2.0 → 0.5    # Easier mean reversion
rsi_oversold: 30 → 40           # Higher oversold threshold
rsi_overbought: 70 → 60         # Lower overbought threshold
max_adx: 30 → 40               # Allow more trending markets
```

#### Risk Management
```python
# Normal → Aggressive (for testing only)
leverage: 5x → 10x              # Higher leverage
position_size: 1% → 10%         # Larger positions
stop_loss: 0.6% → 5%           # Wider stops
take_profit: 0.9% → 8%         # Wider targets
daily_drawdown: 5% → 20%       # Higher risk tolerance
```

## ⚠️ Safety Features

### Automatic Safeguards
- **Testnet Only**: All tests use Bybit sandbox environment
- **Small Positions**: Test orders are limited to 0.001 BTC
- **Auto-Restore**: Original settings are always restored after tests
- **Manual Override**: Press Ctrl+C to stop tests at any time

### Position Limits
- Maximum 1 test position at a time
- 30-second monitoring window
- Automatic position closure
- Comprehensive error handling

## 📊 Test Workflow

1. **Initialize Components**
   - Connect to exchange (testnet)
   - Initialize strategies and risk manager
   - Apply aggressive parameters

2. **Place Test Order**
   - Generate artificial strong signal
   - Calculate position size (0.001 BTC)
   - Execute order through normal trading pipeline
   - Verify order placement success

3. **Monitor Position**
   - Track position P&L for 30 seconds
   - Log position updates every 5 seconds
   - Monitor for any execution issues

4. **Close Position**
   - Execute position closure
   - Verify closure success
   - Calculate final P&L

5. **Restore Settings**
   - Restore all original parameters
   - Reset strategy configurations
   - Log restoration success

## 🎯 Usage Scenarios

### Before Going Live
```bash
# Test order placement capability
python test_bot.py --quick

# If successful, bot is ready for live trading
```

### During Live Trading
```bash
# Monitor positions in real-time
python test_bot.py --positions

# Quick close all positions if needed
# (Use option 3 in the position manager)
```

### Troubleshooting
```bash
# Check configuration details
python test_bot.py --config

# View detailed logs
tail -f logs/trading.log
```

## 📈 Expected Results

### Successful Test Output
```
🎉 TEST COMPLETED SUCCESSFULLY! 🎉
✅ Order placement: SUCCESSFUL
✅ Position monitoring: COMPLETED
✅ Position closure: COMPLETED
✅ Settings restoration: COMPLETED

🚀 The bot is ready for live trading!
💡 You can now use normal settings with confidence.
```

### Test Metrics
- **Order Latency**: < 500ms
- **Position Size**: 0.001 BTC
- **Test Duration**: ~45 seconds total
- **Success Rate**: Should be >95%

## 🔍 Troubleshooting

### Common Issues

**API Connection Failed**
```bash
# Check API credentials in .env file
BYBIT_API_KEY=your_testnet_key
BYBIT_API_SECRET=your_testnet_secret
```

**No Market Data**
- Wait 5-10 seconds for market data to arrive
- Check internet connection
- Verify symbol availability

**Order Placement Failed**
- Check account balance on testnet
- Verify API permissions
- Review position size calculations

**Position Not Found**
- May have closed automatically (stop/target hit)
- Check position manager for open positions
- Review execution engine logs

## 💡 Tips

### Best Practices
1. Run tests during active market hours
2. Keep test positions small
3. Monitor logs for detailed information
4. Use position manager for manual control

### After Successful Testing
1. Verify normal settings are restored
2. Check risk parameters are conservative
3. Monitor first live trades closely
4. Use position manager for oversight

## 🆘 Emergency Commands

### Stop All Activity
```bash
# Ctrl+C in any running script
# Then run position manager to close positions:
python test_bot.py --positions
```

### Manual Position Closure
```bash
python test_bot.py --positions
# Select option 3: "Close all positions"
```

### Reset to Default Settings
```bash
# Settings are automatically restored after tests
# Or restart the main trading bot:
python main.py
```

---

**Remember**: These are testing tools with aggressive parameters. Always verify that normal conservative settings are restored before live trading!
