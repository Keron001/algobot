# MT5 Automated Trading Setup Guide

This guide will help you set up automated trading with MetaTrader 5 once you have access to the platform.

## Prerequisites

1. **MetaTrader 5 Account**: Live or demo account with a broker
2. **MT5 Credentials**: Login, password, and server details
3. **Python Environment**: Python 3.8+ with required packages
4. **Windows System**: MT5 Python package works best on Windows

## Installation Steps

### 1. Install MetaTrader 5 Python Package

```bash
# On Windows (recommended)
pip install MetaTrader5

# Alternative installation methods
pip install --upgrade MetaTrader5
```

### 2. Verify MT5 Connection

Run the test script to verify your MT5 connection:

```bash
python test_mt5_connection.py
```

### 3. Update Configuration

Edit `config.py` with your MT5 credentials:

```python
# MT5 Connection Settings
MT5_LOGIN = "your_login_number"
MT5_PASSWORD = "your_password"
MT5_SERVER = "your_broker_server"

# Trading Settings
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY"]  # Symbols to trade
TIMEFRAMES = ["M5", "M15", "H1"]          # Timeframes to use
LOT_SIZE = 0.1                            # Default lot size
```

## Automated Trading Setup

### 1. Configure Trading Parameters

Edit `trading_config.json` to set your trading preferences:

```json
{
  "trading_hours": {
    "start": "08:00",
    "end": "20:00",
    "timezone": "UTC"
  },
  "max_daily_loss": 0.05,
  "max_positions": 5,
  "risk_settings": {
    "max_risk_per_trade": 0.02,
    "max_portfolio_risk": 0.06
  }
}
```

### 2. Run Backtesting First

Before live trading, always test your strategy:

```bash
# Run comprehensive backtest
python demo_backtest.py

# Optimize parameters
python example_backtest.py
```

### 3. Start with Paper Trading

Always start with paper trading to verify everything works:

```bash
# Run automated trading in paper mode
python automated_trader.py
```

### 4. Switch to Live Trading

Once you're confident with paper trading:

1. Update `config.py` to set `PAPER_TRADING = False`
2. Verify your risk settings
3. Start the automated trader

```bash
python automated_trader.py
```

## Key Features

### 🕐 Scheduled Trading
- Configure trading hours to match market sessions
- Automatic start/stop based on time
- Timezone support

### 🛡️ Risk Management
- Maximum daily loss limits
- Position size calculation
- Stop loss and take profit management
- Maximum position limits

### 📊 Performance Monitoring
- Real-time P&L tracking
- Win/loss statistics
- Trade history logging
- Daily performance reports

### 🚨 Safety Features
- Emergency stop functionality
- Automatic position closing
- Connection monitoring
- Error handling and recovery

## Monitoring and Control

### Real-time Monitoring

The system provides real-time monitoring through:

1. **Console Logs**: Detailed trading activity
2. **Performance Metrics**: P&L, win rate, trade count
3. **Status Reports**: System health and trading state

### Emergency Controls

```python
# Emergency stop all trading
trader.emergency_stop_trading()

# Check system status
status = trader.get_status()
print(status)
```

### Daily Reports

The system automatically saves daily statistics to:
- `daily_stats_YYYYMMDD.json`
- `trading_config.json` (configuration)

## Troubleshooting

### Common Issues

1. **MT5 Connection Failed**
   - Verify credentials in `config.py`
   - Check internet connection
   - Ensure MT5 terminal is running

2. **No Trading Signals**
   - Check market hours
   - Verify strategy parameters
   - Review market data quality

3. **Performance Issues**
   - Reduce update frequency
   - Check system resources
   - Review logging level

### Debug Mode

Enable debug logging in `utils/logger.py`:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Best Practices

### 1. Start Small
- Begin with small position sizes
- Test thoroughly with paper trading
- Gradually increase exposure

### 2. Monitor Regularly
- Check system status daily
- Review performance weekly
- Monitor for unusual activity

### 3. Risk Management
- Set conservative loss limits
- Diversify across symbols
- Use proper position sizing

### 4. Maintenance
- Keep MT5 terminal updated
- Monitor system resources
- Backup configuration files

## Advanced Configuration

### Custom Strategies

Add your own strategies in `strategy/`:

```python
from strategy.base import BaseStrategy

class MyStrategy(BaseStrategy):
    def generate_signals(self):
        # Your strategy logic here
        pass
```

### Custom Risk Management

Modify risk parameters in `risk/risk_manager.py`:

```python
# Adjust risk settings
max_risk_per_trade = 0.01  # 1% per trade
max_portfolio_risk = 0.05  # 5% total portfolio
```

### Multiple Timeframes

Configure multiple timeframe analysis:

```python
TIMEFRAMES = ["M1", "M5", "M15", "H1", "H4"]
```

## Support and Maintenance

### Regular Tasks

1. **Daily**: Check system status and performance
2. **Weekly**: Review strategy performance
3. **Monthly**: Optimize parameters
4. **Quarterly**: Update strategies and risk settings

### Backup Strategy

Always have a backup plan:
- Manual trading capability
- Alternative strategies
- Emergency contact procedures

## Security Considerations

1. **Secure Credentials**: Never share MT5 credentials
2. **Network Security**: Use secure connections
3. **Access Control**: Limit system access
4. **Monitoring**: Monitor for unauthorized access

## Next Steps

1. **Test thoroughly** with paper trading
2. **Start small** with live trading
3. **Monitor closely** during initial live trading
4. **Optimize** based on performance
5. **Scale up** gradually

---

**⚠️ Important**: Automated trading involves significant risk. Always test thoroughly and start with small amounts. Past performance does not guarantee future results. 