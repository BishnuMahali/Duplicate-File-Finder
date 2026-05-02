# 🎥 Duplicate Video Finder

A fast, practical tool to detect **duplicate or near-duplicate videos** using **frame fingerprinting** — available in both **PowerShell (basic)** and **Python (advanced)** versions.

> ⚠️ Currently optimized for **video files only**  
> 🧠 Future goal: evolve into a **universal duplicate finder (all file types)**

---

## ✨ Features

### 🔰 PowerShell (Basic Version)
- ✔ Works without Python
- 🎞 Frame-based fingerprinting using FFmpeg
- 💾 Smart cache (skips unchanged files)
- 🗑 Interactive duplicate deletion
- 📁 Optional recursive scanning

---

### 🚀 Python (Advanced Version)
- ⚡ Much faster & smarter pipeline
- 🎯 Duration-based grouping (huge speed boost)
- ⚡ Quick binary signature filtering (reduces comparisons)
- 🎞 Frame fingerprinting (high accuracy)
- 💾 Persistent cache with auto-save
- 🧠 GPU acceleration support (CUDA / QSV / DXVA2)
- 🛑 Safe exit (Ctrl+C saves progress)
- 🔍 Adjustable similarity threshold

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

---

## 📦 Usage

### 🟢 PowerShell (Basic)

Run in current folder:
```powershell
& '.\Duplicate File Finder.ps1'
```

### 🚀 Python (Advanced)

Run in current folder with default settings:
```bash
python Duplicate_File_Finder.py
```

Run with custom path, recursion, and GPU acceleration:
```bash
python Duplicate_File_Finder.py --path "C:\path\to\videos" --recurse --gpu auto --threshold 75.0
```

Options:
- `--path PATH` : Folder to scan (default: current directory)
- `--recurse` : Scan subfolders recursively
- `--gpu {auto,cpu,cuda,qsv,dxva2}` : Hardware acceleration mode (default: auto)
- `--threshold THRESHOLD` : Similarity threshold percentage (default: 70.0)

---

## 📜 License

This project is licensed under the MIT License — see the LICENSE file for details.