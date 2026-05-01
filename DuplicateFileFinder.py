"""
find_dupes.py — Duplicate video finder with frame fingerprinting + cache

Usage:
    python find_dupes.py [--path DIR] [--recurse] [--gpu auto|cpu|cuda|qsv|dxva2] [--threshold 70]

Requirements:
    - Python 3.7+  (built-in on most systems; get it from python.org)
    - ffmpeg in PATH  (get it from ffmpeg.org)

Features:
    - Frame-based fingerprinting (MD5 of sampled frames)
    - JSON cache — stop and resume any time, only new files are processed
    - GPU/HW acceleration support (cuda, qsv, dxva2, or auto-detect)
    - Adjustable similarity threshold
    - Shows file sizes when a match is found
    - Safe Ctrl+C — always saves cache before exiting
"""

import argparse
import hashlib
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"}
FRAME_RATE       = "1/10"   # one frame every 10 seconds

# ─────────────────────────────────────────────
# ARGS
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Find duplicate videos via frame fingerprinting")
parser.add_argument("--path",      default=".",   help="Folder to scan (default: current dir)")
parser.add_argument("--recurse",   action="store_true", help="Scan subfolders recursively")
parser.add_argument("--gpu",       default="auto", choices=["auto","cpu","cuda","qsv","dxva2"],
                    help="Hardware acceleration (default: auto)")
parser.add_argument("--threshold", type=float, default=70.0,
                    help="Similarity %% to flag as duplicate (default: 70)")
args = parser.parse_args()

scan_path  = Path(args.path).resolve()
cache_file = scan_path / "video_fingerprints.json"
threshold  = args.threshold

# ─────────────────────────────────────────────
# CHECK FFMPEG
# ─────────────────────────────────────────────
ffmpeg_bin = shutil.which("ffmpeg")
if not ffmpeg_bin:
    print("❌  ffmpeg not found in PATH. Get it from https://ffmpeg.org")
    sys.exit(1)
print(f"✔  ffmpeg: {ffmpeg_bin}")

# ─────────────────────────────────────────────
# GPU / HW ACCEL
# ─────────────────────────────────────────────
def resolve_gpu(mode: str) -> list:
    if mode == "cpu":
        return []
    if mode in ("cuda", "qsv", "dxva2"):
        return ["-hwaccel", mode]
    # auto
    if shutil.which("nvidia-smi"):
        print("  Auto-detected NVIDIA GPU → using cuda")
        return ["-hwaccel", "cuda"]
    return []

hw_args = resolve_gpu(args.gpu)
print(f"  HW accel: {' '.join(hw_args) if hw_args else 'none (cpu)'}")

# ─────────────────────────────────────────────
# CACHE  (plain dict: path → {mtime, hashes})
# ─────────────────────────────────────────────
cache: dict = {}

def load_cache():
    global cache
    if not cache_file.exists():
        return
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        # data is a list of {path, mtime, hashes}
        for entry in data:
            p = entry.get("path")
            if p:
                cache[p] = {
                    "mtime":  entry.get("mtime"),
                    "hashes": list(entry.get("hashes", [])),
                }
        print(f"✔  Cache loaded — {len(cache)} entries")
    except Exception as e:
        print(f"⚠  Cache unreadable ({e}), starting fresh")
        cache = {}

def save_cache():
    try:
        alive = [
            {"path": p, "mtime": v["mtime"], "hashes": v["hashes"]}
            for p, v in cache.items()
            if Path(p).exists()
        ]
        cache_file.write_text(
            json.dumps(alive, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"💾  Cache saved — {len(alive)} entries")
    except Exception as e:
        print(f"⚠  Failed to save cache: {e}")

load_cache()

# ─────────────────────────────────────────────
# CTRL+C  — always save before exit
# ─────────────────────────────────────────────
_stopping = False

def handle_sigint(sig, frame):
    global _stopping
    if _stopping:
        sys.exit(1)          # second Ctrl+C = hard exit
    _stopping = True
    print("\n⚠  Ctrl+C — saving cache and stopping cleanly...")
    save_cache()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sigint)

# ─────────────────────────────────────────────
# FIND VIDEOS
# ─────────────────────────────────────────────
def find_videos(root: Path, recurse: bool) -> list:
    if recurse:
        return [
            f for f in root.rglob("*")
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
        ]
    return [
        f for f in root.iterdir()
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    ]

videos = find_videos(scan_path, args.recurse)
print(f"\nFound {len(videos)} video(s)")

if len(videos) < 2:
    print("Need at least 2 videos to compare.")
    input("Press Enter to exit...")
    sys.exit(0)

# ─────────────────────────────────────────────
# FINGERPRINT  — extract frames, hash each one
# ─────────────────────────────────────────────
def fingerprint(file_path: Path) -> list:
    tmp_dir = Path(tempfile.mkdtemp(prefix="vfp_"))
    try:
        cmd = (
            hw_args
            + ["-i", str(file_path)]
            + ["-vf", f"fps={FRAME_RATE}"]
            + [str(tmp_dir / "frame_%04d.jpg")]
            + ["-hide_banner", "-loglevel", "error"]
        )
        result = subprocess.run(
            [ffmpeg_bin] + cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            err = result.stderr.decode(errors="replace").strip()
            print(f"   ❌ ffmpeg error: {err[:200]}")
            return []

        frames = sorted(tmp_dir.glob("*.jpg"))
        print(f"   → {len(frames)} frame(s) extracted", end="", flush=True)

        if not frames:
            print()
            return []

        hashes = []
        for f in frames:
            try:
                md5 = hashlib.md5(f.read_bytes()).hexdigest()
                hashes.append(md5)
            except Exception:
                pass

        print(f", {len(hashes)} hashed")
        return hashes

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

# ─────────────────────────────────────────────
# PROCESS FILES
# ─────────────────────────────────────────────
fingerprints: dict = {}   # path_str → list[str]

try:
    for i, v in enumerate(videos, 1):
        if _stopping:
            break

        path_str = str(v)
        try:
            mtime = str(v.stat().st_mtime)
        except Exception:
            continue

        cached = cache.get(path_str)
        if cached and cached.get("mtime") == mtime and cached.get("hashes"):
            print(f"[{i}/{len(videos)}] ✔ Cached:     {v.name}")
            fingerprints[path_str] = cached["hashes"]
            continue

        print(f"[{i}/{len(videos)}] ⚙ Processing: {v.name}")
        hashes = fingerprint(v)

        if hashes:
            fingerprints[path_str] = hashes
            cache[path_str] = {"mtime": mtime, "hashes": hashes}
            save_cache()
        else:
            print(f"   ⚠ Skipped — no frames extracted")

finally:
    save_cache()

# ─────────────────────────────────────────────
# COMPARE
# ─────────────────────────────────────────────
fp_paths   = list(fingerprints.keys())
total_pairs = (len(fp_paths) * (len(fp_paths) - 1)) // 2
matches_found = 0

print(f"\nComparing {len(fp_paths)} video(s) — {total_pairs} pair(s)...\n")

for i in range(len(fp_paths)):
    if _stopping:
        break
    for j in range(i + 1, len(fp_paths)):
        if _stopping:
            break

        a = fp_paths[i]
        b = fp_paths[j]

        set_a = set(fingerprints[a])
        set_b = set(fingerprints[b])

        if not set_a or not set_b:
            continue

        common  = len(set_a & set_b)
        smaller = min(len(set_a), len(set_b))
        percent = round((common / smaller) * 100, 1)

        if percent >= threshold:
            matches_found += 1

            size_a = size_b = "?"
            try: size_a = f"{Path(a).stat().st_size / (1024*1024):.1f} MB"
            except Exception: pass
            try: size_b = f"{Path(b).stat().st_size / (1024*1024):.1f} MB"
            except Exception: pass

            print("═" * 50)
            print(f"  DUPLICATE — {percent}% match")
            print(f"  1: {a}  ({size_a})")
            print(f"  2: {b}  ({size_b})")

            choice = input("  Delete which? [1 / 2 / skip]: ").strip()

            if choice == "1" and Path(a).exists():
                Path(a).unlink()
                cache.pop(a, None)
                print(f"  🗑  Deleted: {a}")
            elif choice == "2" and Path(b).exists():
                Path(b).unlink()
                cache.pop(b, None)
                print(f"  🗑  Deleted: {b}")
            else:
                print("  Skipped.")
            print()

save_cache()

print("═" * 50)
print(f"Done. {matches_found} duplicate pair(s) found.")
input("Press Enter to exit...")
