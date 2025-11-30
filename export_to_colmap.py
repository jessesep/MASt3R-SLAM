#!/usr/bin/env python3
"""
Export MASt3R-SLAM reconstruction to COLMAP/GLOMAP format
for Gaussian Splatting training

This script converts SLAM output to COLMAP sparse reconstruction format:
- cameras.txt: Camera intrinsics
- images.txt: Camera poses and keyframe images
- points3D.txt: Sparse 3D point cloud

Compatible with:
- GLOMAP (10-100x faster than COLMAP)
- COLMAP point triangulation
- Nerfstudio Splatfacto
- OpenSplat
- Original Gaussian Splatting implementations

Usage:
    python export_to_colmap.py --input logs/rgbd_dataset_freiburg1_plant.ply \
                                --keyframes logs/keyframes/ \
                                --output colmap_exports/plant/
"""

import argparse
import pathlib
import shutil
import struct
from typing import List, Tuple
import numpy as np
import torch
from plyfile import PlyData
import cv2


def parse_args():
    parser = argparse.ArgumentParser(description='Export MASt3R-SLAM to COLMAP format')

    parser.add_argument('--input', type=str, required=True,
                       help='Input PLY file from MASt3R-SLAM')
    parser.add_argument('--keyframes', type=str, required=True,
                       help='Directory containing keyframe images')
    parser.add_argument('--trajectory', type=str, default=None,
                       help='Trajectory file (.txt) with camera poses')
    parser.add_argument('--output', type=str, required=True,
                       help='Output directory for COLMAP format')
    parser.add_argument('--downsample-points', type=int, default=1,
                       help='Downsample point cloud (1=no downsample, 10=keep every 10th point)')
    parser.add_argument('--binary', action='store_true',
                       help='Export in binary format (faster, smaller files)')
    parser.add_argument('--camera-model', type=str, default='PINHOLE',
                       choices=['PINHOLE', 'SIMPLE_PINHOLE', 'RADIAL'],
                       help='COLMAP camera model')

    # Camera intrinsics (can be estimated if not provided)
    parser.add_argument('--fx', type=float, default=None, help='Focal length X')
    parser.add_argument('--fy', type=float, default=None, help='Focal length Y')
    parser.add_argument('--cx', type=float, default=None, help='Principal point X')
    parser.add_argument('--cy', type=float, default=None, help='Principal point Y')
    parser.add_argument('--width', type=int, default=640, help='Image width')
    parser.add_argument('--height', type=int, default=480, help='Image height')

    return parser.parse_args()


def estimate_intrinsics(width: int, height: int) -> Tuple[float, float, float, float]:
    """Estimate camera intrinsics if not provided"""
    # Common heuristic: fx = fy = max(width, height)
    f = max(width, height)
    fx = fy = f
    cx = width / 2.0
    cy = height / 2.0
    print(f"⚠️  Estimated intrinsics: fx={fx}, fy={fy}, cx={cx}, cy={cy}")
    print("   For better results, provide actual camera intrinsics!")
    return fx, fy, cx, cy


def load_ply_points(ply_path: str, downsample: int = 1) -> Tuple[np.ndarray, np.ndarray]:
    """Load points and colors from PLY file"""
    print(f"Loading PLY: {ply_path}")
    ply_data = PlyData.read(ply_path)
    vertex = ply_data['vertex']

    points = np.vstack([vertex['x'], vertex['y'], vertex['z']]).T
    colors = np.vstack([vertex['red'], vertex['green'], vertex['blue']]).T

    if downsample > 1:
        points = points[::downsample]
        colors = colors[::downsample]
        print(f"Downsampled to {len(points)} points (factor: {downsample})")

    print(f"Loaded {len(points)} points")
    return points, colors


def parse_trajectory(traj_path: str) -> List[Tuple[float, np.ndarray, np.ndarray]]:
    """
    Parse TUM trajectory format: timestamp tx ty tz qx qy qz qw
    Returns: [(timestamp, translation, quaternion), ...]
    """
    poses = []
    with open(traj_path, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                parts = line.strip().split()
                timestamp = float(parts[0])
                tx, ty, tz = float(parts[1]), float(parts[2]), float(parts[3])
                qx, qy, qz, qw = float(parts[4]), float(parts[5]), float(parts[6]), float(parts[7])

                translation = np.array([tx, ty, tz])
                quaternion = np.array([qw, qx, qy, qz])  # COLMAP uses qw first

                poses.append((timestamp, translation, quaternion))

    return poses


def get_image_files(keyframes_dir: str) -> List[pathlib.Path]:
    """Get sorted list of keyframe images"""
    keyframes_path = pathlib.Path(keyframes_dir)

    # Support multiple image formats
    image_files = []
    for ext in ['*.png', '*.jpg', '*.jpeg']:
        image_files.extend(sorted(keyframes_path.glob(ext)))

    print(f"Found {len(image_files)} keyframe images")
    return sorted(image_files)


def write_cameras_txt(output_dir: pathlib.Path, fx, fy, cx, cy, width, height, model='PINHOLE'):
    """
    Write cameras.txt in COLMAP format

    Format:
    # CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]
    1 PINHOLE 640 480 fx fy cx cy
    """
    cameras_file = output_dir / 'cameras.txt'

    with open(cameras_file, 'w') as f:
        f.write("# Camera list with one line of data per camera:\n")
        f.write("#   CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n")
        f.write(f"# Number of cameras: 1\n")

        if model == 'PINHOLE':
            f.write(f"1 PINHOLE {width} {height} {fx} {fy} {cx} {cy}\n")
        elif model == 'SIMPLE_PINHOLE':
            f.write(f"1 SIMPLE_PINHOLE {width} {height} {fx} {cx} {cy}\n")
        elif model == 'RADIAL':
            f.write(f"1 RADIAL {width} {height} {fx} {cx} {cy} 0 0\n")

    print(f"✓ Wrote {cameras_file}")


def quaternion_to_rotation_matrix(q: np.ndarray) -> np.ndarray:
    """Convert quaternion [qw, qx, qy, qz] to 3x3 rotation matrix"""
    qw, qx, qy, qz = q

    R = np.array([
        [1 - 2*(qy**2 + qz**2), 2*(qx*qy - qw*qz), 2*(qx*qz + qw*qy)],
        [2*(qx*qy + qw*qz), 1 - 2*(qx**2 + qz**2), 2*(qy*qz - qw*qx)],
        [2*(qx*qz - qw*qy), 2*(qy*qz + qw*qx), 1 - 2*(qx**2 + qy**2)]
    ])

    return R


def write_images_txt(output_dir: pathlib.Path, image_files: List[pathlib.Path],
                     poses: List[Tuple[float, np.ndarray, np.ndarray]] = None):
    """
    Write images.txt in COLMAP format

    Format:
    # IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME
    # POINTS2D[] as (X, Y, POINT3D_ID)
    """
    images_file = output_dir / 'images.txt'

    with open(images_file, 'w') as f:
        f.write("# Image list with two lines of data per image:\n")
        f.write("#   IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n")
        f.write("#   POINTS2D[] as (X, Y, POINT3D_ID)\n")
        f.write(f"# Number of images: {len(image_files)}\n")

        for i, img_file in enumerate(image_files):
            image_id = i + 1

            if poses and i < len(poses):
                timestamp, translation, quaternion = poses[i]
                qw, qx, qy, qz = quaternion
                tx, ty, tz = translation
            else:
                # Identity pose if no trajectory provided
                qw, qx, qy, qz = 1.0, 0.0, 0.0, 0.0
                tx, ty, tz = 0.0, 0.0, 0.0

            camera_id = 1
            name = img_file.name

            f.write(f"{image_id} {qw} {qx} {qy} {qz} {tx} {ty} {tz} {camera_id} {name}\n")
            f.write("\n")  # Empty line for POINTS2D

    print(f"✓ Wrote {images_file}")


def write_points3D_txt(output_dir: pathlib.Path, points: np.ndarray, colors: np.ndarray):
    """
    Write points3D.txt in COLMAP format

    Format:
    # POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[] as (IMAGE_ID, POINT2D_IDX)
    """
    points3d_file = output_dir / 'points3D.txt'

    with open(points3d_file, 'w') as f:
        f.write("# 3D point list with one line of data per point:\n")
        f.write("#   POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[] as (IMAGE_ID, POINT2D_IDX)\n")
        f.write(f"# Number of points: {len(points)}\n")

        for i, (point, color) in enumerate(zip(points, colors)):
            point_id = i + 1
            x, y, z = point
            r, g, b = color.astype(int)
            error = 0.0  # Reprojection error (unknown for SLAM output)

            # No track information for SLAM points (could be added if correspondences are tracked)
            f.write(f"{point_id} {x} {y} {z} {r} {g} {b} {error}\n")

    print(f"✓ Wrote {points3d_file} ({len(points)} points)")


def copy_images(output_dir: pathlib.Path, image_files: List[pathlib.Path]):
    """Copy keyframe images to COLMAP structure"""
    images_dir = output_dir / 'images'
    images_dir.mkdir(exist_ok=True)

    for img_file in image_files:
        dst = images_dir / img_file.name
        shutil.copy2(img_file, dst)

    print(f"✓ Copied {len(image_files)} images to {images_dir}")


def main():
    args = parse_args()

    # Setup output directory
    output_dir = pathlib.Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("MASt3R-SLAM → COLMAP/GLOMAP Export")
    print("=" * 60)
    print()

    # Load point cloud
    points, colors = load_ply_points(args.input, args.downsample_points)

    # Get keyframe images
    image_files = get_image_files(args.keyframes)

    if len(image_files) == 0:
        print("⚠️  No keyframe images found! Continuing without images...")
        image_files = []

    # Parse trajectory if provided
    poses = None
    if args.trajectory:
        print(f"Loading trajectory: {args.trajectory}")
        poses = parse_trajectory(args.trajectory)
        print(f"Loaded {len(poses)} camera poses")
    else:
        print("⚠️  No trajectory file provided. Using identity poses.")

    # Determine intrinsics
    if args.fx and args.fy and args.cx and args.cy:
        fx, fy, cx, cy = args.fx, args.fy, args.cx, args.cy
        print(f"Using provided intrinsics: fx={fx}, fy={fy}, cx={cx}, cy={cy}")
    else:
        # Try to get image dimensions from first image
        if image_files:
            img = cv2.imread(str(image_files[0]))
            height, width = img.shape[:2]
        else:
            width, height = args.width, args.height

        fx, fy, cx, cy = estimate_intrinsics(width, height)

    # Export COLMAP format
    print()
    print("Exporting COLMAP sparse reconstruction...")
    print(f"Output: {output_dir}")
    print()

    write_cameras_txt(output_dir, fx, fy, cx, cy, width, height, args.camera_model)
    write_images_txt(output_dir, image_files, poses)
    write_points3D_txt(output_dir, points, colors)

    if image_files:
        copy_images(output_dir, image_files)

    print()
    print("=" * 60)
    print("✓ Export complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print()
    print("1. Densify with GLOMAP (recommended, 10-100x faster):")
    print(f"   colmap point_triangulator \\")
    print(f"       --database_path {output_dir}/database.db \\")
    print(f"       --image_path {output_dir}/images \\")
    print(f"       --input_path {output_dir} \\")
    print(f"       --output_path {output_dir}/dense")
    print()
    print("2. Train Gaussian Splatting with Nerfstudio:")
    print(f"   ns-train splatfacto --data {output_dir}")
    print()
    print("3. Or use OpenSplat:")
    print(f"   opensplat {output_dir} --ply-output splat.ply")
    print()


if __name__ == '__main__':
    main()
