# MASt3R-SLAM TouchDesigner Integration Guide

This document explains how to stream live 3D reconstruction data from MASt3R-SLAM to TouchDesigner for real-time visualization and creative applications.

## Overview

MASt3R-SLAM generates point cloud reconstructions that can be streamed to TouchDesigner using several methods:

1. **File Watching** - Simplest approach, monitor PLY files
2. **OSC (Open Sound Control)** - Low latency, native TD support
3. **TCP/UDP Sockets** - Direct network streaming
4. **WebSocket** - Structured data streaming

---

## Method 1: File Watching (Easiest)

Monitor the PLY file that MASt3R-SLAM updates during runtime.

### TouchDesigner Setup

1. Add a **File In TOP** operator
2. Point it to the reconstruction PLY file
3. Enable "Reload Pulse" to watch for file changes
4. Use a **Geometry COMP** to import the point cloud

### MASt3R-SLAM Modification

Modify `mast3r_slam/evaluate.py` to save reconstruction continuously:

```python
# In your main loop, after each keyframe addition:
if add_new_kf:
    keyframes.append(frame)
    states.queue_global_optimization(len(keyframes) - 1)

    # Save live reconstruction for TouchDesigner
    eval.save_reconstruction(
        pathlib.Path("live_output"),
        "live_reconstruction.ply",
        keyframes,
        c_conf_threshold=0.5
    )
```

**Pros:**
- No additional dependencies
- Simple implementation
- Reliable

**Cons:**
- Higher latency (~100-500ms)
- File I/O overhead
- TouchDesigner needs to reload entire file

---

## Method 2: OSC Streaming (Recommended for Real-Time)

Stream point cloud data using OSC protocol with low latency.

### Install OSC Library

```bash
conda activate mast3r-slam-blackwell
pip install python-osc
```

### MASt3R-SLAM Implementation

Create `mast3r_slam/touchdesigner_osc.py`:

```python
"""OSC streaming for TouchDesigner integration"""
import numpy as np
from pythonosc import udp_client
from pythonosc.osc_bundle_builder import OscBundleBuilder
from pythonosc.osc_message_builder import OscMessageBuilder
import time


class TouchDesignerOSC:
    def __init__(self, ip="127.0.0.1", port=9000, max_points=10000):
        """
        Args:
            ip: TouchDesigner machine IP (127.0.0.1 for local)
            port: OSC receive port (default 9000)
            max_points: Maximum points per frame to avoid overload
        """
        self.client = udp_client.SimpleUDPClient(ip, port)
        self.max_points = max_points

    def send_pointcloud(self, points, colors, frame_id=0):
        """
        Send point cloud data to TouchDesigner

        Args:
            points: Nx3 numpy array of XYZ positions
            colors: Nx3 numpy array of RGB colors (0-1 range)
            frame_id: Frame identifier
        """
        # Downsample if too many points
        n_points = len(points)
        if n_points > self.max_points:
            indices = np.random.choice(n_points, self.max_points, replace=False)
            points = points[indices]
            colors = colors[indices]
            n_points = self.max_points

        # Build OSC bundle for atomic update
        bundle_builder = OscBundleBuilder(time.time())

        # Send metadata
        bundle_builder.add_content(
            OscMessageBuilder(address="/mast3r/frame_id")
            .add_arg(frame_id)
            .build()
        )
        bundle_builder.add_content(
            OscMessageBuilder(address="/mast3r/point_count")
            .add_arg(n_points)
            .build()
        )

        # Send points in batches (OSC has size limits)
        batch_size = 100
        for i in range(0, n_points, batch_size):
            batch_end = min(i + batch_size, n_points)
            batch_points = points[i:batch_end]
            batch_colors = colors[i:batch_end]

            for j, (pt, col) in enumerate(zip(batch_points, batch_colors)):
                msg_builder = OscMessageBuilder(address=f"/mast3r/point/{i+j}")
                # Position XYZ
                msg_builder.add_arg(float(pt[0]))
                msg_builder.add_arg(float(pt[1]))
                msg_builder.add_arg(float(pt[2]))
                # Color RGB
                msg_builder.add_arg(float(col[0]))
                msg_builder.add_arg(float(col[1]))
                msg_builder.add_arg(float(col[2]))
                bundle_builder.add_content(msg_builder.build())

        # Send bundle
        bundle = bundle_builder.build()
        self.client.send(bundle)

    def send_keyframe_poses(self, T_WC_list):
        """Send camera poses for visualization"""
        for i, T_WC in enumerate(T_WC_list):
            # Extract translation
            t = T_WC[:3, 3].cpu().numpy()
            self.client.send_message(f"/mast3r/camera/{i}/position",
                                     [float(t[0]), float(t[1]), float(t[2])])


# Usage in main.py
osc_streamer = TouchDesignerOSC(ip="127.0.0.1", port=9000, max_points=5000)

# After backend optimization
if add_new_kf:
    keyframes.append(frame)
    states.queue_global_optimization(len(keyframes) - 1)
    run_backend(states, keyframes)

    # Stream to TouchDesigner
    points, colors = extract_pointcloud(keyframes)
    osc_streamer.send_pointcloud(points, colors, frame_id=i)
```

### TouchDesigner Setup

1. Add **OSC In DAT** operator
2. Set Network Port to 9000
3. Add **CHOP Execute DAT** to parse incoming messages
4. Use **Script SOP** to build point cloud geometry from OSC data

**Example TouchDesigner Python Script:**

```python
# In a Script SOP
def onPulse(channel):
    if channel.name == '/mast3r/point_count':
        n_points = int(channel[0])
        me.par.npts = n_points

def cook(scriptOp):
    # Parse OSC points
    osc_in = op('oscin1')
    points = []
    colors = []

    for i in range(int(osc_in['/mast3r/point_count'][0])):
        x = float(osc_in[f'/mast3r/point/{i}/x'][0])
        y = float(osc_in[f'/mast3r/point/{i}/y'][0])
        z = float(osc_in[f'/mast3r/point/{i}/z'][0])
        r = float(osc_in[f'/mast3r/point/{i}/r'][0])
        g = float(osc_in[f'/mast3r/point/{i}/g'][0])
        b = float(osc_in[f'/mast3r/point/{i}/b'][0])

        points.append([x, y, z])
        colors.append([r, g, b])

    scriptOp.clear()
    for pt, col in zip(points, colors):
        scriptOp.appendPoint(pt)
        scriptOp.appendColor(col)
```

**Pros:**
- Low latency (~10-50ms)
- Native TouchDesigner support
- Industry standard for real-time control

**Cons:**
- UDP packet size limits (need batching)
- Point cloud size limited
- Requires python-osc library

---

## Method 3: TCP Socket Streaming

Stream raw binary data over TCP for maximum throughput.

### MASt3R-SLAM Implementation

Create `mast3r_slam/tcp_streamer.py`:

```python
"""TCP socket streaming for TouchDesigner"""
import socket
import struct
import numpy as np


class TouchDesignerTCP:
    def __init__(self, host="127.0.0.1", port=9001):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((host, port))
        self.socket.listen(1)
        self.conn = None
        print(f"TCP server listening on {host}:{port}")

    def wait_for_connection(self):
        """Wait for TouchDesigner to connect"""
        print("Waiting for TouchDesigner connection...")
        self.conn, addr = self.socket.accept()
        print(f"Connected to {addr}")

    def send_pointcloud_binary(self, points, colors):
        """
        Send point cloud as binary data
        Format: [n_points(int32)][x,y,z,r,g,b(float32) * n_points]
        """
        if self.conn is None:
            return

        n_points = len(points)

        # Pack data: 1 int32 + n_points * 6 float32
        data = struct.pack('i', n_points)

        for i in range(n_points):
            data += struct.pack('ffffff',
                              points[i, 0], points[i, 1], points[i, 2],
                              colors[i, 0], colors[i, 1], colors[i, 2])

        try:
            self.conn.sendall(data)
        except BrokenPipeError:
            print("TouchDesigner disconnected")
            self.conn = None


# Usage in main.py
tcp_streamer = TouchDesignerTCP(host="127.0.0.1", port=9001)
tcp_streamer.wait_for_connection()

# In main loop
if add_new_kf:
    points, colors = extract_pointcloud(keyframes)
    tcp_streamer.send_pointcloud_binary(points, colors)
```

### TouchDesigner Setup

1. Add **TCP/IP DAT** operator
2. Set Mode to "Client"
3. Set Network Address to "127.0.0.1:9001"
4. Add **Script SOP** to parse binary data

**TouchDesigner Python Parser:**

```python
# In a Script SOP
import struct

def cook(scriptOp):
    tcp_dat = op('tcpip1')
    raw_data = tcp_dat.bytes

    if len(raw_data) < 4:
        return

    # Parse header
    n_points = struct.unpack('i', raw_data[:4])[0]

    # Parse points
    scriptOp.clear()
    offset = 4
    point_size = 6 * 4  # 6 floats * 4 bytes

    for i in range(n_points):
        if offset + point_size > len(raw_data):
            break

        x, y, z, r, g, b = struct.unpack('ffffff',
                                         raw_data[offset:offset+point_size])
        scriptOp.appendPoint([x, y, z])
        scriptOp.appendColor([r, g, b])
        offset += point_size
```

**Pros:**
- High throughput
- Binary format efficient
- Reliable TCP connection

**Cons:**
- More complex parsing in TouchDesigner
- Requires connection management
- Blocking if TouchDesigner disconnects

---

## Method 4: WebSocket Streaming

Stream JSON data over WebSocket for flexibility.

### Install WebSocket Library

```bash
pip install websockets
```

### MASt3R-SLAM Implementation

```python
"""WebSocket streaming for TouchDesigner"""
import asyncio
import websockets
import json
import numpy as np


class TouchDesignerWebSocket:
    def __init__(self, host="127.0.0.1", port=9002):
        self.host = host
        self.port = port
        self.clients = set()

    async def handler(self, websocket, path):
        """Handle WebSocket connections"""
        self.clients.add(websocket)
        print(f"TouchDesigner connected: {websocket.remote_address}")
        try:
            await websocket.wait_closed()
        finally:
            self.clients.remove(websocket)

    async def broadcast_pointcloud(self, points, colors, frame_id):
        """Broadcast point cloud to all connected clients"""
        if not self.clients:
            return

        # Downsample for JSON efficiency
        indices = np.random.choice(len(points), min(1000, len(points)), replace=False)

        data = {
            "frame_id": frame_id,
            "points": points[indices].tolist(),
            "colors": colors[indices].tolist()
        }

        message = json.dumps(data)
        await asyncio.gather(
            *[client.send(message) for client in self.clients],
            return_exceptions=True
        )

    async def start_server(self):
        """Start WebSocket server"""
        async with websockets.serve(self.handler, self.host, self.port):
            print(f"WebSocket server started on ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever
```

**Pros:**
- Modern protocol
- Easy debugging (JSON)
- Bidirectional communication

**Cons:**
- JSON overhead (large data)
- Requires async handling
- TouchDesigner WebSocket support limited

---

## Extracting Point Cloud from Keyframes

Helper function to extract point cloud data from MASt3R-SLAM keyframes:

```python
def extract_pointcloud(keyframes, c_conf_threshold=0.5, max_points=50000):
    """
    Extract point cloud from keyframes for streaming

    Args:
        keyframes: SharedKeyframes object
        c_conf_threshold: Confidence threshold for points
        max_points: Maximum points to return

    Returns:
        points: Nx3 numpy array of XYZ positions
        colors: Nx3 numpy array of RGB colors (0-1 range)
    """
    import torch

    pointclouds = []
    colors = []

    with keyframes.lock:
        for i in range(len(keyframes)):
            keyframe = keyframes[i]

            # Get point map and colors
            X = keyframe.X.cpu().numpy()  # (H, W, 3)
            C = keyframe.C.cpu().numpy()  # (H, W, 3)
            C_conf = keyframe.C_conf.cpu().numpy()  # (H, W)

            # Filter by confidence
            mask = C_conf > c_conf_threshold

            # Transform to world coordinates
            T_WC = keyframe.T_WC.matrix().cpu().numpy()
            X_homogeneous = np.concatenate([X, np.ones((*X.shape[:2], 1))], axis=-1)
            X_world = (T_WC @ X_homogeneous.reshape(-1, 4).T).T.reshape(*X.shape[:2], 4)
            X_world = X_world[:, :, :3]

            # Apply mask and collect
            pointclouds.append(X_world[mask])
            colors.append(C[mask])

    # Concatenate all keyframes
    points = np.concatenate(pointclouds, axis=0)
    colors = np.concatenate(colors, axis=0)

    # Downsample if needed
    if len(points) > max_points:
        indices = np.random.choice(len(points), max_points, replace=False)
        points = points[indices]
        colors = colors[indices]

    return points, colors
```

---

## Performance Considerations

### Point Cloud Size

- **File watching**: Can handle full point clouds (100k+ points)
- **OSC**: Limit to 5-10k points for smooth performance
- **TCP**: Can handle 50k+ points efficiently
- **WebSocket**: Limit to 1-5k points (JSON overhead)

### Update Rate

- **File watching**: 1-10 Hz (file I/O limited)
- **OSC**: 30-60 Hz (with small point clouds)
- **TCP**: 60+ Hz (binary format)
- **WebSocket**: 10-30 Hz (JSON parsing)

### Network vs Local

All methods work over network (change `127.0.0.1` to target IP), but:
- OSC: Best for network (UDP resilient)
- TCP: Requires stable connection
- WebSocket: Good for remote monitoring

---

## Recommended Setup

**For real-time visualization:**
- Use **OSC streaming** with 5000-10000 points
- Update every keyframe addition (~9 FPS on WSL2)
- Use confidence threshold 0.5-0.7 to filter noisy points

**For high-quality offline:**
- Use **file watching** on final PLY output
- Process complete reconstruction after SLAM finishes
- No point limit, full quality

**For development/debugging:**
- Start with **file watching** (easiest)
- Upgrade to OSC when you need real-time feedback

---

## Example: OSC Integration in main.py

```python
# Add at top of main.py
from mast3r_slam.touchdesigner_osc import TouchDesignerOSC

# After model loading
if not args.no_viz:
    # Start OSC streaming
    osc_stream = TouchDesignerOSC(ip="127.0.0.1", port=9000, max_points=5000)
    print("OSC streaming enabled on port 9000")

# In main loop, after keyframe addition
if add_new_kf:
    keyframes.append(frame)
    states.queue_global_optimization(len(keyframes) - 1)
    run_backend(states, keyframes)

    # Stream to TouchDesigner every keyframe
    points, colors = extract_pointcloud(keyframes, c_conf_threshold=0.6, max_points=5000)
    osc_stream.send_pointcloud(points, colors, frame_id=i)
    osc_stream.send_keyframe_poses([kf.T_WC for kf in keyframes])
```

---

## TouchDesigner Network Configuration

Make sure TouchDesigner is ready to receive data:

1. **OSC**: OSC In DAT → Set port 9000 → Enable
2. **TCP**: TCP/IP DAT → Client mode → Connect to 127.0.0.1:9001
3. **File**: File In TOP → Point to `/home/sep/MASt3R-SLAM/results/tum/rgbd_dataset_freiburg1_desk/rgbd_dataset_freiburg1_desk.ply`

---

## Output Locations

MASt3R-SLAM saves results to:

```
/home/sep/MASt3R-SLAM/results/<dataset_type>/<sequence_name>/
├── <sequence_name>.txt          # Camera trajectory
├── <sequence_name>.ply          # Final 3D reconstruction
└── keyframes/<sequence_name>/   # Individual keyframe images
    ├── 0000.png
    ├── 0001.png
    └── ...
```

For TUM dataset:
```
/home/sep/MASt3R-SLAM/results/tum/rgbd_dataset_freiburg1_desk/rgbd_dataset_freiburg1_desk.ply
```

---

## Troubleshooting

### No data in TouchDesigner
- Check IP address and port match
- Verify firewall allows connections
- On WSL2, use `127.0.0.1` not `localhost`
- Check if MASt3R-SLAM is actually streaming (add print statements)

### Performance too slow
- Reduce max_points parameter
- Increase confidence threshold to filter more points
- Stream every N keyframes instead of every keyframe

### OSC packets dropped
- Reduce batch size
- Use TCP instead for guaranteed delivery
- Increase TouchDesigner OSC buffer size

---

## References

- [TouchDesigner OSC In DAT](https://docs.derivative.ca/OSC_In_DAT)
- [TouchDesigner TCP/IP DAT](https://docs.derivative.ca/TCPIP_DAT)
- [python-osc Documentation](https://pypi.org/project/python-osc/)
- [MASt3R-SLAM GitHub](https://github.com/benucl/MASt3R-SLAM)

---

**Author:** Claude (Anthropic)
**Last Updated:** 2025-11-30
**Compatible with:** MASt3R-SLAM Blackwell RTX 5090 WSL2 branch
