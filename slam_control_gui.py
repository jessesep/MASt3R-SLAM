#!/usr/bin/env python3
"""
MASt3R-SLAM Control GUI
-----------------------
Process launcher and control panel for MASt3R-SLAM.
Works on WSL2 where ImGui input doesn't work!

Features:
- Launch MASt3R-SLAM with different camera sources
- Switch between camera sources (NDI, Webcam, Files, Datasets)
- Start/Stop/Restart SLAM processes
- Monitor FPS and status from process output
- Select NDI sources from dropdown
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import time
import json
import socket
import subprocess
import signal
import os
import re
from pathlib import Path


class SLAMControlGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MASt3R-SLAM Process Launcher")
        self.root.geometry("800x900")

        # Process management
        self.slam_process = None
        self.process_lock = threading.Lock()
        self.output_queue = queue.Queue()

        # Status variables
        self.status_var = tk.StringVar(value="No process running")
        self.fps_var = tk.StringVar(value="FPS: 0.0")
        self.source_var = tk.StringVar(value="No source")
        self.keyframes_var = tk.StringVar(value="Keyframes: 0")
        self.pid_var = tk.StringVar(value="PID: None")

        # Options
        self.disable_viz = tk.BooleanVar(value=True)  # Default to True for WSL2

        self.create_ui()

        # Start status update thread
        self.running = True
        self.status_thread = threading.Thread(target=self.monitor_process_output, daemon=True)
        self.status_thread.start()

    def create_ui(self):
        """Build the GUI"""

        # ===== HEADER =====
        header = tk.Frame(self.root, bg="#2c3e50", height=60)
        header.pack(fill=tk.X)

        title = tk.Label(
            header,
            text="MASt3R-SLAM Control",
            font=("Arial", 18, "bold"),
            fg="white",
            bg="#2c3e50"
        )
        title.pack(pady=15)

        # ===== STATUS PANEL =====
        status_frame = tk.LabelFrame(self.root, text="Process Status", padx=10, pady=10)
        status_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(status_frame, textvariable=self.status_var, font=("Arial", 10, "bold")).pack(anchor=tk.W)
        tk.Label(status_frame, textvariable=self.pid_var, font=("Arial", 9)).pack(anchor=tk.W)
        tk.Label(status_frame, textvariable=self.fps_var, font=("Arial", 10)).pack(anchor=tk.W)
        tk.Label(status_frame, textvariable=self.source_var, font=("Arial", 10)).pack(anchor=tk.W)
        tk.Label(status_frame, textvariable=self.keyframes_var, font=("Arial", 10)).pack(anchor=tk.W)

        # Process control buttons
        process_btn_frame = tk.Frame(status_frame)
        process_btn_frame.pack(fill=tk.X, pady=(10, 0))

        self.stop_btn = tk.Button(
            process_btn_frame,
            text="⏹️ Stop Process",
            command=self.stop_process,
            bg="#e74c3c",
            fg="white",
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.restart_btn = tk.Button(
            process_btn_frame,
            text="🔄 Restart",
            command=self.restart_process,
            state=tk.DISABLED
        )
        self.restart_btn.pack(side=tk.LEFT, padx=5)

        # ===== SOURCE SELECTION =====
        source_frame = tk.LabelFrame(self.root, text="Camera Source", padx=10, pady=10)
        source_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Source type dropdown
        tk.Label(source_frame, text="Source Type:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=5)

        self.source_type = ttk.Combobox(
            source_frame,
            values=["NDI", "Webcam", "RealSense", "TUM Dataset", "Video File", "Image Folder"],
            state="readonly",
            width=30
        )
        self.source_type.set("NDI")
        self.source_type.pack(fill=tk.X, pady=5)
        self.source_type.bind("<<ComboboxSelected>>", self.on_source_type_changed)

        # Dynamic source selection area
        self.dynamic_frame = tk.Frame(source_frame)
        self.dynamic_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Build NDI options by default
        self.build_ndi_options()

        # Options section
        options_frame = tk.Frame(source_frame)
        options_frame.pack(fill=tk.X, pady=5)

        self.viz_checkbox = tk.Checkbutton(
            options_frame,
            text="Disable Visualization (recommended for WSL2)",
            variable=self.disable_viz,
            font=("Arial", 9)
        )
        self.viz_checkbox.pack(anchor=tk.W)

        # Launch button
        self.launch_btn = tk.Button(
            source_frame,
            text="🚀 Launch SLAM",
            command=self.apply_source,
            bg="#27ae60",
            fg="white",
            font=("Arial", 12, "bold"),
            height=2
        )
        self.launch_btn.pack(fill=tk.X, pady=10)

        # ===== CONSOLE OUTPUT =====
        console_frame = tk.LabelFrame(self.root, text="SLAM Console Output", padx=10, pady=10)
        console_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.console_text = scrolledtext.ScrolledText(
            console_frame,
            height=15,
            bg="black",
            fg="#00ff00",
            font=("Courier", 9),
            wrap=tk.WORD
        )
        self.console_text.pack(fill=tk.BOTH, expand=True)

        # Clear console button
        tk.Button(
            console_frame,
            text="🗑️ Clear Console",
            command=lambda: self.console_text.delete(1.0, tk.END)
        ).pack(pady=5)

    def build_ndi_options(self):
        """Build NDI source selection UI"""
        self.clear_dynamic_frame()

        tk.Label(self.dynamic_frame, text="Scan for NDI sources:", font=("Arial", 9)).pack(anchor=tk.W, pady=5)

        scan_btn = tk.Button(
            self.dynamic_frame,
            text="🔍 Scan Network",
            command=self.scan_ndi_sources,
            bg="#3498db",
            fg="white"
        )
        scan_btn.pack(fill=tk.X, pady=5)

        tk.Label(self.dynamic_frame, text="Available NDI Sources:", font=("Arial", 9)).pack(anchor=tk.W, pady=(10, 5))

        self.ndi_listbox = tk.Listbox(self.dynamic_frame, height=5)
        self.ndi_listbox.pack(fill=tk.BOTH, expand=True, pady=5)

        # Scrollbar
        scrollbar = tk.Scrollbar(self.dynamic_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ndi_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.ndi_listbox.yview)

        # Manual entry option
        tk.Label(self.dynamic_frame, text="Or enter manually:", font=("Arial", 9)).pack(anchor=tk.W, pady=(10, 5))
        self.ndi_manual_entry = tk.Entry(self.dynamic_frame)
        self.ndi_manual_entry.pack(fill=tk.X, pady=5)
        self.ndi_manual_entry.insert(0, "TouchDesigner Output")

    def build_webcam_options(self):
        """Build webcam selection UI"""
        self.clear_dynamic_frame()

        tk.Label(self.dynamic_frame, text="Device ID:", font=("Arial", 9)).pack(anchor=tk.W, pady=5)

        self.webcam_id = tk.Spinbox(self.dynamic_frame, from_=0, to=10, width=10)
        self.webcam_id.pack(anchor=tk.W, pady=5)

        tk.Label(self.dynamic_frame, text="Resolution:", font=("Arial", 9)).pack(anchor=tk.W, pady=(10, 5))

        res_frame = tk.Frame(self.dynamic_frame)
        res_frame.pack(anchor=tk.W)

        tk.Label(res_frame, text="Width:").pack(side=tk.LEFT)
        self.webcam_width = tk.Entry(res_frame, width=10)
        self.webcam_width.insert(0, "1280")
        self.webcam_width.pack(side=tk.LEFT, padx=5)

        tk.Label(res_frame, text="Height:").pack(side=tk.LEFT, padx=(10, 0))
        self.webcam_height = tk.Entry(res_frame, width=10)
        self.webcam_height.insert(0, "720")
        self.webcam_height.pack(side=tk.LEFT, padx=5)

    def build_dataset_options(self):
        """Build TUM dataset selection UI"""
        self.clear_dynamic_frame()

        tk.Label(self.dynamic_frame, text="Dataset Path:", font=("Arial", 9)).pack(anchor=tk.W, pady=5)

        path_frame = tk.Frame(self.dynamic_frame)
        path_frame.pack(fill=tk.X, pady=5)

        self.dataset_path = tk.Entry(path_frame)
        self.dataset_path.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            path_frame,
            text="Browse...",
            command=self.browse_dataset
        ).pack(side=tk.LEFT, padx=5)

        # Quick select buttons for downloaded datasets
        tk.Label(self.dynamic_frame, text="Quick Select:", font=("Arial", 9)).pack(anchor=tk.W, pady=(10, 5))

        datasets = [
            "rgbd_dataset_freiburg1_desk",
            "rgbd_dataset_freiburg1_room",
            "rgbd_dataset_freiburg1_plant",
            "rgbd_dataset_freiburg1_teddy",
        ]

        for ds in datasets:
            btn = tk.Button(
                self.dynamic_frame,
                text=ds,
                command=lambda d=ds: self.select_dataset(d)
            )
            btn.pack(fill=tk.X, pady=2)

    def select_dataset(self, dataset_name):
        """Helper to select a dataset (clears field first)"""
        self.dataset_path.delete(0, tk.END)
        self.dataset_path.insert(0, f"datasets/tum/{dataset_name}/")

    def build_video_options(self):
        """Build video file selection UI"""
        self.clear_dynamic_frame()

        tk.Label(self.dynamic_frame, text="Video File:", font=("Arial", 9)).pack(anchor=tk.W, pady=5)

        path_frame = tk.Frame(self.dynamic_frame)
        path_frame.pack(fill=tk.X, pady=5)

        self.video_path = tk.Entry(path_frame)
        self.video_path.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            path_frame,
            text="Browse...",
            command=self.browse_video
        ).pack(side=tk.LEFT, padx=5)

    def build_folder_options(self):
        """Build image folder watcher UI"""
        self.clear_dynamic_frame()

        tk.Label(
            self.dynamic_frame,
            text="Watch folder for new images from TouchDesigner:",
            font=("Arial", 9)
        ).pack(anchor=tk.W, pady=5)

        path_frame = tk.Frame(self.dynamic_frame)
        path_frame.pack(fill=tk.X, pady=5)

        self.folder_path = tk.Entry(path_frame)
        self.folder_path.insert(0, "/mnt/c/TouchDesigner/frames/")
        self.folder_path.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            path_frame,
            text="Browse...",
            command=self.browse_folder
        ).pack(side=tk.LEFT, padx=5)

        tk.Label(
            self.dynamic_frame,
            text="⚠️ Set TouchDesigner Movie File Out to this folder",
            fg="orange",
            font=("Arial", 9)
        ).pack(anchor=tk.W, pady=10)

    def clear_dynamic_frame(self):
        """Clear dynamic options area"""
        for widget in self.dynamic_frame.winfo_children():
            widget.destroy()

    def on_source_type_changed(self, event=None):
        """Handle source type change"""
        source = self.source_type.get()

        if source == "NDI":
            self.build_ndi_options()
        elif source == "Webcam":
            self.build_webcam_options()
        elif source == "RealSense":
            self.clear_dynamic_frame()
            tk.Label(
                self.dynamic_frame,
                text="RealSense camera will be auto-detected",
                font=("Arial", 10)
            ).pack(pady=20)
        elif source == "TUM Dataset":
            self.build_dataset_options()
        elif source == "Video File":
            self.build_video_options()
        elif source == "Image Folder":
            self.build_folder_options()

    def scan_ndi_sources(self):
        """Scan for NDI sources on network"""
        self.ndi_listbox.delete(0, tk.END)
        self.ndi_listbox.insert(0, "Scanning...")

        def scan():
            try:
                from mast3r_slam.live_camera import NDICamera

                # Quick scan
                ndi_cam = NDICamera(source_index=0, timeout=2000)
                sources = ndi_cam.list_sources()
                ndi_cam.release()

                # Update listbox
                self.root.after(0, lambda: self.update_ndi_list(sources))

            except Exception as err:
                error_msg = str(err)
                self.root.after(0, lambda: messagebox.showerror(
                    "NDI Error",
                    f"Failed to scan NDI sources:\n{error_msg}\n\nMake sure NDI SDK is installed."
                ))
                self.ndi_listbox.delete(0, tk.END)

        threading.Thread(target=scan, daemon=True).start()

    def update_ndi_list(self, sources):
        """Update NDI source list"""
        self.ndi_listbox.delete(0, tk.END)

        if not sources:
            self.ndi_listbox.insert(0, "No NDI sources found")
        else:
            for src in sources:
                self.ndi_listbox.insert(tk.END, src)

    def browse_dataset(self):
        """Browse for dataset folder"""
        folder = filedialog.askdirectory(initialdir="datasets/tum/")
        if folder:
            self.dataset_path.delete(0, tk.END)
            self.dataset_path.insert(0, folder)

    def browse_video(self):
        """Browse for video file"""
        file = filedialog.askopenfilename(
            filetypes=[("Video files", "*.mp4 *.avi *.mov"), ("All files", "*.*")]
        )
        if file:
            self.video_path.delete(0, tk.END)
            self.video_path.insert(0, file)

    def browse_folder(self):
        """Browse for image folder"""
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path.delete(0, tk.END)
            self.folder_path.insert(0, folder)

    def apply_source(self):
        """Launch SLAM with selected source"""
        source_type = self.source_type.get()

        # Stop any existing process first
        if self.slam_process is not None:
            if messagebox.askyesno("Stop Current Process",
                                  "SLAM is already running. Stop and restart?"):
                self.stop_process()
                time.sleep(0.5)  # Brief pause for cleanup
            else:
                return

        # Build command based on source type
        cmd = self.build_slam_command(source_type)

        if cmd is None:
            messagebox.showerror("Invalid Configuration",
                               "Could not build SLAM command. Check your settings.")
            return

        # Launch process
        self.launch_process(cmd)

    def build_slam_command(self, source_type):
        """Build SLAM command based on source type"""
        # Base command with conda activation
        base_cmd = [
            "bash", "-c",
            "source /home/sep/miniconda3/etc/profile.d/conda.sh && "
            "conda activate mast3r-slam-blackwell && "
        ]

        if source_type == "TUM Dataset":
            dataset_path = self.dataset_path.get().strip()
            if not dataset_path:
                messagebox.showerror("Error", "Please specify dataset path")
                return None

            cmd = base_cmd[2] + f"python main.py --dataset {dataset_path} --config config/calib.yaml"
            self.source_var.set(f"Source: TUM Dataset ({Path(dataset_path).name})")

        elif source_type == "NDI":
            # Get NDI source
            selection = self.ndi_listbox.curselection()
            if selection:
                ndi_source = self.ndi_listbox.get(selection[0])
            else:
                ndi_source = self.ndi_manual_entry.get().strip()

            if not ndi_source:
                messagebox.showerror("Error", "Please select or enter NDI source")
                return None

            cmd = base_cmd[2] + f"python main_live.py --source ndi --ndi-name \"{ndi_source}\" --config config/calib.yaml"
            self.source_var.set(f"Source: NDI ({ndi_source})")

        elif source_type == "Webcam":
            device_id = self.webcam_id.get()
            width = self.webcam_width.get()
            height = self.webcam_height.get()

            cmd = base_cmd[2] + f"python main_live.py --source webcam --device-id {device_id} --width {width} --height {height} --config config/calib.yaml"
            self.source_var.set(f"Source: Webcam (Device {device_id})")

        elif source_type == "Image Folder":
            folder_path = self.folder_path.get().strip()
            if not folder_path:
                messagebox.showerror("Error", "Please specify folder path")
                return None

            cmd = base_cmd[2] + f"python main_live.py --source folder --watch-path \"{folder_path}\" --config config/calib.yaml"
            self.source_var.set(f"Source: Folder Watch ({folder_path})")

        elif source_type == "RealSense":
            cmd = base_cmd[2] + "python main_live.py --source realsense --config config/calib.yaml"
            self.source_var.set("Source: RealSense")

        elif source_type == "Video File":
            video_path = self.video_path.get().strip()
            if not video_path:
                messagebox.showerror("Error", "Please specify video file")
                return None

            cmd = base_cmd[2] + f"python main.py --dataset \"{video_path}\" --config config/calib.yaml"
            self.source_var.set(f"Source: Video ({Path(video_path).name})")

        else:
            return None

        # Add --no-viz flag if checkbox is checked
        if self.disable_viz.get():
            cmd += " --no-viz"

        return ["bash", "-c", cmd]

    def launch_process(self, cmd):
        """Launch SLAM process"""
        with self.process_lock:
            try:
                self.log_console(f"Launching SLAM: {' '.join(cmd[2].split()[-5:])}\n")

                self.slam_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    cwd="/home/sep/MASt3R-SLAM"
                )

                # Update UI
                self.status_var.set("SLAM Running")
                self.pid_var.set(f"PID: {self.slam_process.pid}")
                self.stop_btn.config(state=tk.NORMAL)
                self.restart_btn.config(state=tk.NORMAL)
                self.launch_btn.config(state=tk.DISABLED)

                self.log_console(f"Process started (PID: {self.slam_process.pid})\n")

                # Start output reader thread
                output_thread = threading.Thread(
                    target=self.read_process_output,
                    daemon=True
                )
                output_thread.start()

            except Exception as e:
                self.log_console(f"ERROR: Failed to launch process: {e}\n")
                messagebox.showerror("Launch Failed", f"Could not start SLAM:\n{e}")

    def stop_process(self):
        """Stop running SLAM process"""
        with self.process_lock:
            if self.slam_process is None:
                return

            try:
                self.log_console("\nStopping SLAM process...\n")

                # Try graceful termination first
                self.slam_process.terminate()

                # Wait up to 5 seconds
                try:
                    self.slam_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if still running
                    self.log_console("Process not responding, force killing...\n")
                    self.slam_process.kill()
                    self.slam_process.wait()

                self.log_console("Process stopped.\n")

            except Exception as e:
                self.log_console(f"Error stopping process: {e}\n")

            finally:
                self.slam_process = None
                self.status_var.set("No process running")
                self.pid_var.set("PID: None")
                self.stop_btn.config(state=tk.DISABLED)
                self.restart_btn.config(state=tk.DISABLED)
                self.launch_btn.config(state=tk.NORMAL)

    def restart_process(self):
        """Restart SLAM with same settings"""
        source_type = self.source_type.get()
        self.stop_process()
        time.sleep(0.5)
        self.apply_source()

    def read_process_output(self):
        """Read and display process output"""
        if self.slam_process is None:
            return

        try:
            for line in iter(self.slam_process.stdout.readline, ''):
                if not line:
                    break

                # Log to console
                self.root.after(0, lambda l=line: self.log_console(l))

                # Parse for FPS and keyframe count
                self.root.after(0, lambda l=line: self.parse_output_line(l))

            # Process ended
            return_code = self.slam_process.wait()
            self.root.after(0, lambda: self.on_process_ended(return_code))

        except Exception as e:
            self.root.after(0, lambda: self.log_console(f"\nOutput reader error: {e}\n"))

    def parse_output_line(self, line):
        """Extract FPS and other info from output"""
        # Look for FPS patterns like "FPS: 12.3" or "12.3 fps"
        fps_match = re.search(r'(\d+\.\d+)\s*fps|FPS:\s*(\d+\.\d+)', line, re.IGNORECASE)
        if fps_match:
            fps = fps_match.group(1) or fps_match.group(2)
            self.fps_var.set(f"FPS: {fps}")

        # Look for keyframe count
        kf_match = re.search(r'keyframes?:\s*(\d+)', line, re.IGNORECASE)
        if kf_match:
            self.keyframes_var.set(f"Keyframes: {kf_match.group(1)}")

    def log_console(self, text):
        """Add text to console output"""
        self.console_text.insert(tk.END, text)
        self.console_text.see(tk.END)

    def on_process_ended(self, return_code):
        """Handle process termination"""
        self.log_console(f"\n=== Process ended (exit code: {return_code}) ===\n")
        self.slam_process = None
        self.status_var.set(f"Process ended (exit: {return_code})")
        self.pid_var.set("PID: None")
        self.stop_btn.config(state=tk.DISABLED)
        self.restart_btn.config(state=tk.DISABLED)
        self.launch_btn.config(state=tk.NORMAL)

    def monitor_process_output(self):
        """Background thread to check process status"""
        while self.running:
            time.sleep(1.0)

            with self.process_lock:
                if self.slam_process is not None:
                    poll_result = self.slam_process.poll()
                    if poll_result is not None:
                        # Process died unexpectedly
                        self.root.after(0, lambda: self.on_process_ended(poll_result))

    def run(self):
        """Start the GUI"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def on_close(self):
        """Handle window close"""
        # Stop any running process
        if self.slam_process is not None:
            if messagebox.askyesno("Stop Process",
                                  "SLAM is still running. Stop and exit?"):
                self.stop_process()
            else:
                return

        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    print("=" * 60)
    print("MASt3R-SLAM Process Launcher")
    print("=" * 60)
    print()
    print("This GUI allows you to launch MASt3R-SLAM with different")
    print("camera sources and view live console output.")
    print()
    print("Features:")
    print("  - Launch with TUM datasets, NDI, webcam, image folders")
    print("  - View real-time console output")
    print("  - Stop/restart processes easily")
    print("  - Monitor FPS and keyframe count")
    print()
    print("=" * 60)
    print()

    gui = SLAMControlGUI()
    gui.run()
