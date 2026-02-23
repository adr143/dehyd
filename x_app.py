from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import threading
import time
import os
import serial
import schedule

# ===== CONFIGURATION =====
# Match your verified port from the logs (/dev/ttyACM1)
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 9600

# Shared data dictionary
data = {
    "fishname": "No Fish",
    "temperature": 0.0,
    "humidity": 0.0,
    "heater_lamp": False,
    "heater_fan": False
}

# Threading Lock to prevent Serial collisions
serial_lock = threading.Lock()

# Initialize Serial
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    ser.reset_input_buffer()
    print(f"Connected to Arduino on {SERIAL_PORT}")
except Exception as e:
    print(f"Serial Connection Failed: {e}")
    ser = None

# ===== FLASK & DATABASE SETUP =====
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Records(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fishname = db.Column(db.String, nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    datetime = db.Column(db.DateTime, default=datetime.utcnow)

# ===== BACKGROUND TASKS =====

def read_serial_loop():
    """Continuously reads <humid>,<temp> from Arduino"""
    global ser
    while True:
        if ser:
            with serial_lock: # Lock serial while reading
                if ser.in_waiting > 0:
                    try:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        parts = line.split(',')
                        if len(parts) == 2:
                            data["humidity"] = float(parts[0])
                            data["temperature"] = float(parts[1])
                            print(f"Update: T={data['temperature']} H={data['humidity']}")
                    except Exception as e:
                        print(f"Serial Read Error: {e}")
        time.sleep(0.1)

def record_data():
    """Saves current data to SQLite Database"""
    with app.app_context():
        if data["temperature"] is not None and data["temperature"] > 0:
            new_record = Records(
                fishname=data["fishname"],
                temperature=data["temperature"],
                humidity=data["humidity"]
            )
            db.session.add(new_record)
            db.session.commit()
            print("Data saved to database.")

def scheduler_loop():
    schedule.every(3).minutes.do(record_data)
    while True:
        schedule.run_pending()
        time.sleep(1)

# ===== WEB ROUTES =====

@app.route('/')
def index():
    return render_template('index.html', data=data)

@app.route('/data')
def get_data():
    return jsonify(data)

@app.route('/control', methods=['POST'])
def control():
    global ser
    req = request.json
    device = req.get("device")
    state = req.get("state") # True = ON, False = OFF

    if not ser:
        return jsonify(success=False, error="Serial not connected")

    # Determine command byte
    if device == "lamp":
        cmd = b'L' if state else b'l'
        data["heater_lamp"] = state
    elif device == "fan":
        cmd = b'F' if state else b'f'
        data["heater_fan"] = state
    else:
        return jsonify(success=False, error="Unknown device")

    # Lock serial while writing command
    with serial_lock:
        try:
            ser.write(cmd)
            ser.flush() # Ensure byte is sent
            print(f"Sent Command: {cmd.decode()}")
        except Exception as e:
            return jsonify(success=False, error=str(e))

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

# ===== MAIN EXECUTION =====

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    threading.Thread(target=read_serial_loop, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()

    app.run(host="0.0.0.0", port=5000, debug=False)
