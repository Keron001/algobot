from .base import BaseStrategy
import pandas as pd
import numpy as np
from config import (
    RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    ATR_PERIOD, ATR_MULTIPLIER,
    MAX_RISK_PERCENT, MIN_RISK_PERCENT
)
from utils.indicators import calculate_rsi, calculate_atr, calculate_macd

class MovingAverageStrategy(BaseStrategy):
    def __init__(self, data, short_window=10, long_window=30, lot_size=0.01,
                 higher_timeframe_data=None, overtrading_limit=4, use_macd=False, 
                 use_atr_band=False, trend_filter=False, volatility_filter=False,
                 cooldown_period=None, **kwargs):
        super().__init__(data, lot_size)
        self.short_window = short_window
        self.long_window = long_window
        self.last_signal = 0
        self.higher_timeframe_data = higher_timeframe_data
        self.overtrading_limit = overtrading_limit
        self.use_macd = use_macd
        self.use_atr_band = use_atr_band
        self.trend_filter = trend_filter
        self.volatility_filter = volatility_filter
        self.signal_count = 0
        self.last_trade_time = None
        # Allow cooldown_period to be set via config, fallback to default
        if cooldown_period is not None:
            self.cooldown_period = cooldown_period
        else:
            self.cooldown_period = pd.Timedelta(minutes=10)  # Default cooldown

    def _trend_filter(self, df):
        """Only allow trades in the direction of the higher timeframe trend."""
        if not self.trend_filter or self.higher_timeframe_data is None:
            return pd.Series([True] * len(df), index=df.index)
        
        ht_df = self.higher_timeframe_data.copy()
        ht_df['HT_Short_MA'] = ht_df['close'].rolling(window=self.short_window, min_periods=1).mean()
        ht_df['HT_Long_MA'] = ht_df['close'].rolling(window=self.long_window, min_periods=1).mean()
        ht_trend = ht_df['HT_Short_MA'] > ht_df['HT_Long_MA']
        # Forward fill to align with lower timeframe
        ht_trend = ht_trend.reindex(df.index, method='ffill').fillna(False)
        return ht_trend

    def _volatility_filter(self, df):
        """Avoid trading during low volatility (ATR below threshold)."""
        if not self.volatility_filter:
            return pd.Series([True] * len(df), index=df.index)
        
        atr = calculate_atr(df, ATR_PERIOD)
        threshold = atr.mean() * 0.7  # Configurable threshold
        return atr > threshold

    def _macd_confirmation(self, df):
        """MACD confirmation for trend direction."""
        if not self.use_macd:
            return pd.Series([True] * len(df), index=df.index)
        
        macd, signal, _ = calculate_macd(df['close'])
        return macd > signal

    def _atr_band_confirmation(self, df):
        """ATR band confirmation for volatility breakouts."""
        if not self.use_atr_band:
            return pd.Series([True] * len(df), index=df.index)
        
        atr = calculate_atr(df, ATR_PERIOD)
        upper_band = df['close'] + atr * ATR_MULTIPLIER
        lower_band = df['close'] - atr * ATR_MULTIPLIER
        return (df['close'] > upper_band) | (df['close'] < lower_band)

    def _rsi_confirmation(self, df):
        """RSI confirmation for overbought/oversold conditions."""
        rsi = calculate_rsi(df['close'], RSI_PERIOD)
        # Buy when RSI < 70 (not overbought), Sell when RSI > 30 (not oversold)
        buy_condition = rsi < RSI_OVERBOUGHT
        sell_condition = rsi > RSI_OVERSOLD
        return buy_condition, sell_condition

    def _can_trade(self):
        """Check overtrading limit and cooldown period."""
        # Overtrading limit
        if self.signal_count >= self.overtrading_limit:
            print(f"[DEBUG] Overtrading limit reached: {self.signal_count} >= {self.overtrading_limit}")
            return False
        
        # Cooldown period
        if self.last_trade_time is not None:
            time_since_last_trade = pd.Timestamp.now() - self.last_trade_time
            if time_since_last_trade < self.cooldown_period:
                print(f"[DEBUG] Cooldown active: {time_since_last_trade} < {self.cooldown_period}")
                return False
        
        self.signal_count += 1
        self.last_trade_time = pd.Timestamp.now()
        return True

    def _calculate_trailing_stop(self, df, position_type):
        """Calculate trailing stop based on ATR."""
        atr = calculate_atr(df, ATR_PERIOD)
        if position_type == 'buy':
            return df['close'] - (atr * 2)  # 2x ATR below price
        else:
            return df['close'] + (atr * 2)  # 2x ATR above price

    def generate_signals(self):
        """Generate trading signals using all enabled filters for high-probability entries."""
        df = self.data.copy()
        
        # Calculate moving averages
        df['Short_MA'] = df['close'].rolling(window=self.short_window, min_periods=1).mean()
        df['Long_MA'] = df['close'].rolling(window=self.long_window, min_periods=1).mean()
        
        # Calculate RSI
        df['RSI'] = calculate_rsi(df['close'], RSI_PERIOD)
        
        # Calculate ATR
        df['ATR'] = calculate_atr(df, ATR_PERIOD)
        
        # Initialize signals
        df['Signal'] = 0
        df['Position'] = 0
        df['Trailing_Stop'] = np.nan

        # Core MA signals
        ma_buy = (df['Short_MA'] > df['Long_MA'])
        ma_sell = (df['Short_MA'] < df['Long_MA'])

        # RSI confirmation
        rsi_buy, rsi_sell = self._rsi_confirmation(df)

        # Trend filter
        trend = self._trend_filter(df)
        # Volatility filter
        volatility = self._volatility_filter(df)
        # MACD confirmation
        macd_conf = self._macd_confirmation(df)
        # ATR band confirmation
        atr_band = self._atr_band_confirmation(df)

        # Combine all filters for buy/sell
        buy_signal = ma_buy & rsi_buy & trend & volatility & macd_conf & atr_band
        sell_signal = ma_sell & rsi_sell & trend & volatility & macd_conf & atr_band

        # Apply signals with overtrading/cooldown check
        if self._can_trade():
            df.loc[buy_signal, 'Signal'] = 1
            df.loc[sell_signal, 'Signal'] = -1

        # Set Position column based on signals
        df['Position'] = 0
        df.loc[buy_signal, 'Position'] = 1
        df.loc[sell_signal, 'Position'] = -1

        # Calculate trailing stops based on ATR
        df.loc[df['Signal'] == 1, 'Trailing_Stop'] = self._calculate_trailing_stop(df[df['Signal'] == 1], 'buy')
        df.loc[df['Signal'] == -1, 'Trailing_Stop'] = self._calculate_trailing_stop(df[df['Signal'] == -1], 'sell')

        # Store the last signal
        if len(df) > 0:
            self.last_signal = df['Signal'].iloc[-1]

        return df

    def get_parameters(self):
        """Return current strategy parameters."""
        return {
            'short_window': self.short_window,
            'long_window': self.long_window,
            'lot_size': self.lot_size,
            'overtrading_limit': self.overtrading_limit,
            'use_macd': self.use_macd,
            'use_atr_band': self.use_atr_band,
            'trend_filter': self.trend_filter,
            'volatility_filter': self.volatility_filter
        } 