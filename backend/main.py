from datetime import datetime
import asyncio
import time

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func

from database import Base, SessionLocal, engine
from models import SessionRecord
from cv_service import CVService
from detectors import BiteDetector, JawChewDetector

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Bite & Chew AI", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cv_service = None


class RuntimeSession:
    def __init__(self):
        self.active = False
        self.started_at = None
        self.bites = 0
        self.chews = 0


session = RuntimeSession()


@app.on_event("startup")
def startup():
    global cv_service
    cv_service = CVService()


@app.on_event("shutdown")
def shutdown():
    global cv_service
    if cv_service:
        cv_service.close()


@app.get("/")
def root():
    return {"service": "Bite & Chew AI", "version": "3.0.0"}


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "3.0.0"}


@app.get("/api/session")
def get_session():
    duration = 0
    if session.active and session.started_at:
        duration = (datetime.utcnow() - session.started_at).total_seconds()
    return {
        "active": session.active,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "duration_seconds": duration,
        "bites": session.bites,
        "chews": session.chews,
    }


@app.post("/api/session/start")
def start_session():
    session.active = True
    session.started_at = datetime.utcnow()
    session.bites = 0
    session.chews = 0
    return {"success": True, "message": "Session started"}


@app.post("/api/session/stop")
def stop_session():
    if not session.active or not session.started_at:
        return {"success": True, "message": "No active session"}

    ended = datetime.utcnow()
    duration = (ended - session.started_at).total_seconds()
    db = SessionLocal()
    try:
        db.add(SessionRecord(
            started_at=session.started_at,
            ended_at=ended,
            duration_seconds=duration,
            bites=session.bites,
            chews=session.chews,
        ))
        db.commit()
    finally:
        db.close()

    session.active = False
    session.started_at = None
    return {"success": True, "message": "Session saved", "duration_seconds": duration}


@app.get("/api/history")
def history():
    db = SessionLocal()
    try:
        rows = db.execute(select(SessionRecord).order_by(SessionRecord.id.desc()).limit(20)).scalars().all()
        return [
            {
                "id": r.id,
                "started_at": r.started_at.isoformat(sep=" ", timespec="seconds"),
                "duration_seconds": round(r.duration_seconds, 1),
                "bites": r.bites,
                "chews": r.chews,
            }
            for r in rows
        ]
    finally:
        db.close()


@app.get("/api/analytics")
def analytics():
    db = SessionLocal()
    try:
        total_sessions = db.query(func.count(SessionRecord.id)).scalar() or 0
        total_bites = db.query(func.coalesce(func.sum(SessionRecord.bites), 0)).scalar() or 0
        total_chews = db.query(func.coalesce(func.sum(SessionRecord.chews), 0)).scalar() or 0
        return {
            "total_sessions": int(total_sessions),
            "total_bites": int(total_bites),
            "total_chews": int(total_chews),
            "average_bites": round(total_bites / total_sessions, 2) if total_sessions else 0,
            "average_chews": round(total_chews / total_sessions, 2) if total_sessions else 0,
            "average_chews_per_bite": round(total_chews / total_bites, 2) if total_bites else 0,
        }
    finally:
        db.close()


@app.get("/api/cv/status")
def cv_status():
    return {
        "face_landmarker": cv_service is not None,
        "hand_landmarker": cv_service is not None,
        "bite_logic": "hand-required + near-mouth + mouth-open + mouth-close",
        "chew_logic": "complete normalized jaw cycle with amplitude and duration filters",
    }


@app.websocket("/ws/analyze")
async def analyze(websocket: WebSocket):
    await websocket.accept()
    bite_detector = BiteDetector()
    chew_detector = JawChewDetector()
    previous_distance = None
    previous_frame_time = time.monotonic()
    fps_ema = 0.0

    try:
        while True:
            data = await websocket.receive_bytes()
            frame_start = time.monotonic()
            array = np.frombuffer(data, dtype=np.uint8)
            frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
            if frame is None:
                continue

            cv = cv_service.process_frame(frame)
            distance = cv["hand_to_mouth_distance"]
            approaching = (
                previous_distance is not None
                and distance is not None
                and distance < previous_distance - 0.008
            )
            previous_distance = distance

            bite = bite_detector.update(distance, cv["mouth_opening"])
            chew = chew_detector.update(cv["jaw_position"], valid=cv["face_detected"])

            if session.active:
                session.bites = bite["bite_count"]
                session.chews = chew["chew_count"]

            now = time.monotonic()
            dt = max(now - previous_frame_time, 1e-4)
            previous_frame_time = now
            instant_fps = 1.0 / dt
            fps_ema = instant_fps if fps_ema == 0 else fps_ema * 0.85 + instant_fps * 0.15
            processing_ms = (now - frame_start) * 1000.0

            await websocket.send_json({
                "success": True,
                "face_detected": cv["face_detected"],
                "hand_detected": cv["hand_detected"],
                "mouth_opening": cv["mouth_opening"],
                "mouth_state": cv["mouth_state"],
                "hand_to_mouth_distance": distance,
                "hand_near_mouth": cv["hand_near_mouth"],
                "hand_approaching": approaching,
                "selected_hand": cv["selected_hand"],
                "hand_confidence": cv["hand_confidence"],
                "index_tip": cv["index_tip"],
                "hand_points": cv["hand_points"],
                "mouth_center": cv["mouth_center"],
                "bite_state": bite["bite_state"],
                "bite_detected": bite["bite_detected"],
                "bite_confidence": bite["bite_confidence"],
                "bites": bite["bite_count"],
                "jaw_movement": chew["jaw_movement"],
                "jaw_amplitude": chew["jaw_amplitude"],
                "chew_state": chew["chew_state"],
                "chew_detected": chew["chew_detected"],
                "chews": chew["chew_count"],
                "fps": round(fps_ema, 1),
                "processing_ms": round(processing_ms, 1),
            })
            await asyncio.sleep(0)

    except WebSocketDisconnect:
        pass
