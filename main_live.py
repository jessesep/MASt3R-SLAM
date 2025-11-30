#!/usr/bin/env python3
"""
MASt3R-SLAM Live Camera Mode with TouchDesigner Integration

Supports:
- NDI (Network Device Interface) from TouchDesigner
- USB Webcams
- Intel RealSense cameras
- RTSP/HTTP streams
- Image folder watching (for TouchDesigner file output)
- OSC streaming back to TouchDesigner

Usage examples:

# Webcam
python main_live.py --source webcam

# NDI from TouchDesigner
python main_live.py --source ndi --ndi-name "TouchDesigner Output"

# Image folder watching (TouchDesigner file output)
python main_live.py --source folder --watch-path /mnt/c/TD/frames/

# With OSC streaming back to TouchDesigner
python main_live.py --source webcam --osc-enable --osc-port 9001

"""

import argparse
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from mast3r_slam.config import load_config, config
from mast3r_slam.live_camera import create_live_camera, NDICamera, WebcamDataset, RealSenseCamera, RTSPStream
from mast3r_slam.file_watcher import ImageFolderWatcher, ImageSequenceDataset
from mast3r_slam.osc_streamer import OSCStreamer
from mast3r_slam.command_listener import CommandListener, CommandHandler
from mast3r_slam.dataloader import load_dataset
from mast3r_slam.mast3r_utils import get_mast3r_model_from_cfg
import torch
import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(description='MASt3R-SLAM Live Camera Mode')

    # Camera source selection
    parser.add_argument('--source', type=str, default='webcam',
                       choices=['webcam', 'ndi', 'realsense', 'rtsp', 'folder', 'sequence'],
                       help='Camera source type')

    # Source-specific options
    parser.add_argument('--device-id', type=int, default=0,
                       help='Webcam device ID (default: 0)')
    parser.add_argument('--ndi-name', type=str, default=None,
                       help='NDI source name (e.g., "TouchDesigner Output")')
    parser.add_argument('--ndi-index', type=int, default=0,
                       help='NDI source index if name not specified')
    parser.add_argument('--rtsp-url', type=str, default=None,
                       help='RTSP stream URL')
    parser.add_argument('--watch-path', type=str, default=None,
                       help='Folder to watch for new images (TouchDesigner file output)')
    parser.add_argument('--sequence-path', type=str, default=None,
                       help='Path to pre-recorded image sequence')

    # Camera settings
    parser.add_argument('--width', type=int, default=1920,
                       help='Camera width (default: 1920)')
    parser.add_argument('--height', type=int, default=1080,
                       help='Camera height (default: 1080)')
    parser.add_argument('--fps', type=float, default=30.0,
                       help='Target FPS (default: 30)')

    # SLAM configuration
    parser.add_argument('--config', type=str, default='config/calib.yaml',
                       help='SLAM config file')

    # OSC streaming (to TouchDesigner)
    parser.add_argument('--osc-enable', action='store_true',
                       help='Enable OSC streaming to TouchDesigner')
    parser.add_argument('--osc-host', type=str, default='127.0.0.1',
                       help='OSC destination host (default: localhost)')
    parser.add_argument('--osc-port', type=int, default=9001,
                       help='OSC destination port (default: 9001)')
    parser.add_argument('--osc-downsample', type=int, default=10,
                       help='Send every Nth point via OSC (default: 10)')

    # Visualization
    parser.add_argument('--no-viz', action='store_true',
                       help='Disable visualization window')

    # Processing options
    parser.add_argument('--max-frames', type=int, default=None,
                       help='Maximum frames to process (default: infinite)')

    # Output
    parser.add_argument('--output-dir', type=str, default='results/live',
                       help='Output directory for results')
    parser.add_argument('--save-ply', action='store_true',
                       help='Save point cloud as PLY file')

    return parser.parse_args()


def create_camera_dataset(args):
    """Create appropriate camera dataset based on args"""

    if args.source == 'webcam':
        print(f"Creating webcam dataset (device {args.device_id})")
        return WebcamDataset(
            device_id=args.device_id,
            width=args.width,
            height=args.height,
            fps=args.fps,
            max_frames=args.max_frames
        )

    elif args.source == 'ndi':
        print("Creating NDI camera dataset")
        return NDICamera(
            source_name=args.ndi_name,
            source_index=args.ndi_index if args.ndi_name is None else 0,
            fps=args.fps,
            max_frames=args.max_frames
        )

    elif args.source == 'realsense':
        print("Creating RealSense camera dataset")
        return RealSenseCamera(
            width=args.width,
            height=args.height,
            fps=args.fps,
            max_frames=args.max_frames
        )

    elif args.source == 'rtsp':
        if args.rtsp_url is None:
            raise ValueError("--rtsp-url required for RTSP source")
        print(f"Creating RTSP stream: {args.rtsp_url}")
        return RTSPStream(
            stream_url=args.rtsp_url,
            fps=args.fps,
            max_frames=args.max_frames
        )

    elif args.source == 'folder':
        if args.watch_path is None:
            raise ValueError("--watch-path required for folder watching")
        print(f"Creating image folder watcher: {args.watch_path}")
        return ImageFolderWatcher(
            watch_path=args.watch_path,
            poll_interval=1.0/args.fps
        )

    elif args.source == 'sequence':
        if args.sequence_path is None:
            raise ValueError("--sequence-path required for sequence playback")
        print(f"Loading image sequence: {args.sequence_path}")
        return ImageSequenceDataset(
            sequence_path=args.sequence_path,
            fps=args.fps
        )

    else:
        raise ValueError(f"Unknown source type: {args.source}")


def main():
    args = parse_args()

    # Load SLAM config
    print(f"Loading config: {args.config}")
    load_config(args.config)

    # Create camera dataset
    try:
        dataset = create_camera_dataset(args)
    except Exception as e:
        print(f"Error creating camera dataset: {e}")
        sys.exit(1)

    # Initialize OSC streamer if enabled
    osc_streamer = None
    if args.osc_enable:
        print(f"Enabling OSC streaming to {args.osc_host}:{args.osc_port}")
        osc_streamer = OSCStreamer(
            host=args.osc_host,
            port=args.osc_port,
            downsample=args.osc_downsample,
            enabled=True
        )
        osc_streamer.start()

    # Get image shape
    print("Initializing SLAM...")
    H, W = dataset.get_img_shape()

    # Load MASt3R model
    print("Loading MASt3R model...")
    mast3r_model = get_mast3r_model_from_cfg()

    # Initialize SLAM
    slam = SLAM(mast3r_model, H=H[0], W=H[1])

    # Initialize command listener (for Control GUI)
    cmd_listener = CommandListener()
    cmd_handler = CommandHandler(slam)
    cmd_listener.start()
    print("Command listener started (Control GUI ready)")

    # Set up visualization
    if not args.no_viz:
        from mast3r_slam.visualization import SLAMVisualizer
        viz = SLAMVisualizer(slam)
    else:
        viz = None

    # Main processing loop
    print("\nStarting live SLAM processing...")
    print("Press Ctrl+C to stop\n")

    frame_count = 0
    try:
        for idx in range(len(dataset)):
            # Check for commands from Control GUI
            while cmd_listener.has_commands():
                command = cmd_listener.get_command()
                if command:
                    cmd_handler.handle_command(command)

            # Skip frame if paused
            if cmd_handler.is_paused():
                time.sleep(0.1)
                continue

            # Get frame
            timestamp, img = dataset[idx]
            frame_count += 1

            # Process with SLAM
            slam.process_frame(img, timestamp)

            # Update visualization
            if viz is not None:
                viz.update()

                # Check if window closed
                if not viz.is_running():
                    print("Visualization window closed")
                    break

            # Send OSC data to TouchDesigner
            if osc_streamer is not None and osc_streamer.enabled:
                # Get current point cloud
                if slam.pointmap is not None:
                    points = slam.pointmap.get_points()
                    colors = slam.pointmap.get_colors()
                    confidence = slam.pointmap.get_confidence()

                    if points is not None and len(points) > 0:
                        osc_streamer.send_point_cloud(points, colors, confidence)

                # Send camera pose
                if len(slam.keyframes) > 0:
                    latest_kf = slam.keyframes[-1]
                    pose = latest_kf.get_pose()
                    if pose is not None:
                        position = pose[:3, 3]
                        rotation = pose[:3, :3]
                        osc_streamer.send_camera_pose(position, rotation)

                # Send status
                fps = slam.get_fps()
                num_keyframes = len(slam.keyframes)
                num_points = len(points) if points is not None else 0
                osc_streamer.send_status(fps, num_keyframes, num_points)

            # Check if max frames reached
            if args.max_frames and frame_count >= args.max_frames:
                print(f"\nReached max frames: {args.max_frames}")
                break

    except KeyboardInterrupt:
        print("\n\nStopped by user")

    except Exception as e:
        print(f"\nError during processing: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        print("\nCleaning up...")

        if cmd_listener is not None:
            cmd_listener.stop()

        if osc_streamer is not None:
            osc_streamer.stop()

        if hasattr(dataset, 'release'):
            dataset.release()

        if viz is not None:
            viz.close()

        # Save results if requested
        if args.save_ply:
            output_path = Path(args.output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            ply_file = output_path / f"live_{args.source}_{frame_count}frames.ply"

            print(f"Saving point cloud to {ply_file}...")
            slam.save_pointcloud(str(ply_file))
            print("Saved!")

        print(f"\nProcessed {frame_count} frames")
        print(f"Final FPS: {slam.get_fps():.2f}")
        print(f"Keyframes: {len(slam.keyframes)}")


if __name__ == '__main__':
    main()
