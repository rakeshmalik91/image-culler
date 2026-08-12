import os
import shutil
from pathlib import Path
import threading
import sys

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

def train_custom_yolo(
    dataset_dir: str = "_DATASET", 
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
        
    dataset_yaml = Path(dataset_dir) / "dataset.yaml"
    if not dataset_yaml.exists():
        if on_error:
            on_error(Exception(f"Dataset YAML not found at {dataset_yaml}. You need to annotate at least one image first."))
        return False
        
    def worker():
        try:
            if on_progress:
                on_progress("Initializing YOLOv8 Nano model...")
                
            models_dir = Path(__file__).resolve().parent.parent / "lib" / "models"
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

            # Train the model
            # We use workers=0 to prevent multiprocessing freeze on Windows
            results = model.train(
                data=str(dataset_yaml.absolute()),
                epochs=epochs,
                imgsz=640,
                device=device,
                workers=0,
                project=str(runs_dir),
                name="culler_custom",
                exist_ok=True, # overwrite if training again
                verbose=False
            )
            
            best_weights = runs_dir / "culler_custom" / "weights" / "best.pt"
            
            # Copy to lib/models/yolo_custom.pt
            target_dir = Path("lib") / "models"
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
