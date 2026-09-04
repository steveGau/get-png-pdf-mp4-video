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
import subprocess
import vlc


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
        # Use GDI output to avoid Intel D3D11 get_buffer/SetThumbNailClip failures when switching videos
        self.vlc_instance = vlc.Instance("--vout=gdi", "--avcodec-hw=none")
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
        self.is_ab_play_mode = False
        self.ab_start_ms = None
        self.ab_end_ms = None
        
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
        
        self.time_entry_var = tk.StringVar(value="00:00:000")
        self.time_entry = tk.Entry(time_input_frame, textvariable=self.time_entry_var, 
                                  font=("Consolas", 12), width=10, bg=self.button_color, 
                                  fg=self.fg_color, insertbackground=self.fg_color,
                                  relief=tk.FLAT, bd=5)
        self.time_entry.pack(side=tk.LEFT, padx=5)
        self.time_entry.bind("<Return>", self.on_time_entry_change)
        
        go_btn = ttk.Button(time_input_frame, text="Go", command=self.on_time_entry_change, style="TButton")
        go_btn.pack(side=tk.LEFT, padx=5)
        
        # Separator
        tk.Label(time_input_frame, text="|", font=("Segoe UI", 10),
                bg=self.bg_color, fg="#585b70").pack(side=tk.LEFT, padx=10)
        
        # Auto extract start (independent of Go to time, which tracks playback position)
        tk.Label(time_input_frame, text="Auto extract start:", font=("Segoe UI", 10),
                bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT, padx=(0, 5))
        
        self.auto_extract_start_var = tk.StringVar(value="00:00:000")
        self.auto_extract_start_entry = tk.Entry(
            time_input_frame, textvariable=self.auto_extract_start_var,
            font=("Consolas", 12), width=10, bg=self.button_color,
            fg=self.fg_color, insertbackground=self.fg_color,
            relief=tk.FLAT, bd=5,
        )
        self.auto_extract_start_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(
            time_input_frame, text="Copy Go",
            command=self.copy_go_to_auto_extract_start, style="TButton",
        ).pack(side=tk.LEFT, padx=2)
        
        # Auto extract duration input
        tk.Label(time_input_frame, text="Auto extract duration:", font=("Segoe UI", 10),
                bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT, padx=(10, 5))
        
        self.duration_entry_var = tk.StringVar(value="01:00:000")
        self.duration_entry = tk.Entry(time_input_frame, textvariable=self.duration_entry_var, 
                                      font=("Consolas", 12), width=10, bg=self.button_color, 
                                      fg=self.fg_color, insertbackground=self.fg_color,
                                      relief=tk.FLAT, bd=5)
        self.duration_entry.pack(side=tk.LEFT, padx=5)
        
        # Every extract frame time input
        tk.Label(time_input_frame, text="Every:", font=("Segoe UI", 10),
                bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT, padx=(10, 5))
        
        self.interval_entry_var = tk.StringVar(value="00:00:100")
        self.interval_entry = tk.Entry(time_input_frame, textvariable=self.interval_entry_var, 
                                      font=("Consolas", 12), width=10, bg=self.button_color, 
                                      fg=self.fg_color, insertbackground=self.fg_color,
                                      relief=tk.FLAT, bd=5)
        self.interval_entry.pack(side=tk.LEFT, padx=5)
        
        # Video frame resolution label (FPS info)
        self.frame_res_label = tk.Label(time_input_frame, text="[No video]", 
                                        font=("Consolas", 9), bg=self.bg_color, fg="#f9e2af")
        self.frame_res_label.pack(side=tk.LEFT, padx=(10, 5))
        
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

        tk.Label(button_container, text="Step Time:", font=("Segoe UI", 10),
                bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT, padx=(10, 5))
        self.step_time_var = tk.StringVar(value="10.0")
        self.step_time_entry = tk.Entry(
            button_container, textvariable=self.step_time_var,
            font=("Consolas", 11), width=8, bg=self.button_color,
            fg=self.fg_color, insertbackground=self.fg_color,
            relief=tk.FLAT, bd=5, justify=tk.CENTER,
        )
        self.step_time_entry.pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(button_container, text="sec", font=("Segoe UI", 10),
                bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT, padx=(0, 10))
        
        # Backward button
        self.fast_bwd_btn = ttk.Button(button_container, text="⏪ Backward", 
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
        
        # Forward button
        self.fast_fwd_btn = ttk.Button(button_container, text="⏩ Forward", 
                                       command=self.fast_forward, style="TButton")
        self.fast_fwd_btn.pack(side=tk.LEFT, padx=5)
        
        # Speed control frame
        speed_frame = ttk.Frame(controls_container, style="TFrame")
        speed_frame.pack(fill=tk.X, pady=5)
        
        speed_container = ttk.Frame(speed_frame, style="TFrame")
        speed_container.pack(anchor=tk.CENTER)
        
        tk.Label(speed_container, text="Playback Speed:", font=("Segoe UI", 10),
                bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT, padx=5)
        
        # Editable playback speed entry
        self.custom_speed_var = tk.StringVar(value="1.0")
        self.custom_speed_entry = tk.Entry(speed_container, textvariable=self.custom_speed_var,
                                          font=("Consolas", 11), width=6, bg=self.button_color,
                                          fg=self.fg_color, insertbackground=self.fg_color,
                                          relief=tk.FLAT, bd=5, justify=tk.CENTER)
        self.custom_speed_entry.pack(side=tk.LEFT, padx=5)
        self.custom_speed_entry.bind("<Return>", self.on_custom_speed_change)
        
        # Apply custom speed button
        apply_speed_btn = ttk.Button(speed_container, text="Set", 
                                    command=self.on_custom_speed_change, style="TButton")
        apply_speed_btn.pack(side=tk.LEFT, padx=2)
        
        # Separator between custom entry and preset buttons
        tk.Label(speed_container, text="|", font=("Segoe UI", 10),
                bg=self.bg_color, fg="#585b70").pack(side=tk.LEFT, padx=5)
        
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
        
        # Auto extract frame button
        self.auto_extract_btn = ttk.Button(extract_container, text="🎞️ Auto Extract Frame (PNG)", 
                                          command=self.auto_extract_frames, style="Extract.TButton")
        self.auto_extract_btn.pack(side=tk.LEFT, padx=10)
        
        # Create PDF button - left of Clear All PNGs
        self.create_pdf_btn = ttk.Button(extract_container, text="📄 Create PDF", 
                                        command=self.create_pdf, style="Extract.TButton")
        self.create_pdf_btn.pack(side=tk.LEFT, padx=10)
        
        # Clear All PNGs
        self.clear_btn = ttk.Button(extract_container, text="🗑 Clear All PNGs", 
                                   command=self.clear_all_pngs, style="Danger.TButton")
        self.clear_btn.pack(side=tk.LEFT, padx=10)
        
        # Rotate Video (left of Extract Video)
        tk.Label(extract_container, text="Rotate Video:", font=("Segoe UI", 10),
                bg=self.bg_color, fg=self.fg_color).pack(side=tk.LEFT, padx=(10, 5))
        self.rotate_video_options = [
            "No Rotation",
            "Rotate Right 90",
            "Rotate Right 180",
            "Rotate Left 90",
            "Rotate Left 180",
        ]
        self.rotate_video_var = tk.StringVar(value="No Rotation")
        self.rotate_video_combo = ttk.Combobox(
            extract_container,
            textvariable=self.rotate_video_var,
            values=self.rotate_video_options,
            state="readonly",
            width=18,
        )
        self.rotate_video_combo.pack(side=tk.LEFT, padx=5)
        
        # Extract Video
        self.extract_video_btn = ttk.Button(extract_container, text="🎬 Extract Video", 
                                            command=self.extract_video, style="Extract.TButton")
        self.extract_video_btn.pack(side=tk.LEFT, padx=10)
        
        # Start Time (button) - right of Clear All PNGs
        self.start_time_btn = ttk.Button(extract_container, text="Start Time", 
                                         command=self.on_start_time_click, style="TButton")
        self.start_time_btn.pack(side=tk.LEFT, padx=2)
        
        # 1st editable (Start time entry) - right of Start Time
        self.start_time_var = tk.StringVar(value="00:00:000")
        self.start_time_entry = tk.Entry(extract_container, textvariable=self.start_time_var,
                                         font=("Consolas", 11), width=10, bg=self.button_color,
                                         fg=self.fg_color, insertbackground=self.fg_color,
                                         relief=tk.FLAT, bd=5)
        self.start_time_entry.pack(side=tk.LEFT, padx=(0, 2))
        
        # End Time (button) - right of 1st editable
        self.end_time_btn = ttk.Button(extract_container, text="End Time", 
                                       command=self.on_end_time_click, style="TButton")
        self.end_time_btn.pack(side=tk.LEFT, padx=2)
        
        # 2nd editable (End time entry) - right of End Time
        self.end_time_var = tk.StringVar(value="00:00:000")
        self.end_time_entry = tk.Entry(extract_container, textvariable=self.end_time_var,
                                       font=("Consolas", 11), width=10, bg=self.button_color,
                                       fg=self.fg_color, insertbackground=self.fg_color,
                                       relief=tk.FLAT, bd=5)
        self.end_time_entry.pack(side=tk.LEFT, padx=(0, 2))
        
        # AB Play Time - left of Clear All MP4s
        self.ab_play_btn = ttk.Button(extract_container, text="🔁 AB Play Time", 
                                      command=self.ab_play_time, style="Extract.TButton")
        self.ab_play_btn.pack(side=tk.LEFT, padx=10)
        
        # Clear all MP4s - right of 2nd editable
        self.clear_mp4_btn = ttk.Button(extract_container, text="🗑 Clear All MP4s", 
                                        command=self.clear_all_mp4s, style="Danger.TButton")
        self.clear_mp4_btn.pack(side=tk.LEFT, padx=10)
        
        # Get Video Time - right of Clear All MP4s
        self.get_video_time_btn = ttk.Button(extract_container, text="⏱ Get Video Time", 
                                            command=self.get_video_time, style="TButton")
        self.get_video_time_btn.pack(side=tk.LEFT, padx=10)
        
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
        # Stop playback first - required before loading another file when video is playing
        if self.video_path:
            self.stop_video()
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
        # Stop before loading (open_video calls stop_video first; stop again if loading directly)
        self.vlc_player.stop()
        self.is_playing = False
        self.is_ab_play_mode = False

        # Delete VideoTime.txt when opening a new video
        video_dir = os.path.dirname(filepath)
        video_time_path = os.path.join(video_dir, "VideoTime", "VideoTime.txt")
        if os.path.exists(video_time_path):
            try:
                os.remove(video_time_path)
            except OSError:
                pass

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

        self.video_duration = (
            int((self.total_frames / self.fps) * 1000) if self.total_frames > 0 else 0
        )

        # Setup VLC for playback (prefer VLC duration when OpenCV is inaccurate)
        media = self.vlc_instance.media_new(filepath)
        try:
            media.parse()
            vlc_ms = media.get_duration()
            if vlc_ms and vlc_ms > 0:
                self.video_duration = vlc_ms
                if self.total_frames <= 0:
                    self.total_frames = max(
                        1, int(round((vlc_ms / 1000.0) * self.fps))
                    )
        except Exception:
            pass

        self.vlc_player.set_media(media)
        
        # Embed VLC in tkinter window
        # On Windows, we need to set the window handle
        self.video_label.config(text="")  # Clear placeholder text
        self.root.update()  # Ensure window is ready
        
        # Get window handle for VLC
        handle = self.video_label.winfo_id()
        self.vlc_player.set_hwnd(handle)
        
        # Do NOT play - video stays paused until user clicks Play
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
        self.auto_extract_start_var.set("00:00:000")
        
        # Update status
        video_name = os.path.basename(filepath)
        self.status_var.set(f"Loaded: {video_name} | Duration: {self.ms_to_time(self.video_duration)} | FPS: {self.fps:.2f}")
        self.root.title(f"Video Player - {video_name}")
        
        # Update frame resolution label
        ms_per_frame = 1000 / self.fps if self.fps > 0 else 0
        self.frame_res_label.configure(text=f"[{self.fps:.2f} fps = {ms_per_frame:.2f}ms/frame]")
        
        # Calculate and set the lowest playback speed based on video FPS
        lowest_speed = self.calculate_lowest_speed()
        self.custom_speed_var.set(f"{lowest_speed}")
        self.set_speed(lowest_speed)
        
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
                # AB Play: loop back to start when reaching end time
                if self.is_ab_play_mode and self.ab_end_ms is not None and current_time >= self.ab_end_ms:
                    self.vlc_player.set_time(int(self.ab_start_ms))
                    self.slider_var.set(self.ab_start_ms)
                    self.update_time_display(self.ab_start_ms)
                
        # Schedule next update
        self.update_id = self.root.after(100, self.update_ui)
        
    def play_video(self):
        """Start video playback."""
        if self.video_path is None:
            messagebox.showwarning("Warning", "Please open a video file first.")
            return
        # Click Play stops AB mode and does normal play
        self.is_ab_play_mode = False
            
        if not self.vlc_player.is_playing():
            # When video has ended, reload media (set_time alone doesn't restart VLC reliably)
            state = self.vlc_player.get_state()
            at_end = (
                state == vlc.State.Ended
                or (self.video_duration > 0 and self.vlc_player.get_time() >= self.video_duration - 100)
            )
            if at_end:
                self.vlc_player.stop()
                media = self.vlc_instance.media_new(self.video_path)
                self.vlc_player.set_media(media)
                self.vlc_player.set_hwnd(self.video_label.winfo_id())
                self.vlc_player.set_rate(self.playback_speed)
                self.slider_var.set(0)
                self.update_time_display(0)
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
        self.is_ab_play_mode = False
        
        if self.video_path:
            # Reload media to reset
            media = self.vlc_instance.media_new(self.video_path)
            self.vlc_player.set_media(media)
            handle = self.video_label.winfo_id()
            self.vlc_player.set_hwnd(handle)
            
        self.slider_var.set(0)
        self.update_time_display(0)
        self.status_var.set("Stopped")

    def _get_step_ms(self):
        """Parse Step Time edit box (seconds, e.g. 2.35) to milliseconds."""
        try:
            seconds = float(self.step_time_var.get().strip())
        except ValueError:
            messagebox.showwarning(
                "Invalid Step Time",
                "Please enter a valid step time in seconds (e.g. 2.35 or 8.64).",
            )
            return None
        if seconds <= 0:
            messagebox.showwarning("Invalid Step Time", "Step time must be greater than 0.")
            return None
        return int(round(seconds * 1000))

    def _current_playback_ms(self):
        """Current position in ms; fall back to slider if VLC returns -1."""
        current_time = self.vlc_player.get_time()
        if current_time < 0:
            current_time = int(self.slider_var.get())
        return max(0, current_time)

    def fast_forward(self):
        """Skip forward by Step Time (seconds)."""
        if self.video_path is None:
            return

        step_ms = self._get_step_ms()
        if step_ms is None:
            return

        current_time = self._current_playback_ms()
        new_time = min(current_time + step_ms, self.video_duration)
        self.vlc_player.set_time(int(new_time))
        self.slider_var.set(new_time)
        self.update_time_display(new_time)
        self.status_var.set(f"Forward {self.step_time_var.get().strip()} s")

    def fast_backward(self):
        """Skip backward by Step Time (seconds)."""
        if self.video_path is None:
            return

        step_ms = self._get_step_ms()
        if step_ms is None:
            return

        current_time = self._current_playback_ms()
        new_time = max(current_time - step_ms, 0)
        self.vlc_player.set_time(int(new_time))
        self.slider_var.set(new_time)
        self.update_time_display(new_time)
        self.status_var.set(f"Backward {self.step_time_var.get().strip()} s")
        
    def set_speed(self, speed):
        """Set playback speed."""
        self.playback_speed = speed
        self.vlc_player.set_rate(speed)
        self.speed_label.configure(text=f"Speed: {speed}x")
        # Update the custom speed entry to reflect the current speed
        self.custom_speed_var.set(f"{speed}")
        self.status_var.set(f"Playback speed set to {speed}x")
        
    def on_custom_speed_change(self, event=None):
        """Handle custom speed entry change."""
        speed_str = self.custom_speed_var.get().strip()
        try:
            speed = float(speed_str)
            # Validate speed range (VLC typically supports 0.25 to 4.0, but we allow lower)
            if speed <= 0:
                messagebox.showwarning("Invalid Speed", "Playback speed must be greater than 0")
                return
            if speed > 100:
                messagebox.showwarning("Invalid Speed", "Playback speed cannot exceed 100x")
                return
            
            self.playback_speed = speed
            self.vlc_player.set_rate(speed)
            self.speed_label.configure(text=f"Speed: {speed}x")
            self.status_var.set(f"Playback speed set to {speed}x")
        except ValueError:
            messagebox.showwarning("Invalid Speed", "Please enter a valid number for playback speed")
            
    def calculate_lowest_speed(self):
        """Calculate the lowest playback speed based on video FPS.
        
        The lowest speed is 1/fps (each frame displayed for ~1 second), but
        VLC has timestamp conversion errors below 0.25x (especially with Opus).
        Use 0.25x as minimum to avoid "Could not convert timestamp" decoder errors.
        """
        min_safe_speed = 0.25  # VLC minimum for stable playback (avoids Opus timestamp errors)
        if self.fps > 0:
            # Lowest speed = 1/fps, but not below min_safe_speed
            lowest_speed = max(1.0 / self.fps, min_safe_speed)
            return round(lowest_speed, 4)
        return min_safe_speed
        
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
        ms = self.time_hires_to_ms(time_str)
        
        if ms is not None and ms >= 0:
            ms = min(ms, self.video_duration)
            ms = max(ms, 0)
            
            self.vlc_player.set_time(int(ms))
            self.slider_var.set(ms)
            self.update_time_display(ms)
            self.status_var.set(f"Jumped to {self.ms_to_time_hires(ms)}")
        else:
            messagebox.showwarning("Invalid Time", "Please enter time in format MM:SS:mmm (e.g., 01:30:500)")
            
    def copy_go_to_auto_extract_start(self):
        """Copy Go to time into Auto extract start (optional; start defaults to 00:00:000)."""
        self.auto_extract_start_var.set(self.time_entry_var.get().strip())
        self.status_var.set(f"Auto extract start set to {self.auto_extract_start_var.get()}")
            
    def update_time_display(self, current_ms):
        """Update time display labels and entry."""
        time_str = self.ms_to_time(current_ms)
        time_str_hires = self.ms_to_time_hires(current_ms)
        self.current_time_label.configure(text=time_str)
        
        # Only update entry if not being edited (use high-res format)
        if not self.time_entry.focus_get() == self.time_entry:
            self.time_entry_var.set(time_str_hires)
        
    def ms_to_time(self, ms):
        """Convert milliseconds to HH:MM:SS format."""
        if ms < 0:
            ms = 0
        seconds = ms / 1000
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def ms_to_time_hires(self, ms):
        """Convert milliseconds to MM:SS:mmm format (high resolution)."""
        if ms < 0:
            ms = 0
        total_seconds = ms / 1000
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int(ms % 1000)
        return f"{minutes:02d}:{seconds:02d}:{milliseconds:03d}"
    
    def time_hires_to_ms(self, time_str):
        """Convert MM:SS:mmm format to milliseconds."""
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                minutes, seconds, milliseconds = map(int, parts)
                return (minutes * 60 + seconds) * 1000 + milliseconds
            elif len(parts) == 2:
                seconds, milliseconds = map(int, parts)
                return seconds * 1000 + milliseconds
            else:
                return int(time_str)
        except ValueError:
            return None
    
    def ms_to_interval(self, ms):
        """Convert milliseconds to MM:SS:mmm format (high resolution)."""
        if ms < 0:
            ms = 0
        total_seconds = ms / 1000
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int(ms % 1000)
        return f"{minutes:02d}:{seconds:02d}:{milliseconds:03d}"
    
    def interval_to_ms(self, interval_str):
        """Convert MM:SS:mmm format to milliseconds."""
        try:
            parts = interval_str.split(':')
            if len(parts) == 3:
                minutes, seconds, milliseconds = map(int, parts)
                return (minutes * 60 + seconds) * 1000 + milliseconds
            elif len(parts) == 2:
                seconds, milliseconds = map(int, parts)
                return seconds * 1000 + milliseconds
            else:
                return int(interval_str)
        except ValueError:
            return None
        
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
            
    def on_start_time_click(self):
        """Copy time from 'Go to time' to Start Time entry."""
        self.start_time_var.set(self.time_entry_var.get().strip())
        self.status_var.set("Start time set")
        
    def on_end_time_click(self):
        """Copy time from 'Go to time' to End Time entry."""
        self.end_time_var.set(self.time_entry_var.get().strip())
        self.status_var.set("End time set")
        
    def ab_play_time(self):
        """Repeat play video between Start Time and End Time."""
        if self.video_path is None:
            messagebox.showwarning("Warning", "Please open a video file first.")
            return
        start_ms = self.time_hires_to_ms(self.start_time_var.get().strip())
        end_ms = self.time_hires_to_ms(self.end_time_var.get().strip())
        if start_ms is None or start_ms < 0:
            messagebox.showwarning("Invalid Start Time", "Please enter a valid start time (MM:SS:mmm).")
            return
        if end_ms is None or end_ms < 0:
            messagebox.showwarning("Invalid End Time", "Please enter a valid end time (MM:SS:mmm).")
            return
        if start_ms >= end_ms:
            messagebox.showwarning("Invalid Range", "Start time must be less than end time.")
            return
        end_ms = min(end_ms, self.video_duration)
        self.is_ab_play_mode = True
        self.ab_start_ms = start_ms
        self.ab_end_ms = end_ms
        # Pause first for reliable seek, then seek to start, then play
        if self.vlc_player.is_playing():
            self.vlc_player.pause()
        self.vlc_player.set_time(int(start_ms))
        self.slider_var.set(start_ms)
        self.update_time_display(start_ms)
        self.vlc_player.play()
        self.is_playing = True
        self.status_var.set(f"AB Play: {self.start_time_var.get()} - {self.end_time_var.get()}")
        
    def get_video_time(self):
        """Append time from 'Go to time' to VideoTime.txt (as seconds) in VideoTime subfolder."""
        if self.video_path is None:
            messagebox.showwarning("Warning", "Please open a video file first.")
            return
        video_dir = os.path.dirname(self.video_path)
        video_time_folder = os.path.join(video_dir, "VideoTime")
        os.makedirs(video_time_folder, exist_ok=True)
        video_time_path = os.path.join(video_time_folder, "VideoTime.txt")
        time_str = self.time_entry_var.get().strip()
        ms = self.time_hires_to_ms(time_str)
        if ms is None or ms < 0:
            messagebox.showwarning("Invalid Time", "Please enter a valid time (MM:SS:mmm or HH:MM:SS).")
            return
        seconds = ms / 1000.0
        # Format: integer when whole, else 3 decimal places
        seconds_str = f"{int(seconds)}" if seconds == int(seconds) else f"{seconds:.3f}".rstrip('0').rstrip('.')
        try:
            with open(video_time_path, 'a', encoding='utf-8') as f:
                f.write(seconds_str + '\n')
            self.status_var.set(f"Appended {seconds_str} s to VideoTime.txt")
        except OSError as e:
            messagebox.showerror("Error", f"Failed to write VideoTime.txt:\n{e}")
        
    def time_hires_to_ffmpeg(self, time_str):
        """Convert MM:SS:mmm format to ffmpeg format (HH:MM:SS.mmm)."""
        ms = self.time_hires_to_ms(time_str)
        if ms is None or ms < 0:
            return None
        seconds = ms / 1000
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    
    def time_hires_to_filename_safe(self, time_str):
        """Convert MM:SS:mmm to filename-safe format (MM_SS_mmm)."""
        return time_str.replace(":", "_")

    def _parse_playback_speed_for_extract(self):
        """Read playback speed from the Playback Speed entry field."""
        speed_str = self.custom_speed_var.get().strip()
        try:
            speed = float(speed_str)
        except ValueError:
            messagebox.showwarning(
                "Invalid Speed",
                "Please enter a valid number in the Playback Speed field (e.g., 0.5).",
            )
            return None
        if speed <= 0:
            messagebox.showwarning("Invalid Speed", "Playback speed must be greater than 0.")
            return None
        if speed > 100:
            messagebox.showwarning("Invalid Speed", "Playback speed cannot exceed 100x.")
            return None
        self.playback_speed = speed
        return speed

    def _speed_to_filename_tag(self, speed):
        """Filename-safe speed tag, e.g. 0.5 -> speed0_5x."""
        tag = f"{speed:g}".replace(".", "_")
        return f"speed{tag}x"

    def _run_ffmpeg(self, args, label):
        """Run ffmpeg and return (success, stderr_snippet)."""
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode == 0:
            return True, None
        err = result.stderr[:800] if result.stderr else "Unknown error"
        return False, f"{label}:\n{err}"

    def _ffmpeg_base(self):
        """Common ffmpeg prefix with error-tolerant decode for trimmed/copied MP4 files."""
        return [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-fflags", "+discardcorrupt+genpts",
            "-err_detect", "ignore_err",
        ]

    def _ffmpeg_trim_input(self, start_ffmpeg, duration_ffmpeg, accurate_decode):
        """
        Fast seek (-ss before -i) for stream copy.
        Accurate seek (-ss after -i) when filters/re-encode must decode every frame
        (fixes Invalid NAL unit errors on stream-copy segment files).
        """
        if accurate_decode:
            return ["-i", self.video_path, "-ss", start_ffmpeg, "-t", duration_ffmpeg]
        return ["-ss", start_ffmpeg, "-i", self.video_path, "-t", duration_ffmpeg]

    def _reencode_video_codec_args(self):
        return [
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-vsync", "cfr",
        ]

    def _reencode_audio_codec_args(self):
        return ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"]

    def _encode_tail_args(self):
        return ["-max_muxing_queue_size", "1024", "-avoid_negative_ts", "make_zero"]

    def _extract_audio_segment(self, start_ffmpeg, duration_ffmpeg, temp_dir):
        """
        Extract audio from trimmed segment. Stream copy (no decode) often works on
        stream-copy MP4s when AAC decode/re-encode fails.
        """
        temp_a = os.path.join(temp_dir, "_temp_extract_a.m4a")
        temp_wav = os.path.join(temp_dir, "_temp_extract_a.wav")
        for p in (temp_a, temp_wav):
            try:
                if os.path.isfile(p):
                    os.remove(p)
            except OSError:
                pass

        tail = self._encode_tail_args()
        fast_trim = self._ffmpeg_trim_input(start_ffmpeg, duration_ffmpeg, False)
        accurate_trim = self._ffmpeg_trim_input(start_ffmpeg, duration_ffmpeg, True)

        strategies = [
            (
                "Audio stream copy (fast seek)",
                fast_trim + ["-map", "0:a:0?", "-vn", "-c:a", "copy"],
            ),
            (
                "Audio stream copy (accurate seek)",
                accurate_trim + ["-map", "0:a:0?", "-vn", "-c:a", "copy"],
            ),
            (
                "Audio re-encode (fast seek)",
                fast_trim + ["-map", "0:a:0?", "-vn"] + self._reencode_audio_codec_args(),
            ),
            (
                "Audio re-encode (accurate seek)",
                accurate_trim + ["-map", "0:a:0?", "-vn"] + self._reencode_audio_codec_args(),
            ),
        ]

        for label, args in strategies:
            cmd = self._ffmpeg_base() + args + tail + [temp_a]
            ok, _ = self._run_ffmpeg(cmd, label)
            if ok and os.path.isfile(temp_a) and os.path.getsize(temp_a) > 0:
                return True, temp_a

        # PCM WAV intermediate — sometimes decodes when AAC encoder path fails
        wav_cmd = (
            self._ffmpeg_base()
            + fast_trim
            + ["-map", "0:a:0?", "-vn", "-c:a", "pcm_s16le", "-f", "wav", temp_wav]
        )
        ok_wav, _ = self._run_ffmpeg(wav_cmd, "Audio to WAV")
        if ok_wav and os.path.isfile(temp_wav) and os.path.getsize(temp_wav) > 0:
            aac_cmd = (
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", temp_wav]
                + self._reencode_audio_codec_args()
                + [temp_a]
            )
            ok_aac, _ = self._run_ffmpeg(aac_cmd, "WAV to AAC")
            try:
                os.remove(temp_wav)
            except OSError:
                pass
            if ok_aac and os.path.isfile(temp_a) and os.path.getsize(temp_a) > 0:
                return True, temp_a

        try:
            if os.path.isfile(temp_wav):
                os.remove(temp_wav)
        except OSError:
            pass
        return False, None

    def _mux_video_audio(self, temp_v, temp_a, output_av):
        """Mux re-encoded video with extracted audio."""
        mux_copy = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", temp_v, "-i", temp_a,
            "-c", "copy", "-shortest", output_av,
        ]
        ok, err = self._run_ffmpeg(mux_copy, "Mux video+audio (copy)")
        if ok:
            return True, None

        mux_reencode = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", temp_v, "-i", temp_a,
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", output_av,
        ]
        return self._run_ffmpeg(mux_reencode, "Mux video+audio (re-encode audio)")

    def _extract_av_reencode(self, trim_args, vf, output_av, temp_dir, start_ffmpeg, duration_ffmpeg):
        """Re-encode rotated/filtered video with audio; fallbacks for difficult AAC streams."""
        tail = self._encode_tail_args()

        # Try 1: re-encode video, stream-copy audio (no AAC decode needed)
        combined_copy_a = (
            self._ffmpeg_base()
            + trim_args
            + [
                "-map", "0:v:0", "-map", "0:a:0?",
                "-filter:v", vf,
            ]
            + self._reencode_video_codec_args()
            + ["-c:a", "copy"]
            + tail
            + [output_av]
        )
        ok, err = self._run_ffmpeg(combined_copy_a, "Video+audio (video rotate, audio copy)")
        if ok:
            return True, None

        # Try 2: re-encode both video and audio in one pass
        combined = (
            self._ffmpeg_base()
            + trim_args
            + [
                "-map", "0:v:0", "-map", "0:a:0?",
                "-filter:v", vf,
            ]
            + self._reencode_video_codec_args()
            + self._reencode_audio_codec_args()
            + tail
            + [output_av]
        )
        ok, err = self._run_ffmpeg(combined, "Video+audio extract")
        if ok:
            return True, None

        # Try 3: split — rotate video, extract audio with multiple strategies, mux
        temp_v = os.path.join(temp_dir, "_temp_extract_v.mp4")
        for p in (temp_v,):
            try:
                if os.path.isfile(p):
                    os.remove(p)
            except OSError:
                pass

        v_cmd = (
            self._ffmpeg_base()
            + trim_args
            + ["-map", "0:v:0", "-filter:v", vf, "-an"]
            + self._reencode_video_codec_args()
            + tail
            + [temp_v]
        )
        ok_v, err_v = self._run_ffmpeg(v_cmd, "Video extract (rotation)")
        if not ok_v:
            return False, err_v or err

        ok_a, temp_a = self._extract_audio_segment(start_ffmpeg, duration_ffmpeg, temp_dir)

        if ok_a and temp_a:
            ok_mux, err_mux = self._mux_video_audio(temp_v, temp_a, output_av)
            for p in (temp_v, temp_a):
                try:
                    if os.path.isfile(p):
                        os.remove(p)
                except OSError:
                    pass
            if ok_mux:
                return True, None
            return False, err_mux or err

        try:
            if os.path.isfile(output_av):
                os.remove(output_av)
            os.replace(temp_v, output_av)
        except OSError:
            return False, err_v or err
        return True, "Audio could not be extracted; _av file contains video only (no audio)."

    def _video_fps_filter_for_speed(self, speed):
        """
        Build fps filter for playback-speed extract.
        Output duration stays (End - Start); speed scales frame density only.
        e.g. 0.5x -> 2x frames in the same period; 2.0x -> half the frames.
        """
        if self.fps <= 0:
            return None
        out_fps = self.fps / float(speed)
        if out_fps <= 0:
            return None
        return f"fps={out_fps:.6f}"

    def _get_rotate_filter(self):
        """Return ffmpeg transpose filter for the Rotate Video combobox selection."""
        mapping = {
            "No Rotation": None,
            "Rotate Right 90": "transpose=1",
            "Rotate Right 180": "transpose=1,transpose=1",
            "Rotate Left 90": "transpose=2",
            "Rotate Left 180": "transpose=2,transpose=2",
        }
        return mapping.get(self.rotate_video_var.get().strip())

    def _build_video_filter_chain(self, speed):
        """Combine fps (speed) and rotation filters for ffmpeg -filter:v."""
        parts = []
        if abs(speed - 1.0) >= 1e-6:
            fps_filter = self._video_fps_filter_for_speed(speed)
            if not fps_filter:
                return None
            parts.append(fps_filter)
        rotate_filter = self._get_rotate_filter()
        if rotate_filter:
            parts.append(rotate_filter)
        if not parts:
            return None
        return ",".join(parts)

    def _needs_video_reencode(self, speed):
        """Stream copy only when speed is 1.0x and no rotation is selected."""
        return abs(speed - 1.0) >= 1e-6 or self._get_rotate_filter() is not None

    def extract_video(self):
        """
        Extract video segment between Start Time and End Time at the Playback Speed.
        Output duration is always (End - Start). Playback speed changes how many
        frames are packed into that period (0.5x = 2x frames, 2x = half frames).
        Outputs two MP4 files: with audio, and video-only (no audio).
        """
        if self.video_path is None:
            messagebox.showwarning("Warning", "Please open a video file first.")
            return

        speed = self._parse_playback_speed_for_extract()
        if speed is None:
            return

        start_str = self.start_time_var.get().strip()
        end_str = self.end_time_var.get().strip()

        start_ms = self.time_hires_to_ms(start_str)
        end_ms = self.time_hires_to_ms(end_str)

        if start_ms is None or start_ms < 0:
            messagebox.showwarning(
                "Invalid Start Time",
                "Please enter a valid start time in format MM:SS:mmm (e.g., 01:30:500)",
            )
            return
        if end_ms is None or end_ms < 0:
            messagebox.showwarning(
                "Invalid End Time",
                "Please enter a valid end time in format MM:SS:mmm (e.g., 02:00:000)",
            )
            return
        if start_ms >= end_ms:
            messagebox.showwarning("Invalid Range", "Start time must be less than end time.")
            return
        if start_ms >= self.video_duration:
            messagebox.showwarning(
                "Invalid Start Time",
                f"Start time exceeds video duration ({self.ms_to_time(self.video_duration)})",
            )
            return

        end_ms = min(end_ms, self.video_duration)

        video_dir = os.path.dirname(self.video_path)
        mp4_folder = os.path.join(video_dir, "mp4")
        if not os.path.exists(mp4_folder):
            os.makedirs(mp4_folder)

        input_basename = os.path.splitext(os.path.basename(self.video_path))[0]
        start_safe = self.time_hires_to_filename_safe(start_str)
        end_safe = self.time_hires_to_filename_safe(end_str)
        speed_tag = self._speed_to_filename_tag(speed)
        base_name = f"{input_basename}_{start_safe}_{end_safe}_{speed_tag}"

        output_av = os.path.join(mp4_folder, f"{base_name}_av.mp4")
        output_v = os.path.join(mp4_folder, f"{base_name}_v.mp4")

        start_ffmpeg = self.time_hires_to_ffmpeg(start_str)
        duration_ms = end_ms - start_ms
        duration_ffmpeg = self.time_hires_to_ffmpeg(self.ms_to_time_hires(duration_ms))

        if start_ffmpeg is None or duration_ffmpeg is None:
            messagebox.showerror("Error", "Could not convert time format for ffmpeg.")
            return

        needs_reencode = self._needs_video_reencode(speed)
        trim_args = self._ffmpeg_trim_input(start_ffmpeg, duration_ffmpeg, needs_reencode)
        common_input = self._ffmpeg_base() + trim_args

        try:
            self.status_var.set(f"Extracting video at {speed}x (with audio)...")
            self.root.update()

            av_note = None
            if not needs_reencode:
                ok_av, err_av = self._run_ffmpeg(
                    common_input + ["-c", "copy", output_av],
                    "Video+audio extract",
                )
            else:
                vf = self._build_video_filter_chain(speed)
                if not vf:
                    messagebox.showerror(
                        "Error",
                        "Could not build video filter (check speed and rotation settings).",
                    )
                    return
                ok_av, err_av = self._extract_av_reencode(
                    trim_args, vf, output_av, mp4_folder, start_ffmpeg, duration_ffmpeg
                )
                if ok_av and err_av:
                    av_note = err_av

            if not ok_av:
                self.status_var.set("Extract failed")
                messagebox.showerror("Error", f"ffmpeg failed:\n{err_av}")
                return

            self.status_var.set(f"Extracting video at {speed}x (video only)...")
            self.root.update()

            if not needs_reencode:
                ok_v, err_v = self._run_ffmpeg(
                    common_input + ["-map", "0:v:0", "-c", "copy", "-an", output_v],
                    "Video-only extract",
                )
            else:
                vf = self._build_video_filter_chain(speed)
                v_cmd = (
                    common_input
                    + ["-map", "0:v:0", "-filter:v", vf, "-an"]
                    + self._reencode_video_codec_args()
                    + ["-max_muxing_queue_size", "1024", "-avoid_negative_ts", "make_zero", output_v]
                )
                ok_v, err_v = self._run_ffmpeg(v_cmd, "Video-only extract")

            if not ok_v:
                self.status_var.set("Extract partial")
                messagebox.showwarning(
                    "Partial Success",
                    f"Video+audio file created:\n{os.path.basename(output_av)}\n\n"
                    f"Video-only extract failed:\n{err_v}",
                )
                return

            self.status_var.set(f"Extracted: {os.path.basename(output_av)}")
            rotation = self.rotate_video_var.get().strip()
            success_msg = (
                f"Video extracted at {speed}x playback speed.\n"
                f"Rotation: {rotation}\n"
                f"Duration: {self.ms_to_time_hires(duration_ms)} (same as End - Start).\n\n"
                f"With audio: {os.path.basename(output_av)}\n"
                f"Video only: {os.path.basename(output_v)}\n\n"
                f"Saved to: {mp4_folder}"
            )
            if av_note:
                success_msg += f"\n\nNote: {av_note}"
            messagebox.showinfo("Success", success_msg)
        except FileNotFoundError:
            self.status_var.set("Extract failed")
            messagebox.showerror(
                "Error",
                "ffmpeg not found. Please install ffmpeg and add it to your PATH.",
            )
            
    def _imwrite_png(self, path, frame):
        """
        Save PNG to path. cv2.imwrite fails on Windows when path contains
        non-ASCII characters (e.g. Chinese); imencode + open() works.
        """
        try:
            if cv2.imwrite(path, frame):
                return True
        except Exception:
            pass
        try:
            ok, buf = cv2.imencode(".png", frame)
            if ok:
                with open(path, "wb") as f:
                    f.write(buf.tobytes())
                return True
        except Exception:
            pass
        return False

    def _read_frame_at_ms(self, current_ms):
        """Seek OpenCV capture to current_ms and read one frame."""
        if self.cap is None or not self.cap.isOpened():
            return False, None
        try:
            current_ms = int(max(0, current_ms))
            if self.video_duration > 0:
                current_ms = min(current_ms, self.video_duration)

            used_frame_index = False
            if self.total_frames > 0:
                frame_num = int(round((current_ms / 1000.0) * float(self.fps)))
                frame_num = max(0, min(frame_num, self.total_frames - 1))
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                used_frame_index = True
            else:
                self.cap.set(cv2.CAP_PROP_POS_MSEC, float(current_ms))

            ret, frame = self.cap.read()
            if ret and frame is not None:
                return True, frame

            if used_frame_index:
                self.cap.set(cv2.CAP_PROP_POS_MSEC, float(current_ms))
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    return True, frame

            return False, None
        except Exception:
            return False, None

    def _extract_single_png_ffmpeg(self, current_ms, png_path):
        """Grab one frame via ffmpeg (works with Unicode paths on Windows)."""
        hires = self.ms_to_time_hires(current_ms)
        start_ffmpeg = self.time_hires_to_ffmpeg(hires)
        if not start_ffmpeg:
            return False
        fp = os.path.abspath(png_path)
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", start_ffmpeg,
                    "-i", self.video_path,
                    "-map", "0:v:0",
                    "-vframes", "1",
                    "-an",
                    fp,
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            return (
                result.returncode == 0
                and os.path.isfile(fp)
                and os.path.getsize(fp) > 0
            )
        except (FileNotFoundError, OSError):
            return False

    def _write_frame_png(self, current_ms, png_path):
        """Try OpenCV imwrite, then ffmpeg. Returns True if png_path exists."""
        ret, frame = self._read_frame_at_ms(current_ms)
        if ret and self._imwrite_png(png_path, frame):
            return True
        return self._extract_single_png_ffmpeg(current_ms, png_path)

    def extract_frame(self):
        """Extract current frame as PNG."""
        if self.cap is None or self.video_path is None:
            messagebox.showwarning("Warning", "Please open a video file first.")
            return
            
        # Create PNG folder if it doesn't exist
        if not os.path.exists(self.png_folder):
            os.makedirs(self.png_folder)
            
        current_ms = self.vlc_player.get_time()
        if current_ms < 0:
            current_ms = int(self.slider_var.get())
        current_ms = int(max(0, current_ms))
        if self.video_duration > 0:
            current_ms = min(current_ms, self.video_duration)

        self.png_counter += 1
        png_filename = f"{self.png_counter:05d}.png"
        png_path = os.path.join(self.png_folder, png_filename)

        if not self._write_frame_png(current_ms, png_path):
            self.png_counter -= 1
            messagebox.showerror(
                "Error",
                f"Could not save PNG:\n{png_path}\n\n"
                "If the path contains non-English characters, ensure ffmpeg is installed.",
            )
            return
        
        # Get current time string
        time_str = self.ms_to_time(current_ms)
        
        # Append to TIME.txt
        time_file_path = os.path.join(self.png_folder, "TIME.txt")
        with open(time_file_path, 'a', encoding='utf-8') as f:
            f.write(f"{png_filename}, {time_str}\n")
            
        self.status_var.set(f"Extracted: {png_filename} at {time_str}")
        
    def auto_extract_frames(self):
        """Automatically extract frames from start time for the specified duration."""
        if self.cap is None or self.video_path is None:
            messagebox.showwarning("Warning", "Please open a video file first.")
            return
            
        # Start from Auto extract start field (not Go to time — Go tracks current playback position)
        start_time_str = self.auto_extract_start_var.get().strip()
        start_ms = self.time_hires_to_ms(start_time_str)
        
        if start_ms is None or start_ms < 0:
            messagebox.showwarning(
                "Invalid Start Time",
                "Please enter a valid auto extract start in format MM:SS:mmm (e.g., 00:00:000)",
            )
            return
            
        # Get duration from duration entry (MM:SS:mmm — same format as Every / Go to time)
        duration_str = self.duration_entry_var.get().strip()
        duration_ms = self.time_hires_to_ms(duration_str)

        if duration_ms is None or duration_ms <= 0:
            messagebox.showwarning(
                "Invalid Duration",
                "Please enter a valid duration in format MM:SS:mmm (e.g., 00:10:070 for 10.07 s)",
            )
            return
            
        # Get interval from interval entry (high resolution MM:SS:mmm format)
        interval_str = self.interval_entry_var.get().strip()
        interval_ms = self.interval_to_ms(interval_str)
        
        if interval_ms is None or interval_ms <= 0:
            messagebox.showwarning("Invalid Interval", "Please enter a valid interval in format MM:SS:mmm (must be > 0)")
            return
            
        # Validate times are within video bounds
        if start_ms >= self.video_duration:
            messagebox.showwarning(
                "Invalid Start Time",
                f"Auto extract start exceeds video duration "
                f"({self.ms_to_time_hires(self.video_duration)})",
            )
            return
            
        end_ms = min(start_ms + duration_ms, self.video_duration)
        actual_duration_ms = end_ms - start_ms

        if actual_duration_ms <= 0:
            messagebox.showwarning("Invalid Range", "No frames to extract in the specified range.")
            return

        capped = (start_ms + duration_ms) > self.video_duration
        # Confirm with user
        num_frames = int(actual_duration_ms / interval_ms) + 1
        msg = (
            f"Auto Extract Frames:\n\n"
            f"Start Time: {self.ms_to_time_hires(start_ms)}\n"
            f"End Time: {self.ms_to_time_hires(end_ms)}\n"
            f"Duration: {self.ms_to_time_hires(actual_duration_ms)}"
        )
        if capped:
            msg += (
                f"\n(requested {self.ms_to_time_hires(duration_ms)}, "
                f"capped at video end {self.ms_to_time_hires(self.video_duration)})"
            )
        msg += (
            f"\nInterval: {interval_str} (every {interval_ms}ms / {interval_ms / 1000:.3f}s)\n"
            f"Frames to extract: ~{num_frames}\n\n"
            f"Continue?"
        )
        
        if not messagebox.askyesno("Confirm Auto Extract", msg):
            return
            
        # Create PNG folder if it doesn't exist
        if not os.path.exists(self.png_folder):
            os.makedirs(self.png_folder)
            
        # Pause video during extraction
        was_playing = self.vlc_player.is_playing()
        if was_playing:
            self.vlc_player.pause()
            
        # Extract frames
        extracted_count = 0
        time_file_path = os.path.join(self.png_folder, "TIME.txt")
        
        current_ms = start_ms
        while current_ms <= end_ms:
            self.png_counter += 1
            png_filename = f"{self.png_counter:05d}.png"
            png_path = os.path.join(self.png_folder, png_filename)

            if self._write_frame_png(current_ms, png_path):
                time_str = self.ms_to_time(current_ms)
                with open(time_file_path, "a", encoding="utf-8") as f:
                    f.write(f"{png_filename}, {time_str}\n")
                extracted_count += 1
                self.status_var.set(
                    f"Auto extracting... {extracted_count}/{num_frames} frames"
                )
                self.root.update()
            else:
                self.png_counter -= 1
                try:
                    if os.path.isfile(png_path):
                        os.remove(png_path)
                except OSError:
                    pass

            current_ms += interval_ms
            
        # Restore playback state
        if was_playing:
            self.vlc_player.play()
            
        self.status_var.set(f"Auto extract complete: {extracted_count} frames extracted")
        messagebox.showinfo("Success", 
                           f"Auto extraction complete!\n\n"
                           f"Frames extracted: {extracted_count}\n"
                           f"Time range: {self.ms_to_time(start_ms)} - {self.ms_to_time(end_ms)}\n"
                           f"Saved to: {self.png_folder}")
        
    def create_pdf(self):
        """Create PDF from all PNG files in png folder (sorted by filename)."""
        if self.png_folder is None:
            messagebox.showwarning("Warning", "Please open a video file first.")
            return
            
        if not os.path.exists(self.png_folder):
            messagebox.showwarning("Warning", "PNG folder does not exist.")
            return
            
        png_files = sorted([f for f in os.listdir(self.png_folder) if f.lower().endswith('.png')])
        if not png_files:
            messagebox.showwarning("Warning", "No PNG files in folder to create PDF.")
            return
            
        pdf_path = os.path.join(self.png_folder, "videoPDF.pdf")
        try:
            images = []
            for f in png_files:
                img = Image.open(os.path.join(self.png_folder, f))
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                images.append(img)
            images[0].save(pdf_path, "PDF", save_all=True, append_images=images[1:])
            for img in images:
                img.close()
            self.status_var.set(f"Created: videoPDF.pdf ({len(png_files)} pages)")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create PDF:\n{e}")
            
    def clear_all_pngs(self):
        """Clear all PNG files and TIME.txt from the png folder."""
        if self.png_folder is None:
            messagebox.showwarning("Warning", "Please open a video file first.")
            return
            
        # Check if folder exists
        folder_exists = os.path.exists(self.png_folder)
        
        # Count files to delete
        png_files = []
        has_time_file = False
        if folder_exists:
            png_files = [f for f in os.listdir(self.png_folder) if f.endswith('.png')]
            time_file = os.path.join(self.png_folder, "TIME.txt")
            has_time_file = os.path.exists(time_file)
        
        if not png_files and not has_time_file:
            # No files to delete, but still reset counter
            self.png_counter = 0
            self.status_var.set("No files to clear. PNG ID reset to 00001")
            messagebox.showinfo("Info", "No files to clear.\n\nPNG counter reset. Next frame will be: 00001.png")
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
                    
            # Reset counter to 0 so next extraction starts from 00001
            self.png_counter = 0
            
            self.status_var.set(f"Cleared {len(png_files)} PNG files and TIME.txt. Next PNG ID: 00001")
            messagebox.showinfo("Success", f"All PNG files and TIME.txt have been deleted.\n\nPNG counter reset. Next frame will be: 00001.png")
            
    def clear_all_mp4s(self):
        """Clear all MP4 files from the mp4 folder."""
        if self.video_path is None:
            messagebox.showwarning("Warning", "Please open a video file first.")
            return
            
        video_dir = os.path.dirname(self.video_path)
        mp4_folder = os.path.join(video_dir, "mp4")
        
        if not os.path.exists(mp4_folder):
            messagebox.showinfo("Info", "No mp4 folder found. Nothing to clear.")
            return
            
        mp4_files = [f for f in os.listdir(mp4_folder) if f.lower().endswith('.mp4')]
        
        if not mp4_files:
            messagebox.showinfo("Info", "No MP4 files to clear.")
            return
            
        if messagebox.askyesno("Confirm Deletion", 
                               f"This will delete {len(mp4_files)} MP4 file(s) from:\n{mp4_folder}\n\nAre you sure?"):
            for f in mp4_files:
                try:
                    os.remove(os.path.join(mp4_folder, f))
                except Exception as e:
                    print(f"Error deleting {f}: {e}")
            self.status_var.set(f"Cleared {len(mp4_files)} MP4 files")
            messagebox.showinfo("Success", f"All MP4 files have been deleted from:\n{mp4_folder}")
            
    def on_closing(self):
        """Handle window closing."""
        # Cancel update timer
        if self.update_id:
            self.root.after_cancel(self.update_id)
            
        # Stop and release VLC (player before instance)
        self.vlc_player.stop()
        self.vlc_player.release()
        self.vlc_instance.release()
        
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
