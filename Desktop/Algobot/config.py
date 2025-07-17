import pandas as pd

# Trading symbols and timeframes
SYMBOLS = ["XAUUSD"]  # Default trading pair: XAUUSD only
TIMEFRAMES = ["H1"]   # Only 1-hour timeframe
DEFAULT_LOT_SIZE = 0.02  # Updated lot size for XAUUSD

# MT5 Connection Management
MT5_CONNECTION_ACTIVE = False  # Global flag to prevent multiple connections
MT5_CONNECTION_LOCK = False  # Lock to prevent concurrent connection attempts

# Symbol Selection
SYMBOL_PRIORITY = ["XAUUSD", "XAUEUR"]  # XAUUSD first as it has the tightest spread

# Position Management
MAX_OPEN_POSITIONS = 5  # Maximum number of simultaneous positions (based on account balance)
MAX_HOLDING_HOURS = 24  # Maximum hours to hold a position

# Risk Management
RISK_PERCENT = 0.2  # Reduced to 0.2% of account per trade for safer position sizing
STOP_LOSS_PERCENT = 0.30  # 30% stop loss as requested
TAKE_PROFIT_PERCENT = 0.60  # 60% take profit (2:1 risk-reward ratio)
STOP_LOSS_PIPS = 20  # 20 pips stop loss (fallback)
TAKE_PROFIT_PIPS = 40  # 40 pips take profit (fallback)
MAX_POSITION_SIZE = 1.0  # Maximum lot size per position
MIN_POSITION_SIZE = 0.001  # Minimum lot size per position

# Volatility Settings
ATR_PERIOD = 14  # Period for Average True Range calculation
ATR_MULTIPLIER = 2.0  # Multiplier for ATR-based position sizing
MAX_RISK_PERCENT = 1.0  # Maximum risk per trade
MIN_RISK_PERCENT = 0.1  # Minimum risk per trade

# RSI Settings
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
TRAILING_STOP_ACTIVATION = 10  # Pips in profit to activate trailing stop
TRAILING_STOP_DISTANCE = 10  # Pips to maintain from price peak

# Volatility Settings
ATR_PERIOD = 14  # Period for Average True Range calculation
VOLATILITY_MULTIPLIER = 1.5  # Adjust position size based on volatility

# News Filter Settings
AVOID_NEWS = True  # Enable/disable news filter
MINUTES_BEFORE_NEWS = 30  # Minutes before news to avoid trading
MINUTES_AFTER_NEWS = 60  # Minutes after news to avoid trading

# MT5 Login Credentials
MT5_LOGIN = 10006848101
MT5_PASSWORD = "J!DfEl7l"
MT5_SERVER = "MetaQuotes-Demo"
MT5_TIMEOUT = 60000  # Connection timeout in milliseconds
MT5_RETRY_ATTEMPTS = 3  # Number of connection retry attempts
MT5_RETRY_DELAY = 2  # Delay between retry attempts in seconds

# Trading Settings
MAGIC_NUMBER = 123456  # Unique identifier for your bot's orders
AUTO_TRADE = True  # Enable/disable automatic trade execution
VERBOSE = True  # Enable detailed logging

# Additional Trades Configuration
ADDITIONAL_TRADES = 4  # Number of additional trades to execute
ADDITIONAL_TRADE_LOT_SIZE = 0.02  # Fixed lot size for additional trades
ADDITIONAL_TRADE_SPACING = 0.5  # Price spacing between additional trades (in pips)

# Order Filling Type Configuration
# Options: 'IOC' (Immediate-Or-Cancel), 'RETURN' (Return)
ORDER_FILLING_TYPE = 'IOC'  # Change to 'RETURN' if your broker requires it


# Trading Hours (UTC)
TRADING_HOURS = {
    'start': '00:00',  # 24-hour format - 24-hour trading for XAUUSD
    'end': '23:59',    # 24-hour format - 24-hour trading for XAUUSD
    'timezone': 'UTC'  # All times are in UTC
}
DEVIATION = 20  # Maximum price deviation for order execution 

# Enhanced Trader Defaults
MAX_DAILY_LOSS = 0.05  # Maximum daily loss as a fraction of account balance
MAX_POSITIONS = 10     # Maximum open positions
PAPER_TRADING = False  # Live trading mode enabled

# Paper trading simulation parameters
PAPER_INITIAL_BALANCE = 10000.0  # Starting balance for paper trading
PAPER_SLIPPAGE = 0.0  # Slippage in price units (e.g., 0.1 = 10 cents)
PAPER_COMMISSION = 0.0  # Commission per trade (in account currency)

# Default strategy parameters
DEFAULT_STRATEGY_PARAMS = {
    'short_window': 10,
    'long_window': 30,
    'lot_size': DEFAULT_LOT_SIZE,
    'use_macd': False,
    'use_atr_band': False,
    'trend_filter': False,
    'volatility_filter': False,
    'overtrading_limit': 10,  # Allow up to 10 trades per session
    'cooldown_period':  pd.Timedelta(minutes=1)  # Only 1 minute cooldown between trades
} 

# Strategy selection per symbol (plug-in system)
STRATEGY_SELECTION = {
    "XAUUSD": "MovingAverageStrategy",  # Use MovingAverageStrategy for robust param compatibility
    # Add more: "SYMBOL": "StrategyClassName"
} 

# --- SL/TP Calculation Mode ---
# Options: 'fixed' (use FIXED_STOP_LOSS_PIPS/TAKE_PROFIT_PIPS), 'atr' (use ATR multipliers)
SLTP_MODE = 'atr'  # Options: 'fixed', 'atr'
FIXED_STOP_LOSS_PIPS = 20  # 20 pips SL
FIXED_TAKE_PROFIT_PIPS = 40  # 40 pips TP
ATR_STOP_LOSS_MULTIPLIER = 2.0  # SL = 2x ATR
ATR_TAKE_PROFIT_MULTIPLIER = 4.0  # TP = 4x ATR 