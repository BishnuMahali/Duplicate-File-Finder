# MIT License
# Copyright (c) 2026 Bishnu Mahali
# See LICENSE file in the repository root for full license text.

"""
find_dupes.py — Duplicate video finder with duration grouping + fingerprinting + cache
"""

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

# ─────────────────────────────────────────────
# 🎬 CONFIG
# ─────────────────────────────────────────────
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"}
FRAME_RATE = "1/10"
DURATION_TOLERANCE = 5  # seconds

# ─────────────────────────────────────────────
# ⚙️ ARGUMENTS
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser(description="🎥 Duplicate video finder")
parser.add_argument("--path", default=".")
parser.add_argument("--recurse", action="store_true")
parser.add_argument("--gpu", default="auto", choices=["auto","cpu","cuda","qsv","dxva2"])
parser.add_argument("--threshold", type=float, default=70.0)
args = parser.parse_args()

scan_path = Path(args.path).resolve()
cache_file = scan_path / "video_fingerprints.json"
threshold = args.threshold

print("═" * 60)
print("🎥 VIDEO DUPLICATE FINDER")
print("═" * 60)
print(f"📂 Path       : {scan_path}")
print(f"🔁 Recursive  : {'Yes' if args.recurse else 'No'}")
print(f"🎯 Threshold  : {threshold}%")
print(f"⏱ Tolerance  : ±{DURATION_TOLERANCE}s")

# ─────────────────────────────────────────────
# 🧠 FFMPEG + GPU
# ─────────────────────────────────────────────
ffmpeg_bin = shutil.which("ffmpeg")
if not ffmpeg_bin:
    print("❌ ffmpeg not found")
    sys.exit(1)

def resolve_gpu(mode):
    if mode == "cpu":
        return []
    if mode in ("cuda", "qsv", "dxva2"):
        return ["-hwaccel", mode]
    if shutil.which("nvidia-smi"):
        print("⚡ GPU detected → CUDA")
        return ["-hwaccel", "cuda"]
    return []

hw_args = resolve_gpu(args.gpu)
print(f"🚀 Acceleration: {' '.join(hw_args) if hw_args else 'CPU only'}")

# ─────────────────────────────────────────────
# 💾 CACHE
# ─────────────────────────────────────────────
cache = {}

def load_cache():
    global cache
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            for e in data:
                cache[e["path"]] = {"mtime": e["mtime"], "hashes": e["hashes"]}
            print(f"💾 Cache loaded: {len(cache)} entries")
        except:
            print("⚠ Cache corrupted, starting fresh")
            cache = {}

def save_cache():
    data = [{"path": p, "mtime": v["mtime"], "hashes": v["hashes"]}
            for p, v in cache.items() if Path(p).exists()]
    cache_file.write_text(json.dumps(data, indent=2))

load_cache()

# ─────────────────────────────────────────────
# 🛑 CTRL+C
# ─────────────────────────────────────────────
def handle_sigint(sig, frame):
    print("\n⚠ Interrupted — saving cache...")
    save_cache()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sigint)

# ─────────────────────────────────────────────
# 🔍 FIND VIDEOS
# ─────────────────────────────────────────────
def find_videos(root, recurse):
    if recurse:
        return [f for f in root.rglob("*") if f.suffix.lower() in VIDEO_EXTENSIONS]
    return [f for f in root.iterdir() if f.suffix.lower() in VIDEO_EXTENSIONS]

print("\n🔍 Scanning videos...")
videos = find_videos(scan_path, args.recurse)
print(f"📦 Found {len(videos)} video(s)")

# ─────────────────────────────────────────────
# ⏱ GET DURATION
# ─────────────────────────────────────────────
def get_duration(path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1",
             str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return float(result.stdout.strip())
    except:
        return None

# ─────────────────────────────────────────────
# ⏱ GROUP BY DURATION
# ─────────────────────────────────────────────
print("\n⏱ Grouping by duration...")

groups = []

for v in videos:
    d = get_duration(v)
    if d is None:
        continue

    placed = False
    for g in groups:
        if abs(g["duration"] - d) <= DURATION_TOLERANCE:
            g["files"].append(v)
            placed = True
            break

    if not placed:
        groups.append({"duration": d, "files": [v]})

videos = [f for g in groups if len(g["files"]) > 1 for f in g["files"]]

print(f"🎯 After duration filter: {len(videos)} candidate(s)")

if not videos:
    print("❌ No possible duplicates after duration filtering")
    sys.exit()

# ─────────────────────────────────────────────
# ⚡ QUICK SIGNATURE FILTER
# ─────────────────────────────────────────────
def quick_signature(path, chunk_size=1024*1024):
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            start = f.read(chunk_size)
            if size > chunk_size:
                f.seek(-chunk_size, os.SEEK_END)
                end = f.read(chunk_size)
            else:
                end = start
        return (size, hashlib.md5(start + end).hexdigest())
    except:
        return None

print("\n⚡ Running quick signature filter...")

sig_map = {}
filtered = []

for v in videos:
    sig = quick_signature(v)
    if not sig:
        continue
    if sig in sig_map:
        filtered.append(v)
        filtered.append(sig_map[sig])
    else:
        sig_map[sig] = v

videos = list(set(filtered)) if filtered else videos
print(f"🎯 After quick filter: {len(videos)}")

# ─────────────────────────────────────────────
# 🎞 FINGERPRINT
# ─────────────────────────────────────────────
def fingerprint(file_path):
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        cmd = hw_args + [
            "-i", str(file_path),
            "-vf", f"fps={FRAME_RATE}",
            str(tmp_dir / "frame_%04d.jpg"),
            "-loglevel", "error"
        ]

        subprocess.run([ffmpeg_bin] + cmd)

        hashes = []
        for f in sorted(tmp_dir.glob("*.jpg")):
            hashes.append(hashlib.md5(f.read_bytes()).hexdigest())
        return hashes

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

# ─────────────────────────────────────────────
# ⚙ PROCESS
# ─────────────────────────────────────────────
print("\n⚙ Processing videos...\n")

fingerprints = {}

for i, v in enumerate(videos, 1):
    path = str(v)
    mtime = str(v.stat().st_mtime)

    print(f"[{i}/{len(videos)}] 🎬 {v.name}")

    if path in cache and cache[path]["mtime"] == mtime:
        fingerprints[path] = cache[path]["hashes"]
        print("   ✔ Cached\n")
        continue

    print("   ⚙ Extracting fingerprint...")
    h = fingerprint(v)

    if h:
        fingerprints[path] = h
        cache[path] = {"mtime": mtime, "hashes": h}
        save_cache()
    print()

# ─────────────────────────────────────────────
# 🔍 COMPARE
# ─────────────────────────────────────────────
print("\n🔍 Comparing videos...\n")

paths = list(fingerprints.keys())
matches = 0

for i in range(len(paths)):
    for j in range(i + 1, len(paths)):
        a, b = paths[i], paths[j]

        set_a = set(fingerprints[a])
        set_b = set(fingerprints[b])

        if not set_a or not set_b:
            continue

        smaller = min(len(set_a), len(set_b))
        needed = threshold / 100 * smaller

        common = 0
        for h in set_a:
            if h in set_b:
                common += 1
                if common >= needed:
                    break

        percent = (common / smaller) * 100

        if percent >= threshold:
            matches += 1
            print("─" * 50)
            print(f"🔥 MATCH — {percent:.1f}%")
            print(f"📁 {a}")
            print(f"📁 {b}\n")

# ─────────────────────────────────────────────
save_cache()

print("═" * 60)
print(f"✅ Done — {matches} match(es) found")
print("═" * 60)

input("Press Enter to exit...")