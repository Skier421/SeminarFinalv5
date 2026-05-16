"""
SeminarFinal_v5.1 - Stock Market Simulator
Production-Ready Flask Application for Render Free Tier
"""

import os
import random
import string
import time
import threading
import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room

from models import Room, Player, init_db
from data_engine import data_engine
from game_clock import clock_manager
from headlines_data import HEADLINES_BY_YEAR, get_headline_for_year, get_headline_for_date, get_headline_sentiment

# Constants
DEFAULT_START_DATE = '1928-01-03'

# Initialize Flask app
app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'seminarfinal-secret-key-v2-1')

# Version for cache invalidation
APP_VERSION = '5.1'

# Initialize SocketIO with explicit threading mode
socketio = SocketIO(
    app,
    async_mode='threading',
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True
)

# Game state tracking
ROOM_USER_SIDS = {}
SOCKET_ROOM_MAP = {}
SID_USER_MAP = {}
ROOM_HEADLINE_META = {}
ROOM_GAME_OVER_SENT = set()
ROOM_REUBEN_SENT = set()
ROOM_SP500_LAUNCH_SENT = set()
ROOM_CURRENT_PRICES = {}
AUDIT_WINDOW_SECONDS = 20
RUMOR_LEAD_TICKS = 10
INSIDER_AUDIT_CHANCE = 0.75
INSIDER_CASH_PENALTY = 0.60

# Per-room game thread management
ROOM_GAME_THREADS = {}
ROOM_THREAD_LOCKS = {}

# Insider trigger dates with specific advice (one-shot rule)
INSIDER_TIPS = {
    '1929-10-15': 'Market is a bubble. SELL EVERYTHING now.',
    '1932-06-01': 'The bottom is in. BUY A LOT. Prices will never be this low again.',
    '1973-01-10': 'Oil crisis is starting. SELL EVERYTHING before the 50% crash.',
    '1982-08-01': 'Interest rates are dropping. BUY A LOT. The greatest bull market in history starts now.',
    '1987-10-12': 'Black Monday is coming. SELL EVERYTHING.',
    '2008-01-15': 'Housing market is dead. SELL EVERYTHING.',
    '1928-01-02': 'TEST TIP: This is a test to verify the Noir popup works correctly.'
}

# Initialize database
if not os.path.exists('stock_simulator.db'):
    init_db()

# Clear cache to ensure new MASTER_HISTORY data is used
if os.path.exists('stock_data_cache.json'):
    print("Clearing old cache stock_data_cache.json...")
    os.remove('stock_data_cache.json')


def generate_room_code(length: int = 5) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def get_price_with_lookback(ticker: str, date_str: str) -> float:
    """
    Fetch a price with weekend/holiday lookback logic.
    If the exact date has no data, look backward up to 7 days.
    Returns a hardcoded fallback if nothing works.
    """
    price = data_engine.get_price(ticker, date_str)
    if price is not None:
        return price

    current = datetime.datetime.strptime(date_str, '%Y-%m-%d')
    for lookback in range(1, 8):
        fallback = current - datetime.timedelta(days=lookback)
        fallback_str = fallback.strftime('%Y-%m-%d')
        price = data_engine.get_price(ticker, fallback_str)
        if price is not None:
            return price

    if ticker == '^DJI':
        return 200.0
    if ticker == '^GSPC':
        return 15.0
    return 100.0


def calculate_next_price(base_price: float) -> float:
    """Apply random variance to a base price to simulate market volatility."""
    if base_price is None or base_price != base_price or base_price <= 0:
        return base_price
    price = base_price * (1 + random.uniform(-0.05, 0.05))
    return round(price, 2)


def broadcast_leaderboard(room_code: str):
    players = Player.get_all_in_room(room_code)
    clock = clock_manager.get_clock(room_code)
    current_prices = ROOM_CURRENT_PRICES.get(room_code, {})
    prices = {
        '^DJI': current_prices.get('^DJI') or get_price_with_lookback('^DJI', clock.current_date),
        '^GSPC': current_prices.get('^GSPC') or get_price_with_lookback('^GSPC', clock.current_date)
    }

    leaderboard = []
    for player in players:
        if player.is_admin:
            continue
        leaderboard.append(player.to_dict(prices))

    leaderboard.sort(key=lambda x: x['net_worth'], reverse=True)
    for i, entry in enumerate(leaderboard):
        entry['rank'] = i + 1

    socketio.emit('leaderboard_update', {'leaderboard': leaderboard}, room=room_code)


def build_final_leaderboard(room_code: str, prices: dict):
    players = Player.get_all_in_room(room_code)
    leaderboard = [player.to_dict(prices) for player in players if not player.is_admin]
    leaderboard.sort(key=lambda x: x['net_worth'], reverse=True)
    for i, entry in enumerate(leaderboard):
        entry['rank'] = i + 1
    return leaderboard


def emit_game_over(room_code: str, current_date: str, prices: dict):
    if room_code in ROOM_GAME_OVER_SENT:
        return

    ROOM_GAME_OVER_SENT.add(room_code)
    leaderboard = build_final_leaderboard(room_code, prices)
    socketio.emit('leaderboard_update', {'leaderboard': leaderboard}, room=room_code)

    for entry in leaderboard:
        sid = ROOM_USER_SIDS.get(room_code, {}).get(entry['username'])
        if sid:
            socketio.emit('game_over', {
                'current_date': current_date,
                'rank': entry['rank'],
                'total_players': len(leaderboard),
                'net_worth': round(entry['net_worth'], 2),
                'leaderboard': leaderboard
            }, room=sid)


def run_game_loop(app_instance, room_code: str):
    """
    Native Python threading game loop bound within Flask app context.
    Advances dates, fetches prices with lookback, and broadcasts updates.
    """
    with app_instance.app_context():
        try:
            while True:
                lock = ROOM_THREAD_LOCKS.get(room_code)
                if lock is None:
                    print(f"DEBUG: No lock for room {room_code}, exiting loop")
                    break

                with lock:
                    clock = clock_manager.get_clock(room_code)
                    if clock.game_state != 'playing':
                        print(f"DEBUG: Game not playing for room {room_code}, exiting loop")
                        break

                print('--- TICK ---')

                clock._advance_time()
                current_date_str = clock.current_date

                dji_base = get_price_with_lookback('^DJI', current_date_str)
                gspc_base = get_price_with_lookback('^GSPC', current_date_str)
                dji_p = calculate_next_price(dji_base)
                gspc_p = calculate_next_price(gspc_base)
                ROOM_CURRENT_PRICES[room_code] = {'^DJI': dji_p, '^GSPC': gspc_p}

                room = Room.get(room_code)
                if room and room.current_date != current_date_str:
                    room.update_date(current_date_str)

                if current_date_str >= '2026-12-31':
                    clock.game_state = 'paused'
                    if room:
                        room.set_state('paused')
                    prices = {'^DJI': dji_p, '^GSPC': gspc_p}
                    emit_game_over(room_code, current_date_str, prices)
                    break

                tick_payload = {
                    'game_date': current_date_str,
                    'dji_price': dji_p
                }
                if current_date_str >= '1957-03-04':
                    tick_payload['gspc_price'] = gspc_p
                socketio.emit('game_tick', tick_payload, room=room_code)

                broadcast_game_state(room_code)
                broadcast_leaderboard(room_code)

                time.sleep(1.0)
        except Exception as e:
            print(f"CRITICAL: Game loop thread crashed for room {room_code}: {e}")
            import traceback
            traceback.print_exc()


def broadcast_game_state(room_code: str):
    clock = clock_manager.get_clock(room_code)
    room = Room.get(room_code)
    if not room:
        return

    headline_text = get_headline_for_date(clock.current_date) or get_headline_for_year(int(clock.current_date[:4]))
    current_prices = ROOM_CURRENT_PRICES.get(room_code, {})
    dji_p = current_prices.get('^DJI') or get_price_with_lookback('^DJI', clock.current_date)
    gspc_p = current_prices.get('^GSPC') or get_price_with_lookback('^GSPC', clock.current_date)
    post_ipo = clock.current_date >= '1957-03-04'

    for username, sid in ROOM_USER_SIDS.get(room_code, {}).items():
        player = Player.get(room_code, username)
        if not player:
            continue

        prices_payload = {'^DJI': dji_p}
        if post_ipo:
            prices_payload['^GSPC'] = gspc_p

        if player.is_admin:
            user_state = {
                'current_date': clock.current_date,
                'game_state': clock.game_state,
                'headline': headline_text,
                'prices': prices_payload,
                'tickers': ['^DJI', '^GSPC'],
                'company_names': {
                    '^DJI': 'Dow Jones Industrial Average',
                    '^GSPC': 'S&P 500'
                }
            }
        else:
            holdings_value = sum(
                get_price_with_lookback(ticker, clock.current_date) * shares
                for ticker, shares in player.holdings.items()
            )
            net_worth = player.cash + holdings_value
            user_state = {
                'current_date': clock.current_date,
                'game_state': clock.game_state,
                'headline': headline_text,
                'prices': prices_payload,
                'cash': round(player.cash, 2),
                'holdings': player.holdings,
                'holdings_value': round(holdings_value, 2),
                'net_worth': round(net_worth, 2),
                'tickers': ['^DJI', '^GSPC'],
                'company_names': {
                    '^DJI': 'Dow Jones Industrial Average',
                    '^GSPC': 'S&P 500'
                }
            }

        socketio.emit('game_state_update', user_state, room=sid)

    current_year = int(clock.current_date[:4])

    if clock.current_date >= '1990-01-01' and room_code not in ROOM_REUBEN_SENT:
        ROOM_REUBEN_SENT.add(room_code)
        socketio.emit('market_event', {
            'type': 'reuben_born',
            'message': 'Reuben Seidl is born! 🍺🍺🍺',
            'date': clock.current_date
        }, room=room_code)

    if clock.current_date >= '1957-03-04' and room_code not in ROOM_SP500_LAUNCH_SENT:
        ROOM_SP500_LAUNCH_SENT.add(room_code)
        socketio.emit('market_event', {
            'type': 'sp500_launch',
            'message': "FINANCIAL MILESTONE: Standard & Poor's launches the 500 Stock Index.",
            'date': clock.current_date
        }, room=room_code)

    if clock.current_date in INSIDER_TIPS:
        for username, sid in ROOM_USER_SIDS.get(room_code, {}).items():
            player = Player.get(room_code, username)
            if player and not player.has_used_insider_tip:
                player.has_used_insider_tip = True
                player.save()
                socketio.emit('insider_tip', {
                    'tip': INSIDER_TIPS[clock.current_date],
                    'message': 'CLASSIFIED INFORMATION: You only get one tip per game. Use it wisely.'
                }, room=sid)

    insider_rumor = get_insider_rumor(clock.current_date)
    if insider_rumor:
        for username, sid in ROOM_USER_SIDS.get(room_code, {}).items():
            socketio.emit('insider_opportunity', {
                'available': True,
                'message': 'Insider rumor available. Viewing it carries a 75% SEC audit risk.'
            }, room=sid)


def get_next_headline_year(current_year: int) -> int:
    years = sorted(HEADLINES_BY_YEAR.keys())
    for year in years:
        if year > current_year:
            return year
    return None


def get_insider_rumor(current_date: str):
    current_year = int(current_date[:4])
    current_month = int(current_date[5:7])
    next_year = get_next_headline_year(current_year)
    if not next_year:
        active_ticker = '^GSPC' if current_date >= '1957-03-01' else '^DJI'
        current_price = get_price_with_lookback(active_ticker, current_date)
        if current_price:
            return f"Pssst... Insider chatter: the market is nearing the present day with {active_ticker} around ${current_price:,.2f}."
        return "Pssst... Insider chatter: the market is nearing the present day."

    months_until = (next_year - current_year) * 12 - (current_month - 1)
    ticks_until = max(0, (months_until + 2) // 3)
    sentiment = get_headline_sentiment(next_year)
    action = 'BUY NOW' if sentiment == 'buy' else 'SELL NOW'
    if ticks_until <= RUMOR_LEAD_TICKS:
        return f"Pssst... {get_headline_for_year(next_year)} — {action}"
    return f"Pssst... Insider chatter points toward a major market headline in {next_year}: {get_headline_for_year(next_year)} — {action}"


@socketio.on('join_room')
def handle_join_room(data):
    try:
        room_code = data.get('room_code', '').upper()
        username = data.get('username', '').strip()
        print(f"DEBUG: Join room request - room_code={room_code}, username={username}")
        if not room_code or not username:
            emit('error', {'message': 'Room code and username required'})
            return

        if not Room.exists(room_code):
            emit('error', {'message': 'Room not found'})
            return

        player = Player.get(room_code, username)
        if not player:
            print(f"DEBUG: Player {username} not found, creating new player")
            player = Player.create(room_code, username)
            print(f"DEBUG: Player created with cash={player.cash}")
        else:
            print(f"DEBUG: Player {username} found with cash={player.cash}")

        if player.cash is None or player.cash == 0:
            player.cash = 1000.0
            player.save()
            print(f"DEBUG: Forced cash injection to 1000.0 for {username}")

        join_room(room_code)
        ROOM_USER_SIDS.setdefault(room_code, {})[player.username] = request.sid
        SOCKET_ROOM_MAP[request.sid] = room_code
        SID_USER_MAP[request.sid] = player.username

        session['room_code'] = room_code
        session['username'] = player.username
        session['is_admin'] = player.is_admin

        clock = clock_manager.get_clock(room_code)
        room = Room.get(room_code)
        if room:
            clock.set_date(room.current_date)
            clock.game_state = room.game_state

        emit('joined_room', {
            'room_code': room_code,
            'username': player.username,
            'is_admin': player.is_admin,
            'is_insider': player.is_insider,
            'tickers': ['^DJI', '^GSPC']
        })

        holdings_value = player.get_holdings_value({
            '^DJI': get_price_with_lookback('^DJI', clock.current_date),
            '^GSPC': get_price_with_lookback('^GSPC', clock.current_date)
        })
        net_worth = player.cash + holdings_value
        socketio.emit('portfolio_update', {
            'cash': round(player.cash, 2),
            'net_worth': round(net_worth, 2),
            'holdings': player.holdings,
            'holdings_value': round(holdings_value, 2)
        }, room=request.sid)

        broadcast_game_state(room_code)
        broadcast_leaderboard(room_code)

    except Exception as e:
        print(f"ERROR in join_room: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error joining room: {str(e)}'})


@socketio.on('execute_buy')
def handle_execute_buy(data):
    sid = request.sid
    room_code = SOCKET_ROOM_MAP.get(sid)
    username = SID_USER_MAP.get(sid)
    if not room_code or not username:
        emit('error', {'message': 'Not in a room'})
        return

    ticker = data.get('ticker')
    try:
        amount = float(data.get('amount', 0))
    except (TypeError, ValueError):
        emit('error', {'message': 'Invalid amount'})
        return

    if not ticker or amount <= 0:
        emit('error', {'message': 'Invalid ticker or amount'})
        return

    if ticker not in ['^DJI', '^GSPC']:
        emit('error', {'message': 'Invalid ticker'})
        return

    clock = clock_manager.get_clock(room_code)
    current_prices = ROOM_CURRENT_PRICES.get(room_code, {})
    price = current_prices.get(ticker) or get_price_with_lookback(ticker, clock.current_date)

    shares = round(amount / price, 8)
    if shares <= 0:
        emit('error', {'message': 'Amount too small'})
        return

    player = Player.get(room_code, username)
    print(f"DEBUG execute_buy BEFORE: {username} cash={player.cash}, buying {shares} shares of {ticker} at {price} for ${amount}")
    if player.buy(ticker, shares, price, amount):
        print(f"DEBUG execute_buy AFTER: {username} cash={player.cash}, holdings={player.holdings}")
        emit('trade_success', {
            'action': 'buy',
            'ticker': ticker,
            'shares': shares,
            'price': price,
            'total': round(amount, 2)
        })

        current_prices = ROOM_CURRENT_PRICES.get(room_code, {})
        holdings_value = player.get_holdings_value({
            '^DJI': current_prices.get('^DJI') or get_price_with_lookback('^DJI', clock.current_date),
            '^GSPC': current_prices.get('^GSPC') or get_price_with_lookback('^GSPC', clock.current_date)
        })
        net_worth = player.cash + holdings_value
        emit('portfolio_update', {
            'cash': round(player.cash, 2),
            'net_worth': round(net_worth, 2),
            'holdings': player.holdings,
            'holdings_value': round(holdings_value, 2)
        })

        broadcast_leaderboard(room_code)
    else:
        print(f"DEBUG execute_buy FAILED: {username} insufficient funds. cash={player.cash}, cost={amount}")
        emit('error', {'message': 'Insufficient funds'})


@socketio.on('execute_sell')
def handle_execute_sell(data):
    sid = request.sid
    room_code = SOCKET_ROOM_MAP.get(sid)
    username = SID_USER_MAP.get(sid)
    if not room_code or not username:
        emit('error', {'message': 'Not in a room'})
        return

    ticker = data.get('ticker')
    try:
        shares = float(data.get('shares', 0))
    except (TypeError, ValueError):
        emit('error', {'message': 'Invalid shares'})
        return

    if not ticker or shares <= 0:
        emit('error', {'message': 'Invalid ticker or shares'})
        return

    if ticker not in ['^DJI', '^GSPC']:
        emit('error', {'message': 'Invalid ticker'})
        return

    clock = clock_manager.get_clock(room_code)
    current_prices = ROOM_CURRENT_PRICES.get(room_code, {})
    price = current_prices.get(ticker) or get_price_with_lookback(ticker, clock.current_date)

    player = Player.get(room_code, username)
    print(f"DEBUG execute_sell BEFORE: {username} cash={player.cash}, selling {shares} shares of {ticker} at {price}")
    if player.sell(ticker, shares, price):
        print(f"DEBUG execute_sell AFTER: {username} cash={player.cash}, holdings={player.holdings}")
        emit('trade_success', {
            'action': 'sell',
            'ticker': ticker,
            'shares': shares,
            'price': price,
            'total': round(shares * price, 2)
        })

        current_prices = ROOM_CURRENT_PRICES.get(room_code, {})
        holdings_value = player.get_holdings_value({
            '^DJI': current_prices.get('^DJI') or get_price_with_lookback('^DJI', clock.current_date),
            '^GSPC': current_prices.get('^GSPC') or get_price_with_lookback('^GSPC', clock.current_date)
        })
        net_worth = player.cash + holdings_value
        emit('portfolio_update', {
            'cash': round(player.cash, 2),
            'net_worth': round(net_worth, 2),
            'holdings': player.holdings,
            'holdings_value': round(holdings_value, 2)
        })

        broadcast_leaderboard(room_code)
    else:
        print(f"DEBUG execute_sell FAILED: {username} insufficient shares. holdings={player.holdings}")
        emit('error', {'message': 'Insufficient shares'})


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    room_code = SOCKET_ROOM_MAP.pop(sid, None)
    username = SID_USER_MAP.pop(sid, None)
    if room_code and username and room_code in ROOM_USER_SIDS:
        ROOM_USER_SIDS[room_code].pop(username, None)


@socketio.on('toggle_game')
def handle_toggle_game():
    sid = request.sid
    room_code = SOCKET_ROOM_MAP.get(sid)
    username = SID_USER_MAP.get(sid)
    print(f"DEBUG toggle_game: sid={sid}, room={room_code}, user={username}")
    if not room_code or not username:
        emit('error', {'message': 'Not authenticated. Please refresh and rejoin.'})
        return

    player = Player.get(room_code, username)
    if not player or not player.is_admin:
        emit('error', {'message': 'Admin only'})
        return

    room = Room.get(room_code)
    if not room:
        return

    clock = clock_manager.get_clock(room_code)
    new_state = 'playing' if room.game_state == 'paused' else 'paused'
    room.set_state(new_state)
    clock.game_state = new_state

    socketio.emit('game_state_update', {'playing': new_state == 'playing'})

    if new_state == 'playing':
        if room_code not in ROOM_THREAD_LOCKS:
            ROOM_THREAD_LOCKS[room_code] = threading.Lock()

        with ROOM_THREAD_LOCKS[room_code]:
            thread = ROOM_GAME_THREADS.get(room_code)
            if thread is None or not thread.is_alive():
                ROOM_GAME_THREADS[room_code] = threading.Thread(
                    target=run_game_loop,
                    args=(app, room_code)
                )
                ROOM_GAME_THREADS[room_code].daemon = True
                ROOM_GAME_THREADS[room_code].start()
                print(f"DEBUG: Started game loop thread for room {room_code}")
    else:
        print(f"DEBUG: Paused game for room {room_code}")

    broadcast_game_state(room_code)


@socketio.on('admin_set_date')
def handle_set_date(data=None):
    sid = request.sid
    room_code = SOCKET_ROOM_MAP.get(sid)
    username = SID_USER_MAP.get(sid)
    if not room_code or not username:
        return

    player = Player.get(room_code, username)
    if not player or not player.is_admin:
        emit('error', {'message': 'Admin only'})
        return

    new_date = (data or {}).get('date')
    if not new_date:
        return

    room = Room.get(room_code)
    if not room:
        return

    room.update_date(new_date)
    clock = clock_manager.get_clock(room_code)
    clock.set_date(new_date)
    ROOM_GAME_OVER_SENT.discard(room_code)
    if new_date < '1990-01-01':
        ROOM_REUBEN_SENT.discard(room_code)

    broadcast_game_state(room_code)
    broadcast_leaderboard(room_code)


@socketio.on('admin_reset')
def handle_reset(data=None):
    sid = request.sid
    room_code = SOCKET_ROOM_MAP.get(sid)
    username = SID_USER_MAP.get(sid)
    if not room_code or not username:
        return

    player = Player.get(room_code, username)
    if not player or not player.is_admin:
        emit('error', {'message': 'Admin only'})
        return

    room = Room.get(room_code)
    if not room:
        return

    start_date = DEFAULT_START_DATE
    room.update_date(start_date)
    room.set_state('paused')

    clock = clock_manager.get_clock(room_code)
    clock.reset(start_date)
    ROOM_GAME_OVER_SENT.discard(room_code)
    ROOM_REUBEN_SENT.discard(room_code)
    ROOM_SP500_LAUNCH_SENT.discard(room_code)
    ROOM_CURRENT_PRICES.pop(room_code, None)
    for room_player in Player.get_all_in_room(room_code):
        room_player.is_insider = False
        room_player.has_used_insider_tip = False
        room_player.save()

    broadcast_game_state(room_code)
    broadcast_leaderboard(room_code)


@socketio.on('admin_set_insider')
def handle_set_insider(data=None):
    sid = request.sid
    room_code = SOCKET_ROOM_MAP.get(sid)
    username = SID_USER_MAP.get(sid)
    if not room_code or not username:
        return

    player = Player.get(room_code, username)
    if not player or not player.is_admin:
        emit('error', {'message': 'Admin only'})
        return

    target_username = (data or {}).get('username', '').strip()
    target_insider = bool((data or {}).get('is_insider', True))
    if not target_username:
        emit('error', {'message': 'Username required'})
        return

    target_player = Player.get(room_code, target_username)
    if not target_player:
        emit('error', {'message': 'Player not found'})
        return

    if target_insider and room_code in ROOM_USER_SIDS and target_username in ROOM_USER_SIDS[room_code]:
        target_sid = ROOM_USER_SIDS[room_code][target_username]
        socketio.emit('insider_status_updated', {
            'message': 'You have been granted insider access.',
            'is_insider': True
        }, room=target_sid)

    target_player.set_insider(target_insider)
    broadcast_game_state(room_code)
    broadcast_leaderboard(room_code)


@socketio.on('request_insider_rumor')
def handle_request_insider_rumor():
    sid = request.sid
    room_code = SOCKET_ROOM_MAP.get(sid)
    username = SID_USER_MAP.get(sid)
    if not room_code or not username:
        emit('error', {'message': 'Not in a room'})
        return

    player = Player.get(room_code, username)
    if not player:
        emit('error', {'message': 'Player not found'})
        return

    clock = clock_manager.get_clock(room_code)
    rumor_text = get_insider_rumor(clock.current_date)
    if not rumor_text:
        emit('insider_opportunity', {
            'available': False,
            'message': 'No insider rumor is available right now.'
        })
        return

    player.is_insider = False
    player.save()

    emit('insider_rumor', {
        'headline': rumor_text,
        'message': 'Insider rumor'
    })

    if random.random() < INSIDER_AUDIT_CHANCE:
        penalty = round(player.cash * INSIDER_CASH_PENALTY, 2)
        player.cash = round(player.cash - penalty, 2)
        player.save()
        prices = {
            '^DJI': get_price_with_lookback('^DJI', clock.current_date),
            '^GSPC': get_price_with_lookback('^GSPC', clock.current_date)
        }
        holdings_value = player.get_holdings_value(prices)
        net_worth = player.cash + holdings_value
        emit('sec_penalty', {
            'message': 'SEC ENFORCEMENT: You were audited after viewing insider information. 60% of your cash was seized.',
            'penalty': penalty,
            'cash_remaining': player.cash
        })
        emit('portfolio_update', {
            'cash': round(player.cash, 2),
            'holdings': player.holdings,
            'holdings_value': holdings_value,
            'net_worth': round(net_worth, 2)
        })
        broadcast_leaderboard(room_code)
    else:
        emit('info', {'message': 'You avoided an SEC audit this time.'})

    emit('insider_opportunity', {
        'available': True,
        'message': 'Another insider rumor will be available as the market updates.'
    })


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/create_room', methods=['POST'])
def create_room():
    username = request.form.get('username', '').strip()
    if not username:
        return render_template('index.html', error='Username required')

    room_code = generate_room_code()
    while Room.exists(room_code):
        room_code = generate_room_code()

    Room.create(room_code, DEFAULT_START_DATE)
    Player.create(room_code, username, is_admin=True)
    clock_manager.get_clock(room_code).set_date(DEFAULT_START_DATE)
    return redirect(url_for('dashboard', room_code=room_code, username=username))


@app.route('/join_room', methods=['POST'])
def join_room_route():
    room_code = request.form.get('room_code', '').upper().strip()
    username = request.form.get('username', '').strip()
    if not room_code or not username:
        return render_template('index.html', error='Room code and username required')
    if not Room.exists(room_code):
        return render_template('index.html', error='Room not found')
    return redirect(url_for('dashboard', room_code=room_code, username=username))


@app.route('/dashboard')
def dashboard():
    room_code = request.args.get('room_code', '').upper()
    username = request.args.get('username', '')
    if not room_code or not username:
        return redirect(url_for('index'))
    if not Room.exists(room_code):
        return redirect(url_for('index'))

    room = Room.get(room_code)
    player = Player.get(room_code, username)
    if not player:
        player = Player.create(room_code, username)

    session['room_code'] = room_code
    session['username'] = username
    session['is_admin'] = player.is_admin

    min_date, max_date = data_engine.get_date_range()
    return render_template(
        'dashboard.html',
        room_code=room_code,
        username=username,
        is_admin=player.is_admin,
        is_insider=player.is_insider,
        start_date=room.current_date if room else DEFAULT_START_DATE,
        min_date=min_date,
        max_date=max_date,
        tickers=['^DJI', '^GSPC'],
        company_names={
            '^DJI': 'Dow Jones Industrial Average',
            '^GSPC': 'S&P 500'
        }
    )


@app.route('/api/room/<room_code>')
def get_room_info(room_code):
    room = Room.get(room_code.upper())
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    clock = clock_manager.get_clock(room_code)
    prices = {
        '^DJI': get_price_with_lookback('^DJI', clock.current_date),
        '^GSPC': get_price_with_lookback('^GSPC', clock.current_date)
    }
    return jsonify({
        'room_code': room.code,
        'start_date': room.start_date,
        'current_date': room.current_date,
        'game_state': room.game_state,
        'prices': prices
    })


@app.route('/api/player/<room_code>/<username>')
def get_player_info(room_code, username):
    player = Player.get(room_code.upper(), username)
    if not player:
        return jsonify({'error': 'Player not found'}), 404
    clock = clock_manager.get_clock(room_code)
    prices = {
        '^DJI': get_price_with_lookback('^DJI', clock.current_date),
        '^GSPC': get_price_with_lookback('^GSPC', clock.current_date)
    }
    return jsonify(player.to_dict(prices))


@app.route('/api/headline/<int:year>')
def get_headline(year):
    min_year = 1900
    max_year = 2100
    if year < min_year or year > max_year:
        return jsonify({'error': f'Year must be between {min_year} and {max_year}'}), 400
    headline_text = get_headline_for_year(year)
    return jsonify({
        'headline': headline_text,
        'pub_date': f'{year}-01-01',
        'url': None,
        'source': 'Historical Archive',
        'error': None
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, use_reloader=False)
