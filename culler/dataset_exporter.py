import os
import shutil
import uuid
from pathlib import Path
from typing import Optional, Tuple

def create_dataset_structure(dataset_dir: str = "_DATASET"):
    """Creates the YOLO format dataset directory structure."""
    base = Path(dataset_dir)
    images_dir = base / "images" / "train"
    labels_dir = base / "labels" / "train"
    
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    
    yaml_path = base / "dataset.yaml"
    if not yaml_path.exists():
        yaml_content = f"""path: {base.absolute().as_posix()}
train: images/train
val: images/train

names:
  0: subject
  1: eye
"""
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
            
    return images_dir, labels_dir

def normalize_box(box: Tuple[int, int, int, int], img_w: int, img_h: int) -> str:
    """Converts (x1, y1, x2, y2) to YOLO format (x_center, y_center, width, height) normalized."""
    x1, y1, x2, y2 = box
    
    # Ensure bounds
    x1 = max(0, min(x1, img_w))
    x2 = max(0, min(x2, img_w))
    y1 = max(0, min(y1, img_h))
    y2 = max(0, min(y2, img_h))
    
    bw = x2 - x1
    bh = y2 - y1
    cx = x1 + bw / 2.0
    cy = y1 + bh / 2.0
    
    # Normalize to 0.0 - 1.0
    cx_n = cx / img_w
    cy_n = cy / img_h
    bw_n = bw / img_w
    bh_n = bh / img_h
    
    return f"{cx_n:.6f} {cy_n:.6f} {bw_n:.6f} {bh_n:.6f}"

def save_annotation(
    image_path: str,
    img_w: int,
    img_h: int,
    subject_box: Optional[Tuple[int, int, int, int]],
    eye_box: Optional[Tuple[int, int, int, int]],
    dataset_dir: str = "_DATASET",
    pil_image=None
) -> bool:
    """
    Saves an image and its annotations into a YOLO training dataset.
    Returns True on success.
    """
    if not subject_box and not eye_box:
        return False
        
    try:
        images_dir, labels_dir = create_dataset_structure(dataset_dir)
        
        # Generate unique ID for this sample
        sample_id = str(uuid.uuid4())[:8]
        orig_name = Path(image_path).name
        safe_name = f"anno_{sample_id}_{orig_name}"
        if not safe_name.lower().endswith(('.jpg', '.jpeg', '.png')):
            safe_name += ".jpg"
            
        target_img_path = images_dir / safe_name
        target_lbl_path = labels_dir / f"{Path(safe_name).stem}.txt"
        
        # Save image
        if pil_image:
            if hasattr(pil_image, "mode") and pil_image.mode in ("RGBA", "P"):
                pil_image = pil_image.convert("RGB")
            pil_image.save(target_img_path, format="JPEG", quality=95)
        else:
            shutil.copy2(image_path, target_img_path)
        
        # Write labels
        lines = []
        if subject_box:
            box_str = normalize_box(subject_box, img_w, img_h)
            lines.append(f"0 {box_str}")
        
        if eye_box:
            box_str = normalize_box(eye_box, img_w, img_h)
            lines.append(f"1 {box_str}")
            
        with open(target_lbl_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
            
        return True
    except Exception as e:
        print(f"Error saving annotation: {e}")
        return False
