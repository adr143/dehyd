from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import adafruit_dht
import schedule
from board import D4, D25
import gpiozero
import RPi.GPIO as GPIO
import dht11
import threading
import time
import os
import serial

# ===== CONFIGURATION =====
DHT_PIN = 4
HEATER_LAMP_PIN = 17
HEATER_FAN_PIN = 27

# Setup GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
dht_device = adafruit_dht.DHT22(D4, use_pulseio=False)

# Setup Arduino Serial
#ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
#ser.reset_input_buffer()

# Relay setup (Active LOW)
heater_lamp = gpiozero.OutputDevice(HEATER_LAMP_PIN, active_high=False, initial_value=True)
heater_fan = gpiozero.OutputDevice(HEATER_FAN_PIN, active_high=False, initial_value=True)

# Shared data dictionary
data = {
    "fishname":"No Fish",
    "temperature": None,
    "humidity": None,
    "heater_lamp": False,
    "heater_fan": False
}

started = False

# ===== BACKGROUND THREAD FOR DHT11 =====
def read_dht11():
    while True:
        try:
            #read_serial()
            result = dht_device
            if result.temperature is not None and result.humidity is not None:
                data["temperature"] = result.temperature
                data["humidity"] = result.humidity
                print("Meron")
            else:
                data["temperature"] = None
                data["humidity"] = None
            time.sleep(3.0)
            schedule.run_pending()
        except:
            print("DHT no results...")
            continue

def read_serial():
    if ser.in_waiting > 0:
        # Read line and remove whitespace/newlines
        line = ser.readline().decode('utf-8').strip()

        # Split the string by the comma
        parts = line.split(',')

        if len(parts) == 2:
            data["temperature"] = float(parts[0])
            data["humidity"] = float(parts[1])

            print(f"Current Environment: Temp: {data['temperature']}°C | Humidity: {data['humidity']}%")

            # NEXT STEP: Add your 'requests.post' here to send to Render

        else:
            data["temperature"] = None
            data["humidity"] = None
            print(f"Malformed data received: {line}")

threading.Thread(target=read_dht11, daemon=True).start()

# ===== FLASK APP =====
app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Records(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fishname = db.Column(db.String, unique=False, nullable=False)
    temperature = db.Column(db.Float, unique=False, nullable=False)
    humidity = db.Column(db.Float, unique=False, nullable=False)
    datetime = db.Column(db.DateTime, default=datetime.utcnow())

    def __repr__(self):
        return f"{self.datetime} -- {self.temperature} -- {self.humidity}"

def record_data():
    temp_temp = 0
    temp_humid = 0
    temp_fish = "No Fish"
    with app.app_context(): 
        if data["temperature"] != None:
            temp_temp = data["temperature"]
        if data["humidity"] != None:
            temp_humid = data["humidity"]
        if data["fishname"] != "":
            temp_fish = data["fishname"]
        record = Records(fishname=temp_fish,temperature=temp_temp, humidity=temp_humid)
        db.session.add(record)
        db.session.commit()
        print("data recorded")

@app.route('/')
def index():
    return render_template('index.html', data=data)

@app.route('/data')
def get_data():
    return jsonify(data)

@app.route('/control', methods=['POST'])
def control():
    req = request.json
    device = req.get("device")
    state = req.get("state")

    if device == "lamp":
        heater_lamp.value = not state  # Active LOW
        data["heater_lamp"] = state
    elif device == "fan":
        heater_fan.value = not state
        data["heater_fan"] = state

    return jsonify(success=True, data=data)

@app.route('/change_fish', methods=['POST'])
def change_fish():
    req = request.json
    fishname = req.get("fishname")

    data["fishname"] = fishname.lower()
    print(fishname)

    return jsonify(success=True, data=data)


@app.route('/data_table')
def data_table():
    records = Records.query.all()
    return render_template('table.html', records=records)

@app.route('/data_table/<fish>', methods=['GET'])
def fish_table(fish):
    records = Records.query.filter((Records.fishname==fish))
    return render_template('table.html', records=records)



# ===== RUN FLASK SERVER =====
if __name__ == "__main__":
    schedule.every(3).minutes.do(record_data)
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=False)
