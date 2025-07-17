import time
import pytz
import sys
import traceback
from datetime import datetime, timedelta
import MetaTrader5 as mt5
import pandas as pd
import os
os.environ['LOG_FORMAT'] = 'json'  # Enable structured JSON logging for this script

# Import configuration
from config import (
    SYMBOLS, TIMEFRAMES, DEFAULT_LOT_SIZE, MAGIC_NUMBER,
    TRADING_HOURS, AUTO_TRADE, VERBOSE,
    RISK_PERCENT, STOP_LOSS_PIPS, TAKE_PROFIT_PIPS
)

# Import the enhanced trader
from enhanced_trader import EnhancedTrader

# Import from the data package
from data import login_mt5, logout_mt5

# Import from the utils package
from utils.logger import get_logger

logger = get_logger("Main")

print("[DEBUG] main.py is running...")

def is_trading_hours():
    """Check if current time is within trading hours"""
    try:
        tz = pytz.timezone(TRADING_HOURS['timezone'])
        now = datetime.now(tz)
        
        # No trading on weekends
        if now.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            if VERBOSE:
                logger.info("📅 Weekend - No trading")
            return False
        
        # Parse trading hours
        start_time = datetime.strptime(TRADING_HOURS['start'], '%H:%M').time()
        end_time = datetime.strptime(TRADING_HOURS['end'], '%H:%M').time()
        current_time = now.time()
        
        # Check if current time is within trading hours
        in_session = start_time <= current_time <= end_time
        if VERBOSE and not in_session:
            logger.info(f"⏰ Outside trading hours: {start_time} - {end_time} {TRADING_HOURS['timezone']}")
            
        return in_session
        
    except Exception as e:
        logger.error(f"Error checking trading hours: {str(e)}")
        return False

def check_symbol_trading_conditions(symbol):
    """Check if a symbol is available for trading"""
    try:
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)  # type: ignore
        if symbol_info is None:
            return False, f"Symbol {symbol} not found"
        
        # Check if trading is allowed
        if not symbol_info.visible or not symbol_info.trade_mode == 0:  # 0 = SYMBOL_TRADE_MODE_DISABLED
            return False, f"Symbol {symbol} is not available for trading"
            
        # Try to get tick data
        tick = mt5.symbol_info_tick(symbol)  # type: ignore
        if tick is None:
            return False, f"No price data available for {symbol}"
            
        # Check if bid/ask prices are valid
        if tick.bid <= 0 or tick.ask <= 0:
            return False, f"Invalid prices for {symbol} (Bid: {tick.bid}, Ask: {tick.ask})"
            
        return True, f"{symbol} is ready for trading"
        
    except Exception as e:
        return False, f"Error checking {symbol}: {str(e)}"

def ensure_symbol_selected(symbol, max_retries=5, retry_delay=2):
    """
    Enhanced function to ensure a symbol is selected and ready for trading.
    
    Features:
    - Multiple retry attempts with configurable delays
    - Automatic symbol discovery with fuzzy matching
    - Detailed error reporting
    - Symbol validation and health checks
    - Memory management for MT5 terminal
    
    Args:
        symbol (str): The trading symbol to select (e.g., 'XAUUSD')
        max_retries (int): Maximum number of selection attempts
        retry_delay (int): Delay between retry attempts in seconds
        
    Returns:
        tuple: (success: bool, symbol_name: str or error_message: str)
    """
    def log_step(message, level='info'):
        """Helper for consistent logging"""
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(f"[Symbol Select] {message}")
    
    original_symbol = symbol
    
    for attempt in range(1, max_retries + 1):
        try:
            log_step(f"Attempt {attempt}/{max_retries} for symbol: {original_symbol}")
            
            # 1. Try to get symbol info directly
            symbol_info = mt5.symbol_info(symbol)  # type: ignore
            
            # 2. If symbol not found, try to find similar symbols
            if symbol_info is None:
                log_step(f"Symbol '{symbol}' not found directly, searching alternatives...")
                
                # Get all available symbols
                all_symbols = mt5.symbols_get()  # type: ignore
                if all_symbols is None:
                    error = mt5.last_error()  # type: ignore
                    log_step(f"Failed to get symbol list: {error}", 'error')
                    time.sleep(retry_delay)
                    continue
                
                # Find matching symbols (case insensitive, partial match in name or description)
                symbol_upper = symbol.upper()
                matching_symbols = []
                
                # First pass: exact match in name
                exact_matches = [s for s in all_symbols if s.name.upper() == symbol_upper]
                if exact_matches:
                    matching_symbols = exact_matches
                else:
                    # Second pass: partial match in name or description
                    matching_symbols = [
                        s for s in all_symbols 
                        if (symbol_upper in s.name.upper() or 
                            (hasattr(s, 'description') and symbol_upper in s.description.upper()))
                    ]
                
                # Third pass: try common variations for Gold
                if not matching_symbols and 'XAU' in symbol_upper:
                    gold_variations = ['XAU', 'GOLD', 'XAUEUR', 'XAUUSD', 'XAUUSDm', 'XAUUSD.']
                    matching_symbols = [s for s in all_symbols 
                                      if any(v in s.name.upper() for v in gold_variations)]
                
                if not matching_symbols:
                    log_step(f"No matching symbols found for '{symbol}'", 'error')
                    time.sleep(retry_delay)
                    continue
                
                # Sort by relevance (exact match first, then by name length)
                matching_symbols.sort(key=lambda x: (
                    x.name.upper() != symbol_upper,  # Exact match first
                    len(x.name)  # Shorter names first
                ))
                
                # Try each matching symbol (limit to top 3 to avoid memory issues)
                for sym in matching_symbols[:3]:
                    log_step(f"Trying alternative: {sym.name} ({getattr(sym, 'description', 'No description')})")
                    if mt5.symbol_select(sym.name, True):  # type: ignore
                        symbol = sym.name
                        symbol_info = mt5.symbol_info(symbol)  # type: ignore
                        log_step(f"Successfully selected alternative: {symbol}")
                        break
                else:
                    log_step(f"Could not select any matching symbol for {symbol}", 'error')
                    time.sleep(retry_delay)
                    continue
            
            # 3. Ensure symbol is visible in Market Watch
            if not getattr(symbol_info, 'visible', False):
                log_step(f"Adding {symbol} to Market Watch...")
                if not mt5.symbol_select(symbol, True):  # type: ignore
                    error = mt5.last_error()  # type: ignore
                    log_step(f"Failed to add {symbol} to Market Watch: {error}", 'warning')
                    time.sleep(retry_delay)
                    continue
                symbol_info = mt5.symbol_info(symbol)  # type: ignore  # Refresh info
            
            # 4. Verify we can get price data
            tick = mt5.symbol_info_tick(symbol)  # type: ignore
            if tick is None:
                log_step(f"No price data available for {symbol}", 'warning')
                time.sleep(retry_delay)
                continue
                
            # 5. Check trading conditions
            is_ok, status = check_symbol_trading_conditions(symbol)
            if not is_ok:
                log_step(f"Trading conditions not met: {status}", 'warning')
                time.sleep(retry_delay)
                continue
            
            # 6. Final validation
            if not all([tick.bid > 0, tick.ask > 0]):
                log_step(f"Invalid prices for {symbol} (Bid: {tick.bid}, Ask: {tick.ask})", 'warning')
                time.sleep(retry_delay)
                continue
            
            # Success!
            log_step(f"✅ Successfully verified {symbol} for trading")
            log_step(f"   Description: {getattr(symbol_info, 'description', 'N/A')}")
            log_step(f"   Bid: {tick.bid}")
            log_step(f"   Ask: {tick.ask}")
            log_step(f"   Spread: {(tick.ask - tick.bid):.5f} points")
            log_step(f"   Time: {tick.time}")
            
            return True, symbol
            
        except Exception as e:
            log_step(f"Unexpected error: {str(e)}\n{traceback.format_exc()}", 'error')
            time.sleep(retry_delay)
    
    return False, f"Failed to select symbol '{original_symbol}' after {max_retries} attempts"

def calculate_sleep_interval(timeframe):
    """Calculate sleep interval based on timeframe"""
    if timeframe == 'M1':
        return 60  # 1 minute
    elif timeframe == 'M5':
        return 300  # 5 minutes
    elif timeframe == 'M15':
        return 900  # 15 minutes
    elif timeframe == 'H1':
        return 3600  # 1 hour
    else:
        return 60  # Default to 1 minute

if __name__ == "__main__":
    # Initialize MT5 connection
    try:
        if not login_mt5():
            logger.error("❌ Failed to connect to MetaTrader 5")
            sys.exit(1)
        
        # Display startup banner
        logger.info("\n" + "="*70)
        logger.info(f"🚀 Starting AlgoBot | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*70)
        logger.info(f"📊 Trading: {SYMBOLS[0]} on {TIMEFRAMES[0]} timeframe")
        logger.info(f"💰 Risk: {RISK_PERCENT}% per trade | SL: {STOP_LOSS_PIPS} pips | TP: {TAKE_PROFIT_PIPS} pips")
        logger.info(f"⚡ Auto Trading: {'ENABLED' if AUTO_TRADE else 'DISABLED'}")
        logger.info("="*70 + "\n")
        
        # Initialize EnhancedTrader
        trader = EnhancedTrader()
        trader.start_trading_session()
        
        # Main trading loop
        while True:
            try:
                for symbol in SYMBOLS:
                    trader.process_symbol(symbol)
                # Sleep to align with next candle (H1 = 1 hour)
                now = datetime.now()
                sleep_time = 3600 - (now.minute * 60 + now.second)
                if sleep_time > 0:
                    if VERBOSE:
                        next_run = (now + timedelta(seconds=sleep_time)).strftime('%H:%M:%S')
                        logger.info(f"⏳ Next update at {next_run}")
                    time.sleep(sleep_time)
            except KeyboardInterrupt:
                logger.info("\n🛑 Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Unexpected error: {str(e)}", exc_info=True)
                logger.info("🔄 Retrying in 60 seconds...")
                time.sleep(60)
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}", exc_info=True)
    finally:
        try:
            trader.stop_trading_session()
        except Exception:
            pass
        try:
            mt5.shutdown()  # type: ignore
            logger.info("Successfully logged out from MT5")
            logger.info("🔌 Disconnected from MT5")
        except Exception as e:
            logger.error(f"❌ Error disconnecting from MT5: {str(e)}")
        logger.info("👋 AlgoBot has been stopped")
        sys.exit(0)