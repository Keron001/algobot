# Configuration

This page explains how to configure Algobot for your trading needs.

## Main Configuration Files
- `config.py`: Core settings (MT5 credentials, symbols, timeframes, lot size, etc.)
- `trading_config.json`: Trading hours, risk settings, and other user preferences.

## Example: config.py
```python
MT5_LOGIN = "your_login_number"
MT5_PASSWORD = "your_password"
MT5_SERVER = "your_broker_server"
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY"]
TIMEFRAMES = ["M5", "M15", "H1"]
LOT_SIZE = 0.1
```

## Example: trading_config.json
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

## Environment Variables
Set these in your Render.com dashboard for security:
- `MT5_LOGIN`
- `MT5_PASSWORD`
- `MT5_SERVER`

## Tips
- Never commit real credentials to GitHub.
- Use environment variables for secrets. 