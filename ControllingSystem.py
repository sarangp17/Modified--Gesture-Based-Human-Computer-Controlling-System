# ControllingSystem – Touchless Hand Gesture Control


# ControllingSystem is a touchless computer-control system that uses a webcam and hand-gesture recognition to control different functions of a computer. It uses OpenCV and MediaPipe to detect hand movements and provides a graphical interface where the user can switch between Mouse Control and Brightness/Volume Control modes. The system starts with mouse control automatically and displays a live camera preview inside the application.

# The system is controlled mainly through hand gestures. Raising the index finger moves the mouse cursor, while pinching the thumb and index finger performs a left click. In the Brightness/Volume mode, the left hand controls screen brightness and the right hand controls system volume. The user can switch modes using the on-screen toggle buttons. If no hand is detected for 7 seconds in Brightness/Volume mode, it automatically returns to Mouse Control; if no hand is detected anywhere for 60 seconds, the application closes automatically.
# | Gesture / Action               | Function                           |
# | ------------------------------ | ---------------------------------- |
# | ☝️ Index finger up             | Move mouse cursor                  |
# | 🤏 Thumb + index pinch         | Left mouse click                   |
# | 🤏 Left-hand pinch             | Adjust brightness                  |
# | 🤏 Right-hand pinch            | Adjust volume                      |
# | **Mouse Control toggle**       | Enable/disable mouse control       |
# | **Brightness / Volume toggle** | Enable brightness & volume control |
# | **Quit button**                | Close the application              |





import time
import threading
from ctypes import cast, POINTER

import cv2
import numpy as np
import mediapipe as mp
import pyautogui
import customtkinter as ctk
from PIL import Image, ImageTk
from google.protobuf.json_format import MessageToDict
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

import htm
from brightnes_lefthand import Brightness
from volume_control_righthand import Volume

# ------------------------------------------------------------
# Disable any raw OpenCV popup windows. Brightness()/Volume()
# (and any other helper) may internally call cv2.imshow — we
# already render everything inside the app's embedded preview,
# so silence that to avoid a duplicate floating "img" window.
# ------------------------------------------------------------
cv2.imshow = lambda *args, **kwargs: None
cv2.namedWindow = lambda *args, **kwargs: None
cv2.destroyAllWindows = lambda *args, **kwargs: None

# ============================================================
#  THEME
# ============================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG_COLOR = "#0f1117"
CARD_COLOR = "#171a23"
CARD_HOVER = "#1f2330"
ACCENT = "#5b8cff"
ACCENT_HOVER = "#4472e0"
SUCCESS = "#3ddc84"
DANGER = "#ff5c5c"
IDLE_COLOR = "#4a4f5e"
TEXT_MAIN = "#f1f2f6"
TEXT_SUB = "#8a8f9c"

# ============================================================
#  AUDIO SETUP
# ============================================================
devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
volume_control = cast(interface, POINTER(IAudioEndpointVolume))
volMin, volMax = volume_control.GetVolumeRange()[:2]

# ============================================================
#  MEDIAPIPE SETUP
# ============================================================
mphands = mp.solutions.hands
hands = mphands.Hands(
    static_image_mode=False,
    model_complexity=1,
    max_num_hands=2,
    min_detection_confidence=0.75,
    min_tracking_confidence=0.5,
)
Draw = mp.solutions.drawing_utils

detector = htm.handDetector(detectionCon=0.60, maxHands=1)
wScr, hScr = pyautogui.size()

# Mouse-control tuning
wCam, hCam = 640, 480
frameR = 100
smoothening = 7


# ============================================================
#  CONTROLLER  (all camera / gesture logic, UI-agnostic)
# ============================================================
class GestureController:
    """Runs camera + gesture logic in a background thread and reports
    frames / status back to the UI via callbacks.

    Timing rules:
      - BV_IDLE_TIMEOUT (7s):  no hand seen while in Brightness/Volume
        mode -> drop back to Mouse Control automatically.
      - GLOBAL_IDLE_TIMEOUT (60s): no hand seen at all, in *either*
        mode, for a full minute -> the whole app closes itself.
    """

    BV_IDLE_TIMEOUT = 7
    GLOBAL_IDLE_TIMEOUT = 60

    def __init__(self, on_frame, on_status, on_timeout):
        self.on_frame = on_frame        # callback(frame_bgr)
        self.on_status = on_status      # callback(mode: str, state: str)
        self.on_timeout = on_timeout    # callback() -> close the whole app

        self.cap = None
        self.mouse_thread = None
        self.bv_thread = None

        # A single lock ensures only one loop ever opens/holds the
        # webcam at a time, so switching modes can't fight over it
        # (that fight is what caused the "resistance"/freeze).
        self._camera_lock = threading.Lock()

        self.mouse_running = False
        self.bv_running = False

        self.plocX, self.plocY = 0, 0
        self.clocX, self.clocY = 0, 0
        self.pTime = 0

        # Shared across both modes: last time ANY hand was seen.
        self.last_activity_time = time.time()
        self._shutting_down = False

        # Debounce so a held pinch doesn't fire clicks every frame.
        self.last_click_time = 0
        self.CLICK_COOLDOWN = 0.4

    # ---------------- Mouse control ----------------
    def start_mouse_control(self):
        if self.mouse_running or self.bv_running or self._shutting_down:
            return
        self.mouse_running = True
        self.last_activity_time = time.time()
        self.on_status("mouse", "connecting")
        self.mouse_thread = threading.Thread(target=self._mouse_entry, daemon=True)
        self.mouse_thread.start()

    def _mouse_entry(self):
        # Wait for the B/V loop (if any) to fully let go of the camera
        # before we try to open it ourselves.
        self._wait_for_thread(self.bv_thread)
        if not self.mouse_running:
            return
        with self._camera_lock:
            self._mouse_loop()

    def _mouse_loop(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, wCam)
        self.cap.set(4, hCam)
        self.pTime = time.time()
        self.on_status("mouse", "active")

        while self.mouse_running:
            success, img = self.cap.read()
            if not success:
                self.on_status("mouse", "error")
                break

            img = detector.findHands(img)
            lmList, bbox = detector.findPosition(img)

            if len(lmList) != 0:
                self.last_activity_time = time.time()
                x1, y1 = lmList[8][1:]
                fingers = detector.fingersUp()

                # Move cursor whenever the index finger is up.
                if fingers[1] == 1:
                    x3 = np.interp(x1, (frameR, wCam - frameR), (0, wScr))
                    y3 = np.interp(y1, (frameR, hCam - frameR), (0, hScr))
                    self.clocX = self.plocX + (x3 - self.plocX) / smoothening
                    self.clocY = self.plocY + (y3 - self.plocY) / smoothening
                    pyautogui.moveTo(wScr - self.clocX, self.clocY)
                    cv2.circle(img, (x1, y1), 14, (91, 140, 255), cv2.FILLED)
                    self.plocX, self.plocY = self.clocX, self.clocY

                    # Click: pinch thumb (id 4) and index tip (id 8) together.
                    length, img, lineInfo = detector.findDistance(4, 8, img)
                    if length < 40 and (time.time() - self.last_click_time) > self.CLICK_COOLDOWN:
                        cv2.circle(img, (lineInfo[4], lineInfo[5]), 14,
                                   (61, 220, 132), cv2.FILLED)
                        pyautogui.click()
                        self.last_click_time = time.time()

            # Global 60s "nobody's here at all" check.
            if time.time() - self.last_activity_time > self.GLOBAL_IDLE_TIMEOUT:
                self.mouse_running = False
                self._release_camera()
                self.on_status("mouse", "idle")
                self._shutting_down = True
                self.on_timeout()
                return

            cTime = time.time()
            fps = 1 / (cTime - self.pTime) if (cTime - self.pTime) > 0 else 0
            self.pTime = cTime
            self._stamp_fps(img, fps)
            self.on_frame(img)

        self._release_camera()
        self.mouse_running = False

    # ---------------- Brightness / Volume control ----------------
    def start_bv_control(self):
        if self.bv_running or self._shutting_down:
            return
        self.bv_running = True
        self.last_activity_time = time.time()
        self.on_status("bv", "connecting")
        self.stop_mouse_control()
        self.bv_thread = threading.Thread(target=self._bv_entry, daemon=True)
        self.bv_thread.start()

    def _bv_entry(self):
        self._wait_for_thread(self.mouse_thread)
        if not self.bv_running:
            return
        with self._camera_lock:
            self._bv_loop()

    def _bv_loop(self):
        self.cap = cv2.VideoCapture(0)
        self.on_status("bv", "active")
        last_local_hand_time = time.time()

        while self.bv_running:
            ret, img = self.cap.read()
            if not ret:
                self.on_status("bv", "error")
                break

            img = cv2.flip(img, 1)
            imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = hands.process(imgRGB)

            if results.multi_hand_landmarks:
                self.last_activity_time = time.time()
                last_local_hand_time = time.time()
                if len(results.multi_handedness) == 2:
                    cv2.putText(img, "Both Hands", (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (61, 220, 132), 2)
                else:
                    for hd in results.multi_handedness:
                        label = MessageToDict(hd)["classification"][0]["label"]
                        if label == "Left":
                            cv2.putText(img, "Left - Brightness", (20, 40),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                                        (255, 200, 61), 2)
                            Brightness(img, imgRGB, results, Draw, mphands, hands)
                        elif label == "Right":
                            cv2.putText(img, "Right - Volume", (20, 40),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                                        (91, 140, 255), 2)
                            Volume(img, imgRGB, results, Draw, mphands, hands)
            else:
                # 7s with no hand -> fall back to mouse control.
                if time.time() - last_local_hand_time > self.BV_IDLE_TIMEOUT:
                    break

            # Global 60s check applies here too, as a safety net.
            if time.time() - self.last_activity_time > self.GLOBAL_IDLE_TIMEOUT:
                self.bv_running = False
                self._release_camera()
                self.on_status("bv", "idle")
                self._shutting_down = True
                self.on_timeout()
                return

            self.on_frame(img)

        self._release_camera()
        was_running = self.bv_running
        self.bv_running = False
        if was_running:
            self.on_status("bv", "idle")
            self.start_mouse_control()

    # ---------------- Shared controls ----------------
    def stop_mouse_control(self):
        if self.mouse_running:
            self.mouse_running = False
            self.on_status("mouse", "idle")

    def stop_bv_control(self):
        if self.bv_running:
            self.bv_running = False
            self.on_status("bv", "idle")

    def stop_all(self):
        self._shutting_down = True
        self.mouse_running = False
        self.bv_running = False
        self._release_camera()

    def _release_camera(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    @staticmethod
    def _wait_for_thread(thread, timeout=2.0):
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)

    @staticmethod
    def _stamp_fps(img, fps):
        cv2.rectangle(img, (0, 0), (90, 30), (15, 17, 23), -1)
        cv2.putText(img, f"{int(fps)} FPS", (8, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (91, 140, 255), 2)


# ============================================================
#  UI COMPONENTS
# ============================================================
class StatusDot(ctk.CTkCanvas):
    """A small glowing status indicator dot."""
    def __init__(self, master, size=14, **kwargs):
        super().__init__(master, width=size, height=size,
                          bg=CARD_COLOR, highlightthickness=0, **kwargs)
        self.size = size
        self.oval = self.create_oval(2, 2, size - 2, size - 2,
                                      fill=IDLE_COLOR, outline="")

    def set_state(self, state):
        color = {"active": SUCCESS, "connecting": ACCENT,
                 "idle": IDLE_COLOR, "error": DANGER}.get(state, IDLE_COLOR)
        self.itemconfig(self.oval, fill=color)


class ModeCard(ctk.CTkFrame):
    """A card representing one control mode, with toggle + live status."""
    def __init__(self, master, icon, title, subtitle, on_toggle, **kwargs):
        super().__init__(master, fg_color=CARD_COLOR, corner_radius=16, **kwargs)
        self.on_toggle = on_toggle
        self.enabled = False

        self.grid_columnconfigure(1, weight=1)

        icon_lbl = ctk.CTkLabel(self, text=icon, font=("Segoe UI Emoji", 28),
                                 width=48)
        icon_lbl.grid(row=0, column=0, rowspan=2, padx=(18, 8), pady=18)

        title_lbl = ctk.CTkLabel(self, text=title, font=("Segoe UI", 16, "bold"),
                                  text_color=TEXT_MAIN, anchor="w")
        title_lbl.grid(row=0, column=1, sticky="w", pady=(16, 0))

        self.status_lbl = ctk.CTkLabel(self, text=subtitle, font=("Segoe UI", 12),
                                        text_color=TEXT_SUB, anchor="w")
        self.status_lbl.grid(row=1, column=1, sticky="w", pady=(0, 16))

        self.dot = StatusDot(self)
        self.dot.grid(row=0, column=2, padx=(4, 4))

        self.switch_var = ctk.BooleanVar(value=False)
        self.switch = ctk.CTkSwitch(self, text="", variable=self.switch_var,
                                     command=self._toggled, progress_color=ACCENT,
                                     button_color="#e8e8e8")
        self.switch.grid(row=0, column=3, rowspan=2, padx=18)

    def _toggled(self):
        self.on_toggle(self.switch_var.get())

    def set_status(self, text, state):
        self.status_lbl.configure(text=text)
        self.dot.set_state(state)
        if state == "active":
            self.configure(fg_color=CARD_HOVER)
        else:
            self.configure(fg_color=CARD_COLOR)

    def force_switch(self, value: bool):
        self.switch_var.set(value)


# ============================================================
#  MAIN APPLICATION
# ============================================================
class HandControlApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Hand Control System")
        self.geometry("980x640")
        self.minsize(880, 580)
        self.configure(fg_color=BG_COLOR)

        self.controller = GestureController(self._on_frame, self._on_status,
                                             self._on_inactivity_timeout)
        self._preview_photo = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Auto-start mouse control on launch
        self.after(400, self._start_mouse_default)

    # ---------------- UI BUILD ----------------
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0, minsize=340)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ----- Sidebar -----
        sidebar = ctk.CTkFrame(self, fg_color=BG_COLOR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(24, 12), pady=24)
        sidebar.grid_columnconfigure(0, weight=1)

        header = ctk.CTkLabel(sidebar, text="✋ Hand Control",
                               font=("Segoe UI", 24, "bold"), text_color=TEXT_MAIN,
                               anchor="w")
        header.grid(row=0, column=0, sticky="w", pady=(4, 0))

        subheader = ctk.CTkLabel(sidebar,
                                  text="Touchless gestures for mouse, brightness & volume",
                                  font=("Segoe UI", 12), text_color=TEXT_SUB,
                                  anchor="w", justify="left", wraplength=300)
        subheader.grid(row=1, column=0, sticky="w", pady=(2, 20))

        self.mouse_card = ModeCard(
            sidebar, "🖱️", "Mouse Control", "Idle — index finger to move",
            on_toggle=self._toggle_mouse
        )
        self.mouse_card.grid(row=2, column=0, sticky="ew", pady=8)

        self.bv_card = ModeCard(
            sidebar, "🔆", "Brightness / Volume", "Idle — left hand: brightness, right: volume",
            on_toggle=self._toggle_bv
        )
        self.bv_card.grid(row=3, column=0, sticky="ew", pady=8)

        # Gesture guide
        guide = ctk.CTkFrame(sidebar, fg_color=CARD_COLOR, corner_radius=16)
        guide.grid(row=4, column=0, sticky="ew", pady=(20, 8))
        ctk.CTkLabel(guide, text="Gesture Guide", font=("Segoe UI", 14, "bold"),
                     text_color=TEXT_MAIN, anchor="w").pack(anchor="w", padx=18, pady=(14, 6))

        tips = [
            ("☝️", "Index finger up", "Move the cursor"),
            ("🤏", "Pinch thumb + index", "Left click"),
            ("🤚", "Left hand pinch", "Adjust brightness"),
            ("🤙", "Right hand pinch", "Adjust volume"),
        ]
        for emoji, gesture, action in tips:
            row = ctk.CTkFrame(guide, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=4)
            ctk.CTkLabel(row, text=emoji, font=("Segoe UI Emoji", 16)).pack(side="left")
            ctk.CTkLabel(row, text=f"{gesture}", font=("Segoe UI", 12, "bold"),
                         text_color=TEXT_MAIN).pack(side="left", padx=(8, 4))
            ctk.CTkLabel(row, text=f"→ {action}", font=("Segoe UI", 12),
                         text_color=TEXT_SUB).pack(side="left")
        ctk.CTkLabel(guide, text="", height=1).pack(pady=4)  # bottom padding

        exit_btn = ctk.CTkButton(sidebar, text="Quit", fg_color="transparent",
                                  border_width=1, border_color=DANGER,
                                  text_color=DANGER, hover_color="#2a1414",
                                  command=self._on_close)
        exit_btn.grid(row=5, column=0, sticky="ew", pady=(20, 0))

        # ----- Camera preview panel -----
        preview_frame = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=20)
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=(12, 24), pady=24)
        preview_frame.grid_rowconfigure(1, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        top_bar = ctk.CTkFrame(preview_frame, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 6))
        ctk.CTkLabel(top_bar, text="Live Preview", font=("Segoe UI", 16, "bold"),
                     text_color=TEXT_MAIN).pack(side="left")
        self.live_dot = StatusDot(top_bar, size=10)
        self.live_dot.pack(side="right")
        self.live_label = ctk.CTkLabel(top_bar, text="Idle", font=("Segoe UI", 12),
                                        text_color=TEXT_SUB)
        self.live_label.pack(side="right", padx=(0, 8))

        self.video_label = ctk.CTkLabel(preview_frame, text="",
                                         fg_color="#000000", corner_radius=14)
        self.video_label.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))

    # ---------------- Controller callbacks ----------------
    def _on_frame(self, frame_bgr):
        try:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img = img.resize((640, 480))
            photo = ImageTk.PhotoImage(image=img)
            self._preview_photo = photo  # keep reference
            self.video_label.configure(image=photo)
        except Exception:
            pass

    def _on_status(self, mode, state):
        def update():
            if mode == "mouse":
                text = {"active": "Active — tracking hand",
                        "connecting": "Starting camera…",
                        "idle": "Idle — index finger to move",
                        "error": "Camera error"}[state]
                self.mouse_card.set_status(text, state)
                self.mouse_card.force_switch(state in ("active", "connecting"))
            elif mode == "bv":
                text = {"active": "Active — show left/right hand",
                        "connecting": "Starting camera…",
                        "idle": "Idle — left hand: brightness, right: volume",
                        "error": "Camera error"}[state]
                self.bv_card.set_status(text, state)
                self.bv_card.force_switch(state in ("active", "connecting"))

            live = state in ("active", "connecting")
            self.live_dot.set_state(state if live else "idle")
            self.live_label.configure(text="Live" if state == "active" else
                                       ("Connecting…" if state == "connecting" else "Idle"))

        self.after(0, update)

    def _on_inactivity_timeout(self):
        # Called from a background thread once 60s pass with no hand
        # seen at all — hand off to the main thread to close safely.
        self.after(0, self._on_close)

    # ---------------- Toggle handlers ----------------
    def _toggle_mouse(self, want_on):
        if want_on:
            self.controller.stop_bv_control()
            self.controller.start_mouse_control()
        else:
            self.controller.stop_mouse_control()

    def _toggle_bv(self, want_on):
        if want_on:
            self.controller.start_bv_control()
        else:
            self.controller.stop_bv_control()

    def _start_mouse_default(self):
        self.mouse_card.force_switch(True)
        self.controller.start_mouse_control()

    def _on_close(self):
        self.controller.stop_all()
        self.after(200, self.destroy)


# ============================================================
#  ENTRY POINT
# ============================================================
if __name__ == "__main__":
    app = HandControlApp()
    app.mainloop()