"""Live camera input for MASt3R-SLAM

Supports:
- NDI (Network Device Interface) sources
- USB Webcams via OpenCV
- Intel RealSense cameras
- RTSP/HTTP streams
"""

import time
import numpy as np
import cv2
import torch
from mast3r_slam.mast3r_utils import resize_img
from mast3r_slam.config import config


class LiveCameraDataset:
    """Base class for live camera streaming"""

    def __init__(self, img_size=512, fps=30, max_frames=None):
        self.img_size = img_size
        self.fps = fps
        self.max_frames = max_frames  # None = infinite
        self.frame_count = 0
        self.start_time = time.time()
        self.camera_intrinsics = None
        self.use_calibration = False
        self.save_results = True

    def __len__(self):
        # Return max_frames if set, otherwise a large number for infinite streaming
        return self.max_frames if self.max_frames is not None else 999999

    def __getitem__(self, idx):
        """Get next frame from live stream"""
        frame = self.capture_frame()
        if frame is None:
            raise StopIteration("No more frames available")

        timestamp = time.time() - self.start_time
        self.frame_count += 1

        # Convert to format expected by MASt3R-SLAM
        img = frame.astype(np.float32) / 255.0
        return timestamp, img

    def capture_frame(self):
        """Override in subclass to capture from specific source"""
        raise NotImplementedError

    def release(self):
        """Release camera resources"""
        pass

    def get_img_shape(self):
        """Get image shape for initialization"""
        frame = self.capture_frame()
        if frame is None:
            raise RuntimeError("Failed to capture initial frame")
        resized = resize_img(frame, self.img_size)
        return resized["img"][0].shape[1:], frame.shape[:2]

    def subsample(self, subsample):
        """Adjust FPS for subsampling"""
        self.fps = self.fps // subsample

    def has_calib(self):
        return self.camera_intrinsics is not None


class NDICamera(LiveCameraDataset):
    """NDI (Network Device Interface) camera source

    Perfect for TouchDesigner integration and professional video workflows!

    Usage:
        # Find available NDI sources
        ndi_cam = NDICamera()
        sources = ndi_cam.list_sources()
        print(f"Available NDI sources: {sources}")

        # Connect to specific source
        ndi_cam = NDICamera(source_name="TouchDesigner Output")

        # Or connect to first available source
        ndi_cam = NDICamera(source_index=0)
    """

    def __init__(self, source_name=None, source_index=0, timeout=5000, **kwargs):
        super().__init__(**kwargs)

        try:
            import NDIlib as ndi
            self.ndi = ndi
        except ImportError:
            raise ImportError(
                "NDI library not found. Install with:\n"
                "  pip install ndi-python\n"
                "Or install NewTek NDI SDK from: https://ndi.tv/sdk/"
            )

        # Initialize NDI
        if not self.ndi.initialize():
            raise RuntimeError("Failed to initialize NDI")

        # Create NDI finder to locate sources
        self.finder = self.ndi.find_create_v2()
        if self.finder is None:
            raise RuntimeError("Failed to create NDI finder")

        # Wait for sources
        print(f"Searching for NDI sources (timeout: {timeout}ms)...")
        time.sleep(timeout / 1000.0)

        sources = self.ndi.find_get_current_sources(self.finder)

        if not sources:
            raise RuntimeError("No NDI sources found on network")

        print(f"Found {len(sources)} NDI source(s):")
        for i, src in enumerate(sources):
            print(f"  [{i}] {src.ndi_name}")

        # Select source
        if source_name:
            source = next((s for s in sources if source_name in s.ndi_name), None)
            if source is None:
                raise ValueError(f"NDI source '{source_name}' not found")
        else:
            if source_index >= len(sources):
                raise ValueError(f"Source index {source_index} out of range (0-{len(sources)-1})")
            source = sources[source_index]

        print(f"Connecting to NDI source: {source.ndi_name}")

        # Create NDI receiver
        self.receiver = self.ndi.recv_create_v3()
        if self.receiver is None:
            raise RuntimeError("Failed to create NDI receiver")

        # Connect to source
        self.ndi.recv_connect(self.receiver, source)

        # Wait for connection
        print("Waiting for video frames...")
        for _ in range(50):  # Try for 5 seconds
            frame = self._receive_frame()
            if frame is not None:
                print(f"✓ Connected! Receiving {frame.shape[1]}x{frame.shape[0]} video")
                self.last_frame = frame
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("No video frames received from NDI source")

    def _receive_frame(self):
        """Internal method to receive NDI frame"""
        t, v, _, _ = self.ndi.recv_capture_v2(self.receiver, 100)  # 100ms timeout

        if t == self.ndi.FRAME_TYPE_VIDEO:
            # Convert NDI frame to numpy array
            frame = np.copy(v.data)
            self.ndi.recv_free_video_v2(self.receiver, v)

            # NDI uses BGRA, convert to RGB
            if frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
            elif frame.shape[2] == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            return frame

        return None

    def capture_frame(self):
        """Capture frame from NDI source"""
        frame = self._receive_frame()

        if frame is None:
            # Return last frame if no new frame (keeps stream alive)
            return getattr(self, 'last_frame', None)

        self.last_frame = frame
        return frame

    def list_sources(self):
        """List all available NDI sources on network"""
        sources = self.ndi.find_get_current_sources(self.finder)
        return [src.ndi_name for src in sources]

    def release(self):
        """Release NDI resources"""
        if hasattr(self, 'receiver') and self.receiver:
            self.ndi.recv_destroy(self.receiver)
        if hasattr(self, 'finder') and self.finder:
            self.ndi.find_destroy(self.finder)
        self.ndi.destroy()
        print("NDI connection closed")


class WebcamDataset(LiveCameraDataset):
    """USB Webcam via OpenCV"""

    def __init__(self, device_id=0, width=1920, height=1080, **kwargs):
        super().__init__(**kwargs)

        self.cap = cv2.VideoCapture(device_id)

        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open webcam {device_id}")

        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))

        print(f"Webcam opened: {actual_width}x{actual_height} @ {actual_fps} FPS")

    def capture_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return None
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def release(self):
        if self.cap:
            self.cap.release()
        print("Webcam closed")


class RTSPStream(LiveCameraDataset):
    """RTSP/HTTP network stream"""

    def __init__(self, stream_url, **kwargs):
        super().__init__(**kwargs)

        self.cap = cv2.VideoCapture(stream_url)

        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open stream: {stream_url}")

        print(f"Connected to stream: {stream_url}")

    def capture_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return None
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def release(self):
        if self.cap:
            self.cap.release()
        print("Stream closed")


class RealSenseCamera(LiveCameraDataset):
    """Intel RealSense depth camera (D435, D455, etc.)"""

    def __init__(self, width=1280, height=720, **kwargs):
        super().__init__(**kwargs)

        import pyrealsense2 as rs

        self.pipeline = rs.pipeline()
        config = rs.config()

        config.enable_stream(rs.stream.color, width, height, rs.format.rgb8, self.fps)

        try:
            self.pipeline.start(config)
            print(f"RealSense camera started: {width}x{height} @ {self.fps} FPS")
        except Exception as e:
            raise RuntimeError(f"Failed to start RealSense camera: {e}")

    def capture_frame(self):
        import pyrealsense2 as rs

        frames = self.pipeline.wait_for_frames(timeout_ms=1000)
        color_frame = frames.get_color_frame()

        if not color_frame:
            return None

        # Convert to numpy array
        frame = np.asanyarray(color_frame.get_data())
        return frame

    def release(self):
        if hasattr(self, 'pipeline'):
            self.pipeline.stop()
        print("RealSense camera closed")


# Factory function to create appropriate camera
def create_live_camera(source_type="ndi", **kwargs):
    """Create live camera dataset

    Args:
        source_type: "ndi", "webcam", "rtsp", or "realsense"
        **kwargs: Parameters passed to specific camera class

    Returns:
        LiveCameraDataset instance

    Examples:
        # NDI from TouchDesigner
        camera = create_live_camera("ndi", source_name="TouchDesigner")

        # Webcam
        camera = create_live_camera("webcam", device_id=0)

        # RTSP stream
        camera = create_live_camera("rtsp", stream_url="rtsp://192.168.1.100:8554/stream")

        # RealSense
        camera = create_live_camera("realsense", width=1280, height=720)
    """
    cameras = {
        "ndi": NDICamera,
        "webcam": WebcamDataset,
        "rtsp": RTSPStream,
        "realsense": RealSenseCamera,
    }

    if source_type not in cameras:
        raise ValueError(f"Unknown source type: {source_type}. Choose from: {list(cameras.keys())}")

    return cameras[source_type](**kwargs)
