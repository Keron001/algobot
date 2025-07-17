import os
import json
from flask import Flask, render_template_string, request, Response, send_file
from werkzeug.security import check_password_hash, generate_password_hash
import threading
import datetime
USER_AUDIT_LOG = 'user_audit.log'
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import io
import csv
from collections import defaultdict

app = Flask(__name__)

STATUS_FILE = os.environ.get('BOT_STATUS_FILE', 'bot_status.json')
TRADE_HISTORY_FILE = os.environ.get('TRADE_HISTORY_FILE', 'trade_history.json')
ANALYTICS_FILE = os.environ.get('ANALYTICS_FILE', 'analytics.json')
LOG_FILE = os.environ.get('LOG_FILE', 'EnhancedTrader.log')
USERS_FILE = 'users.json'
PAPER_TRADES_FILE = 'paper_trades.json'

# Load users from file or create default
_users_lock = threading.Lock()
def load_users():
    if not os.path.exists(USERS_FILE):
        # Default admin user
        users = {'Admin': {'hash': generate_password_hash('Admin123$#'), 'role': 'admin'}}
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f)
        return users
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with _users_lock:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f)

def log_user_action(admin, action, target, role=None):
    with open(USER_AUDIT_LOG, 'a') as f:
        ts = datetime.datetime.now().isoformat()
        entry = {'timestamp': ts, 'admin': admin, 'action': action, 'target': target}
        if role:
            entry['role'] = role
        f.write(json.dumps(entry) + '\n')

USERS = load_users()

API_KEY = 'changeme123'  # Should match the bot's API_KEY

TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AlgoBot Dashboard</title>
    <meta http-equiv="refresh" content="5">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 0; }
        .container { max-width: 900px; margin: 40px auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #ccc; padding: 32px; }
        h1 { color: #333; }
        .status { font-size: 1.2em; margin-bottom: 16px; }
        .pnl { font-size: 2em; color: #007b3a; }
        .positions { margin-top: 24px; }
        .positions th, .positions td { padding: 6px 12px; }
        .positions th { background: #eee; }
        .positions tr:nth-child(even) { background: #f9f9f9; }
        .trades { margin-top: 32px; }
        .trades th, .trades td { padding: 6px 12px; }
        .trades th { background: #eee; }
        .trades tr:nth-child(even) { background: #f9f9f9; }
        .analytics { margin-top: 32px; background: #f7f7f7; padding: 16px; border-radius: 6px; }
        .logs { margin-top: 32px; background: #222; color: #eee; padding: 16px; border-radius: 6px; max-height: 300px; overflow-y: scroll; font-family: monospace; font-size: 0.95em; }
        .logs pre { margin: 0; }
        .equity-curve { margin-top: 32px; background: #f7f7f7; padding: 16px; border-radius: 6px; }
        .controls { margin-top: 32px; }
        .controls button { margin-right: 12px; padding: 8px 18px; font-size: 1em; border-radius: 4px; border: none; background: #007b3a; color: #fff; cursor: pointer; }
        .controls button.stop { background: #c0392b; }
        .controls .status-msg { margin-left: 16px; color: #007b3a; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>AlgoBot Dashboard</h1>
        <div class="controls">
            <button onclick="control('pause')">Pause</button>
            <button onclick="control('resume')">Resume</button>
            <button class="stop" onclick="control('stop')">Stop</button>
            <span class="status-msg" id="controlStatus"></span>
        </div>
        {% if status %}
            <div class="status">
                <b>Status:</b> {{ 'RUNNING' if status['is_running'] else 'STOPPED' }}<br>
                <b>Trading:</b> {{ 'ACTIVE' if status['is_trading'] else 'INACTIVE' }}<br>
                <b>Paper Trading:</b> {{ status['paper_trading'] }}<br>
                <b>Max Positions:</b> {{ status['max_positions'] }}<br>
            </div>
            <div class="pnl">
                <b>Daily P&L:</b> ${{ '{:.2f}'.format(status['daily_pnl']) }}
            </div>
            <div class="positions">
                <h3>Open Positions: {{ status['open_positions'] }}</h3>
            </div>
        {% else %}
            <div class="status">No status available. Is the bot running?</div>
        {% endif %}
        <div class="analytics">
            <h3>Analytics</h3>
            {% if analytics %}
                <ul>
                {% for k, v in analytics.items() %}
                    <li><b>{{ k.replace('_', ' ').title() }}:</b> {{ v }}</li>
                {% endfor %}
                </ul>
            {% else %}
                <div>No analytics available.</div>
            {% endif %}
        </div>
        <div class="equity-curve">
            <h3>Equity Curve</h3>
            <canvas id="equityCurveChart" width="800" height="250"></canvas>
        </div>
        <div class="trades">
            <h3>Recent Trades</h3>
            {% if trades and trades|length > 0 %}
            <table border="0" width="100%">
                <tr>
                    <th>Time</th><th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th><th>P&L</th>
                </tr>
                {% for t in trades[-20:] %}
                <tr>
                    <td>{{ t.get('timestamp', '') }}</td>
                    <td>{{ t.get('symbol', '') }}</td>
                    <td>{{ t.get('side', t.get('direction', '')) }}</td>
                    <td>{{ t.get('entry_price', '') }}</td>
                    <td>{{ t.get('exit_price', '') }}</td>
                    <td>{{ t.get('pnl', t.get('PnL', '')) }}</td>
                </tr>
                {% endfor %}
            </table>
            {% else %}
                <div>No trades yet.</div>
            {% endif %}
        </div>
        <div class="logs">
            <h3>Recent Log Entries</h3>
            {% if logs and logs|length > 0 %}
                <pre>{% for line in logs %}{{ line }}
{% endfor %}</pre>
            {% else %}
                <div>No log entries found.</div>
            {% endif %}
        </div>
        <div style="margin-top:32px; color:#888; font-size:0.9em;">
            <b>Auto-refreshes every 5 seconds.</b>
        </div>
    </div>
    <script>
        // Manual controls
        function control(action) {
            const statusMsg = document.getElementById('controlStatus');
            statusMsg.textContent = '...';
            fetch(`http://127.0.0.1:8000/api/${action}`, {
                method: 'POST',
                headers: { 'X-API-KEY': API_KEY }
            })
            .then(r => r.json())
            .then(data => {
                if (data.status) {
                    statusMsg.textContent = 'Success: ' + data.status;
                } else {
                    statusMsg.textContent = 'Error: ' + (data.error || 'Unknown');
                }
            })
            .catch(e => {
                statusMsg.textContent = 'Error: ' + e;
            });
        }
        // Equity curve chart
        const ctx = document.getElementById('equityCurveChart').getContext('2d');
        const tradeData = {{ equity_curve|tojson }};
        const labels = tradeData.map(t => t.time);
        const equity = tradeData.map(t => t.equity);
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Equity Curve',
                    data: equity,
                    borderColor: '#007b3a',
                    backgroundColor: 'rgba(0,123,58,0.1)',
                    fill: true,
                    tension: 0.2
                }]
            },
            options: {
                responsive: false,
                plugins: { legend: { display: false } },
                scales: { x: { display: false }, y: { beginAtZero: true } }
            }
        });
    </script>
</body>
</html>
'''

def check_auth(username, password):
    if username in USERS:
        return check_password_hash(USERS[username]['hash'], password)
    return False

def get_user_role(username):
    return USERS.get(username, {}).get('role', 'readonly')

def authenticate():
    return Response(
        'Login required', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated

# Flask-Limiter setup
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per minute"]
)

# Rate limit login attempts
@app.before_request
def limit_login():
    if request.endpoint in ['dashboard', 'manage_users'] and request.authorization:
        limiter.limit("5 per minute")(lambda: None)()

# Rate limit API endpoints
@app.route('/api/<action>', methods=['POST'])
@limiter.limit("10 per minute")
def api_proxy(action):
    # Proxy to the bot API (if running separately)
    # This is a placeholder for future extension
    return Response('Not implemented', 501)

# User management route (admin only)
@app.route('/users', methods=['GET', 'POST'])
@requires_auth
def manage_users():
    auth = request.authorization
    if not auth or get_user_role(auth.username) != 'admin':
        return Response('Forbidden', 403)
    msg = ''
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role') or 'readonly'
        global USERS
        if action == 'add' and username and password:
            if username in USERS:
                msg = f'User {username} already exists.'
            else:
                USERS[username] = {'hash': generate_password_hash(password), 'role': role}
                save_users(USERS)
                log_user_action(auth.username, 'add', username, role)
                msg = f'User {username} added as {role}.'
        elif action == 'remove' and username:
            if username == 'Admin':
                msg = 'Cannot remove Admin user.'
            elif username not in USERS:
                msg = f'User {username} does not exist.'
            else:
                log_user_action(auth.username, 'remove', username, USERS[username]['role'])
                del USERS[username]
                save_users(USERS)
                msg = f'User {username} removed.'
        elif action == 'role' and username and role:
            if username not in USERS:
                msg = f'User {username} does not exist.'
            elif username == 'Admin':
                msg = 'Cannot change Admin role.'
            else:
                USERS[username]['role'] = role
                save_users(USERS)
                log_user_action(auth.username, 'role_change', username, role)
                msg = f'User {username} role changed to {role}.'
    user_list = [(u, USERS[u]['role']) for u in USERS if u != 'Admin']
    return render_template_string('''
    <h2>User Management</h2>
    <form method="post">
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password">
        <select name="role">
            <option value="trader">trader</option>
            <option value="readonly">readonly</option>
            <option value="admin">admin</option>
        </select>
        <button type="submit" name="action" value="add">Add User</button>
        <button type="submit" name="action" value="remove">Remove User</button>
        <button type="submit" name="action" value="role">Change Role</button>
    </form>
    <div style="color:green; margin:10px 0;">{{msg}}</div>
    <h3>Current Users:</h3>
    <ul>
    {% for u, r in user_list %}<li>{{u}} ({{r}})</li>{% endfor %}
    </ul>
    <a href="/">Back to Dashboard</a>
    ''', msg=msg, user_list=user_list)

@app.route('/')
@requires_auth
def dashboard():
    status = None
    trades = []
    analytics = None
    logs = []
    equity_curve = []
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, 'r') as f:
                status = json.load(f)
        except Exception:
            status = None
    if os.path.exists(TRADE_HISTORY_FILE):
        try:
            with open(TRADE_HISTORY_FILE, 'r') as f:
                trades = json.load(f)
            # Compute equity curve
            equity = 0.0
            equity_curve = []
            for t in trades:
                pnl = t.get('pnl') or t.get('PnL') or 0.0
                try:
                    pnl = float(pnl)
                except Exception:
                    pnl = 0.0
                equity += pnl
                equity_curve.append({
                    'time': t.get('timestamp', ''),
                    'equity': equity
                })
        except Exception:
            trades = []
            equity_curve = []
    if os.path.exists(ANALYTICS_FILE):
        try:
            with open(ANALYTICS_FILE, 'r') as f:
                analytics = json.load(f)
        except Exception:
            analytics = None
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                lines = f.readlines()
                logs = [line.strip() for line in lines[-50:]]
        except Exception:
            logs = []
    return render_template_string(TEMPLATE, status=status, trades=trades, analytics=analytics, logs=logs, equity_curve=equity_curve)

PAPER_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Paper Trading Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>body { font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 0; } .container { max-width: 900px; margin: 40px auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #ccc; padding: 32px; } h1 { color: #333; } .tab { margin-bottom: 24px; } .tab a { margin-right: 18px; text-decoration: none; color: #007b3a; font-weight: bold; } .tab a.active { color: #c0392b; } .paper-summary { margin-bottom: 24px; } .paper-table th, .paper-table td { padding: 6px 12px; } .paper-table th { background: #eee; } .paper-table tr:nth-child(even) { background: #f9f9f9; } .analytics { margin-top: 32px; background: #f7f7f7; padding: 16px; border-radius: 6px; } .toggle { margin-top: 24px; } .toggle label { font-weight: bold; margin-right: 8px; } .toggle input { transform: scale(1.3); } </style>
</head>
<body>
    <div class="container">
        <div class="tab">
            <a href="/">Live Dashboard</a>
            <a href="/paper" class="active">Paper Trading</a>
        </div>
        <h1>Paper Trading Dashboard</h1>
        <div class="toggle">
            <form method="post" action="/toggle_paper">
                <label>Paper Trading:</label>
                <input type="checkbox" name="paper" value="1" {% if paper_trading %}checked{% endif %} onchange="this.form.submit()">
            </form>
        </div>
        <div class="paper-summary">
            <b>Balance:</b> ${{ balance|round(2) }} &nbsp; <b>Equity:</b> ${{ equity|round(2) }}
            <br><b>Open Positions:</b> {{ open_positions|length }} &nbsp; <b>Closed Trades:</b> {{ closed_trades|length }}
        </div>
        <form method="get" style="margin-bottom:16px;">
            <input type="text" name="symbol" placeholder="Symbol" value="{{ filter_symbol }}">
            <input type="date" name="date" value="{{ filter_date }}">
            <input type="text" name="strategy" placeholder="Strategy" value="{{ filter_strategy }}">
            <button type="submit">Filter</button>
            <a href="/paper">Clear</a>
            <a href="/api/paper_trades/export" style="margin-left:16px;">Export CSV</a>
            <a href="/api/paper_trades/clear" style="margin-left:16px; color:#c0392b;">Clear All</a>
        </form>
        <div class="analytics">
            <h3>Analytics</h3>
            {% if analytics %}
                <ul>
                {% for k, v in analytics.items() %}
                    <li><b title="{{ k }}">{{ k.replace('_', ' ').title() }}:</b> {{ v }}</li>
                {% endfor %}
                </ul>
            {% else %}
                <div>No analytics available.</div>
            {% endif %}
        </div>
        <!-- New charts for advanced analytics -->
        <div style="margin-top:32px;">
            <h3>P&L by Symbol</h3>
            <canvas id="pnlBySymbolChart" width="800" height="200"></canvas>
        </div>
        <div style="margin-top:32px;">
            <h3>P&L by Strategy</h3>
            <canvas id="pnlByStrategyChart" width="800" height="200"></canvas>
        </div>
        <div style="margin-top:32px;">
            <h3>Trade P&L Distribution</h3>
            <canvas id="pnlHistogramChart" width="800" height="200"></canvas>
        </div>
        <div style="margin-top:32px;">
            <h3>Win/Loss Ratio</h3>
            <canvas id="winLossPieChart" width="400" height="200"></canvas>
        </div>
        <div style="margin-top:32px;">
            <h3>Equity Curve</h3>
            <canvas id="equityCurveChart" width="800" height="250"></canvas>
        </div>
        <div style="margin-top:32px;">
            <h3>Open Positions</h3>
            <table class="paper-table" border="0" width="100%">
                <tr><th>Symbol</th><th>Side</th><th>Open Price</th><th>Lot</th><th>SL</th><th>TP</th><th>Open Time</th></tr>
                {% for p in open_positions %}
                <tr><td>{{ p.symbol }}</td><td>{{ 'BUY' if p.signal > 0 else 'SELL' }}</td><td>{{ p.open_price }}</td><td>{{ p.lot_size }}</td><td>{{ p.stop_loss }}</td><td>{{ p.take_profit }}</td><td>{{ p.open_time|datetime }}</td></tr>
                {% endfor %}
            </table>
        </div>
        <div style="margin-top:32px;">
            <h3>Closed Trades</h3>
            <table class="paper-table" border="0" width="100%">
                <tr><th>Symbol</th><th>Side</th><th>Open</th><th>Close</th><th>Lot</th><th>P&L</th><th>Open Time</th><th>Close Time</th></tr>
                {% for t in closed_trades %}
                <tr><td>{{ t.symbol }}</td><td>{{ 'BUY' if t.signal > 0 else 'SELL' }}</td><td>{{ t.open_price }}</td><td>{{ t.close_price }}</td><td>{{ t.lot_size }}</td><td>{{ t.pnl|round(2) }}</td><td>{{ t.open_time|datetime }}</td><td>{{ t.close_time|datetime }}</td></tr>
                {% endfor %}
            </table>
        </div>
    </div>
    <script>
        // Equity curve chart
        const ctx = document.getElementById('equityCurveChart').getContext('2d');
        const tradeData = {{ equity_curve|tojson }};
        const labels = tradeData.map(t => new Date(t.time * 1000).toLocaleString());
        const equity = tradeData.map(t => t.equity);
        new Chart(ctx, {
            type: 'line',
            data: { labels: labels, datasets: [{ label: 'Equity Curve', data: equity, borderColor: '#007b3a', backgroundColor: 'rgba(0,123,58,0.1)', fill: true, tension: 0.2 }] },
            options: { responsive: false, plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { beginAtZero: true } } }
        });

        // P&L by Symbol Bar Chart
        const pnlBySymbol = {{ pnl_by_symbol|tojson }};
        const symbolLabels = Object.keys(pnlBySymbol);
        const symbolPnL = Object.values(pnlBySymbol);
        new Chart(document.getElementById('pnlBySymbolChart').getContext('2d'), {
            type: 'bar',
            data: {
                labels: symbolLabels,
                datasets: [{
                    label: 'P&L',
                    data: symbolPnL,
                    backgroundColor: '#007b3a',
                }]
            },
            options: { responsive: false, plugins: { legend: { display: false } } }
        });

        // P&L by Strategy Bar Chart
        const pnlByStrategy = {{ pnl_by_strategy|tojson }};
        const strategyLabels = Object.keys(pnlByStrategy);
        const strategyPnL = Object.values(pnlByStrategy);
        new Chart(document.getElementById('pnlByStrategyChart').getContext('2d'), {
            type: 'bar',
            data: {
                labels: strategyLabels,
                datasets: [{
                    label: 'P&L',
                    data: strategyPnL,
                    backgroundColor: '#c0392b',
                }]
            },
            options: { responsive: false, plugins: { legend: { display: false } } }
        });

        // Trade P&L Histogram
        function getHistogramBins(data, binCount) {
            if (data.length === 0) return { bins: [], counts: [] };
            const min = Math.min(...data), max = Math.max(...data);
            const binSize = (max - min) / binCount;
            const bins = Array.from({length: binCount}, (_, i) => min + i * binSize);
            const counts = Array(binCount).fill(0);
            data.forEach(val => {
                let idx = Math.floor((val - min) / binSize);
                if (idx === binCount) idx = binCount - 1;
                counts[idx]++;
            });
            return { bins, counts };
        }
        const closedPnLList = {{ closed_pnl_list|tojson }};
        const hist = getHistogramBins(closedPnLList, 20);
        new Chart(document.getElementById('pnlHistogramChart').getContext('2d'), {
            type: 'bar',
            data: {
                labels: hist.bins.map(x => x.toFixed(2)),
                datasets: [{
                    label: 'Trade Count',
                    data: hist.counts,
                    backgroundColor: '#8884d8',
                }]
            },
            options: { responsive: false, plugins: { legend: { display: false } } }
        });

        // Win/Loss Pie Chart
        const winCount = {{ win_count }};
        const lossCount = {{ loss_count }};
        new Chart(document.getElementById('winLossPieChart').getContext('2d'), {
            type: 'pie',
            data: {
                labels: ['Wins', 'Losses'],
                datasets: [{
                    data: [winCount, lossCount],
                    backgroundColor: ['#007b3a', '#c0392b'],
                }]
            },
            options: { responsive: false }
        });
    </script>
</body>
</html>
'''

def parse_datetime(ts):
    try:
        return datetime.datetime.fromtimestamp(float(ts)).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ''

@app.template_filter('datetime')
def datetime_filter(ts):
    return parse_datetime(ts)

@app.route('/paper', methods=['GET'])
@requires_auth
def paper_dashboard():
    filter_symbol = request.args.get('symbol', '').upper()
    filter_date = request.args.get('date', '')
    filter_strategy = request.args.get('strategy', '')
    paper_trading = False
    open_positions, closed_trades, balance, equity, history = [], [], 0, 0, []
    analytics = {}
    if os.path.exists(PAPER_TRADES_FILE):
        with open(PAPER_TRADES_FILE, 'r') as f:
            state = json.load(f)
            open_positions = state.get('open_positions', [])
            closed_trades = state.get('closed_trades', [])
            balance = state.get('balance', 0)
            equity = state.get('equity', 0)
            history = state.get('history', [])
    # Filtering
    if filter_symbol:
        open_positions = [p for p in open_positions if p['symbol'] == filter_symbol]
        closed_trades = [t for t in closed_trades if t['symbol'] == filter_symbol]
    if filter_date:
        open_positions = [p for p in open_positions if datetime.datetime.fromtimestamp(p['open_time']).strftime('%Y-%m-%d') == filter_date]
        closed_trades = [t for t in closed_trades if datetime.datetime.fromtimestamp(t['open_time']).strftime('%Y-%m-%d') == filter_date]
    if filter_strategy:
        open_positions = [p for p in open_positions if p.get('strategy', '') == filter_strategy]
        closed_trades = [t for t in closed_trades if t.get('strategy', '') == filter_strategy]
    # Analytics
    total = len(closed_trades)
    wins = sum(1 for t in closed_trades if t.get('pnl', 0) > 0)
    losses = sum(1 for t in closed_trades if t.get('pnl', 0) < 0)
    total_pnl = sum(t.get('pnl', 0) for t in closed_trades)
    win_rate = (wins / total * 100) if total else 0
    avg_pnl = (total_pnl / total) if total else 0
    max_drawdown = 0
    peak = balance
    # --- New analytics ---
    win_trades = [t for t in closed_trades if t.get('pnl', 0) > 0]
    loss_trades = [t for t in closed_trades if t.get('pnl', 0) < 0]
    avg_win = sum(t.get('pnl', 0) for t in win_trades) / len(win_trades) if win_trades else 0
    avg_loss = sum(t.get('pnl', 0) for t in loss_trades) / len(loss_trades) if loss_trades else 0
    profit_factor = (sum(t.get('pnl', 0) for t in win_trades) / abs(sum(t.get('pnl', 0) for t in loss_trades))) if loss_trades else 0
    largest_win = max((t.get('pnl', 0) for t in closed_trades), default=0)
    largest_loss = min((t.get('pnl', 0) for t in closed_trades), default=0)
    expectancy = (win_rate/100 * avg_win + (1 - win_rate/100) * avg_loss) if total else 0
    # Trade duration stats
    durations = [(t.get('close_time', 0) - t.get('open_time', 0)) for t in closed_trades if t.get('close_time') and t.get('open_time')]
    avg_duration = sum(durations) / len(durations) if durations else 0
    max_duration = max(durations) if durations else 0
    min_duration = min(durations) if durations else 0
    # P&L by symbol and strategy
    pnl_by_symbol = defaultdict(float)
    pnl_by_strategy = defaultdict(float)
    for t in closed_trades:
        pnl_by_symbol[t['symbol']] += t.get('pnl', 0)
        pnl_by_strategy[t.get('strategy', 'N/A')] += t.get('pnl', 0)
    # --- End new analytics ---
    for h in history:
        if h['equity'] > peak:
            peak = h['equity']
        dd = (peak - h['equity'])
        if dd > max_drawdown:
            max_drawdown = dd
    # Sharpe ratio (simple)
    returns = [history[i]['equity'] - history[i-1]['equity'] for i in range(1, len(history))]
    mean_return = sum(returns) / len(returns) if returns else 0
    std_return = (sum((r - mean_return) ** 2 for r in returns) / len(returns)) ** 0.5 if returns else 0
    sharpe = (mean_return / std_return) * (252 ** 0.5) if std_return else 0
    analytics = {
        'total_trades': total,
        'wins': wins,
        'losses': losses,
        'win_rate': f'{win_rate:.1f}%',
        'total_pnl': f'{total_pnl:.2f}',
        'avg_pnl': f'{avg_pnl:.2f}',
        'max_drawdown': f'{max_drawdown:.2f}',
        'sharpe_ratio': f'{sharpe:.2f}',
        # New metrics
        'avg_win': f'{avg_win:.2f}',
        'avg_loss': f'{avg_loss:.2f}',
        'profit_factor': f'{profit_factor:.2f}',
        'largest_win': f'{largest_win:.2f}',
        'largest_loss': f'{largest_loss:.2f}',
        'expectancy': f'{expectancy:.2f}',
        'avg_duration': f'{avg_duration/60:.2f} min',
        'max_duration': f'{max_duration/60:.2f} min',
        'min_duration': f'{min_duration/60:.2f} min',
    }
    # Pass breakdowns for charts
    pnl_by_symbol = dict(pnl_by_symbol)
    pnl_by_strategy = dict(pnl_by_strategy)
    # Paper trading toggle (read from config or status file)
    if os.path.exists('config.py'):
        with open('config.py', 'r') as f:
            for line in f:
                if line.strip().startswith('PAPER_TRADING'):
                    paper_trading = 'True' in line.split('=')[1]
    return render_template_string(PAPER_TEMPLATE, open_positions=open_positions, closed_trades=closed_trades, balance=balance, equity=equity, history=history, equity_curve=history, analytics=analytics, filter_symbol=filter_symbol, filter_date=filter_date, filter_strategy=filter_strategy, paper_trading=paper_trading, pnl_by_symbol=pnl_by_symbol, pnl_by_strategy=pnl_by_strategy, closed_pnl_list=[t.get('pnl', 0) for t in closed_trades], win_count=wins, loss_count=losses)

@app.route('/toggle_paper', methods=['POST'])
@requires_auth
def toggle_paper():
    # Toggle PAPER_TRADING in config.py
    val = 'True' if request.form.get('paper') else 'False'
    lines = []
    with open('config.py', 'r') as f:
        for line in f:
            if line.strip().startswith('PAPER_TRADING'):
                lines.append(f'PAPER_TRADING = {val}\n')
            else:
                lines.append(line)
    with open('config.py', 'w') as f:
        f.writelines(lines)
    return ('', 204)

@app.route('/api/paper_trades', methods=['GET'])
@requires_auth
def api_paper_trades():
    # Return all paper trades (optionally filtered)
    symbol = request.args.get('symbol', '').upper()
    with open(PAPER_TRADES_FILE, 'r') as f:
        state = json.load(f)
    trades = state.get('closed_trades', [])
    if symbol:
        trades = [t for t in trades if t['symbol'] == symbol]
    return json.dumps(trades)

@app.route('/api/paper_trades/clear', methods=['GET', 'POST'])
@requires_auth
def api_paper_trades_clear():
    # Clear all paper trades
    if os.path.exists(PAPER_TRADES_FILE):
        with open(PAPER_TRADES_FILE, 'w') as f:
            json.dump({'open_positions': [], 'closed_trades': [], 'balance': 10000, 'equity': 10000, 'history': []}, f) # Assuming a default balance/equity for clearing
    return ('', 204)

@app.route('/api/paper_trades/export', methods=['GET'])
@requires_auth
def api_paper_trades_export():
    # Export closed trades as CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['symbol', 'side', 'open_price', 'close_price', 'lot_size', 'pnl', 'open_time', 'close_time'])
    if os.path.exists(PAPER_TRADES_FILE):
        with open(PAPER_TRADES_FILE, 'r') as f:
            state = json.load(f)
            for t in state.get('closed_trades', []):
                writer.writerow([
                    t['symbol'],
                    'BUY' if t['signal'] > 0 else 'SELL',
                    t['open_price'],
                    t.get('close_price', ''),
                    t['lot_size'],
                    t.get('pnl', ''),
                    parse_datetime(t['open_time']),
                    parse_datetime(t.get('close_time', 0))
                ])
    output.seek(0)
    return Response(output, mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=paper_trades.csv'})

if __name__ == '__main__':
    print("\n[INFO] Starting AlgoBot Dashboard on http://127.0.0.1:5000/")
    print("[INFO] Make sure your bot writes status to bot_status.json!")
    app.run(debug=False, port=5000) 