# Bite & Chew AI V3

A React + FastAPI computer-vision prototype for detecting eating bites and chewing from a webcam.

## What is improved in V3

### Bite detection
A bite is counted only after this sequence:

1. A hand is actually detected.
2. A fingertip/palm enters the normalized mouth zone.
3. The mouth opens.
4. The mouth closes.
5. The timing is valid and the detector is not in cooldown.

A mouth opening by itself does **not** count. A hand near the face by itself does **not** count.

The backend also exposes bite confidence, selected hand, hand-mouth distance and hand approach information.

### Chew detection
Chews are complete normalized jaw cycles, not simply "jaw moved" frames. The detector uses:

- jaw position relative to the eyes/face reference
- smoothing
- adaptive baseline
- minimum amplitude
- minimum/maximum cycle duration
- return-to-baseline hysteresis
- cooldown

This reduces false chews from small landmark jitter and normal head movement.

### Camera diagnostics
The live camera now overlays:

- hand skeleton
- hand landmarks
- mouth center
- fingertip-to-mouth line

The dashboard also reports FPS, processing time, hand confidence, bite confidence and jaw amplitude.

## Folder structure

```text
bite-chew-ai-v3/
├── backend/
│   ├── main.py
│   ├── cv_service.py
│   ├── detectors.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── requirements.txt
│   ├── download_models.ps1
│   └── ...
├── src/
│   ├── App.jsx
│   ├── index.css
│   ├── main.jsx
│   ├── components/CameraPreview.jsx
│   └── services/api.js
├── package.json
└── vite.config.js
```

## Windows setup

### 1. Backend

Open PowerShell:

```powershell
cd backend
python -m venv venv3
venv3\Scripts\activate
pip install -r requirements.txt
.\download_models.ps1
uvicorn main:app --reload
```

If PowerShell blocks scripts, use:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\download_models.ps1
```

### 2. Frontend

Open a second terminal at the project root:

```powershell
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## Testing bite detection

Sit 50-100 cm from the camera with your face and one hand visible.

Perform this exact test:

```text
hand far
  ↓
move hand toward mouth
  ↓
hand near mouth
  ↓
open mouth
  ↓
close mouth
```

The dashboard should move through states similar to:

```text
IDLE
HAND_NEAR_MOUTH
MOUTH_OPEN
COOLDOWN
```

and Bites should increase by exactly 1.

## Testing chew detection

After the bite test, make several normal chewing movements while keeping the head relatively stable. The detector should count completed jaw cycles, not every small frame-to-frame movement.

## If Hand detected still says No

Check these in order:

1. Confirm `backend/hand_landmarker.task` exists.
2. Run the backend from the `backend` directory.
3. Make sure the whole hand is inside the camera frame.
4. Improve room lighting.
5. Hold the hand around the lower face/mouth area.
6. Watch the green hand landmark overlay.
7. Check the terminal for MediaPipe/model errors.

The model binaries are intentionally not bundled in the ZIP. `download_models.ps1` downloads the official MediaPipe task files directly from Google's storage.

## Existing history

The SQLite database is kept compatible with the previous application. Old session records are not deleted automatically.

## Important

This is a computer-vision prototype and is not a medical device. Bite/chew counts depend on camera angle, lighting, face/hand visibility and the user's movement.
