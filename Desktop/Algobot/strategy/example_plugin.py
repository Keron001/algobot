from .base import BaseStrategy
import pandas as pd
import numpy as np

class ExamplePluginStrategy(BaseStrategy):
    """
    Example plug-in strategy: Simple mean-reversion.
    Buys when price is below rolling mean by 1 std, sells when above by 1 std.
    """
    def __init__(self, data, window=20, lot_size=0.01):
        super().__init__(data, lot_size)
        self.window = window

    def generate_signals(self):
        df = self.data.copy()
        df['mean'] = df['close'].rolling(window=self.window, min_periods=1).mean()
        df['std'] = df['close'].rolling(window=self.window, min_periods=1).std()
        df['Signal'] = 0
        df['Signal'] = np.where(df['close'] < df['mean'] - df['std'], 1, df['Signal'])
        df['Signal'] = np.where(df['close'] > df['mean'] + df['std'], -1, df['Signal'])
        df['Position'] = df['Signal'].diff().fillna(0)
        return df 