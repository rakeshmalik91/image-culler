"""
AI Subject Focus Detection Algorithm.
Uses YOLOv8 object detection to locate main subject bounding box, then evaluates focus
sharpness using 95th percentile Laplacian + Sobel gradient energy on multi-layer crops.
Falls back to center-60% ROI crop when no YOLO detection is available.
"""

from pathlib import Path
from typing import Any, Optional
from PIL import Image

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

from .bird_subject import compute_bird_subject_sharpness


def evaluate_region_sharpness(crop: Any) -> float:
    """
    Clean 2-metric region sharpness evaluator.
    Computes 95th percentile Laplacian magnitude + 95th percentile Sobel gradient energy.
    Uses percentile instead of mean/variance for immunity to smooth background bokeh areas.
    """
    if crop is None or crop.size < 36:
        return 0.0
    try:
        lap_mag = np.abs(cv2.Laplacian(crop, cv2.CV_64F))
        p95_lap = float(np.percentile(lap_mag, 95))

        gx = cv2.Sobel(crop, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(crop, cv2.CV_64F, 0, 1, ksize=3)
        p95_sob = float(np.percentile(np.sqrt(gx**2 + gy**2), 95))

        return (p95_lap * 3.0) + (p95_sob * 0.5)
    except Exception:
        return 0.0


def compute_patch_grid_sharpness(crop: Any, grid_size: int = 8) -> float:
    """
    Local Patch Grid Bokeh Protection Engine.
    Divides crop into an NxN grid of patches, computes Laplacian variance per patch,
    and returns 90th percentile score. Ensures localized subject sharpness is rewarded
    even if large portions of the crop are smooth bokeh.
    """
    if crop is None or crop.size < 64:
        return 0.0
    try:
        h, w = crop.shape
        ph = max(4, h // grid_size)
        pw = max(4, w // grid_size)

        patch_scores = []
        for y in range(0, h - ph + 1, ph):
            for x in range(0, w - pw + 1, pw):
                p = crop[y:y+ph, x:x+pw]
                if p.size > 16:
                    lap_var = float(cv2.Laplacian(p, cv2.CV_64F).var())
                    patch_scores.append(lap_var)

        if not patch_scores:
            return 0.0

        # Scale to match region sharpness score range
        return float(np.percentile(patch_scores, 90)) * 0.8
    except Exception:
        return 0.0


def compute_ai_subject_sharpness(gray: Any, rgb_img: Image.Image, yolo_model: Optional[Any] = None) -> float:
    """
    AI Subject Focus sharpness score.

    Pipeline:
      1. Run YOLOv8 detection to find the highest-confidence subject bounding box.
      2. Evaluate 3 crop layers within the detection box:
         - Full Subject Crop (10% inset to eliminate edge background)
         - Head & Eye Zone (top 40% of bounding box)
         - Subject Core (central 60% of bounding box)
      3. Combine scores using weighted blend: best * 0.7 + median * 0.3
         (preserves dynamic range between sharp and blurry subjects)
      4. Also compute patch grid score for bokeh protection.
      5. Falls back to center-60% ROI crop if no YOLO detection available.
    """
    if cv2 is None or np is None or gray is None:
        return 0.0
    h, w = gray.shape
    try:
        if yolo_model is None:
            from ultralytics import YOLO
            models_dir = Path(__file__).resolve().parent.parent.parent.parent / "lib" / "models"
            models_dir.mkdir(parents=True, exist_ok=True)
            model_path = models_dir / "yolov8n.pt"
            yolo_model = YOLO(str(model_path))

        results = yolo_model(np.array(rgb_img), verbose=False)
        boxes = results[0].boxes
        if len(boxes) > 0:
            best_box = max(boxes, key=lambda b: float(b.conf[0]))
            x1, y1, x2, y2 = [int(v) for v in best_box.xyxy[0]]

            # Inset box by 10% to eliminate edge background pixels
            bw, bh = x2 - x1, y2 - y1
            cx1 = max(0, x1 + int(bw * 0.10))
            cx2 = min(w, x2 - int(bw * 0.10))
            cy1 = max(0, y1 + int(bh * 0.10))
            cy2 = min(h, y2 - int(bh * 0.10))

            if cx2 > cx1 and cy2 > cy1:
                full_crop = gray[cy1:cy2, cx1:cx2]
            else:
                full_crop = gray[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]

            if full_crop.size > 0:
                ch, cw = full_crop.shape

                # Layer 1: Full Subject Crop
                score_full = evaluate_region_sharpness(full_crop)

                # Layer 2: Head & Eye Zone (top 40% of subject box)
                head_crop = full_crop[0:max(1, int(ch * 0.40)), :]
                score_head = evaluate_region_sharpness(head_crop)

                # Layer 3: Subject Core (central 60%)
                core_y1, core_y2 = int(ch * 0.15), max(ch, int(ch * 0.85))
                core_x1, core_x2 = int(cw * 0.15), max(cw, int(cw * 0.85))
                core_crop = full_crop[core_y1:core_y2, core_x1:core_x2]
                score_core = evaluate_region_sharpness(core_crop)

                # Patch grid bokeh protection on full crop
                score_grid = compute_patch_grid_sharpness(full_crop, grid_size=8)

                # Weighted blend: best * 0.7 + median * 0.3
                # Preserves wider dynamic range than max() alone
                region_scores = sorted([score_full, score_head, score_core])
                best_region = region_scores[2]
                median_region = region_scores[1]
                blended = best_region * 0.7 + median_region * 0.3

                # Take the higher of region blend or grid score
                final = max(blended, score_grid)
                return round(final, 2)
    except Exception:
        pass

    # Fallback to central ROI crop if no object detected or YOLO unavailable
    return compute_bird_subject_sharpness(gray)


# Backward compatibility alias
compute_yolo_subject_sharpness = compute_ai_subject_sharpness
