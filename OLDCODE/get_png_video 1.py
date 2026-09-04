"""
Video Player with Frame Extraction
A GUI application to play videos with audio and extract frames as PNG files.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
from PIL import Image, ImageTk
import os
import re
import vlc
import time as time_module


class VideoPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Player - Frame Extractor")
        self.root.geometry("1000x800")
        self.root.minsize(900, 700)
        self.root.configure(bg="#1e1e2e")
        
        # Video variables
        self.video_path = None
        self.cap = None  # OpenCV capture for frame extraction
        self.vlc_instance = vlc.Instance()
        self.vlc_player = self.vlc_instance.media_player_new()
        self.is_playing = False
        self.total_frames = 0
        self.fps = 30
        self.video_duration = 0  # in milliseconds
        self.playback_speed = 1.0
        
        # PNG extraction variables
        self.png_folder = None
        self.png_counter = 0
        
        # Update timer
        self.update_id = None
        self.slider_dragging = False
        
        # Setup GUI
        self.setup_styles()
        self.setup_gui()
        
        # Start update loop
        self.update_ui()
        
    def setup_styles(self):
        """Setup custom styles for the application."""
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Colors
        self.bg_color = "#1e1e2e"
        self.fg_color = "#cdd6f4"
        self.accent_color = "#89b4fa"
        self.button_color = "#313244"
        self.hover_color = "#45475a"
        
        # Configure styles
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("TLabel", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 10))
        self.style.configure("TButton", background=self.button_color, foreground=self.fg_color, 
                           font=("Segoe UI", 10, "bold"), padding=10)
        self.style.map("TButton", background=[("active", self.hover_color)])
        
        self.style.configure("Accent.TButton", background=self.accent_color, foreground="#1e1e2e",
                           font=("Segoe UI", 10, "bold"), padding=10)
        self.style.map("Accent.TButton", background=[("active", "#b4befe")])
        
        self.style.configure("Danger.TButton", background="#f38ba8", foreground="#1e1e2e",
                           font=("Segoe UI", 10, "bold"), padding=10)
        self.style.map("Danger.TButton", background=[("active", "#eba0ac")])
        
        self.style.configure("Extract.TButton", background="#a6e3a1", foreground="#1e1e2e",
                           font=("Segoe UI", 10, "bold"), padding=10)
        self.style.map("Extract.TButton", background=[("active", "#94e2d5")])
        
        self.style.configure("Horizontal.TScale", background=self.bg_color, troughcolor=self.button_color)
        
    def setup_gui(self):
        """Setup the main GUI components."""
        # Main container with grid layout
        self.main_frame = ttk.Frame(self.root, style="TFrame")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configure grid weights
        self.main_frame.grid_rowconfigure(1, weight=1)  # Video row expands
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Title (row 0)
        title_label = tk.Label(self.main_frame, text="🎬 Video Player - Frame Extractor", 
                              font=("Segoe UI", 18, "bold"), bg=self.bg_color, fg=self.accent_color)
        title_label.grid(row=0, column=0, pady=(0, 10), sticky="ew")
        
        # Video display area (row 1) - with fixed minimum height
        self.video_container = tk.Frame(self.main_frame, bg="#11111b", relief=tk.SUNKEN, bd=2)
        self.video_container.grid(row=1, column=0, sticky="nsew", pady=5)
        self.video_container.grid_propagate(False)  # Prevent resizing based on content
        
        # Set minimum size for video container
        self.video_container.config(width=800, height=400)
        
        self.video_label = tk.Label(self.video_container, bg="#11111b", 
                                   text="No video loaded\nClick 'Open Video' to start",
                                   font=("Segoe UI", 14), fg="#585b70")
        self.video_label.pack(fill=tk.BOTH, expand=True)
        
        # Controls container (row 2) - fixed height area for all controls
        controls_container = ttk.Frame(self.main_frame, style="TFrame")
        controls_container.grid(row=2, column=0, sticky="ew", pady=5)
        
        # Time display frame
        time_frame = ttk.Frame(controls_container, style="TFrame")
        time_frame.pack(fill=tk.X, pady=5)
        
        # Current time label
        self.current_time_label = tk.Label(time_frame, text="00:00:00", font=("Consolas", 12, "bold"),
                                          bg=self.bg_color, fg=self.fg_color)
        self.current_time_label.pack(side=tk.LEFT, padx=10)
        
        # Slider
        self.slider_var = tk.DoubleVar(value=0)
        self.slider = ttk.Scale(time_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                               variable=self.slider_var, style="Horizontal.TScale")
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        # Bind slider events
        self.slider.bind("<ButtonPress-1>", self.on_slider_press)
        self.slider.bind("<ButtonRelease-1>", self.on_slider_release)
        self.slider.bind("<B1-Motion>", self.on_slider_motion)
        
        # Total time label
        self.total_time_label = tk.Label(time_frame, text="00:00:00", font=("Consolas", 12, "bold"),
                                        bg=self.bg_color, fg=self.fg_color)
        self.total_time_label.pack(side=tk.LEFT, padx=10)
        
        # Time input frame
        time_input_frame = ttk.Frame(controls_container, style="TFrame")
        time_input_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(time_input_frame, text="Go to time:", font=("Segoe UI", 10),
                bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT, padx=(10, 5))
        
        self.time_entry_var = tk.StringVar(value="00:00:00")
        self.time_entry = tk.Entry(time_input_frame, textvariable=self.time_entry_var, 
                                  font=("Consolas", 12), width=10, bg=self.button_color, 
                                  fg=self.fg_color, insertbackground=self.fg_color,
                                  relief=tk.FLAT, bd=5)
        self.time_entry.pack(side=tk.LEFT, padx=5)
        self.time_entry.bind("<Return>", self.on_time_entry_change)
        
        go_btn = ttk.Button(time_input_frame, text="Go", command=self.on_time_entry_change, style="TButton")
        go_btn.pack(side=tk.LEFT, padx=5)
        
        # Speed label
        self.speed_label = tk.Label(time_input_frame, text="Speed: 1.0x", font=("Segoe UI", 10),
                                   bg=self.bg_color, fg=self.accent_color)
        self.speed_label.pack(side=tk.RIGHT, padx=10)
        
        # Control buttons frame
        control_frame = ttk.Frame(controls_container, style="TFrame")
        control_frame.pack(fill=tk.X, pady=10)
        
        # Center the buttons
        button_container = ttk.Frame(control_frame, style="TFrame")
        button_container.pack(anchor=tk.CENTER)
        
        # Open button
        self.open_btn = ttk.Button(button_container, text="📂 Open Video", 
                                  command=self.open_video, style="Accent.TButton")
        self.open_btn.pack(side=tk.LEFT, padx=5)
        
        # Fast backward button
        self.fast_bwd_btn = ttk.Button(button_container, text="⏪ -10s", 
                                       command=self.fast_backward, style="TButton")
        self.fast_bwd_btn.pack(side=tk.LEFT, padx=5)
        
        # Play button
        self.play_btn = ttk.Button(button_container, text="▶ Play", 
                                  command=self.play_video, style="TButton")
        self.play_btn.pack(side=tk.LEFT, padx=5)
        
        # Pause button
        self.pause_btn = ttk.Button(button_container, text="⏸ Pause", 
                                   command=self.pause_video, style="TButton")
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        # Stop button
        self.stop_btn = ttk.Button(button_container, text="⏹ Stop", 
                                  command=self.stop_video, style="TButton")
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Fast forward button
        self.fast_fwd_btn = ttk.Button(button_container, text="⏩ +10s", 
                                       command=self.fast_forward, style="TButton")
        self.fast_fwd_btn.pack(side=tk.LEFT, padx=5)
        
        # Speed control frame
        speed_frame = ttk.Frame(controls_container, style="TFrame")
        speed_frame.pack(fill=tk.X, pady=5)
        
        speed_container = ttk.Frame(speed_frame, style="TFrame")
        speed_container.pack(anchor=tk.CENTER)
        
        tk.Label(speed_container, text="Playback Speed:", font=("Segoe UI", 10),
                bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT, padx=5)
        
        speeds = [0.25, 0.5, 1.0, 1.5, 2.0, 4.0]
        for speed in speeds:
            btn = ttk.Button(speed_container, text=f"{speed}x", 
                           command=lambda s=speed: self.set_speed(s), style="TButton")
            btn.pack(side=tk.LEFT, padx=2)
        
        # Extraction frame
        extract_frame = ttk.Frame(controls_container, style="TFrame")
        extract_frame.pack(fill=tk.X, pady=10)
        
        extract_container = ttk.Frame(extract_frame, style="TFrame")
        extract_container.pack(anchor=tk.CENTER)
        
        # Extract frame button
        self.extract_btn = ttk.Button(extract_container, text="📸 Extract Frame (PNG)", 
                                     command=self.extract_frame, style="Extract.TButton")
        self.extract_btn.pack(side=tk.LEFT, padx=10)
        
        # Clear all button
        self.clear_btn = ttk.Button(extract_container, text="🗑 Clear All PNGs", 
                                   command=self.clear_all_pngs, style="Danger.TButton")
        self.clear_btn.pack(side=tk.LEFT, padx=10)
        
        # Status bar (row 3)
        self.status_var = tk.StringVar(value="Ready - Open a video file to begin")
        self.status_bar = tk.Label(self.main_frame, textvariable=self.status_var, 
                                  font=("Segoe UI", 9), bg="#11111b", fg=self.fg_color,
                                  anchor=tk.W, padx=10, pady=5)
        self.status_bar.grid(row=3, column=0, sticky="ew", pady=(5, 0))
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Bind resize event
        self.root.bind("<Configure>", self.on_resize)
        
    def on_resize(self, event=None):
        """Handle window resize to adjust video container."""
        if event and event.widget == self.root:
            # Calculate available height for video
            total_height = self.root.winfo_height()
            # Reserve space for title, controls, and status bar (approximately 350 pixels)
            video_height = max(300, total_height - 400)
            video_width = self.root.winfo_width() - 40
            self.video_container.config(width=video_width, height=video_height)
        
    def open_video(self):
        """Open a video file dialog."""
        filetypes = [
            ("All Video Files", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v *.mpeg *.mpg *.3gp *.ogv *.ts *.mts *.m2ts"),
            ("MP4 Files", "*.mp4"),
            ("AVI Files", "*.avi"),
            ("MKV Files", "*.mkv"),
            ("MOV Files", "*.mov"),
            ("WMV Files", "*.wmv"),
            ("FLV Files", "*.flv"),
            ("WebM Files", "*.webm"),
            ("All Files", "*.*")
        ]
        
        filepath = filedialog.askopenfilename(title="Select Video File", filetypes=filetypes)
        
        if filepath:
            self.load_video(filepath)
            
    def load_video(self, filepath):
        """Load a video file."""
        # Stop any current playback
        self.vlc_player.stop()
        self.is_playing = False
        
        # Release previous OpenCV capture if any
        if self.cap is not None:
            self.cap.release()
            
        self.video_path = filepath
        
        # Setup OpenCV for frame extraction
        self.cap = cv2.VideoCapture(filepath)
        if not self.cap.isOpened():
            messagebox.showerror("Error", f"Could not open video file:\n{filepath}")
            return
            
        # Get video properties from OpenCV
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps <= 0:
            self.fps = 30  # Default FPS
            
        # Setup VLC for playback
        media = self.vlc_instance.media_new(filepath)
        self.vlc_player.set_media(media)
        
        # Embed VLC in tkinter window
        # On Windows, we need to set the window handle
        self.video_label.config(text="")  # Clear placeholder text
        self.root.update()  # Ensure window is ready
        
        # Get window handle for VLC
        handle = self.video_label.winfo_id()
        self.vlc_player.set_hwnd(handle)
        
        # Start playing briefly to get duration, then pause
        self.vlc_player.play()
        time_module.sleep(0.3)  # Wait for media to initialize
        
        # Get duration in milliseconds
        self.video_duration = self.vlc_player.get_length()
        if self.video_duration <= 0:
            self.video_duration = int((self.total_frames / self.fps) * 1000)
        
        # Pause after loading
        self.vlc_player.pause()
        self.vlc_player.set_position(0)
        self.is_playing = False
        
        # Setup PNG folder
        video_dir = os.path.dirname(filepath)
        self.png_folder = os.path.join(video_dir, "png")
        
        # Count existing PNGs
        self.update_png_counter()
        
        # Update slider range
        self.slider.configure(to=self.video_duration)
        
        # Update total time label
        self.total_time_label.configure(text=self.ms_to_time(self.video_duration))
        
        # Reset to beginning
        self.slider_var.set(0)
        self.update_time_display(0)
        
        # Update status
        video_name = os.path.basename(filepath)
        self.status_var.set(f"Loaded: {video_name} | Duration: {self.ms_to_time(self.video_duration)} | FPS: {self.fps:.2f}")
        self.root.title(f"Video Player - {video_name}")
        
    def update_png_counter(self):
        """Update PNG counter based on existing files."""
        if self.png_folder and os.path.exists(self.png_folder):
            existing_pngs = [f for f in os.listdir(self.png_folder) if f.endswith('.png')]
            if existing_pngs:
                # Find the highest number
                numbers = []
                for f in existing_pngs:
                    match = re.match(r'(\d+)\.png', f)
                    if match:
                        numbers.append(int(match.group(1)))
                if numbers:
                    self.png_counter = max(numbers)
                else:
                    self.png_counter = 0
            else:
                self.png_counter = 0
        else:
            self.png_counter = 0
            
    def update_ui(self):
        """Update UI elements periodically."""
        if self.vlc_player.is_playing():
            current_time = self.vlc_player.get_time()
            if current_time >= 0 and not self.slider_dragging:
                self.slider_var.set(current_time)
                self.update_time_display(current_time)
                
        # Schedule next update
        self.update_id = self.root.after(100, self.update_ui)
        
    def play_video(self):
        """Start video playback."""
        if self.video_path is None:
            messagebox.showwarning("Warning", "Please open a video file first.")
            return
            
        if not self.vlc_player.is_playing():
            self.vlc_player.play()
            self.is_playing = True
            self.status_var.set(f"Playing at {self.playback_speed}x speed")
            
    def pause_video(self):
        """Pause video playback."""
        if self.vlc_player.is_playing():
            self.vlc_player.pause()
            self.is_playing = False
            self.status_var.set("Paused")
            
    def stop_video(self):
        """Stop video playback and reset to beginning."""
        self.vlc_player.stop()
        self.is_playing = False
        
        if self.video_path:
            # Reload media to reset
            media = self.vlc_instance.media_new(self.video_path)
            self.vlc_player.set_media(media)
            handle = self.video_label.winfo_id()
            self.vlc_player.set_hwnd(handle)
            
        self.slider_var.set(0)
        self.update_time_display(0)
        self.status_var.set("Stopped")
        
    def fast_forward(self):
        """Skip forward 10 seconds."""
        if self.video_path is None:
            return
            
        current_time = self.vlc_player.get_time()
        new_time = min(current_time + 10000, self.video_duration)  # 10 seconds in ms
        self.vlc_player.set_time(int(new_time))
        self.slider_var.set(new_time)
        self.update_time_display(new_time)
        self.status_var.set("Fast forward +10s")
        
    def fast_backward(self):
        """Skip backward 10 seconds."""
        if self.video_path is None:
            return
            
        current_time = self.vlc_player.get_time()
        new_time = max(current_time - 10000, 0)  # 10 seconds in ms
        self.vlc_player.set_time(int(new_time))
        self.slider_var.set(new_time)
        self.update_time_display(new_time)
        self.status_var.set("Fast backward -10s")
        
    def set_speed(self, speed):
        """Set playback speed."""
        self.playback_speed = speed
        self.vlc_player.set_rate(speed)
        self.speed_label.configure(text=f"Speed: {speed}x")
        self.status_var.set(f"Playback speed set to {speed}x")
        
    def on_slider_press(self, event):
        """Handle slider press."""
        self.slider_dragging = True
        
    def on_slider_release(self, event):
        """Handle slider release."""
        self.slider_dragging = False
        if self.video_path:
            new_time = int(self.slider_var.get())
            self.vlc_player.set_time(new_time)
            self.update_time_display(new_time)
            
    def on_slider_motion(self, event):
        """Handle slider drag motion."""
        if self.slider_dragging and self.video_path:
            new_time = int(self.slider_var.get())
            self.update_time_display(new_time)
            
    def on_time_entry_change(self, event=None):
        """Handle time entry change."""
        if self.video_path is None:
            return
            
        time_str = self.time_entry_var.get().strip()
        ms = self.time_to_ms(time_str)
        
        if ms is not None and ms >= 0:
            ms = min(ms, self.video_duration)
            ms = max(ms, 0)
            
            self.vlc_player.set_time(int(ms))
            self.slider_var.set(ms)
            self.update_time_display(ms)
            self.status_var.set(f"Jumped to {self.ms_to_time(ms)}")
        else:
            messagebox.showwarning("Invalid Time", "Please enter time in format HH:MM:SS or H:MM:SS")
            
    def update_time_display(self, current_ms):
        """Update time display labels and entry."""
        time_str = self.ms_to_time(current_ms)
        self.current_time_label.configure(text=time_str)
        
        # Only update entry if not being edited
        if not self.time_entry.focus_get() == self.time_entry:
            self.time_entry_var.set(time_str)
        
    def ms_to_time(self, ms):
        """Convert milliseconds to HH:MM:SS format."""
        if ms < 0:
            ms = 0
        seconds = ms / 1000
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        
    def time_to_ms(self, time_str):
        """Convert HH:MM:SS format to milliseconds."""
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                return (hours * 3600 + minutes * 60 + seconds) * 1000
            elif len(parts) == 2:
                minutes, seconds = map(int, parts)
                return (minutes * 60 + seconds) * 1000
            else:
                return int(time_str) * 1000
        except ValueError:
            return None
            
    def extract_frame(self):
        """Extract current frame as PNG."""
        if self.cap is None or self.video_path is None:
            messagebox.showwarning("Warning", "Please open a video file first.")
            return
            
        # Create PNG folder if it doesn't exist
        if not os.path.exists(self.png_folder):
            os.makedirs(self.png_folder)
            
        # Get current time from VLC player
        current_ms = self.vlc_player.get_time()
        if current_ms < 0:
            current_ms = 0
            
        # Calculate frame number
        frame_num = int((current_ms / 1000) * self.fps)
        frame_num = min(frame_num, self.total_frames - 1)
        
        # Get frame using OpenCV
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = self.cap.read()
            
        if not ret:
            messagebox.showerror("Error", "Could not read current frame.")
            return
            
        # Increment counter and save PNG
        self.png_counter += 1
        png_filename = f"{self.png_counter:05d}.png"
        png_path = os.path.join(self.png_folder, png_filename)
        
        cv2.imwrite(png_path, frame)
        
        # Get current time string
        time_str = self.ms_to_time(current_ms)
        
        # Append to TIME.txt
        time_file_path = os.path.join(self.png_folder, "TIME.txt")
        with open(time_file_path, 'a', encoding='utf-8') as f:
            f.write(f"{png_filename}, {time_str}\n")
            
        self.status_var.set(f"Extracted: {png_filename} at {time_str}")
        messagebox.showinfo("Success", f"Frame extracted!\n\nFile: {png_filename}\nTime: {time_str}\nSaved to: {self.png_folder}")
        
    def clear_all_pngs(self):
        """Clear all PNG files and TIME.txt from the png folder."""
        if self.png_folder is None:
            messagebox.showwarning("Warning", "Please open a video file first.")
            return
            
        if not os.path.exists(self.png_folder):
            messagebox.showinfo("Info", "No PNG folder found. Nothing to clear.")
            return
            
        # Count files to delete
        png_files = [f for f in os.listdir(self.png_folder) if f.endswith('.png')]
        time_file = os.path.join(self.png_folder, "TIME.txt")
        has_time_file = os.path.exists(time_file)
        
        if not png_files and not has_time_file:
            messagebox.showinfo("Info", "No files to clear.")
            return
            
        # Confirm deletion
        msg = f"This will delete:\n- {len(png_files)} PNG file(s)"
        if has_time_file:
            msg += "\n- TIME.txt"
        msg += f"\n\nFrom folder: {self.png_folder}\n\nAre you sure?"
        
        if messagebox.askyesno("Confirm Deletion", msg):
            # Delete PNG files
            for f in png_files:
                try:
                    os.remove(os.path.join(self.png_folder, f))
                except Exception as e:
                    print(f"Error deleting {f}: {e}")
                    
            # Delete TIME.txt
            if has_time_file:
                try:
                    os.remove(time_file)
                except Exception as e:
                    print(f"Error deleting TIME.txt: {e}")
                    
            # Reset counter
            self.png_counter = 0
            
            self.status_var.set(f"Cleared {len(png_files)} PNG files and TIME.txt")
            messagebox.showinfo("Success", "All PNG files and TIME.txt have been deleted.")
            
    def on_closing(self):
        """Handle window closing."""
        # Cancel update timer
        if self.update_id:
            self.root.after_cancel(self.update_id)
            
        # Stop VLC player
        self.vlc_player.stop()
        
        # Release OpenCV capture
        if self.cap is not None:
            self.cap.release()
            
        self.root.destroy()


def main():
    root = tk.Tk()
    app = VideoPlayer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
