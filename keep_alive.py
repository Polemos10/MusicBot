from flask import Flask
from threading import Thread
import logging

# Disable Flask logging clutter
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask('')


@app.route('/')
def home():
    return "Bot is alive!"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()
    print("✅ Keep-alive server running!")  # Confirmation message
