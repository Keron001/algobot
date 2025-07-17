from .base import BaseStrategy
import pandas as pd

class AdvancedStrategy(BaseStrategy):
    def __init__(self, data, lot_size=0.01):
        super().__init__(data, lot_size)

    def run(self):
        print("Running Advanced Strategy (RSI + MA Crossover)")
        df = self.data.copy()
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        # Calculate MA
        df['MA'] = df['close'].rolling(window=50).mean()
        # Example signal: Buy when RSI < 30 and price > MA
        df['Signal'] = ((df['RSI'] < 30) & (df['close'] > df['MA'])).astype(int)
        df['Position'] = df['Signal'].diff()
        print(df[['close', 'RSI', 'MA', 'Signal', 'Position']].tail())
        # Placeholder: Add trade simulation, performance metrics, and optimization 