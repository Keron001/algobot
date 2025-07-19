![CI](https://github.com/Keron001/algobot/actions/workflows/python-app.yml/badge.svg)

# Algobot

A robust, user-specific, and production-ready trading bot for MetaTrader 5.

## Features

- Moving average crossover strategy with advanced filters (RSI, MACD, ATR, etc.)
- ATR-based stop loss and take profit
- Trailing stop logic
- Detailed trade logging and analytics
- Backtesting and parameter optimization
- Risk management and advanced reporting

## Installation

```sh
git clone https://github.com/YOUR_USERNAME/algobot.git
cd algobot
python -m venv .venv
.venv\Scripts\activate  # On Windows
pip install -r requirements.txt
```

## Usage

```sh
python enhanced_trader.py
```

## Configuration

Edit `trading_config.json` and `config.py` to set your trading parameters and credentials.

## Environment Variables

Set these as environment variables or in your Render dashboard:
- `MT5_LOGIN`
- `MT5_PASSWORD`
- `MT5_SERVER`
- (Add any others your bot requires)

## Testing

```sh
python test_enhanced_bot.py
```

## Deployment (Render.com)

1. Create a free account at [Render](https://render.com/).
2. Click "New Web Service" → "Connect your GitHub repo".
3. Set build command:
   ```sh
   pip install -r requirements.txt
   ```
4. Set start command:
   ```sh
   python enhanced_trader.py
   ```
5. Add environment variables (MT5 credentials, etc.) in the Render dashboard.
6. Deploy!

## License

MIT

## Contact

[Your Name] - [your.email@example.com] 