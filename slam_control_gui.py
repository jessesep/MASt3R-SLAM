#!/usr/bin/env python3
"""
MASt3R-SLAM Control GUI
-----------------------
Separate control panel for switching camera sources on the fly.
Works on WSL2 where ImGui input doesn't work!

Features:
- Switch between camera sources (NDI, Webcam, Files, Datasets)
- Control SLAM parameters
- Monitor FPS and status
- Select NDI sources from dropdown
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import time
import json
import socket
from pathlib import Path


class SLAMControlGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MASt3R-SLAM Control Panel")
        self.root.geometry("600x800")

        # Command queue for SLAM process
        self.command_queue = queue.Queue()

        # Status variables
        self.status_var = tk.StringVar(value="Ready")
        self.fps_var = tk.StringVar(value="FPS: 0.0")
        self.source_var = tk.StringVar(value="No source")
        self.keyframes_var = tk.StringVar(value="Keyframes: 0")

        self.create_ui()

        # Start status update thread
        self.running = True
        self.status_thread = threading.Thread(target=self.update_status, daemon=True)
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
        status_frame = tk.LabelFrame(self.root, text="Status", padx=10, pady=10)
        status_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(status_frame, textvariable=self.status_var, font=("Arial", 10)).pack(anchor=tk.W)
        tk.Label(status_frame, textvariable=self.fps_var, font=("Arial", 10)).pack(anchor=tk.W)
        tk.Label(status_frame, textvariable=self.source_var, font=("Arial", 10)).pack(anchor=tk.W)
        tk.Label(status_frame, textvariable=self.keyframes_var, font=("Arial", 10)).pack(anchor=tk.W)

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

        # Apply button
        apply_btn = tk.Button(
            source_frame,
            text="🎬 Apply Source",
            command=self.apply_source,
            bg="#27ae60",
            fg="white",
            font=("Arial", 12, "bold"),
            height=2
        )
        apply_btn.pack(fill=tk.X, pady=10)

        # ===== SLAM CONTROLS =====
        control_frame = tk.LabelFrame(self.root, text="SLAM Controls", padx=10, pady=10)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        btn_frame = tk.Frame(control_frame)
        btn_frame.pack(fill=tk.X)

        tk.Button(
            btn_frame,
            text="⏸️ Pause",
            command=self.pause_slam,
            width=12
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="▶️ Resume",
            command=self.resume_slam,
            width=12
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="🔄 Reset",
            command=self.reset_slam,
            width=12
        ).pack(side=tk.LEFT, padx=5)

        # Save controls
        save_frame = tk.Frame(control_frame)
        save_frame.pack(fill=tk.X, pady=10)

        tk.Button(
            save_frame,
            text="💾 Save PLY",
            command=self.save_ply,
            width=12
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            save_frame,
            text="📸 Save Keyframes",
            command=self.save_keyframes,
            width=12
        ).pack(side=tk.LEFT, padx=5)

        # ===== SETTINGS =====
        settings_frame = tk.LabelFrame(self.root, text="Settings", padx=10, pady=10)
        settings_frame.pack(fill=tk.X, padx=10, pady=10)

        # Subsample
        subsample_frame = tk.Frame(settings_frame)
        subsample_frame.pack(fill=tk.X, pady=5)

        tk.Label(subsample_frame, text="Subsample:").pack(side=tk.LEFT)
        self.subsample_var = tk.IntVar(value=2)
        subsample_spin = tk.Spinbox(
            subsample_frame,
            from_=1,
            to=10,
            textvariable=self.subsample_var,
            width=10
        )
        subsample_spin.pack(side=tk.LEFT, padx=5)

        # Confidence threshold
        conf_frame = tk.Frame(settings_frame)
        conf_frame.pack(fill=tk.X, pady=5)

        tk.Label(conf_frame, text="Confidence Threshold:").pack(side=tk.LEFT)
        self.conf_var = tk.DoubleVar(value=0.5)
        conf_spin = tk.Spinbox(
            conf_frame,
            from_=0.0,
            to=1.0,
            increment=0.1,
            textvariable=self.conf_var,
            width=10
        )
        conf_spin.pack(side=tk.LEFT, padx=5)

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
                command=lambda d=ds: self.dataset_path.insert(0, f"datasets/tum/{d}/")
            )
            btn.pack(fill=tk.X, pady=2)

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
        """Apply selected source to SLAM"""
        source_type = self.source_type.get()

        command = {
            "action": "change_source",
            "type": source_type,
            "subsample": self.subsample_var.get(),
            "conf_threshold": self.conf_var.get()
        }

        if source_type == "NDI":
            # Get selected or manual entry
            selection = self.ndi_listbox.curselection()
            if selection:
                command["source"] = self.ndi_listbox.get(selection[0])
            else:
                command["source"] = self.ndi_manual_entry.get()

        elif source_type == "Webcam":
            command["device_id"] = int(self.webcam_id.get())
            command["width"] = int(self.webcam_width.get())
            command["height"] = int(self.webcam_height.get())

        elif source_type == "TUM Dataset":
            command["path"] = self.dataset_path.get()

        elif source_type == "Video File":
            command["path"] = self.video_path.get()

        elif source_type == "Image Folder":
            command["path"] = self.folder_path.get()

        self.send_command(command)
        self.status_var.set(f"Switching to {source_type}...")

    def pause_slam(self):
        """Pause SLAM processing"""
        self.send_command({"action": "pause"})
        self.status_var.set("Paused")

    def resume_slam(self):
        """Resume SLAM processing"""
        self.send_command({"action": "resume"})
        self.status_var.set("Running")

    def reset_slam(self):
        """Reset SLAM (clear map)"""
        if messagebox.askyesno("Reset SLAM", "Clear all keyframes and restart?"):
            self.send_command({"action": "reset"})
            self.status_var.set("Reset")
            self.keyframes_var.set("Keyframes: 0")

    def save_ply(self):
        """Save current reconstruction as PLY"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".ply",
            filetypes=[("PLY files", "*.ply"), ("All files", "*.*")]
        )
        if filename:
            self.send_command({"action": "save_ply", "path": filename})
            messagebox.showinfo("Save", f"Saving reconstruction to:\n{filename}")

    def save_keyframes(self):
        """Save keyframe images"""
        folder = filedialog.askdirectory()
        if folder:
            self.send_command({"action": "save_keyframes", "path": folder})
            messagebox.showinfo("Save", f"Saving keyframes to:\n{folder}")

    def send_command(self, command):
        """Send command to SLAM process via socket"""
        try:
            # Send via UDP socket to localhost:9999
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            msg = json.dumps(command).encode('utf-8')
            sock.sendto(msg, ('127.0.0.1', 9999))
            sock.close()
            print(f"Sent command: {command}")
        except Exception as e:
            print(f"Failed to send command: {e}")

    def update_status(self):
        """Update status from SLAM process"""
        # Listen for status updates on port 10000
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('127.0.0.1', 10000))
        sock.settimeout(1.0)

        while self.running:
            try:
                data, addr = sock.recvfrom(4096)
                status = json.loads(data.decode('utf-8'))

                # Update UI
                self.root.after(0, lambda: self.update_ui_status(status))

            except socket.timeout:
                continue
            except Exception as e:
                print(f"Status update error: {e}")

        sock.close()

    def update_ui_status(self, status):
        """Update UI with status info"""
        if "fps" in status:
            self.fps_var.set(f"FPS: {status['fps']:.1f}")
        if "keyframes" in status:
            self.keyframes_var.set(f"Keyframes: {status['keyframes']}")
        if "source" in status:
            self.source_var.set(f"Source: {status['source']}")
        if "status" in status:
            self.status_var.set(status['status'])

    def run(self):
        """Start the GUI"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def on_close(self):
        """Handle window close"""
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    print("Starting MASt3R-SLAM Control GUI...")
    print("This control panel communicates with SLAM via UDP ports 9999/10000")

    gui = SLAMControlGUI()
    gui.run()
