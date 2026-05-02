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
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from send2trash import send2trash

# ─────────────────────────────────────────────
# 🎬 CONFIG
# ─────────────────────────────────────────────
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpeg", ".mpg", ".m4v", ".3gp", ".vob", ".ts", ".f4v"}
FRAME_RATE = "1/10"
DURATION_TOLERANCE = 5  # seconds

# ─────────────────────────────────────────────
# 🧠 FFMPEG + GPU
# ─────────────────────────────────────────────
def resolve_gpu(mode):
    if mode == "cpu":
        return []
    if mode in ("cuda", "qsv", "dxva2"):
        return ["-hwaccel", mode]
    if shutil.which("nvidia-smi"):
        print("⚡ GPU detected → CUDA")
        return ["-hwaccel", "cuda"]
    return []

# ─────────────────────────────────────────────
# 💾 CACHE
# ─────────────────────────────────────────────
cache = {}

def load_cache(cache_file):
    global cache
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            for e in data:
                cache[e["path"]] = {"mtime": e["mtime"], "hashes": e["hashes"]}
            print(f"💾 Cache loaded: {len(cache)} entries")
        except Exception:
            print("⚠ Cache corrupted, starting fresh")
            cache = {}

def save_cache(cache_file):
    data = [{"path": p, "mtime": v["mtime"], "hashes": v["hashes"]}
            for p, v in cache.items()]
    cache_file.write_text(json.dumps(data, indent=2))

# ─────────────────────────────────────────────
# 🗑 DELETE ENGINE
# ─────────────────────────────────────────────
def delete_files(paths, delete_mode):
    deleted = 0
    for p in paths:
        try:
            p_obj = Path(p)
            if not p_obj.exists():
                continue

            if delete_mode == "recycle":
                try:
                    send2trash(str(p_obj.resolve()))
                except Exception as e:
                    print(f"❌ Recycle bin failed for {p}: {e}")
                    continue
            else:
                p_obj.unlink()
            deleted += 1
            print(f"🗑 Deleted: {p}")
        except Exception as e:
            print(f"❌ Failed to delete {p}: {e}")
    print(f"\n✅ Total deleted: {deleted}/{len(paths)}")

# ─────────────────────────────────────────────
# 🛑 CTRL+C
# ─────────────────────────────────────────────
def handle_sigint(sig, frame, cache_file):
    print("\n⚠ Interrupted — saving cache...")
    save_cache(cache_file)
    sys.exit(0)

# ─────────────────────────────────────────────
# 🔍 FIND FILES
# ─────────────────────────────────────────────
def find_files(root, recurse, extensions=None):
    if recurse:
        files = [f for f in root.rglob("*") if f.is_file()]
    else:
        files = [f for f in root.iterdir() if f.is_file()]

    if extensions:
        files = [f for f in files if f.suffix.lower() in extensions]
    return files

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
    except Exception:
        return None

# ─────────────────────────────────────────────
# 🔍 EXACT MATCH ENGINE
# ─────────────────────────────────────────────
def exact_match(scan_path, recurse, extensions=None):
    files = find_files(scan_path, recurse, extensions)
    print(f"📦 Found {len(files)} file(s) for exact matching")

    if not files:
        return []

    print("\n⏱ Grouping by size...")
    size_groups = {}
    for f in files:
        try:
            size = f.stat().st_size
            if size not in size_groups:
                size_groups[size] = []
            size_groups[size].append(f)
        except Exception:
            pass

    candidates = [f for group in size_groups.values() if len(group) > 1 for f in group]
    print(f"🎯 After size filter: {len(candidates)} candidate(s)")

    if not candidates:
        return []

    print("\n⚡ Running quick signature filter...")
    quick_groups = {}
    for f in candidates:
        qh = quick_signature(f)
        if qh:
            key = (f.stat().st_size, qh[1])
            if key not in quick_groups:
                quick_groups[key] = []
            quick_groups[key].append(f)

    candidates = [f for group in quick_groups.values() if len(group) > 1 for f in group]
    print(f"🎯 After quick hash filter: {len(candidates)} candidate(s)")

    if not candidates:
        return []

    print("\n⚙ Computing full hashes for remaining candidates...")
    def full_hash(f_path):
        try:
            hasher = hashlib.sha256()
            with open(f_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096 * 1024), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None

    full_groups = {}
    for i, f in enumerate(candidates, 1):
        print(f"[{i}/{len(candidates)}] 🧮 {f.name}")
        fh = full_hash(f)
        if fh:
            if fh not in full_groups:
                full_groups[fh] = []
            full_groups[fh].append(f)

    matches = [group for group in full_groups.values() if len(group) > 1]
    return matches

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
    except Exception:
        return None

# ─────────────────────────────────────────────
# 🎞 FINGERPRINT
# ─────────────────────────────────────────────
def fingerprint(file_path, ffmpeg_bin, hw_args):
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
# 🖼 GUI RESULTS
# ─────────────────────────────────────────────
def show_results_gui(matches, delete_callback):
    """
    matches: List of groups, where each group is a list of Path objects or path strings
    delete_callback: function that accepts a list of path strings to delete
    """
    root = tk.Tk()
    root.title("Duplicate Results")
    root.geometry("800x600")

    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    # Treeview with checkboxes (using tags)
    columns = ("Path", "Size", "Group")
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")

    tree.heading("Path", text="Path")
    tree.heading("Size", text="Size")
    tree.heading("Group", text="Group")

    tree.column("Path", width=500)
    tree.column("Size", width=100)
    tree.column("Group", width=100)

    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscroll=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)

    # Populate
    row_to_path = {}
    for i, group in enumerate(matches, 1):
        for f in group:
            try:
                p = Path(f)
                size_mb = f"{p.stat().st_size / (1024*1024):.2f} MB"
            except:
                size_mb = "N/A"

            # Default to not checked (unchecked box character)
            item = tree.insert("", "end", values=(str(f), size_mb, f"Group {i}"), tags=("unchecked",))
            row_to_path[item] = str(f)

    # Toggle selection on click
    def toggle_check(event):
        item = tree.focus()
        if not item: return
        tags = tree.item(item, "tags")
        if "checked" in tags:
            tree.item(item, tags=("unchecked",))
            tree.item(item, text="[ ]")
        else:
            tree.item(item, tags=("checked",))
            tree.item(item, text="[X]")

    tree.bind("<Double-1>", toggle_check)
    tree.bind("<space>", toggle_check)

    btn_frame = ttk.Frame(root)
    btn_frame.pack(fill="x", padx=10, pady=10)

    def process_deletion():
        selected_paths = []
        for item in tree.get_children():
            if "checked" in tree.item(item, "tags"):
                selected_paths.append(row_to_path[item])

        if not selected_paths:
            messagebox.showinfo("Info", "No files selected for deletion.")
            return

        if messagebox.askyesno("Confirm", f"Are you sure you want to delete {len(selected_paths)} file(s)?"):
            delete_callback(selected_paths)
            root.destroy()

    ttk.Button(btn_frame, text="Delete Selected", command=process_deletion).pack(side="right")
    ttk.Label(btn_frame, text="Double-click or press Space to select/deselect.").pack(side="left")

    # Add pseudo-checkboxes to the first column (requires a trick or custom drawing in standard tkinter,
    # so we will just change the background color of checked items instead)
    tree.tag_configure("checked", background="lightpink")
    tree.tag_configure("unchecked", background="white")

    root.mainloop()

# ─────────────────────────────────────────────
# 🖼 GUI SETTINGS
# ─────────────────────────────────────────────
def gui_settings():
    root = tk.Tk()
    root.title("Duplicate File Finder")
    root.geometry("400x350")

    config = {
        "path": str(Path.cwd()),
        "recurse": False,
        "mode": "video",
        "file_types": "videos",
        "delete_mode": "recycle",
        "threshold": 70.0,
        "start": False
    }

    # Path
    path_frame = ttk.Frame(root)
    path_frame.pack(fill="x", padx=10, pady=10)
    ttk.Label(path_frame, text="Path:").pack(side="left")
    path_var = tk.StringVar(value=config["path"])
    ttk.Entry(path_frame, textvariable=path_var).pack(side="left", fill="x", expand=True, padx=5)
    def browse():
        p = filedialog.askdirectory()
        if p:
            path_var.set(p)
    ttk.Button(path_frame, text="Browse", command=browse).pack(side="left")

    # Options
    opts_frame = ttk.LabelFrame(root, text="Settings")
    opts_frame.pack(fill="x", padx=10, pady=5)

    recurse_var = tk.BooleanVar(value=config["recurse"])
    ttk.Checkbutton(opts_frame, text="Recursive Scan", variable=recurse_var).grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=5)

    ttk.Label(opts_frame, text="Mode:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    mode_var = tk.StringVar(value=config["mode"])
    ttk.Combobox(opts_frame, textvariable=mode_var, values=["video", "exact"], state="readonly").grid(row=1, column=1, sticky="w", padx=5, pady=5)

    ttk.Label(opts_frame, text="File Types:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    types_var = tk.StringVar(value=config["file_types"])
    ttk.Combobox(opts_frame, textvariable=types_var, values=["all", "videos", "images", "documents", "audio"], state="readonly").grid(row=2, column=1, sticky="w", padx=5, pady=5)

    ttk.Label(opts_frame, text="Delete:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    del_var = tk.StringVar(value=config["delete_mode"])
    ttk.Combobox(opts_frame, textvariable=del_var, values=["recycle", "permanent"], state="readonly").grid(row=3, column=1, sticky="w", padx=5, pady=5)

    def on_start():
        config["path"] = path_var.get()
        config["recurse"] = recurse_var.get()
        config["mode"] = mode_var.get()
        config["file_types"] = types_var.get()
        config["delete_mode"] = del_var.get()
        config["start"] = True
        root.destroy()

    ttk.Button(root, text="Start Scan", command=on_start).pack(pady=15)

    root.mainloop()
    return config

# ─────────────────────────────────────────────
# ⚙️ MAIN
# ─────────────────────────────────────────────
def main():
    # If no args are passed, use GUI
    if len(sys.argv) == 1:
        try:
            config = gui_settings()
            if not config["start"]:
                sys.exit(0)
            args = argparse.Namespace(**config)
            # Need to fill missing defaults
            args.gpu = "auto"
        except Exception as e:
            print(f"GUI failed to load: {e}")
            sys.exit(1)
    else:
        parser = argparse.ArgumentParser(description="🎥 Duplicate File Finder")
        parser.add_argument("--path", default=None, help="Path to scan")
        parser.add_argument("--recurse", action="store_true", help="Scan subdirectories recursively")
        parser.add_argument("--mode", choices=["video", "exact"], default="video", help="Scan mode: video (similar) or exact (identical)")
        parser.add_argument("--file-types", choices=["all", "videos", "images", "documents", "audio"], default="videos", help="File types to scan (only used in exact mode)")
        parser.add_argument("--delete-mode", choices=["permanent", "recycle"], default="recycle", help="Deletion method")
        parser.add_argument("--gpu", default="auto", choices=["auto","cpu","cuda","qsv","dxva2"], help="Hardware acceleration for video mode")
        parser.add_argument("--threshold", type=float, default=70.0, help="Similarity threshold for video mode")
        args = parser.parse_args()

    scan_path = Path(args.path if args.path else ".").resolve()
    cache_file = scan_path / "video_fingerprints.json"
    threshold = args.threshold

    print("═" * 60)
    print(f"🎥 DUPLICATE FINDER - {args.mode.upper()} MODE")
    print("═" * 60)
    print(f"📂 Path       : {scan_path}")
    print(f"🔁 Recursive  : {'Yes' if args.recurse else 'No'}")

    if args.mode == "video":
        print(f"🎯 Threshold  : {threshold}%")
        print(f"⏱ Tolerance  : ±{DURATION_TOLERANCE}s")
    else:
        print(f"📂 File Types : {args.file_types}")

    print(f"🗑 Delete Mode: {args.delete_mode}")

    # Exact mode doesn't need ffmpeg or cache
    if args.mode == "video":
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            print("❌ ffmpeg not found")
            sys.exit(1)

        hw_args = resolve_gpu(args.gpu)
        print(f"🚀 Acceleration: {' '.join(hw_args) if hw_args else 'CPU only'}")

        load_cache(cache_file)

    signal.signal(signal.SIGINT, lambda s, f: handle_sigint(s, f, cache_file))

    # EXACT MATCH ROUTE
    if args.mode == "exact":
        extensions = None
        if args.file_types == "videos":
            extensions = VIDEO_EXTENSIONS
        elif args.file_types == "images":
            extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
        elif args.file_types == "documents":
            extensions = {".pdf", ".doc", ".docx", ".txt", ".rtf", ".xls", ".xlsx", ".csv"}
        elif args.file_types == "audio":
            extensions = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}

        matches = exact_match(scan_path, args.recurse, extensions)

        if not matches:
            print("✅ No exact duplicates found.")
            sys.exit(0)

        print(f"\n✅ Done — {len(matches)} match group(s) found")

        # Output or GUI
        if len(sys.argv) == 1: # We were launched via GUI
            show_results_gui(matches, lambda paths: delete_files(paths, args.delete_mode))
        else:
            for i, group in enumerate(matches, 1):
                print("─" * 50)
                print(f"🔥 EXACT MATCH GROUP {i}")
                for f in group:
                    print(f"📁 {f}")
            input("\nPress Enter to exit...")
        sys.exit(0)

    # VIDEO MATCH ROUTE
    print("\n🔍 Scanning videos...")
    # Using find_files since find_videos was replaced
    videos = find_files(scan_path, args.recurse, VIDEO_EXTENSIONS)
    print(f"📦 Found {len(videos)} video(s)")

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
        h = fingerprint(v, ffmpeg_bin, hw_args)
        if h:
            fingerprints[path] = h
            cache[path] = {"mtime": mtime, "hashes": h}
            save_cache(cache_file)
        print()

    print("\n🔍 Comparing videos...\n")
    paths = list(fingerprints.keys())
    match_groups = []

    # Simple pairing for video matches to mimic groups
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            a, b = paths[i], paths[j]
            set_a = set(fingerprints[a])
            set_b = set(fingerprints[b])
            if not set_a or not set_b:
                continue
            smaller = min(len(set_a), len(set_b))
            if smaller == 0:
                continue
            needed = threshold / 100 * smaller
            common = 0
            for h in set_a:
                if h in set_b:
                    common += 1
                    if common >= needed:
                        break
            percent = (common / smaller) * 100
            if percent >= threshold:
                match_groups.append([Path(a), Path(b)])

    save_cache(cache_file)
    print("═" * 60)
    print(f"✅ Done — {len(match_groups)} match group(s) found")
    print("═" * 60)

    if len(sys.argv) == 1:
        show_results_gui(match_groups, lambda paths: delete_files(paths, args.delete_mode))
    else:
        for i, group in enumerate(match_groups, 1):
            print("─" * 50)
            print(f"🔥 MATCH GROUP {i}")
            for f in group:
                print(f"📁 {f}")
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
