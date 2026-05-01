# 🧩 Duplicate File Finder (PowerShell)

A PowerShell-based utility to detect **duplicate or similar files**, starting with video comparison using FFmpeg-based fingerprinting.

> ⚠️ Currently supports **video files only** (MP4, MKV, AVI, MOV, WMV).  
Future versions will expand to other file types.

---

## 🚀 Features

- 🔍 Detects similar videos (not just exact duplicates)
- ⚡ Frame-based fingerprinting using FFmpeg
- 🧠 Smart caching (avoids reprocessing unchanged files)
- 🗑 Interactive deletion of detected duplicates
- 📁 Optional recursive scanning

---

## ⚙️ Requirements

- PowerShell 5.1+
- FFmpeg installed and available in PATH

Download FFmpeg: https://ffmpeg.org/download.html

---

## 📦 Usage

### Run in current folder
```powershell
.\DuplicateFileFinder.ps1