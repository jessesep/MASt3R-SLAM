# MASt3R-SLAM Live Camera & TouchDesigner Integration

Complete guide for feeding live camera input to MASt3R-SLAM and integrating with TouchDesigner!

## Quick Start Options

### Option 1: Webcam (Easiest - Works Now!)

MASt3R-SLAM already has webcam support built-in!

```bash
python main.py --dataset webcam --config config/calib.yaml
```

That's it! Your webcam will feed live video into MASt3R-SLAM with real-time 3D reconstruction.

### Option 2: MP4 Video File

Process any video file:

```bash
python main.py --dataset /path/to/video.mp4 --config config/calib.yaml
```

### Option 3: TouchDesigner → NDI → MASt3R-SLAM

**TouchDesigner Setup:**
1. Add **NDI Out TOP** to your network
2. Set output name: "TouchDesigner_SLAM"
3. Enable NDI output

**MASt3R-SLAM Setup:**

Install NDI SDK first:
```bash
# Download NDI SDK from: https://ndi.tv/sdk/
# Extract and install for Linux

# Then install Python NDI
pip install ndi-python
```

**Use NDI Camera:**
```python
from mast3r_slam.live_camera import create_live_camera

# Create NDI camera
camera = create_live_camera("ndi", source_name="TouchDesigner_SLAM")

# Run SLAM
python main_live.py --camera ndi --ndi-source "TouchDesigner_SLAM"
```

### Option 4: TouchDesigner → File Watching (No NDI Required!)

**Easiest TouchDesigner integration without NDI:**

**TouchDesigner Setup:**
1. Add **Movie File Out TOP**
2. Output format: Image Sequence
3. Path: `C:/SLAM/frames/frame_$F.jpg`
4. Cook type: Realtime

**MASt3R-SLAM watches folder:**
```python
python main_live.py --camera folder --watch-path /mnt/c/SLAM/frames/
```

This polls the folder for new images and processes them in real-time!

---

## Detailed Setup Guides

### 1. Webcam Live SLAM

The simplest option - uses any USB webcam or laptop camera.

**Update dataloader.py:** (already implemented!)

The `Webcam` class is already in `mast3r_slam/dataloader.py:206-228`

**Run it:**
```bash
cd /home/sep/MASt3R-SLAM
conda activate mast3r-slam-blackwell
python main.py --dataset webcam --config config/calib.yaml
```

**Features:**
- Auto-detects default camera (device 0)
- Runs at 30 FPS
- Real-time 3D reconstruction
- GUI shows live point cloud building

---

### 2. TouchDesigner Integration Workflows

#### Method A: Spout/Syphon (Windows/Mac)

**TouchDesigner:**
- Output via **Spout Out TOP** (Windows) or **Syphon Out TOP** (Mac)

**MASt3R-SLAM side:**
- Use `SpoutToCV2` or similar bridge to capture frames
- Feed into webcam-style pipeline

**Install Spout for Python:**
```bash
pip install SpoutGL  # Windows only
```

**Create Spout receiver:**
```python
from SpoutGL.SpoutSDK import SpoutReceiver
import numpy as np

spout = SpoutReceiver()
spout.setReceiverName("TouchDesigner")

# In frame capture loop:
frame = spout.receiveImage(...)
```

#### Method B: File Watching (Cross-Platform, No Dependencies!)

**TouchDesigner network:**
```
Camera/Video Input → Movie File Out TOP
```

**Settings:**
- Format: PNG or JPG sequence
- Output path: `/path/to/shared/frames/`
- Filename: `frame_$F.png` (auto-increments)
- Cook type: Realtime

**MASt3R-SLAM File Watcher:**

Create `/home/sep/MASt3R-SLAM/live_file_watcher.py`:

```python
#!/usr/bin/env python3
"""Watch a folder for new images and run SLAM"""

import time
import pathlib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import cv2

class ImageHandler(FileSystemEventHandler):
    def __init__(self, slam_processor):
        self.slam = slam_processor
        self.processed = set()

    def on_created(self, event):
        if event.is_directory:
            return

        path = pathlib.Path(event.src_path)
        if path.suffix.lower() in ['.jpg', '.png', '.jpeg']:
            if path not in self.processed:
                time.sleep(0.1)  # Wait for file write complete
                img = cv2.imread(str(path))
                if img is not None:
                    self.slam.process_frame(img)
                    self.processed.add(path)

# Usage:
# python live_file_watcher.py --watch-path /mnt/c/TouchDesigner/frames/
```

#### Method C: OSC Communication (Lightweight Control)

**TouchDesigner sends OSC messages** to trigger MASt3R-SLAM:

```python
# In TouchDesigner CHOP Execute:
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(b'/slam/capture', ('127.0.0.1', 9000))
```

**MASt3R-SLAM OSC receiver:**
```python
from pythonosc import udp_client, dispatcher, osc_server

def capture_frame(unused_addr):
    # Trigger frame capture
    pass

disp = dispatcher.Dispatcher()
disp.map("/slam/capture", capture_frame)

server = osc_server.ThreadingOSCUDPServer(('127.0.0.1', 9000), disp)
server.serve_forever()
```

---

### 3. Intel RealSense Camera (Best for SLAM!)

**Why RealSense?**
- Provides RGB + Depth
- Perfect for SLAM
- Wide field of view
- USB powered

**Already supported!** See `RealSenseCamera` class in dataloader.py (lines 160-205)

**Run it:**
```bash
python main.py --dataset realsense --config config/calib.yaml
```

---

## Live SLAM Main Script

Create `/home/sep/MASt3R-SLAM/main_live.py`:

```python
#!/usr/bin/env python3
"""Run MASt3R-SLAM with live camera input"""

import argparse
from mast3r_slam.dataloader import Webcam, RealSenseCamera
from mast3r_slam.config import load_config
# ... rest of main.py imports

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", default="webcam", choices=["webcam", "realsense"])
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--device-id", type=int, default=0, help="Webcam device ID")
    parser.add_argument("--max-frames", type=int, default=None, help="Max frames to process")
    parser.add_argument("--save-output", action="store_true", help="Save PLY reconstruction")

    args = parser.parse_args()

    load_config(args.config)

    # Create live camera dataset
    if args.camera == "webcam":
        dataset = Webcam()
    elif args.camera == "realsense":
        dataset = RealSenseCamera()

    # Limit frames if specified
    if args.max_frames:
        dataset.save_results = args.save_output

    # Run SLAM (same as main.py)
    # ... rest of main.py logic
```

**Usage:**
```bash
# Webcam
python main_live.py --camera webcam

# RealSense
python main_live.py --camera realsense

# Webcam, max 1000 frames, save PLY
python main_live.py --camera webcam --max-frames 1000 --save-output
```

---

## TouchDesigner → MASt3R-SLAM → TouchDesigner Loop

**Full creative pipeline:**

```
TouchDesigner (Camera/Generative)
    ↓ (NDI/Spout/Files)
MASt3R-SLAM (Real-time 3D Reconstruction)
    ↓ (OSC point cloud data)
TouchDesigner (3D Visualization/VJ)
```

**TouchDesigner receives SLAM data via OSC** (from TOUCHDESIGNER_INTEGRATION.md)

This creates a live feedback loop where TouchDesigner can:
- Send live video to SLAM
- Receive 3D point cloud back
- Visualize/manipulate the reconstruction
- Generate new content based on SLAM output

---

## Performance Tips

### For Best Real-Time Performance:

1. **Lower Resolution**
   - 640x480 or 1280x720 works great
   - Higher res = slower processing

2. **Adjust Subsampling**
   ```yaml
   # config/live.yaml
   dataset:
     subsample: 1  # Process every frame (30 FPS input)
     subsample: 2  # Process every 2nd frame (15 FPS effective)
   ```

3. **WSL2 Performance**
   - Expect ~9 FPS on WSL2
   - Run on native Linux for ~18 FPS

4. **GPU Utilization**
   - RTX 5090 is OVERKILL for this (in a good way!)
   - Should handle 1080p @ 30 FPS easily on native Linux

---

## Troubleshooting

### Webcam not found (WSL2)
WSL2 doesn't have direct USB access. Options:
1. **USBIPD** - Share USB from Windows to WSL2
   ```bash
   # On Windows PowerShell (Admin):
   usbipd list
   usbipd bind --busid <BUSID>
   usbipd attach --wsl --busid <BUSID>
   ```

2. **Use TouchDesigner** on Windows → Stream to WSL2

3. **Use IP camera/stream** instead of USB

### No NDI sources found
- Check firewall (port 5353 UDP, 5960-5969 TCP)
- Ensure TouchDesigner and SLAM on same network
- Try `source_name` instead of `source_index`

### Camera opened but no frames
- Check camera permissions
- Try different device ID: `--device-id 1`, `--device-id 2`, etc.
- Verify camera works: `ffplay /dev/video0`

---

## Examples

### Example 1: Quick Webcam Test
```bash
cd /home/sep/MASt3R-SLAM
python main.py --dataset webcam --config config/calib.yaml
```
Move the webcam around your room - watch 3D reconstruction build!

### Example 2: TouchDesigner → File → SLAM
**TD Network:**
```
Video Device In → Movie File Out TOP
  Output: /mnt/c/slam_frames/frame_####.jpg
  Realtime: ON
```

**SLAM:**
```bash
# Watch folder and process new images
python live_file_watcher.py --watch /mnt/c/slam_frames/
```

### Example 3: Long Recording Session
```bash
# Webcam, 10000 frames max, save everything
python main_live.py \
  --camera webcam \
  --max-frames 10000 \
  --save-output \
  --config config/calib.yaml
```
Output: `results/webcam/live_session.ply`

---

## Next Steps

1. **Test webcam first** - simplest setup
2. **Try TouchDesigner file watching** - no NDI needed
3. **Implement OSC streaming** - get point cloud back to TD
4. **Create live installation** - SLAM → 3D viz → projections

You now have everything to build a **live 3D reconstruction pipeline** from any video source!

**LET'S BUILD SOMETHING COOL!** 🚀
