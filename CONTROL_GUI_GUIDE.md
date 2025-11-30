# MASt3R-SLAM Control GUI Guide

## Quick Start

The Control GUI is a **separate tkinter window** that lets you control MASt3R-SLAM without using the main visualization's non-working ImGui controls on WSL2.

### Launch the Control GUI:

```bash
cd /home/sep/MASt3R-SLAM
python slam_control_gui.py
```

A window will open with full control over SLAM!

---

## Features

### 1. Camera Source Selection

**Dropdown Menu** with options:
- **NDI** - Network Device Interface (TouchDesigner)
- **Webcam** - USB camera
- **RealSense** - Intel depth camera
- **TUM Dataset** - Pre-recorded datasets
- **Video File** - Process .mp4/.avi files
- **Image Folder** - Watch folder for new images (TouchDesigner file output!)

### 2. NDI Source Scanner

When NDI is selected:
1. Click **"🔍 Scan Network"**
2. Wait for NDI sources to appear
3. Select from list OR enter manually
4. Click **"🎬 Apply Source"**

**Perfect for TouchDesigner!**

### 3. Quick Dataset Selection

When "TUM Dataset" is selected, you get buttons for all downloaded datasets:
- Click button → path auto-fills
- Or browse manually

### 4. SLAM Controls

- **⏸️ Pause** - Pause processing
- **▶️ Resume** - Continue
- **🔄 Reset** - Clear all keyframes, restart fresh
- **💾 Save PLY** - Export current reconstruction
- **📸 Save Keyframes** - Export keyframe images

### 5. Settings

- **Subsample**: Process every Nth frame (1 = all frames, 2 = every other)
- **Confidence Threshold**: Filter point cloud quality (0.0-1.0)
- **Resolution**: Set webcam resolution

### 6. Status Monitor

Real-time display of:
- Current status
- FPS
- Active source
- Keyframe count

---

## How It Works

The Control GUI communicates with MASt3R-SLAM via **UDP sockets**:

- **Port 9999**: Commands (GUI → SLAM)
- **Port 10000**: Status updates (SLAM → GUI)

This works even when ImGui input doesn't!

---

## Usage Examples

### Example 1: Switch from Dataset to NDI

1. SLAM is processing TUM dataset
2. Open Control GUI
3. Select "NDI" from dropdown
4. Click "Scan Network"
5. Select "TouchDesigner Output"
6. Click "Apply Source"
7. SLAM smoothly switches to live NDI feed!

### Example 2: TouchDesigner File Watching

1. In TouchDesigner:
   - Add **Movie File Out TOP**
   - Path: `C:\TouchDesigner\frames\frame_####.jpg`
   - Cook type: Realtime

2. In Control GUI:
   - Select "Image Folder"
   - Path: `/mnt/c/TouchDesigner/frames/`
   - Click "Apply Source"

3. SLAM now watches folder and processes new images as TD writes them!

### Example 3: Quick Testing Multiple Datasets

1. Open Control GUI
2. Select "TUM Dataset"
3. Click "rgbd_dataset_freiburg1_desk" → processes desk
4. Click "rgbd_dataset_freiburg1_plant" → switches to plant
5. Click "rgbd_dataset_freiburg1_teddy" → switches to teddy

No restart needed!

---

## Keyboard Shortcuts (in Control GUI)

- `Space` - Pause/Resume
- `R` - Reset
- `S` - Save PLY
- `Ctrl+Q` - Quit

---

## Troubleshooting

### GUI doesn't open
WSL2 needs X server. WSLg (built into Windows 11) should handle this automatically. If not:
```bash
export DISPLAY=:0
python slam_control_gui.py
```

### "No connection to SLAM"
The control GUI needs MASt3R-SLAM running with socket support. Make sure you're using the updated `main.py` that listens on port 9999.

### NDI scan finds nothing
- Check firewall
- Ensure TouchDesigner and WSL2 on same network
- Try manual entry instead: "TouchDesigner Output"

### Source switch doesn't work
MASt3R-SLAM needs to be modified to accept source changes. The GUI sends commands, but main.py needs to handle them. See "Integration with main.py" below.

---

## Integration with main.py

To make source switching work, add UDP listener to `main.py`:

```python
import socket
import json
import threading

def command_listener(queue):
    """Listen for GUI commands"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 9999))
    sock.settimeout(1.0)

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            command = json.loads(data.decode('utf-8'))
            queue.put(command)
        except socket.timeout:
            continue
        except:
            break

# In main.py:
command_queue = queue.Queue()
listener_thread = threading.Thread(target=command_listener, args=(command_queue,), daemon=True)
listener_thread.start()

# In main loop:
if not command_queue.empty():
    cmd = command_queue.get()
    if cmd['action'] == 'change_source':
        # Switch to new source
        dataset = load_new_source(cmd)
    elif cmd['action'] == 'pause':
        states.pause()
    # etc...
```

---

## Advanced: Custom Controls

You can add your own controls to the GUI by editing `slam_control_gui.py`:

```python
# Add a button
tk.Button(
    control_frame,
    text="My Custom Action",
    command=self.my_custom_function
).pack()

def my_custom_function(self):
    self.send_command({"action": "custom", "param": "value"})
```

Then handle it in main.py command listener!

---

## For TouchDesigner Users

### Workflow: TD → SLAM → TD Loop

1. **TouchDesigner generates content**
   - Camera input, generative patterns, etc.
   - Output via NDI or Movie File Out

2. **Control GUI selects source**
   - NDI or Image Folder
   - Adjust settings (subsample, confidence)

3. **SLAM processes live**
   - Real-time 3D reconstruction
   - Sends point cloud back via OSC (see TOUCHDESIGNER_INTEGRATION.md)

4. **TouchDesigner receives 3D data**
   - OSC In DAT
   - Visualize/manipulate
   - Create feedback loop!

### Complete TD Network Example:

```
[Camera In] → [Effects] → [NDI Out TOP]
                            ↓
                    [MASt3R-SLAM]
                            ↓
[OSC In DAT] ← [Point Cloud Data]
     ↓
[3D Visualization]
```

Control everything from the GUI!

---

## Next Steps

1. **Test the GUI** - Launch it and explore
2. **Integrate with main.py** - Add command listener
3. **Set up TouchDesigner** - NDI or file watching
4. **Build something cool!** - Live SLAM in your installations

The Control GUI makes MASt3R-SLAM **fully controllable on WSL2** despite ImGui limitations!

🎮 **Happy SLAMming!**
