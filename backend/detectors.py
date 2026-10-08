"""Temporal bite and chew detectors.

The detectors intentionally work on landmark-derived measurements instead of
trying to classify a bite/chew from a single frame.
"""
from collections import deque
import math
import time


class BiteDetector:
    """Strict bite state machine.

    Required sequence:
        hand detected/near mouth -> mouth opens -> mouth closes -> bite.

    A short hand-tracking gap is tolerated after the hand has entered the
    mouth zone, but a bite can never be created without a real hand distance.
    """

    def __init__(
        self,
        near_enter=0.95,
        near_exit=1.25,
        mouth_open=0.055,
        mouth_close=0.035,
        open_hold=0.10,
        near_hold=0.10,
        max_open_wait=1.50,
        max_near_wait=2.00,
        cooldown=0.90,
        missing_hand_grace=0.35,
    ):
        self.near_enter = near_enter
        self.near_exit = near_exit
        self.mouth_open = mouth_open
        self.mouth_close = mouth_close
        self.open_hold = open_hold
        self.near_hold = near_hold
        self.max_open_wait = max_open_wait
        self.max_near_wait = max_near_wait
        self.cooldown = cooldown
        self.missing_hand_grace = missing_hand_grace

        self.state = "IDLE"
        self.bite_count = 0
        self.near_started = None
        self.open_started = None
        self.last_bite = 0.0
        self.hand_missing_since = None
        self.near_peak = None
        self.open_peak = None

    def update(self, hand_distance, mouth_opening):
        now = time.monotonic()
        detected = False

        if now - self.last_bite < self.cooldown:
            self.state = "COOLDOWN"
            return self.result(False, hand_distance, mouth_opening, 0.0)

        hand_present = hand_distance is not None and math.isfinite(hand_distance)
        mouth_present = mouth_opening is not None and math.isfinite(mouth_opening)

        # Never start a bite without a real hand measurement.
        if not hand_present:
            if self.state in {"MOUTH_OPEN", "HAND_NEAR_MOUTH"}:
                if self.hand_missing_since is None:
                    self.hand_missing_since = now
                if now - self.hand_missing_since <= self.missing_hand_grace:
                    # Keep the state briefly; this prevents a one-frame hand
                    # tracking dropout from destroying an otherwise valid bite.
                    return self.result(False, hand_distance, mouth_opening, self.confidence(mouth_opening, hand_distance))
            self.reset()
            return self.result(False, hand_distance, mouth_opening, 0.0)

        self.hand_missing_since = None

        near = hand_distance <= self.near_enter
        far = hand_distance >= self.near_exit

        if not mouth_present:
            if self.state == "MOUTH_OPEN" and self.open_started and now - self.open_started > self.max_open_wait:
                self.reset()
            return self.result(False, hand_distance, mouth_opening, self.confidence(mouth_opening, hand_distance))

        if self.state == "IDLE":
            if near:
                self.near_started = self.near_started or now
                self.near_peak = hand_distance if self.near_peak is None else min(self.near_peak, hand_distance)
                if now - self.near_started >= self.near_hold:
                    self.state = "HAND_NEAR_MOUTH"
            else:
                self.near_started = None
                self.near_peak = None

        elif self.state == "HAND_NEAR_MOUTH":
            if far:
                self.reset()
            elif now - (self.near_started or now) > self.max_near_wait:
                self.reset()
            elif mouth_opening >= self.mouth_open:
                self.open_started = self.open_started or now
                self.open_peak = mouth_opening if self.open_peak is None else max(self.open_peak, mouth_opening)
                if now - self.open_started >= self.open_hold:
                    self.state = "MOUTH_OPEN"
            elif not near:
                # Allow a small exit band, but don't hold a bite forever.
                if self.near_started and now - self.near_started > self.max_near_wait:
                    self.reset()

        elif self.state == "MOUTH_OPEN":
            self.open_peak = mouth_opening if self.open_peak is None else max(self.open_peak, mouth_opening)

            # Closing can happen while the hand is still near OR just after it
            # starts leaving. This models a realistic bite.
            if mouth_opening <= self.mouth_close and self.open_peak is not None:
                self.bite_count += 1
                self.last_bite = now
                detected = True
                self.state = "COOLDOWN"
                self.near_started = None
                self.open_started = None
                self.near_peak = None
                self.open_peak = None
            elif self.open_started and now - self.open_started > self.max_open_wait:
                self.reset()

        elif self.state == "COOLDOWN":
            self.reset()

        return self.result(detected, hand_distance, mouth_opening, self.confidence(mouth_opening, hand_distance))

    def confidence(self, mouth_opening, hand_distance):
        if mouth_opening is None or hand_distance is None:
            return 0.0
        hand_score = max(0.0, min(1.0, (self.near_exit - hand_distance) / (self.near_exit - self.near_enter)))
        mouth_score = max(0.0, min(1.0, mouth_opening / max(self.mouth_open, 1e-6)))
        return round((0.55 * hand_score + 0.45 * mouth_score), 3)

    def reset(self):
        self.state = "IDLE"
        self.near_started = None
        self.open_started = None
        self.hand_missing_since = None
        self.near_peak = None
        self.open_peak = None

    def result(self, detected, distance, mouth, confidence):
        return {
            "bite_count": self.bite_count,
            "bite_detected": detected,
            "bite_state": self.state,
            "hand_to_mouth_distance": distance,
            "mouth_opening": mouth,
            "bite_confidence": confidence,
        }


class JawChewDetector:
    """Detect complete jaw cycles rather than raw jaw movement.

    The input is a jaw position normalized to the face. The detector uses
    smoothing, an adaptive baseline, hysteresis, minimum amplitude, valid
    cycle duration and cooldown. This greatly reduces counts from talking,
    head movement and landmark jitter.
    """

    def __init__(
        self,
        amplitude_threshold=0.018,
        smoothing_window=7,
        return_ratio=0.42,
        cooldown=0.32,
        baseline_alpha=0.025,
        min_cycle=0.22,
        max_cycle=1.40,
    ):
        self.amplitude_threshold = amplitude_threshold
        self.return_ratio = return_ratio
        self.cooldown = cooldown
        self.baseline_alpha = baseline_alpha
        self.min_cycle = min_cycle
        self.max_cycle = max_cycle
        self.values = deque(maxlen=smoothing_window)
        self.baseline = None
        self.peak = 0.0
        self.phase = "IDLE"
        self.chew_count = 0
        self.last_chew = 0.0
        self.move_started = None

    def update(self, jaw_position, valid=True):
        now = time.monotonic()
        detected = False

        if jaw_position is None or not valid or not math.isfinite(jaw_position):
            return self.result(False, 0.0, 0.0)

        self.values.append(float(jaw_position))
        smooth = sum(self.values) / len(self.values)

        if self.baseline is None:
            self.baseline = smooth
            return self.result(False, 0.0, 0.0)

        # Only slowly follow the baseline. Fast jaw movement therefore remains
        # visible as a signal while long-term head-position drift is absorbed.
        self.baseline = self.baseline * (1.0 - self.baseline_alpha) + smooth * self.baseline_alpha
        signed = smooth - self.baseline
        movement = abs(signed)

        if self.phase == "IDLE":
            if movement >= self.amplitude_threshold and now - self.last_chew >= self.cooldown:
                self.phase = "MOVING"
                self.move_started = now
                self.peak = movement

        elif self.phase == "MOVING":
            self.peak = max(self.peak, movement)
            elapsed = now - (self.move_started or now)

            if elapsed > self.max_cycle:
                self.phase = "IDLE"
                self.peak = 0.0
                self.move_started = None
            elif movement <= self.peak * self.return_ratio:
                if (
                    self.peak >= self.amplitude_threshold
                    and self.min_cycle <= elapsed <= self.max_cycle
                    and now - self.last_chew >= self.cooldown
                ):
                    self.chew_count += 1
                    self.last_chew = now
                    detected = True
                self.phase = "IDLE"
                self.peak = 0.0
                self.move_started = None

        return self.result(detected, movement, self.peak)

    def result(self, detected, movement, amplitude):
        return {
            "chew_count": self.chew_count,
            "chew_detected": detected,
            "chew_state": self.phase,
            "jaw_movement": round(float(movement), 5),
            "jaw_amplitude": round(float(amplitude), 5),
        }
