import os
import sys
import json
import time
import shutil
import threading
import send2trash
from pathlib import Path
from datetime import datetime
from tkinter import filedialog, ttk, END, messagebox

import customtkinter as ctk

# Ensure the ENGINE folder is on the path so we can load the dff_lite engine module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ENGINE"))

# --- DFF Lite Core Imports ---
from dff_lite.config.Config import load_config
from dff_lite.database.DB import DFFDatabase
from dff_lite.scanner.Scanner import scan_folders
from dff_lite.scoring.Pipeline import run_compare_pipeline
from dff_lite.exporters.Exporter import export_to_csv

def bootstrap():
    if hasattr(sys, 'real_prefix') or (sys.base_prefix != sys.prefix):
        return
    venv_dir = Path(".venv")
    python_exe = venv_dir / "Scripts" / "python.exe" if os.name == 'nt' else venv_dir / "bin" / "python"
    if python_exe.exists():
        os.execv(str(python_exe), [str(python_exe)] + sys.argv)

bootstrap()

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("green")

def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

class DFFLiteEngine:
    def __init__(self, app_callbacks):
        self.callbacks = app_callbacks
        self.stop_requested = False
        self.config = load_config()

    def log(self, message):
        self.callbacks.get("log", print)(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def run_scan(self, folders, use_cache=True, recursive=True):
        self.log("Initializing Advanced Scan Engine...")
        self.callbacks.get("status")("Connecting to Database...")
        self.callbacks.get("progress")(0.1)
        start_time = time.time()
        try:
            db_path = self.config.database.db_path
            db = DFFDatabase(db_path)
            if not use_cache:
                self.log("Cache disabled. Clearing existing DB records...")
                db.clear_cache()
            self.log(f"Scanning target folders: {', '.join(folders)}")
            self.callbacks.get("status")("Scanning and caching file metadata...")
            
            records = scan_folders(folders, db, self.config.scan, self.config.normalization, recursive=recursive)
            total = len(records)
            
            elapsed = time.time() - start_time
            self.log(f"Scan complete. Indexed {total} files in {elapsed:.2f}s.")
            self.callbacks.get("stats_update")("scanned", total)
            self.callbacks.get("stats_update")("time", f"{elapsed:.1f}s")
            
            self.callbacks.get("progress")(1.0)
            self.callbacks.get("status")("Ready")
            self.callbacks.get("scan_complete")()
        except Exception as e:
            self.log(f"[ERROR] Scan Pipeline failed: {str(e)}")
            self.callbacks.get("status")("Error")

    def run_compare(self, folders, threshold):
        self.log(f"Initializing Similarity Engine (Threshold: {threshold}%)...")
        self.callbacks.get("status")("Running matching algorithms...")
        self.callbacks.get("progress")(0.1)
        start_time = time.time()
        try:
            db_path = self.config.database.db_path
            
            db = DFFDatabase(db_path)
            self.log("Loading cache and computing blocks...")
            records = db.load_file_records()
            if folders:
                norm_folders = [os.path.normcase(os.path.abspath(f)) for f in folders]
                records = [r for r in records if any(os.path.normcase(r.path).startswith(f) for f in norm_folders)]
            self.callbacks.get("progress")(0.4)
            
            self.log("Evaluating similarity heuristics...")
            matches = run_compare_pipeline(records, self.config, db=db, threshold_override=threshold)
            self.callbacks.get("progress")(0.9)
            
            elapsed = time.time() - start_time
            self.log(f"Match Pipeline complete in {elapsed:.2f}s. Found {len(matches)} duplicate pairs.")
            self.callbacks.get("stats_update")("time", f"{elapsed:.1f}s")
            self.callbacks.get("stats_update")("duplicates", len(matches))
            
            wasted = sum(min(m.file_a_size, m.file_b_size) for m in matches)
            self.callbacks.get("stats_update")("wasted", format_size(wasted))
            
            if matches:
                out_csv = Path("TEMP/DFF_Lite_Matches.csv")
                export_to_csv(matches, out_csv)
                self.log(f"Results have been exported to: {out_csv.name}")
            
            self.callbacks.get("populate_grid")(matches)
                    
            self.callbacks.get("progress")(1.0)
            self.callbacks.get("status")("Ready")
        except Exception as e:
            self.log(f"[ERROR] Similarity Pipeline failed: {str(e)}")
            self.callbacks.get("status")("Error")
            import traceback
            traceback.print_exc()

class DFFLiteGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DFF-Lite: Advanced Duplicate File Finder PRO")
        self.geometry("1400x900")
        self.minsize(1000, 700)
        self.settings_file = "CONFIG/dff_ui_settings.json"
        self.selected_folders = []
        self.is_running = False
        
        # Grid layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.engine = DFFLiteEngine({
            "log": self.write_console,
            "progress": self.set_progress,
            "status": self.set_status,
            "stats_update": self.update_stat_card,
            "populate_grid": self.populate_treeview,
            "scan_complete": self.on_scan_complete
        })
        
        self.build_sidebar()
        self.build_main_content()
        self.load_settings()

    def build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(9, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="DFF-Lite PRO", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 5))
        self.subtitle_label = ctk.CTkLabel(self.sidebar_frame, text="Advanced Filename Intelligence", font=ctk.CTkFont(size=11, slant="italic"), text_color="gray")
        self.subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 20))
        
        self.btn_scan_tab = ctk.CTkButton(self.sidebar_frame, text="1. Select & Scan", height=40, anchor="w", fg_color="transparent", text_color=("gray10", "gray90"), command=lambda: self.select_tab("scan"))
        self.btn_scan_tab.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        self.btn_compare_tab = ctk.CTkButton(self.sidebar_frame, text="2. Compare & Execute", height=40, anchor="w", fg_color="transparent", text_color=("gray10", "gray90"), command=lambda: self.select_tab("compare"))
        self.btn_compare_tab.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        
        # Settings Card
        self.settings_card = ctk.CTkFrame(self.sidebar_frame)
        self.settings_card.grid(row=4, column=0, padx=15, pady=20, sticky="ew")
        
        ctk.CTkLabel(self.settings_card, text="ENGINE SETTINGS", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(pady=(10, 5), padx=10, anchor="w")
        self.chk_cache = ctk.CTkCheckBox(self.settings_card, text="Enable Smart Cache")
        self.chk_cache.pack(padx=10, pady=5, anchor="w")
        self.chk_cache.select()
        
        self.chk_resume = ctk.CTkCheckBox(self.settings_card, text="Enable Resume Log")
        self.chk_resume.pack(padx=10, pady=5, anchor="w")
        self.chk_resume.select()
        
        self.chk_log = ctk.CTkCheckBox(self.settings_card, text="Verbose Logging")
        self.chk_log.pack(padx=10, pady=5, anchor="w")
        
        self.chk_recursive = ctk.CTkCheckBox(self.settings_card, text="Recursive Scan")
        self.chk_recursive.pack(padx=10, pady=(5, 10), anchor="w")
        self.chk_recursive.select()
        
        # Action Card
        self.action_card = ctk.CTkFrame(self.sidebar_frame)
        self.action_card.grid(row=5, column=0, padx=15, pady=10, sticky="ew")
        ctk.CTkLabel(self.action_card, text="EXECUTION ACTION", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(pady=(10, 5), padx=10, anchor="w")
        self.combo_action = ctk.CTkComboBox(self.action_card, values=["Send to Recycle Bin", "Permanently Delete", "Move to Backup Folder"])
        self.combo_action.pack(padx=10, pady=(0, 5), fill="x")
        
        self.chk_dry_run = ctk.CTkCheckBox(self.action_card, text="Dry Run (Test only)")
        self.chk_dry_run.pack(padx=10, pady=(5, 10), anchor="w")
        self.chk_dry_run.select()
        
        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Appearance Mode:", anchor="w")
        self.appearance_mode_label.grid(row=10, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["System", "Dark", "Light"], command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=11, column=0, padx=20, pady=(10, 20))

    def build_main_content(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)  # Give weight to DataGrid
        
        # 1. Stats Overview Cards
        self.stats_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.stats_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        for i in range(4): self.stats_frame.grid_columnconfigure(i, weight=1)
        
        self.stat_cards = {}
        self.stat_cards["scanned"] = self.create_stat_card(self.stats_frame, 0, "FILES SCANNED", "0", "#3a7ebf")
        self.stat_cards["duplicates"] = self.create_stat_card(self.stats_frame, 1, "DUPLICATES FOUND", "0", "#CF222E")
        self.stat_cards["wasted"] = self.create_stat_card(self.stats_frame, 2, "WASTED SPACE", "0 B", "#E3B341")
        self.stat_cards["time"] = self.create_stat_card(self.stats_frame, 3, "PROCESSING TIME", "0.0s", "#2DA44E")
        
        # 2. Dynamic Content Area (Switches between Scan Input and DataGrid)
        self.content_area = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_area.grid(row=1, column=0, sticky="nsew", pady=(0, 15))
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)
        
        # 2A. Scan Input Frame
        self.scan_input_frame = ctk.CTkFrame(self.content_area)
        self.scan_input_frame.grid(row=0, column=0, sticky="nsew")
        self.scan_input_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.scan_input_frame, text="Target Directories to Scan:", font=ctk.CTkFont(weight="bold", size=14)).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))
        self.folder_textbox = ctk.CTkTextbox(self.scan_input_frame, height=120, state="disabled", font=ctk.CTkFont(size=13))
        self.folder_textbox.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))
        
        btn_frame = ctk.CTkFrame(self.scan_input_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 15))
        ctk.CTkButton(btn_frame, text="Clear All", fg_color="transparent", border_width=1, text_color=("gray10", "#DCE4EE"), command=self.clear_folders, width=100).pack(side="left")
        ctk.CTkButton(btn_frame, text="+ Add Directory", command=self.add_folder, width=140).pack(side="right")
        
        # 2B. DataGrid Frame
        self.grid_frame = ctk.CTkFrame(self.content_area)
        self.grid_frame.grid(row=0, column=0, sticky="nsew")
        self.grid_frame.grid_columnconfigure(0, weight=1)
        self.grid_frame.grid_rowconfigure(0, weight=1)
        
        # Treeview styling
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", rowheight=25, fieldbackground="#2b2b2b")
        style.map("Treeview", background=[("selected", "#3a7ebf")])
        style.configure("Treeview.Heading", background="#1f1f1f", foreground="white", font=('Helvetica', 10, 'bold'))
        
        self.tree = ttk.Treeview(self.grid_frame, columns=("Select", "Group", "Filename", "Size", "Path", "Confidence"), show="headings")
        self.tree.tag_configure("selected_row", background="#542828", foreground="#ffb3b3")
        
        self.tree.heading("Select", text="☐", command=self.toggle_all)
        self.tree.heading("Group", text="Group")
        self.tree.heading("Filename", text="Filename")
        self.tree.heading("Size", text="Size")
        self.tree.heading("Path", text="Path")
        self.tree.heading("Confidence", text="Confidence")
        
        self.tree.column("Select", width=40, anchor="center")
        self.tree.column("Group", width=80, anchor="center")
        self.tree.column("Filename", width=250)
        self.tree.column("Size", width=80, anchor="e")
        self.tree.column("Path", width=350)
        self.tree.column("Confidence", width=80, anchor="center")
        
        self.tree.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        scrollbar = ttk.Scrollbar(self.grid_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<space>", self.on_tree_spacebar)
        
        # Quick Select Panel (under Grid)
        self.quick_select_frame = ctk.CTkFrame(self.grid_frame, fg_color="transparent", height=40)
        self.quick_select_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 5), padx=5)
        
        ctk.CTkLabel(self.quick_select_frame, text="Quick Select:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        ctk.CTkButton(self.quick_select_frame, text="Select Older", width=100, command=self.select_older).pack(side="left", padx=5)
        ctk.CTkButton(self.quick_select_frame, text="Select Larger", width=100, command=self.select_larger).pack(side="left", padx=5)
        ctk.CTkButton(self.quick_select_frame, text="Select Smaller", width=100, command=self.select_smaller).pack(side="left", padx=5)
        ctk.CTkButton(self.quick_select_frame, text="Select All But One", width=120, command=self.select_all_but_one).pack(side="left", padx=5)
        ctk.CTkButton(self.quick_select_frame, text="Clear Selection", width=100, fg_color="#555", hover_color="#444", command=self.clear_selection).pack(side="right", padx=5)
        
        # 3. Action / Execute Controls
        self.action_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.action_frame.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        self.action_frame.grid_columnconfigure(0, weight=1)
        
        self.btn_execute = ctk.CTkButton(self.action_frame, text="START PRO SCAN", font=ctk.CTkFont(weight="bold", size=16), height=55, command=self.run_current_action)
        self.btn_execute.grid(row=0, column=0, sticky="ew")
        
        self.btn_execute_action = ctk.CTkButton(self.action_frame, text="EXECUTE ACTION ON SELECTED", fg_color="#CF222E", hover_color="#A51B25", font=ctk.CTkFont(weight="bold", size=16), height=55, command=self.execute_action)
        self.btn_execute_action.grid(row=0, column=0, sticky="ew")
        self.btn_execute_action.grid_remove() # Hidden initially
        
        # Compare Options (Threshold)
        self.compare_options_frame = ctk.CTkFrame(self.action_frame, fg_color="transparent")
        self.threshold_label = ctk.CTkLabel(self.compare_options_frame, text="Similarity Threshold:", font=ctk.CTkFont(weight="bold"))
        self.threshold_label.pack(side="left", padx=5)
        self.threshold_slider = ctk.CTkSlider(self.compare_options_frame, from_=0, to=100, number_of_steps=100)
        self.threshold_slider.pack(side="left", padx=15, fill="x", expand=True)
        self.threshold_val_label = ctk.CTkLabel(self.compare_options_frame, text="80%", font=ctk.CTkFont(weight="bold"))
        self.threshold_val_label.pack(side="left", padx=5)
        self.threshold_slider.configure(command=lambda val: self.threshold_val_label.configure(text=f"{int(val)}%"))
        
        # 4. Console Output
        self.console_frame = ctk.CTkFrame(self.main_frame)
        self.console_frame.grid(row=3, column=0, sticky="nsew")
        self.console_frame.grid_columnconfigure(0, weight=1)
        self.console_frame.grid_rowconfigure(1, weight=1)
        
        self.console_label = ctk.CTkLabel(self.console_frame, text="Live Log / Output:", font=ctk.CTkFont(weight="bold", size=12))
        self.console_label.grid(row=0, column=0, sticky="w", padx=10, pady=(5, 0))
        self.console_textbox = ctk.CTkTextbox(self.console_frame, height=120, font=ctk.CTkFont(family="Consolas", size=12))
        self.console_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # 5. Bottom Status Bar (matches Video Optimizer)
        self.bottom_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.bottom_frame.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.bottom_frame.grid_columnconfigure(0, weight=1)
        
        self.progress_bar = ctk.CTkProgressBar(self.bottom_frame, height=10)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 15))
        self.progress_bar.set(0)
        
        self.status_label = ctk.CTkLabel(self.bottom_frame, text="Ready", font=ctk.CTkFont(size=12, weight="bold"))
        self.status_label.grid(row=1, column=0, sticky="w")
        
        self.btn_stop = ctk.CTkButton(self.bottom_frame, text="STOP", fg_color="#CF222E", hover_color="#A51B25", width=120, height=40, font=ctk.CTkFont(weight="bold"), command=self.stop_execution)
        self.btn_stop.grid(row=0, column=1, rowspan=2, sticky="e")
        self.btn_stop.configure(state="disabled")

        self.select_tab("scan")
        self.write_console("[SYSTEM] DFF-Lite PRO Native GUI Initialized.")
        
        self.matches_data = [] # Store MatchResult objects

    def create_stat_card(self, parent, col, title, value, color):
        card = ctk.CTkFrame(parent)
        card.grid(row=0, column=col, padx=5, sticky="ew")
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=10, weight="bold"), text_color="gray").pack(pady=(10, 0))
        val_lbl = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=24, weight="bold"), text_color=color)
        val_lbl.pack(pady=(0, 10))
        return val_lbl

    def update_stat_card(self, key, value):
        self.after(0, lambda: self.stat_cards[key].configure(text=str(value)))

    def select_tab(self, mode):
        self.current_mode = mode
        self.btn_scan_tab.configure(fg_color=("gray75", "#2b2b2b") if mode == "scan" else "transparent")
        self.btn_compare_tab.configure(fg_color=("gray75", "#2b2b2b") if mode == "compare" else "transparent")
        
        if mode == "scan":
            self.scan_input_frame.tkraise()
            self.btn_execute.grid()
            self.btn_execute_action.grid_remove()
            self.btn_execute.configure(text="START PRO SCAN", fg_color=["#3a7ebf", "#1f538d"])
            self.compare_options_frame.grid_forget()
        elif mode == "compare":
            self.grid_frame.tkraise()
            self.btn_execute.grid()
            self.btn_execute_action.grid_remove()
            self.btn_execute.configure(text="RUN COMPARE ALGORITHM", fg_color=["#2DA44E", "#1A7F37"])
            self.compare_options_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)
        
    def add_folder(self):
        folder = filedialog.askdirectory(title="Select Target Directory")
        if folder and folder not in self.selected_folders:
            self.selected_folders.append(folder)
            self.update_folder_textbox()

    def clear_folders(self):
        self.selected_folders.clear()
        self.update_folder_textbox()

    def update_folder_textbox(self):
        self.folder_textbox.configure(state="normal")
        self.folder_textbox.delete("1.0", END)
        for f in self.selected_folders:
            self.folder_textbox.insert(END, f"{f}\n")
        self.folder_textbox.configure(state="disabled")

    def write_console(self, text: str):
        self.after(0, self._write_console_safe, text)
        
    def _write_console_safe(self, text: str):
        self.console_textbox.configure(state="normal")
        self.console_textbox.insert(END, text + "\n")
        self.console_textbox.see(END)
        self.console_textbox.configure(state="disabled")

    def set_progress(self, val: float):
        self.after(0, lambda: self.progress_bar.set(val))

    def set_status(self, text: str):
        self.after(0, lambda: self.status_label.configure(text=text))

    def stop_execution(self):
        if self.is_running:
            self.engine.request_stop()
            self.btn_stop.configure(state="disabled")

    def run_current_action(self):
        if self.is_running:
            return

        if not self.selected_folders and self.current_mode == "scan":
            self.write_console("[!] Please select at least one target folder to scan.")
            return

        self.console_textbox.configure(state="normal")
        self.console_textbox.delete("1.0", END)
        self.console_textbox.configure(state="disabled")
        
        self.is_running = True
        self.set_progress(0)
        self.btn_execute.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.save_settings()
        
        if self.current_mode == "scan":
            folders = list(self.selected_folders)
            threading.Thread(target=self._scan_thread, args=(folders,), daemon=True).start()
        elif self.current_mode == "compare":
            folders = list(self.selected_folders)
            threshold = int(self.threshold_slider.get())
            threading.Thread(target=self._compare_thread, args=(folders, threshold), daemon=True).start()

    def _scan_thread(self, folders):
        try:
            self.engine.run_scan(folders, use_cache=bool(self.chk_cache.get()), recursive=bool(self.chk_recursive.get()))
        finally:
            self.after(0, self._on_finish)

    def _compare_thread(self, folders, threshold):
        try:
            self.engine.run_compare(folders, threshold)
        finally:
            self.after(0, self._on_finish)

    def _on_finish(self):
        self.is_running = False
        self.btn_execute.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.set_progress(1.0)
        
    def on_scan_complete(self):
        self.select_tab("compare")
        
    # --- DataGrid & Execution Logic ---
    
    def populate_treeview(self, matches):
        self.after(0, self._populate_treeview_safe, matches)
        
    def _populate_treeview_safe(self, matches):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        self.matches_data = matches
        
        for idx, match in enumerate(matches):
            group_name = f"Group {idx+1}"
            conf = f"{match.confidence_score:.1f}%"
            
            sz_a = format_size(match.file_a_size)
            self.tree.insert("", "end", values=("☐", group_name, Path(match.path_a).name, sz_a, match.path_a, conf))
            
            sz_b = format_size(match.file_b_size)
            self.tree.insert("", "end", values=("☐", group_name, Path(match.path_b).name, sz_b, match.path_b, conf))
        
        if matches:
            self.btn_execute.grid_remove()
            self.btn_execute_action.grid()
            self.compare_options_frame.grid_forget()

    def toggle_all(self):
        all_checked = True
        for item in self.tree.get_children():
            if self.tree.item(item, "values")[0] == "☐":
                all_checked = False
                break
        
        new_val = "☐" if all_checked else "☑"
        for item in self.tree.get_children():
            vals = list(self.tree.item(item, "values"))
            vals[0] = new_val
            self.tree.item(item, values=vals, tags=("selected_row",) if new_val == "☑" else ())
            
    def on_tree_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.toggle_row(item)
            
    def on_tree_spacebar(self, event):
        selection = self.tree.selection()
        for item in selection:
            self.toggle_row(item)
            
    def toggle_row(self, item):
        vals = list(self.tree.item(item, "values"))
        is_checked = vals[0] == "☑"
        vals[0] = "☐" if is_checked else "☑"
        self.tree.item(item, values=vals, tags=() if is_checked else ("selected_row",))

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
        # Group items by Group Name in tree
        groups = {}
        for item in self.tree.get_children():
            vals = self.tree.item(item, "values")
            grp = vals[1]
            path = vals[4]
            if grp not in groups:
                groups[grp] = []
            groups[grp].append((item, path))
            
        for grp, items in groups.items():
            if len(items) > 1:
                paths = [p for _, p in items]
                to_select = condition_func(paths)
                for item, path in items:
                    if path in to_select:
                        vals = list(self.tree.item(item, "values"))
                        vals[0] = "☑"
                        self.tree.item(item, values=vals, tags=("selected_row",))

    def clear_selection(self):
        for item in self.tree.get_children():
            vals = list(self.tree.item(item, "values"))
            if vals[0] == "☑":
                vals[0] = "☐"
                self.tree.item(item, values=vals, tags=())
                
    def execute_action(self):
        action = self.combo_action.get()
        is_dry_run = bool(self.chk_dry_run.get())
        selected_items = []
        for item in self.tree.get_children():
            if self.tree.item(item, "values")[0] == "☑":
                selected_items.append((item, self.tree.item(item, "values")[4]))
                
        if not selected_items:
            messagebox.showinfo("No Selection", "Please select at least one file using the ☑ column checkboxes.")
            return
            
        action_text = f"[DRY RUN] {action}" if is_dry_run else action
        confirm = messagebox.askyesno("Confirm Action", f"Are you sure you want to execute '{action_text}' on {len(selected_items)} files?")
        if not confirm:
            return
            
        self.write_console(f"Executing: {action_text} on {len(selected_items)} files...")
        
        backup_dir = None
        if action == "Move to Backup Folder" and not is_dry_run:
            backup_dir = filedialog.askdirectory(title="Select Backup Destination")
            if not backup_dir:
                return
        
        success = 0
        for item, path in selected_items:
            try:
                if not os.path.exists(path) and not is_dry_run:
                    self.write_console(f"[WARN] Not found: {path}")
                    continue
                    
                if is_dry_run:
                    self.write_console(f"[DRY RUN] Would execute '{action}' on: {Path(path).name}")
                else:
                    if action == "Send to Recycle Bin":
                        send2trash.send2trash(path)
                    elif action == "Permanently Delete":
                        os.remove(path)
                    elif action == "Move to Backup Folder":
                        shutil.move(path, os.path.join(backup_dir, os.path.basename(path)))
                
                success += 1
                self.tree.delete(item)
            except Exception as e:
                self.write_console(f"[ERROR] Failed on {Path(path).name}: {str(e)}")
                
        self.write_console(f"[OK] Successfully processed {success} files.")
        
        # Reset View if empty
        if len(self.tree.get_children()) == 0:
            self.btn_execute.grid()
            self.btn_execute_action.grid_remove()
            self.compare_options_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))

    # --- Settings Persistence ---
    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                
                mode = settings.get("appearance_mode", "System")
                ctk.set_appearance_mode(mode)
                self.appearance_mode_optionemenu.set(mode)
                
                self.threshold_slider.set(settings.get("threshold", 80))
                self.threshold_val_label.configure(text=f"{int(settings.get('threshold', 80))}%")
                
                self.combo_action.set(settings.get("action", "Send to Recycle Bin"))
                
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
            "appearance_mode": self.appearance_mode_optionemenu.get(),
            "threshold": self.threshold_slider.get(),
            "action": self.combo_action.get(),
            "cache": bool(self.chk_cache.get()),
            "resume": bool(self.chk_resume.get()),
            "log": bool(self.chk_log.get()),
            "recursive": bool(self.chk_recursive.get()),
            "folders": self.selected_folders
        }
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            self.log(f"[WARN] Failed to save settings: {e}")

if __name__ == "__main__":
    app = DFFLiteGUI()
    app.mainloop()
