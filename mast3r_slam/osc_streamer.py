"""OSC Streaming for TouchDesigner Integration

Streams point cloud data from MASt3R-SLAM to TouchDesigner via OSC (Open Sound Control).

Features:
- Real-time point cloud streaming
- Configurable downsample rate (send every Nth point to avoid overwhelming network)
- Batch sending for efficiency
- Color data support
- Camera pose streaming

Usage:
    # In your SLAM loop
    osc_streamer = OSCStreamer(host='127.0.0.1', port=9001)
    osc_streamer.start()

    # After processing each frame
    osc_streamer.send_point_cloud(points, colors, camera_pose)

    # Cleanup
    osc_streamer.stop()
"""

import numpy as np
import threading
import time
from typing import Optional, Tuple


class OSCStreamer:
    """Stream point cloud data to TouchDesigner via OSC"""

    def __init__(self,
                 host: str = '127.0.0.1',
                 port: int = 9001,
                 downsample: int = 10,
                 max_points_per_message: int = 100,
                 enabled: bool = True):
        """
        Args:
            host: OSC destination IP address
            port: OSC destination port
            downsample: Send every Nth point (reduces network load)
            max_points_per_message: Maximum points per OSC bundle
            enabled: Whether OSC streaming is enabled
        """
        self.host = host
        self.port = port
        self.downsample = downsample
        self.max_points_per_message = max_points_per_message
        self.enabled = enabled

        self.client = None
        self.running = False
        self.send_queue = []
        self.send_thread = None

        if enabled:
            try:
                from pythonosc import udp_client
                self.client = udp_client.SimpleUDPClient(host, port)
                print(f"OSC Streamer initialized: {host}:{port}")
            except ImportError:
                print("Warning: python-osc not installed. OSC streaming disabled.")
                print("Install with: pip install python-osc")
                self.enabled = False

    def start(self):
        """Start background sending thread"""
        if not self.enabled:
            return

        self.running = True
        self.send_thread = threading.Thread(target=self._send_worker, daemon=True)
        self.send_thread.start()

    def stop(self):
        """Stop background sending thread"""
        self.running = False
        if self.send_thread:
            self.send_thread.join(timeout=2.0)

    def _send_worker(self):
        """Background thread for sending OSC messages"""
        while self.running:
            if self.send_queue:
                msg_type, data = self.send_queue.pop(0)

                if msg_type == 'point_cloud':
                    self._send_point_cloud_impl(*data)
                elif msg_type == 'camera_pose':
                    self._send_camera_pose_impl(*data)
                elif msg_type == 'status':
                    self._send_status_impl(*data)
            else:
                time.sleep(0.01)  # Small sleep to avoid busy waiting

    def send_point_cloud(self,
                        points: np.ndarray,
                        colors: Optional[np.ndarray] = None,
                        confidence: Optional[np.ndarray] = None):
        """Queue point cloud for sending

        Args:
            points: Nx3 array of point positions
            colors: Nx3 array of RGB colors (0-255)
            confidence: Nx1 array of confidence values (0-1)
        """
        if not self.enabled or not self.running:
            return

        self.send_queue.append(('point_cloud', (points, colors, confidence)))

    def _send_point_cloud_impl(self, points, colors, confidence):
        """Actually send point cloud data via OSC"""
        if points is None or len(points) == 0:
            return

        # Downsample points
        indices = np.arange(0, len(points), self.downsample)
        points_ds = points[indices]

        if colors is not None:
            colors_ds = colors[indices]
        else:
            colors_ds = np.ones_like(points_ds) * 255  # Default white

        if confidence is not None:
            conf_ds = confidence[indices]
        else:
            conf_ds = np.ones(len(points_ds))

        # Send in batches
        num_points = len(points_ds)

        # Send header with total point count
        self.client.send_message("/slam/cloud/start", [num_points])

        for i in range(0, num_points, self.max_points_per_message):
            batch_end = min(i + self.max_points_per_message, num_points)
            batch_points = points_ds[i:batch_end]
            batch_colors = colors_ds[i:batch_end]
            batch_conf = conf_ds[i:batch_end]

            # Flatten arrays for OSC
            # Format: [x1, y1, z1, r1, g1, b1, c1, x2, y2, z2, r2, g2, b2, c2, ...]
            batch_data = []
            for j in range(len(batch_points)):
                batch_data.extend([
                    float(batch_points[j, 0]),
                    float(batch_points[j, 1]),
                    float(batch_points[j, 2]),
                    float(batch_colors[j, 0]) / 255.0,  # Normalize to 0-1
                    float(batch_colors[j, 1]) / 255.0,
                    float(batch_colors[j, 2]) / 255.0,
                    float(batch_conf[j])
                ])

            self.client.send_message("/slam/cloud/batch", batch_data)

        # Send end marker
        self.client.send_message("/slam/cloud/end", [])

    def send_camera_pose(self, position: np.ndarray, rotation: np.ndarray):
        """Queue camera pose for sending

        Args:
            position: 3D position [x, y, z]
            rotation: 3x3 rotation matrix or 4D quaternion [w, x, y, z]
        """
        if not self.enabled or not self.running:
            return

        self.send_queue.append(('camera_pose', (position, rotation)))

    def _send_camera_pose_impl(self, position, rotation):
        """Actually send camera pose via OSC"""
        # Send position
        self.client.send_message("/slam/camera/position", [
            float(position[0]),
            float(position[1]),
            float(position[2])
        ])

        # Send rotation (as matrix flatten to list)
        if rotation.shape == (3, 3):
            rot_flat = rotation.flatten().tolist()
            self.client.send_message("/slam/camera/rotation", [float(x) for x in rot_flat])
        elif len(rotation) == 4:
            # Quaternion
            self.client.send_message("/slam/camera/quaternion", [float(x) for x in rotation])

    def send_status(self, fps: float, num_keyframes: int, num_points: int):
        """Queue status update for sending"""
        if not self.enabled or not self.running:
            return

        self.send_queue.append(('status', (fps, num_keyframes, num_points)))

    def _send_status_impl(self, fps, num_keyframes, num_points):
        """Actually send status via OSC"""
        self.client.send_message("/slam/status/fps", [float(fps)])
        self.client.send_message("/slam/status/keyframes", [int(num_keyframes)])
        self.client.send_message("/slam/status/points", [int(num_points)])

    def send_event(self, event_name: str, *args):
        """Send custom event to TouchDesigner

        Args:
            event_name: Event name (e.g., 'reset', 'save', etc.)
            *args: Optional event arguments
        """
        if not self.enabled or self.client is None:
            return

        self.client.send_message(f"/slam/event/{event_name}", list(args))


class OSCStreamConfig:
    """Configuration for OSC streaming"""

    def __init__(self):
        self.enabled = False
        self.host = '127.0.0.1'
        self.port = 9001
        self.downsample = 10  # Send every 10th point
        self.max_points = 100  # Max points per message
        self.send_camera_pose = True
        self.send_status = True
        self.status_interval = 1.0  # Send status every N seconds

    @staticmethod
    def from_dict(config: dict):
        """Create config from dictionary"""
        cfg = OSCStreamConfig()
        cfg.enabled = config.get('enabled', False)
        cfg.host = config.get('host', '127.0.0.1')
        cfg.port = config.get('port', 9001)
        cfg.downsample = config.get('downsample', 10)
        cfg.max_points = config.get('max_points', 100)
        cfg.send_camera_pose = config.get('send_camera_pose', True)
        cfg.send_status = config.get('send_status', True)
        cfg.status_interval = config.get('status_interval', 1.0)
        return cfg
