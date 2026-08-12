"""
AI Subject Focus Detection Algorithm.
Uses YOLOv8 object detection to locate main subject bounding box, then evaluates focus
sharpness using 95th percentile Laplacian + Sobel gradient energy on multi-layer crops.
Falls back to center-60% ROI crop when no YOLO detection is available.
"""

from pathlib import Path
from typing import Any, Optional, Tuple
from PIL import Image

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

import warnings

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)
        import mediapipe as mp
    if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_mesh"):
        _mp_face_mesh = mp.solutions.face_mesh
        _mp_available = True
    else:
        _mp_available = False
        _mp_face_mesh = None
except Exception:
    _mp_available = False
    _mp_face_mesh = None

from .bird_subject import compute_bird_subject_sharpness


def evaluate_region_sharpness(crop: Any) -> float:
    """
    Region sharpness evaluator using Laplacian variance & 95th percentile gradient energy.
    Operates on quadratic variance scale matching global Laplacian sharpness scores.
    """
    if crop is None or crop.size < 36:
        return 0.0
    try:
        lap_var = float(cv2.Laplacian(crop, cv2.CV_64F).var())

        gx = cv2.Sobel(crop, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(crop, cv2.CV_64F, 0, 1, ksize=3)
        p95_sob = float(np.percentile(np.sqrt(gx**2 + gy**2), 95))
        sob_energy = (p95_sob ** 2) / 10.0

        return lap_var * 0.7 + sob_energy * 0.3
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


def extract_eye_box_mediapipe(rgb_img: Any, subject_box: Tuple[int, int, int, int]) -> Optional[Tuple[int, int, int, int]]:
    """
    Extract precise eye bounding box using MediaPipe Face Mesh (468 landmarks).
    Returns a tight box around both eyes based on key eye contour landmarks.
    Falls back to None if no face is detected or mediapipe is unavailable.
    """
    if not _mp_available or cv2 is None or np is None:
        return None

    x1, y1, x2, y2 = subject_box
    bw, bh = x2 - x1, y2 - y1
    if bw < 5 or bh < 5:
        return None

    try:
        img_arr = np.array(rgb_img)
        h_img, w_img = img_arr.shape[:2]
        sub_crop = img_arr[max(0, y1):min(h_img, y2), max(0, x1):min(w_img, x2)]
        if sub_crop.size == 0:
            return None

        with _mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        ) as face_mesh:
            results = face_mesh.process(cv2.cvtColor(sub_crop, cv2.COLOR_RGB2BGR))
            if not results.multi_face_landmarks:
                return None

            landmarks = results.multi_face_landmarks[0].landmark

            eye_indices = [
                33, 133, 160, 159, 158, 144, 145, 153,
                362, 263, 387, 386, 385, 373, 374, 380
            ]

            xs = []
            ys = []
            for idx in eye_indices:
                lm = landmarks[idx]
                xs.append(lm.x * bw)
                ys.append(lm.y * bh)

            ex1 = int(x1 + min(xs)) - int(bw * 0.05)
            ey1 = int(y1 + min(ys)) - int(bh * 0.05)
            ex2 = int(x1 + max(xs)) + int(bw * 0.05)
            ey2 = int(y1 + max(ys)) + int(bh * 0.05)

            ex1 = max(0, ex1)
            ey1 = max(0, ey1)
            ex2 = min(w_img, ex2)
            ey2 = min(h_img, ey2)

            if ex2 > ex1 and ey2 > ey1:
                return (ex1, ey1, ex2, ey2)
    except Exception:
        pass

    return None


from .eye_detector import (
    detect_animal_bird_eye,
    extract_eye_box_yolo_pose,
    extract_eye_face_box
)


def select_best_subject_box(boxes: Any, img_w: int, img_h: int) -> Optional[Any]:
    """
    Select the true primary subject box by prioritizing subject classes (person, bird, animals)
    and calculating candidate scores based on confidence, class weight, center distance, corner penalty,
    and full-frame background clutter penalty.
    """
    if not boxes or len(boxes) == 0:
        return None

    # Subject classes: person (0), bird (14), cat (15), dog (16), horse (17), sheep (18), cow (19), elephant (20), bear (21), zebra (22), giraffe (23)
    subject_classes = {0, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}

    center_img_x = img_w / 2.0
    center_img_y = img_h / 2.0
    max_dist = np.sqrt(center_img_x**2 + center_img_y**2) or 1.0

    best_box = None
    best_score = 0.02  # Minimum score threshold to reject extreme background junk

    for b in boxes:
        conf = float(b.conf[0])
        cls_id = int(b.cls[0])
        x1, y1, x2, y2 = [float(v) for v in b.xyxy[0]]
        bw = x2 - x1
        bh = y2 - y1

        # Reject giant boxes (>60% of frame width OR height unless confidence is very high)
        is_full_frame = (bw > img_w * 0.60) or (bh > img_h * 0.60)
        full_frame_penalty = 0.10 if is_full_frame else 1.0

        box_cx = (x1 + x2) / 2.0
        box_cy = (y1 + y2) / 2.0

        # Narrow Gaussian center bias (sigma = 1/5th of dimension)
        sigma_x = img_w / 5.0
        sigma_y = img_h / 5.0
        dist_sq = ((box_cx - center_img_x) / sigma_x)**2 + ((box_cy - center_img_y) / sigma_y)**2
        center_bias = np.exp(-0.5 * dist_sq)

        # Margin penalty (applied if box center is in outer 25% border of image)
        is_margin = (box_cx < img_w * 0.25 or box_cx > img_w * 0.75 or box_cy < img_h * 0.25 or box_cy > img_h * 0.75)
        margin_penalty = 0.20 if is_margin else 1.0

        is_subject = cls_id in subject_classes
        # Only grant subject class boost if confidence is >=0.30 to avoid leaf hallucinations
        class_weight = 3.0 if (is_subject and conf >= 0.30) else (1.5 if is_subject else 0.5)

        candidate_score = conf * class_weight * center_bias * margin_penalty * full_frame_penalty

        if candidate_score > best_score:
            best_score = candidate_score
            best_box = b

    return best_box


def extract_saliency_subject_box(rgb_img: Any) -> Tuple[int, int, int, int]:
    """
    Focus-Density Saliency ROI Extractor.
    Used when YOLO model fails to detect heavily camouflaged subjects in complex scenes.
    Calculates the spatial bounding box around the highest local focus energy / contrast cluster.
    Prevents background leaf clutter from expanding to full frame.
    """
    try:
        arr = np.array(rgb_img)
        if cv2 is not None and arr.size > 0:
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            h, w = gray.shape

            # Compute local Laplacian variance map (focus energy)
            lap = cv2.Laplacian(gray, cv2.CV_32F)
            lap_abs = np.abs(lap)

            # Smooth local focus energy
            focus_map = cv2.GaussianBlur(lap_abs, (31, 31), 0)

            # Apply narrow Gaussian center bias to focus map
            cy_grid, cx_grid = np.ogrid[:h, :w]
            sigma_x = w / 5.0
            sigma_y = h / 5.0
            dist_sq = ((cx_grid - w/2.0) / sigma_x)**2 + ((cy_grid - h/2.0) / sigma_y)**2
            center_mask = np.exp(-0.5 * dist_sq)
            center_mask = 0.02 + 0.98 * center_mask  # 2% floor for extreme edges
            weighted = focus_map * center_mask

            # Multi-percentile focus density search
            for p in [85, 75, 65]:
                thresh_val = np.percentile(weighted, p)
                _, mask = cv2.threshold(weighted, thresh_val, 255, cv2.THRESH_BINARY)
                mask = mask.astype(np.uint8)

                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    valid_candidates = []
                    for c in contours:
                        bx, by, bw, bh = cv2.boundingRect(c)
                        area = bw * bh
                        if area < 100:
                            continue
                        # Ignore massive contours that span most of the image (>65% w or >65% h)
                        if bw > 0.65 * w or bh > 0.65 * h:
                            continue

                        # Score contour by average focus energy density & centrality
                        c_mask = np.zeros((h, w), dtype=np.uint8)
                        cv2.drawContours(c_mask, [c], -1, 255, -1)
                        density = cv2.mean(weighted, mask=c_mask)[0]

                        cx_c = bx + bw / 2.0
                        cy_c = by + bh / 2.0
                        
                        # Calculate narrow Gaussian center bias for contour candidate
                        dist_sq_c = ((cx_c - w/2.0) / sigma_x)**2 + ((cy_c - h/2.0) / sigma_y)**2
                        cb_val = np.exp(-0.5 * dist_sq_c)

                        score = density * cb_val
                        valid_candidates.append((score, (bx, by, bw, bh)))

                    if valid_candidates:
                        # Pick contour cluster with HIGHEST focus density (the sharp bird/subject)
                        best_cand = max(valid_candidates, key=lambda item: item[0])
                        bx, by, bw, bh = best_cand[1]

                        margin_x, margin_y = int(bw * 0.10), int(bh * 0.10)
                        x1 = max(0, bx - margin_x)
                        y1 = max(0, by - margin_y)
                        x2 = min(w, bx + bw + margin_x)
                        y2 = min(h, by + bh + margin_y)
                        if (x2 - x1) > 20 and (y2 - y1) > 20:
                            return (x1, y1, x2, y2)
    except Exception:
        pass

    img_w, img_h = rgb_img.size if hasattr(rgb_img, "size") else (400, 400)
    return (int(img_w * 0.25), int(img_h * 0.25), int(img_w * 0.75), int(img_h * 0.75))


def detect_camouflaged_subject(img_np: np.ndarray, yolo_model: Any, img_w: int, img_h: int) -> Optional[Any]:
    """
    Advanced Multi-Layer Camouflage Breaking Pipeline.
    Applies aggressive preprocessing to reveal structurally hidden subjects.
    """
    if yolo_model is None or cv2 is None:
        return None

    # 1. Gamma Correction (Shadow Recovery)
    # Camouflaged subjects often hide in shadows or bright spots.
    inv_gamma = 1.0 / 1.5
    table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    gamma_corrected = cv2.LUT(img_np, table)
    
    results_gamma = yolo_model(gamma_corrected, conf=0.03, verbose=False)
    boxes_gamma = results_gamma[0].boxes if len(results_gamma) > 0 else []
    best_box = select_best_subject_box(boxes_gamma, img_w, img_h)
    if best_box is not None:
        return best_box

    # 2. Unsharp Masking (Edge / High-Frequency detail enhancement)
    # Breaks structural camouflage by amplifying micro-contrast
    blurred = cv2.GaussianBlur(img_np, (9, 9), 10.0)
    unsharp = cv2.addWeighted(img_np, 1.5, blurred, -0.5, 0)
    
    results_unsharp = yolo_model(unsharp, conf=0.03, verbose=False)
    boxes_unsharp = results_unsharp[0].boxes if len(results_unsharp) > 0 else []
    best_box = select_best_subject_box(boxes_unsharp, img_w, img_h)
    if best_box is not None:
        return best_box

    # 3. LAB CLAHE (Luminance Local Contrast)
    try:
        lab = cv2.cvtColor(img_np, cv2.COLOR_RGB2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        cl = clahe.apply(l_ch)
        enhanced = cv2.cvtColor(cv2.merge((cl, a_ch, b_ch)), cv2.COLOR_LAB2RGB)

        results_clahe = yolo_model(enhanced, conf=0.03, verbose=False)
        boxes_clahe = results_clahe[0].boxes if len(results_clahe) > 0 else []
        return select_best_subject_box(boxes_clahe, img_w, img_h)
    except Exception:
        pass

    return None


def compute_ai_subject_sharpness(
    gray: Any,
    rgb_img: Image.Image,
    yolo_model: Optional[Any] = None,
    return_box: bool = False,
    eye_detection_method: str = "yolo",
    yolo_pose_model: Optional[Any] = None
) -> float:
    """
    AI Subject Focus sharpness score with 2-level Subject/Body + Eye/Face detection.

    Pipeline:
      1. Stage 1: Standard YOLOv8 detection (conf=0.15) with subject class prioritization & corner margin filtering.
      2. Stage 2: Low-confidence & CLAHE contrast-enhanced YOLOv8 pass for camouflaged wildlife/subjects.
      3. Stage 3: Focus-density ROI fallback if YOLO yields no candidates.
      4. Stage 4: Level 2 Head/Eye/Face ROI extraction inside subject box.
      5. Evaluate multi-layer sharpness score across subject & eye crops.
    """
    if cv2 is None or np is None:
        if return_box:
            return 0.0, (None, None)
        return 0.0

    gray_available = gray is not None
    if gray_available:
        h, w = gray.shape
    else:
        h, w = 0, 0
    best_box_coords = None
    eye_box_coords = None

    try:
        if hasattr(rgb_img, "convert") and hasattr(rgb_img, "mode") and rgb_img.mode != "RGB":
            rgb_img = rgb_img.convert("RGB")
        img_w, img_h = rgb_img.size if hasattr(rgb_img, "size") else (w, h)

        if yolo_model is None:
            from ultralytics import YOLO
            models_dir = Path(__file__).resolve().parent.parent.parent.parent / "lib" / "models"
            models_dir.mkdir(parents=True, exist_ok=True)
            custom_model_path = models_dir / "yolo_custom.pt"
            
            if custom_model_path.exists():
                model_path = custom_model_path
            else:
                model_path = models_dir / "yolov8n.pt"
                # Ultralytics will automatically download to base_model_path if it doesn't exist
                
            yolo_model = YOLO(str(model_path))

        # Stage 1: High-confidence YOLO inference (conf=0.15)
        results = yolo_model(np.array(rgb_img), conf=0.15, verbose=False)
        boxes = results[0].boxes if len(results) > 0 else []
        best_box = select_best_subject_box(boxes, img_w, img_h)

        # Stage 2: Low-confidence pass
        if best_box is None:
            results_low = yolo_model(np.array(rgb_img), conf=0.03, verbose=False)
            boxes_low = results_low[0].boxes if len(results_low) > 0 else []
            best_box = select_best_subject_box(boxes_low, img_w, img_h)

        # Stage 3: Advanced Multi-Layer Camouflage Breaking
        if best_box is None and cv2 is not None:
            best_box = detect_camouflaged_subject(np.array(rgb_img), yolo_model, img_w, img_h)

        if best_box is not None:
            x1, y1, x2, y2 = [int(v) for v in best_box.xyxy[0]]
            best_box_coords = (x1, y1, x2, y2)
        else:
            # Stage 3: Saliency / Contrast ROI Fallback
            best_box_coords = extract_saliency_subject_box(rgb_img)

        # Stage 4: Extract Level 2 Head/Eye Box inside primary subject box
        eye_box_coords = extract_eye_face_box(
            rgb_img,
            best_box_coords,
            method=eye_detection_method,
            yolo_pose_model=yolo_pose_model
        )

        # If gray is not available (box-only detection mode), return dual boxes immediately
        if not gray_available:
            if return_box:
                return 0.0, (best_box_coords, eye_box_coords)
            return 0.0

        x1, y1, x2, y2 = best_box_coords

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

            # Layer 1: Full Subject Crop (Level 1 Box)
            score_full = evaluate_region_sharpness(full_crop)

            # Layer 2: Eye / Face Zone Crop (Level 2 Box)
            if eye_box_coords:
                ex1, ey1, ex2, ey2 = eye_box_coords
                eye_crop = gray[max(0, ey1):min(h, ey2), max(0, ex1):min(w, ex2)]
                if eye_crop.size > 16:
                    score_eye = evaluate_region_sharpness(eye_crop)
                else:
                    head_crop = full_crop[0:max(1, int(ch * 0.40)), :]
                    score_eye = evaluate_region_sharpness(head_crop)
            else:
                head_crop = full_crop[0:max(1, int(ch * 0.40)), :]
                score_eye = evaluate_region_sharpness(head_crop)

            # Layer 3: Subject Core (central 60%)
            core_y1, core_y2 = int(ch * 0.15), max(ch, int(ch * 0.85))
            core_x1, core_x2 = int(cw * 0.15), max(cw, int(cw * 0.85))
            core_crop = full_crop[core_y1:core_y2, core_x1:core_x2]
            score_core = evaluate_region_sharpness(core_crop)

            # Patch grid bokeh protection on full crop
            score_grid = compute_patch_grid_sharpness(full_crop, grid_size=8)

            # Weighted blend: when a real eye box is detected, eye sharpness
            # dominates because it's the most critical focus indicator for
            # wildlife/portrait photography. Without eye detection, fall back
            # to the generic best+median blend.
            if eye_box_coords:
                # Eye-dominant blend: eye drives the score; grid penalty is
                # skipped because the grid is dominated by out-of-focus
                # background patches when the subject is small in frame.
                final = score_eye * 0.55 + max(score_full, score_core) * 0.30 + min(score_full, score_core) * 0.15
            else:
                # Generic blend favoring sharpest region
                region_scores = sorted([score_full, score_eye, score_core])
                best_region = region_scores[2]
                median_region = region_scores[1]
                blended = best_region * 0.6 + median_region * 0.4

                # Cap grid contribution so out-of-focus crops receive genuine low scores and get rejected
                final = blended * 0.75 + min(blended, score_grid) * 0.25

            if return_box and best_box_coords:
                return round(final, 2), (best_box_coords, eye_box_coords)
            return round(final, 2)
    except Exception:
        pass

    # Fallback to central ROI crop if no object detected or YOLO unavailable
    if gray_available:
        fallback_score = compute_bird_subject_sharpness(gray)
    else:
        fallback_score = 0.0
    if return_box:
        return fallback_score, (None, None)
    return fallback_score


# Backward compatibility alias
compute_yolo_subject_sharpness = compute_ai_subject_sharpness
