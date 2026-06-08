import serial
import time
import json

# ------------------ SETTINGS ------------------
SERIAL_PORT = "/dev/ttyUSB0"  # Change to your ESP32 port
BAUD = 115200
send_angle_delay = 0.02  # seconds between sending frames

# ------------------ SERIAL SETUP ------------------
ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
time.sleep(2)  # wait for ESP32 to initialize

# ------------------ LOAD JSON ------------------
filename = "recordings/grabbing.json"  # path to your saved recording
with open(filename, "r") as f:
    record_data = json.load(f)

# ------------------ HELPER FUNCTION ------------------
def send_all_angles(frame):
    """
    Send a single frame (dictionary of servo angles) to ESP32
    Format: elbow_lr,elbow_ud,wrist_ud,gripper
    """
    msg = f"{frame['elbow_lr']},{frame['elbow_ud']},{frame['wrist_ud']},{frame['gripper']}\n"
    ser.write(msg.encode())

# ------------------ PLAYBACK ------------------
for i in range(len(record_data)-1):
    start = record_data[i]
    end = record_data[i+1]
    steps = max(int(max(abs(end[name]-start[name]) for name in start.keys())/2), 1)
    for j in range(steps+1):
        frame = {name: int(start[name] + (end[name]-start[name])*(j/steps)) for name in start.keys()}
        send_all_angles(frame)
        time.sleep(send_angle_delay)

# Send last frame to make sure servos end at final position
send_all_angles(record_data[-1])

# ------------------ CLEANUP ------------------
ser.close()
print("Playback finished!")
