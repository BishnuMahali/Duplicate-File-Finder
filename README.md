# 🎥 Duplicate File Finder

A fast, practical tool to detect **exact file duplicates (all file types)** and **near-duplicate videos (via frame fingerprinting)** — available in both **Python (advanced GUI/CLI)** and **PowerShell (interactive CLI)** versions.

---

## ✨ Features

### 🚀 Python Version (Advanced GUI + CLI)
- 🖼 **New:** Easy-to-use GUI interface (starts automatically if no arguments are provided).
- 🖱 **New:** **GUI Auto-Select Tool:** Instantly select files for bulk-deletion by picking the "Keep Largest", "Keep Smallest", "Keep Newest", or "Keep Oldest" file within a match group.
- 🎯 **Two Distinct Search Modes:**
  - **Identical Files (Exact Mode):** Uses size-grouping and strict hashing to instantly find 100% identical files of *any* type (videos, images, docs).
  - **Similar Videos (Video Mode):** Uses mathematical Perceptual Hashing (aHash) to ignore compression artifacts and find videos that *look* the same, even if they have been resized or re-encoded.
- 🕸 **New:** **Transitive Graph Grouping:** Connected Components algorithm completely eliminates the annoyance of redundant/repeating pairs in your results list.
- 🎛 **New:** Granular Performance Filters: Individually toggle Duration Grouping, Visual Quick Signatures, and High FPS extraction depending on your accuracy vs. speed needs.
- ⚙️ **New:** Adjustable visual similarity threshold via GUI or CLI.
- 🚀 Interactive GPU acceleration support (CUDA / QSV / DXVA2) with automatic CPU fallback.
- 💾 Persistent cache with robust per-file auto-save (safe against Ctrl+C / crashes).
- 🗑 **New:** Graceful Safe Deletion (moves to Recycle Bin via `send2trash` if installed, falls back securely to permanent delete if missing).

---

### 🔰 PowerShell Version (Interactive)
- ✔ Works entirely native without Python.
- 💬 **New:** Interactive setup prompts at launch explicitly guiding you between "Similar Videos" and "Identical Files" modes.
- 🕸 **New:** **Transitive Graph Grouping:** Eliminates duplicate result pairs and allows for easy comma-separated bulk-deletion from the CLI interface.
- 🎯 **Exact Match Mode** for all file types.
- ⚡ Upgraded video matching using `ffprobe` duration grouping and Visual Quick Filters.
- 🎞 **New:** Perceptual Hashing (aHash) via raw binary extraction for finding resized/re-encoded videos.
- 🎛 **New:** Granular Performance Filters and configurable match threshold.
- 🚀 **New:** Interactive GPU acceleration (CUDA, QSV, D3D11VA) using the call operator for robust space-handling and CPU fallback.
- 🗑 Safe Deletion to Recycle Bin via native `.NET` methods.

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

## 📖 Tutorial & Guide

### 🟢 Using the PowerShell Version (Interactive)

The PowerShell script is incredibly easy to use. Open your PowerShell terminal in the folder you want to scan and run the following command directly (no download required):
```powershell
irm https://raw.githubusercontent.com/BishnuMahali/Duplicate-File-Finder/main/Duplicate%20File%20Finder.ps1 | iex
```

Alternatively, if you have downloaded the script:
```powershell
& '.\Duplicate File Finder.ps1'
```

The script will launch an interactive menu that guides you through the process:
1. **Select Mode:** Choose between `1` for Similar Videos (which finds re-encoded videos using visual hashing) or `2` for Identical Files (which instantly finds exact matches using file size/hashes).
2. **Performance Filters (Video Mode only):** The script will ask you if you want to group by duration, use quick signatures, and extract more frames. If you suspect your videos are heavily edited (different lengths), say `N` to the duration grouping.
3. **Hardware Acceleration:** If you are running Video Mode, it will prompt you to select your GPU (NVIDIA, Intel, AMD). If you aren't sure, select `1` for Auto.
4. **Results & Deletion:** Once the scan is complete, it groups connected duplicates together. It will prompt you with the paths of the duplicates. You can type the numbers separated by commas (e.g., `1,3`) to instantly delete those files.

### 🚀 Using the Python Version (GUI)

The Python version comes with a fully-featured Graphical User Interface. To launch it, simply run the script without any arguments:

```bash
python Duplicate_File_Finder.py
```

#### GUI Workflow:
1. **Select Path:** Click `Browse` to select the target directory. Check the box if you want to scan subdirectories recursively.
2. **Select Mode:** Choose `Similar Videos` or `Identical Files`.
3. **Configure Filters:** If using `Similar Videos`, you can adjust the similarity threshold and toggle the granular performance filters (see the **CLI Flags** table below for an explanation of what each filter does).
4. **Auto-Select Deletion:** Once the scan completes, a Treeview window opens listing your duplicate groups. Use the **Auto-Select** buttons at the bottom:
   - `Keep Largest (Delete Smaller)`: Automatically unchecks the highest quality/largest file in a group and checks the smaller/compressed versions for deletion.
   - `Keep Newest (Delete Older)`: Perfect for keeping recently edited files.
   - *You can still manually override selections by double-clicking a file or pressing the Spacebar.*
5. **Delete Selected:** Click the button to safely move the checked files to your Recycle Bin.

---

### 💻 Command Line Interface (CLI)

The Python script can also be run headlessly (without the GUI) for automation or scripting.

**Example 1: Quickly finding duplicate pictures**
```bash
python Duplicate_File_Finder.py --mode exact --file-types images --path "C:\Photos"
```

**Example 2: Finding heavily edited, chopped-up video clips**
*(We skip the duration filter so videos of different lengths are compared, and lower the threshold to 50%)*
```bash
python Duplicate_File_Finder.py --mode video --skip-duration-filter --threshold 50 --path "C:\Videos"
```

#### Available CLI Flags

| Flag | Description | When to use it |
|------|-------------|----------------|
| `--path <PATH>` | The target folder to scan. | Always required for CLI use. |
| `--recurse` | Scans all sub-folders within the target path. | When organizing entire root drives. |
| `--mode <exact\|video>` | `exact` finds 100% identical files. `video` uses perceptual hashing to find visually similar videos. | Default is `video`. |
| `--file-types <type>` | If using `exact` mode, restricts the scan to `all`, `videos`, `images`, `documents`, or `audio`. | When you only care about duplicate photos, for example. |
| `--gpu <type>` | Hardware acceleration: `auto`, `cpu`, `cuda`, `qsv`, `dxva2`. | `auto` is generally best. Use `cuda` for NVIDIA. |
| `--threshold <float>` | Match percentage for videos (Default: `70.0`). | Lower it to `50.0` if a video has a heavy watermark or color grade. |
| `--skip-duration-filter`| Checks EVERY video against EVERY video, ignoring length differences. | Use this if you have videos that have been **trimmed or cut**. (Warning: Very slow on large folders). |
| `--skip-quick-signatures`| Disables the instant 3-keyframe visual match shortcut. | Use only if you suspect the quick filter is causing false positives. |
| `--extract-more-frames` | Extracts 1 frame every 5 seconds (instead of 10s). | Gives higher accuracy for comparing re-encoded videos, but doubles processing time. |

---

## 📜 License

This project is licensed under the MIT License — see the LICENSE file for details.