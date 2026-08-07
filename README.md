# Python Image Culler

A high-performance Python photo culling application designed for professional photography workflows.
Supports **Sony ARW RAW**, **JPG**, **PNG**, and **HEIF/HEIC** image formats.

Powered by `lib/exif-tools/exiftool.exe` for fast embedded preview extraction and EXIF metadata handling.

---

## 🌟 Key Features

- 📸 **Format Support**:
  - **Sony ARW**: Ultra-fast preview extraction via embedded `exiftool.exe` (with `rawpy` fallback).
  - **JPG / JPEG**: Direct native loading with auto-rotation.
  - **PNG**: Full transparent and RGB decoding.
  - **HEIF / HEIC**: Seamless native loading via `pillow_heif`.
- ⚡ **Dual Interfaces**:
  - **CLI (`culler_cli.py`)**: Scriptable terminal image scanner, interactive text culler, auto-blur detector, and batch organizer.
  - **GUI (`culler_gui.py`)**: Modern dark-mode CustomTkinter application with thumbnail gallery, 25% instant preview downscaling, inspector zoom/pan viewer, EXIF sidebar, and single-key keyboard shortcuts.
- 🎯 **Culling & Rating System**:
  - Flag photos: **PICK** (`P`), **REJECT** (`X`), **UNFLAGGED** (`U`).
  - Star Ratings: `1` to `5` stars with instant selected button highlighting.
  - Sync star ratings directly back into file EXIF/XMP headers via ExifTool.
- 🔍 **7 Advanced Blur Detection Algorithms (`BlurScanDialog`)**:
  1. **Variance of Laplacian**: Ultra-fast edge variance (< 3ms/photo).
  2. **Tenengrad Sobel Gradient**: Stable gradient energy for natural textures (~8ms/photo).
  3. **Brenner Focus Measure**: High-frequency pixel difference focus measure (~4ms/photo).
  4. **FFT Frequency Analysis**: 2D Fast Fourier Transform high-frequency spectrum ratio for motion blur (~18ms/photo).
  5. **Local Patch Variance**: 10x10 grid patch texture variance for bokeh protection (~12ms/photo).
  6. **Bird & Wildlife Subject ROI**: Central 60% ROI crop box ignoring background bokeh (~10ms/photo).
  7. **AI YOLO Subject Crop**: Pre-trained YOLOv8 AI object detection bounding box crop (~25ms/photo).
- 👯 **3 Duplicate Detection Algorithms (`DuplicateScanDialog`)**:
  1. **Perceptual Hash (dHash)**: 64-bit difference hash vector with configurable Hamming distance threshold (1–12 bits).
  2. **Exact File Hash (MD5)**: 100% byte-identical file match.
  3. **Burst Time Window**: EXIF timestamp & sequence grouping within configurable delta time window (0.5s–5.0s).
- 💾 **Automatic Method Persistence**:
  - Automatically saves and restores your last selected blur and duplicate algorithms and sensitivity sliders in local SQLite.
- 📁 **Settings Modal & Batch Organization**:
  - Settings Modal (`⚙️ Settings`) for RAW scale (20%, 50%, 100%), White Balance, JPG Save Folder, RAW+JPG Stacking, and Picked/Rejected directory paths.
  - Batch move Picked photos to `_SELECTED/` subfolder.
  - Batch move Rejected photos to `_REJECTED/` subfolder.
  - Metadata Cleanup Modal (`🧹 Cleanup`) for stripping non-essential EXIF metadata.
  - Export culling metadata manifest to JSON or CSV.

---

## 🚀 Installation & Setup

Ensure Python 3.10+ is installed on your system.

```bash
pip install -r requirements.txt
```

ExifTool binary is included at:
`d:\Projects\image-culler\lib\exif-tools\exiftool.exe`

---

## 💻 CLI Usage (`culler_cli.py`)

### 1. Scan Directory & Report Metadata Summary
```bash
python culler_cli.py scan "C:\Path\To\Photos"
```

### 2. Interactive Terminal Culler
```bash
python culler_cli.py cull "C:\Path\To\Photos"
```

### 3. Auto-Detect & Reject Blurry Photos (Bottom 15%)
```bash
python culler_cli.py auto-blur "C:\Path\To\Photos" --percentile 15
```

### 4. Move Picked / Rejected Photos
```bash
python culler_cli.py move-picked "C:\Path\To\Photos" --target _SELECTED
python culler_cli.py move-rejected "C:\Path\To\Photos" --target _REJECTED
```

### 5. Export Manifest (JSON / CSV)
```bash
python culler_cli.py export "C:\Path\To\Photos" --output manifest.json
python culler_cli.py export "C:\Path\To\Photos" --output manifest.csv --csv
```

### 6. Sync Ratings Back to File EXIF Tags
```bash
python culler_cli.py sync-exif "C:\Path\To\Photos"
```

---

## 🖥️ GUI Usage (`culler_gui.py`)

Launch the GUI desktop application:

```bash
python culler_gui.py
```

### Keyboard Shortcuts in GUI:
| Key | Action |
|---|---|
| `P` | Flag as **PICK** (Green) |
| `X` | Flag as **REJECT** (Red) |
| `U` | **UNFLAG** photo |
| `1` - `5` | Set **Star Rating** (1 to 5 Stars) |
| `C` | Toggle **Manual Crop Tool** (Aspect ratios: 1:1, 16:9, 4:3, 3:2, 9:16, 4:5, Free) |
| `Enter` or `Ctrl+S` | **Save Crop** (When Crop mode is active) |
| `Esc` | **Cancel Manual Crop Mode** |
| `Ctrl+C` | **Copy Active Image (or Cropped Selection)** as JPEG to Clipboard |
| `Ctrl+S` | **Save Active Image As** (JPEG / PNG / WEBP format dialog) |
| `Left` / `Right` / `Up` / `Down` / `A` / `D` | Navigate `+/- 1` Photo |
| `Ctrl` + `Up` / `Down` / `Left` / `Right` | Jump `+/- 10` Photos |
| `Shift` + `Up` / `Down` / `Left` / `Right` | Move `+/- 1` Photo & **Multi-Select Range** |
| `Shift` + `Ctrl` + `Up` / `Down` / `Left` / `Right` | Jump `+/- 10` Photos & **Multi-Select Range** |
| `Ctrl` + `Click` | **Random Multi-Select** individual photo items |
| `Delete` or `D` | **Move Selected Photos to Trash / Recycle Bin** (with confirmation) |
| `Home` / `End` | Jump to **First / Last Photo** |
| `Shift` + `Home` / `End` | Multi-Select to **First / Last Photo** |
| `Page Up` / `Page Down` | Jump **10 Photos Backward / Forward** |
| `Mouse Wheel` | Zoom in / Zoom out |
| `Click & Drag` | Pan across zoomed image |
| `Double Click` | Reset Zoom & Centering |



---

## 🧪 Running Automated Unit Tests

We use **Pytest** for test execution. To run the complete automated test suite (30 unit tests covering navigation, culling engine, database persistence, RAM image caching, blur detection, and duplicate detection):

```bash
# Run test suite with pytest
pytest

# Run test suite with Python's built-in runner
python tests/run_all_tests.py
```
