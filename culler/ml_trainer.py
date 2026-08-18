import os
import shutil
from pathlib import Path
import threading
import sys
from typing import Optional

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

from culler.paths import DATASET_DIR


def train_custom_yolo(
    dataset_dir: Optional[str] = None, 
    epochs: int = 25, 
    on_progress=None, 
    on_complete=None, 
    on_error=None,
    sync: bool = False
):
    """
    Trains a custom YOLO model using the constructed dataset.
    Executes asynchronously on a background thread unless sync=True.
    """
    if YOLO is None:
        if on_error:
            on_error(Exception("ultralytics package is not installed. Please install it to use Custom Training."))
        return False
        
    ds_dir = Path(dataset_dir) if dataset_dir else DATASET_DIR
    dataset_yaml = ds_dir / "dataset.yaml"
    if not dataset_yaml.exists():
        if on_error:
            on_error(Exception(f"Dataset YAML not found at {dataset_yaml}. You need to annotate at least one image first."))
        return False
        
    def worker():
        try:
            if on_progress:
                on_progress("Initializing YOLOv8 Nano model...")
                
            base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
            models_dir = base_dir / "lib" / "models"
            models_dir.mkdir(parents=True, exist_ok=True)
            base_model_path = models_dir / "yolov8n.pt"
            
            # Ultralytics will automatically download to base_model_path if it doesn't exist
            
            model = YOLO(str(base_model_path))
            
            try:
                import torch
                device = 0 if torch.cuda.is_available() else "cpu"
                device_name = f"GPU ({torch.cuda.get_device_name(0)})" if torch.cuda.is_available() else "CPU"
            except Exception:
                device = "cpu"
                device_name = "CPU"

            if on_progress:
                on_progress(0, epochs, f"Starting training on {device_name} for {epochs} epochs...")
                
            runs_dir = Path(dataset_dir).absolute() / "runs"
            
            def on_epoch_end(trainer):
                ep = trainer.epoch + 1
                tot = trainer.epochs
                if on_progress:
                    on_progress(ep, tot, f"Training on {device_name}: Epoch {ep}/{tot} completed")

            model.add_callback("on_train_epoch_end", on_epoch_end)

            # Train the model with maximum throughput optimizations:
            # - cache='ram': 0ms RAM image caching across epochs
            # - val=False: bypasses 10-15s per-epoch validation overhead
            # - batch=16: optimal GPU utilization
            # - plots=False: skips disk/matplotlib plotting overhead
            # - workers=0: prevents Windows multiprocessing freeze
            results = model.train(
                data=str(dataset_yaml.absolute()),
                epochs=epochs,
                imgsz=640,
                device=device,
                workers=0,
                batch=16,
                cache="ram",
                val=False,
                plots=False,
                save=True,
                project=str(runs_dir),
                name="culler_custom",
                exist_ok=True, # overwrite if training again
                verbose=False
            )
            
            best_weights = runs_dir / "culler_custom" / "weights" / "best.pt"
            
            # Copy to lib/models/yolo_custom.pt
            base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
            target_dir = base_dir / "lib" / "models"
            target_dir.mkdir(parents=True, exist_ok=True)
            target_weights = target_dir / "yolo_custom.pt"
            
            if best_weights.exists():
                shutil.copy2(best_weights, target_weights)
                if on_complete:
                    on_complete(str(target_weights))
                return True
            else:
                raise Exception("Training finished but best.pt was not found.")
        except Exception as e:
            if on_error:
                on_error(e)
            else:
                print(f"[ERROR] Training failed: {e}")
            return False
                
    if sync:
        return worker()
    else:
        threading.Thread(target=worker, daemon=True).start()
        return True
