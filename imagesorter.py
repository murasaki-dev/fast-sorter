import os
import sys
import json
import shutil
import subprocess
import platform
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

# Determine the absolute directory where this script or executable resides
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "sorter_config.json")

class SetupDialog:
    def __init__(self, root):
        self.root = root
        self.root.title("Fast Image Sorter - Configuration")
        self.root.geometry("620x720")
        
        self.source_dir = ""
        self.dest_dirs = {}
        self.dest_entries = {}
        
        # --- Source Folder Section ---
        tk.Label(root, text="Unsorted Images Folder:", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 0))
        self.src_entry = tk.Entry(root, width=65)
        self.src_entry.pack(padx=20, pady=5)
        tk.Button(root, text="Browse Source", command=self.browse_source).pack(padx=20, anchor="w")
        
        # --- Destination Folders Section ---
        tk.Label(root, text="Assign Folders to 8 Keys (WASD + IJKL):", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 0))
        
        # 8 Keys Definition
        self.all_keys = [
            ("w", "W Key"),
            ("a", "A Key"),
            ("s", "S Key"),
            ("d", "D Key"),
            ("i", "I Key"),
            ("j", "J Key"),
            ("k", "K Key"),
            ("l", "L Key")
        ]

        self.folder_rows_frame = tk.Frame(root)
        self.folder_rows_frame.pack(fill="x", padx=20, pady=5)

        for key, label_text in self.all_keys:
            frame = tk.Frame(self.folder_rows_frame)
            frame.pack(fill="x", pady=2)
            tk.Label(frame, text=f"{label_text}:", width=15, anchor="w").pack(side="left")
            entry = tk.Entry(frame, width=45)
            entry.pack(side="left", padx=5)
            btn = tk.Button(frame, text="Browse", command=lambda k=key, e=entry: self.browse_dest(k, e))
            btn.pack(side="left")
            self.dest_entries[key] = (entry, btn)

        tk.Label(root, text="* SPACEBAR = Skip Image | Mouse Wheel = Zoom | Left-click Drag = Pan\n* Nav: Left/Right Arrows = Prev/Next | Backspace = Undo Last Move", 
                 fg="gray", font=("Arial", 9), justify="left").pack(pady=10)
        
        # Action Buttons Frame
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Start Sorting", bg="#28a745", fg="white", font=("Arial", 11, "bold"), 
                  padx=15, pady=5, command=self.validate_and_start).pack(side="left", padx=10)
        
        tk.Button(btn_frame, text="Clear Saved Folders", bg="#dc3545", fg="white", font=("Arial", 10), 
                  padx=10, pady=5, command=self.clear_config).pack(side="left", padx=10)

        # Load saved config on startup
        self.load_saved_config()

    def browse_source(self):
        path = filedialog.askdirectory()
        if path:
            self.src_entry.delete(0, tk.END)
            self.src_entry.insert(0, path)

    def browse_dest(self, key, entry_widget):
        path = filedialog.askdirectory()
        if path:
            self.dest_dirs[key] = path
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)

    def load_saved_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    
                src_path = config.get("source", "")
                if src_path and os.path.exists(src_path):
                    self.src_entry.insert(0, src_path)
                    
                dest_paths = config.get("destinations", {})
                for key, path in dest_paths.items():
                    if key in self.dest_entries:
                        entry, _ = self.dest_entries[key]
                        entry.delete(0, tk.END)
                        entry.insert(0, path)
                        self.dest_dirs[key] = path
            except Exception as e:
                print(f"Failed to load config: {e}")

    def save_config(self, src, dests):
        config = {
            "source": src,
            "destinations": dests
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def clear_config(self):
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all folder paths?"):
            self.src_entry.delete(0, tk.END)
            for entry, _ in self.dest_entries.values():
                entry.delete(0, tk.END)
            self.dest_dirs.clear()
            
            if os.path.exists(CONFIG_FILE):
                try:
                    os.remove(CONFIG_FILE)
                except Exception as e:
                    print(f"Failed to delete config file: {e}")

    def validate_and_start(self):
        src = self.src_entry.get().strip()
        if not src or not os.path.exists(src):
            messagebox.showerror("Error", "Please select a valid source folder.")
            return

        self.dest_dirs.clear()
        for key, (entry, _) in self.dest_entries.items():
            val = entry.get().strip()
            if val:
                self.dest_dirs[key] = val

        # Save preferences for future runs
        self.save_config(src, self.dest_dirs)

        self.root.destroy()
        
        main_root = tk.Tk()
        ImageSorterApp(main_root, src, self.dest_dirs)
        main_root.mainloop()

class ImageSorterApp:
    def __init__(self, root, src_folder, dest_dirs):
        self.root = root
        self.src_folder = src_folder
        self.dest_dirs = dest_dirs
        
        valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')
        self.images = [os.path.join(src_folder, f) for f in os.listdir(src_folder) 
                       if f.lower().endswith(valid_extensions)]
        
        # Default sort by filename alphabetically
        self.images.sort()
        
        self.index = 0
        self.history = []
        self.toast_timer = None
        self.anim_job = None
        
        # Zoom and Pan State Variables
        self.zoom_scale = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.raw_pil_image = None
        
        self.root.title("Fast Image Sorter")
        self.root.geometry("1100x800")
        
        self.status_label = tk.Label(root, text="", font=("Arial", 9), bg="#f0f0f0", anchor="w")
        self.status_label.pack(side="top", fill="x", padx=10, pady=5)
        
        # Bottom navigation bar
        self.nav_bar = tk.Frame(root, bg="#2b2b2b", height=45)
        self.nav_bar.pack(side="bottom", fill="x")
        self.nav_bar.pack_propagate(False)
        
        self.explorer_btn = tk.Button(self.nav_bar, text="📂 Open in Explorer", command=self.open_in_explorer, 
                                      bg="#444444", fg="white", font=("Arial", 9), relief="flat", activebackground="#555555", activeforeground="white")
        self.explorer_btn.pack(side="left", padx=10, pady=7)

        # Sort Order Dropdown
        tk.Label(self.nav_bar, text="Sort by:", bg="#2b2b2b", fg="white", font=("Arial", 9)).pack(side="left", padx=(10, 2))
        
        self.sort_var = tk.StringVar(value="Filename (A-Z)")
        self.sort_dropdown = ttk.Combobox(self.nav_bar, textvariable=self.sort_var, state="readonly", width=16,
                                          values=["Filename (A-Z)", "Date Modified (Newest)", "Date Modified (Oldest)", 
                                                  "File Size (Largest)", "File Size (Smallest)", "File Type"])
        self.sort_dropdown.pack(side="left", padx=5)
        
        # Bind events
        self.sort_dropdown.bind("<<ComboboxSelected>>", self.on_sort_changed)
        
        # Safe global click-away handler to restore focus to canvas if user clicks outside the dropdown
        self.root.bind("<Button-1>", self.check_focus_restore, add="+")

        self.jump_label = tk.Label(self.nav_bar, text="", bg="#2b2b2b", fg="white", font=("Arial", 9, "bold"))
        self.jump_label.pack(side="right", padx=10)
        
        self.jump_slider = tk.Scale(self.nav_bar, from_=1, to=max(1, len(self.images)), orient="horizontal", 
                                    command=self.slider_moved, bg="#2b2b2b", fg="white", highlightthickness=0, troughcolor="#444444")
        self.jump_slider.pack(side="right", fill="x", expand=True, padx=10)
        
        tk.Label(self.nav_bar, text="Jump to image:", bg="#2b2b2b", fg="white", font=("Arial", 9)).pack(side="right", padx=5)

        # Canvas for zooming & panning
        self.container = tk.Frame(root, bg="black")
        self.container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 5))
        
        self.canvas = tk.Canvas(self.container, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.focus_set()  # Ensure keyboard shortcuts target the canvas by default
        
        # Toast Overlay
        self.toast_label = tk.Label(self.container, text="", font=("Arial", 11, "bold"), 
                                    bg="#222222", fg="#00FF7F", padx=10, pady=5)

        # Event Bindings
        self.root.bind('<Key>', self.handle_keypress)
        self.canvas.bind('<MouseWheel>', self.on_zoom)          # Windows & MacOS
        self.canvas.bind('<Button-4>', self.on_zoom)            # Linux scroll up
        self.canvas.bind('<Button-5>', self.on_zoom)            # Linux scroll down
        self.canvas.bind('<ButtonPress-1>', self.start_pan)
        self.canvas.bind('<B1-Motion>', self.do_pan)
        self.canvas.bind('<Configure>', self.on_canvas_resize)

        self.load_current_image()

    def check_focus_restore(self, event):
        # If the user clicks anywhere outside the combobox, return focus to the canvas for hotkeys
        current_focus = self.root.focus_get()
        if current_focus == self.sort_dropdown and event.widget != self.sort_dropdown:
            self.canvas.focus_set()

    def on_sort_changed(self, event=None):
        if not self.images:
            return
            
        current_image_path = self.images[self.index] if 0 <= self.index < len(self.images) else None
        sort_mode = self.sort_var.get()
        
        if sort_mode == "Filename (A-Z)":
            self.images.sort(key=lambda p: os.path.basename(p).lower())
        elif sort_mode == "Date Modified (Newest)":
            self.images.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        elif sort_mode == "Date Modified (Oldest)":
            self.images.sort(key=lambda p: os.path.getmtime(p))
        elif sort_mode == "File Size (Largest)":
            self.images.sort(key=lambda p: os.path.getsize(p), reverse=True)
        elif sort_mode == "File Size (Smallest)":
            self.images.sort(key=lambda p: os.path.getsize(p))
        elif sort_mode == "File Type":
            self.images.sort(key=lambda p: (os.path.splitext(p)[1].lower(), os.path.basename(p).lower()))
            
        if current_image_path and current_image_path in self.images:
            self.index = self.images.index(current_image_path)
        else:
            self.index = 0
            
        # Instantly release focus back to canvas after a sort option is selected
        self.canvas.focus_set()
        
        self.show_toast(f"Sorted by: {sort_mode}", color="#00BFFF")
        self.load_current_image()

    def show_toast(self, message, color="#00FF7F"):
        if self.toast_timer:
            self.root.after_cancel(self.toast_timer)
            
        self.toast_label.config(text=message, fg=color)
        self.toast_label.place(relx=0.98, rely=0.95, anchor="se")
        self.toast_timer = self.root.after(1200, lambda: self.toast_label.place_forget())

    def open_in_explorer(self):
        if not (0 <= self.index < len(self.images)):
            return
        img_path = os.path.normpath(self.images[self.index])
        if os.path.exists(img_path):
            if platform.system() == "Windows":
                subprocess.run(f'explorer /select,"{img_path}"')
            elif platform.system() == "Darwin":
                subprocess.run(['open', '-R', img_path])
            else:
                subprocess.run(['xdg-open', os.path.dirname(img_path)])

    def slider_moved(self, val):
        if not self.images:
            return
        target_idx = int(val) - 1
        if 0 <= target_idx < len(self.images) and target_idx != self.index:
            self.index = target_idx
            self.load_current_image()

    def reset_view(self):
        self.zoom_scale = 1.0
        self.pan_x = 0
        self.pan_y = 0

    def on_canvas_resize(self, event):
        self.render_image_view()

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
            self.render_image_view()

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
        self.render_image_view()

    def load_current_image(self):
        if self.anim_job:
            self.root.after_cancel(self.anim_job)
            self.anim_job = None

        self.reset_view()

        if 0 <= self.index < len(self.images):
            img_path = self.images[self.index]
            filename = os.path.basename(img_path)
            
            mapping_parts = []
            for k in ['w', 'a', 's', 'd', 'i', 'j', 'k', 'l']:
                v = self.dest_dirs.get(k)
                if v:
                    mapping_parts.append(f"{k.upper()}: {os.path.basename(v)}")
                    
            mapping_str = " | ".join(mapping_parts)
            self.status_label.config(text=f"[{self.index + 1}/{len(self.images)}] {filename}\nKeys: {mapping_str} | [SPACE: Skip]")
            
            self.jump_slider.config(to=max(1, len(self.images)))
            self.jump_slider.set(self.index + 1)
            self.jump_label.config(text=f"{self.index + 1} / {len(self.images)}")
            
            try:
                self.raw_pil_image = Image.open(img_path)
                
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
                    self.render_image_view()
            except Exception as e:
                self.canvas.delete("all")
                self.canvas.create_text(self.canvas.winfo_width()//2, self.canvas.winfo_height()//2, 
                                        text=f"Error loading image:\n{e}", fill="white", font=("Arial", 12))
                
        elif self.index >= len(self.images):
            self.status_label.config(text="Sorting Complete! (Use Left Arrow to review or Backspace to undo)")
            self.canvas.delete("all")
            self.canvas.create_text(self.canvas.winfo_width()//2, self.canvas.winfo_height()//2, 
                                    text="All images processed!", fill="white", font=("Arial", 16))
            self.toast_label.place_forget()
            self.jump_slider.config(to=1)
            self.jump_label.config(text="0 / 0")
        else:
            self.index = 0
            self.load_current_image()

    def animate_gif(self):
        if not self.gif_frames:
            return
        self.raw_pil_image = self.gif_frames[self.frame_idx]
        self.render_image_view()
        self.frame_idx = (self.frame_idx + 1) % len(self.gif_frames)
        self.anim_job = self.root.after(100, self.animate_gif)

    def render_image_view(self):
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
        # Ignore hotkeys if user is interacting with the combobox dropdown
        if isinstance(self.root.focus_get(), ttk.Combobox):
            return
            
        key = event.keysym.lower()
        valid_keys = ['w', 'a', 's', 'd', 'i', 'j', 'k', 'l']
        
        if key == 'space':
            self.skip_action()
        elif key in valid_keys:
            self.handle_move_action(key)
        elif key == 'left':
            self.navigate(-1)
        elif key == 'right':
            self.navigate(1)
        elif key == 'backspace':
            self.undo_last_action()

    def handle_move_action(self, key):
        if not (0 <= self.index < len(self.images)):
            return
            
        current_image_path = self.images[self.index]
        target_folder = self.dest_dirs.get(key)
        
        if target_folder:
            os.makedirs(target_folder, exist_ok=True)
            folder_name = os.path.basename(target_folder)
            dest_path = os.path.join(target_folder, os.path.basename(current_image_path))
            
            shutil.move(current_image_path, dest_path)
            self.history.append((current_image_path, self.index, dest_path))
            self.images.pop(self.index)
            
            if self.index >= len(self.images) and self.index > 0:
                self.index = len(self.images) - 1
                
            self.show_toast(f"Moved to: {folder_name}", color="#00FF7F")
            self.load_current_image()

    def skip_action(self):
        if len(self.images) == 0:
            return
        self.index = (self.index + 1) % len(self.images)
        self.show_toast("Skipped", color="#FFD700")
        self.load_current_image()

    def navigate(self, direction):
        if len(self.images) == 0:
            return
        self.index = (self.index + direction) % len(self.images)
        self.load_current_image()

    def undo_last_action(self):
        if not self.history:
            return
            
        last_image_path, old_index, last_dest_path = self.history.pop()
        
        if os.path.exists(last_dest_path):
            restored_path = os.path.join(self.src_folder, os.path.basename(last_image_path))
            shutil.move(last_dest_path, restored_path)
            
            self.images.insert(old_index, restored_path)
            self.index = old_index
            self.show_toast("Undo Move", color="#00BFFF")
            self.load_current_image()

if __name__ == "__main__":
    setup_root = tk.Tk()
    SetupDialog(setup_root)
    setup_root.mainloop()