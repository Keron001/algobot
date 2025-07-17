from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import os
from models import db, User, Trade, Log
import threading
import multiprocessing
from config import SYMBOLS

app = Flask(__name__)
CORS(app)
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///algobot.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
jwt = JWTManager(app)
db.init_app(app)

with app.app_context():
    db.create_all()

user_bots = {}  # user_id: (Process, stop_event)

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    if data is None:
        return jsonify({'msg': 'Missing JSON body'}), 400
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'msg': 'Username and password required'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'msg': 'User already exists'}), 400
    user = User()
    user.username = username
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({'msg': 'User registered successfully'})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    if data is None:
        return jsonify({'msg': 'Missing JSON body'}), 400
    username = data.get('username')
    password = data.get('password')
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'msg': 'Invalid credentials'}), 401
    access_token = create_access_token(identity=user.id)
    return jsonify(access_token=access_token)

@app.route('/mt5', methods=['POST'])
@jwt_required()
def set_mt5():
    user_id = get_jwt_identity()
    data = request.json
    if data is None:
        return jsonify({'msg': 'Missing JSON body'}), 400
    user = User.query.get(user_id)
    if user is None:
        return jsonify({'msg': 'User not found'}), 404
    user.mt5_login = data.get('login')
    user.mt5_password_enc = data.get('password')  # TODO: encrypt in production
    user.mt5_server = data.get('server')
    db.session.commit()
    return jsonify({'msg': 'MT5 credentials updated'})

@app.route('/mt5', methods=['GET'])
@jwt_required()
def get_mt5():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user is None:
        return jsonify({'msg': 'User not found'}), 404
    return jsonify({
        'login': user.mt5_login,
        'password': user.mt5_password_enc,  # TODO: decrypt in production
        'server': user.mt5_server
    })

# --- Trade History Endpoint ---
@app.route('/trades', methods=['GET'])
@jwt_required()
def get_trades():
    user_id = get_jwt_identity()
    trades = Trade.query.filter_by(user_id=user_id).order_by(Trade.timestamp.desc()).all()
    return jsonify([{
        'symbol': t.symbol,
        'type': t.type,
        'volume': t.volume,
        'price': t.price,
        'profit': t.profit,
        'timestamp': t.timestamp.isoformat()
    } for t in trades])

# --- Logs Endpoint ---
@app.route('/logs', methods=['GET'])
@jwt_required()
def get_logs():
    user_id = get_jwt_identity()
    logs = Log.query.filter_by(user_id=user_id).order_by(Log.timestamp.desc()).limit(100).all()
    return jsonify([{
        'message': l.message,
        'level': l.level,
        'timestamp': l.timestamp.isoformat()
    } for l in logs])

# --- Bot Process Management ---
def run_user_bot(user_id):
    # Placeholder: Replace with actual bot logic using user's MT5 credentials
    import time
    while True:
        # Simulate bot activity
        time.sleep(10)
        # Optionally, log activity or update DB
        pass

# --- Start Bot Endpoint ---
@app.route('/start_bot', methods=['POST'])
@jwt_required()
def start_bot():
    user_id = get_jwt_identity()
    if user_id in user_bots and user_bots[user_id][0].is_alive():
        return jsonify({'msg': 'Bot already running'}), 400
    user = User.query.get(user_id)
    if not user or not user.mt5_login or not user.mt5_password_enc or not user.mt5_server:
        return jsonify({'msg': 'MT5 credentials not set'}), 400
    stop_event = multiprocessing.Event()
    def run_bot(user_id, stop_event):
        from enhanced_trader import EnhancedTrader
        user = User.query.get(user_id)
        if user is None:
            import logging
            logging.error(f'User with id {user_id} not found. Bot will not start.')
            return
        trader = EnhancedTrader(
            user_id=user_id,
            mt5_login=user.mt5_login,
            mt5_password=user.mt5_password_enc,
            mt5_server=user.mt5_server
        )
        trader.start_trading_session()
        while not stop_event.is_set():
            for symbol in SYMBOLS:
                trader.process_symbol(symbol)
            stop_event.wait(3600)  # H1 timeframe
        trader.stop_trading_session()
    p = multiprocessing.Process(target=run_bot, args=(user_id, stop_event))
    p.start()
    user_bots[user_id] = (p, stop_event)
    return jsonify({'msg': 'Bot started'})

# --- Stop Bot Endpoint ---
@app.route('/stop_bot', methods=['POST'])
@jwt_required()
def stop_bot():
    user_id = get_jwt_identity()
    if user_id not in user_bots:
        return jsonify({'msg': 'Bot not running'}), 400
    p, stop_event = user_bots[user_id]
    stop_event.set()
    p.join(timeout=10)
    if p.is_alive():
        p.terminate()
    del user_bots[user_id]
    return jsonify({'msg': 'Bot stopped'})

@app.route('/bot/status', methods=['GET'])
@jwt_required()
def bot_status():
    user_id = get_jwt_identity()
    status = user_bots.get(user_id, 'stopped')
    return jsonify({'status': status})

if __name__ == '__main__':
    app.run(debug=True) 