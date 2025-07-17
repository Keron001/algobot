import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import pytz
from datetime import datetime, time as dt_time
from typing import Optional, Tuple, Dict, Any
from config import (
    MAGIC_NUMBER, DEFAULT_LOT_SIZE, 
    STOP_LOSS_PIPS, TAKE_PROFIT_PIPS,
    RISK_PERCENT, VERBOSE, TRADING_HOURS,
    PAPER_INITIAL_BALANCE, PAPER_SLIPPAGE, PAPER_COMMISSION
)
from utils.logger import get_logger
from data.fetch_mt5 import ensure_mt5_connection
import json

# Constants
MAX_SPREAD_PIPS = 50  # Maximum allowed spread in pips
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
MIN_TICK_UPDATE_TIME = 1.0  # Minimum time between tick updates (seconds)

logger = get_logger("TradeManager")

class ConnectionMonitor:
    """Monitors and maintains MT5 connection health"""
    def __init__(self):
        self.last_check = 0
        self.last_tick_time = {}
        self.connection_errors = 0
        self.max_connection_errors = 5
        
    def check_connection(self) -> bool:
        """Check if MT5 connection is healthy"""
        current_time = time.time()
        if current_time - self.last_check < 5:  # Throttle checks
            return True
            
        self.last_check = current_time
        try:
            # Use the improved connection management
            if not ensure_mt5_connection():
                logger.error("MT5 connection lost")
                self.connection_errors += 1
                return False
                
            # Verify we can get account info
            account = mt5.account_info()  # type: ignore
            if account is None:
                logger.error("Failed to get account info")
                self.connection_errors += 1
                return False
                
            self.connection_errors = 0
            return True
            
        except Exception as e:
            logger.error(f"Connection check failed: {str(e)}")
            self.connection_errors += 1
            return False
    
    def is_market_open(self, symbol: str) -> bool:
        """Check if market is open for trading"""
        try:
            # Check if within trading hours (using UTC time)
            utc_tz = pytz.UTC
            now_utc = datetime.now(utc_tz).time()
            market_open = dt_time(*map(int, TRADING_HOURS['start'].split(':')))
            market_close = dt_time(*map(int, TRADING_HOURS['end'].split(':')))
            
            if not (market_open <= now_utc <= market_close):
                logger.warning(f"Outside trading hours: {TRADING_HOURS['start']}-{TRADING_HOURS['end']} UTC (current UTC time: {now_utc})")
                return False
                
            # Check if we have recent tick data - update with current tick time
            current_time = time.time()
            self.last_tick_time[symbol] = current_time
            
            # For now, always allow trading if we have valid prices
            # The tick data check was too restrictive
            return True
                
            return True
            
        except Exception as e:
            logger.error(f"Market check failed: {str(e)}")
            return False

class TradeManager:
    def __init__(self, symbol, lot_size=DEFAULT_LOT_SIZE, paper_trading=False):
        self.symbol = symbol.upper()
        self.lot_size = lot_size
        self.magic = MAGIC_NUMBER
        self.max_retries = MAX_RETRIES
        self.retry_delay = RETRY_DELAY
        self.connection = ConnectionMonitor()
        self.performance_metrics = {
            'trades': 0,
            'errors': 0,
            'avg_execution_time': 0.0,
            'last_trade_time': 0
        }
        self.volatility_cache = {}  # Store ATR values for volatility-based sizing
        self.paper_trading = paper_trading
        self.paper_trades = []  # Store simulated trades
        self.paper_positions = []  # Open simulated positions
        self.paper_closed_trades = []  # Closed simulated trades
        self.paper_balance = PAPER_INITIAL_BALANCE
        self.paper_equity = PAPER_INITIAL_BALANCE
        self.paper_history = []  # Equity curve
        
        # Ensure MT5 connection is established
        if not ensure_mt5_connection():
            raise RuntimeError("Failed to establish MT5 connection")
            
        try:
            # First, try to get the symbol info with retries
            symbol_info = None
            for attempt in range(self.max_retries):
                symbol_info = mt5.symbol_info(symbol)  # type: ignore
                if symbol_info is not None:
                    break
                logger.warning(f"Failed to get symbol info (attempt {attempt + 1}/{self.max_retries})")
                time.sleep(self.retry_delay)
            
            # If symbol not found or not visible, try to select it
            if symbol_info is None or not symbol_info.visible:
                logger.warning(f"Symbol {symbol} not in Market Watch, attempting to add...")
                
                # First, try to select the symbol
                if not mt5.symbol_select(symbol, True):  # type: ignore
                    error = mt5.last_error()  # type: ignore
                    logger.error(f"Failed to select {symbol}: {error}")
                    
                    # Try to find a similar symbol
                    all_symbols = mt5.symbols_get()  # type: ignore
                    if all_symbols is not None and len(all_symbols) > 0:
                        similar_symbols = [s.name for s in all_symbols if symbol.lower() in s.name.lower()]
                        if similar_symbols:
                            logger.warning(f"Found similar symbols: {', '.join(similar_symbols)}")
                            # Try the first similar symbol
                            alternative = similar_symbols[0]
                            logger.warning(f"Trying alternative symbol: {alternative}")
                            if not mt5.symbol_select(alternative, True):  # type: ignore
                                raise RuntimeError(f"Failed to select alternative symbol {alternative}")
                            symbol = alternative
                            symbol_info = mt5.symbol_info(symbol)  # type: ignore
                            if symbol_info is None:
                                raise RuntimeError(f"Failed to get info for alternative symbol {alternative}")
                    else:
                        raise RuntimeError(f"No symbols available from MT5. Please check your MT5 terminal connection.")
                else:
                    # Refresh symbol info after selection
                    symbol_info = mt5.symbol_info(symbol)  # type: ignore
            
            # If we still don't have symbol info, raise an error
            if symbol_info is None:
                raise RuntimeError(f"Failed to get symbol info for {symbol}")
                
            # Check if symbol is tradeable
            if symbol_info.trade_mode != 0:  # 0 = TRADE_MODE_FULL
                if symbol_info.trade_mode == 4:  # TRADE_MODE_MARGIN
                    logger.warning(f"Symbol {symbol} is in margin mode (4). This might limit some trading operations.")
                else:
                    logger.warning(f"Symbol {symbol} has limited trading mode: {symbol_info.trade_mode}")
            
                # For XAUUSD with trade mode 4, we'll still try to proceed
                if symbol.upper() == 'XAUUSD' and symbol_info.trade_mode == 4:
                    logger.info("Proceeding with XAUUSD despite limited trading mode")
                    
            # Check if we can get tick data
            tick = mt5.symbol_info_tick(symbol)  # type: ignore
            if tick is None:
                logger.warning(f"Warning: Could not get tick data for {symbol}")
            else:
                logger.info(f"Current {symbol} price: Bid={tick.bid}, Ask={tick.ask}")
                
        except Exception as e:
            raise RuntimeError(f"Error initializing symbol {symbol}: {str(e)}")
            
        # If we get here, we have a valid symbol_info
        
        try:
            # Store symbol information
            self.point = symbol_info.point
            self.digits = symbol_info.digits
            self.symbol = symbol  # Update symbol in case we switched to an alternative
            
            # Log successful initialization
            logger.info(f"Initialized TradeManager for {self.symbol}:")
            logger.info(f"  Description: {getattr(symbol_info, 'description', 'N/A')}")
            logger.info(f"  Point: {self.point}")
            logger.info(f"  Digits: {self.digits}")
            logger.info(f"  Lot Size: {self.lot_size}")
            logger.info(f"  Magic Number: {self.magic}")
            logger.info(f"  Trade Mode: {getattr(symbol_info, 'trade_mode', 'N/A')}")
            logger.info(f"  Trade Ticks: {getattr(symbol_info, 'trade_ticks', 'N/A')}")
            
        except Exception as e:
            raise RuntimeError(f"Error initializing TradeManager: {str(e)}")
            
        finally:
            # We don't shutdown MT5 here as we'll need it for trading
            pass
        
    def get_position(self):
        """
        Get the current position status for the symbol
        Returns:
            tuple: (position_count, position_type) 
                - position_count: number of open positions
                - position_type: 1 for long, -1 for short, 0 for no position
        """
        positions = mt5.positions_get(symbol=self.symbol)  # type: ignore
        if positions is None or len(positions) == 0:
            logger.debug(f"No positions found for {self.symbol}")
            return 0, 0
            
        # Count positions and determine direction
        position_count = 0
        position_type = 0
        
        for position in positions:
            if position.symbol == self.symbol and position.magic == self.magic:
                position_count += 1
                if position.type == mt5.ORDER_TYPE_BUY:
                    position_type = 1
                elif position.type == mt5.ORDER_TYPE_SELL:
                    position_type = -1
                    
        logger.debug(f"Found {position_count} positions for {self.symbol}, type: {position_type}")
        return position_count, position_type
        
    def get_market_volatility(self, symbol: str, period: int = 14, timeframe=mt5.TIMEFRAME_D1) -> float:
        """Calculate Average True Range (ATR) for volatility measurement"""
        try:
            # Check cache first
            cache_key = f"{symbol}_{timeframe}_{period}"
            if cache_key in self.volatility_cache:
                return self.volatility_cache[cache_key]
                
            # Get historical data
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 1)  # type: ignore
            if rates is None or len(rates) < period:
                return 0.0
                
            # Calculate True Range
            high = rates['high'][1:]
            low = rates['low'][1:]
            close = rates['close'][:-1]
            
            tr1 = high - low
            tr2 = np.abs(high - close)
            tr3 = np.abs(low - close)
            
            true_ranges = np.maximum(np.maximum(tr1, tr2), tr3)
            atr = np.mean(true_ranges)
            
            # Cache the result
            self.volatility_cache[cache_key] = atr
            return atr
            
        except Exception as e:
            logger.error(f"Error calculating volatility: {str(e)}")
            return 0.0
            
    def calculate_dynamic_position_size(self, symbol: str, stop_loss_pips: float, 
                                      volatility_adjustment: float = 1.0) -> Tuple[float, float]:
        """Calculate position size based on volatility and account balance"""
        try:
            # Get account balance
            account = mt5.account_info()  # type: ignore
            if account is None:
                logger.error("Failed to get account info")
                return 0.0, 0.0
                
            # Get current price for position sizing
            tick = mt5.symbol_info_tick(symbol)  # type: ignore
            if tick is None:
                logger.error("Failed to get current price")
                return 0.0, 0.0
                
            # Get volatility (ATR)
            atr = self.get_market_volatility(symbol)
            current_price = (tick.ask + tick.bid) / 2
            
            # Adjust risk based on volatility
            if atr > 0:
                volatility_ratio = atr / (current_price * 0.01)  # ATR as % of price
                volatility_factor = max(0.5, min(2.0, 1.0 / (volatility_ratio * 10)))
            else:
                volatility_factor = 1.0
                
            # Calculate position size
            risk_amount = account.balance * (RISK_PERCENT / 100) * volatility_adjustment * volatility_factor
            risk_per_share = stop_loss_pips * 10 * (0.1 if symbol.upper() == 'XAUUSD' else 0.0001)
            
            if risk_per_share <= 0:
                logger.error("Invalid risk per share calculation")
                return 0.0, 0.0
                
            position_size = risk_amount / risk_per_share
            
            # Convert to lots (1 lot = 100,000 units for forex)
            lot_size = round(position_size / 100000, 2)
            
            logger.info(f"Dynamic position size: {lot_size:.2f} lots "
                      f"(Risk: {RISK_PERCENT}%, Volatility: {volatility_factor:.2f}x)")
                      
            return lot_size, RISK_PERCENT * volatility_adjustment * volatility_factor
            
        except Exception as e:
            logger.error(f"Error in position sizing: {str(e)}")
            return 0.0, 0.0

    def _simulate_paper_trade(self, signal, price, stop_loss_pips, take_profit_pips, volatility_adjustment, comment, is_additional_trade):
        # Apply slippage
        slippage = PAPER_SLIPPAGE if signal > 0 else -PAPER_SLIPPAGE
        exec_price = price + slippage
        # Commission
        commission = PAPER_COMMISSION
        # Simulate position opening
        position = {
            'symbol': self.symbol,
            'signal': signal,
            'lot_size': self.lot_size,
            'open_price': exec_price,
            'stop_loss': exec_price - stop_loss_pips if signal > 0 else exec_price + stop_loss_pips,
            'take_profit': exec_price + take_profit_pips if signal > 0 else exec_price - take_profit_pips,
            'open_time': time.time(),
            'comment': comment,
            'commission': commission,
            'is_open': True
        }
        self.paper_positions.append(position)
        self.paper_balance -= commission  # Deduct commission
        self._update_paper_equity(exec_price)
        self._write_paper_state()
        logger.info(f"[PAPER TRADE] Opened simulated {'BUY' if signal > 0 else 'SELL'} position: {position}")
        return True

    def _update_paper_equity(self, last_price):
        # Mark-to-market all open positions
        equity = self.paper_balance
        for pos in self.paper_positions:
            if pos['is_open']:
                pnl = (last_price - pos['open_price']) * pos['lot_size'] * (1 if pos['signal'] > 0 else -1)
                equity += pnl
        self.paper_equity = equity
        self.paper_history.append({'time': time.time(), 'equity': equity, 'balance': self.paper_balance})

    def _close_paper_positions(self, current_price):
        # Simulate SL/TP and close positions
        for pos in self.paper_positions:
            if not pos['is_open']:
                continue
            hit_sl = (pos['signal'] > 0 and current_price <= pos['stop_loss']) or (pos['signal'] < 0 and current_price >= pos['stop_loss'])
            hit_tp = (pos['signal'] > 0 and current_price >= pos['take_profit']) or (pos['signal'] < 0 and current_price <= pos['take_profit'])
            if hit_sl or hit_tp:
                close_price = pos['stop_loss'] if hit_sl else pos['take_profit']
                pnl = (close_price - pos['open_price']) * pos['lot_size'] * (1 if pos['signal'] > 0 else -1)
                pos['close_price'] = close_price
                pos['close_time'] = time.time()
                pos['pnl'] = pnl - pos['commission']
                pos['is_open'] = False
                self.paper_balance += pnl
                self.paper_closed_trades.append(pos)
                logger.info(f"[PAPER TRADE] Closed simulated position: {pos}")
        self._update_paper_equity(current_price)
        self._write_paper_state()

    def _write_paper_state(self):
        # Write all simulated trades, positions, and account state to file
        state = {
            'open_positions': self.paper_positions,
            'closed_trades': self.paper_closed_trades,
            'balance': self.paper_balance,
            'equity': self.paper_equity,
            'history': self.paper_history
        }
        try:
            with open('paper_trades.json', 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write paper trading state: {e}")

    def execute_trade(self, signal, stop_loss_pips=None, take_profit_pips=None, 
                     volatility_adjustment=1.0, comment="", is_additional_trade=False):
        """
        Execute a trade with proper risk management and retry logic
        If paper_trading is True, simulate the trade and log it instead of sending to MT5.
        """
        from config import (
            STOP_LOSS_PIPS, TAKE_PROFIT_PIPS, 
            MIN_POSITION_SIZE, MAX_POSITION_SIZE,
            ADDITIONAL_TRADE_LOT_SIZE, ORDER_FILLING_TYPE
        )
        
        # Use default values if not provided
        stop_loss_pips = stop_loss_pips or STOP_LOSS_PIPS
        take_profit_pips = take_profit_pips or TAKE_PROFIT_PIPS
        
        # Validate inputs
        if signal not in (1, -1):
            logger.error(f"Invalid signal: {signal}. Must be 1 (buy) or -1 (sell)")
            return False
            
        if not 0 < volatility_adjustment <= 1.0:
            logger.warning(f"Volatility adjustment {volatility_adjustment} out of range (0-1), using 1.0")
            volatility_adjustment = 1.0
            
        if self.paper_trading:
            # Simulate trade at current price (no MT5)
            # You may want to pass price as an argument for more realism
            price = 0  # TODO: Pass actual price from caller
            return self._simulate_paper_trade(signal, price, stop_loss_pips, take_profit_pips, volatility_adjustment, comment, is_additional_trade)
            
        # Ensure MT5 connection is established
        if not ensure_mt5_connection():
            logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
            return False
            
        signal_type = "BUY" if signal > 0 else "SELL"
        logger.info(f"Preparing to execute {signal_type} order for {self.symbol}")
        
        # Get current position status
        position_count, position_type = self.get_position()
        
        # Check maximum position limit
        from config import MAX_OPEN_POSITIONS
        if position_count >= MAX_OPEN_POSITIONS:
            logger.warning(f"Maximum positions ({MAX_OPEN_POSITIONS}) reached for {self.symbol}. Skipping trade.")
            return False
        # Prevent hedging: do not allow both BUY and SELL at the same time
        if position_count > 0 and ((signal > 0 and position_type < 0) or (signal < 0 and position_type > 0)):
            logger.warning(f"Opposite position already open for {self.symbol}. Skipping trade to prevent hedging.")
            return False
        
        # Check if we already have a position in the same direction
        if (signal > 0 and position_type > 0) or (signal < 0 and position_type < 0):
            if VERBOSE:
                logger.info(f"Position already exists in the same direction for {signal_type} signal")
            # We'll still proceed to open another position if under the limit
            
        # Calculate position size
        try:
            if is_additional_trade:
                # Use fixed lot size for additional trades
                lot_size = min(max(ADDITIONAL_TRADE_LOT_SIZE, MIN_POSITION_SIZE), MAX_POSITION_SIZE)
                adjusted_risk = 0.1  # Fixed risk for additional trades
                logger.info(f"Using fixed lot size for additional trade: {lot_size} lots")
            else:
                # Use configured lot size for simplicity
                lot_size = self.lot_size
                adjusted_risk = 0.1
                logger.info(f"Using configured lot size: {lot_size} lots")
                
            if lot_size <= 0:
                logger.error(f"Invalid lot size: {lot_size}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to calculate position size: {str(e)}")
            return False
                
        # Get current price with retry logic and validation
        tick = None
        for attempt in range(self.max_retries):
            try:
                tick = mt5.symbol_info_tick(self.symbol)  # type: ignore
                if tick is not None and hasattr(tick, 'bid') and hasattr(tick, 'ask') and tick.bid > 0 and tick.ask > 0:
                    # Validate the spread is reasonable (less than 100 pips for XAUUSD)
                    spread_pips = (tick.ask - tick.bid) / (0.1 if self.symbol.upper() == 'XAUUSD' else 0.0001)
                    if spread_pips > 100:  # Unusually wide spread
                        logger.warning(f"Wide spread detected: {spread_pips:.1f} pips (attempt {attempt + 1}/{self.max_retries})")
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay)
                            continue
                    break
                else:
                    logger.warning(f"Invalid tick data received (attempt {attempt + 1}/{self.max_retries})")
            except Exception as e:
                logger.warning(f"Error fetching tick data (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        if tick is None or not hasattr(tick, 'bid') or not hasattr(tick, 'ask') or tick.bid <= 0 or tick.ask <= 0:
            logger.error(f"Failed to get valid tick data for {self.symbol} after {self.max_retries} attempts")
            if tick is not None:
                logger.error(f"Invalid tick data: bid={getattr(tick, 'bid', 'N/A')}, ask={getattr(tick, 'ask', 'N/A')}")
            return False
            
        logger.info(f"Current {self.symbol} price - Bid: {tick.bid:.5f}, Ask: {tick.ask:.5f}, Spread: {(tick.ask-tick.bid)/0.1 if self.symbol.upper() == 'XAUUSD' else (tick.ask-tick.bid)/0.0001:.1f} pips")
            
        # Get symbol info with retry logic and validation
        symbol_info = None
        for attempt in range(self.max_retries):
            try:
                symbol_info = mt5.symbol_info(self.symbol)  # type: ignore
                if symbol_info is not None and hasattr(symbol_info, 'point') and hasattr(symbol_info, 'digits'):
                    break
                logger.warning(f"Incomplete symbol info received (attempt {attempt + 1}/{self.max_retries})")
            except Exception as e:
                logger.warning(f"Error fetching symbol info (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        if symbol_info is None or not hasattr(symbol_info, 'point') or not hasattr(symbol_info, 'digits'):
            logger.error(f"Failed to get valid symbol info for {self.symbol} after {self.max_retries} attempts")
            if symbol_info is not None:
                logger.error(f"Symbol info missing required attributes: {', '.join([a for a in ['point', 'digits'] if not hasattr(symbol_info, a)])}")
            return False
            
        # Ensure the symbol is selected in Market Watch
        if not symbol_info.visible:
            logger.warning(f"Symbol {self.symbol} not in Market Watch, attempting to add...")
            if not mt5.symbol_select(self.symbol, True):  # type: ignore
                error = mt5.last_error()  # type: ignore
                logger.error(f"Failed to add {self.symbol} to Market Watch: {error}")
                return False
            # Refresh symbol info after selection
            symbol_info = mt5.symbol_info(self.symbol)  # type: ignore
            if symbol_info is None or not symbol_info.visible:
                logger.error(f"Failed to verify {self.symbol} in Market Watch after selection")
                return False
            
        # For XAUUSD, we need to adjust the point value
        if self.symbol.upper() == 'XAUUSD':
            point = 0.01  # XAUUSD has 2 decimal places
            pip_value = 0.1  # 1 pip = 0.1 for XAUUSD (2 decimal places)
            logger.info("XAUUSD detected: Using special pip calculation (1 pip = 0.1)")
        else:
            point = symbol_info.point if hasattr(symbol_info, 'point') else 0.0001
            pip_value = point * 10  # For 5-digit brokers, 1 pip = 10 points
            
        # Log the calculated values for verification
        logger.info(f"Point value: {point}, Pip value: {pip_value}, Digits: {symbol_info.digits if hasattr(symbol_info, 'digits') else 'N/A'}")
            
        # Get minimum stop level in points with fallback
        min_stop_level = 0
        if hasattr(symbol_info, 'trade_stops_level') and symbol_info.trade_stops_level > 0:
            min_stop_level = symbol_info.trade_stops_level * point
            logger.info(f"Using trade_stops_level: {symbol_info.trade_stops_level} points")
        elif hasattr(symbol_info, 'levels_stoplevel') and symbol_info.levels_stoplevel > 0:
            min_stop_level = symbol_info.levels_stoplevel * point
            logger.info(f"Using levels_stoplevel: {symbol_info.levels_stoplevel} points")
        else:
            # Fallback to a reasonable default (30 pips)
            min_stop_level = 30 * pip_value
            logger.warning(f"No stop level found in symbol info, using default: {min_stop_level} ({30} pips)")
            
        logger.info(f"Minimum stop level: {min_stop_level} ({min_stop_level/pip_value:.1f} pips)")
        
        # Calculate stop loss and take profit
        if signal > 0:  # BUY
            price = tick.ask
            sl = price - (stop_loss_pips * pip_value)
            tp = price + (take_profit_pips * pip_value)
            order_type = mt5.ORDER_TYPE_BUY
            
            # Ensure SL/TP are valid distances from price
            min_sl_distance = price - sl  # Positive for BUY
            min_tp_distance = tp - price  # Positive for BUY
            
            # Check against minimum stop level
            if min_sl_distance < min_stop_level:
                logger.warning(f"SL distance {min_sl_distance} is less than minimum {min_stop_level}. Adjusting...")
                sl = price - min_stop_level
                
            if min_tp_distance < min_stop_level:
                logger.warning(f"TP distance {min_tp_distance} is less than minimum {min_stop_level}. Adjusting...")
                tp = price + min_stop_level
                
        else:  # SELL
            price = tick.bid
            sl = price + (stop_loss_pips * pip_value)
            tp = price - (take_profit_pips * pip_value)
            order_type = mt5.ORDER_TYPE_SELL
            
            # Ensure SL/TP are valid distances from price
            min_sl_distance = sl - price  # Positive for SELL
            min_tp_distance = price - tp  # Positive for SELL
            
            # Check against minimum stop level
            if min_sl_distance < min_stop_level:
                logger.warning(f"SL distance {min_sl_distance} is less than minimum {min_stop_level}. Adjusting...")
                sl = price + min_stop_level
                
            if min_tp_distance < min_stop_level:
                logger.warning(f"TP distance {min_tp_distance} is less than minimum {min_stop_level}. Adjusting...")
                tp = price - min_stop_level
        
        # Prepare the trade request
        # Ensure comment is a valid string
        safe_comment = str(comment) if comment else "AlgoBot_Trade"
        safe_comment = safe_comment[:25]  # Limit comment length to 25 characters
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lot_size,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,  # Slippage in points
            "magic": self.magic,
            "comment": safe_comment,
            "type_time": mt5.ORDER_TIME_GTC,  # Good Till Cancel
            "type_filling": mt5.ORDER_FILLING_FOK  # Fill or Kill
        }
        
        logger.info(f"Sending {signal_type} order: {lot_size} lots, price={price}, sl={sl}, tp={tp}")
        
        # Execute the trade with timing
        start_time = time.time()
        
        try:
            # Check connection before sending order
            if not self.connection.check_connection():
                logger.error("Cannot execute trade: Connection check failed")
                self.performance_metrics['errors'] += 1
                return False
            
            # Check market conditions
            if not self.connection.is_market_open(self.symbol):
                logger.error(f"Cannot execute trade: Market conditions not favorable for {self.symbol}")
                return False
            
            # Execute the trade
            result = mt5.order_send(request)  # type: ignore
            execution_time = time.time() - start_time
            
            # Update performance metrics
            self.performance_metrics['trades'] += 1
            self.performance_metrics['last_trade_time'] = time.time()
            self.performance_metrics['avg_execution_time'] = (
                (self.performance_metrics['avg_execution_time'] * (self.performance_metrics['trades'] - 1) + execution_time) 
                / self.performance_metrics['trades']
            )
            
            if result is None:
                error = mt5.last_error()  # type: ignore
                logger.error(f"Failed to send order: {error}")
                self.performance_metrics['errors'] += 1
                return False
                
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Failed to open {signal_type} position: {result.comment} (code: {result.retcode})")
                self.performance_metrics['errors'] += 1
                return False
            
            logger.info(f"Successfully executed {signal_type} position in {execution_time*1000:.2f}ms: {result.order}")
            logger.info(f"   Price: {result.price}, SL: {getattr(result, 'sl', 'N/A')}, TP: {getattr(result, 'tp', 'N/A')}")
            
            # Log performance metrics periodically
            if self.performance_metrics['trades'] % 10 == 0:
                self.log_performance_metrics()
            
            return True
            
        except Exception as e:
            logger.error(f"Unexpected error in execute_trade: {str(e)}")
            self.performance_metrics['errors'] += 1
            return False
                
    def calculate_position_size(self, symbol, stop_loss_pips, volatility_adjustment=1.0, signal=0):
        """
        Calculate position size based on account balance, risk percentage, and stop loss
        with volatility adjustment
        
        Args:
            symbol: Trading symbol
            stop_loss_pips: Stop loss in pips
            volatility_adjustment: Multiplier based on market volatility (0.1 to 1.0)
            signal: 1 for buy, -1 for sell (used for margin calculation)
            
        Returns:
            tuple: (position_size, adjusted_risk)
        """
        try:
            # Import config values here to avoid circular imports
            from config import RISK_PERCENT, MIN_RISK_PERCENT, MAX_RISK_PERCENT
            
            # Get account info
            account_info = mt5.account_info()  # type: ignore
            if account_info is None:
                logger.error("Failed to get account info")
                return 0.0, 0.0
                
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)  # type: ignore
            if symbol_info is None:
                logger.error(f"Failed to get symbol info for {symbol}")
                return 0.0, 0.0
                
            # Calculate position size based on risk
            balance = account_info.balance
            
            # Adjust risk based on volatility (clamped between min and max)
            adjusted_risk = max(MIN_RISK_PERCENT, 
                              min(MAX_RISK_PERCENT, 
                                  RISK_PERCENT * volatility_adjustment)) / 100.0
            risk_amount = balance * adjusted_risk
            
            # Get point value and pip value
            if symbol.upper() == 'XAUUSD':
                point = 0.01  # XAUUSD has 2 decimal places
                pip_value = 0.1  # 1 pip = 0.1 for XAUUSD
            else:
                point = symbol_info.point if symbol_info.point > 0 else 0.0001  # Default for most forex pairs
                pip_value = point * 10  # For 5-digit brokers, 1 pip = 10 points
                
            # Calculate tick value (value per 1 lot per pip)
            tick_value = 1.0  # Default value
            if hasattr(symbol_info, 'trade_tick_value') and symbol_info.trade_tick_value > 0:
                tick_value = symbol_info.trade_tick_value
            
            # For XAUUSD, adjust the tick value if needed
            if symbol.upper() == 'XAUUSD' and tick_value == 1.0:
                # Estimate tick value based on current price
                tick = mt5.symbol_info_tick(symbol)  # type: ignore
                if tick is not None:
                    # Assuming 1 standard lot (100,000 units) of XAUUSD
                    # 1 pip = 0.1 * 100,000 = 10,000 units of account currency
                    tick_value = 10.0  # This is an estimate, adjust based on your broker
                    logger.info(f"Using estimated tick value for XAUUSD: {tick_value}")
            
            # Calculate position size
            stop_loss_price = stop_loss_pips * 10 * point
            if stop_loss_price == 0:
                logger.error("Stop loss price is zero")
                return 0.0, 0.0
                
            # Get current market data
            tick = mt5.symbol_info_tick(symbol)  # type: ignore
            spread = (tick.ask - tick.bid) / point if tick and point > 0 else 0
            spread_pips = spread * 10  # Convert points to pips
            
            # Log initial calculation parameters with better formatting
            logger.info("\n" + "=" * 85)
            logger.info(f"🔍 POSITION SIZE CALCULATION FOR {symbol.upper():<10} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 85)
            
            # Account Information
            logger.info("\n💼 ACCOUNT INFORMATION")
            logger.info("-" * 40)
            logger.info(f"{'Balance:':<20} {account_info.balance:>12.2f} {account_info.currency}")
            logger.info(f"{'Equity:':<20} {account_info.equity:>12.2f} {account_info.currency}")
            logger.info(f"{'Free Margin:':<20} {account_info.margin_free:>12.2f} {account_info.currency}")
            logger.info(f"{'Leverage:':<20} 1:{account_info.leverage:<10}")
            
            # Market Data & Conditions
            logger.info("\n📈 MARKET CONDITIONS")
            logger.info("-" * 80)
            
            # Get current price early to avoid undefined variable error
            if tick is None:
                logger.error("No tick data available for position size calculation")
                return 0.0, 0.0
            current_price = tick.ask if signal >= 0 else tick.bid
            
            if tick:
                # Calculate spread impact as percentage of price
                spread_impact = (spread / current_price) * 100 if current_price > 0 else 0
                
                # Get current market session
                current_hour = datetime.now().hour
                if 0 <= current_hour < 5:
                    market_session = "Asian"
                elif 5 <= current_hour < 13:
                    market_session = "European"
                elif 13 <= current_hour < 21:
                    market_session = "American"
                else:
                    market_session = "Pacific"
                
                # Get daily ATR for volatility
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 14)  # type: ignore
                atr = np.mean([high - low for high, low in zip(rates['high'], rates['low'])]) if len(rates) > 0 else 0
                atr_pips = atr / point / 10
                
                # Log market data
                logger.info("Current Price Levels:")
                logger.info(f" - Bid/Ask:          {tick.bid:.5f} / {tick.ask:.5f}")
                logger.info(f" - Spread:           {spread_pips:>6.1f} pips ({spread_impact:.4f}% of price)")
                logger.info("\nMarket Conditions:")
                logger.info(f" - Volatility (ATR): {atr_pips:>6.1f} pips (14-day average)")
                logger.info(f" - Market Session:   {market_session} (Current hour: {current_hour}:00)")
                
                # Spread warning
                if spread_pips > 5.0:  # Adjust threshold as needed
                    logger.warning("⚠️  High spread detected! Consider waiting for better conditions.")
            else:
                logger.warning("  - No current market data available")
            
            # Risk Parameters
            logger.info("\n⚠️  RISK PARAMETERS")
            logger.info("-" * 40)
            logger.info(f"{'Base Risk:':<20} {RISK_PERCENT:>12.2f}%")
            logger.info(f"{'Volatility Adj:':<20} {volatility_adjustment:>12.2f}")
            logger.info(f"{'Effective Risk:':<20} {adjusted_risk*100:>10.2f}%")
            logger.info(f"{'Risk Amount:':<20} {risk_amount:>12.2f} {account_info.currency}")
            logger.info(f"{'Stop Loss:':<20} {stop_loss_pips:>12.2f} pips")
            
            # Calculate risk-reward ratio if take profit is available
            from config import TAKE_PROFIT_PIPS
            if hasattr(self, 'take_profit_pips'):
                risk_reward = TAKE_PROFIT_PIPS / stop_loss_pips
                logger.info(f"{'Risk-Reward:':<20} 1:{risk_reward:>11.2f}")
            else:
                logger.info(f"{'Take Profit:':<20} {TAKE_PROFIT_PIPS:>12.2f} pips")
                logger.info(f"{'Risk-Reward:':<20} 1:{TAKE_PROFIT_PIPS/stop_loss_pips:>11.2f}")
                
            # Symbol Information
            logger.info("\n📊 SYMBOL INFORMATION")
            logger.info("-" * 40)
            logger.info(f"{'Point Value:':<20} {point:>12.5f}")
            logger.info(f"{'Pip Value:':<20} {pip_value:>12.5f}")
            logger.info(f"{'Tick Value:':<20} {tick_value:>12.5f} {account_info.currency}")
            if symbol.upper() == 'XAUUSD':
                logger.info("  - XAUUSD detected: Using special pip calculation (1 pip = 0.1)")
            
            # Determine trade direction
            trade_type = "BUY" if signal >= 0 else "SELL"
            
            # Calculate price levels
            if trade_type == "BUY":
                stop_loss_price = current_price - (stop_loss_pips * point * 10)
                take_profit_price = current_price + (TAKE_PROFIT_PIPS * point * 10)
            else:
                stop_loss_price = current_price + (stop_loss_pips * point * 10)
                take_profit_price = current_price - (TAKE_PROFIT_PIPS * point * 10)
            
            # Position Size Calculation
            logger.info("\n🧮 TRADE DETAILS")
            logger.info("-" * 80)
            logger.info(f"{'Trade Type:':<20} {trade_type:>12}")
            logger.info(f"{'Current Price:':<20} {current_price:>12.5f}")
            logger.info(f"{'Stop Loss:':<20} {stop_loss_price:>12.5f} ({stop_loss_pips:.1f} pips)")
            logger.info(f"{'Take Profit:':<20} {take_profit_price:>12.5f} ({TAKE_PROFIT_PIPS:.1f} pips)")
            
            # Calculate risk-reward ratio
            risk_reward_ratio = TAKE_PROFIT_PIPS / stop_loss_pips
            risk_reward_str = f"1:{risk_reward_ratio:.2f}"
            
            # Visual risk-reward indicator
            rr_visual = ""
            if risk_reward_ratio >= 2.0:
                rr_visual = "✅ Excellent (1:2+)"
            elif risk_reward_ratio >= 1.5:
                rr_visual = "👍 Good (1:1.5+)"
            else:
                rr_visual = "⚠️  Low (1:1.5-)"
                
            logger.info(f"\n📊 RISK-REWARD ANALYSIS")
            logger.info("-" * 80)
            logger.info(f"{'Risk-Reward:':<20} {risk_reward_str:<15} {rr_visual}")
            
            # Visual representation of risk-reward
            sl_units = int(min(20, abs(stop_loss_pips) * 2))
            tp_units = int(min(40, TAKE_PROFIT_PIPS * 2))
            logger.info(f"{'Risk:':<20} [{'=' * sl_units}>{' ' * (20-sl_units)}] {abs(stop_loss_pips):.1f}p")
            logger.info(f"{'Reward:':<20} [{'=' * tp_units}>{' ' * (40-tp_units)}] {TAKE_PROFIT_PIPS:.1f}p")
            
            # Position Size Calculation
            logger.info("\n🧮 POSITION SIZE CALCULATION")
            logger.info("-" * 80)
            
            # Use configured lot size instead of risk-based calculation
            position_size = self.lot_size
            logger.info(f"{'Mode:':<20} {'Fixed Lot Size':>12}")
            logger.info(f"{'Lot Size:':<20} {position_size:.4f} lots")
            logger.info(f"{'Units:':<20} {position_size * 100000:>12,.0f}")
            
            # Position Size & Management
            logger.info("\n📦 POSITION MANAGEMENT")
            logger.info("-" * 80)
            
            # Calculate position as percentage of account
            position_value = position_size * 100000 * current_price if current_price > 0 else 0
            position_pct = (position_value / account_info.balance) * 100 if account_info.balance > 0 else 0
            
            # Position size details
            logger.info("Position Size Breakdown:")
            logger.info(f" - Standard Lots:    {position_size:>12.6f}")
            logger.info(f" - Units:            {position_size * 100000:>12,.0f}")
            logger.info(f" - Account %%:        {position_pct:>11.2f}% of balance")
            
            # Position sizing guidelines
            logger.info("\nPosition Sizing Guidelines:")
            logger.info(f" - Max Risk/Trade:   {RISK_PERCENT:>10.2f}% of balance")
            logger.info(f" - Current Risk:     {adjusted_risk*100:>10.2f}% of balance")
            
            # Position sizing visualization
            risk_ratio = (adjusted_risk * 100) / RISK_PERCENT
            risk_bars = min(20, int(risk_ratio * 20))
            logger.info("\nRisk Level: [" + "=" * risk_bars + " " * (20 - risk_bars) + "] " + 
                      f"{adjusted_risk*100:.1f}% of max risk")
            
            # Advanced Risk Analysis
            risk_per_pip = position_size * tick_value
            total_risk = risk_per_pip * abs(stop_loss_pips)
            
            # Calculate potential profit first
            if hasattr(self, 'take_profit_pips'):
                take_profit = self.take_profit_pips
            else:
                take_profit = TAKE_PROFIT_PIPS
            potential_profit = risk_per_pip * take_profit
            
            # Calculate expected value (simplified)
            win_rate = 0.60  # Default win rate, should be calculated from historical data
            expected_value = (win_rate * potential_profit) - ((1 - win_rate) * total_risk)
            
            # Kelly Criterion position sizing
            kelly_fraction = win_rate - ((1 - win_rate) / (TAKE_PROFIT_PIPS / abs(stop_loss_pips))) if abs(stop_loss_pips) > 0 else 0
            kelly_position_size = (account_info.balance * kelly_fraction) / total_risk if total_risk > 0 else 0
            
            logger.info("\n⚠️  ADVANCED RISK ANALYSIS")
            logger.info("-" * 80)
            
            # Basic Risk
            logger.info("Basic Risk Metrics:")
            logger.info(f" - Risk per Pip:     {risk_per_pip:>10.2f} {account_info.currency}")
            logger.info(f" - Total Risk:       {total_risk:>10.2f} {account_info.currency}")
            logger.info(f" - Stop Loss:        {stop_loss_pips:>10.2f} pips")
            
            # Advanced Metrics
            logger.info("\nAdvanced Risk Metrics:")
            logger.info(f" - Win Rate:         {win_rate*100:>9.1f}% (assumed)")
            logger.info(f" - Expected Value:   {expected_value:>10.2f} {account_info.currency} per trade")
            logger.info(f" - Kelly %%:         {kelly_fraction*100:>9.1f}% of account")
            logger.info(f" - Kelly Position:   {kelly_position_size:.4f} lots")
            
            # Risk Visualization
            logger.info("\nRisk Visualization:")
            risk_units = min(20, int((adjusted_risk * 100 / RISK_PERCENT) * 10))
            logger.info(f" [{'=' * risk_units}{' ' * (20-risk_units)}] {adjusted_risk*100:.1f}% of max risk")
            
            # Calculate potential profit/loss
            if hasattr(self, 'take_profit_pips'):
                take_profit = self.take_profit_pips
            else:
                take_profit = TAKE_PROFIT_PIPS
                
            potential_profit = risk_per_pip * take_profit
            logger.info(f"{'Take Profit:':<20} {take_profit:>12.2f} pips")
            logger.info(f"{'Potential Profit:':<20} {potential_profit:>12.2f} {account_info.currency}")
            
            # Margin Analysis
            logger.info("\n💳 MARGIN & ACCOUNT IMPACT")
            logger.info("-" * 80)
            
            try:
                # Calculate required margin
                margin_required = mt5.order_calc_margin(
                    mt5.ORDER_TYPE_BUY if signal >= 0 else mt5.ORDER_TYPE_SELL,
                    symbol,
                    position_size,
                    current_price
                )  # type: ignore
                
                if margin_required is not None:
                    free_margin = account_info.margin_free
                    equity = account_info.equity
                    balance = account_info.balance
                    margin_ratio = (margin_required / balance) * 100
                    margin_level = (equity / account_info.margin) * 100 if account_info.margin > 0 else 0
                    
                    # Calculate account impact
                    risk_percent = (total_risk / balance) * 100
                    margin_after_trade = free_margin - margin_required
                    
                    # Format margin ratio with color and risk level
                    margin_ratio_str = f"{margin_ratio:.2f}%"
                    if margin_ratio > 50:
                        margin_risk = "\033[91mHIGH RISK\033[0m"
                        margin_ratio_str = f"\033[91m{margin_ratio_str} (High)\033[0m"
                    elif margin_ratio > 25:
                        margin_risk = "\033[93mMODERATE\033[0m"
                        margin_ratio_str = f"\033[93m{margin_ratio_str} (Medium)\033[0m"
                    else:
                        margin_risk = "\033[92mLOW RISK\033[0m"
                        margin_ratio_str = f"\033[92m{margin_ratio_str} (Low)\033[0m"
                    
                    # Broker Requirements
                    logger.info("Broker Requirements:   %s", margin_risk)
                    logger.info(" - Margin Required:    %10.2f %s", margin_required, account_info.currency)
                    logger.info(" - Leverage Used:      1:%-10d", account_info.leverage)
                    
                    # Account Impact
                    logger.info("\n📊 ACCOUNT IMPACT")
                    logger.info(" - Free Margin:      %10.2f %s", free_margin, account_info.currency)
                    logger.info(" - After Trade:      %10.2f %s", margin_after_trade, account_info.currency)
                    logger.info(" - Risk per Trade:    %9.2f%% of balance", risk_percent)
                    logger.info(" - Margin Level:     %10.2f%%", margin_level)
                    
                    # Check margin requirements
                    if margin_required > free_margin:
                        logger.warning("\n⚠️  INSUFFICIENT MARGIN!")
                        logger.warning(f" - Required: {margin_required:.2f} {account_info.currency}")
                        logger.warning(f" - Available: {free_margin:.2f} {account_info.currency}")
                        logger.warning(f" - Deficit: {margin_required - free_margin:.2f} {account_info.currency}")
                        return 0.0, 0.0
                    
                    # Trade Summary
                    logger.info("\n📝 TRADE SUMMARY")
                    logger.info("-" * 80)
                    logger.info(f"{'Symbol:':<15} {symbol}")
                    logger.info(f"{'Direction:':<15} {trade_type}")
                    logger.info(f"{'Entry:':<15} {current_price:.5f}")
                    logger.info(f"{'Stop Loss:':<15} {stop_loss_price:.5f} ({abs(current_price - stop_loss_price)/point/10:.1f} pips)")
                    logger.info(f"{'Take Profit:':<15} {take_profit_price:.5f} ({abs(take_profit_price - current_price)/point/10:.1f} pips)")
                    logger.info(f"{'Position Size:':<15} {position_size:.4f} lots")
                    logger.info(f"{'Risk/Reward:':<15} 1:{risk_reward_ratio:.2f} {rr_visual}")
                    logger.info(f"{'Risk Amount:':<15} {total_risk:.2f} {account_info.currency} ({risk_percent:.2f}% of balance)")
                    logger.info(f"{'Potential Profit:':<15} {potential_profit:.2f} {account_info.currency}")
                    
                    # Final Check
                    logger.info("\n🔍 FINAL CHECKS")
                    logger.info(f" - Sufficient Margin: {'✅' if margin_required <= free_margin else '❌'}")
                    logger.info(f" - Acceptable Risk: {'✅' if risk_percent <= RISK_PERCENT else '❌'}")
                    logger.info(f" - Valid Position Size: {'✅' if position_size > 0 else '❌'}")
                    
            except Exception as e:
                logger.error(f"❌ Error in margin analysis: {str(e)}")
                return 0.0, 0.0
            
            # Trade Summary with Visual Indicators
            logger.info("\n" + "=" * 85)
            logger.info("✅ TRADE VALIDATION COMPLETE")
            logger.info("-" * 85)
            
            # Visual risk-reward indicator
            rr_ratio = TAKE_PROFIT_PIPS / stop_loss_pips
            if rr_ratio >= 2.0:
                rr_emoji = "🚀"
                rr_status = "Excellent"
            elif rr_ratio >= 1.5:
                rr_emoji = "👍"
                rr_status = "Good"
            else:
                rr_emoji = "⚠️ "
                rr_status = "Low"
                
            # Position sizing status
            if position_pct > 5.0:
                size_status = "⚠️  Large"
            elif position_pct > 2.0:
                size_status = "🔍 Moderate"
            else:
                size_status = "✅ Small"
                
            # Margin safety status
            margin_ratio = (margin_required / account_info.balance) * 100
            if margin_ratio > 50:
                margin_status = "⚠️  High"
            elif margin_ratio > 25:
                margin_status = "🔍 Moderate"
            else:
                margin_status = "✅ Low"
            
            # Summary Table
            logger.info("📊 TRADE SUMMARY")
            logger.info("-" * 85)
            logger.info(f"{'Symbol:':<15} {symbol:<15} | {'Position Size:':<15} {position_size:>8.4f} lots")
            logger.info(f"{'Direction:':<15} {trade_type:<15} | {'Risk/Reward:':<15} 1:{rr_ratio:.2f} {rr_emoji} ({rr_status})")
            logger.info(f"{'Entry:':<15} {current_price:<15.5f} | {'Risk Amount:':<15} {total_risk:>8.2f} {account_info.currency} ({risk_percent:.1f}%)")
            logger.info(f"{'Stop Loss:':<15} {stop_loss_price:<15.5f} | {'Potential Profit:':<15} {potential_profit:>8.2f} {account_info.currency}")
            logger.info(f"{'Take Profit:':<15} {take_profit_price:<15.5f} | {'Position Size:':<15} {size_status} ({position_pct:.1f}%)")
            logger.info(f"{'Margin Used:':<15} {margin_required:>8.2f} {account_info.currency} | {'Margin Safety:':<15} {margin_status} ({margin_ratio:.1f}%)")
            
            # Ensure lot size is within broker limits and account margin
            from config import MIN_POSITION_SIZE, MAX_POSITION_SIZE
            min_lot = MIN_POSITION_SIZE
            max_lot = MAX_POSITION_SIZE
            
            # Final Checks
            logger.info("\n🔍 FINAL CHECKS")
            logger.info(f" - Sufficient Margin: {'✅' if margin_required <= account_info.margin_free else '❌'}")
            logger.info(f" - Acceptable Risk: {'✅' if risk_percent <= RISK_PERCENT else '❌'}")
            logger.info(f" - Valid Position Size: {'✅' if 0 < position_size <= max_lot else '❌'}")
            
            logger.info("\n" + "=" * 85 + "\n")
            # Clamp position size to config limits
            position_size = max(min_lot, min(max_lot, position_size))
            # Round to allowed step
            step = 0.001  # Default step for most brokers
            if hasattr(symbol_info, 'volume_step') and symbol_info.volume_step > 0:
                step = symbol_info.volume_step
            position_size = round(position_size / step) * step
            
            # Get current price for reference
            tick = mt5.symbol_info_tick(symbol)  # type: ignore
            current_price = tick.ask if signal > 0 else tick.bid
            
            logger.info(f"Position size: {position_size:.2f} lots | "
                      f"Risk: {adjusted_risk*100:.1f}% | "
                      f"Stop Loss: {stop_loss_pips} pips | "
                      f"Price: {current_price:.2f} | "
                      f"Margin Req: {margin_required * position_size:.2f} {account_info.currency} | "
                      f"Volatility Adj: {volatility_adjustment:.2f}")
                      
            return position_size, adjusted_risk
            
        except Exception as e:
            logger.error(f"Error calculating position size: {str(e)}")
            return 0.0, 0.0

    def open_trade(self, signal):
        """Open a trade based on the signal (BUY/SELL)"""
        if not signal or signal not in ['BUY', 'SELL']:
            return False
            
        symbol_info = mt5.symbol_info(self.symbol)  # type: ignore
        if symbol_info is None:
            logger.error(f"Failed to get symbol info for {self.symbol}")
            return False
            
        # Calculate lot size based on risk
        lot_size = self.calculate_position_size(self.symbol, STOP_LOSS_PIPS)
        
        # Get current price
        if signal == 'BUY':
            price = mt5.symbol_info_tick(self.symbol).ask
            stop_loss = price - STOP_LOSS_PIPS * 10 * self.point
            take_profit = price + TAKE_PROFIT_PIPS * 10 * self.point
            order_type = mt5.ORDER_TYPE_BUY
        else:  # SELL
            price = mt5.symbol_info_tick(self.symbol).bid
            stop_loss = price + STOP_LOSS_PIPS * 10 * self.point
            take_profit = price - TAKE_PROFIT_PIPS * 10 * self.point
            order_type = mt5.ORDER_TYPE_SELL
            
        # Prepare the trade request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lot_size,
            "type": order_type,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 20,
            "magic": self.magic,
            "comment": f"AutoTrade {signal}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send the trade request
        result = mt5.order_send(request)  # type: ignore
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Failed to send {signal} order: {result.comment}")
            return False
            
        logger.info(f"{signal} order executed: {lot_size} lots at {price}")
        if VERBOSE:
            logger.info(f"Stop Loss: {stop_loss}, Take Profit: {take_profit}")
        return True

    def log_performance_metrics(self):
        """Log performance metrics"""
        metrics = self.performance_metrics
        if metrics['trades'] == 0:
            return
            
        logger.info("\n📊 TRADING PERFORMANCE METRICS")
        logger.info("=" * 85)
        logger.info(f"Total Trades:       {metrics['trades']}")
        logger.info(f"Errors:             {metrics['errors']} ({metrics['errors']/metrics['trades']*100:.1f}%)")
        logger.info(f"Avg Execution Time: {metrics['avg_execution_time']*1000:.2f}ms")
        logger.info(f"Last Trade:         {datetime.fromtimestamp(metrics['last_trade_time']).strftime('%Y-%m-%d %H:%M:%S') if metrics['last_trade_time'] > 0 else 'Never'}")
        
        # Connection health
        if hasattr(self, 'connection'):
            logger.info(f"Connection Errors:  {self.connection.connection_errors}")
        
        logger.info("=" * 85 + "\n")
    
    def close_all_positions(self):
        """Close all open positions for the symbol"""
        try:
            # Check connection first
            if not self.connection.check_connection():
                logger.error("Cannot close positions: Connection check failed")
                return False
                
            positions = mt5.positions_get(symbol=self.symbol)  # type: ignore
            if positions is None:
                error = mt5.last_error()  # type: ignore
                if error[0] != 1:  # 1 means no positions found, which is not an error
                    logger.error(f"Error getting positions: {error}")
                    return False
                logger.info(f"No open positions for {self.symbol}")
                return True
                
            # Close each position
            for position in positions:
                # Get current price
                tick = mt5.symbol_info_tick(self.symbol)  # type: ignore
                if tick is None:
                    logger.error("Failed to get tick data")
                    return False
                    
                # Determine order type and price
                if position.type == mt5.POSITION_TYPE_BUY:
                    order_type = mt5.ORDER_TYPE_SELL
                    price = tick.bid
                else:
                    order_type = mt5.ORDER_TYPE_BUY
                    price = tick.ask
                
                max_retries = 3
                for attempt in range(max_retries):
                    # Prepare close request
                    close_request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": self.symbol,
                        "volume": position.volume,
                        "type": order_type,
                        "position": position.ticket,
                        "price": price,
                        "deviation": 20,
                        "magic": self.magic,
                        "comment": "Close position",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_FOK,
                    }
                    
                    # Send close order
                    result = mt5.order_send(close_request)  # type: ignore
                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                        logger.info(f"Successfully closed position {position.ticket} at {price}")
                        break
                    elif result.retcode == 10004:  # Requote
                        logger.warning(f"Requote received on attempt {attempt+1}. Refreshing price...")
                        time.sleep(0.5)
                        # Refresh price
                        tick = mt5.symbol_info_tick(self.symbol)  # type: ignore
                        if tick is None:
                            logger.error("Failed to refresh tick data")
                            return False
                        price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
                    else:
                        logger.error(f"Failed to close position {position.ticket}: {result.comment}")
                        if attempt == max_retries - 1:  # Last attempt
                            logger.error(f"Failed to close position {position.ticket} after {max_retries} attempts")
                            return False
                        
                        # Wait before retry
                        time.sleep(1)
            
            return True
            
        except Exception as e:
            logger.error(f"Error in close_all_positions: {str(e)}")
            return False
