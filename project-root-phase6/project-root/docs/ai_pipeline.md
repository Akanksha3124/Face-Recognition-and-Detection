# AI Pipeline

## Phase 6: Image validation → quality → face detection

```
Image upload (POST /detect)
  ↓ content-type + size validation (415 / 413 / 422)
  ↓ decode (cv2.imdecode) — 422 if not a valid JPEG/PNG
  ↓ quality assessment (blur, resolution, brightness) — always runs, never blocks detection
  ↓ face detection (OpenCV DNN, SSD ResNet-10) — bounding boxes + confidence, sorted descending
  ↓ response: { quality: {...}, faces: [...] }
```

Zero faces is a valid, non-error response — an empty `faces` array, not a 4xx.
Low quality (blurry/dark/tiny) is reported in `quality.passed` but does **not**
block detection from running; the caller decides what to do with a
low-quality-but-detected face.

## Model choice: OpenCV DNN (SSD ResNet-10), not RetinaFace/MTCNN

The architecture proposal originally named RetinaFace/MTCNN. Phase 6 uses
OpenCV's own pretrained Caffe face detector instead — a deliberate scope
decision, not an oversight:

- Needs only OpenCV (already a dependency for image I/O) — no PyTorch/
  TensorFlow install, no multi-hundred-MB model download.
- Runs comfortably on a CPU-only student machine.
- Well-established, widely used (ships with OpenCV's own official samples).

**The real cost of this choice:** this model outputs bounding boxes and a
confidence score only — no 5-point facial landmarks (eyes, nose, mouth
corners). RetinaFace/MTCNN provide those, which is what you'd normally use
for precise, rotation-corrected face alignment before generating an ArcFace
embedding. Phase 6's `crop_face()` is therefore a simple margin-padded
rectangular crop, not a landmark-aligned one.

**Why this is safe to defer:** `detect_faces()` is the only interface
Phase 7 (embedding) depends on. If alignment quality turns out to matter for
embedding accuracy, swapping in a landmark-capable detector (e.g.
insightface's bundled RetinaFace/SCRFD) is a contained change — it doesn't
ripple through the codebase. Flagged here so it isn't forgotten if Phase 7's
accuracy numbers look off.

## Model weights

Not committed to the repo (keeps it small; re-downloading is trivial and
these are large binary files). Run once before starting the service:

```bash
cd ai
python scripts/download_models.py
```

Downloads `deploy.prototxt` + `res10_300x300_ssd_iter_140000.caffemodel`
into `ai/models/face_detection/`, both hosted directly by OpenCV's own
GitHub repos. If the AI service starts without them, `POST /detect` returns
`503` with a message telling you to run this script — not a confusing
internal error.

## Quality thresholds (heuristic, not yet calibrated)

| Check | Threshold | Method |
|---|---|---|
| Resolution | < 80×80 | raw pixel dimensions |
| Blur | Laplacian variance < 100 | standard cheap blur proxy — sharp images have high-frequency edge content |
| Too dark | mean grayscale intensity < 40 | — |
| Too bright | mean grayscale intensity > 220 | — |

These are reasonable starting points, not calibrated against a labeled
dataset. That calibration is exactly what the Phase 11/12 evaluation
harnesses are for — revisit these numbers there if false positives/negatives
on real data suggest they're off.

## Endpoint

`POST /detect` (internal-only — no public port; reached by the backend over
the Docker network). Multipart file upload, JPEG/PNG only, 10MB limit.

```json
{
  "quality": {
    "width": 512, "height": 512,
    "blur_score": 387.1, "brightness": 124.2,
    "is_low_resolution": false, "is_blurry": false,
    "is_too_dark": false, "is_too_bright": false,
    "passed": true
  },
  "faces": [
    { "x1": 208, "y1": 185, "x2": 353, "y2": 389, "confidence": 0.998 }
  ]
}
```

## Planned pipeline stages (not yet implemented)

Face alignment, embedding generation (ArcFace/InsightFace), vector storage,
similarity search, video/CCTV processing, age-gap and appearance-robustness
evaluation — see the phase list in the root README.
