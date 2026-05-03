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

try:
    from send2trash import send2trash
    HAS_SEND2TRASH = True
except ImportError:
    HAS_SEND2TRASH = False

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
                if HAS_SEND2TRASH:
                    try:
                        send2trash(str(p_obj.resolve()))
                    except Exception as e:
                        print(f"❌ Recycle bin failed for {p}: {e}")
                        continue
                else:
                    print(f"⚠ send2trash module missing, falling back to permanent delete for {p}")
                    p_obj.unlink()
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

def get_visual_quick_signature(hashes):
    if not hashes:
        return None
    if len(hashes) < 3:
        return tuple(hashes)
    mid = len(hashes) // 2
    return (hashes[0], hashes[mid], hashes[-1])

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
def fingerprint(file_path, ffmpeg_bin, hw_args, extreme=False):
    fps = "1/5" if extreme else "1/10"

    try:
        def run_ffmpeg(args):
            cmd = args + [
                "-i", str(file_path),
                "-vf", f"fps={fps},scale=8:8,format=gray",
                "-f", "rawvideo",
                "pipe:1",
                "-loglevel", "error"
            ]
            result = subprocess.run([ffmpeg_bin] + cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.stdout

        try:
            raw_data = run_ffmpeg(hw_args)
        except subprocess.CalledProcessError as e:
            if hw_args:
                print(f"⚠ GPU acceleration failed for {file_path.name}, falling back to CPU...")
                raw_data = run_ffmpeg([])
            else:
                raise

        hashes = []
        # Each 8x8 frame is exactly 64 bytes
        for i in range(0, len(raw_data), 64):
            frame_data = raw_data[i:i+64]
            if len(frame_data) == 64:
                mean = sum(frame_data) / 64
                bits = "".join("1" if b >= mean else "0" for b in frame_data)
                hashes.append(int(bits, 2))

        return hashes

    except Exception as e:
        print(f"❌ Failed to extract frames from {file_path.name}: {e}")
        return []

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
    group_to_items = {}

    for i, group in enumerate(matches, 1):
        group_items = []
        for f in group:
            try:
                p = Path(f)
                size_mb = f"{p.stat().st_size / (1024*1024):.2f} MB"
            except:
                size_mb = "N/A"

            # Default to not checked (unchecked box character)
            item = tree.insert("", "end", values=(str(f), size_mb, f"Group {i}"), tags=("unchecked",))
            row_to_path[item] = str(f)
            group_items.append(item)

        group_to_items[i] = group_items

    # Toggle selection on click
    def toggle_check(event=None, item=None):
        if not item:
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

    # Auto-Select Features
    def auto_select(strategy):
        # First, clear all selections
        for item in tree.get_children():
            tree.item(item, tags=("unchecked",))
            tree.item(item, text="[ ]")

        for g_id, items in group_to_items.items():
            if not items: continue

            # Extract data for sorting
            data = []
            for item in items:
                p = Path(row_to_path[item])
                try:
                    stat = p.stat()
                    data.append({"item": item, "size": stat.st_size, "mtime": stat.st_mtime})
                except:
                    data.append({"item": item, "size": 0, "mtime": 0})

            # Sort to find the "best" one to keep
            if strategy == "largest":
                data.sort(key=lambda x: x["size"], reverse=True)
            elif strategy == "smallest":
                data.sort(key=lambda x: x["size"])
            elif strategy == "newest":
                data.sort(key=lambda x: x["mtime"], reverse=True)
            elif strategy == "oldest":
                data.sort(key=lambda x: x["mtime"])

            # Keep the first one, mark the rest for deletion
            for d in data[1:]:
                tree.item(d["item"], tags=("checked",))
                tree.item(d["item"], text="[X]")

    auto_frame = ttk.LabelFrame(root, text="Auto-Select for Deletion")
    auto_frame.pack(fill="x", padx=10, pady=5)

    ttk.Button(auto_frame, text="Keep Largest (Delete Smaller)", command=lambda: auto_select("largest")).pack(side="left", padx=5, pady=5)
    ttk.Button(auto_frame, text="Keep Smallest (Delete Larger)", command=lambda: auto_select("smallest")).pack(side="left", padx=5, pady=5)
    ttk.Button(auto_frame, text="Keep Newest (Delete Older)", command=lambda: auto_select("newest")).pack(side="left", padx=5, pady=5)
    ttk.Button(auto_frame, text="Keep Oldest (Delete Newer)", command=lambda: auto_select("oldest")).pack(side="left", padx=5, pady=5)

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
        "skip_duration_filter": False,
        "skip_quick_signatures": False,
        "extract_more_frames": False,
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
    mode_cb = ttk.Combobox(opts_frame, textvariable=mode_var, values=["video", "exact"], state="readonly", width=10)
    mode_cb.grid(row=1, column=1, sticky="w", padx=5, pady=5)

    lbl_ftypes = ttk.Label(opts_frame, text="Exact Types:")
    lbl_ftypes.grid(row=1, column=2, sticky="w", padx=5, pady=5)
    types_var = tk.StringVar(value=config["file_types"])
    cb_ftypes = ttk.Combobox(opts_frame, textvariable=types_var, values=["all", "videos", "images", "documents", "audio"], state="readonly", width=10)
    cb_ftypes.grid(row=1, column=3, sticky="w", padx=5, pady=5)

    ttk.Label(opts_frame, text="Delete:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    del_var = tk.StringVar(value=config["delete_mode"])
    ttk.Combobox(opts_frame, textvariable=del_var, values=["recycle", "permanent"], state="readonly", width=10).grid(row=2, column=1, sticky="w", padx=5, pady=5)

    ttk.Label(opts_frame, text="Threshold (%):").grid(row=2, column=2, sticky="w", padx=5, pady=5)
    thresh_var = tk.StringVar(value=str(config["threshold"]))
    ttk.Entry(opts_frame, textvariable=thresh_var, width=10).grid(row=2, column=3, sticky="w", padx=5, pady=5)

    skip_dur_var = tk.BooleanVar(value=config["skip_duration_filter"])
    ttk.Checkbutton(opts_frame, text="Skip Duration Filter (Finds edited lengths)", variable=skip_dur_var).grid(row=3, column=0, columnspan=4, sticky="w", padx=5, pady=2)

    skip_sig_var = tk.BooleanVar(value=config["skip_quick_signatures"])
    ttk.Checkbutton(opts_frame, text="Skip Quick Visual Sigs", variable=skip_sig_var).grid(row=4, column=0, columnspan=4, sticky="w", padx=5, pady=2)

    ext_frames_var = tk.BooleanVar(value=config["extract_more_frames"])
    ttk.Checkbutton(opts_frame, text="Extract More Frames (1fps/5s for higher accuracy)", variable=ext_frames_var).grid(row=5, column=0, columnspan=4, sticky="w", padx=5, pady=2)

    def update_ui(*args):
        if mode_var.get() == "video":
            cb_ftypes.grid_remove()
            lbl_ftypes.grid_remove()
        else:
            cb_ftypes.grid()
            lbl_ftypes.grid()

    mode_var.trace_add("write", update_ui)
    update_ui()

    def on_start():
        config["path"] = path_var.get()
        config["recurse"] = recurse_var.get()
        config["mode"] = mode_var.get()
        config["file_types"] = types_var.get()
        config["delete_mode"] = del_var.get()
        config["skip_duration_filter"] = skip_dur_var.get()
        config["skip_quick_signatures"] = skip_sig_var.get()
        config["extract_more_frames"] = ext_frames_var.get()
        try:
            config["threshold"] = float(thresh_var.get())
        except ValueError:
            pass
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
        parser.add_argument("--gpu", default="prompt", choices=["prompt","auto","cpu","cuda","qsv","dxva2"], help="Hardware acceleration for video mode")
        parser.add_argument("--threshold", type=float, default=70.0, help="Similarity threshold for video mode")
        parser.add_argument("--skip-duration-filter", action="store_true", help="Skips duration filtering to find edited lengths")
        parser.add_argument("--skip-quick-signatures", action="store_true", help="Skips the fast visual quick signature match")
        parser.add_argument("--extract-more-frames", action="store_true", help="Extracts 1fps/5s instead of 10s for higher accuracy on re-encodes")
        args = parser.parse_args()

    # Prompt for GPU mode if in video mode and we want to prompt
    # Note: If running via GUI, args.gpu is set to "auto" earlier, bypassing this prompt unless explicitly set to "prompt"
    if args.mode == "video" and getattr(args, "gpu", "auto") == "prompt":
        print("\nSelect hardware acceleration mode:")
        print("1) Auto (Detect automatically, fallback to CPU)")
        print("2) NVIDIA (CUDA)")
        print("3) Intel (QSV)")
        print("4) AMD/Windows (D3D11VA)")
        print("5) CPU Only (None)")
        choice = input("Enter choice [1-5] (default 1): ").strip()

        mapping = {"1": "auto", "2": "cuda", "3": "qsv", "4": "dxva2", "5": "cpu", "": "auto"}
        args.gpu = mapping.get(choice, "auto")

    scan_path = Path(args.path if args.path else ".").resolve()
    cache_file = scan_path / "video_fingerprints.json"
    threshold = args.threshold

    print("═" * 60)
    print(f"🎥 DUPLICATE FINDER - {args.mode.upper()} MODE")
    print("═" * 60)
    print(f"📂 Path       : {scan_path}")
    print(f"🔁 Recursive  : {'Yes' if args.recurse else 'No'}")

    if args.mode == "video":
        print(f"🎯 Threshold    : {threshold}%")
        if getattr(args, "skip_duration_filter", False):
            print("⏱ Duration Grp : SKIPPED")
        else:
            print(f"⏱ Duration Grp : Active (±{DURATION_TOLERANCE}s)")
        print(f"⚡ Quick Sigs   : {'SKIPPED' if getattr(args, 'skip_quick_signatures', False) else 'Active'}")
        print(f"🎞 Frame Rate   : {'1/5s' if getattr(args, 'extract_more_frames', False) else '1/10s'}")
    else:
        print(f"📂 File Types : {args.file_types}")

    print(f"🗑 Delete Mode: {args.delete_mode}")

    # Exact mode doesn't need ffmpeg or cache
    if args.mode == "video":
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            print("❌ ffmpeg not found")
            sys.exit(1)

        hw_args = resolve_gpu("auto" if getattr(args, "gpu", "auto") == "prompt" else args.gpu)
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

    if getattr(args, "skip_duration_filter", False):
        print("\n⏭ Skipping duration filtering (Checking all videos against each other)...")
    else:
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
        print("❌ No possible duplicates to process.")
        sys.exit()

    print("\n⚙ Processing videos...\n")
    fingerprints = {}
    try:
        for i, v in enumerate(videos, 1):
            path = str(v)
            mtime = str(v.stat().st_mtime)
            print(f"[{i}/{len(videos)}] 🎬 {v.name}")
            if path in cache and cache[path]["mtime"] == mtime:
                fingerprints[path] = cache[path]["hashes"]
                print("   ✔ Cached\n")
                continue
            print("   ⚙ Extracting fingerprint...")
            h = fingerprint(v, ffmpeg_bin, hw_args, getattr(args, "extract_more_frames", False))
            if h:
                fingerprints[path] = h
                cache[path] = {"mtime": mtime, "hashes": h}
                save_cache(cache_file)
            print()
    except KeyboardInterrupt:
        print("\n⚠ Interrupted — saving cache...")
        save_cache(cache_file)
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
        save_cache(cache_file)
        raise

    print("\n🔍 Comparing videos...\n")
    paths = list(fingerprints.keys())

    edges = []

    def hamming_distance(h1, h2):
        x = h1 ^ h2
        return bin(x).count('1')

    # Visual Quick Filter Pre-Computation
    quick_sigs = {}
    for p in paths:
        quick_sigs[p] = get_visual_quick_signature(fingerprints[p])

    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            a, b = paths[i], paths[j]
            matched = False

            # 1. Visual Quick Filter Check
            if not getattr(args, "skip_quick_signatures", False):
                qa = quick_sigs[a]
                qb = quick_sigs[b]
                if qa and qb:
                    if qa == qb:
                        matched = True

            # 2. Full Perceptual Hash Comparison
            if not matched:
                list_a = fingerprints[a]
                list_b = fingerprints[b]
                if list_a and list_b:
                    smaller = min(len(list_a), len(list_b))
                    if smaller > 0:
                        match_count = 0
                        for ha in list_a:
                            for hb in list_b:
                                if hamming_distance(ha, hb) <= 10:
                                    match_count += 1
                                    break

                        percent = (match_count / smaller) * 100
                        if percent >= threshold:
                            matched = True

            if matched:
                edges.append((a, b))

    save_cache(cache_file)

    # 3. Build Connected Components (Group transitive matches)
    from collections import defaultdict
    adj = defaultdict(list)
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)

    visited = set()
    match_groups = []
    for node in adj:
        if node not in visited:
            group = []
            stack = [node]
            visited.add(node)
            while stack:
                curr = stack.pop()
                group.append(Path(curr))
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)
            if len(group) > 1:
                match_groups.append(group)

    print("═" * 60)
    print(f"✅ Done — {len(match_groups)} connected match group(s) found")
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
