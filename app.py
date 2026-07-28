from flask import Flask, request, jsonify
import json
from datetime import datetime

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "Webhook server is running."

@app.route("/chartink-webhook", methods=["POST"])
def chartink_webhook():
    data = request.get_json(force=True, silent=True) or request.form.to_dict()
    
    log_entry = {
        "received_at": datetime.now().isoformat(),
        "payload": data
    }
    
    with open("chartink_log.jsonl", "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    
    print("Received Chartink alert:", data)
    
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
