import serial
import time
import tkinter as tk
from threading import Thread
from tkinter import simpledialog, messagebox
import json
import os

# ------------------ SETTINGS ------------------
SERIAL_PORT = "/dev/ttyUSB0"  # Replace with your ESP32 port
BAUD = 115200
ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
time.sleep(2)

send_angle_delay = 0.02  # seconds between sending angles during playback

# Current angles for servos
angles = {
    "elbow_lr": 90,
    "elbow_ud": 90,
    "wrist_ud": 90,
    "gripper": 0   # 0=open, 180=closed
}

# Recording
is_recording = False
record_data = []

# Directory to save recordings
SAVE_DIR = "recordings"
os.makedirs(SAVE_DIR, exist_ok=True)

# ------------------ SEND ANGLES ------------------
def send_all_angles():
    msg = f"{angles['elbow_lr']},{angles['elbow_ud']},{angles['wrist_ud']},{angles['gripper']}\n"
    ser.write(msg.encode())

# ------------------ CALLBACKS ------------------
def slider_changed(name, val):
    angles[name] = int(val)
    send_all_angles()
    if is_recording:
        record_data.append(angles.copy())

def gripper_open():
    angles["gripper"] = 0
    send_all_angles()
    if is_recording:
        record_data.append(angles.copy())

def gripper_close():
    angles["gripper"] = 180
    send_all_angles()
    if is_recording:
        record_data.append(angles.copy())

def gripper_toggle(event=None):
    if angles["gripper"] == 0:
        gripper_close()
    else:
        gripper_open()

def wrist_up(event=None):
    angles["wrist_ud"] = min(180, angles["wrist_ud"] + 5)
    send_all_angles()
    slider_wrist.set(angles["wrist_ud"])
    if is_recording:
        record_data.append(angles.copy())

def wrist_down(event=None):
    angles["wrist_ud"] = max(0, angles["wrist_ud"] - 5)
    send_all_angles()
    slider_wrist.set(angles["wrist_ud"])
    if is_recording:
        record_data.append(angles.copy())

def start_recording(event=None):
    global record_data, is_recording
    record_data = []
    is_recording = True
    print("Recording started...")

def stop_recording(event=None):
    global is_recording
    is_recording = False
    print(f"Recording stopped. {len(record_data)} steps saved.")

def clear_recording(event=None):
    global record_data
    record_data = []
    print("Recording cleared.")

# ------------------ SAVE / LOAD ------------------
def save_recording():
    if len(record_data) == 0:
        messagebox.showinfo("Save Recording", "No recording to save.")
        return
    name = simpledialog.askstring("Save Recording", "Enter recording name:")
    if not name:
        return
    filename = os.path.join(SAVE_DIR, f"{name}.json")
    with open(filename, "w") as f:
        json.dump(record_data, f)
    messagebox.showinfo("Save Recording", f"Recording saved as '{name}'.")

def load_recording():
    recordings = [f[:-5] for f in os.listdir(SAVE_DIR) if f.endswith(".json")]
    if not recordings:
        messagebox.showinfo("Load Recording", "No recordings found.")
        return
    name = simpledialog.askstring("Load Recording", f"Available: {', '.join(recordings)}\nEnter name to load:")
    if not name:
        return
    filename = os.path.join(SAVE_DIR, f"{name}.json")
    if not os.path.exists(filename):
        messagebox.showerror("Load Recording", f"Recording '{name}' not found.")
        return
    global record_data
    with open(filename, "r") as f:
        record_data = json.load(f)
    messagebox.showinfo("Load Recording", f"Recording '{name}' loaded. {len(record_data)} steps ready for playback.")

# ------------------ PLAYBACK ------------------
def playback(event=None):
    if len(record_data) == 0:
        print("No recording available.")
        return
    print("Playback started...")
    speed = speed_slider.get() / 100
    for i in range(len(record_data)-1):
        start = record_data[i]
        end = record_data[i+1]
        steps = max(int(max(abs(end[name]-start[name]) for name in start.keys())/2), 1)
        for j in range(steps+1):
            for name in angles.keys():
                angles[name] = int(start[name] + (end[name]-start[name])*(j/steps))
            send_all_angles()
            slider_lr.set(angles["elbow_lr"])
            slider_ud.set(angles["elbow_ud"])
            slider_wrist.set(angles["wrist_ud"])
            time.sleep(send_angle_delay * (1 / speed))
    for name in angles.keys():
        angles[name] = record_data[-1][name]
    send_all_angles()
    slider_lr.set(angles["elbow_lr"])
    slider_ud.set(angles["elbow_ud"])
    slider_wrist.set(angles["wrist_ud"])
    print("Playback done.")

def quit_app(event=None):
    ser.close()
    root.destroy()

# ------------------ TKINTER GUI ------------------
root = tk.Tk()
root.title("Hand Servo Controller")

# Sliders
slider_lr = tk.Scale(root, from_=0, to=180, orient=tk.HORIZONTAL, label="Elbow Left/Right", length=400,
                     command=lambda val: slider_changed("elbow_lr", val))
slider_lr.set(angles["elbow_lr"])
slider_lr.pack(pady=5)

slider_ud = tk.Scale(root, from_=0, to=180, orient=tk.HORIZONTAL, label="Elbow Up/Down", length=400,
                     command=lambda val: slider_changed("elbow_ud", val))
slider_ud.set(angles["elbow_ud"])
slider_ud.pack(pady=5)

slider_wrist = tk.Scale(root, from_=0, to=180, orient=tk.HORIZONTAL, label="Wrist Up/Down", length=400,
                        command=lambda val: slider_changed("wrist_ud", val))
slider_wrist.set(angles["wrist_ud"])
slider_wrist.pack(pady=5)

# Gripper buttons
frame_gripper = tk.Frame(root)
tk.Label(frame_gripper, text="Gripper").pack(side=tk.LEFT, padx=5)
tk.Button(frame_gripper, text="Open", command=gripper_open, width=10).pack(side=tk.LEFT, padx=5)
tk.Button(frame_gripper, text="Close", command=gripper_close, width=10).pack(side=tk.LEFT, padx=5)
frame_gripper.pack(pady=5)

# Control buttons
tk.Button(root, text="Start Recording", command=start_recording, width=20).pack(pady=5)
tk.Button(root, text="Stop Recording", command=stop_recording, width=20).pack(pady=5)
tk.Button(root, text="Playback", command=lambda: Thread(target=playback).start(), width=20).pack(pady=5)
tk.Button(root, text="Clear Recording", command=clear_recording, width=20).pack(pady=5)
tk.Button(root, text="Save Recording", command=save_recording, width=20).pack(pady=5)
tk.Button(root, text="Load Recording", command=load_recording, width=20).pack(pady=5)
tk.Button(root, text="Quit", command=quit_app, width=20).pack(pady=5)

# Playback speed slider
speed_slider = tk.Scale(root, from_=50, to=200, orient=tk.HORIZONTAL, label="Playback Speed (%)", length=400)
speed_slider.set(100)
speed_slider.pack(pady=10)

# ------------------ KEYBOARD SHORTCUTS ------------------
root.bind('r', start_recording)
root.bind('s', stop_recording)
root.bind('p', lambda event=None: Thread(target=playback).start())
root.bind('c', clear_recording)
root.bind('q', quit_app)

# Elbow control
root.bind('<Left>', lambda e: slider_lr.set(max(0, slider_lr.get()-5)))
root.bind('<Right>', lambda e: slider_lr.set(min(180, slider_lr.get()+5)))
root.bind('<Up>', lambda e: slider_ud.set(min(180, slider_ud.get()+5)))
root.bind('<Down>', lambda e: slider_ud.set(max(0, slider_ud.get()-5)))

# Wrist control
root.bind('w', wrist_up)
root.bind('s', wrist_down)

# Gripper toggle
root.bind('g', gripper_toggle)

# ------------------ START GUI ------------------
send_all_angles()  # move servos to starting positions
root.mainloop()
