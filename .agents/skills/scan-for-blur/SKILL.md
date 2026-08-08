---
name: scan-for-blur
description: Technical approach for automated edge sharpness detection, blur scanning, auto-flagging, and image tagging in photo culling software.
---

# Scan for Blur (Blur Detection & Tagging Pipeline)

This skill documents all 3 algorithms for detecting out-of-focus or blurry photos during photographic culling sessions, auto-flagging them as `REJECT`, and applying the `"Blur"` tag.

---

## 🔬 3 Blur Detection Algorithms

Photographers can select their preferred algorithm from a 2-column sidebar modal (`BlurScanDialog`):

### 1. Variance of Laplacian (`"laplacian"`) - Default / Ultra-Fast
Measures the variance of the 2D Laplacian operator across the luminance channel:
$$\text{Sharpness Score} = \text{Var}(\nabla^2 I)$$
- **Speed**: ⭐⭐⭐⭐⭐ (< 3ms / image)
- **Detects**: General defocus blur and soft edges.
- **Best For**: Rapid first-pass culling, general photography, landscape, studio.

---

### 2. AI Subject Focus (`"ai_subject"`) - YOLO + ROI + Patch Grid
Unified intelligent algorithm combining YOLOv8 AI detection, center-ROI fallback, and patch grid bokeh protection.

- **Algorithm**:
  1. Run YOLOv8 object detection (`yolov8n.pt`) to find the highest-confidence subject bounding box.
  2. Evaluate 3 crop layers within the detection box:
     - **Full Subject Crop** (10% inset to eliminate edge background pixels)
     - **Head & Eye Zone** (top 40% of bounding box — where bird/animal eyes are located)
     - **Subject Core** (central 60% of bounding box)
  3. Score each layer using 95th percentile Laplacian + Sobel gradient energy:
     $$\text{Region Score} = p_{95}(\nabla^2 I) \times 3.0 + p_{95}(\sqrt{G_x^2 + G_y^2}) \times 0.5$$
  4. Combine using weighted blend: $\text{best} \times 0.7 + \text{median} \times 0.3$
  5. Also compute 8x8 patch grid Laplacian variance (90th percentile) for bokeh protection.
  6. Falls back to center-60% ROI crop if no YOLO detection is available.

- **Speed**: ⭐⭐⭐ (~25ms / image)
- **Detects**: Subject-aware focus sharpness — eyes, head, beak, and facial details.
- **Best For**: Birding, wildlife, shallow depth-of-field portraits, off-center subjects, macro, and heavy background bokeh.
- **Backward Compat**: Old method names `"yolo_subject"`, `"bird_subject"`, `"local_var"` all redirect here.

---

### 3. FFT Frequency Analysis (`"fft"`) - Motion Blur Detection
Performs a 2D Fast Fourier Transform, masks out central low-frequency components, and calculates high-frequency energy ratio:
$$\text{FFT Score} = \text{mean}(|\text{FFTshift}(\mathcal{F}(I))|_{\text{high\_freq}})$$
- **Speed**: ⭐⭐⭐ (~18ms / image)
- **Detects**: High-frequency spectrum energy ratio (distinguishes motion blur/camera shake from soft focus).
- **Best For**: Action shots, handheld low-light photos, and camera shake detection.

---

## Removed Algorithms (Backward Compatible)

The following algorithms were consolidated as they were mathematically redundant:

| Old Method | Redirects To | Reason |
|------------|-------------|--------|
| `"tenengrad"` | `"laplacian"` | Sobel gradient energy — functionally similar ranking behavior |
| `"brenner"` | `"laplacian"` | Horizontal pixel-difference² — subset of Laplacian |
| `"local_var"` | `"ai_subject"` | Patch variance — absorbed into AI Subject Focus's internal engine |
| `"bird_subject"` | `"ai_subject"` | Center-60% ROI — absorbed as the no-YOLO fallback path |

---

## ⚡ Multi-Threaded Batch Processing & Percentile Outliers

1. **Multi-Threaded Processing**: Sharpness computations execute in parallel using `ThreadPoolExecutor(max_workers=8)`.
2. **Percentile Outlier Detection**: Sorts session photo scores into a relative distribution. The bottom $N\%$ (default: 15%) are auto-tagged `"Blur"` and flagged as `REJECT`.
3. **SQLite Persistence**: Stores flag, score, and `"Blur"` tag in local SQLite database (`image_records`).

---

## 💻 Code Reference

```python
# culler/detectors/blur/__init__.py - calculate_sharpness router
def calculate_sharpness(pil_img, method="laplacian", yolo_model=None):
    m = (method or "laplacian").lower()
    if m in ("ai_subject", "yolo_subject", "bird_subject", "local_var", ...):
        return compute_ai_subject_sharpness(gray, pil_img, yolo_model)
    elif m == "fft":
        return compute_fft_sharpness(gray)
    else:  # laplacian, tenengrad, brenner all route here
        return compute_laplacian_sharpness(gray)
```
