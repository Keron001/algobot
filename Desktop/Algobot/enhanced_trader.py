#!/usr/bin/env python3
"""
Enhanced Trading Bot with 30% Stop-Loss and Improved Profitability
"""

import time
import threading
import json
import os
from datetime import datetime, timedelta
from typing import Optional
import signal
import sys
import traceback
from flask import Flask, request, jsonify

# Import our modules
from config import (
    SYMBOLS, TIMEFRAMES, DEFAULT_LOT_SIZE as LOT_SIZE, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT,
    MAX_DAILY_LOSS, MAX_POSITIONS, PAPER_TRADING, DEFAULT_STRATEGY_PARAMS, STRATEGY_SELECTION, ATR_MULTIPLIER, ATR_PERIOD
)
from strategy import get_strategy_registry
from risk.risk_manager import RiskManager
from utils.logger import get_logger
from data.fetch_mt5 import fetch_mt5_data, get_account_info, login_mt5
import execution.mt5_executor as mt5_executor
from utils.news_filter import NewsFilter
from utils.analytics import TradeAnalytics
from utils.alerts import send_email_alert, send_telegram_alert

logger = get_logger("EnhancedTrader")

API_KEY = os.environ.get('API_KEY', 'changeme123')

class EnhancedTrader:
    def __init__(
        self,
        user_id: Optional[int] = None,
        mt5_login: Optional[str] = None,
        mt5_password: Optional[str] = None,
        mt5_server: Optional[str] = None,
        trading_hours: Optional[dict] = None,
        max_daily_loss: float = MAX_DAILY_LOSS,
        max_positions: int = MAX_POSITIONS,
        paper_trading: bool = PAPER_TRADING
    ):
        """
        Initialize the EnhancedTrader.
        Args:
            trading_hours (Optional[dict]): Trading hours config.
            max_daily_loss (float): Max daily loss as fraction of balance.
            max_positions (int): Max open positions.
            paper_trading (bool): If True, do not execute real trades.
        """
        self.user_id = user_id
        self.mt5_login = mt5_login
        self.mt5_password = mt5_password
        self.mt5_server = mt5_server
        if trading_hours is None:
            self.trading_hours = {
                'start': '00:00',  # 24-hour trading for XAUUSD
                'end': '21:59'
            }
        else:
            self.trading_hours = trading_hours
        
        self.max_daily_loss = max_daily_loss
        self.max_positions = max_positions
        self.paper_trading = paper_trading
        
        # Trading state
        self.is_running = False
        self.is_trading = False
        self.daily_pnl = 0.0
        self.emergency_stop = False
        
        # Performance tracking
        self.daily_stats = {
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0
        }
        
        # Initialize components with 30% stop-loss
        self.risk_manager = RiskManager(
            max_risk_per_trade=0.02,
            max_portfolio_risk=0.06,
            max_positions=max_positions,
            stop_loss_pct=STOP_LOSS_PERCENT,  # 30% stop-loss
            take_profit_pct=TAKE_PROFIT_PERCENT  # 60% take-profit
        )
        
        # Initialize components
        self.news_filter = NewsFilter()
        self.analytics = TradeAnalytics()
        
        # Trading strategies and positions
        self.strategies = {}
        self.active_positions = {}
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("Enhanced Trading Bot Initialized")
        logger.info(f"   Stop-Loss: {STOP_LOSS_PERCENT*100}%")
        logger.info(f"   Take-Profit: {TAKE_PROFIT_PERCENT*100}%")
        logger.info(f"   Trading Hours: {self.trading_hours['start']} - {self.trading_hours['end']}")
        logger.info(f"   Max Daily Loss: {self.max_daily_loss:.1%}")
        logger.info(f"   Max Positions: {max_positions}")
        logger.info(f"   Paper Trading: {self.paper_trading}")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Stopping Enhanced Trading System...")
        self.stop()
        sys.exit(0)
    
    def start(self):
        """Start the enhanced trading system"""
        if self.is_running:
            logger.warning("Enhanced trader is already running")
            return
        
        # Test MT5 connection
        if not login_mt5():
            logger.error("Failed to connect to MT5")
            return False
        
        logger.info("Starting Enhanced Trading System...")
        self.is_running = True
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        # Start trading loop
        self.trading_loop()
    
    def stop(self):
        """Enhanced stop method with analytics save and alerting."""
        logger.info("Stopping Enhanced Trading System...")
        self.is_running = False
        self.is_trading = False
        self.emergency_stop = True
        self.close_all_positions()
        self.save_daily_stats()
        self.analytics.save_trade_history()
        self.analytics.export_to_csv()
        self.analytics.log_performance_summary()
        logger.info("Enhanced Trading System stopped")
        # ALERT: Send system stop alert
        send_email_alert("Bot Stopped", "The Enhanced Trading System has been stopped.")
        send_telegram_alert("The Enhanced Trading System has been stopped.")
        self.write_status_file()  # Update dashboard status on stop
        self.write_trade_history_file()
        self.write_analytics_file()
    
    def trading_loop(self):
        """Main trading loop with enhanced error handling and alerting."""
        logger.info("Starting enhanced trading loop...")
        
        while self.is_running and not self.emergency_stop:
            try:
                # Check if we should be trading
                if self.should_be_trading():
                    if not self.is_trading:
                        self.start_trading_session()
                    
                    # Process each symbol
                    for symbol in SYMBOLS:
                        if not self.is_running:
                            break
                        self.process_symbol(symbol)
                else:
                    if self.is_trading:
                        self.stop_trading_session()
                
                self.write_status_file()  # Update dashboard status
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                # ALERT: Send error alert
                send_email_alert("Error in Trading Loop", str(e))
                send_telegram_alert(f"Error in Trading Loop: {e}")
                self.write_status_file()  # Update dashboard status on error
                time.sleep(30)
    
    def should_be_trading(self) -> bool:
        """Check if we should be trading"""
        # Check emergency stop
        if self.emergency_stop:
            return False
        
        # Check daily loss limit
        if self.daily_pnl <= -self.max_daily_loss:
            logger.warning(f"Daily loss limit reached: {self.daily_pnl:.2%}")
            return False
        
        # Check trading hours
        current_time = datetime.now().time()
        start_time = datetime.strptime(self.trading_hours['start'], '%H:%M').time()
        end_time = datetime.strptime(self.trading_hours['end'], '%H:%M').time()
        
        return start_time <= current_time <= end_time
    
    def start_trading_session(self):
        """Start a trading session"""
        logger.info("Starting Enhanced Trading Session...")
        self.is_trading = True
        self.initialize_strategies()
    
    def stop_trading_session(self):
        """Stop the current trading session"""
        logger.info("Stopping Trading Session...")
        self.is_trading = False
        self.close_all_positions()
        self.save_daily_stats()
    
    def initialize_strategies(self) -> None:
        """
        Initialize trading strategies for each symbol using default parameters.
        """
        logger.info("Initializing enhanced trading strategies...")
        registry = get_strategy_registry()
        for symbol in SYMBOLS:
            try:
                strategy_name = STRATEGY_SELECTION.get(symbol, "MovingAverageStrategy")
                strategy_cls = registry.get(strategy_name)
                if not strategy_cls:
                    logger.warning(f"Strategy '{strategy_name}' not found, using MovingAverageStrategy.")
                    from strategy.moving_average import MovingAverageStrategy
                    strategy_cls = MovingAverageStrategy
                strategy_params = DEFAULT_STRATEGY_PARAMS.copy()
                self.strategies[symbol] = {
                    'strategy': strategy_cls,
                    'params': strategy_params,
                    'last_signal': None
                }
                logger.info(f"   {symbol}: {strategy_cls.__name__} initialized")
            except Exception as e:
                logger.error(f"Error initializing strategy for {symbol}: {e}")
    
    def process_symbol(self, symbol: str):
        """Process a single symbol with enhanced error handling"""
        try:
            # Fetch market data
            data = fetch_mt5_data(symbol, TIMEFRAMES[0], n_bars=200, login=self.mt5_login, password=self.mt5_password, server=self.mt5_server)
            if data is None or data.empty:
                logger.warning(f"No data received for {symbol}")
                return
            
            # Get current market price
            current_price = data['close'].iloc[-1]
            
            # Check existing positions for stop-loss/take-profit
            self.check_position_exits(symbol, current_price)
            
            # Check if we can open new positions
            if not self.risk_manager.can_open_position(symbol):
                logger.info(f"Cannot open position for {symbol} - risk limits reached")
                return
            
            # Generate trading signals
            strategy_cls = self.strategies[symbol]['strategy']
            strategy = strategy_cls(data, **self.strategies[symbol]['params'])
            signals = strategy.generate_signals()
            
            if not signals.empty:
                latest = signals.iloc[-1]
                logger.info(f"DEBUG: {symbol} | Short_MA={latest.get('Short_MA')} | Long_MA={latest.get('Long_MA')} | RSI={latest.get('RSI')} | Signal={latest.get('Signal')} | Position={latest.get('Position')}")
                if not self.risk_manager.can_open_position(symbol):
                    logger.info(f"DEBUG: Risk manager blocked opening position for {symbol}")
                else:
                    logger.info(f"DEBUG: Risk manager allows opening position for {symbol}")
                
                if latest['Position'] == 1:  # Buy signal
                    logger.info(f"BUY signal for {symbol} at {current_price}")
                    if not self.paper_trading:
                        success = self.execute_buy_order(symbol, current_price, data=data)
                        if success:
                            logger.info(f"Buy order successfully executed for {symbol}")
                        else:
                            logger.error(f"Buy order failed for {symbol}")
                    else:
                        logger.info(f"Paper trading: Would buy {symbol} at {current_price}")
                        # Simulate trade in paper trading mode
                        trade = {
                            'symbol': symbol,
                            'side': 'buy',
                            'price': current_price,
                            'lot_size': self.risk_manager.calculate_position_size(current_price, self.risk_manager.calculate_stop_loss(current_price, 'buy')),
                            'timestamp': str(datetime.now()),
                            'mode': 'paper'
                        }
                        self.analytics.trades.append(trade)
                        self.write_trade_history_file()

                elif latest['Position'] == -1:  # Sell signal
                    logger.info(f"SELL signal for {symbol} at {current_price}")
                    if not self.paper_trading:
                        success = self.execute_sell_order(symbol, current_price, data=data)
                        if success:
                            logger.info(f"Sell order successfully executed for {symbol}")
                        else:
                            logger.error(f"Sell order failed for {symbol}")
                    else:
                        logger.info(f"Paper trading: Would sell {symbol} at {current_price}")
                        # Simulate trade in paper trading mode
                        trade = {
                            'symbol': symbol,
                            'side': 'sell',
                            'price': current_price,
                            'lot_size': self.risk_manager.calculate_position_size(current_price, self.risk_manager.calculate_stop_loss(current_price, 'sell')),
                            'timestamp': str(datetime.now()),
                            'mode': 'paper'
                        }
                        self.analytics.trades.append(trade)
                        self.write_trade_history_file()
                        
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def check_position_exits(self, symbol, current_price):
        """Check if positions should be closed due to stop-loss or take-profit"""
        try:
            # Check risk manager for position exits
            exit_reason = self.risk_manager.check_stop_loss_take_profit(symbol, current_price)
            
            if exit_reason:
                logger.info(f"Triggering {exit_reason.upper()} for {symbol} at {current_price}")
                
                # Close position via MT5
                if not self.paper_trading:
                    positions = mt5_executor.get_open_positions()
                    for pos in positions:
                        if pos.symbol == symbol:
                            entry_price = pos.price_open
                            lot_size = pos.volume
                            direction = 'buy' if pos.type == 0 else 'sell'
                            pnl = (current_price - entry_price) * lot_size * 100000 if direction == 'buy' else (entry_price - current_price) * lot_size * 100000
                            duration = None  # Could be calculated if entry time is tracked
                            if mt5_executor.close_position(pos.ticket):
                                logger.info(f"Position closed for {symbol}")
                                self.analytics.log_trade_exit(symbol, current_price, pnl, reason=exit_reason, duration=duration)
                                self.risk_manager.remove_position(symbol)
                            else:
                                logger.error(f"Failed to close position for {symbol}")
                            break
                            
        except Exception as e:
            logger.error(f"Error checking position exits for {symbol}: {e}")
    
    def execute_buy_order(self, symbol, price, data=None):
        """Execute buy order with flexible stop-loss and take-profit, with alerting."""
        try:
            import MetaTrader5 as mt5
            stop_loss = self.risk_manager.calculate_stop_loss(price, 'buy', data=data)
            take_profit = self.risk_manager.calculate_take_profit(price, 'buy', data=data)
            lot_size = self.risk_manager.calculate_position_size(price, stop_loss)
            # Calculate initial trailing stop
            trailing_stop = None
            entry_reason = "Buy signal: MA crossover + filters"  # You can make this more detailed if needed
            indicators = {}
            if data is not None:
                from utils.indicators import calculate_atr
                import pandas as pd
                atr = calculate_atr(data, ATR_PERIOD)
                if isinstance(atr, pd.Series):
                    atr_val = atr.iloc[-1]
                else:
                    atr_val = atr[-1]
                trailing_stop = price - ATR_MULTIPLIER * atr_val
                indicators['ATR'] = atr_val
            # Log trade entry
            self.analytics.log_trade_entry(symbol, 'buy', price, lot_size, stop_loss, take_profit, indicators=indicators, reason=entry_reason)
            result = mt5_executor.send_order(symbol, lot_size, mt5.ORDER_TYPE_BUY, price, sl=stop_loss, tp=take_profit)
            if result:
                logger.info(f"Buy order executed: {symbol} at {price}, SL: {stop_loss}, TP: {take_profit}, Lot: {lot_size}")
                self.risk_manager.add_position(symbol, 'buy', price, lot_size, stop_loss, take_profit, trailing_stop)
                # ALERT: Send trade execution alert
                msg = f"BUY EXECUTED: {symbol} at {price}\nSL: {stop_loss}, TP: {take_profit}, Lot: {lot_size}"
                send_email_alert(f"Trade Executed: BUY {symbol}", msg)
                send_telegram_alert(msg)
                self.write_trade_history_file()
                self.write_analytics_file()
                return True
            else:
                logger.error(f"Failed to execute buy order for {symbol}")
                # ALERT: Send error alert
                send_email_alert(f"Trade Error: BUY {symbol}", f"Failed to execute buy order for {symbol} at {price}")
                send_telegram_alert(f"Trade Error: Failed BUY {symbol} at {price}")
                return False
        except Exception as e:
            logger.error(f"Error executing buy order for {symbol}: {e}")
            # ALERT: Send exception alert
            send_email_alert(f"Exception: BUY {symbol}", str(e))
            send_telegram_alert(f"Exception: BUY {symbol}: {e}")
            return False
    
    def execute_sell_order(self, symbol, price, data=None):
        """Execute sell order with flexible stop-loss and take-profit, with alerting."""
        try:
            import MetaTrader5 as mt5
            stop_loss = self.risk_manager.calculate_stop_loss(price, 'sell', data=data)
            take_profit = self.risk_manager.calculate_take_profit(price, 'sell', data=data)
            lot_size = self.risk_manager.calculate_position_size(price, stop_loss)
            # Calculate initial trailing stop
            trailing_stop = None
            entry_reason = "Sell signal: MA crossover + filters"  # You can make this more detailed if needed
            indicators = {}
            if data is not None:
                from utils.indicators import calculate_atr
                import pandas as pd
                atr = calculate_atr(data, ATR_PERIOD)
                if isinstance(atr, pd.Series):
                    atr_val = atr.iloc[-1]
                else:
                    atr_val = atr[-1]
                trailing_stop = price + ATR_MULTIPLIER * atr_val
                indicators['ATR'] = atr_val
            # Log trade entry
            self.analytics.log_trade_entry(symbol, 'sell', price, lot_size, stop_loss, take_profit, indicators=indicators, reason=entry_reason)
            result = mt5_executor.send_order(symbol, lot_size, mt5.ORDER_TYPE_SELL, price, sl=stop_loss, tp=take_profit)
            if result:
                logger.info(f"Sell order executed: {symbol} at {price}, SL: {stop_loss}, TP: {take_profit}, Lot: {lot_size}")
                self.risk_manager.add_position(symbol, 'sell', price, lot_size, stop_loss, take_profit, trailing_stop)
                # ALERT: Send trade execution alert
                msg = f"SELL EXECUTED: {symbol} at {price}\nSL: {stop_loss}, TP: {take_profit}, Lot: {lot_size}"
                send_email_alert(f"Trade Executed: SELL {symbol}", msg)
                send_telegram_alert(msg)
                self.write_trade_history_file()
                self.write_analytics_file()
                return True
            else:
                logger.error(f"Failed to execute sell order for {symbol}")
                # ALERT: Send error alert
                send_email_alert(f"Trade Error: SELL {symbol}", f"Failed to execute sell order for {symbol} at {price}")
                send_telegram_alert(f"Trade Error: Failed SELL {symbol} at {price}")
                return False
        except Exception as e:
            logger.error(f"Error executing sell order for {symbol}: {e}")
            # ALERT: Send exception alert
            send_email_alert(f"Exception: SELL {symbol}", str(e))
            send_telegram_alert(f"Exception: SELL {symbol}: {e}")
            return False
    
    def close_all_positions(self):
        """Close all open positions"""
        try:
            if not self.paper_trading:
                positions = mt5_executor.get_open_positions()
                for pos in positions:
                    if mt5_executor.close_position(pos.ticket):
                        logger.info(f"Closed position: {pos.symbol}")
                        self.risk_manager.remove_position(pos.symbol)
                    else:
                        logger.error(f"Failed to close position: {pos.symbol}")
        except Exception as e:
            logger.error(f"Error closing positions: {e}")
    
    def monitoring_loop(self):
        """Monitor trading performance and system health"""
        while self.is_running:
            try:
                # Update account balance
                account_info = get_account_info(login=self.mt5_login, password=self.mt5_password, server=self.mt5_server)
                if account_info:
                    self.risk_manager.update_account_balance(account_info['balance'])
                
                # Log performance summary
                if self.is_trading:
                    logger.info(f"Trading Status: Active | Daily PnL: {self.daily_pnl:.2f}")
                    logger.info(f"Open Positions: {len(self.risk_manager.open_positions)}")
                
                time.sleep(300)  # Update every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)
    
    def save_daily_stats(self):
        """Save daily trading statistics"""
        try:
            stats = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'trades': self.daily_stats['trades'],
                'wins': self.daily_stats['wins'],
                'losses': self.daily_stats['losses'],
                'total_pnl': self.daily_stats['total_pnl'],
                'win_rate': self.daily_stats['wins'] / max(self.daily_stats['trades'], 1)
            }
            
            filename = f"daily_stats_{datetime.now().strftime('%Y%m%d')}.json"
            with open(filename, 'w') as f:
                json.dump(stats, f, indent=2)
            
            logger.info(f"Daily stats saved to {filename}")
            
        except Exception as e:
            logger.error(f"Error saving daily stats: {e}")
    
    def get_status(self) -> dict:
        """Get current trading status"""
        return {
            'is_running': self.is_running,
            'is_trading': self.is_trading,
            'daily_pnl': self.daily_pnl,
            'open_positions': len(self.risk_manager.open_positions),
            'max_positions': self.max_positions,
            'paper_trading': self.paper_trading,
            'stop_loss_percent': STOP_LOSS_PERCENT * 100,
            'take_profit_percent': TAKE_PROFIT_PERCENT * 100
        }

    def write_status_file(self) -> None:
        """Write current status to bot_status.json for dashboard consumption."""
        try:
            with open('bot_status.json', 'w') as f:
                json.dump(self.get_status(), f, indent=2)
        except Exception as e:
            logger.error(f"Error writing status file: {e}")

    def write_trade_history_file(self) -> None:
        """Write recent trade history to trade_history.json for dashboard consumption."""
        try:
            with open('trade_history.json', 'w') as f:
                json.dump(self.analytics.trades, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error writing trade history file: {e}")

    def write_analytics_file(self) -> None:
        """Write analytics summary to analytics.json for dashboard consumption."""
        try:
            if hasattr(self.analytics, 'get_performance_summary'):
                summary = self.analytics.get_performance_summary()
                with open('analytics.json', 'w') as f:
                    json.dump(summary, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error writing analytics file: {e}")

    def pause(self):
        """Pause trading (no new trades will be opened)."""
        self.is_trading = False
        logger.info("Trading paused by API.")
        return True

    def resume(self):
        """Resume trading (allow new trades)."""
        self.is_trading = True
        logger.info("Trading resumed by API.")
        return True

    def periodic_trailing_stop_update(self):
        """Periodically update trailing stops for all open positions."""
        import time
        def get_latest_data(symbol):
            # NOTE: self.data must be a dict of DataFrames keyed by symbol.
            if hasattr(self, 'data') and isinstance(self.data, dict) and symbol in self.data:  # type: ignore[attr-defined]
                return self.data[symbol]  # type: ignore[attr-defined]
            return None
        def update_broker_sl(symbol, new_sl):
            mt5_executor.update_stop_loss(symbol, new_sl)
        while self.is_running:
            self.risk_manager.update_trailing_stops(get_latest_data, update_broker_sl)
            time.sleep(60)  # Check every minute

# --- Flask API for manual controls ---
app = Flask(__name__)
trader_instance = None

def require_api_key():
    key = request.headers.get('X-API-KEY')
    if key != API_KEY:
        return jsonify({'error': 'Unauthorized'}), 401

@app.route('/api/pause', methods=['POST'])
def api_pause():
    auth = require_api_key()
    if auth:
        return auth
    global trader_instance
    if trader_instance:
        trader_instance.pause()
        return jsonify({'status': 'paused'})
    return jsonify({'error': 'No trader instance'}), 500

@app.route('/api/resume', methods=['POST'])
def api_resume():
    auth = require_api_key()
    if auth:
        return auth
    global trader_instance
    if trader_instance:
        trader_instance.resume()
        return jsonify({'status': 'resumed'})
    return jsonify({'error': 'No trader instance'}), 500

@app.route('/api/stop', methods=['POST'])
def api_stop():
    auth = require_api_key()
    if auth:
        return auth
    global trader_instance
    if trader_instance:
        trader_instance.stop()
        return jsonify({'status': 'stopped'})
    return jsonify({'error': 'No trader instance'}), 500

def main() -> None:
    """
    Main function to run the enhanced trading bot and Flask API.
    """
    global trader_instance
    try:
        trader_instance = EnhancedTrader(
            paper_trading=PAPER_TRADING,  # Use config value
            max_positions=MAX_POSITIONS
        )
        # Start the trading system in a background thread
        import threading
        trading_thread = threading.Thread(target=trader_instance.start, daemon=False)
        trading_thread.start()
        # Start Flask API for manual controls
        app.run(port=8000, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        if trader_instance:
            trader_instance.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if trader_instance:
            trader_instance.stop()

if __name__ == "__main__":
    main() 