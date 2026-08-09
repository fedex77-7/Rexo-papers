"""
Render's free "Web Service" tier requires the app to bind to a port
(so its health check passes). Our Telegram bot itself doesn't need one
(it uses polling, not webhooks) — so this tiny Flask app just exists to
keep Render happy, and gives you a URL you can ping with UptimeRobot
to stop the free instance from spinning down after inactivity.
"""
import os
import threading
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Rexo Papers bot is running."

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def start_keep_alive():
    t = threading.Thread(target=run, daemon=True)
    t.start()
