"""
Enhanced MT5 Data Fetcher with Robust Connection Handling

This module provides functions to interact with MetaTrader 5 terminal,
including connection management, data fetching, and account operations.
"""
import os
import time
import psutil
import platform
import subprocess
from typing import Optional, Dict, Any, List, Union, Tuple
from datetime import datetime, timedelta

import MetaTrader5 as mt5
import pandas as pd

from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_TIMEOUT, MT5_RETRY_ATTEMPTS, MT5_RETRY_DELAY, MT5_CONNECTION_ACTIVE, MT5_CONNECTION_LOCK
from utils.logger import get_logger

logger = get_logger("MT5DataFetcher")

# Default MT5 paths for different platforms
DEFAULT_MT5_PATHS = {
    'Windows': [
        r"C:\Program Files\MetaTrader 5\terminal64.exe",
        r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe"
    ],
    'Linux': [
        "/home/$(whoami)/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"
    ]
}

class MT5ConnectionError(Exception):
    """Custom exception for MT5 connection errors"""
    pass

def is_mt5_running() -> bool:
    """Check if MT5 terminal process is running"""
    try:
        for proc in psutil.process_iter(['name']):
            if 'terminal' in proc.info['name'].lower() or 'metatrader' in proc.info['name'].lower():
                return True
        return False
    except Exception as e:
        logger.warning(f"Error checking MT5 process: {e}")
        return False

def start_mt5_terminal() -> bool:
    """Attempt to start MT5 terminal"""
    system = platform.system()
    for path in DEFAULT_MT5_PATHS.get(system, []):
        try:
            if not os.path.exists(path):
                continue
                
            logger.info(f"Starting MT5 terminal: {path}")
            subprocess.Popen([path], shell=True)
            time.sleep(10)  # Give MT5 time to start
            return True
        except Exception as e:
            logger.warning(f"Failed to start MT5 at {path}: {e}")
            continue
    
    logger.error("Could not start MT5 terminal. Please start it manually.")
    return False

def ensure_mt5_connection(login=None, password=None, server=None, timeout=None) -> bool:
    """Ensure MT5 is properly connected with user-specific credentials if provided."""
    global MT5_CONNECTION_ACTIVE, MT5_CONNECTION_LOCK
    # Check if already connected
    if MT5_CONNECTION_ACTIVE:
        try:
            account_info = mt5.account_info()
            if account_info is not None:
                return True
            else:
                logger.warning("MT5 connection lost, reconnecting...")
                MT5_CONNECTION_ACTIVE = False
        except Exception:
            logger.warning("MT5 connection lost, reconnecting...")
            MT5_CONNECTION_ACTIVE = False
    if MT5_CONNECTION_LOCK:
        logger.warning("MT5 connection attempt already in progress, waiting...")
        return False
    MT5_CONNECTION_LOCK = True
    try:
        try:
            mt5.shutdown()
        except Exception:
            pass
        if not mt5.initialize():
            error = mt5.last_error()
            logger.error(f"Failed to initialize MT5: {error}")
            return False
        # Use user-specific credentials if provided
        login_val = login if login is not None else MT5_LOGIN
        password_val = password if password is not None else MT5_PASSWORD
        server_val = server if server is not None else MT5_SERVER
        timeout_val = timeout if timeout is not None else MT5_TIMEOUT
        authorized = mt5.login(
            login=login_val,
            password=password_val,
            server=server_val,
            timeout=timeout_val
        )
        if not authorized:
            error = mt5.last_error()
            logger.error(f"Failed to login to MT5: {error}")
            mt5.shutdown()
            return False
        account_info = mt5.account_info()
        if account_info is None:
            logger.error("Failed to get account info")
            mt5.shutdown()
            return False
        MT5_CONNECTION_ACTIVE = True
        logger.info(f"Successfully connected to MT5 account {login_val}")
        return True
    except Exception as e:
        logger.error(f"Error ensuring MT5 connection: {str(e)}")
        try:
            mt5.shutdown()
        except Exception:
            pass
        return False
    finally:
        MT5_CONNECTION_LOCK = False

def login_mt5(max_retries: int = None, retry_delay: int = None, login=None, password=None, server=None, timeout=None) -> bool:
    """
    Login to MT5 with credentials from config or user-specific values
    """
    max_retries = max_retries or MT5_RETRY_ATTEMPTS
    retry_delay = retry_delay or MT5_RETRY_DELAY
    for attempt in range(1, max_retries + 1):
        try:
            current_delay = min(retry_delay * (2 ** (attempt - 1)), 60)
            if ensure_mt5_connection(login=login, password=password, server=server, timeout=timeout):
                account_info = mt5.account_info()
                logger.info("\n" + "="*70)
                logger.info("SUCCESSFULLY CONNECTED TO MT5")
                logger.info("-"*70)
                logger.info(f"Account:      {account_info.login}")
                logger.info(f"Server:       {server if server else MT5_SERVER}")
                logger.info(f"Balance:      {account_info.balance:.2f} {account_info.currency}")
                logger.info(f"Equity:       {account_info.equity:.2f} {account_info.currency}")
                logger.info(f"Leverage:     1:{account_info.leverage}")
                logger.info(f"Trading Mode: {'Demo' if account_info.trade_mode == 0 else 'Real'}")
                logger.info(f"Trading Allowed: {'Yes' if account_info.trade_allowed else 'No'}")
                logger.info("="*70 + "\n")
                return True
            logger.warning(f"Connection attempt {attempt}/{max_retries} failed")
            time.sleep(current_delay)
        except Exception as e:
            logger.error(f"Unexpected error during login: {str(e)}", exc_info=True)
            if attempt < max_retries:
                time.sleep(current_delay)
                continue
            logger.error(f"Failed to connect to MT5 after {max_retries} attempts")
            return False
    return False

def list_available_symbols():
    """List all available symbols from the server"""
    if not login_mt5():
        return None
        
    try:
        symbols = mt5.symbols_get()
        if symbols is None:
            logger.error(f"Failed to get symbols: {mt5.last_error()}")
            return None
            
        logger.info("\n" + "="*70)
        logger.info("AVAILABLE SYMBOLS:")
        logger.info("-"*70)
        
        # Group symbols by category
        symbols_by_category = {}
        for symbol in symbols:
            category = symbol.path.split('\\')[-2] if '\\' in symbol.path else 'Other'
            if category not in symbols_by_category:
                symbols_by_category[category] = []
            symbols_by_category[category].append(symbol.name)
        
        # Log symbols by category
        for category, sym_list in symbols_by_category.items():
            logger.info(f"\n{category.upper()}:")
            logger.info("-" * (len(category) + 1))
            for i in range(0, len(sym_list), 5):
                logger.info("  " + "  ".join(sym_list[i:i+5]))
                
        return symbols
        
    except Exception as e:
        logger.error(f"Error listing symbols: {str(e)}")
        return None
    finally:
        mt5.shutdown()

def check_connection() -> bool:
    """
    Check if we have a valid connection to MT5
    
    Returns:
        bool: True if connected, False otherwise
    """
    try:
        # Try a simple operation to verify connection
        return mt5.terminal_info() is not None and mt5.terminal_info().connected
    except Exception as e:
        logger.warning(f"Connection check failed: {str(e)}")
        return False

def fetch_mt5_data(symbol: str, timeframe: str, n_bars: int = 1000, login=None, password=None, server=None, timeout=None) -> Optional[pd.DataFrame]:
    """
    Fetch historical data from MT5 with enhanced error handling
    
    Args:
        symbol: Symbol to fetch data for (e.g., 'EURUSD')
        timeframe: Timeframe string (e.g., 'H1', 'D1')
        n_bars: Number of bars to fetch (max 5000)
        
    Returns:
        DataFrame with OHLCV data or None if failed
    """
    # Map timeframe string to MT5 timeframe constant
    tf_map = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1,
    }
    
    if timeframe not in tf_map:
        logger.error(f"Invalid timeframe: {timeframe}. Must be one of: {', '.join(tf_map.keys())}")
        return None
    
    mt5_tf = tf_map[timeframe]
    
    if not login_mt5(login=login, password=password, server=server, timeout=timeout):
        return None
    
    try:
        # Ensure symbol is selected in Market Watch
        if not mt5.symbol_select(symbol, True):
            error = mt5.last_error()
            logger.error(f"Failed to select {symbol}: {error}")
            return None
        
        logger.info(f"Fetching {n_bars} {timeframe} bars for {symbol}...")
        
        # Fetch the data with error handling
        rates = None
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, n_bars)
        except Exception as e:
            logger.error(f"Error fetching rates: {str(e)}")
            # Try to reconnect and fetch again
            if login_mt5(login=login, password=password, server=server, timeout=timeout):
                rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, n_bars)
        
        if rates is None or len(rates) == 0:
            error = mt5.last_error()
            logger.error(f"No data received for {symbol} on {timeframe}: {error}")
            return None
        
        # Process the data
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Rename columns for consistency
        df.rename(columns={
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'tick_volume': 'volume',
            'real_volume': 'real_volume',
            'spread': 'spread',
        }, inplace=True)
        
        # Set time as index
        df.set_index('time', inplace=True)
        
        # Log success
        logger.info(f"✅ Successfully fetched {len(df)} {timeframe} bars for {symbol} "
                   f"(from {df.index[0]} to {df.index[-1]})")
        
        return df
        
    except Exception as e:
        logger.error(f"Error in fetch_mt5_data: {str(e)}", exc_info=True)
        return None
    finally:
        mt5.shutdown()

def get_account_info(login=None, password=None, server=None, timeout=None) -> Optional[Dict[str, Any]]:
    """
    Get MT5 account information with error handling
    
    Returns:
        Dictionary with account info or None if failed
    """
    if not login_mt5(login=login, password=password, server=server, timeout=timeout):
        return None
    
    try:
        account_info = mt5.account_info()
        if account_info is None:
            error = mt5.last_error()
            logger.error(f"Failed to get account info: {error}")
            return None
            
        # Format account information
        account_data = {
            'login': account_info.login,
            'name': account_info.name,
            'server': account_info.server,
            'balance': account_info.balance,
            'equity': account_info.equity,
            'margin': account_info.margin,
            'free_margin': account_info.margin_free,
            'margin_level': account_info.margin_level,
            'currency': account_info.currency,
            'leverage': account_info.leverage,
            'trade_mode': 'Demo' if account_info.trade_mode == 0 else 'Real',
            'trade_allowed': bool(account_info.trade_allowed),
            'trade_expert': bool(account_info.trade_expert)
        }
        
        logger.info("\n" + "="*70)
        logger.info("ACCOUNT INFORMATION")
        logger.info("-"*70)
        for key, value in account_data.items():
            if isinstance(value, float):
                logger.info(f"  {key.replace('_', ' ').title()}: {value:.2f}")
            else:
                logger.info(f"  {key.replace('_', ' ').title()}: {value}")
        logger.info("="*70 + "\n")
                
        return account_data
        
    except Exception as e:
        logger.error(f"Error getting account info: {str(e)}", exc_info=True)
        return None

def logout_mt5() -> bool:
    """
    Logout and shutdown MT5 connection
    
    Returns:
        bool: True if logout successful, False otherwise
    """
    try:
        mt5.shutdown()
        logger.info("Successfully logged out from MT5")
        return True
    except Exception as e:
        logger.error(f"Error during MT5 logout: {str(e)}", exc_info=True)
        return False

def check_mt5_version() -> bool:
    """
    Check if MT5 terminal version is compatible
    
    Returns:
        bool: True if version is compatible, False otherwise
    """
    try:
        if not check_connection() and not login_mt5():
            return False
            
        version_info = mt5.version()
        if version_info is None:
            logger.error("Failed to get MT5 version")
            return False
            
        # version_info is a tuple: (major, build, build_date)
        major, build, build_date = version_info
        logger.info(f"MT5 Terminal Version: {major}.{build} (Build: {build_date})")
        
        # Check if version is recent enough (example: build 3000 or higher)
        if build < 3000:
            logger.warning("Your MT5 terminal build is quite old. Consider updating to the latest version.")
            
        return True
        
    except Exception as e:
        logger.error(f"Error checking MT5 version: {str(e)}", exc_info=True)
        return False
    finally:
        # Don't shutdown here as it might be called during normal operation
        pass

# Register cleanup function to run on program exit
import atexit
atexit.register(logout_mt5)

# Check MT5 version when module is imported
check_mt5_version() 