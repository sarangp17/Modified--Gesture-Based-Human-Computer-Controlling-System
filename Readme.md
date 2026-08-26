# ✋ ControllingSystem

> **A touchless desktop control system powered by hand gestures.**

ControllingSystem is a **computer vision-based touchless control system** that allows users to interact with their computer using hand gestures. A webcam captures the user's hand movements, while **OpenCV** and **MediaPipe** detect and track hand landmarks in real time.

The system can control the **mouse cursor, left-click, screen brightness, and system volume** without requiring physical interaction with a mouse or keyboard. It also provides a modern **CustomTkinter GUI** with an embedded live camera preview and real-time control status.

---

## 🎥 Demo Video

A demonstration video of **ControllingSystem** is included with this project and shows the system running with the different hand gestures and control modes.

> 📹 **Demo:** See the uploaded project video / repository media for a complete demonstration of the system.

---

## ✨ Features

* 🖱️ **Gesture-based Mouse Control**

  * Move the cursor using your index finger
  * Perform a left-click using a thumb + index finger pinch

* 🔆 **Brightness Control**

  * Use the **left hand** to adjust screen brightness

* 🔊 **Volume Control**

  * Use the **right hand** to adjust system volume

* 🎥 **Live Camera Preview**

  * Webcam feed is displayed directly inside the application
  * No separate OpenCV camera window is required

* 🌓 **Modern Graphical Interface**

  * Dark-themed UI
  * Control mode switches
  * Live status indicators
  * Built-in gesture guide

* 🔄 **Automatic Mode Switching**

  * Brightness/Volume mode automatically returns to Mouse Control after 7 seconds without hand detection

* ⏱️ **Automatic Inactivity Shutdown**

  * Application automatically closes after 60 seconds without detecting any hand activity

* 🔒 **Safe Camera Management**

  * Camera access is coordinated when switching between control modes

---

## 🖐️ Gesture Guide

| Gesture                | Action                   |
| ---------------------- | ------------------------ |
| ☝️ Index finger up     | Move mouse cursor        |
| 🤏 Thumb + index pinch | Left mouse click         |
| 🤚 Left-hand pinch     | Adjust screen brightness |
| 🤙 Right-hand pinch    | Adjust system volume     |

---

## 🖥️ Control Modes

### 🖱️ Mouse Control

Mouse Control starts automatically when the application launches.

Raise your **index finger** and move your hand to control the mouse cursor. The system maps the position of your finger from the camera frame to your computer screen and applies smoothing for more stable movement.

To perform a left-click, bring your **thumb and index finger together**. A short click cooldown prevents multiple clicks from being triggered continuously.

---

### 🔆 Brightness / 🔊 Volume Control

Enable the **Brightness / Volume** mode using the switch in the application.

The system identifies the detected hand and assigns the appropriate function:

```text
Left Hand  →  Screen Brightness
Right Hand →  System Volume
```

If no hand is detected for approximately **7 seconds**, the system automatically stops this mode and returns to Mouse Control.

---

## ⚙️ How It Works

```text
              Webcam
                 │
                 ▼
        ┌─────────────────┐
        │     OpenCV      │
        │ Camera Capture  │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │    MediaPipe    │
        │ Hand Detection  │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ Gesture / Hand  │
        │ Identification  │
        └────────┬────────┘
                 │
       ┌─────────┼─────────┐
       ▼         ▼         ▼
     Mouse    Brightness  Volume
    Control    Control    Control
```

The main application manages the camera, gesture-processing logic, control modes, timers, and graphical interface.

---

## 📦 Requirements

* **Windows OS**
* **Python 3.9+**
* Working webcam
* Camera access permission

> **Note:** System volume control uses `pycaw`, so the current implementation is intended for Windows.

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/ControllingSystem.git
cd ControllingSystem
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the application

The main entry point of the project is:

```bash
python ControllingSystem.py
```

---

## 🗂️ Project Structure

```text
ControllingSystem/
│
├── ControllingSystem.py          # ⭐ Main application
│
├── htm.py                        # Hand tracking helper
├── brightnes_lefthand.py         # Left-hand brightness control
├── volume_control_righthand.py   # Right-hand volume control
│
├── requirements.txt              # Project dependencies
├── README.md                     # Project documentation
├── LICENSE                       # License information
└── .gitignore                    # Git configuration
```

> **Note:** The project contains additional supporting files/modules. Keep the required Python modules in the appropriate project directory so that `ControllingSystem.py` can import and use them correctly.

---

## 📄 Main File

### `ControllingSystem.py`

This is the **main file and entry point** of the project.

It is responsible for:

* Starting the application
* Creating the graphical user interface
* Managing the webcam
* Running gesture detection
* Controlling mouse movement and clicking
* Switching between Mouse and Brightness/Volume modes
* Managing inactivity timeouts
* Displaying the live camera preview
* Handling application shutdown

The application automatically starts Mouse Control when launched.

---

## 🧩 Supporting Modules

### `htm.py`

Provides the hand-tracking functionality used by Mouse Control.

### `brightnes_lefthand.py`

Handles the **left-hand brightness control** functionality.

### `volume_control_righthand.py`

Handles the **right-hand system volume control** functionality.

The main application imports these modules specifically for the corresponding controls.

---

## ⏱️ Automatic Behavior

### 7-Second Timeout

When Brightness/Volume mode is active:

```text
No hand detected
       │
       ▼
   7 seconds
       │
       ▼
Mouse Control
```

The system automatically returns to Mouse Control if no hand is detected for 7 seconds.

### 60-Second Timeout

If there is no hand activity anywhere in the application:

```text
No hand detected
       │
       ▼
   60 seconds
       │
       ▼
Application closes
```

This global inactivity timeout applies to both control modes.

---

## 🛠️ Tech Stack

| Technology           | Purpose                                  |
| -------------------- | ---------------------------------------- |
| 🐍 **Python**        | Core programming language                |
| 👁️ **OpenCV**       | Webcam capture and image processing      |
| ✋ **MediaPipe**      | Hand landmark detection and tracking     |
| 🖱️ **PyAutoGUI**    | Mouse and cursor control                 |
| 🔊 **Pycaw**         | Windows system audio control             |
| 🎨 **CustomTkinter** | Graphical user interface                 |
| 🖼️ **Pillow**       | Live camera preview handling             |
| 🧵 **Threading**     | Background gesture and camera processing |

The project initializes MediaPipe for up to two hands and uses PyAutoGUI for screen-sized cursor control.

---

## ⚠️ Limitations

* Currently designed primarily for **Windows**.
* Good lighting improves hand-detection accuracy.
* Webcam quality can affect gesture recognition.
* Mouse Control uses one-hand tracking.
* Brightness/Volume mode can detect left and right hands.
* The system requires webcam access.
* The brightness controller depends on the implementation provided in the supporting brightness module.

---

## 🚀 Future Improvements

* [ ] Add right-click gesture
* [ ] Add scrolling gestures
* [ ] Add drag-and-drop gesture
* [ ] Add keyboard control through gestures
* [ ] Add customizable gestures
* [ ] Add gesture sensitivity settings
* [ ] Improve low-light hand detection
* [ ] Add more control modes
* [ ] Improve cross-platform support

---

## 📄 License

This project is licensed under the **MIT License**.

See the [`LICENSE`](LICENSE) file for more information.

---

## 👤 Author

**Sarang Palsutkar**

---

## ⭐ Support

If you find **ControllingSystem** useful or interesting, consider giving the repository a ⭐ on GitHub!

**Built with Python, Computer Vision, and Hand Gestures.** ✋
