import RPi.GPIO as GPIO
import dht11
import time

# --- SETUP ---
DHT_PIN = 4  # Change if connected to another GPIO pin

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.cleanup()

# Initialize DHT11 sensor
sensor = dht11.DHT11(pin=DHT_PIN)

print("📡 Starting DHT11 sensor test... (Press Ctrl+C to stop)\n")

try:
    while True:
        result = sensor.read()
        if result.is_valid():
            print(f"🌡 Temperature: {result.temperature}°C  💧 Humidity: {result.humidity}%")
        else:
            print("⚠️  Sensor read failed. Retrying...")
        time.sleep(2)

except KeyboardInterrupt:
    print("\n🛑 Test stopped by user.")
    GPIO.cleanup()
