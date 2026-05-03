# 🎥 Duplicate File Finder

A fast, practical tool to detect **exact file duplicates (all file types)** and **near-duplicate videos (via frame fingerprinting)** — available in both **Python (advanced GUI/CLI)** and **PowerShell (interactive CLI)** versions.

---

## ✨ Features

### 🚀 Python Version (Advanced GUI + CLI)
- 🖼 **New:** Easy-to-use GUI interface (starts automatically if no arguments are provided).
- 🖼 **New:** Visual Treeview to inspect duplicates and bulk-delete.
- 🎯 **New:** Exact match mode for **all file types** (videos, images, documents, audio) using smart size-grouping and hashing.
- 🗑 **New:** Safe Deletion (moves to Recycle Bin via `send2trash` or permanently deletes).
- ⚡ Lightning fast video processing with Duration-based grouping and Visual Quick Filters.
- 🎞 **New:** Perceptual Hashing (aHash) perfectly detects re-encoded, compressed, or resized videos.
- 🎛 **New:** Granular Performance Filters: Individually toggle Duration Grouping, Quick Signatures, and High FPS extraction.
- ⚙️ **New:** Adjustable similarity threshold via GUI or CLI.
- 🚀 Interactive GPU acceleration support (CUDA / QSV / DXVA2) with automatic CPU fallback.
- 💾 Persistent cache with robust per-file auto-save (safe against Ctrl+C / crashes).

---

### 🔰 PowerShell Version (Interactive)
- ✔ Works without Python.
- 💬 **New:** Interactive setup prompts at launch (Select Mode, File Types, Deletion type).
- 🎯 **New:** Exact match mode for **all file types**.
- ⚡ Upgraded video matching using `ffprobe` duration grouping and Visual Quick Filters.
- 🎞 **New:** Perceptual Hashing (aHash) for finding resized/re-encoded videos.
- 🎛 **New:** Granular Performance Filters and configurable match threshold.
- 🚀 **New:** Interactive GPU acceleration (CUDA, QSV, D3D11VA) with CPU fallback.
- 🗑 Safe Deletion to Recycle Bin.

---

## 🆚 Which Version Should You Use?

| Use Case | Recommended |
|----------|------------|
| No Python installed | 🟢 PowerShell |
| Large video collections | 🚀 Python |
| Maximum speed & accuracy | 🚀 Python |
| Simplicity | 🟢 PowerShell |

---

## ⚙️ Requirements

### Common
- 🎬 FFmpeg (required for both versions)  
  https://ffmpeg.org/download.html

---

### PowerShell Version
- Windows PowerShell **5.1+**

---

### Python Version
- Python **3.7+**
- FFmpeg + FFprobe in PATH
- Install dependencies: `pip install -r requirements.txt`

---

## 📦 Usage

### 🟢 PowerShell (Interactive)

Run the script and follow the on-screen prompts:
```powershell
& '.\Duplicate File Finder.ps1'
```

### 🚀 Python (GUI & CLI)

**Launch the GUI (Settings & Results Treeview):**
```bash
python Duplicate_File_Finder.py
```

**Run purely from the CLI:**
```bash
python Duplicate_File_Finder.py --mode exact --file-types images --delete-mode recycle --path "C:\path\to\files"
```

Options:
- `--path PATH` : Folder to scan (default: current directory)
- `--recurse` : Scan subfolders recursively
- `--mode {video,exact}` : Scan mode: video (similar) or exact (identical) (default: video)
- `--file-types {all,videos,images,documents,audio}` : File types to scan (only used in exact mode)
- `--delete-mode {permanent,recycle}` : Deletion method
- `--gpu {prompt,auto,cpu,cuda,qsv,dxva2}` : Hardware acceleration for video mode (default: prompt)
- `--threshold THRESHOLD` : Similarity threshold for video mode (default: 70.0)
- `--skip-duration-filter` : Skips duration grouping to find edited/cut videos (slower).
- `--skip-quick-signatures` : Skips the 100% exact keyframe check.
- `--extract-more-frames` : Extracts 1 frame every 5s instead of 10s for higher accuracy on re-encodes.

---

## 📜 License

This project is licensed under the MIT License — see the LICENSE file for details.