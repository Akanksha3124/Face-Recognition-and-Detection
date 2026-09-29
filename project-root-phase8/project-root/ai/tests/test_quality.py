"""
Image quality checks — pure functions, no model/network dependency.
Fixtures under tests/fixtures/: sample_face.jpg is a standard, freely
redistributed CV test image sourced from OpenCV's own public sample
data (github.com/opencv/opencv); sample_blurry/tiny/dark.jpg are
generated from it (Gaussian blur, downscale, darken) purely to exercise
the quality thresholds — not separately sourced images.
"""
from pathlib import Path

import cv2
import pytest

from app.image_quality.quality import assess_quality

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    image = cv2.imread(str(FIXTURES / name))
    assert image is not None, f"fixture {name} failed to load"
    return image


def test_normal_image_passes_quality_checks():
    report = assess_quality(load("sample_face.jpg"))
    assert report.passed
    assert not report.is_low_resolution
    assert not report.is_blurry
    assert not report.is_too_dark
    assert not report.is_too_bright


def test_blurry_image_flagged():
    report = assess_quality(load("sample_blurry.jpg"))
    assert report.is_blurry
    assert not report.passed


def test_tiny_image_flagged_low_resolution():
    report = assess_quality(load("sample_tiny.jpg"))
    assert report.is_low_resolution
    assert not report.passed


def test_dark_image_flagged():
    report = assess_quality(load("sample_dark.jpg"))
    assert report.is_too_dark
    assert not report.passed


def test_quality_report_includes_raw_metrics():
    report = assess_quality(load("sample_face.jpg"))
    assert report.width == 512
    assert report.height == 512
    assert report.blur_score > 0
    assert 0 <= report.brightness <= 255
