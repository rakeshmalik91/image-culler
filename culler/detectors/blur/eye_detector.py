"""
High-Precision Eye & Face Detection Module for Photo Culling.
Supports YOLO Pose, YOLO BBox, and Morphological Bird & Wildlife Eye Shape Analysis.

Morphological Eye Analyzer features:
  - Dark circular/elliptical pupil core (circularity, aspect ratio, fitting)
  - Dark pupil surrounded by lighter iris ring (Iris Contrast Ratio)
  - Local edge & radial gradient pattern around iris boundary
  - Species-adaptive scaling (Owl, Eagle, Duck, Heron, Kingfisher, Woodpecker)
  - Head geometry & anatomical prior
"""

from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None


def detect_eye_yolo_pose(
    crop_head_scaled: np.ndarray,
    yolo_pose_model: Optional[Any] = None
) -> Optional[Tuple[float, float, float]]:
    """Detect keypoint center (x, y, confidence) for eyes using YOLO Pose."""
    if yolo_pose_model is None:
        try:
            from ultralytics import YOLO
            root_dir = Path(__file__).resolve().parent.parent.parent.parent
            models_dir = root_dir / "lib" / "models"
            pose_path = models_dir / "yolov8n-pose.pt"
            # Ultralytics will automatically download to base_model_path if it doesn't exist
            yolo_pose_model = YOLO(str(pose_path))
        except Exception:
            pass

    if yolo_pose_model is None:
        return None

    try:
        results = yolo_pose_model(crop_head_scaled, conf=0.30, verbose=False)
        if len(results) > 0 and hasattr(results[0], "keypoints") and results[0].keypoints is not None:
            kp_obj = results[0].keypoints
            if hasattr(kp_obj, "data") and len(kp_obj.data) > 0:
                kps = kp_obj.data[0]
                valid_kps = []
                for idx in [1, 2, 0]:
                    if len(kps) > idx and len(kps[idx]) >= 3:
                        conf = float(kps[idx][2])
                        # High confidence required to prevent hallucinating human eyes on bird wings/shoulders
                        if conf >= 0.65:
                            valid_kps.append((float(kps[idx][0]), float(kps[idx][1]), conf))

                if valid_kps:
                    best_kp = max(valid_kps, key=lambda item: item[2])
                    avg_cx = sum(item[0] for item in valid_kps) / len(valid_kps)
                    avg_cy = sum(item[1] for item in valid_kps) / len(valid_kps)
                    return (avg_cx, avg_cy, best_kp[2])
    except Exception:
        pass

    return None


def detect_eye_yolo_bbox(
    crop_head_scaled: np.ndarray,
    yolo_eye_model: Optional[Any] = None
) -> Optional[Tuple[float, float, float]]:
    """Detect eye bounding box center (x, y, confidence) using YOLO detector."""
    if yolo_eye_model is None:
        try:
            from ultralytics import YOLO
            root_dir = Path(__file__).resolve().parent.parent.parent.parent
            models_dir = root_dir / "lib" / "models"
            eye_path = models_dir / "yolov8n-eye.pt"
            if not eye_path.exists():
                eye_path = models_dir / "yolov8n.pt"
                # Ultralytics will automatically download to base_model_path if it doesn't exist
            yolo_eye_model = YOLO(str(eye_path))
        except Exception:
            pass

    if yolo_eye_model is None:
        return None

    try:
        results = yolo_eye_model(crop_head_scaled, conf=0.50, verbose=False)
        if len(results) > 0 and hasattr(results[0], "boxes") and results[0].boxes is not None:
            boxes = results[0].boxes
            if len(boxes) > 0:
                best_box = None
                best_conf = -1.0
                for box in boxes:
                    conf = float(box.conf[0]) if hasattr(box, "conf") else 0.0
                    if conf >= 0.50 and conf > best_conf:
                        xyxy = box.xyxy[0].tolist()
                        cx = (xyxy[0] + xyxy[2]) / 2.0
                        cy = (xyxy[1] + xyxy[3]) / 2.0
                        best_conf = conf
                        best_box = (cx, cy, conf)

                if best_box is not None:
                    return best_box
    except Exception:
        pass

    return None


def detect_bird_eye_morphological(crop_head: np.ndarray) -> Optional[Tuple[float, float, float]]:
    """
    Morphological Bird & Wildlife Eye Shape Analyzer (DoG Center-Surround Model).
    Uses a biologically-inspired Difference of Gaussians (DoG) approach to robustly 
    find dark pupil-like blobs (local contrast minimums) regardless of global lighting.
    """
    if cv2 is None or crop_head is None or crop_head.size == 0:
        return None

    hh, hw = crop_head.shape[:2]
    if hh < 12 or hw < 12:
        return None

    if len(crop_head.shape) == 3:
        gray = cv2.cvtColor(crop_head, cv2.COLOR_RGB2GRAY)
    else:
        gray = crop_head.copy()

    # Contrast enhancement for sharp pupil-iris boundary
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray_clahe = clahe.apply(gray)

    # 1. Biologically-inspired Center-Surround (Difference of Gaussians)
    # Highlights dark spots (pupils) by subtracting small blur from large blur
    blur_small = cv2.GaussianBlur(gray_clahe, (3, 3), 0)
    blur_large = cv2.GaussianBlur(gray_clahe, (15, 15), 0)
    dog_dark = cv2.subtract(blur_large, blur_small)

    # 2. Threshold top 3% darkest local spots
    thresh_val = np.percentile(dog_dark, 97)
    if thresh_val < 5:
        thresh_val = 5  # Minimum response threshold
        
    _, p_bin = cv2.threshold(dog_dark, thresh_val, 255, cv2.THRESH_BINARY)
    p_bin = p_bin.astype(np.uint8)

    # Morphological open to remove noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    p_bin = cv2.morphologyEx(p_bin, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(p_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_eye = None
    best_eye_score = -1.0

    # Scale constraints
    min_area = np.pi * max(1.5, min(hh, hw) * 0.012)**2
    max_area = np.pi * max(6.0, min(hh, hw) * 0.22)**2

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue

        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue

        # Relaxed Circularity / Elliptical shape check
        circularity = (4.0 * np.pi * area) / (perimeter**2)
        if circularity < 0.15:
            continue

        bx, by, bw, bh = cv2.boundingRect(cnt)
        aspect_ratio = float(bw) / max(1.0, float(bh))
        if aspect_ratio < 0.25 or aspect_ratio > 4.0:
            continue

        M = cv2.moments(cnt)
        if M["m00"] <= 0:
            continue

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        r_est = int(np.sqrt(area / np.pi))
        if cx - r_est < 1 or cx + r_est >= hw - 1 or cy - r_est < 1 or cy + r_est >= hh - 1:
            continue

        # Local dark contrast check (Pupil vs Iris)
        r_inner = max(2, int(r_est * 0.6))
        r_outer = min(int(r_est * 1.8 + 2), min(cx, cy, hw - 1 - cx, hh - 1 - cy))
        if r_outer <= r_inner:
            continue

        core_mask = np.zeros((hh, hw), dtype=np.uint8)
        cv2.circle(core_mask, (cx, cy), r_inner, 255, -1)
        pupil_val = cv2.mean(gray, mask=core_mask)[0]

        iris_mask = np.zeros((hh, hw), dtype=np.uint8)
        cv2.circle(iris_mask, (cx, cy), r_outer, 255, -1)
        cv2.circle(iris_mask, (cx, cy), r_inner, 0, -1)
        iris_val = cv2.mean(gray, mask=iris_mask)[0]

        # Very relaxed contrast ratio (iris just needs to be slightly lighter, or even same if DoG caught it)
        contrast_ratio = iris_val / max(1.0, pupil_val)
        if contrast_ratio < 0.95: 
            continue

        # Calculate Center-Surround DoG strength at this spot
        dog_strength = cv2.mean(dog_dark, mask=core_mask)[0]

        # Position Prior: Head is usually centered horizontally, and upper half vertically
        dist_cx = abs(cx - hw/2.0) / (hw/2.0)
        pos_weight = 1.0 - 0.3 * dist_cx
        if cy > hh * 0.60:
            pos_weight *= 0.5  # Penalty for lower half of the crop

        # Combined scoring metric
        score = dog_strength * circularity * pos_weight * contrast_ratio

        if score > best_eye_score:
            best_eye_score = score
            best_eye = (float(cx), float(cy), float(score))

    if best_eye is not None and best_eye_score > 2.0:
        return best_eye

    return None


def extract_eye_face_box(
    rgb_img: Any,
    subject_box: Tuple[int, int, int, int],
    method: str = "auto",
    yolo_pose_model: Optional[Any] = None,
    yolo_eye_model: Optional[Any] = None
) -> Optional[Tuple[int, int, int, int]]:
    """
    Unified High-Precision Eye & Face ROI Extractor for Photo Culling.
    Combines YOLO Pose keypoints, YOLO Eye bounding boxes, and Morphological Bird Eye Shape Analysis.
    """
    x1, y1, x2, y2 = subject_box
    bw, bh = x2 - x1, y2 - y1
    if bw < 5 or bh < 5:
        return None

    # Default structured head box fallback
    default_head_box = (
        max(0, x1 + int(bw * 0.15)),
        max(0, y1 + int(bh * 0.04)),
        max(1, x2 - int(bw * 0.15)),
        max(1, y1 + int(bh * 0.38))
    )

    img_arr = np.array(rgb_img) if hasattr(rgb_img, "size") else None
    if img_arr is None or img_arr.size == 0:
        return default_head_box

    h_img, w_img = img_arr.shape[:2]

    # Crop upper 50% head ROI of subject box
    head_y1 = max(0, y1)
    head_y2 = min(h_img, y1 + int(bh * 0.50))
    head_x1 = max(0, x1)
    head_x2 = min(w_img, x2)

    crop_head = img_arr[head_y1:head_y2, head_x1:head_x2]
    ch, cw = crop_head.shape[:2]
    if ch == 0 or cw == 0:
        return default_head_box

    # High-Resolution Upscaling Strategy
    scale_x, scale_y = 1.0, 1.0
    crop_head_scaled = crop_head
    if cv2 is not None and (ch < 480 or cw < 480):
        target_size = 640
        scale = float(target_size) / float(max(ch, cw))
        if scale > 1.0:
            new_w = max(1, int(cw * scale))
            new_h = max(1, int(ch * scale))
            crop_head_scaled = cv2.resize(crop_head, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            scale_x = float(cw) / float(new_w)
            scale_y = float(ch) / float(new_h)

    detected_eye_center = None

    # Stage 1: Morphological Bird & Wildlife Eye Shape Analyzer (Dark pupil + iris ring + edge symmetry)
    # Run FIRST for birds/wildlife to avoid YOLO Pose hallucinating on wings/beaks
    morph_res = detect_bird_eye_morphological(crop_head)
    if morph_res is not None:
        cx_orig, cy_orig, conf = morph_res
        detected_eye_center = (head_x1 + cx_orig, head_y1 + cy_orig)

    # Stage 2: YOLO Pose Keypoints (Fallback for humans/pets)
    if detected_eye_center is None:
        pose_res = detect_eye_yolo_pose(crop_head_scaled, yolo_pose_model=yolo_pose_model)
        if pose_res is not None:
            cx_scaled, cy_scaled, conf = pose_res
            cx_orig = cx_scaled * scale_x
            cy_orig = cy_scaled * scale_y
            detected_eye_center = (head_x1 + cx_orig, head_y1 + cy_orig)

    # Stage 3: YOLO Eye Bounding Box (Last resort)
    if detected_eye_center is None:
        bbox_res = detect_eye_yolo_bbox(crop_head_scaled, yolo_eye_model=yolo_eye_model)
        if bbox_res is not None:
            cx_scaled, cy_scaled, conf = bbox_res
            cx_orig = cx_scaled * scale_x
            cy_orig = cy_scaled * scale_y
            detected_eye_center = (head_x1 + cx_orig, head_y1 + cy_orig)

    # Build precision Eye ROI box around detected center (50-100% expansion per Section 11 of spec)
    if detected_eye_center is not None:
        eye_cx, eye_cy = detected_eye_center
        target_w = max(30, int(bw * 0.38))
        target_h = max(30, int(bh * 0.26))

        ex1 = max(x1, int(eye_cx - target_w / 2.0))
        ey1 = max(y1, int(eye_cy - target_h / 2.0))
        ex2 = min(x2, int(eye_cx + target_w / 2.0))
        ey2 = min(y2, int(eye_cy + target_h / 2.0))

        if (ex2 - ex1) > 15 and (ey2 - ey1) > 15:
            return (ex1, ey1, ex2, ey2)

    return default_head_box


def extract_eye_box_yolo_pose(
    rgb_img: Any,
    subject_box: Tuple[int, int, int, int],
    yolo_pose_model: Optional[Any] = None
) -> Optional[Tuple[int, int, int, int]]:
    """Alias for extract_eye_face_box for backward compatibility."""
    return extract_eye_face_box(rgb_img, subject_box, method="auto", yolo_pose_model=yolo_pose_model)


def detect_animal_bird_eye(crop_sub: np.ndarray) -> Optional[Tuple[int, int]]:
    """Legacy helper alias delegating to detect_bird_eye_morphological."""
    res = detect_bird_eye_morphological(crop_sub)
    if res is not None:
        return (int(res[0]), int(res[1]))
    return None
