"""
Analytics Module
Enhanced logging and performance tracking
"""

import json
import pandas as pd
from datetime import datetime
from utils.logger import get_logger
from config import SYMBOLS

logger = get_logger("Analytics")

class TradeAnalytics:
    def __init__(self):
        self.trades = []
        self.performance_metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'sharpe_ratio': 0.0
        }
        self.session_start_time = datetime.now()
        
    def log_trade_entry(self, symbol, direction, entry_price, lot_size, stop_loss, take_profit, 
                       indicators=None, reason=""):
        """Log detailed trade entry information."""
        trade = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'lot_size': lot_size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'indicators': indicators or {},
            'reason': reason,
            'status': 'open'
        }
        
        self.trades.append(trade)
        
        # Log detailed entry information
        logger.info("=" * 80)
        logger.info(f"[ENTRY] TRADE ENTRY: {symbol} {direction.upper()}")
        logger.info("=" * 80)
        logger.info(f"Entry Price: {entry_price:.5f}")
        logger.info(f"Lot Size: {lot_size:.4f}")
        logger.info(f"Stop Loss: {stop_loss:.5f}")
        logger.info(f"Take Profit: {take_profit:.5f}")
        logger.info(f"Risk/Reward: 1:{(take_profit - entry_price) / (entry_price - stop_loss):.2f}")
        logger.info(f"Reason: {reason}")
        
        if indicators:
            logger.info("Indicator Values:")
            for indicator, value in indicators.items():
                logger.info(f"  {indicator}: {value}")
                
        logger.info("=" * 80)
        
    def log_trade_exit(self, symbol, exit_price, pnl, reason="", duration=None):
        """Log detailed trade exit information."""
        # Find the corresponding trade
        for trade in self.trades:
            if trade['symbol'] == symbol and trade['status'] == 'open':
                trade['exit_price'] = exit_price
                trade['pnl'] = pnl
                trade['exit_reason'] = reason
                trade['duration'] = duration
                trade['status'] = 'closed'
                trade['exit_timestamp'] = datetime.now()
                
                # Update performance metrics
                self._update_performance_metrics(trade)
                
                # Log detailed exit information
                logger.info("=" * 80)
                logger.info(f"[EXIT] TRADE EXIT: {symbol}")
                logger.info("=" * 80)
                logger.info(f"Exit Price: {exit_price:.5f}")
                logger.info(f"PnL: ${pnl:.2f}")
                logger.info(f"Exit Reason: {reason}")
                if duration:
                    logger.info(f"Duration: {duration}")
                logger.info(f"Win/Loss: {'WIN' if pnl > 0 else 'LOSS'}")
                logger.info("=" * 80)
                
                break
                
    def _update_performance_metrics(self, trade):
        """Update performance metrics after trade closure."""
        self.performance_metrics['total_trades'] += 1
        self.performance_metrics['total_pnl'] += trade['pnl']
        
        if trade['pnl'] > 0:
            self.performance_metrics['winning_trades'] += 1
        else:
            self.performance_metrics['losing_trades'] += 1
            
        # Calculate win rate
        total = self.performance_metrics['total_trades']
        wins = self.performance_metrics['winning_trades']
        self.performance_metrics['win_rate'] = wins / total if total > 0 else 0
        
        # Calculate average win/loss
        winning_trades = [t for t in self.trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in self.trades if t.get('pnl', 0) < 0]
        
        if winning_trades:
            self.performance_metrics['avg_win'] = sum(t['pnl'] for t in winning_trades) / len(winning_trades)
        if losing_trades:
            self.performance_metrics['avg_loss'] = sum(t['pnl'] for t in losing_trades) / len(losing_trades)
            
        # Calculate profit factor
        total_wins = sum(t['pnl'] for t in winning_trades)
        total_losses = abs(sum(t['pnl'] for t in losing_trades))
        self.performance_metrics['profit_factor'] = total_wins / total_losses if total_losses > 0 else float('inf')
        
    def get_performance_summary(self):
        """Get comprehensive performance summary."""
        session_duration = datetime.now() - self.session_start_time
        
        summary = {
            'session_duration': str(session_duration),
            'total_trades': self.performance_metrics['total_trades'],
            'winning_trades': self.performance_metrics['winning_trades'],
            'losing_trades': self.performance_metrics['losing_trades'],
            'win_rate': f"{self.performance_metrics['win_rate']:.1%}",
            'total_pnl': f"${self.performance_metrics['total_pnl']:.2f}",
            'avg_win': f"${self.performance_metrics['avg_win']:.2f}",
            'avg_loss': f"${self.performance_metrics['avg_loss']:.2f}",
            'profit_factor': f"{self.performance_metrics['profit_factor']:.2f}",
            'max_drawdown': f"{self.performance_metrics['max_drawdown']:.2%}"
        }
        
        return summary
        
    def log_performance_summary(self):
        """Log current performance summary."""
        summary = self.get_performance_summary()
        
        logger.info("=" * 80)
        logger.info("[SUMMARY] PERFORMANCE SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Session Duration: {summary['session_duration']}")
        logger.info(f"Total Trades: {summary['total_trades']}")
        logger.info(f"Winning Trades: {summary['winning_trades']}")
        logger.info(f"Losing Trades: {summary['losing_trades']}")
        logger.info(f"Win Rate: {summary['win_rate']}")
        logger.info(f"Total PnL: {summary['total_pnl']}")
        logger.info(f"Average Win: {summary['avg_win']}")
        logger.info(f"Average Loss: {summary['avg_loss']}")
        logger.info(f"Profit Factor: {summary['profit_factor']}")
        logger.info(f"Max Drawdown: {summary['max_drawdown']}")
        logger.info("=" * 80)
        
    def save_trade_history(self, filename=None):
        """Save trade history to JSON file."""
        if filename is None:
            filename = f"trade_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
        # Convert trades to serializable format
        serializable_trades = []
        for trade in self.trades:
            serializable_trade = trade.copy()
            serializable_trade['timestamp'] = trade['timestamp'].isoformat()
            if 'exit_timestamp' in trade:
                serializable_trade['exit_timestamp'] = trade['exit_timestamp'].isoformat()
            serializable_trades.append(serializable_trade)
            
        data = {
            'trades': serializable_trades,
            'performance_metrics': self.performance_metrics,
            'session_start_time': self.session_start_time.isoformat(),
            'session_end_time': datetime.now().isoformat()
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
            
        logger.info(f"Trade history saved to {filename}")
        
    def export_to_csv(self, filename=None):
        """Export trade history to CSV for analysis."""
        if filename is None:
            filename = f"trade_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
        df = pd.DataFrame(self.trades)
        df.to_csv(filename, index=False)
        logger.info(f"Trade history exported to {filename}")
        
    def get_symbol_performance(self, symbol):
        """Get performance metrics for a specific symbol."""
        symbol_trades = [t for t in self.trades if t['symbol'] == symbol]
        
        if not symbol_trades:
            return None
            
        total_pnl = sum(t.get('pnl', 0) for t in symbol_trades)
        winning_trades = [t for t in symbol_trades if t.get('pnl', 0) > 0]
        win_rate = len(winning_trades) / len(symbol_trades) if symbol_trades else 0
        
        return {
            'symbol': symbol,
            'total_trades': len(symbol_trades),
            'winning_trades': len(winning_trades),
            'win_rate': f"{win_rate:.1%}",
            'total_pnl': f"${total_pnl:.2f}"
        } 