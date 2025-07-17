import pandas as pd
import numpy as np
from datetime import datetime
from utils.logger import get_logger
from config import ATR_PERIOD, ATR_STOP_LOSS_MULTIPLIER, ATR_TAKE_PROFIT_MULTIPLIER, ATR_MULTIPLIER
from utils.indicators import calculate_atr
import matplotlib.pyplot as plt
import jinja2
import base64

logger = get_logger("Backtester")

class Backtester:
    def __init__(self, strategy_class, data, lot_size=0.02, commission=0.0001, spread=0.0002, risk_per_trade=0.01, pip_value=1.0, max_drawdown=0.2):
        self.strategy_class = strategy_class
        self.data = data
        self.lot_size = lot_size
        self.commission = commission  # Commission per lot
        self.spread = spread  # Spread in pips
        self.trades = []
        self.positions = []
        self.equity_curve = []
        self.risk_per_trade = risk_per_trade  # Fraction of balance to risk per trade
        self.pip_value = pip_value  # Value of one pip (for XAUUSD, 1.0 or 0.1)
        self.max_drawdown = max_drawdown  # Max allowed drawdown (fraction)
        
    def run(self, **strategy_params):
        """Run backtest with given strategy parameters"""
        logger.info(f"Starting backtest with params: {strategy_params}")
        
        # Initialize strategy
        strategy = self.strategy_class(self.data, lot_size=self.lot_size, **strategy_params)
        
        # Get signals from strategy
        signals = strategy.generate_signals()
        
        # Simulate trading
        self._simulate_trading(signals)
        
        # Calculate performance metrics
        performance = self._calculate_performance()
        
        # Plot analytics
        self.plot_equity_curve()
        self.plot_drawdown_curve()
        self.plot_trade_distribution()
        # Generate HTML report
        self.generate_html_report(performance, strategy_params)
        return performance
    
    def _simulate_trading(self, signals):
        """Simulate trading based on signals, with ATR-based SL/TP, trailing stop, dynamic position sizing, and max drawdown stop."""
        balance = 10000  # Starting balance
        equity = balance
        position = None
        trailing_stop = None
        atr_series = calculate_atr(self.data, ATR_PERIOD)
        max_equity = balance
        drawdown_triggered = False
        for i, row in signals.iterrows():
            current_price = row['close']
            # Support both pandas Series and numpy array
            if isinstance(atr_series, pd.Series) and i in atr_series.index:
                atr = atr_series[i]
            elif hasattr(atr_series, '__getitem__'):
                try:
                    atr = atr_series[i]
                except Exception:
                    atr = None
            else:
                atr = None
            # Update max equity and check drawdown
            if equity > max_equity:
                max_equity = equity
            current_drawdown = (max_equity - equity) / max_equity if max_equity > 0 else 0
            if current_drawdown > self.max_drawdown and not drawdown_triggered:
                drawdown_triggered = True
                logger.warning(f"Max drawdown of {self.max_drawdown*100:.1f}% exceeded at {i}. No new trades will be opened.")
            # Handle position management
            if position is not None:
                # Update trailing stop (if in profit)
                if position['direction'] == 'long':
                    new_trailing = current_price - ATR_MULTIPLIER * atr if atr is not None else None
                    if new_trailing is not None and (trailing_stop is None or new_trailing > trailing_stop):
                        trailing_stop = new_trailing
                else:
                    new_trailing = current_price + ATR_MULTIPLIER * atr if atr is not None else None
                    if new_trailing is not None and (trailing_stop is None or new_trailing < trailing_stop):
                        trailing_stop = new_trailing
                # Check SL/TP/trailing stop/opposite signal
                close_reason = None
                if position['direction'] == 'long':
                    if trailing_stop is not None and current_price <= trailing_stop:
                        close_reason = 'trailing_stop'
                    elif current_price <= position['stop_loss']:
                        close_reason = 'stop_loss'
                    elif current_price >= position['take_profit']:
                        close_reason = 'take_profit'
                    elif row['signal'] == -1:
                        close_reason = 'opposite_signal'
                else:
                    if trailing_stop is not None and current_price >= trailing_stop:
                        close_reason = 'trailing_stop'
                    elif current_price >= position['stop_loss']:
                        close_reason = 'stop_loss'
                    elif current_price <= position['take_profit']:
                        close_reason = 'take_profit'
                    elif row['signal'] == 1:
                        close_reason = 'opposite_signal'
                if close_reason:
                    pnl = self._calculate_pnl(position, current_price)
                    balance += pnl
                    equity = balance
                    trade = {
                        'entry_time': position['entry_time'],
                        'exit_time': i,
                        'symbol': position['symbol'],
                        'direction': position['direction'],
                        'entry_price': position['entry_price'],
                        'exit_price': current_price,
                        'lot_size': position['lot_size'],
                        'stop_loss': position['stop_loss'],
                        'take_profit': position['take_profit'],
                        'trailing_stop': trailing_stop,
                        'pnl': pnl,
                        'balance': balance,
                        'exit_reason': close_reason
                    }
                    self.trades.append(trade)
                    position = None
                    trailing_stop = None
            # Handle new signals (only if drawdown not triggered)
            if not drawdown_triggered:
                if position is None and row['Signal'] == 1:
                    entry_price = current_price + self.spread
                    sl = entry_price - ATR_STOP_LOSS_MULTIPLIER * atr if atr is not None else entry_price * 0.97
                    tp = entry_price + ATR_TAKE_PROFIT_MULTIPLIER * atr if atr is not None else entry_price * 1.03
                    stop_dist = abs(entry_price - sl)
                    # Dynamic position sizing
                    lot_size = (self.risk_per_trade * balance) / (stop_dist * self.pip_value) if stop_dist > 0 else self.lot_size
                    trailing_stop = entry_price - ATR_MULTIPLIER * atr if atr is not None else None
                position = {
                    'entry_time': i,
                    'entry_price': entry_price,
                    'direction': 'long',
                        'lot_size': lot_size,
                        'symbol': 'symbol',
                        'stop_loss': sl,
                        'take_profit': tp
                    }
                    # Log entry
                    self.trades.append({
                        'entry_time': i,
                        'symbol': 'symbol',
                        'direction': 'long',
                        'entry_price': entry_price,
                        'lot_size': lot_size,
                        'stop_loss': sl,
                        'take_profit': tp,
                        'trailing_stop': trailing_stop,
                        'entry_reason': 'Buy signal: MA crossover + filters',
                        'status': 'open'
                    })
                elif position is None and row['Signal'] == -1:
                    entry_price = current_price - self.spread
                    sl = entry_price + ATR_STOP_LOSS_MULTIPLIER * atr if atr is not None else entry_price * 1.03
                    tp = entry_price - ATR_TAKE_PROFIT_MULTIPLIER * atr if atr is not None else entry_price * 0.97
                    stop_dist = abs(entry_price - sl)
                    lot_size = (self.risk_per_trade * balance) / (stop_dist * self.pip_value) if stop_dist > 0 else self.lot_size
                    trailing_stop = entry_price + ATR_MULTIPLIER * atr if atr is not None else None
                position = {
                    'entry_time': i,
                    'entry_price': entry_price,
                    'direction': 'short',
                        'lot_size': lot_size,
                        'symbol': 'symbol',
                        'stop_loss': sl,
                        'take_profit': tp
                    }
                    # Log entry
                    self.trades.append({
                        'entry_time': i,
                        'symbol': 'symbol',
                        'direction': 'short',
                        'entry_price': entry_price,
                        'lot_size': lot_size,
                        'stop_loss': sl,
                        'take_profit': tp,
                        'trailing_stop': trailing_stop,
                        'entry_reason': 'Sell signal: MA crossover + filters',
                        'status': 'open'
                    })
            # Update equity curve
            if position is not None:
                unrealized_pnl = self._calculate_pnl(position, current_price)
                equity = balance + unrealized_pnl
            self.equity_curve.append({
                'time': i,
                'balance': balance,
                'equity': equity,
                'position': position is not None
            })
    
    def _should_close_position(self, position, current_price, row):
        """No longer used: close logic is now in _simulate_trading for SL/TP/trailing stop/opposite signal."""
        return False
    
    def _calculate_pnl(self, position, current_price):
        """Calculate PnL for a position"""
        if position['direction'] == 'long':
            pnl = (current_price - position['entry_price']) * position['lot_size'] * 100000
        else:  # short
            pnl = (position['entry_price'] - current_price) * position['lot_size'] * 100000
        
        # Subtract commission
        pnl -= self.commission * position['lot_size'] * 100000
        
        return pnl
    
    def _calculate_performance(self):
        """Calculate comprehensive performance metrics"""
        if not self.trades:
            return {
                'total_return': 0,
                'num_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0
            }
        
        # Basic metrics
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] <= 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0
        
        # Total return
        initial_balance = 10000
        final_balance = self.trades[-1]['balance'] if self.trades else initial_balance
        total_return = (final_balance - initial_balance) / initial_balance
        
        # Calculate drawdown
        equity_values = [e['equity'] for e in self.equity_curve]
        peak = equity_values[0]
        max_drawdown = 0
        
        for equity in equity_values:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak
            max_drawdown = max(max_drawdown, drawdown)
        
        # Calculate Sharpe ratio (simplified)
        returns = pd.Series([e['equity'] for e in self.equity_curve]).pct_change().dropna()
        sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        performance = {
            'total_return': total_return,
            'num_trades': total_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'final_balance': final_balance,
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }
        
        logger.info(f"Backtest completed: {total_return:.2%} return, {total_trades} trades, {win_rate:.2%} win rate")
        return performance 

    def plot_equity_curve(self, filename='equity_curve.png'):
        times = [e['time'] for e in self.equity_curve]
        equity = [e['equity'] for e in self.equity_curve]
        plt.figure(figsize=(10, 5))
        plt.plot(times, equity, label='Equity Curve')
        plt.title('Equity Curve')
        plt.xlabel('Time')
        plt.ylabel('Equity')
        plt.legend()
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()
        logger.info(f"Equity curve saved to {filename}")

    def plot_drawdown_curve(self, filename='drawdown_curve.png'):
        equity = [e['equity'] for e in self.equity_curve]
        peak = equity[0]
        drawdowns = []
        for eq in equity:
            if eq > peak:
                peak = eq
            drawdown = (peak - eq) / peak
            drawdowns.append(drawdown)
        times = [e['time'] for e in self.equity_curve]
        plt.figure(figsize=(10, 5))
        plt.plot(times, drawdowns, label='Drawdown')
        plt.title('Drawdown Curve')
        plt.xlabel('Time')
        plt.ylabel('Drawdown')
        plt.legend()
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()
        logger.info(f"Drawdown curve saved to {filename}")

    def plot_trade_distribution(self, filename='trade_pnl_hist.png'):
        pnls = [t['pnl'] for t in self.trades if 'pnl' in t]
        if not pnls:
            logger.info("No closed trades to plot PnL distribution.")
            return
        plt.figure(figsize=(8, 4))
        plt.hist(pnls, bins=30, alpha=0.7, color='blue', edgecolor='black')
        plt.title('Trade P&L Distribution')
        plt.xlabel('PnL')
        plt.ylabel('Frequency')
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()
        logger.info(f"Trade P&L histogram saved to {filename}") 

    def generate_html_report(self, performance, strategy_params, filename='backtest_report.html'):
        """Generate an HTML report with summary, charts, and trade log."""
        # Read chart images as base64
        def img_to_base64(path):
            with open(path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        equity_img = img_to_base64('equity_curve.png')
        drawdown_img = img_to_base64('drawdown_curve.png')
        pnl_img = img_to_base64('trade_pnl_hist.png')
        # Prepare trade log (show only last 100 trades for brevity)
        trades = performance['trades'][-100:] if len(performance['trades']) > 100 else performance['trades']
        # Jinja2 template
        template = jinja2.Template('''
        <html><head><title>Backtest Report</title>
        <style>body{font-family:sans-serif;} table{border-collapse:collapse;} th,td{border:1px solid #ccc;padding:4px;} .chart{margin:10px 0;}</style>
        </head><body>
        <h1>Backtest Report</h1>
        <h2>Parameters</h2>
        <pre>{{ params }}</pre>
        <h2>Summary</h2>
        <ul>
            <li>Total Return: {{ perf.total_return|round(2) }}</li>
            <li>Num Trades: {{ perf.num_trades }}</li>
            <li>Win Rate: {{ perf.win_rate|round(2) }}</li>
            <li>Avg Win: {{ perf.avg_win|round(2) }}</li>
            <li>Avg Loss: {{ perf.avg_loss|round(2) }}</li>
            <li>Max Drawdown: {{ perf.max_drawdown|round(2) }}</li>
            <li>Sharpe Ratio: {{ perf.sharpe_ratio|round(2) }}</li>
            <li>Final Balance: {{ perf.final_balance|round(2) }}</li>
        </ul>
        <h2>Charts</h2>
        <div class="chart"><b>Equity Curve</b><br><img src="data:image/png;base64,{{ equity_img }}" width="600"></div>
        <div class="chart"><b>Drawdown Curve</b><br><img src="data:image/png;base64,{{ drawdown_img }}" width="600"></div>
        <div class="chart"><b>Trade P&L Histogram</b><br><img src="data:image/png;base64,{{ pnl_img }}" width="600"></div>
        <h2>Trade Log (last 100)</h2>
        <table><tr>{% for k in trades[0].keys() %}<th>{{ k }}</th>{% endfor %}</tr>
        {% for t in trades %}<tr>{% for v in t.values() %}<td>{{ v }}</td>{% endfor %}</tr>{% endfor %}
        </table>
        </body></html>
        ''')
        html = template.render(perf=performance, params=strategy_params, equity_img=equity_img, drawdown_img=drawdown_img, pnl_img=pnl_img, trades=trades)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f"Backtest HTML report saved to {filename}") 