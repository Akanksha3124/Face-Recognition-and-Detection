"""
Downloads pretrained model weights the AI service needs. Weights are
NOT committed to the repo (keeps it small, and re-downloading is
trivial) — run this once before starting the service, or as a Docker
build step.

Usage:
    cd ai && python scripts/download_models.py
"""
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
DETECTION_DIR = MODELS_DIR / "face_detection"
EMBEDDING_DIR = MODELS_DIR / "face_embedding"

# OpenCV's official SSD ResNet-10 Caffe face detector — see the module
# docstring in app/face_detection/detector.py for why this model was
# chosen over RetinaFace/MTCNN for Phase 6. Both files are hosted
# directly by OpenCV's own GitHub repos.
DETECTION_FILES = {
    "deploy.prototxt": (
        "https://raw.githubusercontent.com/opencv/opencv/master/"
        "samples/dnn/face_detector/deploy.prototxt"
    ),
    "res10_300x300_ssd_iter_140000.caffemodel": (
        "https://raw.githubusercontent.com/opencv/opencv_3rdparty/"
        "dnn_samples_face_detector_20170830/"
        "res10_300x300_ssd_iter_140000.caffemodel"
    ),
}

# insightface's "buffalo_s" pack — see app/face_embedding/embedder.py for
# why this (MobileFaceNet-based ArcFace, ~14MB) was chosen over the much
# larger ResNet100 ArcFace model the ONNX Model Zoo ships. The pack
# bundles 5 models (detection, recognition, landmarks, gender/age); we
# only want the recognition one, so download the zip to a temp dir,
# pull out the one file we need, and discard the rest rather than
# keeping ~150MB of unused models around.
EMBEDDING_PACK_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_s.zip"
EMBEDDING_MEMBER_NAME = "w600k_mbf.onnx"
EMBEDDING_DEST_NAME = "w600k_mbf.onnx"


def download(url: str, dest: Path) -> None:
    print(f"Downloading {dest.name} ...")
    urllib.request.urlretrieve(url, dest)
    print(f"  -> saved to {dest} ({dest.stat().st_size:,} bytes)")


def download_detection_models() -> None:
    DETECTION_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in DETECTION_FILES.items():
        dest = DETECTION_DIR / filename
        if dest.exists():
            print(f"{filename} already present, skipping.")
            continue
        download(url, dest)


def download_embedding_model() -> None:
    EMBEDDING_DIR.mkdir(parents=True, exist_ok=True)
    dest = EMBEDDING_DIR / EMBEDDING_DEST_NAME
    if dest.exists():
        print(f"{EMBEDDING_DEST_NAME} already present, skipping.")
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = Path(tmp_dir) / "buffalo_s.zip"
        print(f"Downloading {EMBEDDING_PACK_URL} (~120MB archive; only one file is kept) ...")
        urllib.request.urlretrieve(EMBEDDING_PACK_URL, zip_path)
        print("  -> extracting recognition model ...")
        with zipfile.ZipFile(zip_path) as archive:
            with archive.open(EMBEDDING_MEMBER_NAME) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
    print(f"  -> saved to {dest} ({dest.stat().st_size:,} bytes)")


def main() -> int:
    try:
        download_detection_models()
        download_embedding_model()
    except Exception as exc:  # noqa: BLE001 — report and fail clearly either way
        print(f"Failed to download models: {exc}", file=sys.stderr)
        return 1
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
