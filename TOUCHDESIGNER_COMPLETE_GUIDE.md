# Complete TouchDesigner + MASt3R-SLAM Integration Guide

**Real-time 3D reconstruction from TouchDesigner with live point cloud streaming back to TD!**

This guide shows you how to create a complete feedback loop:
- TouchDesigner → MASt3R-SLAM (via NDI or file output)
- MASt3R-SLAM → TouchDesigner (via OSC point cloud streaming)

## Quick Start

### Method 1: File Watching (Easiest, No NDI SDK Required!)

**TouchDesigner Setup:**
1. Add **Movie File Out TOP**
2. Settings:
   - Output: Image Sequence
   - Path: `C:/SLAM/frames/frame_$F.jpg`
   - Format: JPEG
   - Cook Type: Realtime
   - Create Output Path: ON

**MASt3R-SLAM:**
```bash
# Install python-osc for point cloud streaming back to TD
pip install python-osc

# Run SLAM with file watching + OSC streaming
python main_live.py \
    --source folder \
    --watch-path /mnt/c/SLAM/frames/ \
    --osc-enable \
    --osc-port 9001
```

**TouchDesigner Receive Point Cloud:**
1. Add **OSC In DAT**
2. Set Port: 9001
3. See "OSC Message Format" below for parsing

**Done!** You now have a complete feedback loop.

---

## Method 2: NDI (Best Quality, Requires NDI SDK)

**Prerequisites:**
```bash
# Download NDI SDK: https://ndi.tv/sdk/
# Install for Linux on WSL2

# Install ndi-python
pip install ndi-python
```

**TouchDesigner:**
1. Add **NDI Out TOP**
2. Name: "TouchDesigner_SLAM"
3. Enable output

**MASt3R-SLAM:**
```bash
python main_live.py \
    --source ndi \
    --ndi-name "TouchDesigner_SLAM" \
    --osc-enable \
    --osc-port 9001
```

---

## Method 3: Webcam (Simple Testing)

```bash
python main_live.py \
    --source webcam \
    --osc-enable \
    --osc-port 9001
```

---

## Using the Control GUI

The Control GUI lets you control SLAM without command-line parameters:

**Launch Control GUI:**
```bash
python slam_control_gui.py
```

**Launch SLAM (in separate terminal):**
```bash
python main_live.py --source webcam
```

The Control GUI automatically connects via UDP (port 9999) and lets you:
- Pause/Resume processing
- Reset SLAM
- Save PLY files
- Save keyframe images
- Monitor FPS and status

**Control GUI works with both `main.py` and `main_live.py`!**

---

## OSC Point Cloud Streaming

MASt3R-SLAM streams point cloud data back to TouchDesigner via OSC.

### OSC Message Format

**Point Cloud Batches:**
```
/slam/cloud/start [num_points]
/slam/cloud/batch [x1, y1, z1, r1, g1, b1, conf1, x2, y2, z2, ...]
/slam/cloud/batch [...]
/slam/cloud/end []
```

**Camera Pose:**
```
/slam/camera/position [x, y, z]
/slam/camera/rotation [m00, m01, m02, m10, m11, m12, m20, m21, m22]
```

**Status Updates:**
```
/slam/status/fps [fps_value]
/slam/status/keyframes [num_keyframes]
/slam/status/points [num_points]
```

### TouchDesigner OSC Receiver Setup

**Basic OSC In:**
1. Add **OSC In DAT**
2. Port: 9001
3. All Messages: ON

**Parse Point Cloud (Python Script):**
```python
# In Execute DAT connected to OSC In DAT

def onReceiveOSC(dat, rowIndex, message, bytes):
    address = message[0]
    args = message[2:]

    if address == '/slam/cloud/start':
        # Clear previous point cloud
        op('point_table').clear()
        print(f"Receiving {args[0]} points")

    elif address == '/slam/cloud/batch':
        # Parse batch: [x, y, z, r, g, b, conf, ...]
        for i in range(0, len(args), 7):
            x, y, z = args[i:i+3]
            r, g, b = args[i+3:i+6]
            conf = args[i+6]

            # Add to table
            op('point_table').appendRow([x, y, z, r, g, b, conf])

    elif address == '/slam/cloud/end':
        print("Point cloud complete")
        # Update SOP geometry
        op('points_sop').par.refresh.pulse()
```

**Visualize as 3D Points:**
1. Create **Table DAT** (name: 'point_table')
2. Create **SOP** to convert table to points
3. Add **Geometry COMP** to render

---

## Complete Workflow Examples

### Example 1: Generative Art Feedback Loop

**TouchDesigner Network:**
```
[Noise TOP] → [Feedback] → [NDI Out] → MASt3R-SLAM
                  ↑                           ↓
                  └─────── [OSC In] ← [Point Cloud]
                               ↓
                        [3D Visualization]
```

**Steps:**
1. Generate animated patterns in TD
2. Stream to SLAM via NDI
3. SLAM builds 3D reconstruction
4. Point cloud streams back to TD
5. Use 3D data to influence pattern generation
6. **Infinite creative feedback loop!**

### Example 2: Live Performance Capture

```bash
# SLAM side
python main_live.py \
    --source ndi \
    --ndi-name "Camera_Feed" \
    --osc-enable \
    --osc-port 9001 \
    --save-ply
```

**TouchDesigner:**
- Camera input → NDI Out
- OSC In → Real-time point cloud viz
- Record both video + 3D reconstruction

### Example 3: Multi-Camera Setup

```bash
# Camera 1
python main_live.py --source webcam --device-id 0 --osc-port 9001

# Camera 2
python main_live.py --source webcam --device-id 1 --osc-port 9002
```

**TouchDesigner:** Receive point clouds from both cameras on different ports!

---

## All Command-Line Options

```bash
python main_live.py --help
```

**Camera Sources:**
- `--source webcam` - USB webcam
- `--source ndi` - NDI input
- `--source realsense` - Intel RealSense
- `--source rtsp` - RTSP stream
- `--source folder` - Watch folder for images
- `--source sequence` - Pre-recorded image sequence

**Camera Settings:**
- `--device-id N` - Webcam device (default: 0)
- `--ndi-name "Name"` - NDI source name
- `--rtsp-url "rtsp://..."` - RTSP URL
- `--watch-path /path/` - Folder to watch
- `--width W --height H` - Resolution
- `--fps FPS` - Frame rate

**OSC Streaming:**
- `--osc-enable` - Enable OSC output
- `--osc-host IP` - OSC destination (default: localhost)
- `--osc-port PORT` - OSC port (default: 9001)
- `--osc-downsample N` - Send every Nth point

**Processing:**
- `--config path.yaml` - SLAM config file
- `--max-frames N` - Limit frames
- `--no-viz` - Disable visualization

**Output:**
- `--save-ply` - Save point cloud on exit
- `--output-dir path` - Output directory

---

## Troubleshooting

### WSL2: File watching not working
```bash
# Make sure Windows path is mounted
ls /mnt/c/SLAM/frames/

# Check permissions
chmod 755 /mnt/c/SLAM/frames/
```

### TouchDesigner OSC not receiving
- Check firewall (Windows + WSL2)
- Verify port 9001 is open
- Try localhost (127.0.0.1) first
- Check OSC In DAT "Messages" tab for incoming data

### NDI sources not found
```bash
# Test NDI discovery
python -c "from mast3r_slam.live_camera import NDICamera; cam = NDICamera()"
```

- Ensure TouchDesigner and WSL2 on same network
- Check NDI SDK installed correctly
- Try manual source name instead of auto-discovery

### Low FPS / Performance
- Reduce resolution: `--width 1280 --height 720`
- Increase OSC downsample: `--osc-downsample 20`
- Run on native Linux (not WSL2) for ~2x speedup
- Use `--no-viz` to disable visualization overhead

### Control GUI doesn't affect SLAM
- Make sure you're using `main_live.py`, not `main.py`
- Check port 9999 isn't blocked
- Restart SLAM after launching Control GUI

---

## Performance Tips

**Best Performance:**
```bash
# Native Linux, no viz, subsampled OSC
python main_live.py \
    --source webcam \
    --width 1280 --height 720 \
    --osc-enable --osc-downsample 50 \
    --no-viz
```

**Expected FPS:**
- WSL2 RTX 5090: ~9-12 FPS (1080p)
- Native Linux RTX 5090: ~18-20 FPS (1080p)
- Native Linux RTX 5090: ~30+ FPS (720p)

---

## File Structure

```
MASt3R-SLAM/
├── main_live.py              # Live camera SLAM with OSC streaming
├── slam_control_gui.py       # Control GUI (works with main_live.py)
├── mast3r_slam/
│   ├── live_camera.py        # Camera input sources (NDI, webcam, etc.)
│   ├── file_watcher.py       # Image folder monitoring
│   ├── osc_streamer.py       # OSC point cloud streaming
│   └── command_listener.py   # UDP command receiver (for Control GUI)
├── TOUCHDESIGNER_COMPLETE_GUIDE.md  # This file!
├── LIVE_CAMERA_SETUP.md             # Camera setup details
└── CONTROL_GUI_GUIDE.md             # Control GUI usage
```

---

## Next Steps

1. **Start Simple:** Test webcam + OSC streaming
2. **Add TouchDesigner:** Receive point cloud via OSC
3. **Go Live:** Switch to NDI or file watching
4. **Get Creative:** Build feedback loops!

---

## Example TouchDesigner Networks

See `touchdesigner_examples/` directory for `.toe` files:
- `basic_osc_receiver.toe` - Simple OSC point cloud viewer
- `generative_feedback_loop.toe` - Full creative feedback example
- `multi_camera_merge.toe` - Multiple SLAM instances combined

---

## Resources

- **MASt3R Paper:** https://github.com/naver/mast3r
- **NDI SDK:** https://ndi.tv/sdk/
- **TouchDesigner:** https://derivative.ca/
- **python-osc:** https://pypi.org/project/python-osc/

---

**Questions? Issues?**
- GitHub Issues: https://github.com/jessesep/MASt3R-SLAM/issues
- Branch: `touchdesigner-integration`

**Happy SLAMming in TouchDesigner! 🎨🤖**
