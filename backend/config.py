from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FACE_MODEL = BASE_DIR / "face_landmarker.task"
HAND_MODEL = BASE_DIR / "hand_landmarker.task"
DATABASE_URL = f"sqlite:///{BASE_DIR / 'bite_chew.db'}"
