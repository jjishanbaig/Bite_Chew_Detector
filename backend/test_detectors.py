from detectors import BiteDetector, JawChewDetector


def test_bite_requires_hand():
    d = BiteDetector()
    d.update(None, 0.2)
    assert d.bite_count == 0


def test_bite_sequence():
    d = BiteDetector(near_hold=0.0, open_hold=0.0, cooldown=0.0)
    d.update(0.70, 0.02)
    d.update(0.70, 0.08)
    result = d.update(0.70, 0.02)
    assert result["bite_detected"] is True
    assert d.bite_count == 1


def test_mouth_alone_is_not_bite():
    d = BiteDetector(near_hold=0.0, open_hold=0.0, cooldown=0.0)
    d.update(None, 0.08)
    d.update(None, 0.02)
    assert d.bite_count == 0


if __name__ == "__main__":
    test_bite_requires_hand()
    test_bite_sequence()
    test_mouth_alone_is_not_bite()
    print("Detector tests passed")
