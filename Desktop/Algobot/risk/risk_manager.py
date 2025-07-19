import numpy as np
import pandas as pd
from utils.logger import get_logger
from config import DEFAULT_LOT_SIZE as LOT_SIZE, SLTP_MODE, FIXED_STOP_LOSS_PIPS, FIXED_TAKE_PROFIT_PIPS, ATR_STOP_LOSS_MULTIPLIER, ATR_TAKE_PROFIT_MULTIPLIER, ATR_PERIOD, ATR_MULTIPLIER
from datetime import datetime

logger = get_logger("RiskManager")

class RiskManager:
    def __init__(self, 
                 account_balance=10000,
                 max_risk_per_trade=0.02,  # 2% risk per trade
                 max_portfolio_risk=0.06,  # 6% total portfolio risk
                 stop_loss_pct=0.30,       # 30% stop loss as requested
                 take_profit_pct=0.60,     # 60% take profit (2:1 risk-reward)
                 max_positions=10,          # Maximum concurrent positions (increased to 10)
                 lot_size=LOT_SIZE,
                 max_drawdown_per_symbol=0.05,  # 5% max drawdown per symbol
                 max_drawdown_per_session=0.10,  # 10% max drawdown per session
                 circuit_breaker_losses=5):  # Stop after 5 consecutive losses
        
        self.account_balance = account_balance
        self.max_risk_per_trade = max_risk_per_trade
        self.max_portfolio_risk = max_portfolio_risk
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_positions = max_positions
        self.lot_size = lot_size
        self.max_drawdown_per_symbol = max_drawdown_per_symbol
        self.max_drawdown_per_session = max_drawdown_per_session
        self.circuit_breaker_losses = circuit_breaker_losses
        self.open_positions = []
        self.trade_history = []
        self.session_start_balance = account_balance
        self.consecutive_losses = 0
        self.circuit_breaker_triggered = False
        
    def reset_session(self):
        """Reset session statistics."""
        self.session_start_balance = self.account_balance
        self.consecutive_losses = 0
        self.circuit_breaker_triggered = False
        logger.info("Session reset - circuit breaker cleared")
        
    def check_circuit_breaker(self):
        """Check if circuit breaker should be triggered."""
        if self.consecutive_losses >= self.circuit_breaker_losses:
            self.circuit_breaker_triggered = True
            logger.warning(f"🚨 CIRCUIT BREAKER TRIGGERED! {self.consecutive_losses} consecutive losses")
            return False
        return True
        
    def check_drawdown_limits(self, symbol):
        """Check if drawdown limits are exceeded."""
        # Check session drawdown
        session_drawdown = (self.session_start_balance - self.account_balance) / self.session_start_balance
        if session_drawdown > self.max_drawdown_per_session:
            logger.warning(f"Session drawdown limit exceeded: {session_drawdown:.2%}")
            return False
            
        # Check symbol-specific drawdown
        symbol_positions = [pos for pos in self.open_positions if pos['symbol'] == symbol]
        if symbol_positions:
            symbol_pnl = sum(pos.get('unrealized_pnl', 0) for pos in symbol_positions)
            symbol_drawdown = abs(symbol_pnl) / self.account_balance
            if symbol_drawdown > self.max_drawdown_per_symbol:
                logger.warning(f"Symbol drawdown limit exceeded for {symbol}: {symbol_drawdown:.2%}")
                return False
                
        return True
        
    def record_trade_result(self, symbol, pnl, win_loss):
        """Record trade result for circuit breaker logic."""
        self.trade_history.append({
            'symbol': symbol,
            'pnl': pnl,
            'win_loss': win_loss,
            'timestamp': datetime.now()
        })
        
        if win_loss == 'loss':
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
            
        logger.info(f"Trade recorded: {symbol} {win_loss} (PnL: ${pnl:.2f}, Consecutive losses: {self.consecutive_losses})")
        
    def calculate_position_size(self, entry_price, stop_loss_price, symbol_info=None, atr=None, risk_percent=None):
        """Calculate optimal position size based on risk management rules, ATR, and live account balance."""
        try:
            lot_size = 0.01
            logger.info(f"[FIXED] Using fixed lot size: {lot_size}")
            return lot_size
        except Exception as e:
            logger.error(f"Error in dynamic position sizing: {e}")
            return self.lot_size
    
    def calculate_stop_loss(self, entry_price, direction, data=None):
        """Calculate stop loss based on config mode: fixed pips or ATR."""
        if SLTP_MODE == 'fixed':
            pip_value = 0.1  # For XAUUSD, 1 pip = 0.1
            sl_pips = FIXED_STOP_LOSS_PIPS * pip_value
            if direction == 'buy':
                stop_loss = entry_price - sl_pips
            else:
                stop_loss = entry_price + sl_pips
            logger.info(f"Calculated fixed SL for {direction} at {entry_price}: {stop_loss}")
            return stop_loss
        elif SLTP_MODE == 'atr' and data is not None:
            from utils.indicators import calculate_atr
            atr_series = calculate_atr(data, ATR_PERIOD)
            if isinstance(atr_series, pd.Series):
                atr = atr_series.iloc[-1]
            else:
                atr = atr_series[-1]
            sl_atr = ATR_STOP_LOSS_MULTIPLIER * atr
            if direction == 'buy':
                stop_loss = entry_price - sl_atr
            else:
                stop_loss = entry_price + sl_atr
            logger.info(f"Calculated ATR-based SL for {direction} at {entry_price}: {stop_loss}")
            return stop_loss
        else:
            # fallback to percent
            if direction == 'buy':
                stop_loss = entry_price * (1 - self.stop_loss_pct)
            else:
                stop_loss = entry_price * (1 + self.stop_loss_pct)
            logger.info(f"Calculated fallback percent SL for {direction} at {entry_price}: {stop_loss}")
            return stop_loss

    def calculate_take_profit(self, entry_price, direction, data=None):
        """Calculate take profit based on config mode: fixed pips or ATR."""
        if SLTP_MODE == 'fixed':
            pip_value = 0.1  # For XAUUSD, 1 pip = 0.1
            tp_pips = FIXED_TAKE_PROFIT_PIPS * pip_value
            if direction == 'buy':
                take_profit = entry_price + tp_pips
            else:
                take_profit = entry_price - tp_pips
            logger.info(f"Calculated fixed TP for {direction} at {entry_price}: {take_profit}")
            return take_profit
        elif SLTP_MODE == 'atr' and data is not None:
            from utils.indicators import calculate_atr
            atr_series = calculate_atr(data, ATR_PERIOD)
            if isinstance(atr_series, pd.Series):
                atr = atr_series.iloc[-1]
            else:
                atr = atr_series[-1]
            tp_atr = ATR_TAKE_PROFIT_MULTIPLIER * atr
            if direction == 'buy':
                take_profit = entry_price + tp_atr
            else:
                take_profit = entry_price - tp_atr
            logger.info(f"Calculated ATR-based TP for {direction} at {entry_price}: {take_profit}")
            return take_profit
        else:
            # fallback to percent
            if direction == 'buy':
                take_profit = entry_price * (1 + self.take_profit_pct)
            else:
                take_profit = entry_price * (1 - self.take_profit_pct)
            logger.info(f"Calculated fallback percent TP for {direction} at {entry_price}: {take_profit}")
            return take_profit
    
    def can_open_position(self, symbol):
        """Check if we can open a new position based on risk rules."""
        # Check circuit breaker
        if not self.check_circuit_breaker():
            logger.warning("Cannot open position: Circuit breaker active")
            return False
            
        # Check drawdown limits
        if not self.check_drawdown_limits(symbol):
            logger.warning("Cannot open position: Drawdown limits exceeded")
            return False
            
        # Check maximum positions limit
        if len(self.open_positions) >= self.max_positions:
            logger.warning(f"Cannot open position: Maximum positions ({self.max_positions}) reached")
            return False
        
        # Allow multiple positions per symbol (up to max_positions)
        
        # Check portfolio risk limit
        current_portfolio_risk = self.calculate_portfolio_risk()
        if current_portfolio_risk >= self.max_portfolio_risk:
            logger.warning(f"Cannot open position: Portfolio risk limit ({self.max_portfolio_risk:.2%}) reached")
            return False
        
        return True
    
    def calculate_portfolio_risk(self):
        """Calculate current portfolio risk"""
        if not self.open_positions:
            return 0.0
        
        total_risk = 0.0
        for position in self.open_positions:
            # Calculate unrealized P&L as percentage of account
            unrealized_pnl = position.get('unrealized_pnl', 0)
            risk_pct = abs(unrealized_pnl) / self.account_balance
            total_risk += risk_pct
        
        return total_risk
    
    def add_position(self, symbol, direction, entry_price, lot_size, stop_loss, take_profit, trailing_stop=None):
        """Add a new position to tracking, with entry time and optional trailing stop"""
        position = {
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'lot_size': lot_size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'trailing_stop': trailing_stop,  # NEW: track trailing stop
            'entry_time': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),  # Set entry time
            'unrealized_pnl': 0.0,
            'pnl': 0.0,
        }
        self.open_positions.append(position)
        logger.info(f"Added position: {symbol} {direction} {lot_size} lots at {entry_price} (Trailing Stop: {trailing_stop}) Entry Time: {position['entry_time']}")

    def update_trailing_stops(self, get_latest_data, update_broker_sl):
        """Recalculate and update trailing stops for all open positions.
        get_latest_data(symbol) should return a DataFrame with latest price data.
        update_broker_sl(symbol, new_sl) should update SL on broker.
        """
        from utils.indicators import calculate_atr
        for position in self.open_positions:
            symbol = position['symbol']
            direction = position['direction']
            data = get_latest_data(symbol)
            if data is None or len(data) < 2:
                continue
            price = data['close'].iloc[-1]
            atr = calculate_atr(data, ATR_PERIOD)
            if isinstance(atr, pd.Series):
                atr_val = atr.iloc[-1]
            else:
                atr_val = atr[-1]
            # Calculate new trailing stop
            if direction == 'buy':
                new_trailing_stop = price - ATR_MULTIPLIER * atr_val
                # Only move SL up (never down)
                if new_trailing_stop > position['stop_loss']:
                    logger.info(f"Updating trailing stop for {symbol} (buy): {position['stop_loss']} -> {new_trailing_stop}")
                    position['stop_loss'] = new_trailing_stop
                    position['trailing_stop'] = new_trailing_stop
                    update_broker_sl(symbol, new_trailing_stop)
            else:
                new_trailing_stop = price + ATR_MULTIPLIER * atr_val
                # Only move SL down (never up)
                if new_trailing_stop < position['stop_loss']:
                    logger.info(f"Updating trailing stop for {symbol} (sell): {position['stop_loss']} -> {new_trailing_stop}")
                    position['stop_loss'] = new_trailing_stop
                    position['trailing_stop'] = new_trailing_stop
                    update_broker_sl(symbol, new_trailing_stop)
    
    def remove_position(self, symbol, direction=None):
        """Remove a position from tracking by symbol and (optionally) direction"""
        before = len(self.open_positions)
        if direction:
            self.open_positions = [pos for pos in self.open_positions if not (pos['symbol'] == symbol and pos['direction'] == direction)]
        else:
            self.open_positions = [pos for pos in self.open_positions if pos['symbol'] != symbol]
        after = len(self.open_positions)
        logger.info(f"Removed position: {symbol} {direction if direction else ''} (before: {before}, after: {after})")
    
    def update_position_pnl(self, symbol, current_price):
        """Update unrealized and realized P&L for a position"""
        for position in self.open_positions:
            if position['symbol'] == symbol:
                if position['direction'] == 'buy':
                    pnl = (current_price - position['entry_price']) * position['lot_size'] * 100000
                else:
                    pnl = (position['entry_price'] - current_price) * position['lot_size'] * 100000
                position['unrealized_pnl'] = pnl
                position['pnl'] = pnl
                logger.info(f"Updated PnL for {symbol} {position['direction']}: {pnl}")
                break
    
    def check_stop_loss_take_profit(self, symbol, current_price):
        """Check if position should be closed due to stop loss or take profit"""
        for position in self.open_positions:
            if position['symbol'] == symbol:
                if position['direction'] == 'buy':
                    # Check stop loss (price below stop loss)
                    if current_price <= position['stop_loss']:
                        logger.info(f"Stop loss triggered for {symbol} at {current_price}")
                        return 'stop_loss'
                    
                    # Check take profit (price above take profit)
                    if current_price >= position['take_profit']:
                        logger.info(f"Take profit triggered for {symbol} at {current_price}")
                        return 'take_profit'
                        
                else:  # short position
                    # Check stop loss (price above stop loss)
                    if current_price >= position['stop_loss']:
                        logger.info(f"Stop loss triggered for {symbol} at {current_price}")
                        return 'stop_loss'
                    
                    # Check take profit (price below take profit)
                    if current_price <= position['take_profit']:
                        logger.info(f"Take profit triggered for {symbol} at {current_price}")
                        return 'take_profit'
        
        return None
    
    def get_position_summary(self):
        """Get summary of all open positions"""
        if not self.open_positions:
            return "No open positions"
        
        summary = f"Open Positions ({len(self.open_positions)}):\n"
        total_pnl = 0.0
        
        for position in self.open_positions:
            pnl = position.get('unrealized_pnl', 0)
            total_pnl += pnl
            summary += f"  {position['symbol']}: {position['direction']} {position['lot_size']} lots, PnL: ${pnl:.2f}\n"
        
        summary += f"Total PnL: ${total_pnl:.2f}"
        return summary
    
    def update_account_balance(self, new_balance):
        """Update account balance (e.g., after deposits/withdrawals)"""
        self.account_balance = new_balance
        logger.info(f"Updated account balance: ${new_balance:.2f}")
    
    def get_risk_summary(self):
        """Get current risk summary"""
        portfolio_risk = self.calculate_portfolio_risk()
        
        summary = {
            'account_balance': self.account_balance,
            'open_positions': len(self.open_positions),
            'max_positions': self.max_positions,
            'portfolio_risk': portfolio_risk,
            'max_portfolio_risk': self.max_portfolio_risk,
            'risk_available': self.max_portfolio_risk - portfolio_risk
        }
        
        return summary 