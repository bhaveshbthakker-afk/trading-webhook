from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_FILE = "alerts.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT,
            scan_name TEXT,
            triggered_at TEXT,
            symbol TEXT,
            trigger_price REAL
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.route("/", methods=["GET"])
def home():
    return "Webhook server is running."

@app.route("/chartink-webhook", methods=["POST"])
def chartink_webhook():
    data = request.get_json(force=True, silent=True) or request.form.to_dict()

    scan_name = data.get("scan_name", "")
    triggered_at = data.get("triggered_at", "")
    stocks = [s.strip() for s in data.get("stocks", "").split(",") if s.strip()]
    prices = [p.strip() for p in data.get("trigger_prices", "").split(",") if p.strip()]

    conn = sqlite3.connect(DB_FILE)
    for symbol, price in zip(stocks, prices):
        conn.execute(
            "INSERT INTO alerts (received_at, scan_name, triggered_at, symbol, trigger_price) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), scan_name, triggered_at, symbol, float(price))
        )
    conn.commit()
    conn.close()

    print(f"Stored {len(stocks)} alert(s) from scan '{scan_name}'")

    return jsonify({"status": "ok", "stored": len(stocks)}), 200

@app.route("/alerts", methods=["GET"])
def view_alerts():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
