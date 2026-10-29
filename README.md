# AURA.ai // Autonomous Facial Attendance & Biometric Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![OpenCV](https://img.shields.io/badge/OpenCV-YuNet%20ONNX-orange.svg)](https://opencv.org)
[![InsightFace](https://img.shields.io/badge/InsightFace-ArcFace%20512D-purple.svg)](https://insightface.ai)
[![License](https://img.shields.io/badge/License-Academic%20MIT-lightgrey.svg)]()

> **AURA** stands for **Automated Recognition & Attendance**. It is a modern, high-precision computer vision attendance system designed for universities, colleges, and large lecture halls. It replaces traditional paper roll calls and proxy-vulnerable biometric hardware with instant multi-face group recognition and continuous real-time optical tracking.

---

## 📑 Table of Contents
1. [Key Features](#-key-features)
2. [Architecture & Technology Stack](#-architecture--technology-stack)
3. [Quick Start & Installation](#-quick-start--installation)
4. [Using on Mobile & Android Devices](#-using-on-mobile--android-devices)
5. [Testing & Verification Suite](#-testing--verification-suite)
6. [Engineering Challenges & Technical Solutions](#-engineering-challenges--technical-solutions)
7. [Directory Structure](#-directory-structure)
8. [Downloads & Academic Artifacts](#-downloads--academic-artifacts)

---

## ⚡ Key Features

### 1. Dual-Mode Attendance Engine
- **Classroom Group Photo Mode**: Upload or snap a single wide-angle photo of an entire auditorium or lecture hall. Detects **100+ faces in milliseconds**, aligns them, matches against enrolled student embeddings, draws emerald-green bounding boxes for matched students, and soft-crimson boxes for `Unknown` faces.
- **60 FPS Live Optical Biometric HUD**: Real-time camera stream with a futuristic, cyber-themed tracking HUD overlay. Renders smooth spring-interpolated corner brackets, status beacons, and confidence badges directly on recognized faces.

### 2. Enterprise Student & Course Management
- **Smart Enrollment**: Multi-photo profile registration (with/without glasses, side angles) to maximize embedding recall.
- **Auto Date & Time Detection**: Session date and timestamp are automatically generated based on the device clock.
- **Dynamic Branch Classification**: Supports modern departments (e.g. `AI&DS`, `Computer Science`, `ECE`, `Mechanical`).
- **Course Rosters & Attendance Rules**: Enforce university attendance thresholds (e.g. 75% minimum eligibility rule) with instant `SHORTAGE` vs `ELIGIBLE` tags.

### 3. Student Self-Service Portal
- Students can look up their Roll Number to inspect their overall attendance percentage, subject-by-subject breakdown, and date-by-date session audit logs.

### 4. Reporting & Exporting
- 1-Click export of session attendance sheets to Microsoft Excel (`.xlsx`) or `.csv`.
- Semester-long course attendance summary matrix downloads.
- Built-in technical presentation (`.pptx`) and ML teaching guide (`.pdf`) download endpoints.

---

## 🧠 Architecture & Technology Stack

```
           ┌───────────────────────────────────────────────┐
           │        Client Layer (Web / Mobile)            │
           │  Vanilla JS (ES6+), Canvas 2D, Cyber HUD CSS  │
           └───────────────────────┬───────────────────────┘
                                   │ HTTP Multipart / JSON
                                   ▼
           ┌───────────────────────────────────────────────┐
           │          API Layer (FastAPI Backend)          │
           │      Uvicorn ASGI Server, REST Endpoints      │
           └───────────────────────┬───────────────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
┌───────────────────────────┐             ┌───────────────────────────┐
│     AURA Face Engine      │             │     Database Storage      │
│  - OpenCV YuNet (ONNX)    │             │   SQLite (attendance.db)  │
│  - SVD Affine Crop (112)  │             │  - Students & Rosters     │
│  - ArcFace (Buffalo_L)    │             │  - 512D Float32 BLOBs     │
│  - Multi-Scale IoM NMS    │             │  - Sessions & Attendance  │
└───────────────────────────┘             └───────────────────────────┘
```

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Backend Framework** | FastAPI (Python) | High-performance asynchronous REST API |
| **Face Detector** | OpenCV YuNet (`face_detection_yunet_2026may.onnx`) | Ultra-fast anchor-based face detection (FPN) |
| **Face Recognition** | InsightFace ArcFace (`buffalo_l/w600k_r50.onnx`) | ResNet-50 trained on MS1MV2 (512D hypersphere embeddings) |
| **Database** | SQLite3 (`attendance.db`) | Relational student records and binary vector storage |
| **Frontend UI** | HTML5, Modern CSS, Vanilla JavaScript | Responsive desktop/mobile UI, 60 FPS Biometric HUD |

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12 (64-bit recommended)
- Git (optional)

### 2. Setup Virtual Environment
```powershell
# Clone or navigate to the project directory
cd Ai_classroom_attendence_anti

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\activate

# Install required dependencies
pip install -r requirements.txt
```

### 3. Run the Application
```powershell
# Option A: One-click Python launcher (automatically opens browser)
.\venv\Scripts\python.exe run.py

# Option B: Direct Uvicorn server command
.\venv\Scripts\python.exe -m uvicorn server:app --host 0.0.0.0 --port 8000
```
Open your browser to: **`http://localhost:8000`**

---

## 📱 Using on Mobile & Android Devices

AURA is fully optimized for smartphones and tablets over local Wi-Fi / LAN:

1. **Find your Laptop's LAN IP**:
   Open a terminal and run `ipconfig`. Note your IPv4 Address (e.g. `192.168.137.1` or `172.16.122.141`).
2. **Open on Phone**:
   Connect your Android phone to the same Wi-Fi / Hotspot and open:
   `http://<your-laptop-ip>:8000`
3. **1-Tap Camera Attendance**:
   - Go to **Take Attendance** ➔ Select Session.
   - Tap **📸 Tap to Click Photo (Phone Camera)**.
   - Snap the classroom photo using your phone's native camera.
   - Tap **⚡ Scan & Identify Faces** — the photo is compressed client-side, sent in milliseconds, and annotated with identified student names!

> [!NOTE]
> **Live Webcam Streaming on Mobile**: Chromium security policies strictly require **HTTPS** or `localhost` to access `navigator.mediaDevices.getUserMedia`. For instant 1-tap phone camera captures on HTTP, use **Group Photo AI Upload**. Alternatively, enable `chrome://flags/#unsafely-treat-insecure-origin-as-secure` in Android Chrome.

---

## 🧪 Testing & Verification Suite

A standalone multi-face test harness is included: [`test_group_recognition.py`](file:///C:/Users/Md%20Dilnawaz%20Ahmad/Downloads/Ai_classroom_attendence_anti/test_group_recognition.py).

### How to test any new group photo:
```powershell
# Run on a specific image (e.g. test_images/my_photo.jpg)
.\venv\Scripts\python.exe test_group_recognition.py my_photo.jpg

# Run on all photos in test_images/
.\venv\Scripts\python.exe test_group_recognition.py

# Adjust cosine threshold (default: 0.36)
.\venv\Scripts\python.exe test_group_recognition.py my_photo.jpg --threshold 0.34
```
**Annotated Visual Output**: Annotated images with green/crimson boxes are automatically saved in `annotated_samples/`.

---

## 🛠️ Engineering Challenges & Technical Solutions

During development and live mobile testing, several subtle edge cases were encountered and systematically solved:

### 1. The "Krishna Agarwal" Hubness Failure (False Positive Cascade)
- **Problem**: Whenever photos were clicked from mobile phones, the model frequently mispredicted the subject as "Krishna Agarwal".
- **Root Cause**: During Krishna's initial portrait enrollment, YuNet detected his real face ($91\%$ confidence, area: 68k) but also fired a low-confidence false box ($59\%$ confidence, area: 120k) on his shirt collar. The registration code previously sorted candidate faces purely by area ($w \times h$), causing it to extract the non-face collar patch! In ArcFace 512D unit hypersphere space, textureless patches collapse into a central bias vector (a "hub" vector) that had false cosine similarities ($>0.40$) to random faces.
- **Solution**:
  1. Implemented a **Multi-Factor Face Quality Score**:
     $$\text{Score} = (\text{Confidence}^2) \times \text{Centrality} \times \sqrt{\text{Area Ratio}}$$
     Centered portrait subjects dominate over low-confidence edge detections.
  2. Implemented **Ensemble Student-Level Scoring**: For students with multiple photos, the engine combines top-2 similarities ($0.75 \cdot s_1 + 0.25 \cdot s_2$) and penalizes single-embedding outliers.
  3. Re-extracted all database embeddings: False matches dropped to exactly **0**.

### 2. Android 48MP Resolution Explosion & YuNet Saturation
- **Problem**: Group photo recognition on laptops was instantaneous, but phone uploads took seconds or produced phantom face boxes.
- **Root Cause**: Modern Android cameras capture at 12MP to 48MP ($4000 \times 3000$). At this resolution, YuNet's anchor grids saturated, producing 11 phantom detections and 1100ms inference latency.
- **Solution**:
  - Implemented client-side canvas compression (`optimizeImageForUpload`) in `static/app.js` downscaling to 1600px prior to upload.
  - Added a backend 1600px receptive-field normalization guard in `face_engine.py`, dropping inference time to **138ms**.

### 3. Dual Overlapping Bounding Boxes on Close-up Faces
- **Problem**: When a student took a close-up selfie portrait, the UI rendered two overlapping green boxes on the same face.
- **Root Cause**: On very large faces, adjacent Feature Pyramid Network (FPN) levels fired simultaneously (one on the upper forehead/eyes, one on the eyes/nose/mouth). Because standard IoU between the two was only ~18%, standard NMS at 0.30 failed to suppress the duplicate.
- **Solution**:
  - Implemented **Intersection over Minimum (IoM)** overlap suppression:
    $$\text{IoM} = \frac{\text{Area}(B_1 \cap B_2)}{\min(\text{Area}_1, \text{Area}_2)}$$
    Any detections sharing $>30\%$ of either box are recognized as part of the same face and suppressed.
  - Enforced a **Same-Student Single Match Guarantee**: A single student cannot have multiple detections in the same spatial proximity.

### 4. Windows File Locks & Console Unicode
- **Problem**: `PermissionError: [Errno 13]` when updating presentation slides while PowerPoint was open; Unicode `\u2713` crashed on Windows `cp1252` terminal.
- **Solution**: Dynamic file timestamping, safe file-streaming downloads via FastAPI, and ASCII-safe logging tags (`[MATCH]`, `[UNKNOWN]`).

---

## 📁 Directory Structure

```plaintext
Ai_classroom_attendence_anti/
├── database.py              # SQLite schema, query helpers, and vector operations
├── face_engine.py           # YuNet face detector, SVD aligner, and ArcFace matcher
├── server.py                # FastAPI endpoints, download routes, static files
├── run.py                   # Automatic browser launcher and server initializer
├── test_group_recognition.py # CLI multi-face test suite
├── generate_presentation.py # Automated PowerPoint generator (.pptx)
├── generate_teaching_pdf.py  # Automated mathematical teaching PDF generator (.pdf)
├── attendance.db            # SQLite database file
├── models/                  # ONNX YuNet face detection weights
├── student_photos/          # Enrolled student portrait repositories
├── test_images/             # Benchmark classroom & group test images
├── annotated_samples/       # Visual prediction outputs with bounding boxes
└── static/                  # Web Frontend
    ├── index.html           # SPA Dashboard layout
    ├── style.css            # Responsive, Android-optimized stylesheet
    └── app.js               # Biometric HUD, camera controller, and client optimizer
```

---

## 📄 Downloads & Academic Artifacts

Once the server is running, the following academic documentation can be downloaded directly:
- **White Background Slide Deck**: `http://localhost:8000/api/download/presentation`
- **Machine Learning & Mathematical Guide (PDF)**: `http://localhost:8000/api/download/math-ml-guide`

---

## 📜 License & Acknowledgements
- Built with [FastAPI](https://fastapi.tiangolo.com), [OpenCV](https://opencv.org), and [InsightFace](https://insightface.ai).
- Developed for educational, academic, and non-commercial research use.
