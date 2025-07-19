# Strategy Development

Learn how to develop and customize trading strategies in Algobot.

## Built-in Strategies
- **Moving Average Crossover**: Uses short and long moving averages to generate buy/sell signals.
- **ATR-based Stop Loss/Take Profit**: Uses Average True Range for dynamic risk management.

## Creating a Custom Strategy
1. Create a new Python file in the `strategy/` directory.
2. Inherit from `BaseStrategy`.
3. Implement the `generate_signals()` method.

### Example
```python
from strategy.base import BaseStrategy

class MyStrategy(BaseStrategy):
    def generate_signals(self):
        # Your custom logic here
        pass
```

## Advanced Filters
- RSI, MACD, ATR, trend and volatility filters are available.
- Combine multiple indicators for robust signals.

## Testing Your Strategy
- Use the backtester (`backtest/backtester.py`) to evaluate performance.
- Run `python test_enhanced_bot.py` for integration tests. 