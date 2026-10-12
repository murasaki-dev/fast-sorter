import os
import sys
import json
import shutil
import subprocess
import platform
import ctypes
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

def set_window_title_bar_theme(root, is_dark):
    """Enables or disables native dark mode on the Windows title bar."""
    if platform.system() != "Windows":
        return
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        if not hwnd:
            hwnd = root.winfo_id()
        
        for attribute in (20, 19):
            value = ctypes.c_int(1 if is_dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                attribute,
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
    except Exception as e:
        print(f"Failed to set title bar theme: {e}")

class ToolTip:
    """Helper class to create lightweight hover tooltips for Tkinter widgets."""
    active_tooltips = []

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.schedule)
        self.widget.bind("<Leave>", self.hide)
        self.widget.bind("<ButtonPress>", self.hide)
        
        try:
            top_root = self.widget.winfo_toplevel()
            top_root.bind("<Button-1>", lambda e: ToolTip.hide_all(), add="+")
        except Exception:
            pass

    @classmethod
    def hide_all(cls):
        """Hides and destroys all active tooltips globally."""
        for t in cls.active_tooltips:
            t._force_hide()
        cls.active_tooltips.clear()

    def schedule(self, event=None):
        self.unschedule()
        self.id = self.widget.after(500, self.show)

    def unschedule(self):
        id_val = self.id
        self.id = None
        if id_val:
            try:
                self.widget.after_cancel(id_val)
            except Exception:
                pass

    def show(self, event=None):
        if self.tip_window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            label = tk.Label(tw, text=self.text, background="#ffffe0", foreground="#000000",
                             relief="solid", borderwidth=1, font=("Arial", 8), padx=4, pady=2)
            label.pack(ipadx=1)
            if self not in ToolTip.active_tooltips:
                ToolTip.active_tooltips.append(self)
        except Exception:
            pass

    def _force_hide(self):
        self.unschedule()
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None

    def hide(self, event=None):
        self.unschedule()
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None
        if self in ToolTip.active_tooltips:
            ToolTip.active_tooltips.remove(self)

class SetupDialog:
    def __init__(self, root):
        self.root = root
        self.root.title("Fast Media Sorter - Configuration")
        self.root.geometry("620x980")
        
        self.source_dir = ""
        self.dest_dirs = {}
        self.dest_entries = {}
        self.key_buttons = {}
        self.action_key_buttons = {}
        self.listening_key = None
        self.listening_action = None
        
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
            'undo': 'backspace',
            'temp': 'e',
            'pick_temp': 'q',
            'details': 'p',
            'delete': 'delete'
        }
        self.current_keys = self.default_keys.copy()
        self.current_action_keys = self.default_action_keys.copy()
        
        self.dark_mode_var = tk.BooleanVar(value=False)
        self.collision_mode_var = tk.StringVar(value="append")
        
        self.lbl_src = tk.Label(root, text="Unsorted Media Folder:", font=("Arial", 10, "bold"))
        self.lbl_src.pack(anchor="w", padx=20, pady=(15, 0))
        
        self.src_frame = tk.Frame(root)
        self.src_frame.pack(fill="x", padx=20, pady=5)
        
        self.src_entry = tk.Entry(self.src_frame, width=45, relief="solid", bd=1)
        self.src_entry.pack(side="left", padx=(0, 5), fill="x", expand=True)
        self.src_browse_btn = tk.Button(self.src_frame, text="Browse Source", command=self.browse_source, relief="flat", bd=0)
        self.src_browse_btn.pack(side="left")
        ToolTip(self.src_browse_btn, "Select the folder containing unsorted media files")
        
        self.lbl_dest = tk.Label(root, text="Assign Folders & Rebind Folder Keys (Click button to change key):", font=("Arial", 10, "bold"))
        self.lbl_dest.pack(anchor="w", padx=20, pady=(15, 0))
        
        self.folder_rows_frame = tk.Frame(root)
        self.folder_rows_frame.pack(fill="x", padx=20, pady=5)

        self.lbl_action = tk.Label(root, text="Action Keys Rebinding:", font=("Arial", 10, "bold"))
        self.lbl_action.pack(anchor="w", padx=20, pady=(10, 0))
        
        self.action_rows_frame = tk.Frame(root)
        self.action_rows_frame.pack(fill="x", padx=20, pady=5)

        self.rebuild_key_ui()

        self.theme_frame = tk.Frame(root)
        self.theme_frame.pack(fill="x", padx=20, pady=10)
        
        self.dark_mode_chk = tk.Checkbutton(self.theme_frame, text="Enable Dark Mode", variable=self.dark_mode_var, font=("Arial", 10, "bold"), command=self.apply_theme)
        self.dark_mode_chk.pack(anchor="w", pady=(0, 5))

        self.collision_config_frame = tk.Frame(self.theme_frame)
        self.collision_config_frame.pack(anchor="w", fill="x", pady=5)
        
        self.config_collision_lbl = tk.Label(self.collision_config_frame, text="Filename Conflict:", font=("Arial", 10, "bold"))
        self.config_collision_lbl.pack(side="left", padx=(0, 10))
        
        self.config_collision_dropdown = ttk.Combobox(self.collision_config_frame, textvariable=self.collision_mode_var, state="readonly", width=12, values=["append", "replace"])
        self.config_collision_dropdown.pack(side="left")
        ToolTip(self.config_collision_dropdown, "Choose how to handle filename conflicts when moving files:\n• append: Adds a suffix number if file exists\n• replace: Overwrites existing file")

        self.lbl_hints = tk.Label(root, text="* Mouse Wheel = Zoom | Left-click Drag = Pan\n* Press [Escape] while rebinding a key to cancel", 
                                  fg="gray", font=("Arial", 9), justify="left")
        self.lbl_hints.pack(pady=5)
        
        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(pady=10)

        self.start_btn = tk.Button(self.btn_frame, text="Start Sorting", bg="#28a745", fg="white", font=("Arial", 11, "bold"), 
                                   padx=15, pady=5, relief="flat", bd=0, command=self.validate_and_start)
        self.start_btn.pack(side="left", padx=10)
        ToolTip(self.start_btn, "Save configuration and launch the sorter interface")
        
        self.clear_btn = tk.Button(self.btn_frame, text="Clear Saved Folders", bg="#dc3545", fg="white", font=("Arial", 10), 
                                   padx=10, pady=5, relief="flat", bd=0, command=self.clear_config)
        self.clear_btn.pack(side="left", padx=10)
        ToolTip(self.clear_btn, "Clear all saved folder assignments and custom key bindings")

        self.load_saved_config()
        self.apply_theme()
        self.root.bind("<Key>", self.handle_key_listen)

    def apply_theme(self):
        is_dark = self.dark_mode_var.get()
        set_window_title_bar_theme(self.root, is_dark)
        
        bg_color = "#121212" if is_dark else "#f0f0f0"
        fg_color = "#ffffff" if is_dark else "#000000"
        frame_bg = "#1e1e1e" if is_dark else "#f0f0f0"
        widget_bg = "#252526" if is_dark else "#ffffff"
        widget_fg = "#ffffff" if is_dark else "#000000"
        btn_bg = "#333333" if is_dark else "#e0e0e0"
        
        self.root.config(bg=bg_color)
        for parent_frame in [self.src_frame, self.folder_rows_frame, self.action_rows_frame, self.theme_frame, self.collision_config_frame, self.btn_frame]:
            parent_frame.config(bg=bg_color)

        for parent_frame in [self.folder_rows_frame, self.action_rows_frame]:
            for child in parent_frame.winfo_children():
                try:
                    child.config(bg=frame_bg)
                    for sub in child.winfo_children():
                        if isinstance(sub, tk.Label):
                            sub.config(bg=frame_bg, fg=fg_color)
                        elif isinstance(sub, tk.Entry):
                            sub.config(bg=widget_bg, fg=widget_fg, insertbackground=widget_fg, relief="solid", bd=1)
                        elif isinstance(sub, tk.Button):
                            if sub["bg"] not in ["#28a745", "#dc3545", "#ffc107", "#ff4d4d"]:
                                sub.config(bg=btn_bg, fg=fg_color, activebackground="#444444" if is_dark else "#d0d0d0", activeforeground=fg_color, relief="flat", bd=0)
                except Exception:
                    pass

        for lbl in [self.lbl_src, self.lbl_dest, self.lbl_action, self.config_collision_lbl, self.lbl_hints]:
            lbl.config(bg=bg_color, fg=fg_color)
            
        self.dark_mode_chk.config(bg=bg_color, fg=fg_color, activebackground=bg_color, activeforeground=fg_color, selectcolor="#333333" if is_dark else "#ffffff")
        self.src_entry.config(bg=widget_bg, fg=widget_fg, insertbackground=widget_fg, relief="solid", bd=1)
        self.src_browse_btn.config(bg=btn_bg, fg=fg_color, activebackground="#444444" if is_dark else "#d0d0d0", activeforeground=fg_color, relief="flat", bd=0)
        self.start_btn.config(bg="#28a745", fg="white", activebackground="#218838", activeforeground="white", relief="flat", bd=0)
        self.clear_btn.config(bg="#dc3545", fg="white", activebackground="#c82333", activeforeground="white", relief="flat", bd=0)
        self.highlight_conflicts()

    def rebuild_key_ui(self):
        for widget in self.folder_rows_frame.winfo_children():
            widget.destroy()
        for widget in self.action_rows_frame.winfo_children():
            widget.destroy()
            
        self.dest_entries.clear()
        self.key_buttons.clear()
        self.action_key_buttons.clear()

        is_dark = self.dark_mode_var.get()
        frame_bg = "#1e1e1e" if is_dark else "#f0f0f0"
        fg_color = "#ffffff" if is_dark else "#000000"
        widget_bg = "#252526" if is_dark else "#ffffff"

        for i in range(8):
            slot_id = f"slot_{i}"
            current_bind = self.current_keys[slot_id].upper()
            
            frame = tk.Frame(self.folder_rows_frame, bg=frame_bg)
            frame.pack(fill="x", pady=2)
            
            key_btn = tk.Button(frame, text=f"[{current_bind}]", width=12, bg="#333333" if is_dark else "#e0e0e0", fg=fg_color, relief="flat", bd=0,
                                command=lambda s=slot_id: self.start_listening_slot(s))
            key_btn.pack(side="left")
            ToolTip(key_btn, "Click to rebind shortcut key")
            self.key_buttons[slot_id] = key_btn
            
            entry = tk.Entry(frame, width=45, bg=widget_bg, fg=fg_color, insertbackground=fg_color, relief="solid", bd=1)
            entry.pack(side="left", padx=5, fill="x", expand=True)
            
            bound_key_char = self.current_keys[slot_id]
            if bound_key_char in self.dest_dirs:
                entry.insert(0, self.dest_dirs[bound_key_char])
                
            btn = tk.Button(frame, text="Browse", bg="#333333" if is_dark else "#e0e0e0", fg=fg_color, relief="flat", bd=0, command=lambda s=slot_id, e=entry: self.browse_dest(s, e))
            btn.pack(side="left")
            ToolTip(btn, "Browse and select destination folder path")
            self.dest_entries[slot_id] = (entry, btn)

        actions = [
            ('skip', 'Skip Media'), 
            ('undo', 'Undo Last Move'),
            ('temp', 'Send to Temp Folder'),
            ('pick_temp', 'Pick New Temp & Send'),
            ('details', 'Toggle Details Panel'),
            ('delete', 'Move to Trash')
        ]
        for action_id, action_label in actions:
            current_bind = self.current_action_keys[action_id].upper()
            
            frame = tk.Frame(self.action_rows_frame, bg=frame_bg)
            frame.pack(fill="x", pady=2)
            
            key_btn = tk.Button(frame, text=f"[{current_bind}]", width=12, bg="#333333" if is_dark else "#e0e0e0", fg=fg_color, relief="flat", bd=0,
                                command=lambda a=action_id: self.start_listening_action(a))
            key_btn.pack(side="left")
            ToolTip(key_btn, "Click to rebind action shortcut key")
            self.action_key_buttons[action_id] = key_btn
            
            lbl = tk.Label(frame, text=action_label, font=("Arial", 9), bg=frame_bg, fg=fg_color)
            lbl.pack(side="left", padx=10)

        self.highlight_conflicts()

    def highlight_conflicts(self):
        """Scans all active key bindings and highlights conflicting buttons in red."""
        all_keys = list(self.current_keys.values()) + list(self.current_action_keys.values())
        duplicates = {k for k in all_keys if all_keys.count(k) > 1}

        is_dark = self.dark_mode_var.get()
        default_bg = "#333333" if is_dark else "#e0e0e0"

        for s_id, btn in self.key_buttons.items():
            char = self.current_keys[s_id]
            if char in duplicates:
                btn.config(bg="#ff4d4d", fg="white")
            else:
                btn.config(bg=default_bg, fg="#ffffff" if is_dark else "#000000")

        for a_id, btn in self.action_key_buttons.items():
            char = self.current_action_keys[a_id]
            if char in duplicates:
                btn.config(bg="#ff4d4d", fg="white")
            else:
                btn.config(bg=default_bg, fg="#ffffff" if is_dark else "#000000")

    def start_listening_slot(self, slot_id):
        self.listening_key = slot_id
        self.listening_action = None
        is_dark = self.dark_mode_var.get()
        default_bg = "#333333" if is_dark else "#e0e0e0"
        for s_id, btn in self.key_buttons.items():
            if s_id == slot_id:
                btn.config(text="Press any key...", bg="#ffc107", fg="black")
            else:
                btn.config(relief="flat", bg=default_bg)
        for a_id, btn in self.action_key_buttons.items():
            btn.config(relief="flat", bg=default_bg)

    def start_listening_action(self, action_id):
        self.listening_action = action_id
        self.listening_key = None
        is_dark = self.dark_mode_var.get()
        default_bg = "#333333" if is_dark else "#e0e0e0"
        for a_id, btn in self.action_key_buttons.items():
            if a_id == action_id:
                btn.config(text="Press any key...", bg="#ffc107", fg="black")
            else:
                btn.config(relief="flat", bg=default_bg)
        for s_id, btn in self.key_buttons.items():
            btn.config(relief="flat", bg=default_bg)

    def handle_key_listen(self, event):
        if not self.listening_key and not self.listening_action:
            return
            
        if event.keysym.lower() == 'escape':
            self.listening_key = None
            self.listening_action = None
            self.rebuild_key_ui()
            return

        if event.keysym.lower() in ['shift_l', 'shift_r', 'control_l', 'control_r', 'alt_l', 'alt_r', 'caps_lock']:
            return
            
        new_char = event.keysym.lower()
        reserved_keys = ['return', 'escape']
        if new_char in reserved_keys:
            return

        has_conflict = False
        conflict_msg = ""

        if self.listening_key:
            for s_id, char in self.current_keys.items():
                if char == new_char and s_id != self.listening_key:
                    has_conflict = True
                    conflict_msg = f"Key '{new_char.upper()}' is already assigned to another folder slot."
            for a_id, char in self.current_action_keys.items():
                if char == new_char:
                    has_conflict = True
                    conflict_msg = f"Key '{new_char.upper()}' is already assigned to action '{a_id.capitalize()}."

            if has_conflict:
                if not messagebox.askyesno("Key Conflict Warning", f"{conflict_msg}\n\nDo you want to assign it anyway? (Conflicting buttons will be highlighted in red)"):
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
                    has_conflict = True
                    conflict_msg = f"Key '{new_char.upper()}' is already assigned to a folder slot."
            for a_id, char in self.current_action_keys.items():
                if char == new_char and a_id != self.listening_action:
                    has_conflict = True
                    conflict_msg = f"Key '{new_char.upper()}' is already assigned to another action."

            if has_conflict:
                if not messagebox.askyesno("Key Conflict Warning", f"{conflict_msg}\n\nDo you want to assign it anyway? (Conflicting buttons will be highlighted in red)"):
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

                self.dark_mode_var.set(config.get("dark_mode", False))
                self.collision_mode_var.set(config.get("collision_mode", "append"))
                self.apply_theme()
                    
                self.rebuild_key_ui()
            except Exception as e:
                print(f"Failed to load config: {e}")

    def save_config(self, src, dests, key_bindings, action_keys, dark_mode, collision_mode):
        config = {
            "source": os.path.normpath(src),
            "key_bindings": key_bindings,
            "action_keys": action_keys,
            "destinations": {k: os.path.normpath(v) for k, v in dests.items()},
            "dark_mode": dark_mode,
            "collision_mode": collision_mode
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
            self.dark_mode_var.set(False)
            self.collision_mode_var.set("append")
            self.apply_theme()
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

        ToolTip.hide_all()
        self.save_config(src, self.dest_dirs, self.current_keys, self.current_action_keys, self.dark_mode_var.get(), self.collision_mode_var.get())
        self.root.destroy()
        
        main_root = tk.Tk()
        MediaSorterApp(main_root, src, self.dest_dirs, self.current_keys, self.current_action_keys, self.dark_mode_var.get(), self.collision_mode_var.get())
        main_root.mainloop()

class MediaSorterApp:
    def __init__(self, root, src_folder, dest_dirs, key_bindings, action_keys, dark_mode=False, collision_mode="append"):
        self.root = root
        self.src_folder = os.path.normpath(src_folder)
        self.dest_dirs = dest_dirs
        self.key_bindings = key_bindings
        self.action_keys = action_keys
        self.dark_mode = dark_mode
        self.collision_mode = collision_mode
        
        initial_main_bg = "#121212" if self.dark_mode else "#f0f0f0"
        self.root.config(bg=initial_main_bg)
        set_window_title_bar_theme(self.root, self.dark_mode)

        valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.mp4', '.webm', '.mov', '.mkv')
        self.media_files = [os.path.normpath(os.path.join(self.src_folder, f)) for f in os.listdir(self.src_folder) 
                            if f.lower().endswith(valid_extensions)]
        
        self.media_files.sort()
        
        self.index = 0
        self.history = []
        self.moved_count = 0
        self.toast_timer = None
        self.anim_job = None
        self.last_temp_folder = None
        
        self.pressed_keys = set()
        
        self.scroll_job = None
        self.scroll_direction = 0
        self.scroll_start_time = 0
        
        self.cap = None
        self.video_fps = 30
        self.video_job = None
        
        self.zoom_scale = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.raw_pil_image = None
        self.show_details_panel = True
        
        self.root.title("Fast Media Sorter")
        self.root.geometry("1150x800")
        
        self.nav_container = tk.Frame(root)
        self.nav_container.pack(side="bottom", fill="x")
        
        self.nav_bar_top = tk.Frame(self.nav_container, height=40)
        self.nav_bar_top.pack(side="top", fill="x", padx=5, pady=(5, 0))
        self.nav_bar_top.pack_propagate(False)

        self.open_file_btn = tk.Button(self.nav_bar_top, text="📄 Open File", command=self.open_current_file, 
                                       font=("Arial", 9), relief="flat", bd=0)
        self.open_file_btn.pack(side="left", padx=5, pady=5)
        ToolTip(self.open_file_btn, "Open current media file with the operating system's default application")
        
        self.explorer_btn = tk.Button(self.nav_bar_top, text="📂 Open in Explorer", command=self.open_in_explorer, 
                                      font=("Arial", 9), relief="flat", bd=0)
        self.explorer_btn.pack(side="left", padx=5, pady=5)
        ToolTip(self.explorer_btn, "Reveal current media file in system file explorer")

        self.trash_btn = tk.Button(self.nav_bar_top, text="🗑 Empty Trashbin", command=self.empty_local_trash, 
                                   font=("Segoe UI Symbol", 9, "bold"), relief="flat", bd=0, padx=6)
        self.trash_btn.pack(side="left", padx=5, pady=5)
        ToolTip(self.trash_btn, "Permanently delete files stored inside the local .trash folder")

        self.restore_trash_btn = tk.Button(self.nav_bar_top, text="♻ Restore All", command=self.restore_all_from_trash, 
                                           font=("Arial", 9), relief="flat", bd=0)
        self.restore_trash_btn.pack(side="left", padx=5, pady=5)
        ToolTip(self.restore_trash_btn, "Restore all files from local trash back to source folder")

        self.counter_label = tk.Label(self.nav_bar_top, text="Moved: 0", font=("Arial", 9, "bold"))
        self.counter_label.pack(side="left", padx=10, pady=5)

        self.config_btn = tk.Button(self.nav_bar_top, text="⚙ Config", command=self.return_to_config,
                                    font=("Arial", 9, "bold"), relief="flat", bd=0, padx=8, pady=2)
        self.config_btn.pack(side="right", padx=(5, 5), pady=5)
        ToolTip(self.config_btn, "Return to configuration window")

        self.dark_mode_var = tk.BooleanVar(value=self.dark_mode)
        self.footer_dark_chk = tk.Checkbutton(self.nav_bar_top, text="Dark Mode", variable=self.dark_mode_var, 
                                              command=self.toggle_dark_mode)
        self.footer_dark_chk.pack(side="right", padx=5, pady=5)
        ToolTip(self.footer_dark_chk, "Toggle application dark mode")

        self.collision_var = tk.StringVar(value=self.collision_mode)
        self.collision_dropdown = ttk.Combobox(self.nav_bar_top, textvariable=self.collision_var, state="readonly", width=10,
                                               values=["append", "replace"])
        self.collision_dropdown.bind("<<ComboboxSelected>>", self.on_collision_changed)
        ToolTip(self.collision_dropdown, "Filename Conflict Resolution Mode:\n• append: Automatically adds a number suffix if a file with the same name exists\n• replace: Overwrites the existing file in the destination folder")
        self.collision_dropdown.pack(side="right", padx=5, pady=5)

        self.collision_lbl = tk.Label(self.nav_bar_top, text="Filename Conflict:", font=("Arial", 9, "bold"))
        self.collision_lbl.pack(side="right", padx=(10, 2), pady=5)

        self.nav_bar_bottom = tk.Frame(self.nav_container, height=40)
        self.nav_bar_bottom.pack(side="top", fill="x", padx=5, pady=(0, 5))
        self.nav_bar_bottom.pack_propagate(False)

        self.sort_label = tk.Label(self.nav_bar_bottom, text="Sort by:", font=("Arial", 9))
        self.sort_label.pack(side="left", padx=(5, 2), pady=5)
        
        self.sort_var = tk.StringVar(value="Filename (A-Z)")
        self.sort_dropdown = ttk.Combobox(self.nav_bar_bottom, textvariable=self.sort_var, state="readonly", width=16,
                                          values=["Filename (A-Z)", "Date Modified (Newest)", "Date Modified (Oldest)", 
                                                  "File Size (Largest)", "File Size (Smallest)", "File Type"])
        self.sort_dropdown.pack(side="left", padx=5, pady=5)
        
        self.sort_dropdown.bind("<<ComboboxSelected>>", self.on_sort_changed)
        self.root.bind("<Button-1>", self.check_focus_restore, add="+")

        self.jump_label = tk.Label(self.nav_bar_bottom, text="", font=("Arial", 9, "bold"))
        self.jump_label.pack(side="right", padx=5, pady=5)
        
        self.jump_slider = tk.Scale(self.nav_bar_bottom, from_=1, to=max(1, len(self.media_files)), orient="horizontal", 
                                    command=self.slider_moved, highlightthickness=0)
        self.jump_slider.pack(side="right", fill="x", expand=True, padx=5, pady=2)
        ToolTip(self.jump_slider, "Drag slider to quickly jump between media items")
        
        self.jump_title_lbl = tk.Label(self.nav_bar_bottom, text="Jump to file:", font=("Arial", 9))
        self.jump_title_lbl.pack(side="right", padx=5, pady=5)

        self.folder_action_bar = tk.Frame(root, height=40)
        self.folder_action_bar.pack(side="top", fill="x", padx=10, pady=(5, 5))
        self.folder_action_bar.pack_propagate(False)
        
        self.folder_shortcut_buttons = {}
        self.init_folder_action_bar_widgets()

        self.container = tk.Frame(root)
        self.container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 5))
        
        self.canvas = tk.Canvas(self.container, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.focus_set()
        
        self.details_panel = tk.Frame(self.container, relief="solid", bd=1, width=280)
        self.details_panel.pack_propagate(False)
        
        self.details_title_lbl = tk.Label(self.details_panel, text="📋 File Details", font=("Arial", 9, "bold"))
        self.details_title_lbl.pack(anchor="w", padx=10, pady=(8, 4))

        self.details_text_widget = tk.Text(self.details_panel, font=("Consolas", 9), 
                                           relief="flat", wrap="word", highlightthickness=0, bd=0)
        self.details_text_widget.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.details_text_widget.config(state="disabled")

        if self.show_details_panel:
            self.details_panel.place(x=10, y=10)

        self.toast_label = tk.Label(self.container, text="", font=("Arial", 11, "bold"), padx=10, pady=5)

        self.root.bind('<Key>', self.handle_keypress)
        self.root.bind('<KeyRelease>', self.handle_keyrelease)
        self.canvas.bind('<MouseWheel>', self.on_zoom)
        self.canvas.bind('<Button-4>', self.on_zoom)
        self.canvas.bind('<Button-5>', self.on_zoom)
        self.canvas.bind('<ButtonPress-1>', self.start_pan)
        self.canvas.bind('<B1-Motion>', self.do_pan)
        self.canvas.bind('<Configure>', self.on_canvas_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.update_trash_counter()
        self.apply_theme_colors()
        self.load_current_media()

    def return_to_config(self):
        """Saves configuration and switches back to the SetupDialog window."""
        ToolTip.hide_all()
        self.stop_video_stream()
        self.save_current_config_to_file()
        self.root.destroy()
        
        setup_root = tk.Tk()
        SetupDialog(setup_root)
        setup_root.mainloop()

    def toggle_dark_mode(self):
        self.dark_mode = self.dark_mode_var.get()
        self.apply_theme_colors()
        self.save_current_config_to_file()

    def on_collision_changed(self, event=None):
        self.collision_mode = self.collision_var.get()
        self.save_current_config_to_file()

    def save_current_config_to_file(self):
        config = {
            "source": self.src_folder,
            "key_bindings": self.key_bindings,
            "action_keys": self.action_keys,
            "destinations": {k: os.path.normpath(v) for k, v in self.dest_dirs.items()},
            "dark_mode": self.dark_mode,
            "collision_mode": self.collision_mode
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def apply_theme_colors(self):
        is_dark = self.dark_mode
        set_window_title_bar_theme(self.root, is_dark)
        
        main_bg = "#121212" if is_dark else "#f0f0f0"
        bar_bg = "#1e1e1e" if is_dark else "#e8e8e8"
        container_bg = "#181818" if is_dark else "#e8e8e8"
        canvas_bg = "#121212" if is_dark else "#808080"
        fg_color = "#ffffff" if is_dark else "#222222"
        btn_bg = "#333333" if is_dark else "#d0d0d0"
        
        self.root.config(bg=main_bg)
        self.container.config(bg=canvas_bg)
        self.canvas.config(bg=canvas_bg)
        self.folder_action_bar.config(bg=bar_bg)
        self.nav_container.config(bg=container_bg)
        self.nav_bar_top.config(bg=container_bg)
        self.nav_bar_bottom.config(bg=container_bg)
        
        self.counter_label.config(bg=container_bg, fg="#008000" if not is_dark else "#00FF7F")
        self.sort_label.config(bg=container_bg, fg=fg_color)
        self.collision_lbl.config(bg=container_bg, fg=fg_color)
        self.jump_title_lbl.config(bg=container_bg, fg=fg_color)
        self.jump_label.config(bg=container_bg, fg=fg_color)
        self.jump_slider.config(bg=container_bg, fg=fg_color, troughcolor="#333333" if is_dark else "#bbbbbb")
        self.footer_dark_chk.config(bg=container_bg, fg=fg_color, activebackground=container_bg, activeforeground=fg_color, selectcolor="#333333" if is_dark else "#ffffff")

        self.open_file_btn.config(bg=btn_bg, fg=fg_color, activebackground="#444444" if is_dark else "#c0c0c0", activeforeground=fg_color, relief="flat", bd=0)
        self.explorer_btn.config(bg=btn_bg, fg=fg_color, activebackground="#444444" if is_dark else "#c0c0c0", activeforeground=fg_color, relief="flat", bd=0)
        self.trash_btn.config(bg="#5a2323" if is_dark else "#d9534f", fg="white", activebackground="#7a2e2e" if is_dark else "#c9302c", activeforeground="white", relief="flat", bd=0)
        self.restore_trash_btn.config(bg="#3a4a3a" if is_dark else "#5cb85c", fg="white", activebackground="#4a5a4a" if is_dark else "#449d44", activeforeground="white", relief="flat", bd=0)
        self.config_btn.config(bg=btn_bg, fg=fg_color, activebackground="#444444" if is_dark else "#c0c0c0", activeforeground=fg_color, relief="flat", bd=0)

        self.details_panel.config(bg="#1e1e1e" if is_dark else "#ffffff", bd=1, relief="solid")
        self.details_title_lbl.config(bg="#1e1e1e" if is_dark else "#ffffff", fg="#ffffff" if is_dark else "#000000")
        self.details_text_widget.config(bg="#121212" if is_dark else "#f9f9f9", fg="#00FF7F" if is_dark else "#000000")
        
        self.toast_label.config(bg="#222222", fg="#00FF7F")

        self.update_folder_action_bar()

    def init_folder_action_bar_widgets(self):
        """Creates all action bar widgets once during startup to completely eliminate recreation flashing."""
        is_dark = self.dark_mode
        bar_bg = "#1e1e1e" if is_dark else "#e8e8e8"
        btn_bg = "#333333" if is_dark else "#d0d0d0"
        btn_fg = "#ffffff" if is_dark else "#222222"

        self.folder_action_bar.config(bg=bar_bg)

        self.details_toggle_btn = tk.Button(self.folder_action_bar, text="ℹ Details", bg=btn_bg, fg=btn_fg,
                                            font=("Arial", 9, "bold"), relief="flat", bd=0, padx=6, pady=2,
                                            command=self.toggle_details_panel)
        self.details_toggle_btn.pack(side="left", padx=(4, 12), pady=6)
        ToolTip(self.details_toggle_btn, "Show or hide the floating file details panel")

        self.prev_btn = tk.Button(self.folder_action_bar, text="⬅ Prev", bg=btn_bg, fg=btn_fg,
                                  font=("Arial", 9, "bold"), relief="flat", bd=0, padx=6, pady=2,
                                  command=lambda: self.navigate(-1))
        self.prev_btn.pack(side="left", padx=4, pady=6)
        ToolTip(self.prev_btn, "Go to previous media item")

        self.next_btn = tk.Button(self.folder_action_bar, text="Next ➡", bg=btn_bg, fg=btn_fg,
                                  font=("Arial", 9, "bold"), relief="flat", bd=0, padx=6, pady=2,
                                  command=lambda: self.navigate(1))
        self.next_btn.pack(side="left", padx=4, pady=6)
        ToolTip(self.next_btn, "Go to next media item")

        self.trash_action_btn = tk.Button(self.folder_action_bar, text="🗑 Trash", bg="#5a2323" if is_dark else "#ffcccc", fg="#ff8888" if is_dark else "#880000",
                                          font=("Segoe UI Symbol", 9, "bold"), relief="flat", bd=0, padx=8, pady=2,
                                          command=self.delete_current_file)
        self.trash_action_btn.pack(side="left", padx=4, pady=6)
        ToolTip(self.trash_action_btn, "Move current file to local trash folder")

        self.undo_action_btn = tk.Button(self.folder_action_bar, text="↶ Undo", bg=btn_bg, fg=btn_fg,
                                         font=("Segoe UI Symbol", 9, "bold"), relief="flat", bd=0, padx=6, pady=2,
                                         command=self.undo_last_action)
        self.undo_action_btn.pack(side="left", padx=4, pady=6)
        ToolTip(self.undo_action_btn, "Undo last move or delete action")

        self.action_sep = tk.Frame(self.folder_action_bar, width=2, bg="#444444" if is_dark else "#cccccc")
        self.action_sep.pack(side="left", fill="y", padx=2, pady=6)

        for slot_id, k in self.key_bindings.items():
            btn = tk.Button(self.folder_action_bar, text="", font=("Arial", 9, "bold"), relief="flat", bd=0, padx=8, pady=2)
            
            hold_timer = [None]
            def make_press_handlers(key_char):
                def on_press(event):
                    ToolTip.hide_all()
                    hold_timer[0] = self.folder_action_bar.after(500, lambda: on_long_press(key_char))
                def on_release(event):
                    ToolTip.hide_all()
                    if hold_timer[0]:
                        self.folder_action_bar.after_cancel(hold_timer[0])
                        hold_timer[0] = None
                        self.handle_move_action(key_char)
                return on_press, on_release
            
            def on_long_press(key_char):
                hold_timer[0] = None
                ToolTip.hide_all()
                path = filedialog.askdirectory(title=f"Select New Folder for Key [{key_char.upper()}]")
                if path:
                    path = os.path.normpath(path)
                    self.dest_dirs[key_char] = path
                    self.save_current_config_to_file()
                    self.update_folder_action_bar()
                    self.show_toast(f"Updated folder for [{key_char.upper()}]", color="#00FF7F")
                self.canvas.focus_set()

            p_handler, r_handler = make_press_handlers(k)
            btn.bind("<ButtonPress-1>", p_handler)
            btn.bind("<ButtonRelease-1>", r_handler)
            
            self.folder_shortcut_buttons[k] = btn

        self.assign_shortcut_btn = tk.Button(self.folder_action_bar, text="➕ Assign Shortcut", bg="#2b6cb0" if is_dark else "#bee3f8", fg="#ebf8ff" if is_dark else "#2b6cb0",
                                             font=("Arial", 9, "bold"), relief="flat", bd=0, padx=8, pady=2,
                                             command=self.assign_next_shortcut)
        ToolTip(self.assign_shortcut_btn, "Assign a destination folder to the next available shortcut key in order")

        self.no_mapping_lbl = tk.Label(self.folder_action_bar, text="No destination folders assigned in configuration.", font=("Arial", 9, "italic"))

        self.temp_btn = tk.Button(self.folder_action_bar, text="📁 Temp Folder", bg="#1a365d" if is_dark else "#cce5ff", fg="#90cdf4" if is_dark else "#004085", 
                                  font=("Arial", 9, "bold"), relief="flat", bd=0, padx=8, pady=2)
        ToolTip(self.temp_btn, "Click to change temp folder\nHold-press (0.5s) to send file instantly to temp folder")
        
        temp_hold_timer = [None]
        def on_temp_press(event):
            ToolTip.hide_all()
            temp_hold_timer[0] = self.folder_action_bar.after(500, on_temp_long_press)

        def on_temp_release(event):
            ToolTip.hide_all()
            if temp_hold_timer[0]:
                self.folder_action_bar.after_cancel(temp_hold_timer[0])
                temp_hold_timer[0] = None
                self.handle_temp_folder_action(force_prompt=True)

        def on_temp_long_press():
            temp_hold_timer[0] = None
            ToolTip.hide_all()
            if not self.last_temp_folder:
                self.handle_temp_folder_action(force_prompt=True)
            else:
                self.execute_move_to_path(self.last_temp_folder, "Temp Folder")
            self.canvas.focus_set()

        self.temp_btn.bind("<ButtonPress-1>", on_temp_press)
        self.temp_btn.bind("<ButtonRelease-1>", on_temp_release)
        self.temp_btn.pack(side="right", padx=(12, 4), pady=6)

    def assign_next_shortcut(self):
        ToolTip.hide_all()
        sequence = list(self.key_bindings.values())
        next_key = None
        for key in sequence:
            if key not in self.dest_dirs or not self.dest_dirs[key]:
                next_key = key
                break
        
        if not next_key:
            messagebox.showinfo("All Assigned", "All shortcut keys have already been assigned!")
            return
            
        path = filedialog.askdirectory(title=f"Select Folder for Shortcut [{next_key.upper()}]")
        if path:
            path = os.path.normpath(path)
            self.dest_dirs[next_key] = path
            self.save_current_config_to_file()
            self.update_folder_action_bar()
            self.show_toast(f"Assigned folder to [{next_key.upper()}]", color="#00FF7F")
        self.canvas.focus_set()

    def update_folder_action_bar(self):
        ToolTip.hide_all()
        is_dark = self.dark_mode
        bar_bg = "#1e1e1e" if is_dark else "#e8e8e8"
        btn_bg = "#333333" if is_dark else "#d0d0d0"
        btn_fg = "#ffffff" if is_dark else "#222222"

        self.folder_action_bar.config(bg=bar_bg)

        details_bg = btn_bg if self.show_details_panel else ("#222222" if is_dark else "#b0b0b0")
        self.details_toggle_btn.config(bg=details_bg, fg=btn_fg)

        for btn in [self.prev_btn, self.next_btn, self.undo_action_btn]:
            btn.config(bg=btn_bg, fg=btn_fg)

        self.trash_action_btn.config(bg="#5a2323" if is_dark else "#ffcccc", fg="#ff8888" if is_dark else "#880000")
        self.action_sep.config(bg="#444444" if is_dark else "#cccccc")

        temp_text = "📁 Temp Folder"
        if self.last_temp_folder:
            temp_text = f"📁 Temp: {os.path.basename(self.last_temp_folder)}"
        self.temp_btn.config(text=temp_text, bg="#1a365d" if is_dark else "#cce5ff", fg="#90cdf4" if is_dark else "#004085")

        for btn in self.folder_shortcut_buttons.values():
            btn.pack_forget()
        self.assign_shortcut_btn.pack_forget()
        self.no_mapping_lbl.pack_forget()

        mapping_found = False
        for slot_id, k in self.key_bindings.items():
            v = self.dest_dirs.get(k)
            if v and k in self.folder_shortcut_buttons:
                mapping_found = True
                folder_name = os.path.basename(v)
                btn = self.folder_shortcut_buttons[k]
                btn.config(text=f"📁 {folder_name} [{k.upper()}]", bg=btn_bg, fg=btn_fg)
                ToolTip(btn, f"Single-click to send file to {folder_name} (Shortcut: [{k.upper()}])\nHold-press to change folder")
                btn.pack(side="left", padx=4, pady=6)

        sequence = list(self.key_bindings.values())
        has_unassigned = any(key not in self.dest_dirs or not self.dest_dirs[key] for key in sequence)
        if has_unassigned:
            self.assign_shortcut_btn.config(bg="#2b6cb0" if is_dark else "#bee3f8", fg="#ebf8ff" if is_dark else "#2b6cb0")
            self.assign_shortcut_btn.pack(side="left", padx=6, pady=6)

        if not mapping_found and not has_unassigned:
            self.no_mapping_lbl.config(bg=bar_bg, fg="#aaaaaa" if is_dark else "gray")
            self.no_mapping_lbl.pack(side="left", padx=10, pady=8)

    def handle_temp_folder_action(self, force_prompt=False):
        ToolTip.hide_all()
        if not (0 <= self.index < len(self.media_files)):
            return
            
        if force_prompt or not self.last_temp_folder:
            path = filedialog.askdirectory(title="Select Temporary Destination Folder")
            if path:
                path = os.path.normpath(path)
                self.last_temp_folder = path
                self.update_folder_action_bar()
                self.execute_move_to_path(path, "Temp Folder")
        else:
            self.execute_move_to_path(self.last_temp_folder, "Temp Folder")
        self.canvas.focus_set()

    def execute_move_to_path(self, path, label_name):
        ToolTip.hide_all()
        if not (0 <= self.index < len(self.media_files)):
            return
        self.stop_video_stream()
        current_media_path = os.path.normpath(self.media_files[self.index])
        os.makedirs(path, exist_ok=True)
        filename = os.path.basename(current_media_path)
        dest_path = os.path.normpath(os.path.join(path, filename))
        
        # Check for file collision
        if os.path.exists(dest_path):
            mode_desc = "Append Number" if self.collision_mode == "append" else "Replace Existing"
            proceed = messagebox.askyesno(
                "Filename Conflict Warning",
                f"A file named '{filename}' already exists in destination folder '{os.path.basename(path)}'.\n\n"
                f"Selected Conflict Behavior: {mode_desc}\n\n"
                f"Do you want to proceed with this behavior?"
            )
            if not proceed:
                self.canvas.focus_set()
                return

            if self.collision_mode == "append":
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.normpath(os.path.join(path, f"{base}_{counter}{ext}"))
                    counter += 1

        shutil.move(current_media_path, dest_path)
        self.history.append((current_media_path, self.index, dest_path, 'move'))
        self.media_files.pop(self.index)
        
        self.moved_count += 1
        self.counter_label.config(text=f"Moved: {self.moved_count}")
        
        if self.index >= len(self.media_files) and self.index > 0:
            self.index = len(self.media_files) - 1
            
        self.show_toast(f"Moved to {label_name}: {os.path.basename(path)}", color="#00FF7F")
        self.load_current_media()

    def toggle_details_panel(self):
        ToolTip.hide_all()
        self.show_details_panel = not self.show_details_panel
        if self.show_details_panel:
            self.details_panel.place(x=10, y=10)
        else:
            self.details_panel.place_forget()
        self.update_folder_action_bar()
        self.canvas.focus_set()

    def update_details_box(self, info_text):
        self.details_text_widget.config(state="normal")
        self.details_text_widget.delete("1.0", tk.END)
        self.details_text_widget.insert("1.0", info_text)
        self.details_text_widget.config(state="disabled")
        
        self.details_text_widget.update_idletasks()
        end_index = self.details_text_widget.index("end-1c")
        total_lines = int(end_index.split('.')[0])
        
        line_height = 16
        header_padding = 35
        computed_height = max(120, (total_lines * line_height) + header_padding)
        
        self.details_panel.config(height=computed_height)

    def format_file_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

    def update_trash_counter(self):
        local_trash_dir = os.path.normpath(os.path.join(self.src_folder, ".trash"))
        count = 0
        if os.path.exists(local_trash_dir):
            try:
                count = len([f for f in os.listdir(local_trash_dir) if os.path.isfile(os.path.join(local_trash_dir, f))])
            except Exception:
                count = 0
        
        if count > 0:
            self.trash_btn.config(text=f"🗑 Empty Trashbin ({count})")
        else:
            self.trash_btn.config(text="🗑 Empty Trashbin")

    def check_focus_restore(self, event):
        current_focus = self.root.focus_get()
        if current_focus == self.sort_dropdown and event.widget != self.sort_dropdown:
            self.canvas.focus_set()

    def on_sort_changed(self, event=None):
        ToolTip.hide_all()
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

    def open_current_file(self):
        ToolTip.hide_all()
        if not (0 <= self.index < len(self.media_files)):
            return
        media_path = os.path.normpath(self.media_files[self.index])
        if os.path.exists(media_path):
            try:
                if platform.system() == "Windows":
                    os.startfile(media_path)
                elif platform.system() == "Darwin":
                    subprocess.run(['open', media_path])
                else:
                    subprocess.run(['xdg-open', media_path])
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file:\n{e}")

    def open_in_explorer(self):
        ToolTip.hide_all()
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
        ToolTip.hide_all()
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
        ToolTip.hide_all()
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
            
            folder_name = os.path.basename(self.src_folder)
            self.root.title(f"Sorting: {folder_name} {self.index + 1}/{len(self.media_files)} - {filename}")
            
            self.jump_slider.config(to=max(1, len(self.media_files)))
            self.jump_slider.set(self.index + 1)
            self.jump_label.config(text=f"{self.index + 1} / {len(self.media_files)}")
            
            try:
                file_size_bytes = os.path.getsize(media_path)
                formatted_size = self.format_file_size(file_size_bytes)
                video_extensions = ('.mp4', '.webm', '.mov', '.mkv')

                if ext in video_extensions:
                    self.cap = cv2.VideoCapture(media_path)
                    fps = self.cap.get(cv2.CAP_PROP_FPS)
                    if fps > 0 and fps <= 60:
                        self.video_fps = fps
                    else:
                        self.video_fps = 30

                    total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    duration_sec = (total_frames / fps) if fps > 0 else 0
                    mins = int(duration_sec // 60)
                    secs = int(duration_sec % 60)
                    duration_str = f"{mins:02d}:{secs:02d}"

                    width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    
                    fourcc_int = int(self.cap.get(cv2.CAP_PROP_FOURCC))
                    codec_str = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)]).strip().upper()
                    if not codec_str or not codec_str.isalnum():
                        codec_str = "N/A"

                    details_str = (
                        f"Filename:\n{filename}\n\n"
                        f"Format:\nVideo ({ext.upper()[1:]})\n\n"
                        f"Resolution:\n{width} x {height}\n\n"
                        f"File Size:\n{formatted_size}\n\n"
                        f"Duration:\n{duration_str} ({total_frames} frames)\n\n"
                        f"Frame Rate:\n{fps:.2f} FPS\n\n"
                        f"Codec:\n{codec_str}"
                    )
                    self.update_details_box(details_str)
                    self.play_video_frame()
                else:
                    self.raw_pil_image = Image.open(media_path)
                    iw, ih = self.raw_pil_image.size
                    
                    if getattr(self.raw_pil_image, "is_animated", False):
                        self.gif_frames = []
                        try:
                            while True:
                                self.gif_frames.append(self.raw_pil_image.copy())
                                self.raw_pil_image.seek(len(self.gif_frames))
                        except EOFError:
                            pass
                        
                        total_frames = len(self.gif_frames)
                        details_str = (
                            f"Filename:\n{filename}\n\n"
                            f"Format:\nAnimated GIF\n\n"
                            f"Resolution:\n{iw} x {ih}\n\n"
                            f"File Size:\n{formatted_size}\n\n"
                            f"Frames:\n1 / {total_frames} (Looping)"
                        )
                        self.update_details_box(details_str)
                        self.frame_idx = 0
                        self.animate_gif()
                    else:
                        self.gif_frames = None
                        details_str = (
                            f"Filename:\n{filename}\n\n"
                            f"Format:\nImage ({ext.upper()[1:]})\n\n"
                            f"Resolution:\n{iw} x {ih}\n\n"
                            f"File Size:\n{formatted_size}"
                        )
                        self.update_details_box(details_str)
                        self.render_media_view()
            except Exception as e:
                self.update_details_box(f"Error loading metadata:\n{e}")
                self.canvas.delete("all")
                self.canvas.create_text(self.canvas.winfo_width()//2, self.canvas.winfo_height()//2, 
                                        text=f"Error loading media:\n{e}", fill="white", font=("Arial", 12))
                
        elif self.index >= len(self.media_files):
            self.root.title("Fast Media Sorter - Complete")
            self.update_details_box("Queue finished.\nAll items processed.")
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
        
        filename = os.path.basename(self.media_files[self.index])
        file_size_bytes = os.path.getsize(self.media_files[self.index])
        formatted_size = self.format_file_size(file_size_bytes)
        iw, ih = self.raw_pil_image.size
        total_frames = len(self.gif_frames)
        
        details_str = (
            f"Filename:\n{filename}\n\n"
            f"Format:\nAnimated GIF\n\n"
            f"Resolution:\n{iw} x {ih}\n\n"
            f"File Size:\n{formatted_size}\n\n"
            f"Frames:\n{self.frame_idx + 1} / {total_frames} (Looping)"
        )
        self.update_details_box(details_str)

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
        if isinstance(self.root.focus_get(), (ttk.Combobox, tk.Entry)):
            return
            
        key = event.keysym.lower()
        
        if key not in ['prior', 'next']:
            if key in self.pressed_keys:
                return
            self.pressed_keys.add(key)
        
        active_bound_keys = list(self.dest_dirs.keys())
        skip_key = self.action_keys.get('skip', 'space').lower()
        undo_key = self.action_keys.get('undo', 'backspace').lower()
        temp_key = self.action_keys.get('temp', 'e').lower()
        pick_temp_key = self.action_keys.get('pick_temp', 'q').lower()
        details_key = self.action_keys.get('details', 'p').lower()
        delete_key = self.action_keys.get('delete', 'delete').lower()
        
        if key == skip_key:
            self.skip_action()
        elif key == undo_key:
            self.undo_last_action()
        elif key == delete_key or (event.keysym.lower() == 'delete' and delete_key == 'delete'):
            self.delete_current_file()
        elif key == temp_key:
            if not self.last_temp_folder:
                self.handle_temp_folder_action(force_prompt=True)
            else:
                self.execute_move_to_path(self.last_temp_folder, "Temp Folder")
        elif key == pick_temp_key:
            self.handle_temp_folder_action(force_prompt=True)
        elif key == details_key:
            self.toggle_details_panel()
        elif key == 'home':
            self.jump_to_index(0)
        elif key == 'end':
            self.jump_to_index(len(self.media_files) - 1)
        elif key in ['prior', 'next']:
            if self.scroll_direction == 0:
                self.scroll_direction = -1 if key == 'prior' else 1
                self.scroll_start_time = self.root.tk.call('clock', 'clicks')
                self.start_progressive_scroll()
        elif key in active_bound_keys:
            self.handle_move_action(key)
        elif key == 'left':
            self.navigate(-1)
        elif key == 'right':
            self.navigate(1)

    def handle_keyrelease(self, event):
        key = event.keysym.lower()
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)
            
        if key in ['prior', 'next']:
            self.stop_progressive_scroll()

    def start_progressive_scroll(self):
        if self.scroll_job:
            self.root.after_cancel(self.scroll_job)
            self.scroll_job = None

        if not self.media_files:
            return

        elapsed = (self.root.tk.call('clock', 'clicks') - self.scroll_start_time) / 1000.0 if hasattr(self, 'scroll_start_time') else 0
        
        if elapsed < 3.0:
            step = 5
        elif elapsed < 6.0:
            step = 10
        else:
            step = 15

        new_index = max(0, min(len(self.media_files) - 1, self.index + (self.scroll_direction * step)))
        if new_index != self.index:
            self.index = new_index
            self.show_toast(f"Jumped by {step}", color="#00BFFF")
            self.load_current_media()

        self.scroll_job = self.root.after(300, self.start_progressive_scroll)

    def stop_progressive_scroll(self):
        if self.scroll_job:
            self.root.after_cancel(self.scroll_job)
            self.scroll_job = None
        self.scroll_direction = 0

    def jump_to_index(self, idx):
        if not self.media_files:
            return
        self.stop_video_stream()
        self.index = max(0, min(len(self.media_files) - 1, idx))
        self.load_current_media()

    def handle_move_action(self, key):
        ToolTip.hide_all()
        if not (0 <= self.index < len(self.media_files)):
            return
            
        target_folder = self.dest_dirs.get(key)
        if target_folder:
            self.execute_move_to_path(target_folder, f"[{key.upper()}]")

    def delete_current_file(self):
        ToolTip.hide_all()
        if not (0 <= self.index < len(self.media_files)):
            return

        self.stop_video_stream()
        current_media_path = os.path.normpath(self.media_files[self.index])

        try:
            local_trash_dir = os.path.normpath(os.path.join(self.src_folder, ".trash"))
            os.makedirs(local_trash_dir, exist_ok=True)
            
            filename = os.path.basename(current_media_path)
            dest_path = os.path.normpath(os.path.join(local_trash_dir, filename))
            
            base, ext = os.path.splitext(filename)
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
        ToolTip.hide_all()
        if len(self.media_files) == 0:
            return
        self.stop_video_stream()
        self.index = (self.index + 1) % len(self.media_files)
        self.show_toast("Skipped", color="#FFD700")
        self.load_current_media()

    def navigate(self, direction):
        ToolTip.hide_all()
        if len(self.media_files) == 0:
            return
        self.stop_video_stream()
        self.index = (self.index + direction) % len(self.media_files)
        self.load_current_media()

    def undo_last_action(self):
        ToolTip.hide_all()
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
        ToolTip.hide_all()
        self.stop_video_stream()
        self.root.destroy()

if __name__ == "__main__":
    # Check if a directory path was passed via command line argument or drag-and-drop onto executable
    target_dir = None
    if len(sys.argv) > 1:
        potential_path = sys.argv[1]
        if os.path.isdir(potential_path):
            target_dir = os.path.normpath(potential_path)

    if target_dir:
        # Load saved config defaults if available, then override source with target_dir
        dest_dirs = {}
        key_bindings = {
            'slot_0': 'w', 'slot_1': 'a', 'slot_2': 's', 'slot_3': 'd',
            'slot_4': 'i', 'slot_5': 'j', 'slot_6': 'k', 'slot_7': 'l'
        }
        action_keys = {
            'skip': 'space', 'undo': 'backspace', 'temp': 'e',
            'pick_temp': 'q', 'details': 'p', 'delete': 'delete'
        }
        dark_mode = False
        collision_mode = "append"

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    dest_dirs = {k: os.path.normpath(v) for k, v in config.get("destinations", {}).items()}
                    if config.get("key_bindings"):
                        key_bindings = config.get("key_bindings")
                    if config.get("action_keys"):
                        action_keys = config.get("action_keys")
                    dark_mode = config.get("dark_mode", False)
                    collision_mode = config.get("collision_mode", "append")
            except Exception as e:
                print(f"Failed to load config: {e}")

        main_root = tk.Tk()
        MediaSorterApp(main_root, target_dir, dest_dirs, key_bindings, action_keys, dark_mode, collision_mode)
        main_root.mainloop()
    else:
        setup_root = tk.Tk()
        SetupDialog(setup_root)
        setup_root.mainloop()