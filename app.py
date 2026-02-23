from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import threading
import time
import os
import schedule
import gpiozero
import board
import adafruit_dht

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

DHT_DATA_PIN = board.D4
LAMP_GPIO = 17
FAN_GPIO = 27

data = {
    "fishname": "No Fish",
    "temperature": 0.0,
    "humidity": 0.0,
    "heater_lamp": False,
    "heater_fan": False
}

dht_sensor = adafruit_dht.DHT22(DHT_DATA_PIN, use_pulseio=False)
heater_lamp = gpiozero.OutputDevice(LAMP_GPIO, active_high=False, initial_value=False)
heater_fan = gpiozero.OutputDevice(FAN_GPIO, active_high=False, initial_value=False)

class Records(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fishname = db.Column(db.String, nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    datetime = db.Column(db.DateTime, default=datetime.utcnow)

def read_sensors_loop():
    global data
    while True:
        try:
            temp_c = dht_sensor.temperature
            hum = dht_sensor.humidity
            if temp_c is not None and hum is not None:
                data["temperature"] = round(temp_c, 1)
                data["humidity"] = round(hum, 1)
                print(temp_c)
                print(hum)
            print(f"Update: T={data['temperature']} H={data['humidity']}")
        #except RuntimeError:
        #    print("ok")
        except Exception as e:
            print(f"DHT22 Error: {e}")
        time.sleep(2.1)

def record_data():
    with app.app_context():
        if data["temperature"] != 0.0:
            new_record = Records(
                fishname=data["fishname"],
                temperature=data["temperature"],
                humidity=data["humidity"]
            )
            db.session.add(new_record)
            db.session.commit()

def scheduler_loop():
    schedule.every(3).minutes.do(record_data)
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.route('/')
def index():
    return render_template('index.html', data=data)

@app.route('/data')
def get_data():
    return jsonify(data)

@app.route('/api/history')
def get_history():
    records = Records.query.order_by(Records.datetime.desc()).limit(50).all()
    history = {
        "labels": [r.datetime.strftime('%H:%M') for r in reversed(records)],
        "temp": [r.temperature for r in reversed(records)],
        "hum": [r.humidity for r in reversed(records)]
    }
    return jsonify(history)

@app.route('/graph')
def graph_page():
    return render_template('graph.html')

@app.route('/reset_db', methods=['POST'])
def reset_db():
    Records.query.delete()
    db.session.commit()
    return jsonify(success=True)

@app.route('/control', methods=['POST'])
def control():
    req = request.json
    device = req.get("device")
    state = req.get("state")
    if device == "lamp":
        if state: heater_lamp.on()
        else: heater_lamp.off()
        data["heater_lamp"] = state
    elif device == "fan":
        if state: heater_fan.on()
        else: heater_fan.off()
        data["heater_fan"] = state
    else:
        return jsonify(success=False, error="Unknown device")
    return jsonify(success=True, data=data)

@app.route('/change_fish', methods=['POST'])
def change_fish():
    req = request.json
    data["fishname"] = req.get("fishname", "No Fish").lower()
    return jsonify(success=True, data=data)

@app.route('/data_table')
def data_table():
    records = Records.query.order_by(Records.datetime.desc()).all()
    return render_template('table.html', records=records)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    threading.Thread(target=read_sensors_loop, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
