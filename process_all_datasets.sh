#!/bin/bash
# Process multiple TUM datasets and generate PLY files

source /home/sep/miniconda3/etc/profile.d/conda.sh
conda activate mast3r-slam-blackwell

# Dataset list
DATASETS=(
    "rgbd_dataset_freiburg1_desk"
    "rgbd_dataset_freiburg1_room"
    "rgbd_dataset_freiburg1_xyz"
    "rgbd_dataset_freiburg1_plant"
    "rgbd_dataset_freiburg1_teddy"
)

echo "Processing ${#DATASETS[@]} datasets..."

for dataset in "${DATASETS[@]}"; do
    echo "======================================"
    echo "Processing: $dataset"
    echo "======================================"

    python main.py \
        --dataset "datasets/tum/${dataset}/" \
        --config config/calib.yaml \
        --no-viz

    echo "Completed: $dataset"
    echo "PLY output: results/tum/${dataset}/${dataset}.ply"
    echo ""
done

echo "All datasets processed!"
echo ""
echo "PLY files location:"
for dataset in "${DATASETS[@]}"; do
    echo "  - results/tum/${dataset}/${dataset}.ply"
done
