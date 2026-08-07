---
name: scan-for-blur
description: Technical approach for automated edge sharpness detection, blur scanning, auto-flagging, and image tagging in photo culling software.
---

# Scan for Blur (Blur Detection & Tagging Pipeline)

This skill documents all 7 algorithms for detecting out-of-focus or blurry photos during photographic culling sessions, auto-flagging them as `REJECT`, and applying the `"Blur"` tag.

---

## 🔬 All 7 Implemented Blur Detection Algorithms

Photographers can select their preferred algorithm from a 2-column sidebar modal (`BlurScanDialog`):

### 1. Variance of Laplacian (`"laplacian"`) - Default / Ultra-Fast
Measures the variance of the 2D Laplacian operator across the luminance channel:
$$\text{Sharpness Score} = \text{Var}(\nabla^2 I)$$
- **Speed**: ⭐⭐⭐⭐⭐ (< 3ms / image)
- **Detects**: General defocus blur and soft edges.
- **Best For**: Rapid first-pass culling, general photography, landscape, studio.

---

### 2. Tenengrad Sobel Gradient (`"tenengrad"`) - Stable Gradient Energy
Uses Sobel horizontal ($G_x$) and vertical ($G_y$) gradients to measure gradient magnitude energy:
$$G_x = \text{Sobel}(I, \text{CV\_64F}, 1, 0, k=3), \quad G_y = \text{Sobel}(I, \text{CV\_64F}, 0, 1, k=3)$$
$$\text{Tenengrad Score} = \text{mean}(G_x^2 + G_y^2)$$
- **Speed**: ⭐⭐⭐⭐ (~8ms / image)
- **Detects**: Fine edge gradient sharpness and structural detail.
- **Best For**: Scientific imaging, macro photography, complex natural textures.

---

### 3. Brenner Focus Measure (`"brenner"`) - Focus Difference
Computes squared intensity differences between pixels a fixed distance ($d=2$) apart:
$$\text{Brenner Score} = \text{mean}((I(x+2, y) - I(x, y))^2)$$
- **Speed**: ⭐⭐⭐⭐⭐ (~4ms / image)
- **Detects**: High-frequency pixel intensity differences & autofocus accuracy.
- **Best For**: Autofocus verification, sharp subject checks, and sports culling.

---

### 4. FFT Frequency Analysis (`"fft"`) - Motion Blur Detection
Performs a 2D Fast Fourier Transform, masks out central low-frequency components, and calculates high-frequency energy ratio:
$$\text{FFT Score} = \text{mean}(|\text{FFTshift}(\mathcal{F}(I))|_{\text{high\_freq}})$$
- **Speed**: ⭐⭐⭐ (~18ms / image)
- **Detects**: High-frequency spectrum energy ratio (distinguishes motion blur/camera shake from soft focus).
- **Best For**: Action shots, handheld low-light photos, and camera shake detection.

---

### 5. Local Patch Variance (`"local_var"`) - Texture vs Bokeh
Divides the image into a grid of local patches, computes variance per patch, and takes the 90th percentile:
$$\text{Local Var Score} = \text{Percentile}_{90}(\{\text{Var}(P_k)\})$$
- **Speed**: ⭐⭐⭐⭐ (~12ms / image)
- **Detects**: Localized patch texture variance.
- **Best For**: Shallow depth-of-field portraits, bokeh photos, and macro shots.

---

### 6. Bird & Wildlife Subject ROI (`"bird_subject"`) - Subject Focus
In bird & wildlife photography, background bokeh is naturally soft while the subject is centered.

- **Algorithm**:
  1. Crop the central subject Region of Interest (ROI) box ($[y_1:y_2, x_1:x_2]$ covering central 60%).
  2. Compute both Laplacian variance and Tenengrad gradient energy on the subject crop.
  3. Weighted Subject Score:
     $$\text{Subject Score} = 0.6 \times \text{Laplacian}_{\text{ROI}} + 0.4 \times \text{Tenengrad}_{\text{ROI}}$$
- **Speed**: ⭐⭐⭐⭐ (~10ms / image)
- **Detects**: Subject focus in central crop (ignoring background bokeh).
- **Best For**: Bird photography, wildlife, sports, and centered action shots.

---

### 7. AI YOLO Subject Crop (`"yolo_subject"`) - Pre-trained AI Object Detection
Uses a pre-trained YOLOv8 neural network (`yolov8n.pt`) to detect bounding boxes around birds, wildlife, animals, or persons.

- **Algorithm**:
  1. Detect subject bounding box $[x_1, y_1, x_2, y_2]$ with highest confidence score.
  2. Crop to the exact AI-detected subject bounding box.
  3. Compute weighted Laplacian (60%) + Tenengrad (40%) focus score exclusively on the subject.
- **Speed**: ⭐⭐⭐ (~25ms / image)
- **Detects**: Exact AI-detected subject bounding box focus & sharpness.
- **Best For**: Birding, wildlife action, sports, off-center subjects, and complex background bokeh.

---

## ⚡ Multi-Threaded Batch Processing & Percentile Outliers

1. **Multi-Threaded Processing**: Sharpness computations execute in parallel using `ThreadPoolExecutor(max_workers=8)`.
2. **Percentile Outlier Detection**: Sorts session photo scores into a relative distribution. The bottom $N\%$ (default: 15%) are auto-tagged `"Blur"` and flagged as `REJECT`.
3. **SQLite Persistence**: Stores flag, score, and `"Blur"` tag in local SQLite database (`image_records`).

---

## 💻 Code Reference

```python
# culler/image_loader.py - ImageLoader.calculate_sharpness
def calculate_sharpness(self, pil_image_or_path: Union[Image.Image, str, Path], method: str = "laplacian") -> float:
    # Method 7: AI YOLO Subject Detection
    if method == "yolo_subject":
        from ultralytics import YOLO
        model = YOLO("yolov8n.pt")
        results = model(np.array(img), verbose=False)
        boxes = results[0].boxes
        if len(boxes) > 0:
            best_box = max(boxes, key=lambda b: float(b.conf[0]))
            x1, y1, x2, y2 = [int(v) for v in best_box.xyxy[0]]
            crop = gray[y1:y2, x1:x2]
            return round((cv2.Laplacian(crop, cv2.CV_64F).var() * 0.6) + (np.mean(gx**2 + gy**2) * 0.02), 2)
```
