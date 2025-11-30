#!/usr/bin/env python3
"""
Complete Gaussian Splatting Training Pipeline
==============================================

Automated pipeline from MASt3R-SLAM output to trained Gaussian Splats

Supports:
- GLOMAP (10-100x faster than COLMAP)
- COLMAP (classic, reliable)
- Nerfstudio Splatfacto (recommended)
- OpenSplat (production-ready)
- Original Gaussian Splatting

Usage:
    # Quick training with Nerfstudio (easiest)
    python train_gaussian_splat.py --input logs/rgbd_dataset_freiburg1_plant.ply \\
                                    --keyframes logs/keyframes/ \\
                                    --method nerfstudio

    # Production training with OpenSplat
    python train_gaussian_splat.py --input logs/rgbd_dataset_freiburg1_plant.ply \\
                                    --keyframes logs/keyframes/ \\
                                    --method opensplat

    # With GLOMAP preprocessing (fastest)
    python train_gaussian_splat.py --input logs/rgbd_dataset_freiburg1_plant.ply \\
                                    --keyframes logs/keyframes/ \\
                                    --use-glomap \\
                                    --method nerfstudio
"""

import argparse
import subprocess
import pathlib
import shutil
import sys
import os


def parse_args():
    parser = argparse.ArgumentParser(
        description='Train Gaussian Splatting from MASt3R-SLAM output',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Input data
    parser.add_argument('--input', type=str, required=True,
                       help='Input PLY file from MASt3R-SLAM')
    parser.add_argument('--keyframes', type=str, required=True,
                       help='Directory containing keyframe images')
    parser.add_argument('--trajectory', type=str, default=None,
                       help='Trajectory file (.txt) with camera poses')

    # Training method
    parser.add_argument('--method', type=str, default='nerfstudio',
                       choices=['nerfstudio', 'opensplat', 'original'],
                       help='Training method (default: nerfstudio)')

    # Preprocessing
    parser.add_argument('--use-glomap', action='store_true',
                       help='Use GLOMAP for point triangulation (10-100x faster)')
    parser.add_argument('--skip-preprocessing', action='store_true',
                       help='Skip COLMAP/GLOMAP preprocessing (use sparse points only)')

    # Output
    parser.add_argument('--output', type=str, default='gaussian_splats',
                       help='Output directory for trained model')
    parser.add_argument('--export-ply', action='store_true',
                       help='Export final model as PLY')

    # Camera parameters
    parser.add_argument('--fx', type=float, default=None, help='Focal length X')
    parser.add_argument('--fy', type=float, default=None, help='Focal length Y')
    parser.add_argument('--cx', type=float, default=None, help='Principal point X')
    parser.add_argument('--cy', type=float, default=None, help='Principal point Y')

    # Training parameters
    parser.add_argument('--iterations', type=int, default=30000,
                       help='Training iterations (default: 30000)')
    parser.add_argument('--gpu', type=int, default=0,
                       help='GPU device ID')

    return parser.parse_args()


def check_dependencies(method: str, use_glomap: bool):
    """Check if required tools are installed"""
    print("Checking dependencies...")

    deps = []

    if use_glomap:
        deps.append(('glomap', 'conda install -c conda-forge glomap'))
        deps.append(('colmap', 'conda install conda-forge::colmap'))
    elif not args.skip_preprocessing:
        deps.append(('colmap', 'conda install conda-forge::colmap'))

    if method == 'nerfstudio':
        deps.append(('ns-train', 'pip install nerfstudio'))
    elif method == 'opensplat':
        deps.append(('opensplat', 'Build from https://github.com/pierotofy/OpenSplat'))

    missing = []
    for cmd, install_cmd in deps:
        if shutil.which(cmd) is None:
            missing.append((cmd, install_cmd))

    if missing:
        print("\n⚠️  Missing dependencies:")
        for cmd, install_cmd in missing:
            print(f"   - {cmd}: {install_cmd}")
        print()
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    else:
        print("✓ All dependencies found")


def run_export_to_colmap(args, colmap_dir: pathlib.Path):
    """Export SLAM data to COLMAP format"""
    print()
    print("=" * 60)
    print("Step 1: Exporting to COLMAP format")
    print("=" * 60)

    export_script = pathlib.Path(__file__).parent / 'export_to_colmap.py'

    cmd = [
        'python', str(export_script),
        '--input', args.input,
        '--keyframes', args.keyframes,
        '--output', str(colmap_dir),
    ]

    if args.trajectory:
        cmd += ['--trajectory', args.trajectory]

    if args.fx and args.fy and args.cx and args.cy:
        cmd += ['--fx', str(args.fx), '--fy', str(args.fy),
                '--cx', str(args.cx), '--cy', str(args.cy)]

    subprocess.run(cmd, check=True)


def run_glomap_preprocessing(colmap_dir: pathlib.Path):
    """Run GLOMAP point triangulation for denser reconstruction"""
    print()
    print("=" * 60)
    print("Step 2: Running GLOMAP point triangulation (10-100x faster!)")
    print("=" * 60)

    # Create database if it doesn't exist
    db_path = colmap_dir / 'database.db'
    images_path = colmap_dir / 'images'

    if not db_path.exists():
        print("Creating COLMAP database...")
        subprocess.run([
            'colmap', 'feature_extractor',
            '--database_path', str(db_path),
            '--image_path', str(images_path),
        ], check=True)

        subprocess.run([
            'colmap', 'exhaustive_matcher',
            '--database_path', str(db_path),
        ], check=True)

    # Run GLOMAP mapper
    print("Running GLOMAP mapper...")
    glomap_output = colmap_dir / 'glomap_sparse'
    glomap_output.mkdir(exist_ok=True)

    subprocess.run([
        'glomap', 'mapper',
        '--database_path', str(db_path),
        '--image_path', str(images_path),
        '--output_path', str(glomap_output),
    ], check=True)

    # Triangulate points
    print("Triangulating points with COLMAP...")
    dense_output = colmap_dir / 'dense'
    dense_output.mkdir(exist_ok=True)

    subprocess.run([
        'colmap', 'point_triangulator',
        '--database_path', str(db_path),
        '--image_path', str(images_path),
        '--input_path', str(glomap_output / '0'),  # GLOMAP output in subdir
        '--output_path', str(dense_output),
    ], check=True)

    print(f"✓ Dense reconstruction saved to {dense_output}")
    return dense_output


def run_colmap_preprocessing(colmap_dir: pathlib.Path):
    """Run classic COLMAP reconstruction"""
    print()
    print("=" * 60)
    print("Step 2: Running COLMAP preprocessing")
    print("=" * 60)

    db_path = colmap_dir / 'database.db'
    images_path = colmap_dir / 'images'
    sparse_output = colmap_dir / 'sparse'
    sparse_output.mkdir(exist_ok=True)

    # Feature extraction
    print("Extracting features...")
    subprocess.run([
        'colmap', 'feature_extractor',
        '--database_path', str(db_path),
        '--image_path', str(images_path),
    ], check=True)

    # Feature matching
    print("Matching features...")
    subprocess.run([
        'colmap', 'exhaustive_matcher',
        '--database_path', str(db_path),
    ], check=True)

    # Mapping
    print("Running mapper...")
    subprocess.run([
        'colmap', 'mapper',
        '--database_path', str(db_path),
        '--image_path', str(images_path),
        '--output_path', str(sparse_output),
    ], check=True)

    # Dense reconstruction
    print("Dense reconstruction...")
    dense_output = colmap_dir / 'dense'
    dense_output.mkdir(exist_ok=True)

    subprocess.run([
        'colmap', 'image_undistorter',
        '--image_path', str(images_path),
        '--input_path', str(sparse_output / '0'),
        '--output_path', str(dense_output),
    ], check=True)

    return dense_output


def train_nerfstudio(colmap_dir: pathlib.Path, output_dir: pathlib.Path, args):
    """Train Gaussian Splatting with Nerfstudio Splatfacto"""
    print()
    print("=" * 60)
    print("Step 3: Training with Nerfstudio Splatfacto")
    print("=" * 60)

    cmd = [
        'ns-train', 'splatfacto',
        '--data', str(colmap_dir),
        '--output-dir', str(output_dir),
        '--max-num-iterations', str(args.iterations),
        '--pipeline.model.cull-alpha-thresh', '0.005',
        '--pipeline.model.continue-cull-post-densification', 'False',
    ]

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env={**os.environ, 'CUDA_VISIBLE_DEVICES': str(args.gpu)})

    print()
    print("✓ Training complete!")
    print()
    print(f"View results: ns-viewer --load-config {output_dir}/splatfacto/*/config.yml")

    if args.export_ply:
        print()
        print("Exporting to PLY...")
        export_cmd = [
            'ns-export', 'gaussian-splat',
            '--load-config', str(output_dir / 'splatfacto' / '*' / 'config.yml'),
            '--output-dir', str(output_dir / 'exports'),
        ]
        subprocess.run(' '.join(export_cmd), shell=True, check=True)
        print(f"✓ Exported to {output_dir / 'exports'}")


def train_opensplat(colmap_dir: pathlib.Path, output_dir: pathlib.Path, args):
    """Train with OpenSplat"""
    print()
    print("=" * 60)
    print("Step 3: Training with OpenSplat")
    print("=" * 60)

    output_ply = output_dir / 'splat.ply'

    cmd = [
        'opensplat',
        str(colmap_dir),
        '--ply-output', str(output_ply),
        '--iterations', str(args.iterations),
    ]

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env={**os.environ, 'CUDA_VISIBLE_DEVICES': str(args.gpu)})

    print()
    print("✓ Training complete!")
    print(f"Output: {output_ply}")


def train_original_gs(colmap_dir: pathlib.Path, output_dir: pathlib.Path, args):
    """Train with original Gaussian Splatting implementation"""
    print()
    print("=" * 60)
    print("Step 3: Training with Original Gaussian Splatting")
    print("=" * 60)

    # Assumes original gaussian-splatting repo is available
    gs_repo = pathlib.Path.home() / 'gaussian-splatting'

    if not gs_repo.exists():
        print(f"⚠️  Original Gaussian Splatting not found at {gs_repo}")
        print("   Clone from: https://github.com/graphdeco-inria/gaussian-splatting")
        sys.exit(1)

    cmd = [
        'python', str(gs_repo / 'train.py'),
        '-s', str(colmap_dir),
        '-m', str(output_dir),
        '--iterations', str(args.iterations),
    ]

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env={**os.environ, 'CUDA_VISIBLE_DEVICES': str(args.gpu)})

    print()
    print("✓ Training complete!")
    print(f"Output: {output_dir}")


def main():
    global args
    args = parse_args()

    print("=" * 60)
    print("Gaussian Splatting Training Pipeline")
    print("=" * 60)
    print()
    print(f"Input PLY: {args.input}")
    print(f"Keyframes: {args.keyframes}")
    print(f"Method: {args.method}")
    print(f"Preprocessing: {'GLOMAP' if args.use_glomap else 'COLMAP' if not args.skip_preprocessing else 'None'}")
    print()

    # Check dependencies
    check_dependencies(args.method, args.use_glomap)

    # Setup directories
    output_dir = pathlib.Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    colmap_dir = output_dir / 'colmap_data'
    colmap_dir.mkdir(exist_ok=True)

    # Step 1: Export to COLMAP format
    run_export_to_colmap(args, colmap_dir)

    # Step 2: Preprocessing (optional)
    if args.use_glomap:
        dense_dir = run_glomap_preprocessing(colmap_dir)
        training_input = dense_dir
    elif not args.skip_preprocessing:
        dense_dir = run_colmap_preprocessing(colmap_dir)
        training_input = dense_dir
    else:
        training_input = colmap_dir

    # Step 3: Train Gaussian Splatting
    if args.method == 'nerfstudio':
        train_nerfstudio(training_input, output_dir, args)
    elif args.method == 'opensplat':
        train_opensplat(training_input, output_dir, args)
    elif args.method == 'original':
        train_original_gs(training_input, output_dir, args)

    print()
    print("=" * 60)
    print("✓ Pipeline complete!")
    print("=" * 60)
    print()


if __name__ == '__main__':
    main()
