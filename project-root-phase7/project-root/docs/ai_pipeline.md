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

Vector storage, similarity search, video/CCTV processing, age-gap and
appearance-robustness evaluation — see the phase list in the root README.

---

## Phase 7: Face alignment → embedding generation

```
Detected face (from Phase 6, or an explicit box the caller supplies)
  ↓ align_face() — crop with margin + resize to 112x112
  ↓ preprocess — BGR→RGB, normalize to [-1, 1], HWC→CHW, add batch dim
  ↓ ONNX inference (insightface buffalo_s recognition model, CPU)
  ↓ L2-normalize the raw output
  ↓ response: { embedding: [512 floats], model_version, face_used, quality }
```

`POST /embed` accepts either just an image (it runs detection itself, but
**only proceeds if exactly one face is found**) or an image plus explicit
`x1/y1/x2/y2` form fields (skips re-running detection, embeds exactly that
region — meant for a caller that already ran `/detect` and knows which face
it wants, e.g. a human picking one person out of a group photo).

**Why "more than one face" is a hard error, not "pick the best one":**
silently choosing the highest-confidence face in a multi-person photo risks
enrolling or matching the wrong person. That's exactly the kind of
silent-guess failure mode this project's human-verification principle
exists to prevent — better to make the caller (ultimately a human) decide
than to guess quietly.

## Model choice: insightface `buffalo_s` (MobileFaceNet), not ResNet100 ArcFace

The ONNX Model Zoo's standard ArcFace model (`arcfaceresnet100-8.onnx`) is
~249MB. Phase 7 uses `w600k_mbf.onnx` from insightface's smaller `buffalo_s`
pack instead — ~14MB, MobileFaceNet-based, same reasoning Phase 6 used for
its detector choice: this needs to run on a CPU-only student machine without
a lengthy download.

**The real cost of this choice:** MobileFaceNet trades some accuracy for
size/speed compared to a full ResNet50/100 backbone — particularly likely to
show up under the harder conditions this whole project cares about (age
gap, disguise, low-quality CCTV frames). **This compounds with Phase 6's
landmark gap:** without 5-point landmarks, `align_face()` is a plain
crop-and-resize, not the similarity-transform alignment ArcFace models are
normally evaluated with. Both choices push in the same direction — smaller
detector, smaller embedder, weaker alignment — all individually reasonable
for a demo running on modest hardware, but worth re-examining together once
Phase 11/12's evaluation numbers exist. If they justify it, upgrading is
contained: `w600k_r50.onnx` (same buffalo family, ResNet50, ~166MB) is a
drop-in replacement — identical 112×112 input, identical 512-d output,
identical preprocessing recipe. A landmark-capable detector would be a
separate, slightly larger change confined to `face_detection/detector.py`
and the `align_face()` call site.

**Why the embedding is L2-normalized before returning:** the backend stores
these vectors in pgvector and compares them by cosine distance (see
`backend/app/models/face_embedding.py`, Phase 2). Normalizing here — once,
at generation time — means cosine similarity and dot product become
equivalent, which is one less thing for every future caller of this
embedding to get right independently.

## Endpoint

`POST /embed` (internal-only). Multipart file upload (JPEG/PNG, 10MB limit)
plus optional `x1`, `y1`, `x2`, `y2` form fields.

```json
{
  "embedding": [0.0123, -0.0456, "... 512 floats total"],
  "model_version": "insightface-buffalo_s/w600k_mbf",
  "face_used": { "x1": 208, "y1": 185, "x2": 353, "y2": 389, "confidence": 0.998 },
  "quality": { "width": 512, "height": 512, "...": "same shape as /detect" }
}
```

`face_used.confidence` is `null` when the caller supplied the box explicitly
(no detection was run for it) rather than it coming from auto-detection.

**Error cases:** `422` for no face found, more than one face found (without
an explicit box), an out-of-bounds or partially-specified explicit box, or a
face region too small to embed reliably (< 20px either dimension — resizing
a near-invisible face up to 112×112 mostly encodes noise, not identity).
`503` if embedding model weights aren't downloaded yet.

## Planned pipeline stages (still not yet implemented)

Vector storage, similarity search, video/CCTV processing, age-gap and
appearance-robustness evaluation — see the phase list in the root README.
