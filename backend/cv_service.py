import math
from typing import Optional

import cv2
import mediapipe as mp

from config import FACE_MODEL, HAND_MODEL

BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode


class CVService:
    """MediaPipe landmark extraction and normalized feature calculation."""

    def __init__(self):
        if not FACE_MODEL.exists():
            raise FileNotFoundError(f"Missing {FACE_MODEL.name}. Run download_models.ps1.")
        if not HAND_MODEL.exists():
            raise FileNotFoundError(f"Missing {HAND_MODEL.name}. Run download_models.ps1.")

        self.face = FaceLandmarker.create_from_options(
            FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(FACE_MODEL)),
                running_mode=RunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=0.45,
                min_face_presence_confidence=0.45,
                min_tracking_confidence=0.45,
            )
        )

        self.hand = HandLandmarker.create_from_options(
            HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(HAND_MODEL)),
                running_mode=RunningMode.IMAGE,
                num_hands=2,
                min_hand_detection_confidence=0.30,
                min_hand_presence_confidence=0.30,
                min_tracking_confidence=0.30,
            )
        )

    @staticmethod
    def d(a, b):
        return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)

    @staticmethod
    def p(x, y, z=0.0):
        class P:
            pass
        q = P()
        q.x, q.y, q.z = x, y, z
        return q

    @staticmethod
    def clamp(v, lo=0.0, hi=1.0):
        return max(lo, min(hi, v))

    def process_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        face_result = self.face.detect(image)
        hand_result = self.hand.detect(image)

        base = {
            "face_detected": False,
            "hand_detected": bool(hand_result.hand_landmarks),
            "mouth_opening": None,
            "mouth_state": "UNKNOWN",
            "hand_to_mouth_distance": None,
            "hand_near_mouth": False,
            "chin_y": None,
            "jaw_position": None,
            "face_reference": None,
            "mouth_center": None,
            "selected_hand": None,
            "hand_points": [],
            "index_tip": None,
            "hand_confidence": 0.0,
        }

        if not face_result.face_landmarks:
            return base

        face = face_result.face_landmarks[0]
        upper = face[13]
        lower = face[14]
        left_eye_outer = face[33]
        right_eye_outer = face[263]
        chin = face[152]
        nose = face[1]
        face_reference = self.d(left_eye_outer, right_eye_outer)
        if face_reference <= 1e-6:
            return base

        mouth_center = self.p(
            (upper.x + lower.x) / 2,
            (upper.y + lower.y) / 2,
            (upper.z + lower.z) / 2,
        )
        mouth_opening = self.d(upper, lower) / face_reference
        mouth_state = "OPEN" if mouth_opening >= 0.055 else "CLOSED"

        # Jaw position is relative to the face, not raw image Y. Using the
        # chin-to-eye-midpoint relation removes much of the effect of head
        # translation in the frame.
        eye_mid_y = (left_eye_outer.y + right_eye_outer.y) / 2
        jaw_position = (chin.y - eye_mid_y) / face_reference

        base.update({
            "face_detected": True,
            "mouth_opening": round(mouth_opening, 5),
            "mouth_state": mouth_state,
            "chin_y": round(chin.y, 5),
            "jaw_position": round(jaw_position, 5),
            "face_reference": round(face_reference, 5),
            "mouth_center": {"x": round(mouth_center.x, 5), "y": round(mouth_center.y, 5)},
        })

        if not hand_result.hand_landmarks:
            return base

        best = None
        for hand_idx, hand in enumerate(hand_result.hand_landmarks):
            # Fingertips are the most useful points for eating gestures.
            tips = [4, 8, 12, 16, 20]
            distances = [(idx, self.d(hand[idx], mouth_center)) for idx in tips]
            palm = self.p(
                sum(hand[i].x for i in (0, 5, 9, 13, 17)) / 5,
                sum(hand[i].y for i in (0, 5, 9, 13, 17)) / 5,
                sum(hand[i].z for i in (0, 5, 9, 13, 17)) / 5,
            )
            palm_distance = self.d(palm, mouth_center)
            min_tip_idx, min_tip_distance = min(distances, key=lambda x: x[1])
            score_distance = min(min_tip_distance, palm_distance * 1.15)
            if best is None or score_distance < best[0]:
                best = (score_distance, hand_idx, hand, min_tip_idx, min_tip_distance)

        raw_distance, hand_idx, hand, tip_idx, tip_distance = best
        normalized = raw_distance / face_reference
        near = normalized <= 0.95

        # Normalized proximity score: 1 = very near, 0 = outside the bite zone.
        proximity_score = self.clamp((1.25 - normalized) / (1.25 - 0.95))

        points = []
        for lm in hand:
            points.append({"x": round(lm.x, 5), "y": round(lm.y, 5)})

        label = "RIGHT" if hand_idx == 0 else "LEFT"
        # MediaPipe's handedness label is not always needed for the detector;
        # index order is kept stable for the overlay. The UI calls it selected hand.

        base.update({
            "hand_to_mouth_distance": round(normalized, 5),
            "hand_near_mouth": near,
            "selected_hand": label,
            "hand_points": points,
            "index_tip": {"x": round(hand[8].x, 5), "y": round(hand[8].y, 5)},
            "hand_confidence": round(proximity_score, 3),
        })
        return base

    def close(self):
        self.face.close()
        self.hand.close()
