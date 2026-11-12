"""Chartink webhook receiver. No broker orders or credentials in source."""
import hmac
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, jsonify, request

app = Flask(__name__)
DB = Path(os.environ.get('ALERTS_DB', '/tmp/chartink_alerts.db'))
SECRET = os.environ.get('CHARTINK_WEBHOOK_SECRET', '')
READ_SECRET = os.environ.get('CHARTINK_READ_SECRET', '')
MAX_BODY = 64 * 1024
app.config['MAX_CONTENT_LENGTH'] = MAX_BODY
SYMBOL = re.compile(r'^[A-Z0-9][A-Z0-9._&-]{0,39}$')

def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=10000')
    conn.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        received_at TEXT NOT NULL,
        scan_name TEXT NOT NULL,
        triggered_at TEXT,
        symbol TEXT NOT NULL,
        trigger_price REAL,
        UNIQUE(scan_name, triggered_at, symbol)
    )''')
    conn.commit()
    return conn

def authorized(expected, supplied):
    return bool(expected) and bool(supplied) and hmac.compare_digest(expected, supplied)

def split_values(value):
    if isinstance(value, list):
        return [str(x).strip() for x in value]
    return [x.strip() for x in str(value or '').split(',')]

@app.get('/')
def health():
    return jsonify(status='running')

@app.post('/chartink-webhook/<secret>')
def chartink_webhook(secret):
    if not authorized(SECRET, secret):
        return jsonify(error='unauthorized'), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = request.form.to_dict()
    if not isinstance(data, dict):
        return jsonify(error='invalid payload'), 400
    scan = str(data.get('scan_name', '')).strip()[:120]
    if not scan:
        return jsonify(error='scan_name required'), 400
    triggered = str(data.get('triggered_at', '')).strip()[:100]
    stocks = split_values(data.get('stocks'))
    prices = split_values(data.get('trigger_prices'))
    if not stocks or not any(stocks) or len(stocks) > 500:
        return jsonify(error='invalid stock list'), 400
    parsed = []
    for index, raw in enumerate(stocks):
        symbol = raw.upper().removeprefix('NSE:')
        if not SYMBOL.fullmatch(symbol):
            return jsonify(error='invalid stock symbol'), 400
        raw_price = prices[index] if index < len(prices) else ''
        try:
            price = float(raw_price) if raw_price else None
            if price is not None and not (0 < price < 1e9):
                price = None
        except (ValueError, TypeError):
            price = None
        parsed.append((symbol, price))
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        before = conn.total_changes
        conn.executemany('''INSERT OR IGNORE INTO alerts
            (received_at, scan_name, triggered_at, symbol, trigger_price)
            VALUES (?, ?, ?, ?, ?)''',
            [(now, scan, triggered, symbol, price) for symbol, price in parsed])
        stored = conn.total_changes - before
    return jsonify(status='ok', received=len(parsed), stored=stored), 200

@app.get('/alerts')
def alerts():
    if not authorized(READ_SECRET, request.headers.get('X-Read-Token', '')):
        return jsonify(error='unauthorized'), 401
    try:
        limit = max(1, min(1000, int(request.args.get('limit', '500'))))
    except ValueError:
        return jsonify(error='invalid limit'), 400
    with connect() as conn:
        rows = conn.execute('SELECT * FROM alerts ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    return jsonify([dict(row) for row in rows])

if __name__ == '__main__':
    if not SECRET or not READ_SECRET:
        raise SystemExit('Set CHARTINK_WEBHOOK_SECRET and CHARTINK_READ_SECRET')
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', '5000')))
