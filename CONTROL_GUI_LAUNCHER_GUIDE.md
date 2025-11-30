# MASt3R-SLAM Control GUI - Process Launcher

**Complete process launcher for MASt3R-SLAM with live console output and process management!**

## What Changed

The Control GUI has been completely rewritten from a UDP command sender to a full **process launcher and manager**. This means you can now:

1. **Launch MASt3R-SLAM** with different sources directly from the GUI
2. **See live console output** from SLAM in the GUI
3. **Stop and restart** processes easily
4. **Monitor FPS and keyframe count** parsed from console output

## Quick Start

```bash
# Launch the Control GUI
python slam_control_gui.py
```

The GUI will open. From there you can:

1. Select a source type (TUM Dataset, NDI, Webcam, Image Folder, etc.)
2. Configure source-specific settings
3. Click **"Launch SLAM"** to start the process
4. Watch live console output in the black terminal area
5. Click **"Stop Process"** or **"Restart"** as needed

## Features

### Process Management
- **Launch SLAM** with correct command-line arguments based on GUI selections
- **Stop running processes** gracefully (5 second timeout, then force kill)
- **Restart** with same settings
- **View process PID** and status
- **Automatic process monitoring** - GUI detects if process crashes

### Live Console Output
- **Real-time terminal output** displayed in GUI
- **Auto-scrolling** to latest output
- **FPS parsing** - automatically extracts FPS from output
- **Keyframe count parsing** - shows number of keyframes
- **Syntax highlighting** - green text on black background (terminal style)
- **Clear console** button to reset output

### Source Types Supported

#### 1. TUM Dataset (Uses main.py)
```bash
# GUI builds this command:
python main.py --dataset <path> --config config/calib.yaml
```

**Setup:**
- Select "TUM Dataset" from dropdown
- Click "Browse" or use quick-select buttons
- Example: `datasets/tum/rgbd_dataset_freiburg1_desk/`

#### 2. NDI (Uses main_live.py - requires NDI SDK)
```bash
# GUI builds this command:
python main_live.py --source ndi --ndi-name "<name>" --config config/calib.yaml
```

**Setup:**
- Select "NDI" from dropdown
- Click "Scan Network" to find TouchDesigner sources
- Or enter NDI source name manually
- Example: `TouchDesigner Output`

#### 3. Webcam (Uses main_live.py)
```bash
# GUI builds this command:
python main_live.py --source webcam --device-id 0 --width 1280 --height 720 --config config/calib.yaml
```

**Setup:**
- Select "Webcam" from dropdown
- Choose device ID (0 = default camera)
- Set resolution (default: 1280x720)

#### 4. Image Folder (Uses main_live.py - for TouchDesigner file output)
```bash
# GUI builds this command:
python main_live.py --source folder --watch-path "<path>" --config config/calib.yaml
```

**Setup:**
- Select "Image Folder" from dropdown
- Browse to folder where TouchDesigner saves images
- Example: `/mnt/c/TouchDesigner/frames/`
- In TouchDesigner: Use "Movie File Out TOP" to save images to this folder

#### 5. RealSense (Uses main_live.py - requires Intel RealSense camera)
```bash
# GUI builds this command:
python main_live.py --source realsense --config config/calib.yaml
```

**Setup:**
- Select "RealSense" from dropdown
- Camera will be auto-detected

#### 6. Video File (Uses main_live.py)
```bash
# GUI builds this command:
python main_live.py --source rtsp --rtsp-url "<path>" --config config/calib.yaml
```

**Setup:**
- Select "Video File" from dropdown
- Browse to video file (MP4, AVI, MOV, etc.)

## GUI Layout

```
┌─────────────────────────────────────────────┐
│       MASt3R-SLAM Control Panel             │
├─────────────────────────────────────────────┤
│ Process Status:                             │
│   SLAM Running                              │
│   PID: 12345                                │
│   FPS: 11.8                                 │
│   Source: TUM Dataset (desk)                │
│   Keyframes: 47                             │
│   [Stop Process] [Restart]                  │
├─────────────────────────────────────────────┤
│ Camera Source:                              │
│   Source Type: [TUM Dataset ▼]             │
│                                             │
│   [Dynamic source-specific options]         │
│                                             │
│   [🚀 Launch SLAM]                          │
├─────────────────────────────────────────────┤
│ SLAM Console Output:                        │
│ ┌─────────────────────────────────────────┐ │
│ │ Loading config: config/calib.yaml       │ │
│ │ Loading MASt3R model...                 │ │
│ │ Model loaded: MASt3R ViT-Large          │ │
│ │ Processing frame 47/572 - FPS: 11.8     │ │
│ │ Keyframes: 47                           │ │
│ │ █                                       │ │
│ └─────────────────────────────────────────┘ │
│   [Clear Console]                           │
└─────────────────────────────────────────────┘
```

## How It Works

### Command Building
When you click "Launch SLAM", the GUI:

1. **Validates settings** - Checks that required fields are filled
2. **Builds bash command** - Creates complete command with conda activation:
   ```bash
   bash -c "source /path/to/conda.sh && conda activate mast3r-slam-blackwell && python ..."
   ```
3. **Launches subprocess** - Uses `subprocess.Popen` with stdout capture
4. **Updates UI** - Enables Stop/Restart buttons, disables Launch button

### Process Monitoring
The GUI runs two background threads:

1. **Output reader thread** - Reads stdout line-by-line:
   - Displays in console widget
   - Parses FPS using regex: `r'(\d+\.\d+)\s*fps|FPS:\s*(\d+\.\d+)'`
   - Parses keyframes using regex: `r'keyframes?:\s*(\d+)'`
   - Detects when process ends

2. **Status monitor thread** - Checks process status every second:
   - Calls `process.poll()` to check if alive
   - Updates GUI if process crashes unexpectedly

### Process Termination
When you click "Stop Process":

1. **Send SIGTERM** - Graceful shutdown signal
2. **Wait 5 seconds** - Gives process time to clean up
3. **Force SIGKILL** - If still running after 5 seconds
4. **Update GUI** - Reset buttons and status

## Example Usage

### Example 1: Run TUM Dataset
1. Launch Control GUI: `python slam_control_gui.py`
2. Source Type: "TUM Dataset"
3. Click "rgbd_dataset_freiburg1_desk" quick-select button
4. Click "Launch SLAM"
5. Watch console output in real-time
6. When done, click "Stop Process"

### Example 2: Run with TouchDesigner NDI
1. In TouchDesigner: Add "NDI Out TOP", name it "TD_SLAM", enable
2. Launch Control GUI: `python slam_control_gui.py`
3. Source Type: "NDI"
4. Click "Scan Network" - should show "TD_SLAM"
5. Select "TD_SLAM" from list
6. Click "Launch SLAM"
7. SLAM processes live TouchDesigner output!

### Example 3: Run with TouchDesigner File Output
1. In TouchDesigner: Add "Movie File Out TOP"
2. Set path: `C:/SLAM/frames/frame_$F.jpg`
3. Enable output
4. Launch Control GUI: `python slam_control_gui.py`
5. Source Type: "Image Folder"
6. Path: `/mnt/c/SLAM/frames/`
7. Click "Launch SLAM"
8. GUI watches folder and processes new images as they appear!

## Troubleshooting

### "Failed to launch process"
- Check that conda environment exists: `conda env list | grep mast3r-slam-blackwell`
- Check that main.py or main_live.py exists in `/home/sep/MASt3R-SLAM/`
- Check permissions: `ls -la main.py`

### "Process ended (exit code: 1)"
- Read console output for error message
- Common issues:
  - Dataset path not found
  - Model checkpoints not downloaded
  - NDI SDK not installed (for NDI sources)
  - Missing dependencies

### No console output appearing
- This is normal for first 10-20 seconds while model loads
- If still nothing after 30 seconds, check process is running: `ps aux | grep python`

### GUI not opening
- Check DISPLAY variable: `echo $DISPLAY`
- On WSL2, make sure X server is running (VcXsrv, X410, etc.)
- Try: `export DISPLAY=:0` then relaunch

### "Stop Process" not working
- Process may be stuck in CUDA operation
- Wait 5 seconds for force kill
- If still running: `pkill -9 -f "python main"`

## What's Different from Old Control GUI

| Feature | Old GUI | New GUI |
|---------|---------|---------|
| Launch SLAM | ❌ No | ✅ Yes |
| Stop SLAM | ❌ No | ✅ Yes |
| Console output | ❌ No | ✅ Yes |
| Process management | ❌ UDP commands (didn't work) | ✅ Direct subprocess control |
| Source switching | ❌ Sent commands to running process | ✅ Stop and restart with new source |
| Status monitoring | ❌ Waited for UDP replies | ✅ Parse from console output |

## Technical Details

### File Structure
```
MASt3R-SLAM/
├── slam_control_gui.py      # Main GUI (MODIFIED - now process launcher)
├── main.py                   # Dataset SLAM (used for TUM datasets)
├── main_live.py              # Live camera SLAM (for NDI, webcam, etc.)
└── config/calib.yaml         # SLAM configuration
```

### Process Lifecycle
```
User clicks "Launch SLAM"
    ↓
GUI builds command string
    ↓
subprocess.Popen() launches bash
    ↓
Bash activates conda environment
    ↓
Bash runs python main.py or main_live.py
    ↓
Python process starts SLAM
    ↓
stdout → GUI console widget (live)
    ↓
User clicks "Stop" OR process finishes
    ↓
GUI sends SIGTERM, waits 5s, then SIGKILL if needed
    ↓
Process ends, GUI updates status
```

### Threading Model
```
Main Thread (Tkinter GUI)
    ├─> Output Reader Thread (reads process stdout)
    │     └─> Updates console widget via root.after()
    └─> Status Monitor Thread (checks process.poll())
          └─> Detects crashes via root.after()
```

## Integration with TouchDesigner

The Control GUI makes it easy to integrate with TouchDesigner:

**Method 1: NDI Streaming**
1. TD: Add NDI Out TOP → MASt3R-SLAM
2. GUI: Select NDI source, launch

**Method 2: File Watching**
1. TD: Movie File Out TOP → Folder
2. GUI: Watch that folder
3. SLAM processes images as TD saves them

**Method 3: OSC Streaming (NEW!)**
If using `main_live.py`, add `--osc-enable --osc-port 9001` to send point cloud back to TD:
- Note: You'll need to edit the command builder to add OSC flags
- Or manually add them to the source-specific build functions

## Next Steps

1. **Test the GUI** - Try launching with TUM dataset first
2. **Install NDI SDK** - Follow `NDI_SDK_INSTALL.md` for NDI support
3. **Try TouchDesigner integration** - See `TOUCHDESIGNER_COMPLETE_GUIDE.md`
4. **Customize** - Edit `build_slam_command()` to add custom flags

## Advanced Customization

### Adding Custom Command-Line Flags

To add flags like `--osc-enable`, edit `slam_control_gui.py`:

```python
def build_slam_command(self, source_type):
    # ... existing code ...

    elif source_type == "Webcam":
        device_id = self.webcam_id.get()
        width = self.webcam_width.get()
        height = self.webcam_height.get()

        # Add your custom flags here:
        cmd = base_cmd[2] + f"python main_live.py --source webcam " \
                            f"--device-id {device_id} --width {width} " \
                            f"--height {height} --config config/calib.yaml " \
                            f"--osc-enable --osc-port 9001"  # <-- CUSTOM

    # ... rest of code ...
```

### Changing Window Size

Edit `__init__`:
```python
def __init__(self):
    self.root = tk.Tk()
    self.root.title("MASt3R-SLAM Process Launcher")
    self.root.geometry("800x900")  # <-- Change this (WIDTHxHEIGHT)
```

### Changing Console Colors

Edit `create_ui`:
```python
self.console_text = scrolledtext.ScrolledText(
    console_frame,
    height=15,
    bg="black",          # <-- Background color
    fg="#00ff00",        # <-- Text color (green)
    font=("Courier", 9), # <-- Font
    wrap=tk.WORD
)
```

## Summary

The Control GUI is now a **full process launcher** that:
- ✅ Launches MASt3R-SLAM with correct settings
- ✅ Shows live console output
- ✅ Parses FPS and keyframe counts
- ✅ Stops and restarts processes
- ✅ Monitors for crashes
- ✅ Works on WSL2 where ImGui doesn't

**No more "Control GUI has no effect" - it now fully controls SLAM!**

Enjoy your powerful new SLAM launcher! 🚀
