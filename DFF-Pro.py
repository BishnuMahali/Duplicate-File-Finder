# DFF-Pro.py — Ultimate Duplicate File Finder PRO (CustomTkinter Edition)
# MIT License | Copyright (c) 2026 Bishnu Mahali
# See LICENSE file in the repository root for full license text.

import os
import sys
import time
import json
import shutil
import threading
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, ttk, END, messagebox

import customtkinter as ctk
import send2trash

# Ensure the ENGINE folder is on the path so we can load the core engine module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ENGINE"))
import Duplicate_File_Finder as ProBackend

# --- Restored CustomTkinter Theme Mappings (matching DFF Lite) ---
BG_MAIN = ("gray95", "gray10")
BG_PANEL = ("gray90", "gray15")
BG_CARD = ("gray85", "gray20")
TEXT_MAIN = ("gray10", "gray90")
TEXT_SUB = "gray"
ACCENT_BLUE_TEXT = ("#1f538d", "white")  # High-contrast blue in light mode, clean white in dark mode!
ACCENT_BLUE_BTN = ("#3a7ebf", "#1f538d")   # Beautiful blue button background in both modes
ACCENT_CYAN = ("#4ba3e3", "#2e7bbf")      # Hover blue accent
ACCENT_GREEN = ("#2da44e", "#2da44e")     # Success/Start green
ACCENT_RED = ("#cf222e", "#cf222e")       # Stop/delete red
ACCENT_YELLOW = ("#e0af68", "#e0af68")    # Soft gold/warning/stopping color
def hamming_distance(h1, h2):
    x = h1 ^ h2
    return bin(x).count('1')

class MatchResult:
    def __init__(self, path_a, path_b, file_a_size, file_b_size, confidence_score):
        self.path_a = path_a
        self.path_b = path_b
        self.file_a_size = file_a_size
        self.file_b_size = file_b_size
        self.confidence_score = confidence_score

def bootstrap():
    if hasattr(sys, 'real_prefix') or (sys.base_prefix != sys.prefix):
        return
    venv_dir = Path(".venv")
    python_exe = venv_dir / "Scripts" / "python.exe" if os.name == 'nt' else venv_dir / "bin" / "python"
    if python_exe.exists():
        os.execv(str(python_exe), [str(python_exe)] + sys.argv)

bootstrap()

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue") # Professional blue theme

def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

class DFFProEngine:
    def __init__(self, app_callbacks):
        self.callbacks = app_callbacks
        self.stop_requested = False
        self.ffmpeg_bin = shutil.which("ffmpeg")
        self.fingerprints_cache = {}
        self.exact_matches = []

    def log(self, message):
        self.callbacks.get("log", print)(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def request_stop(self):
        self.stop_requested = True
        self.log("[SYSTEM] STOP requested. Terminating engine execution...")

    def file_progress(self, filepath, status):
        cb = self.callbacks.get("file_progress")
        if cb:
            cb(filepath, status)

    def run_scan(self, folders, use_cache=True, recursive=True, mode="video", file_types="all", gpu_mode="auto", extreme=False):
        self.stop_requested = False
        
        if mode == "exact":
            self.log("Initializing Pro Exact Match Engine...")
            self.callbacks.get("status")("Scanning folders...")
            self.callbacks.get("progress")(0.1)
            start_time = time.time()
            try:
                extensions = None
                if file_types == "videos":
                    extensions = ProBackend.VIDEO_EXTENSIONS
                elif file_types == "images":
                    extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
                elif file_types == "documents":
                    extensions = {".pdf", ".doc", ".docx", ".txt", ".rtf", ".xls", ".xlsx", ".csv"}
                elif file_types == "audio":
                    extensions = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}

                # 1. Discover all files
                all_files = []
                for folder in folders:
                    if self.stop_requested: break
                    folder_path = Path(folder)
                    scanned = ProBackend.find_files(folder_path, recursive, extensions)
                    all_files.extend(scanned)

                self.log(f"Discovered {len(all_files)} files. Grouping by size...")
                
                # 2. Filter by size
                size_groups = {}
                for f in all_files:
                    if self.stop_requested: break
                    try:
                        sz = f.stat().st_size
                        if sz not in size_groups:
                            size_groups[sz] = []
                        size_groups[sz].append(f)
                    except Exception:
                        pass
                
                candidates = [f for group in size_groups.values() if len(group) > 1 for f in group]
                self.log(f"Size filter reduced search space to {len(candidates)} candidates.")

                # Mark all non-candidate files as skipped/grey (since they are unique by size)
                for f in all_files:
                    if f not in candidates:
                        self.file_progress(str(f), "skipped")

                # 3. Filter by quick signatures
                quick_groups = {}
                for f in candidates:
                    if self.stop_requested: break
                    self.file_progress(str(f), "processing")
                    
                    qh = ProBackend.quick_signature(f)
                    if qh:
                        key = (f.stat().st_size, qh[1])
                        if key not in quick_groups:
                            quick_groups[key] = []
                        quick_groups[key].append(f)
                        self.file_progress(str(f), "success")
                    else:
                        self.file_progress(str(f), "failed")

                candidates = [f for group in quick_groups.values() if len(group) > 1 for f in group]
                self.log(f"Quick signature filter reduced to {len(candidates)} candidates.")

                # 4. Compute full hashes for remaining candidates
                def full_hash(f_path):
                    hasher = hashlib.sha256()
                    with open(f_path, "rb") as f_in:
                        for chunk in iter(lambda: f_in.read(4096 * 1024), b""):
                            if self.stop_requested:
                                return None
                            hasher.update(chunk)
                    return hasher.hexdigest()

                full_groups = {}
                for i, f in enumerate(candidates, 1):
                    if self.stop_requested:
                        self.log("Scan stopped by user.")
                        break
                    
                    self.file_progress(str(f), "processing")
                    self.log(f"Hashing [{i}/{len(candidates)}]: {f.name}")
                    
                    try:
                        fh = full_hash(f)
                        if fh:
                            if fh not in full_groups:
                                full_groups[fh] = []
                            full_groups[fh].append(f)
                            self.file_progress(str(f), "success")
                        else:
                            self.file_progress(str(f), "failed")
                    except Exception as e:
                        self.log(f"[WARN] Failed to hash {f.name}: {e}")
                        self.file_progress(str(f), "failed")

                    self.callbacks.get("progress")(0.1 + 0.4 * (i / len(candidates)))

                # Group exact matches as MatchResult objects
                self.exact_matches = []
                for group in full_groups.values():
                    if len(group) > 1:
                        a = str(group[0])
                        sz_a = os.path.getsize(a) if os.path.exists(a) else 0
                        for other in group[1:]:
                            b = str(other)
                            sz_b = os.path.getsize(b) if os.path.exists(b) else 0
                            self.exact_matches.append(MatchResult(a, b, sz_a, sz_b, 100.0))

                elapsed = time.time() - start_time
                self.log(f"Scan complete. Indexed {len(all_files)} files in {elapsed:.2f}s.")
                self.callbacks.get("stats_update")("scanned", len(all_files))
                self.callbacks.get("stats_update")("time", f"{elapsed:.1f}s")
                self.callbacks.get("progress")(0.5)
                self.callbacks.get("status")("Ready")
            except Exception as e:
                self.log(f"[ERROR] Exact Scan failed: {str(e)}")
                self.callbacks.get("status")("Error")
            return

        # Perceptual Video Matching
        self.log("Initializing Pro Video Scan Engine...")
        if not self.ffmpeg_bin:
            self.log("[ERROR] ffmpeg not found in system PATH! Please install FFmpeg.")
            self.callbacks.get("status")("Error: Missing FFmpeg")
            return
            
        self.callbacks.get("status")("Scanning folders...")
        self.callbacks.get("progress")(0.1)
        start_time = time.time()
        try:
            hw_args = ProBackend.resolve_gpu(gpu_mode)
            self.log(f"Acceleration mode: {' '.join(hw_args) if hw_args else 'CPU Only'}")
            
            all_videos = []
            for f in folders:
                if self.stop_requested: break
                all_videos.extend(ProBackend.find_files(Path(f), recursive, ProBackend.VIDEO_EXTENSIONS))
            
            self.log(f"Found {len(all_videos)} video(s). Grouping by duration...")
            groups = []
            for v in all_videos:
                if self.stop_requested: break
                d = ProBackend.get_duration(v)
                if d is None: continue
                placed = False
                for g in groups:
                    if abs(g["duration"] - d) <= ProBackend.DURATION_TOLERANCE:
                        g["files"].append(v)
                        placed = True
                        break
                if not placed:
                    groups.append({"duration": d, "files": [v]})
            
            candidate_videos = [f for g in groups if len(g["files"]) > 1 for f in g["files"]]
            self.log(f"After duration filter: {len(candidate_videos)} candidate(s) need fingerprinting.")
            
            # Mark all non-candidate videos as skipped/grey (since they are unique by duration)
            for v in all_videos:
                if v not in candidate_videos:
                    self.file_progress(str(v), "skipped")

            cache_file = Path("TEMP/video_fingerprints.json")
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            if use_cache:
                ProBackend.load_cache(cache_file)
            else:
                ProBackend.cache = {}
                
            self.fingerprints_cache = {}
            for i, v in enumerate(candidate_videos, 1):
                if self.stop_requested:
                    self.log("Scan stopped by user.")
                    break
                path_str = str(v)
                mtime = str(v.stat().st_mtime)
                
                # Set status to processing (blue)
                self.file_progress(path_str, "processing")
                
                if path_str in ProBackend.cache and ProBackend.cache[path_str]["mtime"] == mtime:
                    self.fingerprints_cache[path_str] = ProBackend.cache[path_str]["hashes"]
                    # Highlight as skipped/loaded from cache (grey)
                    self.file_progress(path_str, "skipped")
                else:
                    self.log(f"Fingerprinting [{i}/{len(candidate_videos)}]: {v.name}")
                    try:
                        h = ProBackend.fingerprint(v, self.ffmpeg_bin, hw_args, extreme)
                        if h:
                            self.fingerprints_cache[path_str] = h
                            ProBackend.cache[path_str] = {"mtime": mtime, "hashes": h}
                            # Highlight as successfully processed (green)
                            self.file_progress(path_str, "success")
                        else:
                            # Highlight as failed (red)
                            self.file_progress(path_str, "failed")
                    except Exception as e:
                        self.log(f"[WARN] Failed to fingerprint {v.name}: {e}")
                        self.file_progress(path_str, "failed")
                
                self.callbacks.get("progress")(0.1 + 0.4 * (i / len(candidate_videos)))
                
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            ProBackend.save_cache(cache_file)
            
            elapsed = time.time() - start_time
            self.log(f"Scan & Fingerprint complete in {elapsed:.2f}s.")
            self.callbacks.get("stats_update")("scanned", len(all_videos))
            self.callbacks.get("stats_update")("time", f"{elapsed:.1f}s")
            self.callbacks.get("status")("Ready")
        except Exception as e:
            self.log(f"[ERROR] Video Scan failed: {str(e)}")
            self.callbacks.get("status")("Error")

    def run_compare(self, folders, threshold, mode="video"):
        self.stop_requested = False
        self.log(f"Initializing Similarity Comparison (Threshold: {threshold}%)...")
        self.callbacks.get("status")("Running matching algorithms...")
        self.callbacks.get("progress")(0.6)
        start_time = time.time()
        try:
            if mode == "exact":
                self.log("Loading exact duplicates...")
                self.callbacks.get("progress")(0.8)
                matches = self.exact_matches
                if folders:
                    norm_folders = [os.path.normcase(os.path.abspath(f)) for f in folders]
                    matches = [m for m in matches if any(os.path.normcase(m.path_a).startswith(f) or os.path.normcase(m.path_b).startswith(f) for f in norm_folders)]
                
                self.callbacks.get("progress")(0.95)
                elapsed = time.time() - start_time
                self.log(f"Match Pipeline complete in {elapsed:.2f}s. Found {len(matches)} exact duplicate pairs.")
                self.callbacks.get("stats_update")("duplicates", len(matches))
                wasted = sum(min(m.file_a_size, m.file_b_size) for m in matches)
                self.callbacks.get("stats_update")("wasted", format_size(wasted))
                self.callbacks.get("populate_grid")(matches)
                self.callbacks.get("progress")(1.0)
                self.callbacks.get("status")("Ready")
                return

            # Video mode compare
            paths = list(self.fingerprints_cache.keys())
            if folders:
                norm_folders = [os.path.normcase(os.path.abspath(f)) for f in folders]
                paths = [p for p in paths if any(os.path.normcase(p).startswith(f) for f in norm_folders)]
                
            quick_sigs = {}
            for p in paths:
                quick_sigs[p] = ProBackend.get_visual_quick_signature(self.fingerprints_cache[p])
                
            matches = []
            total_comparisons = (len(paths) * (len(paths) - 1)) // 2
            comp_count = 0
            
            for i in range(len(paths)):
                if self.stop_requested: break
                for j in range(i + 1, len(paths)):
                    if self.stop_requested: break
                    comp_count += 1
                    a, b = paths[i], paths[j]
                    matched = False
                    qa = quick_sigs[a]
                    qb = quick_sigs[b]
                    
                    if qa and qb and qa == qb:
                        matched = True
                        confidence = 100.0
                    else:
                        list_a = self.fingerprints_cache[a]
                        list_b = self.fingerprints_cache[b]
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
                                    confidence = percent

                    if matched:
                        sz_a = os.path.getsize(a) if os.path.exists(a) else 0
                        sz_b = os.path.getsize(b) if os.path.exists(b) else 0
                        matches.append(MatchResult(a, b, sz_a, sz_b, confidence))

                    if comp_count % 10 == 0:
                        self.callbacks.get("progress")(0.6 + 0.35 * (comp_count / max(1, total_comparisons)))

            elapsed = time.time() - start_time
            self.log(f"Match Pipeline complete in {elapsed:.2f}s. Found {len(matches)} visually similar pairs.")
            self.callbacks.get("stats_update")("duplicates", len(matches))
            
            wasted = sum(min(m.file_a_size, m.file_b_size) for m in matches)
            self.callbacks.get("stats_update")("wasted", format_size(wasted))
            
            self.callbacks.get("populate_grid")(matches)
            self.callbacks.get("progress")(1.0)
            self.callbacks.get("status")("Ready")
        except Exception as e:
            self.log(f"[ERROR] Similarity pipeline failed: {str(e)}")
            self.callbacks.get("status")("Error")


class DFFProGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Duplicate File Finder PRO — Unified Suite")
        self.geometry("1400x900")
        self.minsize(1050, 750)
        self.settings_file = "CONFIG/dff_pro_ui_settings.json"
        self.selected_folders = []
        self.is_running = False
        self.filepath_to_item = {}
        self.item_to_filepath = {}
        
        # Ensure critical subdirectories exist in working directory on startup
        Path("TEMP").mkdir(parents=True, exist_ok=True)
        Path("CONFIG").mkdir(parents=True, exist_ok=True)
        
        # Grid layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.engine = DFFProEngine({
            "log": self.write_console,
            "progress": self.set_progress,
            "status": self.set_status,
            "stats_update": self.update_stat_card,
            "populate_grid": self.populate_treeview,
            "scan_complete": self.on_scan_complete,
            "file_progress": self.update_file_highlight
        })
        
        self.build_sidebar()
        self.build_main_content()
        self.load_settings()
        self.on_mode_changed()  # Toggle settings panels and trigger automatic file listing!

    def build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color=BG_PANEL, border_color=BG_PANEL)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(11, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="DFF PRO SUITE", font=ctk.CTkFont(size=22, weight="bold"), text_color=ACCENT_BLUE_TEXT)
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 2))
        
        self.subtitle_label = ctk.CTkLabel(self.sidebar_frame, text="Unified Visual & Hashing Suite", font=ctk.CTkFont(size=11, slant="italic"), text_color=TEXT_SUB)
        self.subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 15))
        
        # --- Config Card ---
        self.config_card = ctk.CTkFrame(self.sidebar_frame, fg_color=BG_CARD, corner_radius=8)
        self.config_card.grid(row=4, column=0, padx=15, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.config_card, text="SCAN CONFIGURATION", font=ctk.CTkFont(size=10, weight="bold"), text_color=ACCENT_BLUE_TEXT).pack(pady=(10, 5), padx=10, anchor="w")
        
        # Scan Mode Selector
        ctk.CTkLabel(self.config_card, text="Matching Engine Mode:", font=ctk.CTkFont(size=10), text_color=TEXT_MAIN).pack(padx=10, anchor="w")
        self.combo_mode = ctk.CTkComboBox(self.config_card, values=["Similar Videos (Perceptual)", "Identical Files (Exact Hash)"], command=self.on_mode_changed, fg_color=BG_MAIN, border_color=BG_PANEL, text_color=TEXT_MAIN)
        self.combo_mode.pack(padx=10, pady=(0, 10), fill="x")
        
        # Strictness Match Threshold Slider inside Config Card
        self.compare_options_frame = ctk.CTkFrame(self.config_card, fg_color="transparent")
        self.compare_options_frame.pack(padx=10, pady=(0, 10), fill="x")
        
        self.threshold_label = ctk.CTkLabel(self.compare_options_frame, text="Strictness Match Threshold:", font=ctk.CTkFont(size=10), text_color=TEXT_MAIN)
        self.threshold_label.pack(anchor="w")
        
        slider_frame = ctk.CTkFrame(self.compare_options_frame, fg_color="transparent")
        slider_frame.pack(fill="x", pady=(2, 0))
        
        self.threshold_slider = ctk.CTkSlider(slider_frame, from_=50, to=100, number_of_steps=50, height=16, fg_color=BG_MAIN, progress_color=ACCENT_GREEN, button_color=ACCENT_GREEN, button_hover_color=ACCENT_CYAN)
        self.threshold_slider.pack(side="left", fill="x", expand=True)
        
        self.threshold_val_label = ctk.CTkLabel(slider_frame, text="70%", font=ctk.CTkFont(weight="bold", size=12), text_color=ACCENT_GREEN)
        self.threshold_val_label.pack(side="right", padx=(8, 0))
        self.threshold_slider.configure(command=lambda val: (self.threshold_val_label.configure(text=f"{int(val)}%"), self.on_setting_changed()))
        
        # Mode Panels Container
        self.mode_panel_frame = ctk.CTkFrame(self.config_card, fg_color="transparent")
        self.mode_panel_frame.pack(fill="x", padx=10, pady=(0, 5))
        
        # Settings Card (Global Checkboxes)
        self.settings_card = ctk.CTkFrame(self.sidebar_frame, fg_color=BG_CARD, corner_radius=8)
        self.settings_card.grid(row=5, column=0, padx=15, pady=5, sticky="ew")
        
        ctk.CTkLabel(self.settings_card, text="CACHE & TRAILING", font=ctk.CTkFont(size=10, weight="bold"), text_color=ACCENT_BLUE_TEXT).pack(pady=(10, 5), padx=10, anchor="w")
        self.chk_cache = ctk.CTkCheckBox(self.settings_card, text="Enable Smart Cache", text_color=TEXT_MAIN, hover_color=BG_CARD, fg_color=ACCENT_GREEN, command=self.on_setting_changed)
        self.chk_cache.pack(padx=10, pady=4, anchor="w")
        self.chk_cache.select()
        
        self.chk_resume = ctk.CTkCheckBox(self.settings_card, text="Enable Resume Log", text_color=TEXT_MAIN, hover_color=BG_CARD, fg_color=ACCENT_GREEN)
        self.chk_resume.pack(padx=10, pady=4, anchor="w")
        self.chk_resume.select()
        
        self.chk_log = ctk.CTkCheckBox(self.settings_card, text="Verbose Logs", text_color=TEXT_MAIN, hover_color=BG_CARD, fg_color=ACCENT_GREEN)
        self.chk_log.pack(padx=10, pady=4, anchor="w")
        
        self.chk_recursive = ctk.CTkCheckBox(self.settings_card, text="Recursive Scan", text_color=TEXT_MAIN, hover_color=BG_CARD, fg_color=ACCENT_GREEN, command=self.on_setting_changed)
        self.chk_recursive.pack(padx=10, pady=(4, 10), anchor="w")
        self.chk_recursive.select()
        
        # Action Card
        self.action_card = ctk.CTkFrame(self.sidebar_frame, fg_color=BG_CARD, corner_radius=8)
        self.action_card.grid(row=6, column=0, padx=15, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.action_card, text="CLEANUP ACTION", font=ctk.CTkFont(size=10, weight="bold"), text_color=ACCENT_BLUE_TEXT).pack(pady=(10, 5), padx=10, anchor="w")
        self.combo_action = ctk.CTkComboBox(self.action_card, values=["Send to Recycle Bin", "Permanently Delete", "Move to Backup Folder"], fg_color=BG_MAIN, border_color=BG_PANEL, text_color=TEXT_MAIN)
        self.combo_action.pack(padx=10, pady=(0, 5), fill="x")
        
        self.chk_dry_run = ctk.CTkCheckBox(self.action_card, text="Dry Run (Test only)", text_color=TEXT_MAIN, hover_color=BG_CARD, fg_color=ACCENT_GREEN)
        self.chk_dry_run.pack(padx=10, pady=(5, 10), anchor="w")
        self.chk_dry_run.select()
        
        # Style Theme selectors
        self.optionmenu_theme = ctk.CTkOptionMenu(self.sidebar_frame, values=["System", "Dark", "Light"], command=self.change_appearance_mode_event, fg_color=BG_CARD, text_color=TEXT_MAIN, button_color=BG_MAIN, button_hover_color=ACCENT_BLUE_BTN)
        self.optionmenu_theme.grid(row=12, column=0, padx=20, pady=(10, 20))

    def on_mode_changed(self, *args):
        # Clear specific panel options
        for widget in self.mode_panel_frame.winfo_children():
            widget.destroy()
            
        mode = self.combo_mode.get()
        if "Similar Videos" in mode:
            # Show threshold slider in config card
            self.compare_options_frame.pack(padx=10, pady=(0, 10), fill="x")
            
            # Video similarity UI panels
            ctk.CTkLabel(self.mode_panel_frame, text="GPU Hardware Accel:", font=ctk.CTkFont(size=10), text_color=TEXT_MAIN).pack(anchor="w")
            self.combo_gpu = ctk.CTkComboBox(self.mode_panel_frame, values=["Auto", "CUDA (NVIDIA)", "QSV (Intel)", "DXVA2 (AMD)", "CPU Only"], fg_color=BG_MAIN, border_color=BG_PANEL, text_color=TEXT_MAIN, command=self.on_setting_changed)
            self.combo_gpu.pack(pady=(0, 6), fill="x")
            
            self.chk_extreme = ctk.CTkCheckBox(self.mode_panel_frame, text="Extreme Acc (1fps/5s)", font=ctk.CTkFont(size=10), text_color=TEXT_MAIN, fg_color=ACCENT_GREEN, command=self.on_setting_changed)
            self.chk_extreme.pack(pady=4, anchor="w")
            
            self.chk_skip_dur = ctk.CTkCheckBox(self.mode_panel_frame, text="Skip Duration Match", font=ctk.CTkFont(size=10), text_color=TEXT_MAIN, fg_color=ACCENT_GREEN, command=self.on_setting_changed)
            self.chk_skip_dur.pack(pady=4, anchor="w")
            
            self.chk_skip_sig = ctk.CTkCheckBox(self.mode_panel_frame, text="Skip Quick Visual Sigs", font=ctk.CTkFont(size=10), text_color=TEXT_MAIN, fg_color=ACCENT_GREEN, command=self.on_setting_changed)
            self.chk_skip_sig.pack(pady=(4, 10), anchor="w")
        else:
            # Hide threshold slider in config card
            self.compare_options_frame.pack_forget()
            
            # Exact match UI panels
            ctk.CTkLabel(self.mode_panel_frame, text="Exact File Types:", font=ctk.CTkFont(size=10), text_color=TEXT_MAIN).pack(anchor="w")
            self.combo_file_types = ctk.CTkComboBox(self.mode_panel_frame, values=["all", "videos", "images", "documents", "audio"], fg_color=BG_MAIN, border_color=BG_PANEL, text_color=TEXT_MAIN, command=self.on_setting_changed)
            self.combo_file_types.pack(pady=(0, 10), fill="x")
            
        # Update flat/collapsible file listing without triggering comparisons!
        self.populate_all_files_live()

    def on_setting_changed(self, *args):
        if self.is_running: return
        self.populate_all_files_live()

    def build_main_content(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=0) # Stats Frame
        self.main_frame.grid_rowconfigure(1, weight=1) # Unified Content Area
        self.main_frame.grid_rowconfigure(2, weight=0) # Action controls
        self.main_frame.grid_rowconfigure(3, weight=0) # Logs console
        self.main_frame.grid_rowconfigure(4, weight=0) # Progress / status bar
        
        # 1. Stats Grid Cards
        self.stats_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.stats_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        for i in range(4): self.stats_frame.grid_columnconfigure(i, weight=1)
        
        self.stat_cards = {}
        self.stat_cards["scanned"] = self.create_stat_card(self.stats_frame, 0, "FILES INDEXED", "0", ACCENT_BLUE_TEXT)
        self.stat_cards["duplicates"] = self.create_stat_card(self.stats_frame, 1, "DUPLICATES DETECTED", "0", ACCENT_RED)
        self.stat_cards["wasted"] = self.create_stat_card(self.stats_frame, 2, "WASTED MEMORY SPACE", "0 B", ACCENT_YELLOW)
        self.stat_cards["time"] = self.create_stat_card(self.stats_frame, 3, "TOTAL INDEX TIME", "0.0s", ACCENT_GREEN)
        
        # 2. Unified Content Area (Stacked directories and grid)
        self.content_area = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_area.grid(row=1, column=0, sticky="nsew", pady=(0, 15))
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=0) # Directories Panel
        self.content_area.grid_rowconfigure(1, weight=1) # Results Treeview
        
        # 2A. Scan Input Panel (Top stacked card)
        self.scan_input_frame = ctk.CTkFrame(self.content_area, fg_color=BG_PANEL, corner_radius=12, border_color=BG_CARD, border_width=1)
        self.scan_input_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self.scan_input_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.scan_input_frame, text="Target Directories to Analyze:", font=ctk.CTkFont(weight="bold", size=14), text_color=ACCENT_BLUE_TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 5))
        self.folder_textbox = ctk.CTkTextbox(self.scan_input_frame, height=80, state="disabled", font=ctk.CTkFont(family="Consolas", size=13), fg_color=BG_MAIN, text_color=TEXT_MAIN, border_color=BG_CARD, border_width=1)
        self.folder_textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        
        btn_frame = ctk.CTkFrame(self.scan_input_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 15))
        ctk.CTkButton(btn_frame, text="Clear Libraries", fg_color="transparent", border_width=1, border_color=ACCENT_RED, text_color=ACCENT_RED, hover_color=BG_CARD, command=self.clear_folders, width=120).pack(side="left")
        ctk.CTkButton(btn_frame, text="+ Add Library Folder", fg_color=ACCENT_BLUE_BTN, text_color="white", hover_color=ACCENT_CYAN, font=ctk.CTkFont(weight="bold"), command=self.add_folder, width=170).pack(side="right")
        
        # 2B. DataGrid Frame (Bottom stacked card)
        self.grid_frame = ctk.CTkFrame(self.content_area, fg_color=BG_PANEL, corner_radius=12, border_color=BG_CARD, border_width=1)
        self.grid_frame.grid(row=1, column=0, sticky="nsew")
        self.grid_frame.grid_columnconfigure(0, weight=1)
        self.grid_frame.grid_rowconfigure(0, weight=1)
        
        # Treeview Custom Styling
        self.tree = ttk.Treeview(self.grid_frame, columns=("Select", "Filename", "Size", "Confidence"), show="headings")
        self.update_treeview_style()
        
        self.tree.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scrollbar = ttk.Scrollbar(self.grid_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<space>", self.on_tree_spacebar)
        
        # Smart Quick Selector
        self.quick_select_frame = ctk.CTkFrame(self.grid_frame, fg_color="transparent", height=40)
        self.quick_select_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 5), padx=10)
        
        ctk.CTkLabel(self.quick_select_frame, text="Auto-Rules:", font=ctk.CTkFont(weight="bold"), text_color=TEXT_MAIN).pack(side="left", padx=(0, 10))
        ctk.CTkButton(self.quick_select_frame, text="Keep Newest (Older for Del)", font=ctk.CTkFont(size=11), width=160, fg_color=BG_CARD, border_color=ACCENT_BLUE_BTN, border_width=1, hover_color=BG_MAIN, text_color=ACCENT_BLUE_TEXT, command=self.select_older).pack(side="left", padx=5)
        ctk.CTkButton(self.quick_select_frame, text="Keep Smallest (Larger for Del)", font=ctk.CTkFont(size=11), width=160, fg_color=BG_CARD, border_color=ACCENT_BLUE_BTN, border_width=1, hover_color=BG_MAIN, text_color=ACCENT_BLUE_TEXT, command=self.select_larger).pack(side="left", padx=5)
        ctk.CTkButton(self.quick_select_frame, text="Keep Largest (Smaller for Del)", font=ctk.CTkFont(size=11), width=160, fg_color=BG_CARD, border_color=ACCENT_BLUE_BTN, border_width=1, hover_color=BG_MAIN, text_color=ACCENT_BLUE_TEXT, command=self.select_smaller).pack(side="left", padx=5)
        ctk.CTkButton(self.quick_select_frame, text="Mark All But One", font=ctk.CTkFont(size=11), width=130, fg_color=BG_CARD, border_color=ACCENT_BLUE_BTN, border_width=1, hover_color=BG_MAIN, text_color=ACCENT_BLUE_TEXT, command=self.select_all_but_one).pack(side="left", padx=5)
        ctk.CTkButton(self.quick_select_frame, text="Unmark All", font=ctk.CTkFont(size=11), width=100, fg_color=BG_CARD, border_color=TEXT_SUB, border_width=1, hover_color=BG_MAIN, text_color=TEXT_MAIN, command=self.clear_selection).pack(side="right", padx=5)
        
        # 3. Action Execution Control Layer (Unified toggle START SCAN / STOP beside Execute Action)
        self.action_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.action_frame.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        self.action_frame.grid_columnconfigure(0, weight=1)
        self.action_frame.grid_columnconfigure(1, weight=1)
        
        self.btn_execute = ctk.CTkButton(self.action_frame, text="START SCAN", font=ctk.CTkFont(weight="bold", size=16), fg_color=ACCENT_GREEN, hover_color="#248a41", text_color="white", text_color_disabled="white", height=55, command=self.handle_execute_click)
        self.btn_execute.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        self.btn_execute_action = ctk.CTkButton(self.action_frame, text="EXECUTE CLEANUP ACTION", font=ctk.CTkFont(weight="bold", size=16), text_color="white", height=55, command=self.execute_action)
        self.btn_execute_action.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        # Initialized as disabled, beautifully grayed-out to prevent distraction
        is_light = ctk.get_appearance_mode() == "Light"
        self.btn_execute_action.configure(
            state="disabled",
            fg_color="gray" if is_light else "gray30",
            hover_color="gray",
            text_color="gray70" if is_light else "gray60"
        )
        
        # 4. Console Real-Time Log Output Panel
        self.console_frame = ctk.CTkFrame(self.main_frame, fg_color=BG_PANEL, corner_radius=12, border_color=BG_CARD, border_width=1)
        self.console_frame.grid(row=3, column=0, sticky="nsew")
        self.console_frame.grid_columnconfigure(0, weight=1)
        self.console_frame.grid_rowconfigure(1, weight=1)
        
        self.console_label = ctk.CTkLabel(self.console_frame, text="PRO ENGINE PIPELINE LOGS:", font=ctk.CTkFont(weight="bold", size=11), text_color=ACCENT_BLUE_TEXT)
        self.console_label.grid(row=0, column=0, sticky="w", padx=15, pady=(8, 2))
        self.console_textbox = ctk.CTkTextbox(self.console_frame, height=130, font=ctk.CTkFont(family="Consolas", size=12), fg_color=BG_MAIN, text_color=TEXT_MAIN, border_color=BG_CARD, border_width=1)
        self.console_textbox.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        
        # 5. Dynamic Progress Status Bar (Clean and modern green progress bar)
        self.bottom_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.bottom_frame.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self.bottom_frame.grid_columnconfigure(0, weight=1)
        
        self.progress_bar = ctk.CTkProgressBar(self.bottom_frame, height=8, fg_color=BG_CARD, progress_color=ACCENT_GREEN)
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        self.progress_bar.set(0)
        
        self.status_label = ctk.CTkLabel(self.bottom_frame, text="System Ready", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_MAIN)
        self.status_label.grid(row=1, column=0, sticky="w", pady=(5, 0))
        
        self.write_console("[SYSTEM] Duplicate File Finder PRO Suite Graphical Interface Initialized.")
        self.matches_data = []

    def get_display_path(self, filepath):
        path_obj = Path(filepath)
        for folder in self.selected_folders:
            try:
                folder_path = Path(folder)
                if path_obj.is_relative_to(folder_path):
                    # Get relative path from the parent of the library folder
                    rel = path_obj.relative_to(folder_path.parent)
                    # Get relative directory path
                    return "/" + rel.parent.as_posix()
            except Exception:
                pass
        return "/" + path_obj.parent.name

    def configure_tree_columns(self, layout="scanning"):
        is_multi = len(self.selected_folders) > 1
        
        if layout == "scanning":
            if not is_multi:
                self.tree.configure(columns=("Filename", "Size", "Status"))
                self.tree.heading("Filename", text="Filename")
                self.tree.heading("Size", text="Size")
                self.tree.heading("Status", text="Scan Status")
                
                self.tree.column("Filename", width=450, minwidth=200, stretch=True)
                self.tree.column("Size", width=120, anchor="e", stretch=False)
                self.tree.column("Status", width=220, minwidth=150, stretch=True)
            else:
                self.tree.configure(columns=("Filename", "Size", "Path", "Status"))
                self.tree.heading("Filename", text="Filename")
                self.tree.heading("Size", text="Size")
                self.tree.heading("Path", text="Parent Directory")
                self.tree.heading("Status", text="Scan Status")
                
                self.tree.column("Filename", width=300, minwidth=150, stretch=True)
                self.tree.column("Size", width=100, anchor="e", stretch=False)
                self.tree.column("Path", width=300, minwidth=150, stretch=True)
                self.tree.column("Status", width=200, minwidth=120, stretch=True)
        else: # results layout
            if not is_multi:
                self.tree.configure(columns=("Select", "Filename", "Size", "Confidence"))
                self.tree.heading("Select", text="☐", command=self.toggle_all)
                self.tree.heading("Filename", text="Filename")
                self.tree.heading("Size", text="Size")
                self.tree.heading("Confidence", text="Confidence")
                
                self.tree.column("Select", width=40, anchor="center", stretch=False)
                self.tree.column("Filename", width=450, minwidth=200, stretch=True)
                self.tree.column("Size", width=120, anchor="e", stretch=False)
                self.tree.column("Confidence", width=100, anchor="center", stretch=False)
            else:
                self.tree.configure(columns=("Select", "Filename", "Size", "Path", "Confidence"))
                self.tree.heading("Select", text="☐", command=self.toggle_all)
                self.tree.heading("Filename", text="Filename")
                self.tree.heading("Size", text="Size")
                self.tree.heading("Path", text="Parent Directory")
                self.tree.heading("Confidence", text="Confidence")
                
                self.tree.column("Select", width=40, anchor="center", stretch=False)
                self.tree.column("Filename", width=300, minwidth=150, stretch=True)
                self.tree.column("Size", width=100, anchor="e", stretch=False)
                self.tree.column("Path", width=320, minwidth=150, stretch=True)
                self.tree.column("Confidence", width=100, anchor="center", stretch=False)

    def create_stat_card(self, parent, col, title, value, color):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10)
        card.grid(row=0, column=col, padx=6, sticky="ew")
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=9, weight="bold"), text_color=TEXT_SUB).pack(pady=(12, 0))
        val_lbl = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=22, weight="bold"), text_color=color)
        val_lbl.pack(pady=(0, 12))
        return val_lbl

    def update_stat_card(self, key, value):
        self.after(0, lambda: self.stat_cards[key].configure(text=str(value)))

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)
        self.update_treeview_style(new_appearance_mode)
        # Update Execute Action button disabled color style
        self.update_execute_action_button_state()

    def update_treeview_style(self, mode=None):
        if mode is None or mode == "System":
            mode = ctk.get_appearance_mode()
        
        style = ttk.Style()
        style.theme_use("default")
        if mode == "Dark":
            bg = "#2b2b2b"
            fg = "white"
            head_bg = "#1f1f1f"
            head_fg = "white"
            sel_bg = "#2da44e"
            tag_bg = "#542828"
            tag_fg = "#ffb3b3"
            
            # Progress highlights in Dark mode
            prog_bg = "#1f385c"
            prog_fg = "#aaccff"
            succ_bg = "#1b4322"
            succ_fg = "#aaffaa"
            fail_bg = "#542828"
            fail_fg = "#ffb3b3"
            skip_bg = "#3a3a3a"
            skip_fg = "#b0b0b0"
        else:
            bg = "#ebebeb"
            fg = "black"
            head_bg = "#dbdbdb"
            head_fg = "black"
            sel_bg = "#2da44e"
            tag_bg = "#ffcccc"
            tag_fg = "#900000"
            
            # Progress highlights in Light mode
            prog_bg = "#e0f0ff"
            prog_fg = "#004080"
            succ_bg = "#e2f9e5"
            succ_fg = "#115e21"
            fail_bg = "#ffebe9"
            fail_fg = "#a01c1c"
            skip_bg = "#f0f0f0"
            skip_fg = "#606060"
            
        style.configure("Treeview", background=bg, foreground=fg, rowheight=28, fieldbackground=bg, borderwidth=0)
        style.map("Treeview", background=[("selected", sel_bg)], foreground=[("selected", "white")])
        style.configure("Treeview.Heading", background=head_bg, foreground=head_fg, font=('Segoe UI', 10, 'bold'), borderwidth=1)
        
        if hasattr(self, "tree"):
            self.tree.tag_configure("selected_row", background=tag_bg, foreground=tag_fg)
            self.tree.tag_configure("proc_current", background=prog_bg, foreground=prog_fg)
            self.tree.tag_configure("proc_success", background=succ_bg, foreground=succ_fg)
            self.tree.tag_configure("proc_failed", background=fail_bg, foreground=fail_fg)
            self.tree.tag_configure("proc_skipped", background=skip_bg, foreground=skip_fg)
        
    def add_folder(self):
        folder = filedialog.askdirectory(title="Add Library to Analyze")
        if folder and folder not in self.selected_folders:
            self.selected_folders.append(folder)
            self.update_folder_textbox()
            self.preview_directory(folder)
            self.populate_all_files_live() # Trigger dynamic file listing and indexing stats!

    def clear_folders(self):
        self.selected_folders.clear()
        self.update_folder_textbox()
        self.write_console("[SYSTEM] All library folders cleared.")
        self.tree.delete(*self.tree.get_children())
        self.filepath_to_item = {}
        self.item_to_filepath = {}
        self.update_stat_card("scanned", "0")
        self.update_stat_card("duplicates", "0")
        self.update_stat_card("wasted", "0 B")
        self.update_stat_card("time", "0.0s")
        
        # Restore side-by-side action buttons on reset
        self.btn_execute.grid()
        self.btn_execute_action.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.update_execute_action_button_state()

    def update_folder_textbox(self):
        self.folder_textbox.configure(state="normal")
        self.folder_textbox.delete("1.0", END)
        for f in self.selected_folders:
            self.folder_textbox.insert(END, f"{f}\n")
        self.folder_textbox.configure(state="disabled")

    def preview_directory(self, folder):
        """List files in a directory for immediate user feedback."""
        recursive = bool(self.chk_recursive.get())
        try:
            folder_path = Path(folder)
            if recursive:
                files = [f for f in folder_path.rglob("*") if f.is_file()]
            else:
                files = [f for f in folder_path.iterdir() if f.is_file()]

            total_size = sum(f.stat().st_size for f in files)
            size_text = format_size(total_size)

            self.write_console(f"[PREVIEW] Directory loaded: {folder}")
            self.write_console(f"[PREVIEW] Found {len(files)} files ({size_text} total)")

            if files:
                self.write_console(f"[PREVIEW] File listing (first 30):")
                for f in files[:30]:
                    sz = format_size(f.stat().st_size)
                    self.write_console(f"  {f.name}  ({sz})")
                if len(files) > 30:
                    self.write_console(f"  ... and {len(files) - 30} more files")

            self.update_stat_card("scanned", len(files))
            self.set_status(f"Ready - {len(files)} files in {len(self.selected_folders)} folder(s)")
        except Exception as e:
            self.write_console(f"[WARN] Could not preview directory: {e}")

    def write_console(self, text: str):
        self.after(0, self._write_console_safe, text)
        
    def _write_console_safe(self, text: str):
        self.console_textbox.configure(state="normal")
        self.console_textbox.insert(END, text + "\n")
        self.console_textbox.see(END)
        self.console_textbox.configure(state="disabled")

    def update_file_highlight(self, filepath, status):
        self.after(0, self._update_file_highlight_safe, filepath, status)
        
    def _update_file_highlight_safe(self, filepath, status):
        norm_path = os.path.normcase(filepath)
        if norm_path in self.filepath_to_item:
            item_id = self.filepath_to_item[norm_path]
            tag_map = {
                "processing": "proc_current",
                "success": "proc_success",
                "failed": "proc_failed",
                "skipped": "proc_skipped"
            }
            tag = tag_map.get(status)
            
            status_text_map = {
                "processing": "Processing File...",
                "success": "Processed Successfully",
                "failed": "Failed To Process",
                "skipped": "Skipped (Cached Already)"
            }
            status_text = status_text_map.get(status, "")
            
            if tag:
                current_tags = list(self.tree.item(item_id, "tags"))
                filtered_tags = [t for t in current_tags if t not in ["proc_current", "proc_success", "proc_failed", "proc_skipped"]]
                filtered_tags.append(tag)
                self.tree.item(item_id, tags=tuple(filtered_tags))
                
                # Update Status text in the table row
                is_multi = len(self.selected_folders) > 1
                status_col_idx = 3 if is_multi else 2
                
                vals = list(self.tree.item(item_id, "values"))
                if vals and len(vals) > status_col_idx:
                    vals[status_col_idx] = status_text
                    self.tree.item(item_id, values=vals)

    def set_progress(self, val: float):
        self.after(0, lambda: self.progress_bar.set(val))

    def set_status(self, text: str):
        self.after(0, lambda: self.status_label.configure(text=text))

    def handle_execute_click(self):
        if self.is_running:
            self.stop_execution()
        else:
            self.run_current_action()

    def stop_execution(self):
        if self.is_running:
            self.write_console("[SYSTEM] STOP requested. Cancelling current operations...")
            self.set_status("Stopping...")
            self.engine.request_stop()
            # Transition to stopping state to let the user know the click worked and it's stopping safely!
            self.btn_execute.configure(text="STOPPING... PLEASE WAIT", fg_color=ACCENT_YELLOW, state="disabled")

    def run_current_action(self, *args):
        if self.is_running: return
        if not self.selected_folders: return

        self.console_textbox.configure(state="normal")
        self.console_textbox.delete("1.0", END)
        self.console_textbox.configure(state="disabled")
        
        # Populate all files live
        self.populate_all_files_live()
        
        self.is_running = True
        self.set_progress(0)
        self.btn_execute.configure(text="STOP", fg_color=ACCENT_RED, hover_color="#a81c25")
        
        # Make sure execute button is visible and execute action button is gridded correctly in case they were side-by-side
        self.btn_execute.grid()
        self.btn_execute_action.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.update_execute_action_button_state()
        
        self.save_settings()
        
        mode = "exact" if "Identical" in self.combo_mode.get() else "video"
        folders = list(self.selected_folders)
        recursive = bool(self.chk_recursive.get())
        use_cache = bool(self.chk_cache.get())
        threshold = int(self.threshold_slider.get())
        
        if mode == "video":
            gpu = self.combo_gpu.get().replace("CUDA (NVIDIA)", "cuda").replace("QSV (Intel)", "qsv").replace("DXVA2 (AMD)", "dxva2").replace("CPU Only", "cpu")
            extreme = bool(self.chk_extreme.get())
            extra_args = (gpu, extreme)
        else:
            ftypes = self.combo_file_types.get()
            extra_args = (ftypes,)
            
        threading.Thread(target=self._full_pipeline_thread, args=(folders, use_cache, recursive, mode, threshold, extra_args), daemon=True).start()

    def populate_all_files_live(self):
        # Restore side-by-side action buttons on state change/reset
        if hasattr(self, "btn_execute") and hasattr(self, "btn_execute_action"):
            self.btn_execute.grid()
            self.btn_execute_action.grid(row=0, column=1, sticky="ew", padx=(10, 0))
            self.update_execute_action_button_state()
            
        # Clear the Treeview and reset mappings
        self.tree.delete(*self.tree.get_children())
        self.filepath_to_item = {}
        self.item_to_filepath = {}
        
        # Reset Stats
        self.update_stat_card("scanned", "0")
        self.update_stat_card("duplicates", "0")
        self.update_stat_card("wasted", "0 B")
        self.update_stat_card("time", "0.0s")
        
        # Configure columns dynamically based on selected folder count
        self.configure_tree_columns()
        
        # Configure Treeview layout (flat vs parent-child folders)
        if len(self.selected_folders) <= 1:
            self.tree.configure(show="headings")
        else:
            self.tree.configure(show="tree headings")
            self.tree.heading("#0", text="Library Folder Structure")
            self.tree.column("#0", width=250, minwidth=150)
            
        recursive = bool(self.chk_recursive.get())
        mode = "exact" if "Identical" in self.combo_mode.get() else "video"
        
        # Resolve file extensions
        extensions = None
        if mode == "exact":
            file_types = self.combo_file_types.get()
            if file_types == "videos":
                extensions = ProBackend.VIDEO_EXTENSIONS
            elif file_types == "images":
                extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
            elif file_types == "documents":
                extensions = {".pdf", ".doc", ".docx", ".txt", ".rtf", ".xls", ".xlsx", ".csv"}
            elif file_types == "audio":
                extensions = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}
        else:
            extensions = ProBackend.VIDEO_EXTENSIONS
            
        total_files = 0
        is_multi = len(self.selected_folders) > 1
        
        for folder in self.selected_folders:
            folder_path = Path(folder)
            if not folder_path.exists():
                continue
                
            # Create parent folder node if we are tracking multiple folders
            if is_multi:
                folder_id = self.tree.insert("", "end", text=f"📁 /{folder_path.name}", open=True, values=("", "", "", ""))
            else:
                folder_id = ""
                
            try:
                # Find files in target
                scanned_files = ProBackend.find_files(folder_path, recursive, extensions)
                for f in scanned_files:
                    total_files += 1
                    sz = f.stat().st_size if f.exists() else 0
                    sz_str = format_size(sz)
                    
                    if is_multi:
                        display_path = self.get_display_path(f)
                        item_id = self.tree.insert(folder_id, "end", values=(f.name, sz_str, display_path, "Ready to Scan"))
                    else:
                        item_id = self.tree.insert(folder_id, "end", values=(f.name, sz_str, "Ready to Scan"))
                        
                    self.filepath_to_item[os.path.normcase(str(f))] = item_id
                    self.item_to_filepath[item_id] = str(f)
                    
                    if total_files % 10 == 0:
                        self.update_stat_card("scanned", total_files)
            except Exception as e:
                self.write_console(f"[WARN] Error scanning {folder}: {e}")
                
        self.update_stat_card("scanned", total_files)

    def _full_pipeline_thread(self, folders, use_cache, recursive, mode, threshold, extra_args):
        try:
            if mode == "video":
                gpu, extreme = extra_args
                self.engine.run_scan(folders, use_cache=use_cache, recursive=recursive, mode="video", gpu_mode=gpu, extreme=extreme)
            else:
                ftypes = extra_args[0]
                self.engine.run_scan(folders, use_cache=use_cache, recursive=recursive, mode="exact", file_types=ftypes)
                
            if not self.engine.stop_requested:
                self.engine.run_compare(folders, threshold, mode)
        except Exception as e:
            self.write_console(f"[ERROR] Engine pipeline execution failed: {e}")
        finally:
            self.after(0, self._on_finish)

    def _on_finish(self):
        self.is_running = False
        self.btn_execute.configure(text="START SCAN", fg_color=ACCENT_GREEN, hover_color="#248a41", state="normal")
        self.set_progress(1.0)
        self.update_execute_action_button_state()
        
    def on_scan_complete(self):
        # Kept as a no-op placeholder for callbacks
        pass
        
    # --- DataGrid populate and selection ---
    
    def populate_treeview(self, matches):
        self.after(0, self._populate_treeview_safe, matches)
        
    def _populate_treeview_safe(self, matches):
        # 1. Configure the Treeview to use "results" layout
        self.configure_tree_columns(layout="results")
        
        is_multi = len(self.selected_folders) > 1
        conf_col_idx = 4 if is_multi else 3
        
        # 2. Restructure values of all existing file items for the results layout
        # and clear any progress color tags!
        file_items = self.get_all_file_items()
        for item in file_items:
            vals = list(self.tree.item(item, "values"))
            if vals:
                if is_multi:
                    # Old was (Filename, Size, Path, Status)
                    # New is (Select, Filename, Size, Path, Confidence)
                    filename = vals[0]
                    size = vals[1]
                    path = vals[2] if len(vals) > 2 else ""
                    new_vals = ("", filename, size, path, "")
                else:
                    # Old was (Filename, Size, Status)
                    # New is (Select, Filename, Size, Confidence)
                    filename = vals[0]
                    size = vals[1]
                    new_vals = ("", filename, size, "")
                self.tree.item(item, values=new_vals, tags=())

        # Restructure parent folder nodes as well to match results column count
        if is_multi:
            for item in self.tree.get_children(""):
                filepath = self.item_to_filepath.get(item)
                if not filepath: # Parent folder node
                    self.tree.item(item, values=("", "", "", "", ""))
                    
        self.matches_data = matches
        
        # Hide the START SCAN button since the scan is finished!
        self.btn_execute.grid_remove()
        # Regrid EXECUTE CLEANUP ACTION to span the entire action bar (columns 0 and 1)
        self.btn_execute_action.grid(row=0, column=0, columnspan=2, sticky="ew", padx=0)
        
        # 2. Map matches back to respective row lines
        for idx, match in enumerate(matches):
            conf = f"{match.confidence_score:.1f}%"
            
            # Map path_a
            norm_a = os.path.normcase(match.path_a)
            if norm_a in self.filepath_to_item:
                item_a = self.filepath_to_item[norm_a]
                vals = list(self.tree.item(item_a, "values"))
                if vals and len(vals) > conf_col_idx:
                    vals[0] = "☐"
                    vals[conf_col_idx] = conf
                    self.tree.item(item_a, values=vals, tags=("selected_row",))
            else:
                # Fallback insert
                sz_a = format_size(match.file_a_size)
                if is_multi:
                    item_a = self.tree.insert("", "end", values=("☐", Path(match.path_a).name, sz_a, self.get_display_path(match.path_a), conf), tags=("selected_row",))
                else:
                    item_a = self.tree.insert("", "end", values=("☐", Path(match.path_a).name, sz_a, conf), tags=("selected_row",))
                self.filepath_to_item[norm_a] = item_a
                self.item_to_filepath[item_a] = match.path_a
                
            # Map path_b
            norm_b = os.path.normcase(match.path_b)
            if norm_b in self.filepath_to_item:
                item_b = self.filepath_to_item[norm_b]
                vals = list(self.tree.item(item_b, "values"))
                if vals and len(vals) > conf_col_idx:
                    vals[0] = "☐"
                    vals[conf_col_idx] = conf
                    self.tree.item(item_b, values=vals, tags=("selected_row",))
            else:
                # Fallback insert
                sz_b = format_size(match.file_b_size)
                if is_multi:
                    item_b = self.tree.insert("", "end", values=("☐", Path(match.path_b).name, sz_b, self.get_display_path(match.path_b), conf), tags=("selected_row",))
                else:
                    item_b = self.tree.insert("", "end", values=("☐", Path(match.path_b).name, sz_b, conf), tags=("selected_row",))
                self.filepath_to_item[norm_b] = item_b
                self.item_to_filepath[item_b] = match.path_b

        self.update_execute_action_button_state()

    def get_all_file_items(self):
        items = []
        def recurse(parent):
            for child in self.tree.get_children(parent):
                vals = self.tree.item(child, "values")
                if vals and len(vals) > 2: # Filename and size columns exist
                    filepath = self.item_to_filepath.get(child)
                    if filepath: # Has mapped path, so it's a file
                        items.append(child)
                recurse(child)
        recurse("")
        return items

    def cleanup_empty_folders(self):
        # Delete parent nodes with no children
        for item in self.tree.get_children(""):
            filepath = self.item_to_filepath.get(item)
            if not filepath: # Parent folder node
                children = self.tree.get_children(item)
                if not children:
                    self.tree.delete(item)

    def update_execute_action_button_state(self):
        has_checked = False
        for item in self.get_all_file_items():
            vals = self.tree.item(item, "values")
            if vals and len(vals) > 0 and vals[0] == "✅":
                has_checked = True
                break
        if has_checked:
            # Turn bright red and make interactive when there's an action to execute
            self.btn_execute_action.configure(state="normal", fg_color=ACCENT_RED, hover_color="#a81c25", text_color="white")
        else:
            # Beautiful non-distracting disabled gray style
            is_light = ctk.get_appearance_mode() == "Light"
            self.btn_execute_action.configure(
                state="disabled",
                fg_color="gray" if is_light else "gray30",
                hover_color="gray",
                text_color="gray70" if is_light else "gray60"
            )

    def toggle_all(self):
        all_checked = True
        file_items = self.get_all_file_items()
        for item in file_items:
            vals = self.tree.item(item, "values")
            if vals and len(vals) > 0 and vals[0] == "☐":
                all_checked = False
                break
        
        new_val = "☐" if all_checked else "✅"
        for item in file_items:
            if "selected_row" in self.tree.item(item, "tags"): # Only duplicate files
                vals = list(self.tree.item(item, "values"))
                if vals:
                    vals[0] = new_val
                    self.tree.item(item, values=vals, tags=("selected_row",) if new_val == "✅" else ())
                
        self.update_execute_action_button_state()
            
    def on_tree_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.toggle_row(item)
            
    def on_tree_spacebar(self, event):
        selection = self.tree.selection()
        for item in selection:
            self.toggle_row(item)
            
    def toggle_row(self, item):
        if "selected_row" in self.tree.item(item, "tags"): # Only duplicate files
            vals = list(self.tree.item(item, "values"))
            if vals:
                is_checked = vals[0] == "✅"
                vals[0] = "☐" if is_checked else "✅"
                self.tree.item(item, values=vals, tags=() if is_checked else ("selected_row",))
                self.update_execute_action_button_state()

    def select_older(self):
        self.clear_selection()
        self._select_by_condition(lambda files: sorted(files, key=lambda f: os.path.getmtime(f) if os.path.exists(f) else 0)[:-1])

    def select_larger(self):
        self.clear_selection()
        self._select_by_condition(lambda files: sorted(files, key=lambda f: os.path.getsize(f) if os.path.exists(f) else 0)[1:])

    def select_smaller(self):
        self.clear_selection()
        self._select_by_condition(lambda files: sorted(files, key=lambda f: os.path.getsize(f) if os.path.exists(f) else 0)[:-1])

    def select_all_but_one(self):
        self.clear_selection()
        self._select_by_condition(lambda files: files[1:])

    def _select_by_condition(self, condition_func):
        # Build groups based on matches_data
        groups = {}
        for idx, match in enumerate(self.matches_data):
            grp_name = f"Group {idx+1}"
            groups[grp_name] = []
            
            norm_a = os.path.normcase(match.path_a)
            if norm_a in self.filepath_to_item:
                groups[grp_name].append((self.filepath_to_item[norm_a], match.path_a))
                
            norm_b = os.path.normcase(match.path_b)
            if norm_b in self.filepath_to_item:
                groups[grp_name].append((self.filepath_to_item[norm_b], match.path_b))
                
        for grp, items in groups.items():
            if len(items) > 1:
                paths = [p for _, p in items]
                to_select = condition_func(paths)
                for item, path in items:
                    if path in to_select:
                        vals = list(self.tree.item(item, "values"))
                        if vals:
                            vals[0] = "✅"
                            self.tree.item(item, values=vals, tags=("selected_row",))
                            
        self.update_execute_action_button_state()

    def clear_selection(self):
        for item in self.get_all_file_items():
            vals = list(self.tree.item(item, "values"))
            if vals and len(vals) > 0 and vals[0] == "✅":
                vals[0] = "☐"
                self.tree.item(item, values=vals, tags=())
        self.update_execute_action_button_state()
                
    def execute_action(self):
        action = self.combo_action.get()
        is_dry_run = bool(self.chk_dry_run.get())
        selected_items = []
        for item in self.get_all_file_items():
            vals = self.tree.item(item, "values")
            if vals and len(vals) > 0 and vals[0] == "✅":
                filepath = self.item_to_filepath.get(item)
                if filepath:
                    selected_items.append((item, filepath))
                
        if not selected_items:
            messagebox.showinfo("No Selection", "Please mark files using the checkbox column ☐ before executing.")
            return
            
        action_text = f"[DRY RUN] {action}" if is_dry_run else action
        confirm = messagebox.askyesno("Confirm Cleanup", f"Are you sure you want to execute '{action_text}' on {len(selected_items)} marked files?")
        if not confirm: return
            
        self.write_console(f"[CLEANUP] Executing: {action_text} on {len(selected_items)} files...")
        
        backup_dir = None
        if action == "Move to Backup Folder" and not is_dry_run:
            backup_dir = filedialog.askdirectory(title="Select Destination Library Folder")
            if not backup_dir: return
        
        success = 0
        for item, path in selected_items:
            try:
                if not os.path.exists(path) and not is_dry_run:
                    self.write_console(f"[WARN] File no longer exists: {path}")
                    continue
                    
                if is_dry_run:
                    self.write_console(f"[DRY RUN] Would cleanup: {Path(path).name}")
                else:
                    if action == "Send to Recycle Bin":
                        send2trash.send2trash(path)
                    elif action == "Permanently Delete":
                        os.remove(path)
                    elif action == "Move to Backup Folder":
                        shutil.move(path, os.path.join(backup_dir, os.path.basename(path)))
                
                success += 1
                self.tree.delete(item)
                # Remove from filepath mappings
                norm_p = os.path.normcase(path)
                if norm_p in self.filepath_to_item:
                    del self.filepath_to_item[norm_p]
                if item in self.item_to_filepath:
                    del self.item_to_filepath[item]
            except Exception as e:
                self.write_console(f"[ERROR] Failed cleanup on {Path(path).name}: {str(e)}")
                
        self.write_console(f"[SUCCESS] Successfully executed {success} file operations.")
        
        # Clean up empty parent folder nodes
        self.cleanup_empty_folders()
        
        # If no items left in tree, restore buttons
        if len(self.get_all_file_items()) == 0:
            self.btn_execute.grid()
            self.btn_execute_action.grid(row=0, column=1, sticky="ew", padx=(10, 0))
            
        # Update execute action button state
        self.update_execute_action_button_state()

    # --- Configuration Persistence ---
    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                
                mode = settings.get("appearance_mode", "Dark")
                ctk.set_appearance_mode(mode)
                self.optionmenu_theme.set(mode)
                
                self.threshold_slider.set(settings.get("threshold", 70))
                self.threshold_val_label.configure(text=f"{int(settings.get('threshold', 70))}%")
                
                self.combo_action.set(settings.get("action", "Send to Recycle Bin"))
                
                self.combo_mode.set(settings.get("scan_mode", "Similar Videos (Perceptual)"))
                if "Similar Videos" in self.combo_mode.get():
                    if hasattr(self, "combo_gpu"):
                        self.combo_gpu.set(settings.get("gpu", "Auto"))
                    if hasattr(self, "chk_extreme") and not settings.get("extreme", False): self.chk_extreme.deselect()
                    if hasattr(self, "chk_skip_dur") and settings.get("skip_dur", False): self.chk_skip_dur.select()
                    if hasattr(self, "chk_skip_sig") and settings.get("skip_sig", False): self.chk_skip_sig.select()
                else:
                    if hasattr(self, "combo_file_types"):
                        self.combo_file_types.set(settings.get("file_types", "all"))
                
                if not settings.get("cache", True): self.chk_cache.deselect()
                if not settings.get("resume", True): self.chk_resume.deselect()
                if settings.get("log", False): self.chk_log.select()
                if not settings.get("recursive", True): self.chk_recursive.deselect()
                
                self.selected_folders = settings.get("folders", [])
                self.update_folder_textbox()
            except Exception:
                pass

    def save_settings(self):
        settings = {
            "appearance_mode": self.optionmenu_theme.get(),
            "threshold": self.threshold_slider.get(),
            "action": self.combo_action.get(),
            "scan_mode": self.combo_mode.get(),
            "cache": bool(self.chk_cache.get()),
            "resume": bool(self.chk_resume.get()),
            "log": bool(self.chk_log.get()),
            "recursive": bool(self.chk_recursive.get()),
            "folders": self.selected_folders
        }
        if "Similar Videos" in self.combo_mode.get():
            if hasattr(self, "combo_gpu"): settings["gpu"] = self.combo_gpu.get()
            if hasattr(self, "chk_extreme"): settings["extreme"] = bool(self.chk_extreme.get())
            if hasattr(self, "chk_skip_dur"): settings["skip_dur"] = bool(self.chk_skip_dur.get())
            if hasattr(self, "chk_skip_sig"): settings["skip_sig"] = bool(self.chk_skip_sig.get())
        else:
            if hasattr(self, "combo_file_types"): settings["file_types"] = self.combo_file_types.get()
            
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            self.log(f"[WARN] Failed to write settings: {e}")

if __name__ == "__main__":
    app = DFFProGUI()
    app.mainloop()
