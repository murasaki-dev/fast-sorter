import os
import sys
import json
import shutil
import subprocess
import platform
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import cv2

# Determine the absolute directory where this script or executable resides
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "sorter_config.json")

class SetupDialog:
    def __init__(self, root):
        self.root = root
        self.root.title("Fast Media Sorter - Configuration")
        self.root.geometry("620x840")
        
        self.source_dir = ""
        self.dest_dirs = {}
        self.dest_entries = {}
        self.key_buttons = {}
        self.action_key_buttons = {}
        self.listening_key = None
        self.listening_action = None
        
        # Default key bindings
        self.default_keys = {
            'slot_0': 'w',
            'slot_1': 'a',
            'slot_2': 's',
            'slot_3': 'd',
            'slot_4': 'i',
            'slot_5': 'j',
            'slot_6': 'k',
            'slot_7': 'l'
        }
        self.default_action_keys = {
            'skip': 'space',
            'undo': 'backspace'
        }
        self.current_keys = self.default_keys.copy()
        self.current_action_keys = self.default_action_keys.copy()
        
        # --- Source Folder Section ---
        tk.Label(root, text="Unsorted Media Folder:", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 0))
        
        src_frame = tk.Frame(root)
        src_frame.pack(fill="x", padx=20, pady=5)
        
        self.src_entry = tk.Entry(src_frame, width=45)
        self.src_entry.pack(side="left", padx=(0, 5))
        tk.Button(src_frame, text="Browse Source", command=self.browse_source).pack(side="left")
        
        # --- Destination Folders & Key Rebinding Section ---
        tk.Label(root, text="Assign Folders & Rebind Folder Keys (Click button to change key):", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 0))
        
        self.folder_rows_frame = tk.Frame(root)
        self.folder_rows_frame.pack(fill="x", padx=20, pady=5)

        # --- Action Key Rebinding Section ---
        tk.Label(root, text="Action Keys Rebinding:", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(10, 0))
        
        self.action_rows_frame = tk.Frame(root)
        self.action_rows_frame.pack(fill="x", padx=20, pady=5)

        self.rebuild_key_ui()

        tk.Label(root, text="* Mouse Wheel = Zoom | Left-click Drag = Pan\n* Nav: Left/Right Arrows = Prev/Next | Delete = Move to Local Trash (Undoable)", 
                 fg="gray", font=("Arial", 9), justify="left").pack(pady=5)
        
        # Action Buttons Frame
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Start Sorting", bg="#28a745", fg="white", font=("Arial", 11, "bold"), 
                  padx=15, pady=5, command=self.validate_and_start).pack(side="left", padx=10)
        
        tk.Button(btn_frame, text="Clear Saved Folders", bg="#dc3545", fg="white", font=("Arial", 10), 
                  padx=10, pady=5, command=self.clear_config).pack(side="left", padx=10)

        # Load saved config on startup
        self.load_saved_config()
        self.root.bind("<Key>", self.handle_key_listen)

    def rebuild_key_ui(self):
        for widget in self.folder_rows_frame.winfo_children():
            widget.destroy()
        for widget in self.action_rows_frame.winfo_children():
            widget.destroy()
            
        self.dest_entries.clear()
        self.key_buttons.clear()
        self.action_key_buttons.clear()

        # Folder slots UI
        for i in range(8):
            slot_id = f"slot_{i}"
            current_bind = self.current_keys[slot_id].upper()
            
            frame = tk.Frame(self.folder_rows_frame)
            frame.pack(fill="x", pady=2)
            
            key_btn = tk.Button(frame, text=f"Key: [{current_bind}]", width=12, bg="#e0e0e0",
                                command=lambda s=slot_id: self.start_listening_slot(s))
            key_btn.pack(side="left")
            self.key_buttons[slot_id] = key_btn
            
            entry = tk.Entry(frame, width=45)
            entry.pack(side="left", padx=5)
            
            bound_key_char = self.current_keys[slot_id]
            if bound_key_char in self.dest_dirs:
                entry.insert(0, self.dest_dirs[bound_key_char])
                
            btn = tk.Button(frame, text="Browse", command=lambda s=slot_id, e=entry: self.browse_dest(s, e))
            btn.pack(side="left")
            self.dest_entries[slot_id] = (entry, btn)

        # Action slots UI (Skip and Undo)
        actions = [('skip', 'Skip Media'), ('undo', 'Undo Last Move')]
        for action_id, action_label in actions:
            current_bind = self.current_action_keys[action_id].upper()
            
            frame = tk.Frame(self.action_rows_frame)
            frame.pack(fill="x", pady=2)
            
            key_btn = tk.Button(frame, text=f"Key: [{current_bind}]", width=12, bg="#e0e0e0",
                                command=lambda a=action_id: self.start_listening_action(a))
            key_btn.pack(side="left")
            self.action_key_buttons[action_id] = key_btn
            
            lbl = tk.Label(frame, text=action_label, font=("Arial", 9))
            lbl.pack(side="left", padx=10)

    def start_listening_slot(self, slot_id):
        self.listening_key = slot_id
        self.listening_action = None
        for s_id, btn in self.key_buttons.items():
            if s_id == slot_id:
                btn.config(text="Press any key...", bg="#ffc107")
            else:
                btn.config(relief="raised", bg="#e0e0e0")
        for a_id, btn in self.action_key_buttons.items():
            btn.config(relief="raised", bg="#e0e0e0")

    def start_listening_action(self, action_id):
        self.listening_action = action_id
        self.listening_key = None
        for a_id, btn in self.action_key_buttons.items():
            if a_id == action_id:
                btn.config(text="Press any key...", bg="#ffc107")
            else:
                btn.config(relief="raised", bg="#e0e0e0")
        for s_id, btn in self.key_buttons.items():
            btn.config(relief="raised", bg="#e0e0e0")

    def handle_key_listen(self, event):
        if not self.listening_key and not self.listening_action:
            return
            
        if event.keysym.lower() in ['shift_l', 'shift_r', 'control_l', 'control_r', 'alt_l', 'alt_r', 'caps_lock']:
            return
            
        new_char = event.keysym.lower()
        reserved_keys = ['left', 'right', 'return', 'escape', 'delete', 'back_space']
        if new_char in reserved_keys:
            messagebox.showwarning("Invalid Key", f"The key '{event.keysym}' is reserved for navigation or deletion.")
            return

        if self.listening_key:
            for s_id, char in self.current_keys.items():
                if char == new_char and s_id != self.listening_key:
                    messagebox.showwarning("Key in Use", f"Key '{new_char.upper()}' is already assigned to another folder slot.")
                    return
            for a_id, char in self.current_action_keys.items():
                if char == new_char:
                    messagebox.showwarning("Key in Use", f"Key '{new_char.upper()}' is already assigned to action '{a_id.capitalize()}'.")
                    return

            old_char = self.current_keys[self.listening_key]
            if old_char in self.dest_dirs:
                path_val = self.dest_dirs.pop(old_char)
                self.dest_dirs[new_char] = path_val

            self.current_keys[self.listening_key] = new_char
            self.listening_key = None

        elif self.listening_action:
            for s_id, char in self.current_keys.items():
                if char == new_char:
                    messagebox.showwarning("Key in Use", f"Key '{new_char.upper()}' is already assigned to a folder slot.")
                    return
            for a_id, char in self.current_action_keys.items():
                if char == new_char and a_id != self.listening_action:
                    messagebox.showwarning("Key in Use", f"Key '{new_char.upper()}' is already assigned to another action.")
                    return

            self.current_action_keys[self.listening_action] = new_char
            self.listening_action = None
        
        self.rebuild_key_ui()

    def browse_source(self):
        path = filedialog.askdirectory()
        if path:
            path = os.path.normpath(path)
            self.src_entry.delete(0, tk.END)
            self.src_entry.insert(0, path)

    def browse_dest(self, slot_id, entry_widget):
        path = filedialog.askdirectory()
        if path:
            path = os.path.normpath(path)
            bound_char = self.current_keys[slot_id]
            self.dest_dirs[bound_char] = path
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)

    def load_saved_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    
                src_path = config.get("source", "")
                if src_path:
                    src_path = os.path.normpath(src_path)
                    if os.path.exists(src_path):
                        self.src_entry.insert(0, src_path)
                    
                saved_keys = config.get("key_bindings", {})
                if saved_keys:
                    for s_id in self.current_keys:
                        if s_id in saved_keys:
                            self.current_keys[s_id] = saved_keys[s_id].lower()

                saved_action_keys = config.get("action_keys", {})
                if saved_action_keys:
                    for a_id in self.current_action_keys:
                        if a_id in saved_action_keys:
                            self.current_action_keys[a_id] = saved_action_keys[a_id].lower()
                            
                dest_paths = config.get("destinations", {})
                for key, path in dest_paths.items():
                    self.dest_dirs[key] = os.path.normpath(path)
                    
                self.rebuild_key_ui()
            except Exception as e:
                print(f"Failed to load config: {e}")

    def save_config(self, src, dests, key_bindings, action_keys):
        config = {
            "source": os.path.normpath(src),
            "key_bindings": key_bindings,
            "action_keys": action_keys,
            "destinations": {k: os.path.normpath(v) for k, v in dests.items()}
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def clear_config(self):
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all folder paths and key bindings?"):
            self.src_entry.delete(0, tk.END)
            self.dest_dirs.clear()
            self.current_keys = self.default_keys.copy()
            self.current_action_keys = self.default_action_keys.copy()
            self.rebuild_key_ui()
            
            if os.path.exists(CONFIG_FILE):
                try:
                    os.remove(CONFIG_FILE)
                except Exception as e:
                    print(f"Failed to delete config file: {e}")

    def validate_and_start(self):
        src = os.path.normpath(self.src_entry.get().strip())
        if not src or not os.path.exists(src):
            messagebox.showerror("Error", "Please select a valid source folder.")
            return

        self.dest_dirs.clear()
        for slot_id, (entry, _) in self.dest_entries.items():
            val = entry.get().strip()
            bound_char = self.current_keys[slot_id]
            if val:
                self.dest_dirs[bound_char] = os.path.normpath(val)

        self.save_config(src, self.dest_dirs, self.current_keys, self.current_action_keys)
        self.root.destroy()
        
        main_root = tk.Tk()
        MediaSorterApp(main_root, src, self.dest_dirs, self.current_keys, self.current_action_keys)
        main_root.mainloop()

class MediaSorterApp:
    def __init__(self, root, src_folder, dest_dirs, key_bindings, action_keys):
        self.root = root
        self.src_folder = os.path.normpath(src_folder)
        self.dest_dirs = dest_dirs
        self.key_bindings = key_bindings
        self.action_keys = action_keys
        
        valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.mp4', '.webm', '.mov', '.mkv')
        self.media_files = [os.path.normpath(os.path.join(self.src_folder, f)) for f in os.listdir(self.src_folder) 
                            if f.lower().endswith(valid_extensions)]
        
        self.media_files.sort()
        
        self.index = 0
        self.history = []
        self.moved_count = 0
        self.toast_timer = None
        self.anim_job = None
        
        self.cap = None
        self.video_fps = 30
        self.video_job = None
        
        self.zoom_scale = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.raw_pil_image = None
        
        self.root.title("Fast Media Sorter")
        self.root.geometry("1150x800")
        
        self.status_label = tk.Label(root, text="", font=("Arial", 9), bg="#f0f0f0", anchor="w")
        self.status_label.pack(side="top", fill="x", padx=10, pady=(5, 2))
        
        # Clickable Action Bar (Top Toolbar for Mouse Users)
        self.folder_action_bar = tk.Frame(root, bg="#e8e8e8", height=40)
        self.folder_action_bar.pack(side="top", fill="x", padx=10, pady=(0, 5))
        self.folder_action_bar.pack_propagate(False)
        
        # Two-tier responsive bottom container
        self.nav_container = tk.Frame(root, bg="#2b2b2b")
        self.nav_container.pack(side="bottom", fill="x")
        
        # Top row of bottom toolbar (Actions & Counters)
        self.nav_bar_top = tk.Frame(self.nav_container, bg="#2b2b2b", height=40)
        self.nav_bar_top.pack(side="top", fill="x", padx=5, pady=(5, 0))
        self.nav_bar_top.pack_propagate(False)
        
        self.explorer_btn = tk.Button(self.nav_bar_top, text="📂 Open in Explorer", command=self.open_in_explorer, 
                                      bg="#444444", fg="white", font=("Arial", 9), relief="flat", activebackground="#555555", activeforeground="white")
        self.explorer_btn.pack(side="left", padx=5, pady=5)

        self.trash_btn = tk.Button(self.nav_bar_top, text="🗑️ Empty Local Trash", command=self.empty_local_trash, 
                                   bg="#5a2323", fg="white", font=("Arial", 9), relief="flat", activebackground="#7a2e2e", activeforeground="white")
        self.trash_btn.pack(side="left", padx=5, pady=5)

        self.restore_trash_btn = tk.Button(self.nav_bar_top, text="♻️ Restore All", command=self.restore_all_from_trash, 
                                           bg="#3a4a3a", fg="white", font=("Arial", 9), relief="flat", activebackground="#4a5a4a", activeforeground="white")
        self.restore_trash_btn.pack(side="left", padx=5, pady=5)

        self.counter_label = tk.Label(self.nav_bar_top, text="Moved: 0", bg="#2b2b2b", fg="#00FF7F", font=("Arial", 9, "bold"))
        self.counter_label.pack(side="left", padx=10, pady=5)

        # Bottom row of bottom toolbar (Sorting & Jumping)
        self.nav_bar_bottom = tk.Frame(self.nav_container, bg="#2b2b2b", height=40)
        self.nav_bar_bottom.pack(side="top", fill="x", padx=5, pady=(0, 5))
        self.nav_bar_bottom.pack_propagate(False)

        tk.Label(self.nav_bar_bottom, text="Sort by:", bg="#2b2b2b", fg="white", font=("Arial", 9)).pack(side="left", padx=(5, 2), pady=5)
        
        self.sort_var = tk.StringVar(value="Filename (A-Z)")
        self.sort_dropdown = ttk.Combobox(self.nav_bar_bottom, textvariable=self.sort_var, state="readonly", width=16,
                                          values=["Filename (A-Z)", "Date Modified (Newest)", "Date Modified (Oldest)", 
                                                  "File Size (Largest)", "File Size (Smallest)", "File Type"])
        self.sort_dropdown.pack(side="left", padx=5, pady=5)
        
        self.sort_dropdown.bind("<<ComboboxSelected>>", self.on_sort_changed)
        self.root.bind("<Button-1>", self.check_focus_restore, add="+")

        self.jump_label = tk.Label(self.nav_bar_bottom, text="", bg="#2b2b2b", fg="white", font=("Arial", 9, "bold"))
        self.jump_label.pack(side="right", padx=5, pady=5)
        
        self.jump_slider = tk.Scale(self.nav_bar_bottom, from_=1, to=max(1, len(self.media_files)), orient="horizontal", 
                                    command=self.slider_moved, bg="#2b2b2b", fg="white", highlightthickness=0, troughcolor="#444444")
        self.jump_slider.pack(side="right", fill="x", expand=True, padx=5, pady=2)
        
        tk.Label(self.nav_bar_bottom, text="Jump to file:", bg="#2b2b2b", fg="white", font=("Arial", 9)).pack(side="right", padx=5, pady=5)

        self.container = tk.Frame(root, bg="black")
        self.container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 5))
        
        self.canvas = tk.Canvas(self.container, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.focus_set()
        
        self.toast_label = tk.Label(self.container, text="", font=("Arial", 11, "bold"), 
                                    bg="#222222", fg="#00FF7F", padx=10, pady=5)

        self.root.bind('<Key>', self.handle_keypress)
        self.canvas.bind('<MouseWheel>', self.on_zoom)
        self.canvas.bind('<Button-4>', self.on_zoom)
        self.canvas.bind('<Button-5>', self.on_zoom)
        self.canvas.bind('<ButtonPress-1>', self.start_pan)
        self.canvas.bind('<B1-Motion>', self.do_pan)
        self.canvas.bind('<Configure>', self.on_canvas_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Initialize trash counter on start
        self.update_trash_counter()
        self.load_current_media()

    def update_folder_action_bar(self):
        for widget in self.folder_action_bar.winfo_children():
            widget.destroy()

        # Add Nav Buttons & Trash to the top toolbar
        prev_btn = tk.Button(self.folder_action_bar, text="⬅ Prev", bg="#d0d0d0", fg="#222222",
                             font=("Arial", 9, "bold"), relief="raised", padx=6, pady=2,
                             command=lambda: self.navigate(-1))
        prev_btn.pack(side="left", padx=4, pady=6)

        next_btn = tk.Button(self.folder_action_bar, text="Next ➡", bg="#d0d0d0", fg="#222222",
                             font=("Arial", 9, "bold"), relief="raised", padx=6, pady=2,
                             command=lambda: self.navigate(1))
        next_btn.pack(side="left", padx=4, pady=6)

        trash_action_btn = tk.Button(self.folder_action_bar, text="🗑️ Trash", bg="#ffcccc", fg="#880000",
                                     font=("Arial", 9, "bold"), relief="raised", padx=6, pady=2,
                                     command=self.delete_current_file)
        trash_action_btn.pack(side="left", padx=(4, 12), pady=6)

        # Add separator line/frame
        sep = tk.Frame(self.folder_action_bar, width=2, bg="#cccccc")
        sep.pack(side="left", fill="y", padx=2, pady=6)

        mapping_found = False
        for slot_id, k in self.key_bindings.items():
            v = self.dest_dirs.get(k)
            if v:
                mapping_found = True
                folder_name = os.path.basename(v)
                btn_text = f"📁 [{k.upper()}] {folder_name}"
                btn = tk.Button(self.folder_action_bar, text=btn_text, bg="#d0d0d0", fg="#222222", 
                                font=("Arial", 9, "bold"), relief="raised", padx=8, pady=2,
                                command=lambda key_char=k: self.handle_move_action(key_char))
                btn.pack(side="left", padx=4, pady=6)

        if not mapping_found:
            lbl = tk.Label(self.folder_action_bar, text="No destination folders assigned in configuration.", bg="#e8e8e8", fg="gray", font=("Arial", 9, "italic"))
            lbl.pack(side="left", padx=10, pady=8)

    def update_trash_counter(self):
        local_trash_dir = os.path.normpath(os.path.join(self.src_folder, ".trash"))
        count = 0
        if os.path.exists(local_trash_dir):
            try:
                count = len([f for f in os.listdir(local_trash_dir) if os.path.isfile(os.path.join(local_trash_dir, f))])
            except Exception:
                count = 0
        
        if count > 0:
            self.trash_btn.config(text=f"🗑️ Empty Local Trash ({count})")
        else:
            self.trash_btn.config(text="🗑️ Empty Local Trash")

    def check_focus_restore(self, event):
        current_focus = self.root.focus_get()
        if current_focus == self.sort_dropdown and event.widget != self.sort_dropdown:
            self.canvas.focus_set()

    def on_sort_changed(self, event=None):
        if not self.media_files:
            return
            
        current_media_path = self.media_files[self.index] if 0 <= self.index < len(self.media_files) else None
        sort_mode = self.sort_var.get()
        
        if sort_mode == "Filename (A-Z)":
            self.media_files.sort(key=lambda p: os.path.basename(p).lower())
        elif sort_mode == "Date Modified (Newest)":
            self.media_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        elif sort_mode == "Date Modified (Oldest)":
            self.media_files.sort(key=lambda p: os.path.getmtime(p))
        elif sort_mode == "File Size (Largest)":
            self.media_files.sort(key=lambda p: os.path.getsize(p), reverse=True)
        elif sort_mode == "File Size (Smallest)":
            self.media_files.sort(key=lambda p: os.path.getsize(p))
        elif sort_mode == "File Type":
            self.media_files.sort(key=lambda p: (os.path.splitext(p)[1].lower(), os.path.basename(p).lower()))
            
        if current_media_path and current_media_path in self.media_files:
            self.index = self.media_files.index(current_media_path)
        else:
            self.index = 0
            
        self.canvas.focus_set()
        self.show_toast(f"Sorted by: {sort_mode}", color="#00BFFF")
        self.load_current_media()

    def show_toast(self, message, color="#00FF7F"):
        if self.toast_timer:
            self.root.after_cancel(self.toast_timer)
            
        self.toast_label.config(text=message, fg=color)
        self.toast_label.place(relx=0.98, rely=0.95, anchor="se")
        self.toast_timer = self.root.after(1200, lambda: self.toast_label.place_forget())

    def open_in_explorer(self):
        if not (0 <= self.index < len(self.media_files)):
            return
        media_path = os.path.normpath(self.media_files[self.index])
        if os.path.exists(media_path):
            if platform.system() == "Windows":
                subprocess.run(f'explorer /select,"{media_path}"')
            elif platform.system() == "Darwin":
                subprocess.run(['open', '-R', media_path])
            else:
                subprocess.run(['xdg-open', os.path.dirname(media_path)])

    def empty_local_trash(self):
        local_trash_dir = os.path.normpath(os.path.join(self.src_folder, ".trash"))
        if not os.path.exists(local_trash_dir) or not os.listdir(local_trash_dir):
            messagebox.showinfo("Local Trash", "Local trash folder is empty or doesn't exist yet.")
            return
            
        if messagebox.askyesno("Empty Local Trash", "Are you sure you want to permanently delete all items inside the local trash?"):
            try:
                shutil.rmtree(local_trash_dir)
                os.makedirs(local_trash_dir, exist_ok=True)
                self.update_trash_counter()
                self.show_toast("Local Trash Emptied", color="#FF4500")
            except Exception as e:
                messagebox.showerror("Error", f"Could not empty local trash:\n{e}")
        self.canvas.focus_set()

    def restore_all_from_trash(self):
        local_trash_dir = os.path.normpath(os.path.join(self.src_folder, ".trash"))
        if not os.path.exists(local_trash_dir):
            messagebox.showinfo("Restore", "Local trash folder does not exist.")
            return
            
        trash_files = [f for f in os.listdir(local_trash_dir) if os.path.isfile(os.path.join(local_trash_dir, f))]
        if not trash_files:
            messagebox.showinfo("Restore", "Local trash is empty.")
            return

        if messagebox.askyesno("Restore All", f"Are you sure you want to restore all {len(trash_files)} files from the local trash back to the source folder?"):
            try:
                for filename in trash_files:
                    src_file = os.path.normpath(os.path.join(local_trash_dir, filename))
                    dest_file = os.path.normpath(os.path.join(self.src_folder, filename))
                    
                    if os.path.exists(dest_file):
                        base, ext = os.path.splitext(filename)
                        counter = 1
                        while os.path.exists(dest_file):
                            dest_file = os.path.normpath(os.path.join(self.src_folder, f"{base}_restored_{counter}{ext}"))
                            counter += 1
                            
                    shutil.move(src_file, dest_file)
                
                valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.mp4', '.webm', '.mov', '.mkv')
                self.media_files = [os.path.normpath(os.path.join(self.src_folder, f)) for f in os.listdir(self.src_folder) 
                                    if f.lower().endswith(valid_extensions)]
                self.media_files.sort()
                self.index = 0
                
                self.update_trash_counter()
                self.show_toast("Restored all items from trash!", color="#00FF7F")
                self.load_current_media()
            except Exception as e:
                messagebox.showerror("Error", f"Could not restore files:\n{e}")
        self.canvas.focus_set()

    def slider_moved(self, val):
        if not self.media_files:
            return
        target_idx = int(val) - 1
        if 0 <= target_idx < len(self.media_files) and target_idx != self.index:
            self.index = target_idx
            self.load_current_media()

    def reset_view(self):
        self.zoom_scale = 1.0
        self.pan_x = 0
        self.pan_y = 0

    def on_canvas_resize(self, event):
        self.render_media_view()

    def on_zoom(self, event):
        if not self.raw_pil_image:
            return
        
        if event.num == 4 or event.delta > 0:
            factor = 1.15
        elif event.num == 5 or event.delta < 0:
            factor = 0.85
        else:
            return

        new_scale = self.zoom_scale * factor
        if 0.5 <= new_scale <= 10.0:
            self.zoom_scale = new_scale
            self.render_media_view()

    def start_pan(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def do_pan(self, event):
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        self.pan_x += dx
        self.pan_y += dy
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.render_media_view()

    def stop_video_stream(self):
        if self.video_job:
            self.root.after_cancel(self.video_job)
            self.video_job = None
        if self.cap:
            self.cap.release()
            self.cap = None

    def load_current_media(self):
        if self.anim_job:
            self.root.after_cancel(self.anim_job)
            self.anim_job = None
        self.stop_video_stream()

        self.reset_view()
        self.update_folder_action_bar()

        if 0 <= self.index < len(self.media_files):
            media_path = self.media_files[self.index]
            filename = os.path.basename(media_path)
            ext = os.path.splitext(filename)[1].lower()
            
            skip_key_display = self.action_keys.get('skip', 'space').upper()
            self.status_label.config(text=f"[{self.index + 1}/{len(self.media_files)}] {filename} | [{skip_key_display}: Skip] | [Delete: Move to Local Trash]")
            
            self.jump_slider.config(to=max(1, len(self.media_files)))
            self.jump_slider.set(self.index + 1)
            self.jump_label.config(text=f"{self.index + 1} / {len(self.media_files)}")
            
            try:
                video_extensions = ('.mp4', '.webm', '.mov', '.mkv')
                if ext in video_extensions:
                    self.cap = cv2.VideoCapture(media_path)
                    fps = self.cap.get(cv2.CAP_PROP_FPS)
                    if fps > 0 and fps <= 60:
                        self.video_fps = fps
                    else:
                        self.video_fps = 30
                    self.play_video_frame()
                else:
                    self.raw_pil_image = Image.open(media_path)
                    
                    if getattr(self.raw_pil_image, "is_animated", False):
                        self.gif_frames = []
                        try:
                            while True:
                                self.gif_frames.append(self.raw_pil_image.copy())
                                self.raw_pil_image.seek(len(self.gif_frames))
                        except EOFError:
                            pass
                        
                        self.frame_idx = 0
                        self.animate_gif()
                    else:
                        self.gif_frames = None
                        self.render_media_view()
            except Exception as e:
                self.canvas.delete("all")
                self.canvas.create_text(self.canvas.winfo_width()//2, self.canvas.winfo_height()//2, 
                                        text=f"Error loading media:\n{e}", fill="white", font=("Arial", 12))
                
        elif self.index >= len(self.media_files):
            undo_key_display = self.action_keys.get('undo', 'backspace').upper()
            self.status_label.config(text=f"Sorting Complete! (Use Left Arrow to review or {undo_key_display} to undo)")
            self.canvas.delete("all")
            self.canvas.create_text(self.canvas.winfo_width()//2, self.canvas.winfo_height()//2, 
                                    text="All media processed!", fill="white", font=("Arial", 16))
            self.toast_label.place_forget()
            self.jump_slider.config(to=1)
            self.jump_label.config(text="0 / 0")
        else:
            self.index = 0
            self.load_current_media()

    def play_video_frame(self):
        if not self.cap or not self.cap.isOpened():
            return
            
        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if not ret:
                return
                
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.raw_pil_image = Image.fromarray(frame_rgb)
        self.render_media_view()
        
        delay_ms = int(1000 / self.video_fps)
        self.video_job = self.root.after(delay_ms, self.play_video_frame)

    def animate_gif(self):
        if not self.gif_frames:
            return
        self.raw_pil_image = self.gif_frames[self.frame_idx]
        self.render_media_view()
        self.frame_idx = (self.frame_idx + 1) % len(self.gif_frames)
        self.anim_job = self.root.after(100, self.animate_gif)

    def render_media_view(self):
        if not self.raw_pil_image:
            return

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            cw, ch = 850, 520

        iw, ih = self.raw_pil_image.size
        
        fit_scale = min(cw / iw, ch / ih)
        final_scale = fit_scale * self.zoom_scale

        target_w = max(1, int(iw * final_scale))
        target_h = max(1, int(ih * final_scale))

        resized_img = self.raw_pil_image.resize((target_w, target_h), Image.Resampling.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(resized_img)

        x = (cw // 2) + self.pan_x
        y = (ch // 2) + self.pan_y

        self.canvas.delete("all")
        self.canvas.create_image(x, y, anchor="center", image=self.tk_img)

    def handle_keypress(self, event):
        if isinstance(self.root.focus_get(), ttk.Combobox):
            return
            
        key = event.keysym.lower()
        active_bound_keys = list(self.dest_dirs.keys())
        
        skip_key = self.action_keys.get('skip', 'space').lower()
        undo_key = self.action_keys.get('undo', 'backspace').lower()
        
        if key == skip_key:
            self.skip_action()
        elif key == undo_key:
            self.undo_last_action()
        elif key in ['delete', 'backspace'] and event.keysym.lower() == 'delete':
            self.delete_current_file()
        elif key in active_bound_keys:
            self.handle_move_action(key)
        elif key == 'left':
            self.navigate(-1)
        elif key == 'right':
            self.navigate(1)

    def handle_move_action(self, key):
        if not (0 <= self.index < len(self.media_files)):
            return
            
        self.stop_video_stream()
        current_media_path = os.path.normpath(self.media_files[self.index])
        target_folder = self.dest_dirs.get(key)
        
        if target_folder:
            target_folder = os.path.normpath(target_folder)
            os.makedirs(target_folder, exist_ok=True)
            folder_name = os.path.basename(target_folder)
            dest_path = os.path.normpath(os.path.join(target_folder, os.path.basename(current_media_path)))
            
            shutil.move(current_media_path, dest_path)
            self.history.append((current_media_path, self.index, dest_path, 'move'))
            self.media_files.pop(self.index)
            
            self.moved_count += 1
            self.counter_label.config(text=f"Moved: {self.moved_count}")
            
            if self.index >= len(self.media_files) and self.index > 0:
                self.index = len(self.media_files) - 1
                
            self.show_toast(f"Moved to [{key.upper()}]: {folder_name}", color="#00FF7F")
            self.load_current_media()

    def delete_current_file(self):
        if not (0 <= self.index < len(self.media_files)):
            return

        self.stop_video_stream()
        current_media_path = os.path.normpath(self.media_files[self.index])

        try:
            local_trash_dir = os.path.normpath(os.path.join(self.src_folder, ".trash"))
            os.makedirs(local_trash_dir, exist_ok=True)
            
            dest_path = os.path.normpath(os.path.join(local_trash_dir, os.path.basename(current_media_path)))
            
            base, ext = os.path.splitext(os.path.basename(current_media_path))
            counter = 1
            while os.path.exists(dest_path):
                dest_path = os.path.normpath(os.path.join(local_trash_dir, f"{base}_{counter}{ext}"))
                counter += 1

            shutil.move(current_media_path, dest_path)

            self.history.append((current_media_path, self.index, dest_path, 'delete'))
            self.media_files.pop(self.index)

            if self.index >= len(self.media_files) and self.index > 0:
                self.index = len(self.media_files) - 1

            self.update_trash_counter()
            self.show_toast("Moved to Local Trash (Undoable)", color="#FF4500")
            self.load_current_media()
        except Exception as e:
            messagebox.showerror("Error", f"Could not move file to local trash:\n{e}")

    def skip_action(self):
        if len(self.media_files) == 0:
            return
        self.stop_video_stream()
        self.index = (self.index + 1) % len(self.media_files)
        self.show_toast("Skipped", color="#FFD700")
        self.load_current_media()

    def navigate(self, direction):
        if len(self.media_files) == 0:
            return
        self.stop_video_stream()
        self.index = (self.index + direction) % len(self.media_files)
        self.load_current_media()

    def undo_last_action(self):
        if not self.history:
            return
            
        self.stop_video_stream()
        last_record = self.history.pop()
        
        if len(last_record) == 4:
            last_media_path, old_index, target_path, action_type = last_record
        else:
            last_media_path, old_index, target_path = last_record
            action_type = 'move'

        if action_type in ['move', 'delete']:
            if target_path and os.path.exists(target_path):
                restored_path = os.path.normpath(os.path.join(self.src_folder, os.path.basename(last_media_path)))
                
                if os.path.exists(restored_path):
                    base, ext = os.path.splitext(os.path.basename(last_media_path))
                    counter = 1
                    while os.path.exists(restored_path):
                        restored_path = os.path.normpath(os.path.join(self.src_folder, f"{base}_restored_{counter}{ext}"))
                        counter += 1

                shutil.move(target_path, restored_path)
                
                self.media_files.insert(old_index, restored_path)
                self.index = old_index
                
                if action_type == 'move':
                    self.moved_count = max(0, self.moved_count - 1)
                    self.counter_label.config(text=f"Moved: {self.moved_count}")
                    self.show_toast("Undo Move", color="#00BFFF")
                else:
                    self.update_trash_counter()
                    self.show_toast("Undo Delete (Restored)", color="#00FF7F")
                    
                self.load_current_media()

    def on_close(self):
        self.stop_video_stream()
        self.root.destroy()

if __name__ == "__main__":
    setup_root = tk.Tk()
    SetupDialog(setup_root)
    setup_root.mainloop()