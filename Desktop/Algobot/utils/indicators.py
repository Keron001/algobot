"""Technical indicators for trading strategies"""
import numpy as np
import pandas as pd

def calculate_rsi(series, period=14):
    """
    Calculate the Relative Strength Index (RSI)
    
    Args:
        series: Pandas Series of closing prices
        period: Lookback period for RSI calculation
        
    Returns:
        Pandas Series with RSI values
    """
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_atr(df, period=14):
    """
    Calculate Average True Range (ATR)
    
    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: Lookback period for ATR calculation
        
    Returns:
        Pandas Series with ATR values
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    # Calculate True Range
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()
    
    return atr

def calculate_sma(series, window):
    """Calculate Simple Moving Average"""
    return series.rolling(window=window).mean()

def calculate_ema(series, window):
    """Calculate Exponential Moving Average"""
    return series.ewm(span=window, adjust=False).mean()

def calculate_macd(series, fast=12, slow=26, signal=9):
    """
    Calculate MACD (Moving Average Convergence Divergence)
    
    Returns:
        tuple: (macd_line, signal_line, histogram)
    """
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    
    return macd, signal_line, histogram
