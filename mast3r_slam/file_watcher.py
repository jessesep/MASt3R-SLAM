"""File Watcher for TouchDesigner Image Folder Integration

Monitors a folder for new images and provides them to MASt3R-SLAM.
Perfect for TouchDesigner's "Movie File Out TOP" image sequence output.

Features:
- Watches folder for new images (.jpg, .png, .jpeg)
- Maintains frame order
- Handles concurrent file writes
- Configurable polling interval
- Auto-cleanup of processed files (optional)

Usage:
    watcher = ImageFolderWatcher(
        watch_path="/mnt/c/TouchDesigner/frames/",
        poll_interval=0.033  # ~30 FPS
    )

    # Use as dataset
    for timestamp, img in watcher:
        # Process frame
        pass
"""

import os
import time
import glob
import numpy as np
import cv2
from pathlib import Path
from typing import Optional, List
from mast3r_slam.dataloader import MonocularDataset


class ImageFolderWatcher(MonocularDataset):
    """Watch a folder for new images from TouchDesigner

    Compatible with TouchDesigner's Movie File Out TOP:
    - Set output format to Image Sequence
    - Path: C:/TD/frames/frame_$F.jpg
    - Cook type: Realtime
    - MASt3R-SLAM watches /mnt/c/TD/frames/ for new files
    """

    def __init__(self,
                 watch_path: str,
                 poll_interval: float = 0.033,
                 image_exts: List[str] = None,
                 auto_cleanup: bool = False,
                 max_queue_size: int = 30,
                 wait_file_stable: float = 0.05):
        """
        Args:
            watch_path: Directory to monitor for new images
            poll_interval: How often to check for new files (seconds)
            image_exts: List of image extensions to watch
            auto_cleanup: Delete images after processing (careful!)
            max_queue_size: Maximum buffered frames
            wait_file_stable: Wait time to ensure file write complete
        """
        super().__init__()

        self.watch_path = Path(watch_path)
        self.poll_interval = poll_interval
        self.auto_cleanup = auto_cleanup
        self.max_queue_size = max_queue_size
        self.wait_file_stable = wait_file_stable

        if image_exts is None:
            self.image_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        else:
            self.image_exts = image_exts

        # Create watch directory if it doesn't exist
        self.watch_path.mkdir(parents=True, exist_ok=True)

        self.processed_files = set()
        self.frame_queue = []
        self.frame_idx = 0
        self.start_time = time.time()
        self.last_check_time = 0

        print(f"Watching folder: {self.watch_path}")
        print(f"Extensions: {self.image_exts}")
        print(f"Poll interval: {self.poll_interval}s (~{1/self.poll_interval:.1f} FPS max)")

    def __len__(self):
        # Infinite stream
        return 999999

    def scan_for_new_files(self):
        """Scan watch folder for new image files"""
        new_files = []

        for ext in self.image_exts:
            pattern = str(self.watch_path / f"*{ext}")
            files = glob.glob(pattern)

            for filepath in files:
                if filepath not in self.processed_files:
                    new_files.append(filepath)
                    self.processed_files.add(filepath)

        # Sort by modification time (oldest first)
        new_files.sort(key=lambda f: os.path.getmtime(f))

        return new_files

    def wait_for_file_stable(self, filepath: str) -> bool:
        """Wait for file to finish writing

        Returns:
            True if file is stable, False if timeout/error
        """
        if self.wait_file_stable <= 0:
            return True

        try:
            initial_size = os.path.getsize(filepath)
            time.sleep(self.wait_file_stable)
            final_size = os.path.getsize(filepath)

            return initial_size == final_size
        except (OSError, FileNotFoundError):
            return False

    def read_img(self, idx):
        """Read next image from watched folder

        Blocks until new image is available.
        """
        # Check if we need to scan for new files
        current_time = time.time()

        while True:
            # If queue is not empty, return next frame
            if self.frame_queue:
                filepath = self.frame_queue.pop(0)

                # Wait for file to be fully written
                if not self.wait_for_file_stable(filepath):
                    print(f"Warning: File may still be writing: {filepath}")

                # Read image
                try:
                    img = cv2.imread(filepath)
                    if img is None:
                        print(f"Warning: Failed to read {filepath}, skipping")
                        continue

                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                    # Optionally delete file after reading
                    if self.auto_cleanup:
                        try:
                            os.remove(filepath)
                        except OSError as e:
                            print(f"Warning: Failed to delete {filepath}: {e}")

                    return img_rgb

                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
                    continue

            # Queue is empty, scan for new files
            if current_time - self.last_check_time >= self.poll_interval:
                new_files = self.scan_for_new_files()

                if new_files:
                    # Add to queue (limit size)
                    for filepath in new_files[:self.max_queue_size]:
                        self.frame_queue.append(filepath)

                    print(f"Found {len(new_files)} new image(s)")

                self.last_check_time = current_time

            # Small sleep to avoid busy waiting
            time.sleep(0.01)
            current_time = time.time()

    def __getitem__(self, idx):
        """Get next frame (blocks until available)"""
        img = self.read_img(idx)

        # Create timestamp
        timestamp = time.time() - self.start_time

        self.frame_idx += 1

        return timestamp, img


class ImageSequenceDataset(MonocularDataset):
    """Load existing image sequence (non-watching mode)

    For processing pre-recorded TouchDesigner sequences.
    """

    def __init__(self, sequence_path: str, fps: float = 30.0):
        """
        Args:
            sequence_path: Directory containing image sequence
            fps: Assumed frame rate for timestamps
        """
        super().__init__()

        self.sequence_path = Path(sequence_path)
        self.fps = fps
        self.frame_interval = 1.0 / fps

        # Find all images
        self.image_files = []
        for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
            pattern = str(self.sequence_path / f"*{ext}")
            self.image_files.extend(glob.glob(pattern))

        # Sort by filename (assumes numeric naming like frame_0001.jpg)
        self.image_files.sort()

        if not self.image_files:
            raise ValueError(f"No images found in {sequence_path}")

        print(f"Loaded {len(self.image_files)} images from {sequence_path}")
        print(f"FPS: {fps}, Duration: {len(self.image_files) / fps:.2f}s")

    def __len__(self):
        return len(self.image_files)

    def read_img(self, idx):
        """Read image at index"""
        if idx >= len(self.image_files):
            raise StopIteration

        filepath = self.image_files[idx]
        img = cv2.imread(filepath)

        if img is None:
            raise ValueError(f"Failed to read {filepath}")

        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    def __getitem__(self, idx):
        """Get frame at index"""
        img = self.read_img(idx)
        timestamp = idx * self.frame_interval

        return timestamp, img
