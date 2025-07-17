"""
Enhanced strategy executor with RSI and volatility-based position sizing

Features:
- Robust symbol selection with multiple fallback options
- Comprehensive error handling with retries
- Detailed logging for debugging
- Resource cleanup on shutdown
- Configuration validation
"""
import time
import logging
import MetaTrader5 as mt5
import pandas as pd
from typing import Optional, Dict, Any, List, Tuple, Union
from datetime import datetime, timedelta
from strategy.moving_average import MovingAverageStrategy
from config import (
    SYMBOLS, TIMEFRAMES, DEFAULT_LOT_SIZE, MAGIC_NUMBER,
    TRADING_HOURS, AUTO_TRADE, VERBOSE, STOP_LOSS_PIPS,
    TAKE_PROFIT_PIPS, RISK_PERCENT, ATR_PERIOD, ATR_MULTIPLIER,
    RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    MT5_LOGIN, MT5_PASSWORD, MT5_SERVER,
    MT5_RETRY_ATTEMPTS, MT5_RETRY_DELAY, SYMBOL_PRIORITY,
    STRATEGY_SELECTION, PAPER_TRADING, DEFAULT_STRATEGY_PARAMS
)
from strategy import get_strategy_registry
from execution.trade_manager import TradeManager
from data import fetch_mt5_data, login_mt5, logout_mt5
from utils.indicators import calculate_rsi, calculate_atr
from utils.logger import get_logger
import os
import numpy as np
os.environ['LOG_FORMAT'] = 'json'  # Enable structured JSON logging for this script

logger = get_logger("StrategyExecutor")

class StrategyExecutor:
    """
    Main strategy executor class with enhanced error handling and symbol selection.
    
    Attributes:
        symbols (List[str]): List of trading symbols
        timeframe (str): Trading timeframe
        strategies (Dict[str, Any]): Dictionary of strategy instances
        trade_manager (Optional[TradeManager]): Trade manager instance
        last_bar_time (Dict[str, datetime]): Last processed bar time for each symbol
        max_retries (int): Maximum number of retries for operations
        retry_delay (int): Delay between retries in seconds
    """
    
    def __init__(self):
        """Initialize the StrategyExecutor with configuration from config.py"""
        self.symbols = SYMBOLS.copy()
        self.timeframes = TIMEFRAMES.copy()  # Use all configured timeframes
        self.strategies: Dict[str, Any] = {}
        self.trade_manager: Optional[TradeManager] = None
        self.last_bar_time: Dict[str, datetime] = {}
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        self.selected_symbols = set()  # Cache for selected symbols
        
    def _validate_symbol(self, symbol: str) -> bool:
        """
        Validate if a symbol is available and can be traded.
        
        Args:
            symbol: Symbol to validate
            
        Returns:
            bool: True if symbol is valid and can be traded, False otherwise
        """
        if not symbol or not isinstance(symbol, str):
            return False
            
        # Try to select the symbol
        if not mt5.symbol_select(symbol, True):  # type: ignore[attr-defined]
            logger.warning(f"Failed to select symbol {symbol}: {mt5.last_error()}")  # type: ignore[attr-defined]
            return False
            
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)  # type: ignore[attr-defined]
        if symbol_info is None:
            logger.warning(f"No info available for symbol {symbol}")
            return False
            
        # Check if symbol is visible and can be traded
        if not symbol_info.visible:
            logger.warning(f"Symbol {symbol} is not visible in Market Watch")
            return False
            
        # Check if we can get tick data
        tick = mt5.symbol_info_tick(symbol)  # type: ignore[attr-defined]
        if tick is None:
            logger.warning(f"No tick data available for symbol {symbol}")
            return False
            
        return True
        
    def get_available_symbol(self) -> Optional[str]:
        """
        Find and return the first available symbol from the priority list.
        
        Returns:
            Optional[str]: The selected symbol name, or None if no symbol is available
        """
        # Try symbols from the priority list first
        for symbol in SYMBOL_PRIORITY:
            if self._validate_symbol(symbol):
                logger.info(f"Selected symbol from priority list: {symbol}")
                return symbol
            logger.warning(f"Symbol {symbol} not available: {mt5.last_error()}")  # type: ignore[attr-defined]
        
        # Try symbols from the config
        for symbol in self.symbols:
            if symbol not in SYMBOL_PRIORITY and self._validate_symbol(symbol):
                logger.warning(f"Using configured symbol: {symbol}")
                return symbol
        
        # As a last resort, try to find any available symbol
        try:
            all_symbols = mt5.symbols_get()  # type: ignore[attr-defined]
            if all_symbols:
                for symbol in all_symbols[:100]:  # Limit to first 100 to avoid timeout
                    if self._validate_symbol(symbol.name):
                        logger.warning(f"Using available symbol: {symbol.name}")
                        return symbol.name
        except Exception as e:
            logger.error(f"Error getting all symbols: {str(e)}")
        
        logger.error("No tradable symbols found. Please check your MT5 terminal and symbol availability.")
        return None

    def initialize(self) -> bool:
        """
        Initialize trading components with retry logic and validation.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        global SYMBOLS
        
        def cleanup():
            """Helper function to clean up resources"""
            try:
                if mt5.terminal_info() is not None:  # type: ignore[attr-defined]
                    mt5.shutdown()  # type: ignore[attr-defined]
                    logger.info("MT5 connection closed during cleanup")
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")
        
        try:
            logger.info("🔧 Initializing AlgoBot components...")
            
            # Use the improved connection management
            logger.info("📡 Establishing MT5 connection...")
            if not login_mt5():
                logger.error("❌ Failed to establish MT5 connection")
                return False
            logger.info("✅ MT5 connection established")
            
            # Get available symbol
            logger.info("🔍 Finding available trading symbol...")
            available_symbol = self.get_available_symbol()
            if not available_symbol:
                logger.error("❌ No tradable symbols available after multiple attempts")
                cleanup()
                return False
            logger.info(f"✅ Found available symbol: {available_symbol}")
            
            # Update SYMBOLS with the available symbol
            SYMBOLS = [available_symbol]
            logger.info(f"📊 Trading with symbol: {available_symbol}")
            
            # Initialize trade manager
            logger.info("💰 Initializing TradeManager...")
            try:
                self.trade_manager = TradeManager(available_symbol, lot_size=DEFAULT_LOT_SIZE, paper_trading=PAPER_TRADING)
                logger.info(f"✅ Successfully initialized TradeManager with lot size: {DEFAULT_LOT_SIZE} (paper_trading={PAPER_TRADING})")
            except Exception as e:
                logger.error(f"❌ Failed to initialize TradeManager: {str(e)}")
                cleanup()
                return False
            
            # Initialize strategies
            logger.info("📈 Initializing trading strategies...")
            try:
                # Don't initialize strategies here - they will be created with actual data in process_symbol
                self.strategies = {}
                logger.info("✅ Successfully initialized trading strategies container")
            except Exception as e:
                logger.error(f"❌ Failed to initialize strategies: {str(e)}")
                cleanup()
                return False
            
            logger.info("🎉 AlgoBot initialization completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Critical error during initialization: {str(e)}", exc_info=True)
            cleanup()
            return False
    
    def calculate_volatility_adjustment(self, df):
        """
        Calculate position size adjustment based on market volatility
        Returns a value between 0.1 and 1.0
        """
        try:
            # Calculate ATR
            atr = calculate_atr(df, ATR_PERIOD)
            # Fix: ensure atr is a pandas Series
            if isinstance(atr, np.ndarray):
                atr = pd.Series(atr, index=df.index)
            if atr is None or len(atr) < 2:
                return 1.0
                
            # Calculate ATR as percentage of price
            current_atr = atr.iloc[-1]
            current_price = df['close'].iloc[-1]
            atr_pct = (current_atr / current_price) * 100
            
            # Calculate volatility adjustment
            # Higher ATR% = lower position size
            adjustment = 1.0 / (1.0 + (atr_pct * ATR_MULTIPLIER))
            
            # Apply bounds
            adjustment = max(0.1, min(1.0, adjustment))
            
            if VERBOSE:
                logger.info(f"Volatility: ATR={current_atr:.5f} ({atr_pct:.2f}% of price) | "
                          f"Adjustment: {adjustment:.2f}")
                
            return adjustment
            
        except Exception as e:
            logger.error(f"Error calculating volatility adjustment: {str(e)}")
            return 1.0
    
    def process_symbol(self, symbol: str) -> None:
        """
        Process trading signals for a single symbol across multiple timeframes.
        
        Args:
            symbol: Symbol to process
        """
        if not symbol or not isinstance(symbol, str):
            logger.error("Invalid symbol provided")
            return
            
        try:
            # Ensure symbol is selected in Market Watch first (only if not already cached)
            if symbol not in self.selected_symbols:
                if not self._ensure_symbol_selected(symbol):
                    logger.error(f"Failed to select symbol {symbol} for trading")
                    return
                
            # Get symbol info with validation (but don't fail if not found)
            symbol_info = mt5.symbol_info(symbol)  # type: ignore[attr-defined]
            if symbol_info is None:
                logger.warning(f"Symbol {symbol} not found in Market Watch, but continuing with cached selection")
                # Don't remove from cache, just continue
                # self.selected_symbols.discard(symbol)
                # return
            
            # Process each timeframe
            for timeframe in self.timeframes:
                logger.info(f"Processing {symbol} on {timeframe} timeframe")
                
                # Fetch historical data with retry
                df = None
                for attempt in range(self.max_retries):
                    try:
                        df = fetch_mt5_data(symbol, timeframe, 300)  # Get 300 bars
                        if df is not None and not df.empty:
                            break
                        logger.warning(f"No data received for {symbol} on {timeframe} (attempt {attempt + 1}/{self.max_retries})")
                    except Exception as e:
                        logger.error(f"Error fetching data for {symbol} on {timeframe}: {str(e)}")
                    
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                
                if df is None or df.empty:
                    logger.error(f"Failed to fetch data for {symbol} on {timeframe} after {self.max_retries} attempts")
                    continue
            
                # Update strategy with latest data
                try:
                    # Determine which strategy to use for this symbol
                    registry = get_strategy_registry()
                    strategy_name = STRATEGY_SELECTION.get(symbol, "MovingAverageStrategy")
                    strategy_cls = registry.get(strategy_name)
                    if not strategy_cls:
                        logger.warning(f"Strategy '{strategy_name}' not found, using MovingAverageStrategy.")
                        from strategy.moving_average import MovingAverageStrategy
                        strategy_cls = MovingAverageStrategy
                    strategy_key = f"{strategy_name}_{timeframe}"
                    params = DEFAULT_STRATEGY_PARAMS.copy()
                    params["data"] = df
                    params["lot_size"] = DEFAULT_LOT_SIZE
                    self.strategies[strategy_key] = strategy_cls(**params)
                    logger.debug(f"Updated strategy data for {symbol} on {timeframe} with {len(df)} bars")
                    # Generate signals
                    signals = self.strategies[strategy_key].generate_signals()
                    if signals is None or signals.empty:
                        logger.warning(f"No signals generated for {symbol} on {timeframe}")
                        continue
                    logger.debug(f"Generated signals for {symbol} on {timeframe}: {signals[['close', 'Signal']].tail().to_string()}")
                except Exception as e:
                    logger.error(f"Error in strategy execution for {symbol} on {timeframe}: {str(e)}", exc_info=VERBOSE)
                    continue
                
                # Get latest signal and price
                latest_signal = signals['Signal'].iloc[-1]
                latest_price = signals['close'].iloc[-1]
                
                # Skip if no signal
                if latest_signal == 0:
                    logger.info(f"No trading signal for {symbol} on {timeframe}")
                    continue
            
                # Calculate volatility adjustment
                try:
                    volatility_adj = self.calculate_volatility_adjustment(df)
                except Exception as e:
                    logger.error(f"Error calculating volatility adjustment: {str(e)}")
                    volatility_adj = 1.0  # Default to no adjustment on error
                
                # Get point value for the symbol
                point = getattr(symbol_info, 'point', 0.00001) or 0.00001
                if point == 0:
                    point = 0.00001
                    logger.warning(f"Using default point value for {symbol}")
                
                # Determine trade parameters
                signal_type = "BUY" if latest_signal > 0 else "SELL"
                stop_loss_pips = STOP_LOSS_PIPS * (1 if signal_type == "BUY" else -1)
                take_profit_pips = TAKE_PROFIT_PIPS * (1 if signal_type == "BUY" else -1)
                
                # Log trade details
                logger.info(f"{signal_type} Signal for {symbol} on {timeframe} at {latest_price:.5f}")
                logger.info(f"Stop Loss: {stop_loss_pips} pips, Take Profit: {take_profit_pips} pips")
                logger.info(f"Volatility Adjustment: {volatility_adj:.2f}")
                
                # Execute trade with retry
                trade_success = False
                if self.trade_manager is None:
                    logger.error("TradeManager is not initialized. Cannot execute trades.")
                    continue
                for attempt in range(self.max_retries):
                    try:
                        success = self.trade_manager.execute_trade(
                            signal=1 if signal_type == "BUY" else -1,
                            stop_loss_pips=stop_loss_pips,
                            take_profit_pips=take_profit_pips,
                            volatility_adjustment=volatility_adj,
                            comment=f"AlgoBot_{signal_type}_{timeframe}",
                            is_additional_trade=False
                        )
                        
                        if success:
                            trade_success = True
                            logger.info(f"Successfully executed {signal_type} order for {symbol} on {timeframe}")
                            break
                        else:
                            logger.warning(f"Trade execution failed (attempt {attempt + 1}/{self.max_retries})")
                    except Exception as e:
                        logger.error(f"Error executing trade (attempt {attempt + 1}): {str(e)}")
                    
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                
                if not trade_success:
                    logger.error(f"Failed to execute {signal_type} order for {symbol} on {timeframe} after {self.max_retries} attempts")
            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {str(e)}")
    
    def _ensure_symbol_selected(self, symbol: str) -> bool:
        """
        Ensure the symbol is selected in Market Watch with retry logic.
        
        Args:
            symbol: Symbol to select
            
        Returns:
            bool: True if symbol is selected, False otherwise
        """
        # Check if symbol is already in cache and verify it's still available
        if symbol in self.selected_symbols:
            try:
                symbol_info = mt5.symbol_info(symbol)  # type: ignore[attr-defined]
                if symbol_info is not None and symbol_info.visible:
                    return True
                else:
                    # Symbol is no longer available, remove from cache
                    self.selected_symbols.discard(symbol)
            except Exception:
                # If we can't check, assume it's still selected
                return True
            
        # Try to select the symbol
        for attempt in range(self.max_retries):
            try:
                # First check if it's already selected
                symbol_info = mt5.symbol_info(symbol)  # type: ignore[attr-defined]
                if symbol_info is not None and symbol_info.visible:
                    logger.debug(f"Symbol {symbol} is already selected in Market Watch")
                    self.selected_symbols.add(symbol)  # Add to cache
                    return True
                
                # Try to select it
                if mt5.symbol_select(symbol, True):  # type: ignore[attr-defined]
                    logger.info(f"Successfully selected {symbol} in Market Watch")
                    self.selected_symbols.add(symbol)  # Add to cache
                    return True
                else:
                    logger.warning(f"Failed to select {symbol} (attempt {attempt + 1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        
            except Exception as e:
                logger.error(f"Error selecting symbol {symbol}: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    
        logger.error(f"Failed to select {symbol} after {self.max_retries} attempts")
        return False
    
    def run(self) -> bool:
        """
        Main execution loop for the trading bot with enhanced error handling.
        
        Returns:
            bool: True if bot ran successfully, False if initialization failed
        """
        # Initialize components
        if not self.initialize():
            logger.error("Failed to initialize trading components")
            logger.info("Please check the following:")
            logger.info("1. MetaTrader 5 is running")
            logger.info("2. You are logged in to your account")
            logger.info("3. The symbol exists in Market Watch")
            logger.info("4. You have an active internet connection")
            logger.info("5. Your account has sufficient permissions")
            
            # Try to shutdown MT5 if it was initialized
            try:
                if mt5.terminal_info() is not None:  # type: ignore[attr-defined]
                    mt5.shutdown()  # type: ignore[attr-defined]
            except Exception:
                pass
                
            return False  # Return False to indicate initialization failure
        
        logger.info("Trading bot started")
        logger.info(f"Trading symbol: {SYMBOLS[0]}")
        logger.info(f"Timeframes: {', '.join(self.timeframes)}")
        logger.info("Press Ctrl+C to stop the bot")
        
        try:
            consecutive_errors = 0
            max_consecutive_errors = 5
            symbol_failures = 0  # Track symbol selection failures
            max_symbol_failures = 3  # Maximum symbol failures before clearing cache
            last_successful_symbol_check = time.time()  # Track when symbol was last successfully selected
            symbol_check_interval = 30  # Check symbol availability every 30 seconds
            
            while True:
                try:
                    current_time = time.time()
                    
                    # Only check symbol selection periodically to avoid continuous errors
                    if current_time - last_successful_symbol_check > symbol_check_interval:
                        # Clear cache to force symbol re-check
                        self.selected_symbols.clear()
                        last_successful_symbol_check = current_time
                        symbol_failures = 0  # Reset failure counter
                        logger.debug("Cleared symbol cache for periodic re-check")
                    
                    # Process the symbol
                    self.process_symbol(SYMBOLS[0])
                    
                    # Reset error counter on successful iteration
                    consecutive_errors = 0
                    symbol_failures = 0  # Reset symbol failure counter on success
                    last_successful_symbol_check = current_time
                    
                    # Sleep before next iteration
                    time.sleep(1)  # Check every second
                    
                except KeyboardInterrupt:
                    logger.info("Trading bot stopped by user")
                    break
                    
                except Exception as e:
                    consecutive_errors += 1
                    
                    # Check if it's a symbol selection error
                    if "Failed to select" in str(e) or "Symbol" in str(e):
                        symbol_failures += 1
                        if symbol_failures >= max_symbol_failures:
                            logger.warning(f"Too many symbol selection failures ({symbol_failures}), clearing cache and waiting")
                            self.selected_symbols.clear()
                            symbol_failures = 0
                            time.sleep(30)  # Wait 30 seconds before retrying
                    else:
                        # For non-symbol errors, use exponential backoff
                        wait_time = min(60, self.retry_delay * (2 ** (consecutive_errors - 1)))
                        logger.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    
                    logger.error(f"Error in main loop (attempt {consecutive_errors}/{max_consecutive_errors}): {str(e)}", 
                               exc_info=VERBOSE)  # Full traceback only in verbose mode
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"Too many consecutive errors ({max_consecutive_errors}), stopping bot")
                        break
        
        except Exception as e:
            logger.critical(f"Critical error in main loop: {str(e)}", exc_info=True)
            
        finally:
            # Clean up resources
            logger.info("Shutting down trading bot...")
            try:
                if mt5.terminal_info() is not None:  # type: ignore[attr-defined]
                    mt5.shutdown()  # type: ignore[attr-defined]
                    logger.info("MT5 connection closed")
            except Exception as e:
                logger.error(f"Error during shutdown: {str(e)}")
            
            logger.info("Trading bot shutdown complete")
        
        return True  # Return True if bot completed successfully

# MT5 timeframe mapping
TIMEFRAME_MAPPING = {
    'M1': mt5.TIMEFRAME_M1,
    'M5': mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15,
    'M30': mt5.TIMEFRAME_M30,
    'H1': mt5.TIMEFRAME_H1,
    'H4': mt5.TIMEFRAME_H4,
    'D1': mt5.TIMEFRAME_D1,
}

if __name__ == "__main__":
    executor = StrategyExecutor()
    executor.run()
