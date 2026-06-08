import os
import json
import time
import queue
import threading
import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
from threading import Thread

import serial
# optional imports (YOLO / voice)
try:
    import cv2
except Exception:
    cv2 = None

def send_all_angles():
    msg = f"{angles['elbow_lr']},{angles['elbow_ud']},{angles['wrist_ud']},{angles['gripper']}\n"
    ser.write(msg.encode())

def slider_changed(name, value):
    angles[name] = int(value)
    send_all_angles()

    if is_recording:
        record_data.append(angles.copy())
        
# ----- CONFIG ----- #
SERIAL_PORT = "/dev/ttyUSB0"   # <- change this
BAUD = 115200
SEND_DELAY = 0.02              # base delay between frames during playback
RECORDINGS_DIR = "recordings"
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# YOLO settings (fill your model / labels)
YOLO_ENABLED = True if cv2 else False
YOLO_DEVICE = 0                # camera index
YOLO_COOLDOWN = 5.0            # seconds between allowed YOLO-triggered actions
YOLO_MAP = {                   # label -> motion filename (in recordings/)
    "person": "wave.json",
    "bottle": "grab.json",
    # add more mappings as needed
}

# Voice settings
USE_DEEPGRAM = False           # set True if you integrate Deepgram (see TODO)
DEEPGRAM_API_KEY = "YOUR_DEEPGRAM_KEY"  # TODO: supply if using Deepgram

# ----- SERIAL SETUP ----- #
ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
time.sleep(2)  # allow microcontroller to reset

# ----- Shared state ----- #
angles = {
    "elbow_lr": 90,
    "elbow_ud": 90,
    "wrist_ud": 90,
    "gripper": 0
}

is_recording = False
record_data = []

# ----- Motion queue ----- #
command_queue = queue.Queue()

def queue_worker():
    """Worker thread: get motion filenames from queue and play them."""
    while True:
        job = command_queue.get()
        try:
            if isinstance(job, dict) and job.get("type") == "motion_file":
                motion_path = job["path"]
                speed = job.get("speed", 1.0)
                print(f"[QUEUE] Playing {motion_path} speed={speed}")
                play_motion(motion_path, speed)
            elif isinstance(job, dict) and job.get("type") == "motion_frames":
                frames = job["frames"]
                speed = job.get("speed", 1.0)
                play_frames(frames, speed)
            else:
                print("[QUEUE] Unknown job:", job)
        except Exception as e:
            print("[QUEUE] Error while executing job:", e)
        command_queue.task_done()

# start worker thread
threading.Thread(target=queue_worker, daemon=True).start()

# ----- Serial send helpers ----- #
def send_all_angles_dict(frame):
    """Send dict frame to serial: 'lr,ud,wrist,gripper\\n'"""
    msg = f"{frame['elbow_lr']},{frame['elbow_ud']},{frame['wrist_ud']},{frame['gripper']}\n"
    ser.write(msg.encode())

def send_all_angles_current():
    send_all_angles_dict(angles)

# ----- Motion player ----- #
def interpolate_and_send(start, end, speed_factor=1.0):
    """Interpolate between two angle dicts and send intermediate frames."""
    max_delta = max(abs(end[k] - start[k]) for k in start.keys())
    steps = max(int(max_delta / 2), 1)
    # adjust step timing by speed_factor
    step_delay = SEND_DELAY * (1.0 / speed_factor)
    for s in range(steps + 1):
        frame = {}
        for k in start.keys():
            frame[k] = int(start[k] + (end[k] - start[k]) * (s / steps))
        send_all_angles_dict(frame)
        time.sleep(step_delay)

def play_frames(frames, speed_factor=1.0):
    """Play a list of frames (each is dict) smoothly."""
    if not frames:
        return
    for i in range(len(frames) - 1):
        interpolate_and_send(frames[i], frames[i+1], speed_factor)
    # ensure last frame
    send_all_angles_dict(frames[-1])

def play_motion(filepath, speed_factor=1.0):
    """Load JSON file and play it via serial (blocking)."""
    if not os.path.exists(filepath):
        print("[PLAYER] Motion file not found:", filepath)
        return
    with open(filepath, "r") as f:
        frames = json.load(f)
    # frames expected as list of dicts with same keys as 'angles'
    play_frames(frames, speed_factor)

# ----- YOLO Worker ----- #
def yolo_worker(stop_event, mode_var):
    """Continuously run camera detection and enqueue motions when seen.
       Rate-limited by YOLO_COOLDOWN. Only active if mode_var == 'yolo'.
       This is a simple stub — replace model.predict logic with your model.
    """
    if not cv2:
        print("[YOLO] OpenCV not available. YOLO disabled.")
        return

    # try to open camera
    cap = cv2.VideoCapture(YOLO_DEVICE)
    if not cap.isOpened():
        print("[YOLO] Camera open failed.")
        return

    last_action_time = 0

    # TODO: replace below detection with your YOLO model inference
    # This placeholder uses simple color or shape detection — you must adapt.
    print("[YOLO] Started (placeholder). Replace detection with your model.")

    while not stop_event.is_set():
        if mode_var.get() != "yolo":
            time.sleep(0.2)
            continue

        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        # --- PLACEHOLDER DETECTION: convert to grayscale and simple threshold ---
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # pretend we detect "person" if big contour seen
        detected_label = None
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 20000:
                detected_label = "person"
                break
            elif area > 5000:
                detected_label = "bottle"
                break

        if detected_label:
            now = time.time()
            if now - last_action_time < YOLO_COOLDOWN:
                # rate-limited
                # print("[YOLO] Detected", detected_label, "but cooldown active")
                pass
            else:
                print("[YOLO] Detected:", detected_label)
                mapped = YOLO_MAP.get(detected_label)
                if mapped:
                    path = os.path.join(RECORDINGS_DIR, mapped)
                    command_queue.put({"type": "motion_file", "path": path, "speed": 1.0})
                    last_action_time = now
        # small sleep to avoid cpu hog
        time.sleep(0.1)

    cap.release()
    print("[YOLO] Stopped.")

# ----- Voice Worker (Deepgram stub / fallback) ----- #
def voice_worker(stop_event, mode_var):
    """
    This is a placeholder. For Deepgram you would use their realtime API (websocket)
    or a REST-based speech-to-text to get transcriptions, then map text to actions.
    For now, this simple loop waits for a short audio capture or uses keyboard.
    """
    print("[VOICE] Voice worker started. Replace with Deepgram or your chosen STT.")
    # Simple fallback: periodically check a text file 'voice_command.txt' for commands,
    # or you can integrate microphone capture + deepgram here.
    last_text = ""
    while not stop_event.is_set():
        if mode_var.get() != "voice":
            time.sleep(0.2)
            continue
        # TODO: replace this with actual Deepgram integration.
        # Here we check a simple file for a command (for quick testing).
        try:
            if os.path.exists("voice_command.txt"):
                with open("voice_command.txt", "r") as f:
                    txt = f.read().strip().lower()
                if txt and txt != last_text:
                    last_text = txt
                    print("[VOICE] Got text:", txt)
                    # map text to motion
                    if "wave" in txt:
                        command_queue.put({"type": "motion_file", "path": os.path.join(RECORDINGS_DIR, "wave.json")})
                    elif "grab" in txt or "bottle" in txt:
                        command_queue.put({"type": "motion_file", "path": os.path.join(RECORDINGS_DIR, "grab.json")})
                    elif "open" in txt:
                        command_queue.put({"type": "motion_frames", "frames": [{"elbow_lr":angles["elbow_lr"], "elbow_ud":angles["elbow_ud"], "wrist_ud":angles["wrist_ud"], "gripper":0}]})
                    elif "close" in txt:
                        command_queue.put({"type": "motion_frames", "frames": [{"elbow_lr":angles["elbow_lr"], "elbow_ud":angles["elbow_ud"], "wrist_ud":angles["wrist_ud"], "gripper":180}]})
                    # clear file after handling
                    open("voice_command.txt", "w").close()
        except Exception as e:
            print("[VOICE] error:", e)
        time.sleep(0.5)
    print("[VOICE] Stopped.")


# ----- GUI (manual controller) ----- #
root = tk.Tk()
root.title("Hand Controller (Mode: Manual/Yolo/Voice)")

mode_var = tk.StringVar(value="manual")  # manual, yolo, voice

# Top row: mode buttons
frame_modes = tk.Frame(root)
tk.Label(frame_modes, text="Mode:").pack(side=tk.LEFT)
tk.Button(frame_modes, text="Manual", width=10, command=lambda: mode_var.set("manual")).pack(side=tk.LEFT, padx=4)
tk.Button(frame_modes, text="YOLO", width=10, command=lambda: mode_var.set("yolo")).pack(side=tk.LEFT, padx=4)
tk.Button(frame_modes, text="Voice", width=10, command=lambda: mode_var.set("voice")).pack(side=tk.LEFT, padx=4)
frame_modes.pack(pady=6)

# Current mode label
mode_label = tk.Label(root, text="Mode: manual", fg="blue")
mode_label.pack()
def update_mode_label(*args):
    mode_label.config(text=f"Mode: {mode_var.get()}")
mode_var.trace_add("write", update_mode_label)

# Servo sliders
def make_slider(parent, label_text, name):
    s = tk.Scale(parent, from_=0, to=180, orient=tk.HORIZONTAL, length=420,
                 label=label_text, command=lambda v: slider_changed(name, v))
    s.set(angles[name])
    return s

slider_lr = make_slider(root, "Elbow Left/Right", "elbow_lr")
slider_lr.pack(pady=4)
slider_ud = make_slider(root, "Elbow Up/Down", "elbow_ud")
slider_ud.pack(pady=4)
slider_wrist = make_slider(root, "Wrist Up/Down", "wrist_ud")
slider_wrist.pack(pady=4)

# gripper buttons
frame_grip = tk.Frame(root)
tk.Label(frame_grip, text="Gripper").pack(side=tk.LEFT, padx=6)
tk.Button(frame_grip, text="Open", width=10, command=lambda: (angles.update({"gripper":0}), send_all_angles_current(), record_if_on())).pack(side=tk.LEFT, padx=4)
tk.Button(frame_grip, text="Close", width=10, command=lambda: (angles.update({"gripper":180}), send_all_angles_current(), record_if_on())).pack(side=tk.LEFT, padx=4)
frame_grip.pack(pady=6)

# record/playback/save/load controls
frame_ctrl = tk.Frame(root)
tk.Button(frame_ctrl, text="Start Recording", command=lambda: start_recording()).pack(side=tk.LEFT, padx=6)
tk.Button(frame_ctrl, text="Stop Recording", command=lambda: stop_recording()).pack(side=tk.LEFT, padx=6)
tk.Button(frame_ctrl, text="Playback Recording", command=lambda: Thread(target=lambda: command_queue.put({"type":"motion_frames","frames":record_data.copy(),"speed":speed_slider.get()/100.0})).start()).pack(side=tk.LEFT, padx=6)
tk.Button(frame_ctrl, text="Save Recording", command=lambda: save_recording()).pack(side=tk.LEFT, padx=6)
tk.Button(frame_ctrl, text="Load Recording", command=lambda: load_recording()).pack(side=tk.LEFT, padx=6)
tk.Button(frame_ctrl, text="Clear Recording", command=lambda: clear_recording()).pack(side=tk.LEFT, padx=6)
frame_ctrl.pack(pady=8)

# playback speed slider
speed_slider = tk.Scale(root, from_=50, to=200, orient=tk.HORIZONTAL, length=420, label="Playback Speed (%)")
speed_slider.set(100)
speed_slider.pack()

# info / status box
status_var = tk.StringVar(value="Ready")
status_label = tk.Label(root, textvariable=status_var, fg="green")
status_label.pack(pady=6)

# helpers for GUI records
def record_if_on():
    if is_recording:
        record_data.append(angles.copy())

# save / load functions
def save_recording():
    if len(record_data) == 0:
        messagebox.showinfo("Info", "No recording to save.")
        return
    name = simpledialog.askstring("Save Recording", "Enter name for recording:")
    if not name:
        return
    fname = os.path.join(RECORDINGS_DIR, f"{name}.json")
    with open(fname, "w") as f:
        json.dump(record_data, f)
    messagebox.showinfo("Saved", f"Saved as {fname}")

def load_recording():
    files = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith(".json")]
    if not files:
        messagebox.showinfo("Load", "No recordings available.")
        return
    choice = filedialog.askopenfilename(initialdir=RECORDINGS_DIR, title="Select recording",
                                        filetypes=[("JSON files","*.json")])
    if not choice:
        return
    with open(choice, "r") as f:
        global record_data
        record_data = json.load(f)
    messagebox.showinfo("Loaded", f"Loaded {os.path.basename(choice)} ({len(record_data)} steps)")

# keyboard bindings
def on_key(event):
    k = event.keysym.lower()
    if k == "g":
        # toggle gripper
        if angles["gripper"] == 0:
            angles["gripper"] = 180
        else:
            angles["gripper"] = 0
        send_all_angles_current()
        record_if_on()
    elif k == "w":
        angles["wrist_ud"] = min(180, angles["wrist_ud"] + 5)
        slider_wrist.set(angles["wrist_ud"])
        send_all_angles_current()
        record_if_on()
    elif k == "s":
        angles["wrist_ud"] = max(0, angles["wrist_ud"] - 5)
        slider_wrist.set(angles["wrist_ud"])
        send_all_angles_current()
        record_if_on()
    elif k == "left":
        slider_lr.set(max(0, slider_lr.get()-5))
    elif k == "right":
        slider_lr.set(min(180, slider_lr.get()+5))
    elif k == "up":
        slider_ud.set(min(180, slider_ud.get()+5))
    elif k == "down":
        slider_ud.set(max(0, slider_ud.get()-5))
    elif k == "r":
        start_recording()
    elif k == "t":
        stop_recording()
    elif k == "p":
        # enqueue current recording
        if record_data:
            command_queue.put({"type":"motion_frames","frames":record_data.copy(),"speed":speed_slider.get()/100.0})
    elif k == "l":
        load_recording()
    elif k == "q":
        shutdown_app()

root.bind_all("<Key>", on_key)

# ----- control functions ----- #
def start_recording():
    global is_recording, record_data
    record_data = []
    is_recording = True
    status_var.set("Recording...")
    print("[GUI] Recording started")

def stop_recording():
    global is_recording
    is_recording = False
    status_var.set(f"Recorded {len(record_data)} frames")
    print("[GUI] Recording stopped:", len(record_data))

def clear_recording():
    global record_data
    record_data = []
    status_var.set("Recording cleared")
    print("[GUI] Recording cleared")

def shutdown_app():
    # stop workers and close serial
    print("[APP] Shutting down")
    try:
        ser.close()
    except:
        pass
    root.quit()
    root.destroy()

# ----- Start YOLO and voice threads ----- #
stop_event = threading.Event()
yolo_thread = Thread(target=yolo_worker, args=(stop_event, mode_var), daemon=True)
voice_thread = Thread(target=voice_worker, args=(stop_event, mode_var), daemon=True)
yolo_thread.start()
voice_thread.start()

# set initial servo positions
send_all_angles_current()

# ----- start GUI loop ----- #
root.mainloop()

# when GUI closes:
stop_event.set()
print("Application exited.")
