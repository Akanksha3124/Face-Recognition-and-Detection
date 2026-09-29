"""
Image quality checks, run before face detection so obviously unusable
images are flagged early rather than fed straight into the detector.

All thresholds below are heuristic starting points, not calibrated
against a labeled dataset — that calibration is exactly the kind of
thing the Phase 11/12 evaluation harnesses are for. Treat these as
"reasonable defaults to iterate on," not settled numbers.
"""
from dataclasses import dataclass

import cv2
import numpy as np

MIN_WIDTH = 80
MIN_HEIGHT = 80

# Laplacian variance is a standard cheap blur proxy: a sharp image has
# lots of high-frequency edge content (high variance); a blurry one is
# smoothed out (low variance).
BLUR_VARIANCE_THRESHOLD = 100.0

# Mean pixel intensity (0-255 grayscale) outside this range suggests
# the image is too dark or overexposed for reliable face detection.
DARK_BRIGHTNESS_THRESHOLD = 40.0
BRIGHT_BRIGHTNESS_THRESHOLD = 220.0


@dataclass
class QualityReport:
    width: int
    height: int
    blur_score: float
    brightness: float
    is_low_resolution: bool
    is_blurry: bool
    is_too_dark: bool
    is_too_bright: bool

    @property
    def passed(self) -> bool:
        return not (self.is_low_resolution or self.is_blurry or self.is_too_dark or self.is_too_bright)


def assess_quality(image: np.ndarray) -> QualityReport:
    """image: a BGR image as returned by cv2.imread/cv2.imdecode."""
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())

    return QualityReport(
        width=width,
        height=height,
        blur_score=blur_score,
        brightness=brightness,
        is_low_resolution=(width < MIN_WIDTH or height < MIN_HEIGHT),
        is_blurry=blur_score < BLUR_VARIANCE_THRESHOLD,
        is_too_dark=brightness < DARK_BRIGHTNESS_THRESHOLD,
        is_too_bright=brightness > BRIGHT_BRIGHTNESS_THRESHOLD,
    )
